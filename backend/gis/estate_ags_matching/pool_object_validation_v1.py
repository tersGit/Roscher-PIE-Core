"""Pool Object Validation v1 — extraction/object-identity only.

Answers: is this segmented object the swimming pool we intend to compare?

Used independently on:
  * candidate-side OS pool blobs (native15 / GIS parcel crops);
  * listing-side Hybrid pool candidates (per frame, then principal-pool pick).

Does not modify Scoring v2 weights, shape similarity, Pool Gate, Corner Gate,
GIS inventory, stand-size scoring, or historical freeze artefacts.

CLIP is one signal, not a pool/not-pool oracle. Crop containment is not parcel
containment: OS native15 crops include ~18 m padding, so masks must be tested
against the GIS parcel polygon.

When independent signals conflict materially, status is UNKNOWN.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Literal, Mapping, Sequence

import numpy as np

VALIDATION_VERSION = "pool_object_validation_v1"
NATIVE_M_PER_PX = 0.15
PAD_METRES = 18.0

Status = Literal["CONFIRMED", "REJECTED", "UNKNOWN"]
ObjectRole = Literal[
    "principal_pool",
    "attached_spa",
    "detached_spa",
    "water_feature",
    "neighbouring_pool",
    "roof_or_shadow",
    "turf_or_deck",
    "unknown",
]

AERIAL_VIEWS = frozenset({"aerial_near_nadir", "aerial_oblique"})
OVERVIEW_VIEWS = frozenset(
    {"aerial_near_nadir", "aerial_oblique", "elevated_exterior", "pool_overview", "ground_level_exterior"}
)
VIEW_GEOMETRY_RANK = {
    "aerial_near_nadir": 5,
    "aerial_oblique": 4,
    "elevated_exterior": 3,
    "pool_overview": 2,
    "ground_level_exterior": 1,
    "garden_only": 0,
    "pool_closeup": 0,
}
SOURCE_RANK = {
    "yoloe_sam2": 4,
    "yoloe": 3,
    "fastsam_fallback": 1,
    "presence_only": 0,
    "no_usable_geometry": -1,
}

# Typical backyard pool on nadir 15 cm imagery. Extraction thresholds only.
TYPICAL_AREA_M2 = (12.0, 90.0)
PLAUSIBLE_AREA_M2 = (8.0, 140.0)
# Listing relative area: tiny aerial specks vs spa vs principal.
LISTING_TINY_AREA = 0.008
LISTING_SPA_MAX_RATIO = 0.38
LISTING_SPA_MAX_AREA = 0.035


def _clip01(value: float | None, default: float = 0.0) -> float:
    if value is None:
        return default
    return float(min(1.0, max(0.0, value)))


def _mean(values: Iterable[float | None]) -> float | None:
    usable = [float(v) for v in values if v is not None]
    if not usable:
        return None
    return float(sum(usable) / len(usable))


def true_parcel_mask_from_geometry(
    image_size: tuple[int, int],
    geometry: Mapping[str, Any] | None,
    *,
    pad_metres: float = PAD_METRES,
) -> np.ndarray | None:
    """Rasterize the GIS parcel ring into padded-crop pixel space.

    ``image_size`` is ``(width, height)`` matching the native15 crop. The crop
    bbox includes ``pad_metres`` around the ring, but the returned mask is only
    the true parcel polygon — never the full padded crop.
    """
    if not geometry:
        return None
    import cv2

    width, height = int(image_size[0]), int(image_size[1])
    rings = geometry.get("rings") or []
    xs: list[float] = []
    ys: list[float] = []
    for ring in rings:
        for x, y in ring:
            xs.append(float(x))
            ys.append(float(y))
    if len(xs) < 3 or width < 2 or height < 2:
        return None
    pad = pad_metres / 111_320.0
    bbox = (min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad)
    outer = rings[0]
    pts = []
    dx = max(bbox[2] - bbox[0], 1e-12)
    dy = max(bbox[3] - bbox[1], 1e-12)
    for lon, lat in outer:
        x = (float(lon) - bbox[0]) / dx * width
        y = (bbox[3] - float(lat)) / dy * height
        pts.append((int(round(x)), int(round(y))))
    mask = np.zeros((height, width), np.uint8)
    if len(pts) >= 3:
        cv2.fillPoly(mask, [np.array(pts, np.int32)], 255)
    return mask.astype(bool)


def mask_from_norm_contour(
    contour: Sequence[Sequence[float]] | None,
    width: int,
    height: int,
) -> np.ndarray | None:
    if not contour or width < 2 or height < 2:
        return None
    import cv2

    pts = np.array(
        [[int(round(float(x) * (width - 1))), int(round(float(y) * (height - 1)))] for x, y in contour],
        dtype=np.int32,
    )
    if len(pts) < 3:
        return None
    canvas = np.zeros((height, width), np.uint8)
    cv2.fillPoly(canvas, [pts], 255)
    return canvas.astype(bool)


def _overlap_frac(mask: np.ndarray | None, other: np.ndarray | None) -> float | None:
    if mask is None or other is None:
        return None
    if mask.shape != other.shape:
        return None
    area = float(np.asarray(mask).astype(bool).sum())
    if area <= 0:
        return None
    return float(np.logical_and(mask, other).sum() / area)


def infer_image_size_from_geometry(geometry: Mapping[str, Any] | None) -> tuple[int, int] | None:
    if not geometry:
        return None
    cxy = geometry.get("centroid_xy_px")
    cx = geometry.get("centroid_x")
    cy = geometry.get("centroid_y")
    if not cxy or cx is None or cy is None:
        return None
    try:
        width = int(round(float(cxy[0]) / max(float(cx), 1e-6) + 1.0))
        height = int(round(float(cxy[1]) / max(float(cy), 1e-6) + 1.0))
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    if width < 32 or height < 32:
        return None
    return width, height


def parcel_relationship(
    mask: np.ndarray | None,
    true_parcel: np.ndarray | None,
    *,
    centroid_xy: tuple[float, float] | None = None,
    metres_per_pixel: float = NATIVE_M_PER_PX,
) -> dict[str, Any]:
    """True-parcel metrics. Crop-filling masks are treated as missing parcel."""
    empty = {
        "parcel_containment": None,
        "parcel_outside_frac": None,
        "centroid_inside": None,
        "distance_to_boundary_m": None,
        "boundary_band_frac": None,
        "crosses_boundary": None,
        "parcel_mask_is_crop": False,
        "parcel_available": False,
    }
    if mask is None or true_parcel is None:
        return empty
    parcel = np.asarray(true_parcel).astype(bool)
    blob = np.asarray(mask).astype(bool)
    if parcel.shape != blob.shape:
        return empty
    coverage = float(parcel.mean())
    crop_as_parcel = coverage >= 0.80
    if crop_as_parcel or coverage <= 0.01:
        out = dict(empty)
        out["parcel_mask_is_crop"] = crop_as_parcel
        out["parcel_available"] = False
        return out
    area = float(blob.sum())
    if area <= 0:
        return empty
    import cv2

    inside = float(np.logical_and(blob, parcel).sum() / area)
    outside = float(np.logical_and(blob, np.logical_not(parcel)).sum() / area)
    if centroid_xy is None:
        ys, xs = np.where(blob)
        h, w = blob.shape
        centroid_xy = (float(xs.mean() / max(w - 1, 1)), float(ys.mean() / max(h - 1, 1)))
    h, w = blob.shape
    cxi = int(round(centroid_xy[0] * (w - 1)))
    cyi = int(round(centroid_xy[1] * (h - 1)))
    cxi = min(max(cxi, 0), w - 1)
    cyi = min(max(cyi, 0), h - 1)
    centroid_inside = bool(parcel[cyi, cxi])
    parcel_u8 = parcel.astype(np.uint8) * 255
    dist = cv2.distanceTransform(parcel_u8, cv2.DIST_L2, 5)
    dist_m = float(dist[cyi, cxi]) * metres_per_pixel
    band_px = max(3, int(round(3.0 / max(metres_per_pixel, 1e-6))))
    eroded = cv2.erode(parcel_u8, np.ones((band_px, band_px), np.uint8))
    band = (parcel_u8 > 0) & (eroded == 0)
    band_frac = float(np.logical_and(blob, band).sum() / area)
    crosses = bool(outside >= 0.08 and inside >= 0.08)
    return {
        "parcel_containment": round(inside, 4),
        "parcel_outside_frac": round(outside, 4),
        "centroid_inside": centroid_inside,
        "distance_to_boundary_m": round(dist_m, 3),
        "boundary_band_frac": round(band_frac, 4),
        "crosses_boundary": crosses,
        "parcel_mask_is_crop": False,
        "parcel_available": True,
    }


def geometry_plausibility_nadir(geometry: Mapping[str, Any] | None) -> float:
    if not geometry or not geometry.get("present", True):
        return 0.0
    compactness = float(geometry.get("compactness") or 0.0)
    convexity = float(geometry.get("convexity") or geometry.get("solidity") or 0.0)
    rectangularity = float(geometry.get("rectangularity") or 0.0)
    aspect = float(geometry.get("aspect_ratio") or 1.0)
    shape = str(geometry.get("shape") or "")
    compact_term = _clip01((compactness - 0.18) / 0.55)
    convex_term = _clip01((convexity - 0.55) / 0.40)
    rect_term = _clip01((rectangularity - 0.40) / 0.45)
    if 1.05 <= aspect <= 3.2:
        aspect_term = 1.0
    elif 3.2 < aspect <= 4.5:
        aspect_term = 0.45
    elif aspect > 5.5:
        aspect_term = 0.08
    else:
        aspect_term = 0.70
    kidney_bonus = 0.08 if shape in {"kidney_or_curved", "irregular", "rounded"} and convexity >= 0.60 else 0.0
    return _clip01(0.34 * compact_term + 0.28 * convex_term + 0.22 * rect_term + 0.16 * aspect_term + kidney_bonus)


def area_plausibility_nadir(area_m2: float | None) -> float:
    if area_m2 is None:
        return 0.5
    area = float(area_m2)
    lo, hi = TYPICAL_AREA_M2
    if lo <= area <= hi:
        return 1.0
    if PLAUSIBLE_AREA_M2[0] <= area < lo:
        return _clip01(0.35 + 0.65 * (area - PLAUSIBLE_AREA_M2[0]) / max(lo - PLAUSIBLE_AREA_M2[0], 1e-6))
    if hi < area <= PLAUSIBLE_AREA_M2[1]:
        return _clip01(0.35 + 0.65 * (PLAUSIBLE_AREA_M2[1] - area) / max(PLAUSIBLE_AREA_M2[1] - hi, 1e-6))
    if area < PLAUSIBLE_AREA_M2[0]:
        return 0.05
    return 0.05


def _border_distance(centroid_xy: tuple[float, float] | None, box: Sequence[float] | None) -> tuple[float, bool]:
    """Min normalised distance of centroid/box to the frame border."""
    dist = 0.5
    touches = False
    if centroid_xy is not None:
        cx, cy = float(centroid_xy[0]), float(centroid_xy[1])
        dist = min(cx, cy, 1.0 - cx, 1.0 - cy)
    if box is not None and len(box) >= 4:
        x0, y0, x1, y1 = [float(v) for v in box[:4]]
        # box may be pixels; if values look normalised use them directly.
        if max(x1, y1) <= 1.5:
            nx0, ny0, nx1, ny1 = x0, y0, x1, y1
        else:
            nx0 = ny0 = nx1 = ny1 = None  # pixel box without size → ignore
        if nx0 is not None:
            edge = min(nx0, ny0, 1.0 - nx1, 1.0 - ny1)
            dist = min(dist, max(edge, 0.0))
            touches = nx0 <= 0.02 or ny0 <= 0.02 or nx1 >= 0.98 or ny1 >= 0.98
    if centroid_xy is not None:
        cx, cy = float(centroid_xy[0]), float(centroid_xy[1])
        if cx <= 0.03 or cy <= 0.03 or cx >= 0.97 or cy >= 0.97:
            touches = True
    return _clip01(dist), touches


@dataclass
class PoolObjectSignals:
    semantic_pool_confidence: float = 0.0
    water_confidence: float | None = None
    roof_confidence: float = 0.0
    road_shadow_confidence: float = 0.0
    parcel_containment: float | None = None
    parcel_edge_risk: float = 0.0
    building_overlap: float | None = None
    road_overlap: float | None = None
    geometry_plausibility: float = 0.0
    area_plausibility: float = 0.0
    yard_context: float = 0.0
    neighbour_risk: float = 0.0
    crop_containment: float | None = None
    deck_or_turf_confidence: float = 0.0
    border_contact: float = 0.0


@dataclass
class PoolObjectValidation:
    version: str = VALIDATION_VERSION
    final_status: Status = "UNKNOWN"
    final_pool_object_confidence: float = 0.0
    object_role: ObjectRole = "unknown"
    principal_pool_candidate: bool = False
    signals: PoolObjectSignals = field(default_factory=PoolObjectSignals)
    reason_codes: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    contour_retained: bool = True

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return payload


def _yard_context_nadir(
    *,
    parcel: dict[str, Any],
    building_overlap: float | None,
    centroid_xy: tuple[float, float] | None,
    building_centroid: tuple[float, float] | None,
    geometry_plausibility: float,
) -> float:
    if not parcel.get("parcel_available"):
        return 0.45
    containment = float(parcel.get("parcel_containment") or 0.0)
    centroid_inside = bool(parcel.get("centroid_inside"))
    dist_m = parcel.get("distance_to_boundary_m")
    edge = 0.0 if dist_m is None else _clip01((float(dist_m) - 1.5) / 8.0)
    bld = 1.0 - _clip01(building_overlap) if building_overlap is not None else 0.55
    offset = 0.5
    if centroid_xy is not None and building_centroid is not None:
        sep = math.hypot(centroid_xy[0] - building_centroid[0], centroid_xy[1] - building_centroid[1])
        offset = _clip01((sep - 0.04) / 0.22)
    inside = 1.0 if centroid_inside and containment >= 0.75 else (0.45 if centroid_inside else 0.05)
    return _clip01(0.35 * inside + 0.20 * edge + 0.25 * bld + 0.12 * offset + 0.08 * geometry_plausibility)


def _neighbour_risk_nadir(parcel: dict[str, Any], crop_containment: float | None) -> float:
    if not parcel.get("parcel_available"):
        # Missing GIS polygon is UNKNOWN, not a neighbour conviction.
        return 0.40
    containment = float(parcel.get("parcel_containment") or 0.0)
    outside = float(parcel.get("parcel_outside_frac") or 0.0)
    dist_m = float(parcel.get("distance_to_boundary_m") or 0.0)
    band = float(parcel.get("boundary_band_frac") or 0.0)
    centroid_inside = bool(parcel.get("centroid_inside"))
    risk = 0.0
    if containment < 0.45:
        risk = max(risk, 0.92)
    elif containment < 0.70:
        risk = max(risk, 0.72)
    if not centroid_inside:
        risk = max(risk, 0.88)
    if parcel.get("crosses_boundary"):
        risk = max(risk, 0.80)
    if outside >= 0.30:
        risk = max(risk, 0.90)
    if dist_m < 2.0 and containment < 0.92:
        risk = max(risk, 0.62)
    if band >= 0.45 and containment < 0.95:
        risk = max(risk, 0.70)
    return _clip01(risk)


def validate_candidate_pool_object(
    *,
    clip: Mapping[str, float] | None = None,
    geometry: Mapping[str, Any] | None = None,
    mask: np.ndarray | None = None,
    true_parcel: np.ndarray | None = None,
    building_mask: np.ndarray | None = None,
    road_mask: np.ndarray | None = None,
    water_frac: float | None = None,
    vegetation_frac: float | None = None,
    centroid_xy: tuple[float, float] | None = None,
    building_centroid: tuple[float, float] | None = None,
    metres_per_pixel: float = NATIVE_M_PER_PX,
    crop_shape: tuple[int, int] | None = None,
) -> PoolObjectValidation:
    """Validate one OS/native15 pool blob against independent signals."""
    clip = dict(clip or {})
    geometry = dict(geometry or {})
    pool_s = _clip01(clip.get("pool"))
    roof_s = _clip01(clip.get("roof"))
    shadow_s = _clip01(clip.get("shadow"))
    road_s = max(_clip01(clip.get("road")), _clip01(clip.get("driveway")))
    lawn_s = _clip01(clip.get("lawn"))
    if centroid_xy is None and geometry.get("centroid_x") is not None:
        centroid_xy = (float(geometry["centroid_x"]), float(geometry.get("centroid_y") or 0.5))
    parcel = parcel_relationship(mask, true_parcel, centroid_xy=centroid_xy, metres_per_pixel=metres_per_pixel)
    building_overlap = _overlap_frac(mask, building_mask)
    road_overlap = _overlap_frac(mask, road_mask)
    if crop_shape is not None and mask is not None:
        crop_containment = float(np.asarray(mask).astype(bool).mean() > 0)
    else:
        crop_containment = 1.0 if mask is not None else None

    geom_p = geometry_plausibility_nadir(geometry)
    area_m2 = geometry.get("area_m2")
    if area_m2 is None and mask is not None:
        area_m2 = float(np.asarray(mask).astype(bool).sum()) * (metres_per_pixel ** 2)
    area_p = area_plausibility_nadir(None if area_m2 is None else float(area_m2))
    water_c = None if water_frac is None else _clip01(water_frac)
    veg = None if vegetation_frac is None else _clip01(vegetation_frac)

    edge_risk = 0.0
    if parcel.get("parcel_available"):
        dist_m = float(parcel.get("distance_to_boundary_m") or 0.0)
        band = float(parcel.get("boundary_band_frac") or 0.0)
        edge_risk = _clip01(0.55 * band + 0.45 * (1.0 - _clip01(dist_m / 10.0)))
        if parcel.get("crosses_boundary"):
            edge_risk = max(edge_risk, 0.75)
        if not parcel.get("centroid_inside"):
            edge_risk = max(edge_risk, 0.90)
    neighbour = _neighbour_risk_nadir(parcel, crop_containment)
    yard = _yard_context_nadir(
        parcel=parcel,
        building_overlap=building_overlap,
        centroid_xy=centroid_xy,
        building_centroid=building_centroid,
        geometry_plausibility=geom_p,
    )

    signals = PoolObjectSignals(
        semantic_pool_confidence=round(pool_s, 4),
        water_confidence=None if water_c is None else round(water_c, 4),
        roof_confidence=round(roof_s, 4),
        road_shadow_confidence=round(max(shadow_s, road_s), 4),
        parcel_containment=parcel.get("parcel_containment"),
        parcel_edge_risk=round(edge_risk, 4),
        building_overlap=None if building_overlap is None else round(building_overlap, 4),
        road_overlap=None if road_overlap is None else round(road_overlap, 4),
        geometry_plausibility=round(geom_p, 4),
        area_plausibility=round(area_p, 4),
        yard_context=round(yard, 4),
        neighbour_risk=round(neighbour, 4),
        crop_containment=crop_containment,
        deck_or_turf_confidence=round(max(lawn_s, _clip01(clip.get("deck"))), 4),
        border_contact=round(edge_risk, 4),
    )

    reasons: list[str] = []
    notes: list[str] = []
    role: ObjectRole = "unknown"
    status: Status = "UNKNOWN"

    containment = signals.parcel_containment
    roof_spatial = building_overlap is not None and building_overlap >= 0.28
    road_spatial = road_overlap is not None and road_overlap >= 0.28
    strong_roof = roof_s >= 0.32 and roof_spatial
    strong_road = (max(shadow_s, road_s) >= 0.28 and (road_spatial or geom_p < 0.42 or area_p < 0.40))
    weak_clip = pool_s < 0.18
    clip_roof_conflict = roof_s >= 0.35 and pool_s + 0.12 < roof_s and not roof_spatial
    geom_strong = geom_p >= 0.42 and area_p >= 0.50
    parcel_strong = bool(parcel.get("parcel_available") and containment is not None and containment >= 0.75 and parcel.get("centroid_inside"))
    water_strong = water_c is not None and water_c >= 0.35
    missing_parcel = not parcel.get("parcel_available")
    clip_strong = pool_s >= 0.70 and pool_s >= roof_s + 0.25

    if veg is not None and veg >= 0.55 and (water_c is None or water_c < 0.12) and pool_s < 0.30:
        status, role = "REJECTED", "turf_or_deck"
        reasons.append("vegetation_dominant")
    elif parcel.get("parcel_available") and (
        neighbour >= 0.78 or (containment is not None and containment < 0.45) or parcel.get("centroid_inside") is False
    ):
        status, role = "REJECTED", "neighbouring_pool"
        reasons.append("true_parcel_neighbour_or_outside")
    elif parcel.get("crosses_boundary") and containment is not None and containment < 0.70:
        status, role = "REJECTED", "neighbouring_pool"
        reasons.append("material_parcel_boundary_crossing")
    elif strong_roof:
        status, role = "REJECTED", "roof_or_shadow"
        reasons.append("roof_semantic_and_building_overlap")
    elif strong_road:
        status, role = "REJECTED", "roof_or_shadow"
        reasons.append("road_shadow_semantic_and_context")
    elif lawn_s >= 0.40 and pool_s < 0.22 and (water_c is None or water_c < 0.20):
        status, role = "REJECTED", "turf_or_deck"
        reasons.append("lawn_or_turf_dominant")
    elif missing_parcel and not geom_strong:
        status, role = "UNKNOWN", "unknown"
        reasons.append("missing_true_parcel_geometry")
        notes.append("Cannot confirm in-parcel identity without the GIS polygon.")
    elif geom_strong and parcel_strong and neighbour < 0.45 and not strong_roof and not strong_road:
        if pool_s >= 0.40 and pool_s >= roof_s - 0.05:
            status, role = "CONFIRMED", "principal_pool"
            reasons.append("semantics_and_geometry_and_true_parcel")
        elif water_strong and (building_overlap is None or building_overlap < 0.20):
            status, role = "CONFIRMED", "principal_pool"
            reasons.append("water_geometry_true_parcel_despite_weak_clip")
        elif clip_roof_conflict or weak_clip:
            status, role = "UNKNOWN", "principal_pool"
            reasons.append("semantic_conflict_geometry_and_parcel_support")
            notes.append("Weak or contradictory CLIP is not treated as an automatic veto.")
        else:
            status, role = "UNKNOWN", "principal_pool"
            reasons.append("context_supports_pool_semantics_weak")
            notes.append("Moderate CLIP without water evidence is not enough to CONFIRMED.")
    elif geom_strong and missing_parcel and water_strong and not strong_roof:
        status, role = "UNKNOWN", "unknown"
        reasons.append("geometry_without_true_parcel")
    else:
        if roof_s >= 0.40 and pool_s < 0.15 and (geom_p < 0.50 or area_p < 0.45):
            status, role = "REJECTED", "roof_or_shadow"
            reasons.append("roof_semantics_without_pool_geometry")
        elif max(shadow_s, road_s) >= 0.28 and pool_s < 0.20 and area_p < 0.55:
            status, role = "REJECTED", "roof_or_shadow"
            reasons.append("road_shadow_weak_pool_geometry")
        else:
            status, role = "UNKNOWN", "unknown"
            reasons.append("insufficient_independent_support")

    # Confidence: never let a single CLIP axis dominate.
    parts = [
        0.16 * pool_s,
        0.14 * (water_c if water_c is not None else 0.45),
        0.16 * geom_p,
        0.14 * area_p,
        0.14 * (containment if containment is not None else 0.40),
        0.10 * yard,
        0.08 * (1.0 - neighbour),
        0.08 * (1.0 - _clip01(building_overlap) if building_overlap is not None else 0.55),
    ]
    confidence = _clip01(sum(parts))
    if status == "REJECTED":
        confidence = min(confidence, 0.34)
        if role == "neighbouring_pool":
            confidence = min(confidence, 0.22)
    elif status == "UNKNOWN":
        confidence = min(max(confidence, 0.28), 0.72)
    else:
        confidence = max(confidence, 0.62)

    principal = status in {"CONFIRMED", "UNKNOWN"} and role == "principal_pool" and neighbour < 0.55
    if status == "REJECTED":
        principal = False

    return PoolObjectValidation(
        final_status=status,
        final_pool_object_confidence=round(confidence, 4),
        object_role=role,
        principal_pool_candidate=principal,
        signals=signals,
        reason_codes=reasons,
        notes=notes,
        contour_retained=True,
    )


def listing_border_risk(
    *,
    viewpoint: str,
    relative_area: float | None,
    centroid_xy: tuple[float, float] | None,
    box: Sequence[float] | None = None,
    contour: Sequence[Sequence[float]] | None = None,
) -> tuple[float, list[str]]:
    """Distinguish tiny aerial border specks from large overview crops."""
    reasons: list[str] = []
    area = 0.0 if relative_area is None else float(relative_area)
    cx_cy = centroid_xy
    if cx_cy is None and contour:
        xs = [float(p[0]) for p in contour]
        ys = [float(p[1]) for p in contour]
        if xs and ys:
            cx_cy = (sum(xs) / len(xs), sum(ys) / len(ys))
    dist, touches = _border_distance(cx_cy, box)
    if contour:
        ys = [float(p[1]) for p in contour]
        xs = [float(p[0]) for p in contour]
        if xs and ys:
            ymin, ymax, xmin, xmax = min(ys), max(ys), min(xs), max(xs)
            if ymin <= 0.03 or ymax >= 0.97 or xmin <= 0.03 or xmax >= 0.97:
                touches = True
            span_touch = min(xmin, ymin, 1.0 - xmax, 1.0 - ymax)
            dist = min(dist, max(span_touch, 0.0))
    aerial = viewpoint in AERIAL_VIEWS
    overview = viewpoint in {"pool_overview", "elevated_exterior", "ground_level_exterior"}
    tiny = area > 0 and area < LISTING_TINY_AREA
    risk = 0.0
    if aerial and tiny and dist <= 0.12:
        risk = 0.92
        reasons.append("tiny_aerial_border_speck")
    elif aerial and tiny:
        risk = 0.70
        reasons.append("tiny_aerial_object")
    elif aerial and dist <= 0.06 and area < 0.02:
        risk = 0.78
        reasons.append("aerial_edge_object")
    elif overview and area >= 0.04 and touches:
        risk = 0.12
        reasons.append("overview_frame_crop_of_large_pool")
    elif overview and area >= 0.04:
        risk = 0.08
    elif touches and area < 0.02:
        risk = 0.64
        reasons.append("small_border_object")
    elif touches:
        risk = 0.28
    return _clip01(risk), reasons


def classify_listing_water_role(
    *,
    relative_area: float | None,
    secondary_area: float | None,
    adjacent: bool | None,
    neighbour_risk: float,
    validation_status: Status,
) -> ObjectRole:
    if neighbour_risk >= 0.75:
        return "neighbouring_pool"
    if validation_status == "REJECTED":
        return "unknown"
    area = 0.0 if relative_area is None else float(relative_area)
    if secondary_area is not None and area > 0:
        other = float(secondary_area)
        if area <= other and area / max(other, 1e-6) <= LISTING_SPA_MAX_RATIO and area <= LISTING_SPA_MAX_AREA:
            return "attached_spa" if adjacent else "detached_spa"
    if 0 < area <= 0.006 and neighbour_risk < 0.5:
        return "water_feature"
    return "principal_pool"


def validate_listing_pool_object(
    *,
    viewpoint: str,
    source: str = "",
    clip: Mapping[str, float] | None = None,
    geometry: Mapping[str, Any] | None = None,
    relative_area: float | None = None,
    centroid_xy: tuple[float, float] | None = None,
    box: Sequence[float] | None = None,
    contour: Sequence[Sequence[float]] | None = None,
    secondary_relative_area: float | None = None,
    secondary_adjacent: bool | None = None,
    scoring_ready: bool = False,
    yoloe_conf: float | None = None,
) -> PoolObjectValidation:
    """Validate one listing-frame pool candidate. Does not imply official pick."""
    clip = dict(clip or {})
    geometry = dict(geometry or {})
    area = relative_area if relative_area is not None else geometry.get("relative_area")
    if centroid_xy is None and contour:
        xs = [float(p[0]) for p in contour]
        ys = [float(p[1]) for p in contour]
        if xs and ys:
            centroid_xy = (sum(xs) / len(xs), sum(ys) / len(ys))
    pool_s = _clip01(clip.get("pool"))
    veg_s = _clip01(clip.get("vegetation"))
    deck_s = _clip01(clip.get("deck"))
    bath_s = _clip01(clip.get("bathtub"))
    interior_s = _clip01(clip.get("interior"))
    wall_s = _clip01(clip.get("wall"))
    furn_s = _clip01(clip.get("furniture"))
    compactness = float(geometry.get("compactness") or 0.0)
    solidity = float(geometry.get("solidity") or geometry.get("convexity") or 0.0)
    aspect = float(geometry.get("aspect_ratio") or 0.0)
    geom_p = _clip01(
        0.40 * _clip01((compactness - 0.12) / 0.50)
        + 0.35 * _clip01((solidity - 0.55) / 0.40)
        + 0.25 * (1.0 if 1.1 <= aspect <= 4.2 or aspect == 0.0 else 0.45)
    )
    area_p = 0.5
    if area is not None:
        a = float(area)
        if viewpoint in AERIAL_VIEWS:
            area_p = 1.0 if 0.004 <= a <= 0.08 else (0.25 if a < 0.004 else _clip01(1.2 - 8.0 * a))
            if a < LISTING_TINY_AREA:
                area_p = min(area_p, 0.28)
        else:
            area_p = 1.0 if 0.03 <= a <= 0.35 else (0.35 if a < 0.03 else 0.40)

    border_risk, border_reasons = listing_border_risk(
        viewpoint=viewpoint,
        relative_area=None if area is None else float(area),
        centroid_xy=centroid_xy,
        box=box,
        contour=contour,
    )
    turf = 0.0
    if source.startswith("fastsam") and deck_s >= 0.40 and deck_s >= pool_s + 0.12:
        turf = 0.85
    if veg_s >= 0.32 and veg_s >= pool_s:
        turf = max(turf, 0.80)
    neighbour = border_risk
    if viewpoint in AERIAL_VIEWS and area is not None and float(area) < LISTING_TINY_AREA:
        neighbour = max(neighbour, 0.72)

    signals = PoolObjectSignals(
        semantic_pool_confidence=round(pool_s, 4),
        water_confidence=round(pool_s, 4),
        roof_confidence=round(max(wall_s, interior_s), 4),
        road_shadow_confidence=0.0,
        parcel_containment=None,
        parcel_edge_risk=round(border_risk, 4),
        building_overlap=None,
        road_overlap=None,
        geometry_plausibility=round(geom_p, 4),
        area_plausibility=round(area_p, 4),
        yard_context=round(1.0 - neighbour, 4),
        neighbour_risk=round(neighbour, 4),
        crop_containment=1.0,
        deck_or_turf_confidence=round(max(deck_s, turf), 4),
        border_contact=round(border_risk, 4),
    )

    reasons = list(border_reasons)
    notes: list[str] = []
    status: Status = "UNKNOWN"
    role: ObjectRole = "unknown"

    if bath_s >= 0.22 and bath_s >= pool_s:
        status, role = "REJECTED", "unknown"
        reasons.append("bathtub_or_bathroom")
    elif interior_s >= 0.30 and pool_s < 0.25:
        status, role = "REJECTED", "unknown"
        reasons.append("interior_scene")
    elif turf >= 0.80:
        status, role = "REJECTED", "turf_or_deck"
        reasons.append("deck_or_turf_or_vegetation")
    elif neighbour >= 0.85 and viewpoint in AERIAL_VIEWS:
        status, role = "REJECTED", "neighbouring_pool"
        reasons.append("tiny_aerial_border_object")
    elif neighbour >= 0.70 and viewpoint in AERIAL_VIEWS and area is not None and float(area) < LISTING_TINY_AREA:
        status, role = "UNKNOWN", "neighbouring_pool"
        reasons.append("possible_neighbour_or_secondary_speck")
        notes.append("scoring_ready does not imply this is the principal pool.")
    elif pool_s >= 0.28 and geom_p >= 0.35 and area_p >= 0.35 and neighbour < 0.55:
        status = "CONFIRMED"
        reasons.append("listing_object_identity_supported")
    elif scoring_ready and neighbour < 0.60 and turf < 0.70:
        status = "UNKNOWN"
        reasons.append("usable_geometry_identity_uncertain")
        notes.append("scoring_ready means usable geometry, not official principal-pool identity.")
    else:
        status = "UNKNOWN"
        reasons.append("listing_object_uncertain")

    if role == "unknown":
        role = classify_listing_water_role(
            relative_area=None if area is None else float(area),
            secondary_area=secondary_relative_area,
            adjacent=secondary_adjacent,
            neighbour_risk=neighbour,
            validation_status=status,
        )
    if role in {"attached_spa", "detached_spa", "water_feature"} and status != "REJECTED":
        reasons.append(role)
        notes.append("Secondary water retained as diagnostic metadata only.")

    conf = _clip01(
        0.34 * pool_s
        + 0.22 * geom_p
        + 0.18 * area_p
        + 0.16 * (1.0 - neighbour)
        + 0.10 * (0.0 if yoloe_conf is None else _clip01(yoloe_conf))
    )
    if status == "REJECTED":
        conf = min(conf, 0.30)
    principal = (
        status in {"CONFIRMED", "UNKNOWN"}
        and role == "principal_pool"
        and neighbour < 0.62
        and turf < 0.70
    )
    if area is not None and float(area) < LISTING_TINY_AREA and viewpoint in AERIAL_VIEWS:
        principal = False
    return PoolObjectValidation(
        final_status=status,
        final_pool_object_confidence=round(conf, 4),
        object_role=role,
        principal_pool_candidate=principal,
        signals=signals,
        reason_codes=reasons,
        notes=notes,
        contour_retained=True,
    )


def _frame_aspect_shape(frame: Any) -> tuple[float | None, float | None, int | None, float | None]:
    dominant = getattr(frame, "dominant", None) or {}
    if not isinstance(dominant, dict):
        dominant = {}
    geom = dominant.get("geometry") or {}
    desc = getattr(frame, "descriptors", None) or {}
    aspect = geom.get("aspect_ratio") or desc.get("aspect_ratio")
    solidity = geom.get("solidity") or desc.get("solidity")
    indents = geom.get("n_major_indents")
    if indents is None:
        indents = desc.get("n_major_indents")
    area = dominant.get("relative_area")
    if area is None:
        area = geom.get("relative_area")
    return (
        None if aspect is None else float(aspect),
        None if solidity is None else float(solidity),
        None if indents is None else int(indents),
        None if area is None else float(area),
    )


def _contour_centroid(contour: Sequence[Sequence[float]] | None) -> tuple[float, float] | None:
    if not contour:
        return None
    xs = [float(p[0]) for p in contour]
    ys = [float(p[1]) for p in contour]
    if not xs:
        return None
    return (sum(xs) / len(xs), sum(ys) / len(ys))


def listing_candidates_agree(a: Any, b: Any) -> bool:
    """Same principal-pool identity, not a merge/average test."""
    aa, sa, ia, ra = _frame_aspect_shape(a)
    ab, sb, ib, rb = _frame_aspect_shape(b)
    if aa is None or ab is None:
        return False
    if abs(aa - ab) > 1.05:
        return False
    if sa is not None and sb is not None and abs(sa - sb) > 0.28:
        return False
    if ia is not None and ib is not None and abs(ia - ib) >= 3:
        return False
    if ra is not None and rb is not None and min(ra, rb) > 0 and max(ra, rb) / max(min(ra, rb), 1e-6) > 8.0:
        # Relative area can differ by viewpoint; extreme gaps still disagree.
        va = getattr(a, "viewpoint", "")
        vb = getattr(b, "viewpoint", "")
        if {va, vb} <= AERIAL_VIEWS or {va, vb} <= {"pool_overview", "elevated_exterior"}:
            return False
    return True


def cluster_listing_principal_candidates(frames: Sequence[Any]) -> list[list[Any]]:
    principals = [
        f
        for f in frames
        if getattr(f, "principal_pool_candidate", False) or (
            isinstance(getattr(f, "pool_object_validation", None), dict)
            and (f.pool_object_validation or {}).get("principal_pool_candidate")
        )
    ]
    if not principals:
        principals = [f for f in frames if getattr(f, "scoring_ready", False) and getattr(f, "dominant", None)]
    clusters: list[list[Any]] = []
    for frame in principals:
        placed = False
        for cluster in clusters:
            if listing_candidates_agree(frame, cluster[0]):
                cluster.append(frame)
                placed = True
                break
        if not placed:
            clusters.append([frame])
    clusters.sort(
        key=lambda c: (
            sum(1 for f in c if getattr(f, "principal_pool_candidate", False)),
            max((_identity_confidence(f) for f in c), default=0.0),
            sum(1 for f in c if getattr(f, "viewpoint", "") in {"pool_overview", "elevated_exterior"}),
            len(c),
            max(float(getattr(f, "geometry_quality", 0.0) or 0.0) for f in c),
        ),
        reverse=True,
    )
    return clusters


def _identity_confidence(frame: Any) -> float:
    val = getattr(frame, "pool_object_validation", None)
    if isinstance(val, PoolObjectValidation):
        return float(val.final_pool_object_confidence)
    if isinstance(val, dict):
        return float(val.get("final_pool_object_confidence") or 0.0)
    return 0.0


def _geometry_quality_term(frame: Any) -> float:
    return float(getattr(frame, "geometry_quality", 0.0) or 0.0)


def select_principal_listing_pool(frames: Sequence[Any]) -> tuple[Any | None, dict[str, Any]]:
    """Official fingerprint pick: identity → agreement → geometry → viewpoint.

    Incompatible contours are never averaged.
    """
    annotated = []
    for frame in frames:
        val = getattr(frame, "pool_object_validation", None)
        if val is None and getattr(frame, "dominant", None):
            dominant = frame.dominant or {}
            geom = dominant.get("geometry") or {}
            centroid = dominant.get("centroid_xy")
            if isinstance(centroid, (list, tuple)) and len(centroid) >= 2:
                cxy = (float(centroid[0]), float(centroid[1]))
            else:
                cxy = _contour_centroid(dominant.get("contour_image") or getattr(frame, "contour_image", None))
            secondary = getattr(frame, "secondary", None) or {}
            val = validate_listing_pool_object(
                viewpoint=str(getattr(frame, "viewpoint", "") or ""),
                source=str(getattr(frame, "source", "") or ""),
                clip=dominant.get("clip") or {},
                geometry=geom,
                relative_area=dominant.get("relative_area") or geom.get("relative_area"),
                centroid_xy=cxy,
                box=dominant.get("box"),
                contour=dominant.get("contour_image") or getattr(frame, "contour_image", None),
                secondary_relative_area=(secondary or {}).get("relative_area") if secondary else None,
                secondary_adjacent=((getattr(frame, "spa_relationship", None) or {}).get("adjacent")),
                scoring_ready=bool(getattr(frame, "scoring_ready", False)),
                yoloe_conf=getattr(frame, "yoloe_conf", None),
            )
            frame.pool_object_validation = val.to_dict()
            frame.principal_pool_candidate = val.principal_pool_candidate
            frame.object_role = val.object_role
        elif isinstance(val, dict):
            frame.principal_pool_candidate = bool(val.get("principal_pool_candidate"))
            frame.object_role = str(val.get("object_role") or "unknown")
        annotated.append(frame)

    ready = [f for f in annotated if getattr(f, "scoring_ready", False) and getattr(f, "dominant", None)]
    clusters = cluster_listing_principal_candidates(ready)
    cluster_meta = []
    for idx, cluster in enumerate(clusters):
        cluster_meta.append(
            {
                "cluster_id": idx,
                "size": len(cluster),
                "media_ids": [getattr(f, "media_id", None) for f in cluster],
                "viewpoints": [getattr(f, "viewpoint", None) for f in cluster],
                "principal_n": sum(1 for f in cluster if getattr(f, "principal_pool_candidate", False)),
            }
        )
    chosen = None
    reason = "no_scoring_ready_principal_pool"
    if clusters:
        best = clusters[0]
        supported = [f for f in best if getattr(f, "principal_pool_candidate", False)]
        pool = supported or best
        identities = [_identity_confidence(f) for f in pool]
        spread = (max(identities) - min(identities)) if identities else 0.0
        chosen = max(
            pool,
            key=lambda f: (
                1 if getattr(f, "principal_pool_candidate", False) else 0,
                len(best),
                _identity_confidence(f) if spread >= 0.12 else 0.0,
                VIEW_GEOMETRY_RANK.get(getattr(f, "viewpoint", ""), 0),
                SOURCE_RANK.get(getattr(f, "source", ""), -1),
                _geometry_quality_term(f),
            ),
        )
        reason = (
            "principal_pool_identity then cross-frame agreement then geometry then viewpoint; "
            f"cluster_size={len(best)}; incompatible contours are not averaged"
        )
    agreement = {
        "n_clusters": len(clusters),
        "clusters": cluster_meta,
        "note": "Incompatible contours are not averaged. Viewpoint never outranks wrong-object identity.",
    }
    return chosen, {
        "selection_reason": reason,
        "multiframe_clusters": agreement,
        "n_principal_candidates": sum(1 for f in ready if getattr(f, "principal_pool_candidate", False)),
    }


def validate_os_payload(
    payload: Mapping[str, Any],
    *,
    gis_geometry: Mapping[str, Any] | None,
    bgr: np.ndarray | None = None,
    unclipped_mask: np.ndarray | None = None,
    independent_building_mask: np.ndarray | None = None,
    independent_road_mask: np.ndarray | None = None,
    water_frac: float | None = None,
) -> PoolObjectValidation:
    """Re-evaluate a frozen OS JSON pool object without mutating it."""
    pool = payload.get("pool") or {}
    geometry = dict(pool.get("geometry") or {})
    contour = pool.get("contour")
    size = infer_image_size_from_geometry(geometry)
    mask = unclipped_mask
    true_parcel = None
    if size is not None:
        width, height = size
        if mask is None:
            mask = mask_from_norm_contour(contour, width, height)
        true_parcel = true_parcel_mask_from_geometry((width, height), gis_geometry)
        if independent_building_mask is None and bgr is None:
            # Frozen building contours are unreliable when the pool was rejected
            # first (the roof extractor may swallow the blob). Leave overlap unknown.
            independent_building_mask = None
        if independent_road_mask is None:
            drv = (payload.get("driveway") or {}).get("contour")
            if pool.get("status") in {"CONFIRMED", "PROBABLE"}:
                independent_road_mask = mask_from_norm_contour(drv, width, height)
    bld_c = (payload.get("building") or {}).get("geometry") or {}
    bld_xy = None
    if bld_c.get("centroid_x") is not None:
        bld_xy = (float(bld_c["centroid_x"]), float(bld_c.get("centroid_y") or 0.5))
    cx = geometry.get("centroid_x")
    cxy = None if cx is None else (float(cx), float(geometry.get("centroid_y") or 0.5))
    return validate_candidate_pool_object(
        clip=pool.get("clip") or {},
        geometry=geometry,
        mask=mask,
        true_parcel=true_parcel,
        building_mask=independent_building_mask,
        road_mask=independent_road_mask,
        water_frac=water_frac,
        centroid_xy=cxy,
        building_centroid=bld_xy,
        crop_shape=None if size is None else (size[1], size[0]),
    )
