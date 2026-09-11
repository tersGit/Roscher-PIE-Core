"""Typed, opt-in parcel-bound geometry evidence.

This module measures caller-supplied masks only.  It deliberately does not
detect objects, fetch imagery, score candidates, or modify Funnel v1.2/v1.3.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Iterable

import cv2
import numpy as np

from backend.retrieval_funnel.hierarchical_v1_2 import Compatibility, ObservableEvidence
from backend.retrieval_funnel.hierarchical_v1_3 import RescueActivation, StandSizeGateResult

PARCEL_BOUND_GEOMETRY_VERSION = "PARCEL_BOUND_GEOMETRY_V1"
MIN_BINDING_COVERAGE = 0.98
OUTSIDE_MAX_INTERSECTION = 0.05


class Observability(str, Enum):
    OBSERVED = "OBSERVED"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"


class Binding(str, Enum):
    PARCEL_BOUND = "PARCEL_BOUND"
    AMBIGUOUS = "AMBIGUOUS"
    OUTSIDE_PARCEL = "OUTSIDE_PARCEL"
    UNKNOWN = "UNKNOWN"


class Quality(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class WaterCount(str, Enum):
    ONE = "1"
    TWO_OR_MORE = "2+"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class SourceMetadata:
    parcel_id: str
    source_image: str | None = None
    source_date: str | None = None
    resolution_m_per_px: float | None = None
    frame: str = "candidate_aerial_parcel_crop"
    viewpoint: str = "NADIR"
    mask_source: str = "caller_supplied"


@dataclass(frozen=True)
class BindingAssessment:
    binding: Binding
    object_coverage: float | None
    parcel_coverage: float | None
    confidence: float | None
    reason: str


@dataclass(frozen=True)
class ObjectGeometry:
    observability: Observability
    binding: BindingAssessment
    quality: Quality
    mask_valid: bool
    object_confidence: float | None
    centroid_normalized_parcel: tuple[float, float] | None = None
    area_px: float | None = None
    area_to_parcel_ratio: float | None = None
    aspect_ratio: float | None = None
    major_orientation_deg: float | None = None
    rectangularity: float | None = None
    compactness: float | None = None
    convexity: float | None = None
    elongation: float | None = None
    obb: tuple[float, float, float, float, float] | None = None
    nearest_boundary_distance_px: float | None = None
    nearest_boundary_side: str | None = None
    relative_parcel_position: str | None = None
    complexity: float | None = None
    wings_or_protrusions: int | None = None
    courtyard_supported: bool | None = None
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class MultipleWaterEvidence:
    count: WaterCount
    secondary_observability: Observability
    relative_area: float | None = None
    centroid_separation_normalized_parcel: float | None = None
    adjacency: str = "UNKNOWN"
    orientation_relation: str = "UNKNOWN"
    relative_position: str = "UNKNOWN"


@dataclass(frozen=True)
class RelationGeometry:
    quality: Quality
    pool_to_building_centroid: tuple[float, float] | None = None
    centroid_separation_normalized_parcel: float | None = None
    nearest_edge_separation_px: float | None = None
    pool_to_building_area_ratio: float | None = None
    side: str | None = None
    axis_angle_deg: float | None = None
    axis_relation: str = "UNKNOWN"
    facade_adjacency: str = "UNKNOWN"
    partial_enclosure_supported: bool | None = None
    pool_position: str = "UNKNOWN"
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ParcelBoundGeometryRecord:
    schema_version: str
    metadata: SourceMetadata
    pool: ObjectGeometry
    building: ObjectGeometry
    multiple_water: MultipleWaterEvidence
    relation: RelationGeometry

    def to_dict(self) -> dict:
        return asdict(self)


def geometry_candidate_ids(
    gate: StandSizeGateResult, rescue: RescueActivation | None = None
) -> tuple[str, ...]:
    """Return only v1.3-normal IDs, plus IDs actually activated for rescue."""
    if not gate.gate_enabled:
        return gate.normal_candidate_ids
    ids = list(gate.normal_candidate_ids)
    if rescue and rescue.activated:
        if any(level.value == "C" for level in rescue.levels):
            ids.extend(gate.rescue_c_ids)
        if any(level.value == "D" for level in rescue.levels):
            ids.extend(gate.rescue_d_ids)
    return tuple(ids)


def assess_binding(mask: np.ndarray | None, parcel_mask: np.ndarray | None) -> BindingAssessment:
    if mask is None or parcel_mask is None or mask.shape != parcel_mask.shape:
        return BindingAssessment(Binding.UNKNOWN, None, None, None, "missing_or_incompatible_mask")
    obj = np.asarray(mask, dtype=bool)
    parcel = np.asarray(parcel_mask, dtype=bool)
    size = int(obj.sum())
    if not size:
        return BindingAssessment(Binding.UNKNOWN, None, None, None, "empty_object_mask")
    overlap = int(np.logical_and(obj, parcel).sum())
    object_coverage = overlap / size
    parcel_coverage = overlap / max(int(parcel.sum()), 1)
    if object_coverage <= OUTSIDE_MAX_INTERSECTION:
        return BindingAssessment(Binding.OUTSIDE_PARCEL, object_coverage, parcel_coverage, 1.0, "outside_parcel")
    if object_coverage < MIN_BINDING_COVERAGE:
        return BindingAssessment(Binding.AMBIGUOUS, object_coverage, parcel_coverage, object_coverage, "materially_crosses_boundary")
    return BindingAssessment(Binding.PARCEL_BOUND, object_coverage, parcel_coverage, object_coverage, "coverage_meets_preregistered_threshold")


def _contour(mask: np.ndarray) -> np.ndarray | None:
    contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return max(contours, key=cv2.contourArea) if contours else None


def _parcel_coordinates(parcel: np.ndarray, x: float, y: float) -> tuple[float, float]:
    ys, xs = np.where(parcel)
    return (
        (x - float(xs.min())) / max(float(xs.max() - xs.min()), 1.0),
        (y - float(ys.min())) / max(float(ys.max() - ys.min()), 1.0),
    )


def _boundary_metrics(parcel: np.ndarray, x: float, y: float) -> tuple[float, str, str]:
    ys, xs = np.where(parcel)
    left, right, top, bottom = float(xs.min()), float(xs.max()), float(ys.min()), float(ys.max())
    distances = {"WEST": x - left, "EAST": right - x, "NORTH": y - top, "SOUTH": bottom - y}
    side = min(distances, key=distances.get)
    nx, ny = _parcel_coordinates(parcel, x, y)
    return distances[side], side, ("CENTRAL" if .25 <= nx <= .75 and .25 <= ny <= .75 else side)


def measure_object(
    mask: np.ndarray | None,
    parcel_mask: np.ndarray | None,
    *,
    confidence: float | None = None,
    observability: Observability = Observability.UNKNOWN,
    building: bool = False,
) -> ObjectGeometry:
    binding = assess_binding(mask, parcel_mask)
    if mask is None or parcel_mask is None or mask.shape != parcel_mask.shape or not np.any(mask):
        return ObjectGeometry(observability, binding, Quality.UNKNOWN, False, confidence, notes=(binding.reason,))
    if binding.binding == Binding.OUTSIDE_PARCEL:
        return ObjectGeometry(observability, binding, Quality.UNKNOWN, True, confidence, notes=("outside_objects_cannot_discriminate",))
    contour = _contour(np.asarray(mask, dtype=bool))
    if contour is None:
        return ObjectGeometry(observability, binding, Quality.UNKNOWN, False, confidence, notes=("contour_unavailable",))
    area = float(cv2.contourArea(contour))
    perimeter = float(cv2.arcLength(contour, True))
    if area <= 0 or perimeter <= 0:
        return ObjectGeometry(observability, binding, Quality.UNKNOWN, False, confidence, notes=("degenerate_contour",))
    moments = cv2.moments(contour)
    x, y = moments["m10"] / moments["m00"], moments["m01"] / moments["m00"]
    (_, _), (width, height), angle = cv2.minAreaRect(contour)
    major, minor = max(width, height), max(min(width, height), 1e-6)
    orientation = (angle + (90 if height > width else 0)) % 180
    hull = cv2.convexHull(contour)
    hull_area = max(float(cv2.contourArea(hull)), 1e-6)
    distance, side, position = _boundary_metrics(np.asarray(parcel_mask, dtype=bool), x, y)
    quality = Quality.HIGH if binding.binding == Binding.PARCEL_BOUND and observability == Observability.OBSERVED else Quality.MEDIUM if binding.binding == Binding.PARCEL_BOUND else Quality.LOW
    approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
    return ObjectGeometry(
        observability, binding, quality, True, confidence,
        tuple(round(value, 4) for value in _parcel_coordinates(np.asarray(parcel_mask, dtype=bool), x, y)),
        round(area, 2), round(area / max(float(np.asarray(parcel_mask, dtype=bool).sum()), 1.0), 5),
        round(major / minor, 4), round(orientation, 2),
        round(area / max(major * minor, 1e-6), 4), round(4 * math.pi * area / (perimeter * perimeter), 4),
        round(area / hull_area, 4), round(major / minor, 4),
        tuple(round(value, 2) for value in (x, y, major, minor, orientation)),
        round(distance, 2), side, position,
        round(perimeter * perimeter / (4 * math.pi * area), 4) if building else None,
        max(0, len(approx) - 4) if building else None, None,
    )


def _relation(
    pool: ObjectGeometry, building: ObjectGeometry,
    pool_mask: np.ndarray | None = None, building_mask: np.ndarray | None = None,
) -> RelationGeometry:
    if pool.quality not in {Quality.HIGH, Quality.MEDIUM} or building.quality not in {Quality.HIGH, Quality.MEDIUM}:
        return RelationGeometry(Quality.UNKNOWN, notes=("requires_reliable_parcel_bound_pool_and_building",))
    assert pool.centroid_normalized_parcel and building.centroid_normalized_parcel
    dx = pool.centroid_normalized_parcel[0] - building.centroid_normalized_parcel[0]
    dy = pool.centroid_normalized_parcel[1] - building.centroid_normalized_parcel[1]
    angle = abs((pool.major_orientation_deg or 0) - (building.major_orientation_deg or 0)) % 180
    angle = min(angle, 180 - angle)
    axis = "PARALLEL" if angle <= 20 else "PERPENDICULAR" if 70 <= angle <= 110 else "OBLIQUE"
    side = "EAST" if abs(dx) >= abs(dy) and dx > 0 else "WEST" if abs(dx) >= abs(dy) else "SOUTH" if dy > 0 else "NORTH"
    edge_distance = None
    if pool_mask is not None and building_mask is not None:
        if np.logical_and(pool_mask, building_mask).any():
            edge_distance = 0.0
        else:
            distances = cv2.distanceTransform(np.logical_not(building_mask).astype(np.uint8), cv2.DIST_L2, 3)
            edge_distance = round(float(distances[np.asarray(pool_mask, dtype=bool)].min()), 2)
    return RelationGeometry(
        Quality.HIGH if pool.quality == building.quality == Quality.HIGH else Quality.MEDIUM,
        (round(dx, 4), round(dy, 4)), round(math.hypot(dx, dy), 4), edge_distance,
        None if pool.area_px is None or building.area_px is None else round(pool.area_px / max(building.area_px, 1), 5), side,
        round(angle, 2), axis, "UNKNOWN", None,
        "BOUNDARY" if pool.relative_parcel_position != "CENTRAL" else "CENTRAL",
    )


def build_record(
    metadata: SourceMetadata, parcel_mask: np.ndarray | None, pool_masks: Iterable[np.ndarray] = (),
    building_mask: np.ndarray | None = None, *, pool_confidence: float | None = None,
    building_confidence: float | None = None,
) -> ParcelBoundGeometryRecord:
    pools = [measure_object(mask, parcel_mask, confidence=pool_confidence, observability=Observability.OBSERVED) for mask in pool_masks]
    bound = [item for item in pools if item.binding.binding == Binding.PARCEL_BOUND]
    pool = max(bound, key=lambda item: item.area_px or 0) if bound else (pools[0] if pools else measure_object(None, parcel_mask))
    building = measure_object(building_mask, parcel_mask, confidence=building_confidence, observability=Observability.OBSERVED, building=True)
    secondary = bound[1] if len(bound) > 1 else None
    multiple = MultipleWaterEvidence(
        WaterCount.TWO_OR_MORE if len(bound) > 1 else WaterCount.ONE if len(bound) == 1 else WaterCount.UNKNOWN,
        secondary.observability if secondary else Observability.UNKNOWN,
        None if secondary is None or pool.area_px is None else round((secondary.area_px or 0) / max(pool.area_px, 1), 4),
    )
    return ParcelBoundGeometryRecord(
        PARCEL_BOUND_GEOMETRY_VERSION, metadata, pool, building, multiple,
        _relation(pool, building),
    )


def rarity_distinctiveness(records: Iterable[ParcelBoundGeometryRecord]) -> dict[str, int]:
    """Count reliable geometry signatures; callers choose their own population."""
    signatures: dict[tuple[float | None, float | None], int] = {}
    for record in records:
        pool = record.pool
        if pool.quality in {Quality.HIGH, Quality.MEDIUM} and pool.binding.binding == Binding.PARCEL_BOUND:
            key = (pool.aspect_ratio, pool.rectangularity)
            signatures[key] = signatures.get(key, 0) + 1
    return {f"{key[0]}:{key[1]}": count for key, count in signatures.items()}


def lane_evidence(record: ParcelBoundGeometryRecord, population: Iterable[ParcelBoundGeometryRecord]) -> ObservableEvidence:
    """Adapt only reliable geometry to v1.2; LOW/UNKNOWN remains recoverable."""
    pool = record.pool
    if pool.quality not in {Quality.HIGH, Quality.MEDIUM} or pool.binding.binding != Binding.PARCEL_BOUND:
        return ObservableEvidence()
    counts = rarity_distinctiveness(population)
    count = counts.get(f"{pool.aspect_ratio}:{pool.rectangularity}", 0)
    return ObservableEvidence(True, True, Compatibility.STRONG_MATCH, 1 if count == 1 else 0)
