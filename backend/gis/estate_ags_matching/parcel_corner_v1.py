"""GIS parcel corner classification for Corner Stand Detection v1.

A parcel is CORNER=YES only when it has two meaningfully distinct road-facing
sides associated with a road intersection or a sharp corner-bend. UNKNOWN is
returned when road topology is missing or the evidence is insufficient.
Stand size is never used.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Literal, Mapping, Sequence

from shapely.geometry import Point

from backend.gis.estate_ags_matching.corner_geometry_v1 import (
    INTERSECTION_PROXIMITY_M,
    MIN_CONTACT_M,
    MIN_DISTINCT_SIDE_ANGLE_DEG,
    MIN_FRONTAGE_M,
    MISSING_ROAD_M,
    NEAR_ROAD_M,
    WEAK_INTERSECTION_PROXIMITY_M,
    LocalProjector,
    RoadFacingSide,
    RoadFeatureXY,
    cluster_sides,
    detect_intersections,
    extract_road_facing_edges,
    heading_separation_deg,
    load_road_features,
    nearest_intersection,
    polygon_from_rings,
    project_roads,
    projector_for,
    roads_union,
)

CornerStatus = Literal["YES", "NO", "UNKNOWN"]
VALID_CORNER = frozenset({"YES", "NO", "UNKNOWN"})

YES_MIN_CONFIDENCE = 0.72
NO_MIN_CONFIDENCE = 0.70

CURVED_ROAD_RULE = (
    "A property on the outside or inside of a curved road is not a corner. "
    "A cul-de-sac frontage is not a corner. Consecutive road-facing edges that "
    "follow one road through a gentle heading change are clustered into a single "
    "side. Cul-de-sac bulbs (short consecutive facets) are not treated as "
    "intersections. Corner=YES requires two distinct road-facing sides "
    f"(heading separation >= {MIN_DISTINCT_SIDE_ANGLE_DEG:.0f} deg) plus an "
    "actual intersection or sharp same-road corner bend."
)


def normalize_corner_status(value: Any) -> CornerStatus:
    status = str(value or "UNKNOWN").strip().upper()
    if status not in VALID_CORNER:
        return "UNKNOWN"
    return status  # type: ignore[return-value]


@dataclass
class ParcelCornerRecord:
    parcel_id: str | None
    stand_number: str | None
    classification: CornerStatus
    confidence: float
    n_road_facing_edges: int
    n_road_facing_sides: int
    frontage_length_m: list[float]
    frontage_ratio: list[float]
    distinct_road_ids: list[str]
    distinct_road_names: list[str]
    intersection_proximity_m: float | None
    nearest_intersection_kind: str | None
    angle_between_sides_deg: float | None
    centroid_to_intersection_m: float | None
    nearest_road_m: float | None
    curved_single_road: bool
    cul_de_sac_frontage: bool
    reason: str
    sides: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["classification"] = self.classification
        return payload


def _parcel_keys(parcel: Mapping[str, Any]) -> tuple[str | None, str | None]:
    stand = parcel.get("stand_number") or parcel.get("parcel_id")
    pid = parcel.get("property_id") or parcel.get("parcel_id") or stand
    return (None if pid is None else str(pid), None if stand is None else str(stand))


def _side_public(side: RoadFacingSide) -> dict[str, Any]:
    return {
        "heading_deg": side.heading_deg,
        "length_m": side.length_m,
        "contact_m": side.contact_m,
        "frontage_ratio": side.frontage_ratio,
        "road_ids": list(side.road_ids),
        "road_names": list(side.road_names),
        "street_types": list(side.street_types),
        "midpoint_xy": list(side.midpoint_xy),
        "heading_span_deg": side.heading_span_deg,
        "n_edges": side.n_edges,
        "curved_single_road": side.curved_single_road,
        "cul_de_sac_type": side.cul_de_sac_type,
    }


def _yes_confidence(*, two_names: bool, ix_m: float | None, angle: float) -> float:
    conf = 0.74
    if two_names:
        conf += 0.10
    if ix_m is not None and ix_m <= 20.0:
        conf += 0.10
    elif ix_m is not None and ix_m <= INTERSECTION_PROXIMITY_M:
        conf += 0.06
    if 70.0 <= angle <= 90.0:
        conf += 0.06
    elif 50.0 <= angle < 70.0:
        conf += 0.03
    return round(min(conf, 0.98), 4)


def classify_polygon(
    polygon,
    roads: Sequence[RoadFeatureXY],
    intersections: Sequence[Any] | None = None,
    *,
    parcel_id: str | None = None,
    stand_number: str | None = None,
) -> ParcelCornerRecord:
    """Classify one projected parcel polygon. Roads may be empty → UNKNOWN."""
    ix_list = list(intersections) if intersections is not None else detect_intersections(roads)
    empty = ParcelCornerRecord(
        parcel_id=parcel_id,
        stand_number=stand_number,
        classification="UNKNOWN",
        confidence=0.0,
        n_road_facing_edges=0,
        n_road_facing_sides=0,
        frontage_length_m=[],
        frontage_ratio=[],
        distinct_road_ids=[],
        distinct_road_names=[],
        intersection_proximity_m=None,
        nearest_intersection_kind=None,
        angle_between_sides_deg=None,
        centroid_to_intersection_m=None,
        nearest_road_m=None,
        curved_single_road=False,
        cul_de_sac_frontage=False,
        reason="missing_road_data",
        sides=[],
    )
    if polygon is None or polygon.is_empty:
        empty.reason = "missing_parcel_geometry"
        return empty
    if not roads:
        return empty

    union = roads_union(roads)
    centroid = polygon.centroid
    nearest_road_m = None if union is None else round(float(centroid.distance(union)), 3)
    edges = extract_road_facing_edges(polygon, roads)
    sides = cluster_sides(edges)
    names = list(dict.fromkeys(name for side in sides for name in side.road_names))
    ids = list(dict.fromkeys(rid for side in sides for rid in side.road_ids))
    vertex = centroid
    if len(sides) >= 2:
        vertex = Point(
            (sides[0].start_xy[0] + sides[1].start_xy[0] + sides[0].end_xy[0] + sides[1].end_xy[0]) / 4.0,
            (sides[0].start_xy[1] + sides[1].start_xy[1] + sides[0].end_xy[1] + sides[1].end_xy[1]) / 4.0,
        )
    nearest_ix, ix_dist = nearest_intersection(vertex, ix_list)
    centroid_ix, centroid_ix_dist = nearest_intersection(centroid, ix_list)
    angle = None
    if len(sides) >= 2:
        angle = round(heading_separation_deg(sides[0].heading_deg, sides[1].heading_deg), 2)

    record = ParcelCornerRecord(
        parcel_id=parcel_id,
        stand_number=stand_number,
        classification="UNKNOWN",
        confidence=0.0,
        n_road_facing_edges=len(edges),
        n_road_facing_sides=len(sides),
        frontage_length_m=[side.contact_m for side in sides],
        frontage_ratio=[side.frontage_ratio for side in sides],
        distinct_road_ids=ids,
        distinct_road_names=names,
        intersection_proximity_m=ix_dist,
        nearest_intersection_kind=None if nearest_ix is None else nearest_ix.kind,
        angle_between_sides_deg=angle,
        centroid_to_intersection_m=centroid_ix_dist,
        nearest_road_m=nearest_road_m,
        curved_single_road=bool(sides) and all(side.curved_single_road or len(side.road_names) <= 1 for side in sides) and len(sides) == 1,
        cul_de_sac_frontage=any(side.cul_de_sac_type for side in sides) and len(sides) == 1,
        reason="insufficient_evidence",
        sides=[_side_public(side) for side in sides],
    )

    weak_second = any(MIN_CONTACT_M <= edge.contact_m < MIN_FRONTAGE_M for edge in edges) and len(sides) == 1
    near_ix = ix_dist is not None and ix_dist <= INTERSECTION_PROXIMITY_M
    two_names = len(names) >= 2
    associated = near_ix or (
        centroid_ix_dist is not None and centroid_ix_dist <= INTERSECTION_PROXIMITY_M
    )

    if len(sides) == 0:
        if nearest_road_m is None or nearest_road_m > MISSING_ROAD_M:
            record.reason = "insufficient_nearby_road_topology"
            record.confidence = 0.0
            record.classification = "UNKNOWN"
            return record
        conf = 0.82 if nearest_road_m <= NEAR_ROAD_M else 0.64
        if conf < NO_MIN_CONFIDENCE:
            record.reason = "no_meaningful_frontage_but_topology_uncertain"
            record.classification = "UNKNOWN"
            record.confidence = round(conf, 4)
            return record
        record.classification = "NO"
        record.confidence = round(conf, 4)
        record.reason = "no_meaningful_road_frontage"
        return record

    if len(sides) == 1:
        if weak_second and associated:
            record.classification = "UNKNOWN"
            record.confidence = 0.45
            record.reason = "possible_corner_weak_second_frontage"
            return record
        if associated and not sides[0].cul_de_sac_type and not sides[0].curved_single_road:
            record.classification = "UNKNOWN"
            record.confidence = 0.48
            record.reason = "single_frontage_near_intersection_unconfirmed_second_side"
            return record
        conf = 0.88
        if sides[0].curved_single_road:
            record.reason = "curved_single_road_frontage_not_corner"
            conf = 0.90
        elif sides[0].cul_de_sac_type:
            record.reason = "cul_de_sac_single_frontage_not_corner"
            conf = 0.90
        else:
            record.reason = "single_road_frontage_not_corner"
        record.classification = "NO"
        record.confidence = conf
        return record

    assert angle is not None
    if angle < MIN_DISTINCT_SIDE_ANGLE_DEG:
        if two_names:
            record.classification = "UNKNOWN"
            record.confidence = 0.40
            record.reason = "dual_frontage_nearly_parallel_not_confirmed_corner"
            return record
        record.classification = "NO"
        record.confidence = 0.84
        record.reason = "parallel_or_collinear_frontage_not_corner"
        return record

    strong_ix = associated and (ix_dist is None or ix_dist <= INTERSECTION_PROXIMITY_M)
    weak_ix = (ix_dist is not None and ix_dist <= WEAK_INTERSECTION_PROXIMITY_M) or (
        centroid_ix_dist is not None and centroid_ix_dist <= WEAK_INTERSECTION_PROXIMITY_M
    )

    if two_names and strong_ix:
        record.classification = "YES"
        record.confidence = _yes_confidence(two_names=True, ix_m=ix_dist, angle=angle)
        record.reason = "two_distinct_road_facing_sides_at_intersection"
        return record
    if two_names and not weak_ix:
        record.classification = "UNKNOWN"
        record.confidence = 0.42
        record.reason = "two_road_names_without_nearby_intersection"
        return record
    if two_names and weak_ix:
        record.classification = "UNKNOWN"
        record.confidence = 0.55
        record.reason = "two_road_names_intersection_association_weak"
        return record
    if strong_ix:
        record.classification = "YES"
        record.confidence = _yes_confidence(two_names=False, ix_m=ix_dist, angle=angle)
        record.reason = "two_distinct_sides_at_same_road_corner_bend_or_intersection"
        return record

    record.classification = "NO"
    record.confidence = 0.78
    record.reason = "two_sides_same_road_without_intersection_or_corner_bend"
    return record


def classify_parcel(
    parcel: Mapping[str, Any],
    roads: Sequence[RoadFeatureXY],
    intersections: Sequence[Any] | None = None,
    *,
    projector: LocalProjector | None = None,
) -> ParcelCornerRecord:
    pid, stand = _parcel_keys(parcel)
    rings = ((parcel.get("geometry") or {}).get("rings")) or []
    if projector is None:
        projector = projector_for([parcel], [])
    poly = polygon_from_rings(rings, projector)
    return classify_polygon(poly, roads, intersections, parcel_id=pid, stand_number=stand)


@dataclass
class EstateCornerLayer:
    n_parcels: int
    n_yes: int
    n_no: int
    n_unknown: int
    n_roads: int
    n_intersections: int
    missing_road_data: bool
    curved_road_rule: str
    records: list[ParcelCornerRecord] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_parcels": self.n_parcels,
            "n_yes": self.n_yes,
            "n_no": self.n_no,
            "n_unknown": self.n_unknown,
            "n_roads": self.n_roads,
            "n_intersections": self.n_intersections,
            "missing_road_data": self.missing_road_data,
            "curved_road_rule": self.curved_road_rule,
            "counts": {"YES": self.n_yes, "NO": self.n_no, "UNKNOWN": self.n_unknown},
            "records": [row.to_dict() for row in self.records],
        }


def classify_estate(
    parcels: Sequence[Mapping[str, Any]],
    road_payload: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None,
) -> EstateCornerLayer:
    features = load_road_features(road_payload)
    projector = projector_for(parcels, features)
    roads = project_roads(features, projector)
    intersections = detect_intersections(roads) if roads else []
    records: list[ParcelCornerRecord] = []
    for parcel in parcels:
        records.append(classify_parcel(parcel, roads, intersections, projector=projector))
    yes = sum(1 for row in records if row.classification == "YES")
    no = sum(1 for row in records if row.classification == "NO")
    unknown = sum(1 for row in records if row.classification == "UNKNOWN")
    return EstateCornerLayer(
        n_parcels=len(records),
        n_yes=yes,
        n_no=no,
        n_unknown=unknown,
        n_roads=len(roads),
        n_intersections=len(intersections),
        missing_road_data=not roads,
        curved_road_rule=CURVED_ROAD_RULE,
        records=records,
    )


def index_corner_records(records: Iterable[Mapping[str, Any] | ParcelCornerRecord]) -> dict[str, Mapping[str, Any]]:
    index: dict[str, Mapping[str, Any]] = {}
    for raw in records:
        row = raw.to_dict() if isinstance(raw, ParcelCornerRecord) else dict(raw)
        for key in ("parcel_id", "stand_number", "property_id"):
            value = row.get(key)
            if value is not None:
                index[str(value)] = row
                index[str(value).replace("/", "_")] = row
        stand = row.get("stand_number")
        if stand is not None:
            index[str(stand).replace("/", "_")] = row
    return index


def load_road_payload(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))
