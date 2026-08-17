"""Corner Stand Detection v1 — synthetic GIS + listing tests. No listing IDs."""

from __future__ import annotations

import ast
import hashlib
import io
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from shapely.geometry import LineString, Polygon

from backend.gis.estate_ags_matching.corner_geometry_v1 import (
    RoadFeatureXY,
    detect_intersections,
)
from backend.gis.estate_ags_matching.listing_corner_evidence_v1 import (
    inspect_frame_roads,
    observe_listing_corner,
)
from backend.gis.estate_ags_matching.listing_corner_gate_v1 import (
    apply_listing_corner_gate,
    apply_pool_then_corner_gate,
    survives_listing_corner_gate,
)
from backend.gis.estate_ags_matching.os_scoring_v2 import V2_WEIGHTS_NO_BUILDING
from backend.gis.estate_ags_matching.parcel_corner_v1 import (
    CURVED_ROAD_RULE,
    classify_estate,
    classify_polygon,
)

ROOT = Path(__file__).resolve().parents[1]
FROZEN_WEIGHTS = {
    "pool_presence": 0.14,
    "shape_v2": 0.36,
    "spatial_v2": 0.22,
    "aerial": 0.12,
    "exterior": 0.06,
    "gis": 0.03,
    "stand_size": 0.07,
}
ALGO_FILES = (
    ROOT / "backend/gis/estate_ags_matching/corner_geometry_v1.py",
    ROOT / "backend/gis/estate_ags_matching/parcel_corner_v1.py",
    ROOT / "backend/gis/estate_ags_matching/listing_corner_evidence_v1.py",
    ROOT / "backend/gis/estate_ags_matching/listing_corner_gate_v1.py",
)


def _road(road_id: str, coords, name: str | None = None, street_type: str = "DRIVE") -> RoadFeatureXY:
    line = LineString(coords)
    return RoadFeatureXY(
        road_id=road_id,
        name=name or road_id,
        street_type=street_type,
        geom=line,
        paths=[line],
    )


def _square(x0=0.0, y0=0.0, size=30.0) -> Polygon:
    return Polygon([(x0, y0), (x0 + size, y0), (x0 + size, y0 + size), (x0, y0 + size), (x0, y0)])


def _png(image: Image.Image) -> bytes:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def _two_road_aerial() -> bytes:
    image = Image.new("RGB", (320, 240), (12, 14, 18))
    draw = ImageDraw.Draw(image)
    # House block
    draw.rectangle([70, 40, 210, 150], fill=(210, 200, 185))
    # Bottom road + right road (L corner) with street lights
    draw.rectangle([0, 185, 319, 230], fill=(28, 28, 30))
    draw.rectangle([250, 0, 310, 230], fill=(28, 28, 30))
    for x in range(20, 250, 28):
        draw.ellipse([x, 198, x + 6, 204], fill=(240, 230, 180))
    for y in range(20, 190, 28):
        draw.ellipse([272, y, 278, y + 6], fill=(240, 230, 180))
    return _png(image)


def _one_road_aerial() -> bytes:
    image = Image.new("RGB", (320, 240), (18, 22, 16))
    draw = ImageDraw.Draw(image)
    draw.rectangle([40, 20, 260, 160], fill=(200, 190, 170))
    draw.rectangle([0, 190, 319, 235], fill=(40, 40, 42))
    for x in range(16, 300, 30):
        draw.ellipse([x, 205, x + 5, 210], fill=(230, 220, 170))
    return _png(image)


def test_scoring_v2_weights_unchanged_and_corner_not_a_weight():
    assert V2_WEIGHTS_NO_BUILDING == FROZEN_WEIGHTS
    assert "corner" not in V2_WEIGHTS_NO_BUILDING
    source = (ROOT / "backend/gis/estate_ags_matching/os_scoring_v2.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    assigns = [
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(getattr(target, "id", None) == "V2_WEIGHTS_NO_BUILDING" for target in node.targets)
    ]
    assert assigns
    gate_src = (ROOT / "backend/gis/estate_ags_matching/listing_corner_gate_v1.py").read_text(encoding="utf-8")
    assert "Does not modify Scoring v2 weights" in gate_src
    assert "Pool Gate → Corner Gate" in gate_src or "Pool Gate → Corner Gate" in gate_src.replace("→", "->")


def test_algorithm_modules_have_no_listing_or_stand_hardcodes():
    banned = ("117262832", "654", "467", "405", "644", "456", "338", "carlswald")
    for path in ALGO_FILES:
        text = path.read_text(encoding="utf-8").lower()
        for token in banned:
            assert token not in text, f"{path.name} contains {token}"


def test_clear_90_degree_street_corner():
    parcel = _square()
    roads = [
        _road("south", [(-10, -6), (50, -6)], name="SOUTH STREET"),
        _road("east", [(36, -10), (36, 50)], name="EAST STREET"),
    ]
    result = classify_polygon(parcel, roads, detect_intersections(roads))
    assert result.classification == "YES"
    assert result.n_road_facing_sides >= 2
    assert result.angle_between_sides_deg is not None
    assert result.angle_between_sides_deg >= 70
    assert result.confidence >= 0.72


def test_angled_intersection():
    import math

    width, depth, angle = 28.0, 26.0, math.radians(58.0)
    dx, dy = depth * math.cos(angle), depth * math.sin(angle)
    parcel = Polygon([(0, 0), (width, 0), (width + dx, dy), (dx, dy), (0, 0)])
    # Offset the angled road ~8 m outward along the side normal.
    nx, ny = dy / depth, -dx / depth  # right-hand outward of the first angled? south edge is first.
    # Angled east side is (width,0) -> (width+dx, dy); outward right of that edge.
    ex, ey = dx, dy
    elen = math.hypot(ex, ey) or 1.0
    ox, oy = ey / elen, -ex / elen
    roads = [
        _road("a", [(-8, -6), (width + 20, -6)], name="MAIN ROAD"),
        _road(
            "b",
            [
                (width - 12 * (ex / elen) + 8 * ox, 0 - 12 * (ey / elen) + 8 * oy),
                (width + dx + 16 * (ex / elen) + 8 * ox, dy + 16 * (ey / elen) + 8 * oy),
            ],
            name="ANGLED ROAD",
        ),
    ]
    result = classify_polygon(parcel, roads, detect_intersections(roads))
    assert result.classification == "YES"
    assert result.n_road_facing_sides >= 2
    assert result.angle_between_sides_deg is not None
    assert 35 <= result.angle_between_sides_deg <= 90


def test_t_junction_corner_parcel():
    parcel = _square()
    through = _road("through", [(-20, -6), (80, -6)], name="THROUGH ROAD")
    stem = _road("stem", [(36, -6), (36, 60)], name="STEM CLOSE", street_type="CLOSE")
    result = classify_polygon(parcel, [through, stem], detect_intersections([through, stem]))
    assert result.classification == "YES"
    assert result.nearest_intersection_kind in {"t_junction", "crossing"}


def test_single_road_internal_parcel():
    parcel = _square(x0=0, y0=0)
    roads = [_road("only", [(-20, -6), (80, -6)], name="ONLY ROAD")]
    result = classify_polygon(parcel, roads, detect_intersections(roads))
    assert result.classification == "NO"
    assert result.n_road_facing_sides <= 1


def test_curved_single_road_frontage():
    # Parcel sits on the outside of a single curved road; one frontage after clustering.
    front = [(x, 4.0 * np.sin(np.pi * x / 40.0) - 6.0) for x in np.linspace(0, 40, 12)]
    parcel = Polygon([(0, 0)] + [(x, 0) for x, _ in front] + [(40, 0), (40, 28), (0, 28), (0, 0)])
    road_pts = [(x, 4.0 * np.sin(np.pi * x / 40.0) - 12.0) for x in np.linspace(-8, 48, 20)]
    roads = [_road("curve", road_pts, name="CURVE CRESCENT", street_type="CRESCENT")]
    result = classify_polygon(parcel, roads, detect_intersections(roads))
    assert result.classification in {"NO", "UNKNOWN"}
    assert result.classification != "YES"
    assert "cul-de-sac" in CURVED_ROAD_RULE.lower() or "cul-de-sac" in CURVED_ROAD_RULE
    assert "curved" in CURVED_ROAD_RULE.lower()


def test_cul_de_sac_is_not_automatically_corner():
    # Cul-de-sac bulb south of a mid-bulb parcel: single frontage.
    bulb = [(10 + 12 * np.cos(t), -6 + 8 * np.sin(t)) for t in np.linspace(np.pi, 2 * np.pi, 10)]
    stem = [(-20, -6), (10, -6)]
    roads = [_road("close", stem + bulb + [(22, -6)], name="END CLOSE", street_type="CLOSE")]
    parcel = _square(x0=4, y0=2, size=22)
    result = classify_polygon(parcel, roads, detect_intersections(roads))
    assert result.classification in {"NO", "UNKNOWN"}
    assert result.classification != "YES"


def test_tiny_road_buffer_vertex_contact():
    parcel = _square(x0=0, y0=0, size=30)
    # Road only nicks the southwest vertex.
    roads = [_road("nick", [(-25, -1.5), (-0.4, -1.5), (-0.4, -25)], name="DISTANT ROAD")]
    result = classify_polygon(parcel, roads, detect_intersections(roads))
    assert result.classification != "YES"


def test_irregular_parcel_one_road():
    parcel = Polygon(
        [
            (0, 0),
            (8, -2),
            (18, 1),
            (32, -1),
            (36, 8),
            (30, 22),
            (12, 26),
            (2, 18),
            (0, 0),
        ]
    )
    roads = [_road("south", [(-10, -8), (50, -8)], name="SOUTH ROAD")]
    result = classify_polygon(parcel, roads, detect_intersections(roads))
    assert result.classification in {"NO", "UNKNOWN"}
    assert result.classification != "YES"


def test_estate_boundary_parcel_without_second_road():
    # West edge is the estate boundary (open land); only the east side has a road.
    parcel = _square(x0=0, y0=0, size=28)
    roads = [_road("east", [(34, -10), (34, 50)], name="EAST ROAD")]
    result = classify_polygon(parcel, roads, detect_intersections(roads))
    assert result.classification in {"NO", "UNKNOWN"}
    assert result.classification != "YES"


def test_missing_road_data_is_unknown():
    result = classify_polygon(_square(), [], [])
    assert result.classification == "UNKNOWN"
    assert result.reason == "missing_road_data"
    layer = classify_estate(
        [{"stand_number": "A", "geometry": {"rings": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}}],
        {"features": []},
    )
    assert layer.missing_road_data is True
    assert layer.n_unknown == 1
    assert layer.n_yes == 0


def test_listing_explicit_corner_stand_text():
    evidence = observe_listing_corner(text="Superb corner stand with private pool.")
    assert evidence.classification == "YES"
    assert evidence.confidence >= 0.85
    assert evidence.high_confidence is True
    assert any("corner stand" in hit.lower() for hit in evidence.text_evidence)


def test_listing_aerial_two_road_evidence():
    evidence = observe_listing_corner(
        photos={"aerial-01": _two_road_aerial()},
        viewpoints={"aerial-01": "aerial_near_nadir"},
    )
    assert evidence.classification == "YES"
    assert evidence.aerial_evidence is True
    assert evidence.frame_ids == ["aerial-01"]


def test_listing_one_visible_road_is_unknown_not_no():
    evidence = observe_listing_corner(
        photos={"street-01": _one_road_aerial()},
        viewpoints={"street-01": "aerial_near_nadir"},
    )
    assert evidence.classification == "UNKNOWN"
    assert evidence.classification != "NO"


def test_corner_gate_high_yes_removes_no_keeps_unknown():
    candidates = [
        {"stand_number": "1", "parcel_corner": "YES"},
        {"stand_number": "2", "parcel_corner": "NO"},
        {"stand_number": "3", "parcel_corner": "UNKNOWN"},
    ]
    records = [
        {"stand_number": "1", "classification": "YES", "confidence": 0.9, "reason": "ok"},
        {"stand_number": "2", "classification": "NO", "confidence": 0.9, "reason": "ok"},
        {"stand_number": "3", "classification": "UNKNOWN", "confidence": 0.0, "reason": "ok"},
    ]
    gate = apply_listing_corner_gate(candidates, records, "YES", listing_confidence=0.94, listing_high_confidence=True)
    ids = {str(row["stand_number"]) for row in gate.survivors}
    assert ids == {"1", "3"}
    assert gate.removed_confident_no == 1
    assert any(row["stand_number"] == "3" for row in gate.unresolved)


def test_corner_gate_listing_unknown_and_weak_no_are_neutral():
    assert survives_listing_corner_gate("NO", "UNKNOWN")[0] is True
    keep, reason = survives_listing_corner_gate("YES", "NO", listing_confidence=0.6, positive_non_corner_evidence=False)
    assert keep is True
    assert reason == "listing_corner_no_treated_as_neutral_v1"


def test_pool_then_corner_gate_counts_independently():
    candidates = [{"stand_number": str(i)} for i in range(6)]
    inventory = [
        {"stand_number": "0", "pool_status": "YES"},
        {"stand_number": "1", "pool_status": "NO"},
        {"stand_number": "2", "pool_status": "UNKNOWN"},
        {"stand_number": "3", "pool_status": "YES"},
        {"stand_number": "4", "pool_status": "YES"},
        {"stand_number": "5", "pool_status": "YES"},
    ]
    corners = [
        {"stand_number": "0", "classification": "YES"},
        {"stand_number": "1", "classification": "NO"},
        {"stand_number": "2", "classification": "NO"},
        {"stand_number": "3", "classification": "NO"},
        {"stand_number": "4", "classification": "UNKNOWN"},
        {"stand_number": "5", "classification": "YES"},
    ]
    pool, corner = apply_pool_then_corner_gate(candidates, inventory, "YES", corners, "YES", listing_confidence=0.94)
    assert pool.starting_count == 6
    assert pool.total_survivors == 5  # dropped inventory NO stand 1
    assert corner.starting_count == 5
    assert corner.removed_confident_no == 2  # stands 2 and 3
    assert corner.total_survivors == 3


def test_historical_freeze_hash_untouched():
    freeze = ROOT / "data/investigations/blind_117262832_complete_estate/freeze.json"
    recorded = (ROOT / "data/investigations/blind_117262832_complete_estate/freeze.sha256").read_text(encoding="utf-8").strip()
    digest = hashlib.sha256(freeze.read_bytes()).hexdigest()
    assert digest == recorded
    assert recorded == "32ecd4b526d4a299e143c869761664a9ed7a4b2d9ae65aba6ed300583a1dd10a"
