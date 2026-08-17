"""Shared geometry for Corner Stand Detection v1.

Parcel corner status is decided from parcel polygons and road centreline
topology only. Stand size, estate-boundary status, and listing identity are
not inputs.

Curved-road / cul-de-sac rule
-----------------------------
A long frontage that follows one continuous road — including a gentle bend,
crescent, or cul-de-sac bulb — is one road-facing side, not a corner.
A parcel is a GIS corner only when it has two meaningfully distinct
road-facing sides (heading separation >= MIN_DISTINCT_SIDE_ANGLE_DEG) that
are associated with a road intersection or a sharp same-road corner bend
(not a cul-de-sac bulb of short facets). Missing road topology yields
UNKNOWN rather than a guess.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from shapely.geometry import LineString, MultiLineString, Point, Polygon
from shapely.ops import unary_union

# Distances in metres. Generic suburban cadastral / centreline geometry —
# not fitted to a named estate or listing.
ROAD_PROXIMITY_M = 22.0
ROAD_ALIGN_DEG = 32.0
SAMPLE_SPACING_M = 1.5
MIN_FRONTAGE_M = 8.0
MIN_CONTACT_M = 3.5
EDGE_SIMPLIFY_M = 0.6
SIDE_MERGE_HEADING_DEG = 28.0
CURVE_MERGE_HEADING_DEG = 48.0
MIN_DISTINCT_SIDE_ANGLE_DEG = 35.0
INTERSECTION_JOIN_M = 12.0
INTERSECTION_HEADING_DEG = 40.0
INTERSECTION_PROXIMITY_M = 40.0
WEAK_INTERSECTION_PROXIMITY_M = 70.0
BEND_HEADING_DEG = 55.0
BEND_SEGMENT_MIN_M = 12.0
CUL_DE_SAC_FACET_MAX_M = 10.0
MISSING_ROAD_M = 55.0
NEAR_ROAD_M = 32.0

CUL_DE_SAC_TYPES = frozenset({"CLOSE", "END", "CUL-DE-SAC", "CUL DE SAC", "CULDESAC"})
CURVED_ROAD_TYPES = frozenset({"CRESCENT", "VIEW", "CIRCLE", "LOOP"})


@dataclass(frozen=True)
class LocalProjector:
    """Equirectangular metres about a WGS84 origin. Sufficient at estate scale."""

    lat0: float
    lon0: float

    @classmethod
    def from_points(cls, lons: Sequence[float], lats: Sequence[float]) -> "LocalProjector":
        return cls(lat0=float(sum(lats) / max(len(lats), 1)), lon0=float(sum(lons) / max(len(lons), 1)))

    def xy(self, lon: float, lat: float) -> tuple[float, float]:
        mx = 111_320.0 * math.cos(math.radians(self.lat0))
        my = 111_320.0
        return ((lon - self.lon0) * mx, (lat - self.lat0) * my)

    def lonlat(self, x: float, y: float) -> tuple[float, float]:
        mx = 111_320.0 * math.cos(math.radians(self.lat0))
        my = 111_320.0
        return (self.lon0 + x / mx, self.lat0 + y / my)


@dataclass
class RoadFeatureXY:
    road_id: str
    name: str
    street_type: str
    geom: LineString | MultiLineString
    paths: list[LineString] = field(default_factory=list)

    @property
    def is_cul_de_sac_type(self) -> bool:
        return normalize_street_type(self.street_type) in CUL_DE_SAC_TYPES

    @property
    def is_curved_type(self) -> bool:
        return normalize_street_type(self.street_type) in CURVED_ROAD_TYPES


@dataclass
class IntersectionXY:
    x: float
    y: float
    road_ids: tuple[str, ...]
    road_names: tuple[str, ...]
    angle_deg: float
    kind: str  # crossing | t_junction | corner_bend

    @property
    def point(self) -> Point:
        return Point(self.x, self.y)


@dataclass
class RoadFacingEdge:
    x0: float
    y0: float
    x1: float
    y1: float
    length_m: float
    heading_deg: float
    contact_m: float
    road_ids: list[str]
    road_names: list[str]
    street_types: list[str]


@dataclass
class RoadFacingSide:
    heading_deg: float
    length_m: float
    contact_m: float
    frontage_ratio: float
    road_ids: list[str]
    road_names: list[str]
    street_types: list[str]
    midpoint_xy: tuple[float, float]
    start_xy: tuple[float, float]
    end_xy: tuple[float, float]
    heading_span_deg: float
    n_edges: int
    curved_single_road: bool
    cul_de_sac_type: bool


def normalize_street_type(value: Any) -> str:
    return str(value or "").strip().upper().replace("_", " ")


def heading_deg(p0: Sequence[float], p1: Sequence[float]) -> float:
    return math.degrees(math.atan2(p1[1] - p0[1], p1[0] - p0[0])) % 360.0


def heading_separation_deg(h1: float, h2: float) -> float:
    """Undirected heading separation in [0, 90]. Parallel=0, perpendicular=90."""
    delta = abs(h1 - h2) % 180.0
    if delta > 90.0:
        delta = 180.0 - delta
    return delta


def _attr(raw: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if name in raw and raw[name] not in (None, ""):
            return raw[name]
    for key, value in raw.items():
        short = str(key).rsplit(".", 1)[-1]
        if short in names and value not in (None, ""):
            return value
    return None


def road_identity(raw: Mapping[str, Any]) -> tuple[str, str, str]:
    name = str(_attr(raw, "street_name", "STREET_NAME") or "").strip()
    stype = str(_attr(raw, "street_type_name", "STREET_TYPE_NAME", "street_type") or "").strip()
    key = _attr(raw, "street_key", "STREET_KEY", "objectid", "OBJECTID")
    label = " ".join(part for part in (name, stype) if part).strip() or "unnamed"
    road_id = str(key) if key is not None else label
    return road_id, label, stype


def _paths_from_feature(raw: Mapping[str, Any]) -> list[list[tuple[float, float]]]:
    geom = raw.get("geometry") if isinstance(raw.get("geometry"), Mapping) else raw
    paths = []
    if isinstance(geom, Mapping):
        for path in geom.get("paths") or raw.get("paths") or []:
            pts = [(float(x), float(y)) for x, y in path]
            if len(pts) >= 2:
                paths.append(pts)
    elif raw.get("paths"):
        for path in raw["paths"]:
            pts = [(float(x), float(y)) for x, y in path]
            if len(pts) >= 2:
                paths.append(pts)
    return paths


def project_roads(features: Sequence[Mapping[str, Any]], projector: LocalProjector) -> list[RoadFeatureXY]:
    grouped: dict[str, dict[str, Any]] = {}
    for raw in features:
        road_id, name, stype = road_identity(raw)
        bucket = grouped.setdefault(
            road_id,
            {"road_id": road_id, "name": name, "street_type": stype, "lines": []},
        )
        if not bucket["name"] and name:
            bucket["name"] = name
        if not bucket["street_type"] and stype:
            bucket["street_type"] = stype
        for path in _paths_from_feature(raw):
            xy = [projector.xy(lon, lat) for lon, lat in path]
            if len(xy) >= 2:
                line = LineString(xy)
                if line.length >= 1.0:
                    bucket["lines"].append(line)
    roads: list[RoadFeatureXY] = []
    for bucket in grouped.values():
        lines = bucket["lines"]
        if not lines:
            continue
        geom = lines[0] if len(lines) == 1 else MultiLineString(lines)
        roads.append(
            RoadFeatureXY(
                road_id=str(bucket["road_id"]),
                name=str(bucket["name"] or bucket["road_id"]),
                street_type=str(bucket["street_type"] or ""),
                geom=geom,
                paths=list(lines),
            )
        )
    return roads


def polygon_from_rings(rings: Sequence[Sequence[Sequence[float]]], projector: LocalProjector) -> Polygon | None:
    if not rings:
        return None
    shells = []
    for ring in rings:
        xy = [projector.xy(float(x), float(y)) for x, y in ring]
        if len(xy) >= 4:
            shells.append(xy)
    if not shells:
        return None
    holes = shells[1:] if len(shells) > 1 else None
    poly = Polygon(shells[0], holes)
    if not poly.is_valid:
        poly = poly.buffer(0)
    if poly.is_empty:
        return None
    return poly


def _heading_at(line: LineString, point: Point) -> float | None:
    if line.length <= 0:
        return None
    t = min(max(line.project(point), 0.0), line.length)
    delta = min(4.0, max(line.length * 0.05, 0.5))
    a = line.interpolate(max(t - delta, 0.0))
    b = line.interpolate(min(t + delta, line.length))
    if a.distance(b) < 1e-6:
        return None
    return heading_deg((a.x, a.y), (b.x, b.y))


def _is_bulb_vertex(prev_len: float, next_len: float) -> bool:
    return prev_len < CUL_DE_SAC_FACET_MAX_M and next_len < CUL_DE_SAC_FACET_MAX_M


def detect_intersections(roads: Sequence[RoadFeatureXY]) -> list[IntersectionXY]:
    found: list[IntersectionXY] = []
    for i, a in enumerate(roads):
        for b in roads[i + 1 :]:
            if a.geom.distance(b.geom) > INTERSECTION_JOIN_M:
                continue
            inter = a.geom.intersection(b.geom.buffer(INTERSECTION_JOIN_M))
            if inter.is_empty:
                continue
            pt = inter.centroid
            ha = _best_heading(a, pt)
            hb = _best_heading(b, pt)
            if ha is None or hb is None:
                continue
            angle = heading_separation_deg(ha, hb)
            if angle < INTERSECTION_HEADING_DEG:
                continue
            kind = "crossing" if a.geom.intersects(b.geom) else "t_junction"
            found.append(
                IntersectionXY(
                    x=float(pt.x),
                    y=float(pt.y),
                    road_ids=(a.road_id, b.road_id),
                    road_names=(a.name, b.name),
                    angle_deg=round(angle, 2),
                    kind=kind,
                )
            )
        found.extend(_same_road_bends(a))
    return _dedupe_intersections(found)


def _best_heading(road: RoadFeatureXY, point: Point) -> float | None:
    best: tuple[float, float] | None = None
    for path in road.paths or [road.geom]:
        if path.is_empty or path.length <= 0:
            continue
        dist = path.distance(point)
        heading = _heading_at(path if isinstance(path, LineString) else LineString(path.coords), point)
        if heading is None:
            continue
        if best is None or dist < best[0]:
            best = (dist, heading)
    return None if best is None else best[1]


def _same_road_bends(road: RoadFeatureXY) -> list[IntersectionXY]:
    bends: list[IntersectionXY] = []
    for path in road.paths:
        coords = list(path.coords)
        for i in range(1, len(coords) - 1):
            prev_len = math.hypot(coords[i][0] - coords[i - 1][0], coords[i][1] - coords[i - 1][1])
            next_len = math.hypot(coords[i + 1][0] - coords[i][0], coords[i + 1][1] - coords[i][1])
            if _is_bulb_vertex(prev_len, next_len):
                continue
            if prev_len < BEND_SEGMENT_MIN_M or next_len < BEND_SEGMENT_MIN_M:
                continue
            h1 = heading_deg(coords[i - 1], coords[i])
            h2 = heading_deg(coords[i], coords[i + 1])
            angle = heading_separation_deg(h1, h2)
            if angle < BEND_HEADING_DEG:
                continue
            bends.append(
                IntersectionXY(
                    x=float(coords[i][0]),
                    y=float(coords[i][1]),
                    road_ids=(road.road_id,),
                    road_names=(road.name,),
                    angle_deg=round(angle, 2),
                    kind="corner_bend",
                )
            )
    return bends


def _dedupe_intersections(items: Sequence[IntersectionXY], radius_m: float = 8.0) -> list[IntersectionXY]:
    kept: list[IntersectionXY] = []
    for item in sorted(items, key=lambda row: -row.angle_deg):
        if any(math.hypot(item.x - other.x, item.y - other.y) <= radius_m for other in kept):
            continue
        kept.append(item)
    return kept


def _outward_normal(polygon: Polygon, x0: float, y0: float, x1: float, y1: float) -> tuple[float, float]:
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy) or 1.0
    right = (dy / length, -dx / length)
    left = (-dy / length, dx / length)
    mid_x, mid_y = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    probe = Point(mid_x + right[0] * 1.25, mid_y + right[1] * 1.25)
    if polygon.contains(probe):
        return left
    return right


def _edge_contact(
    edge: LineString,
    roads: Sequence[RoadFeatureXY],
    polygon: Polygon,
) -> tuple[float, list[str], list[str], list[str]]:
    """Frontage is sampled contact that is outward, nearby, and heading-aligned.

    A road buffer that merely nicks a vertex does not count: those samples fail
    the alignment test and/or do not accumulate MIN_FRONTAGE_M of contact.
    """
    if edge.length < 1.0 or not roads:
        return 0.0, [], [], []
    nx, ny = _outward_normal(polygon, edge.coords[0][0], edge.coords[0][1], edge.coords[-1][0], edge.coords[-1][1])
    edge_heading = heading_deg(edge.coords[0], edge.coords[-1])
    n_samples = max(int(edge.length / SAMPLE_SPACING_M), 3)
    spacing = edge.length / n_samples
    per_road: dict[str, dict[str, Any]] = {}
    for i in range(n_samples):
        point = edge.interpolate((i + 0.5) / n_samples, normalized=True)
        for road in roads:
            dist = float(road.geom.distance(point))
            if dist > ROAD_PROXIMITY_M:
                continue
            nearest = road.geom.interpolate(road.geom.project(point))
            vx, vy = nearest.x - point.x, nearest.y - point.y
            if vx * nx + vy * ny <= 0:
                continue
            road_heading = _best_heading(road, point)
            if road_heading is None:
                continue
            if heading_separation_deg(edge_heading, road_heading) > ROAD_ALIGN_DEG:
                continue
            bucket = per_road.setdefault(
                road.road_id,
                {"contact": 0.0, "name": road.name, "street_type": road.street_type},
            )
            bucket["contact"] += spacing
    if not per_road:
        return 0.0, [], [], []
    contact = sum(item["contact"] for item in per_road.values())
    ids = [rid for rid, item in per_road.items() if item["contact"] >= 0.4]
    names = list(dict.fromkeys(per_road[rid]["name"] for rid in ids))
    types = list(dict.fromkeys(per_road[rid]["street_type"] for rid in ids))
    return contact, ids, names, types


def extract_road_facing_edges(polygon: Polygon, roads: Sequence[RoadFeatureXY]) -> list[RoadFacingEdge]:
    if not roads:
        return []
    simple = polygon.simplify(EDGE_SIMPLIFY_M)
    if simple.is_empty:
        return []
    coords = list(simple.exterior.coords)
    edges: list[RoadFacingEdge] = []
    for (x0, y0), (x1, y1) in zip(coords[:-1], coords[1:]):
        edge = LineString([(x0, y0), (x1, y1)])
        if edge.length < 1.0:
            continue
        contact, ids, names, types = _edge_contact(edge, roads, simple)
        if contact < MIN_CONTACT_M:
            continue
        edges.append(
            RoadFacingEdge(
                x0=float(x0),
                y0=float(y0),
                x1=float(x1),
                y1=float(y1),
                length_m=round(float(edge.length), 3),
                heading_deg=round(heading_deg((x0, y0), (x1, y1)), 2),
                contact_m=round(contact, 3),
                road_ids=list(dict.fromkeys(ids)),
                road_names=list(dict.fromkeys(names)),
                street_types=list(dict.fromkeys(types)),
            )
        )
    return edges


def cluster_sides(edges: Sequence[RoadFacingEdge]) -> list[RoadFacingSide]:
    if not edges:
        return []
    def _adjacent(a: RoadFacingEdge, b: RoadFacingEdge) -> bool:
        return math.hypot(b.x0 - a.x1, b.y0 - a.y1) <= 8.0

    def _mergeable(a: RoadFacingEdge, b: RoadFacingEdge) -> bool:
        sep = heading_separation_deg(a.heading_deg, b.heading_deg)
        same_road = bool(set(a.road_ids) & set(b.road_ids)) or bool(set(a.road_names) & set(b.road_names))
        return sep <= SIDE_MERGE_HEADING_DEG or (same_road and sep <= CURVE_MERGE_HEADING_DEG)

    clusters: list[list[RoadFacingEdge]] = [[edges[0]]]
    for edge in edges[1:]:
        prev = clusters[-1][-1]
        if _adjacent(prev, edge) and _mergeable(prev, edge):
            clusters[-1].append(edge)
        else:
            clusters.append([edge])
    if len(clusters) > 1:
        first, last = clusters[0][0], clusters[-1][-1]
        if _adjacent(last, first) and _mergeable(last, first):
            clusters[0] = clusters[-1] + clusters[0]
            clusters.pop()

    total_contact = sum(max(edge.contact_m, edge.length_m) for edge in edges) or 1.0
    sides: list[RoadFacingSide] = []
    for group in clusters:
        meaningful = sum(max(edge.contact_m, 0.0) for edge in group)
        if meaningful < MIN_FRONTAGE_M:
            continue
        length = sum(edge.length_m for edge in group)
        headings = [edge.heading_deg for edge in group]
        span = 0.0
        if len(headings) >= 2:
            span = max(heading_separation_deg(a, b) for a in headings for b in headings)
        ids = list(dict.fromkeys(rid for edge in group for rid in edge.road_ids))
        names = list(dict.fromkeys(name for edge in group for name in edge.road_names))
        types = list(dict.fromkeys(stype for edge in group for stype in edge.street_types))
        mx = sum((edge.x0 + edge.x1) / 2.0 for edge in group) / len(group)
        my = sum((edge.y0 + edge.y1) / 2.0 for edge in group) / len(group)
        sides.append(
            RoadFacingSide(
                heading_deg=round(group[len(group) // 2].heading_deg, 2),
                length_m=round(length, 3),
                contact_m=round(meaningful, 3),
                frontage_ratio=round(meaningful / total_contact, 4),
                road_ids=ids,
                road_names=names,
                street_types=types,
                midpoint_xy=(round(mx, 3), round(my, 3)),
                start_xy=(round(group[0].x0, 3), round(group[0].y0, 3)),
                end_xy=(round(group[-1].x1, 3), round(group[-1].y1, 3)),
                heading_span_deg=round(span, 2),
                n_edges=len(group),
                curved_single_road=span >= 20.0 and len(names) <= 1,
                cul_de_sac_type=any(normalize_street_type(t) in CUL_DE_SAC_TYPES for t in types),
            )
        )
    sides.sort(key=lambda side: -side.contact_m)
    return sides


def nearest_intersection(
    point: Point,
    intersections: Sequence[IntersectionXY],
) -> tuple[IntersectionXY | None, float | None]:
    best: IntersectionXY | None = None
    best_d: float | None = None
    for item in intersections:
        dist = math.hypot(point.x - item.x, point.y - item.y)
        if best_d is None or dist < best_d:
            best, best_d = item, dist
    return best, None if best_d is None else round(best_d, 3)


def roads_union(roads: Sequence[RoadFeatureXY]):
    geoms = [road.geom for road in roads if road.geom is not None and not road.geom.is_empty]
    if not geoms:
        return None
    return unary_union(geoms)


def load_road_features(payload: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    if payload is None:
        return []
    if isinstance(payload, Mapping):
        features = payload.get("features")
        if features is None:
            return []
        return [dict(item) for item in features]
    return [dict(item) for item in payload]


def projector_for(
    parcels: Iterable[Mapping[str, Any]],
    road_features: Sequence[Mapping[str, Any]],
) -> LocalProjector:
    lons: list[float] = []
    lats: list[float] = []
    for parcel in parcels:
        for ring in ((parcel.get("geometry") or {}).get("rings") or []):
            for x, y in ring:
                lons.append(float(x))
                lats.append(float(y))
    for raw in road_features:
        for path in _paths_from_feature(raw):
            for x, y in path:
                lons.append(float(x))
                lats.append(float(y))
    if not lons:
        return LocalProjector(0.0, 0.0)
    return LocalProjector.from_points(lons, lats)
