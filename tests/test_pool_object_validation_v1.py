"""Pool Object Validation v1 — synthetic + frozen-OS re-eval. No ranking changes."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import numpy as np

from backend.gis.estate_ags_matching.hybrid_listing_pool_geometry_v1 import (
    FrameGeometry,
    combine_listing_frames,
)
from backend.gis.estate_ags_matching.listing_corner_gate_v1 import survives_listing_corner_gate
from backend.gis.estate_ags_matching.listing_pool_gate_v1 import survives_listing_pool_gate
from backend.gis.estate_ags_matching.os_scoring_v2 import V2_WEIGHTS_NO_BUILDING, shape_v2_similarity
from backend.gis.estate_ags_matching.pool_object_validation_v1 import (
    VALIDATION_VERSION,
    classify_listing_water_role,
    listing_border_risk,
    mask_from_norm_contour,
    select_principal_listing_pool,
    true_parcel_mask_from_geometry,
    validate_candidate_pool_object,
    validate_listing_pool_object,
    validate_os_payload,
)
from backend.vision.object_segmentation import contour_geometry

ROOT = Path(__file__).resolve().parents[1]
OS_DIR = ROOT / "data/investigations/object_segmentation_v1/carlswald_north/json"
GIS_PATH = ROOT / "data/gis/carlswald_north_corrected_001.json"
ALGO_FILES = (
    ROOT / "backend/gis/estate_ags_matching/pool_object_validation_v1.py",
    ROOT / "backend/gis/estate_ags_matching/hybrid_listing_pool_geometry_v1.py",
)
FROZEN_WEIGHTS = {
    "pool_presence": 0.14,
    "shape_v2": 0.36,
    "spatial_v2": 0.22,
    "aerial": 0.12,
    "exterior": 0.06,
    "gis": 0.03,
    "stand_size": 0.07,
}
FREEZE_SHA = {
    "117262832": "32ecd4b526d4a299e143c869761664a9ed7a4b2d9ae65aba6ed300583a1dd10a",
    "116978058": "8cf975a7a14326c520dbfcdba48a73d24df6e3605de1632d6174abab72d97628",
    "116889694": "69b8ea31f1ecdb77311937b2e3db829ef14ecea33b8534d2730a5ed57d331465",
    "116778622": "3eb8f54dc03f804cff519b65d7f452444ff91e7c4133a9ec7b9b638a3337875f",
    "116273255": "227a67c7100639300916d3a405da6030ff90b5d1dff54209c0160290c24ba500",
    "116223230": "be73a1615c5f87f678f9c4948c0d41b22d3f166aea3f10eb05b1ed6e98404126",
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _gis_by_stand() -> dict[str, dict]:
    gis = json.loads(GIS_PATH.read_text(encoding="utf-8"))
    return {str(p["stand_number"]): p for p in gis["parcels"]}


def _clip(**over):
    base = {
        "pool": 0.6,
        "roof": 0.05,
        "shadow": 0.05,
        "road": 0.05,
        "driveway": 0.05,
        "lawn": 0.05,
        "vegetation": 0.02,
        "deck": 0.1,
        "wall": 0.02,
        "furniture": 0.02,
        "bathtub": 0.0,
        "interior": 0.0,
    }
    base.update(over)
    return base


def _rect_mask(h, w, y0, x0, y1, x1) -> np.ndarray:
    m = np.zeros((h, w), dtype=bool)
    m[y0:y1, x0:x1] = True
    return m


def _frame(
    mid,
    *,
    vp="pool_overview",
    source="yoloe_sam2",
    ready=True,
    area=0.12,
    aspect=2.6,
    solidity=0.67,
    compactness=0.34,
    indents=1,
    clip=None,
    centroid=(0.5, 0.72),
    contour=None,
    conf=0.5,
):
    if contour is None:
        cx, cy = centroid
        contour = [
            [cx - 0.15, cy - 0.08],
            [cx + 0.15, cy - 0.08],
            [cx + 0.15, cy + 0.08],
            [cx - 0.15, cy + 0.08],
            [cx - 0.15, cy - 0.08],
        ]
    return FrameGeometry(
        media_id=mid,
        viewpoint=vp,
        source=source,
        source_reason="t",
        scoring_ready=ready,
        pool_present=True,
        yoloe_conf=conf,
        n_components=1,
        dominant={
            "structural_support": 0.5,
            "confidence": conf,
            "clip": clip or _clip(),
            "relative_area": area,
            "centroid_xy": list(centroid),
            "geometry": {
                "relative_area": area,
                "compactness": compactness,
                "solidity": solidity,
                "aspect_ratio": aspect,
                "n_major_indents": indents,
            },
            "contour_image": contour,
        },
        secondary=None,
        component_relation={},
        descriptors={"orientation_deg": 10.0, "oblique": vp not in {"aerial_near_nadir", "aerial_oblique"}, "aspect_ratio": aspect, "solidity": solidity},
        contour_image=contour,
        geometry_quality=50.0 if vp == "aerial_near_nadir" else 30.0,
    )


def test_algorithm_modules_have_no_listing_or_stand_hardcodes():
    for path in ALGO_FILES:
        text = path.read_text(encoding="utf-8")
        lower = text.lower()
        for token in (
            "116978058",
            "116889694",
            "117262832",
            "116778622",
            "ground_truth",
            "expected_stand",
            "carlswald",
            "stand 338",
            "stand_338",
        ):
            assert token not in text and token not in lower
        assert "338" not in path.name


def test_ranking_weights_and_gates_unchanged():
    assert V2_WEIGHTS_NO_BUILDING == FROZEN_WEIGHTS
    source = (ROOT / "backend/gis/estate_ags_matching/os_scoring_v2.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    assigns = [
        node
        for node in tree.body
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "V2_WEIGHTS_NO_BUILDING" for t in node.targets)
    ]
    assert assigns
    assert survives_listing_pool_gate("NO", "YES") is False
    assert survives_listing_pool_gate("YES", "YES") is True
    assert survives_listing_corner_gate("NO", "YES", listing_confidence=0.9)[0] is False
    listing, parts = shape_v2_similarity(
        {"elongation": 1.4, "solidity": 0.9, "circularity": 0.7, "n_corners": 4, "n_major_indents": 1, "max_indent": 0.1, "sharp_frac": 0.4, "radial_cv": 0.1, "hu_log": [0.1] * 7},
        {"elongation": 1.4, "solidity": 0.9, "circularity": 0.7, "n_corners": 4, "n_major_indents": 1, "max_indent": 0.1, "sharp_frac": 0.4, "radial_cv": 0.1, "hu_log": [0.1] * 7},
    )
    assert listing is not None
    assert "chamfer" in parts or listing >= 0.5
    os_src = (ROOT / "backend/vision/object_segmentation.py").read_text(encoding="utf-8")
    assert 'item[2]["pool"] >= 0.40' not in os_src
    assert "validate_candidate_pool_object" in os_src
    assert 'SEGMENTATION_VERSION = "object_segmentation_v1"' in os_src
    corner_src = (ROOT / "backend/gis/estate_ags_matching/listing_corner_gate_v1.py").read_text(encoding="utf-8")
    assert "UNKNOWN is always retained" in corner_src
    gate_src = (ROOT / "backend/gis/estate_ags_matching/listing_pool_gate_v1.py").read_text(encoding="utf-8")
    assert "Hard gate: discard only the opposite confident class" in gate_src


def test_historical_freeze_hashes_unchanged():
    for listing_id, digest in FREEZE_SHA.items():
        recorded = ROOT / f"data/investigations/blind_{listing_id}_complete_estate/freeze.sha256"
        assert recorded.is_file()
        assert recorded.read_text(encoding="utf-8").strip() == digest


def test_frozen_os_json_bytes_not_rewritten_by_this_module():
    expected = {
        "677": "CONFIRMED",
        "612": "REJECTED",
        "408": "UNKNOWN",
        "420": "CONFIRMED",
        "570": "REJECTED",
        "370": "REJECTED",
        "338": "REJECTED",
    }
    for stand, status in expected.items():
        payload = json.loads((OS_DIR / f"{stand}.json").read_text(encoding="utf-8"))
        assert payload["pool"]["status"] == status
        assert payload["version"] == "object_segmentation_v1"


def test_low_pool_clip_good_parcel_yard_geometry_is_not_rejected():
    parcel = np.zeros((160, 160), dtype=bool)
    parcel[30:130, 30:130] = True
    pool = _rect_mask(160, 160, 70, 48, 108, 92)
    geom = contour_geometry(pool)
    val = validate_candidate_pool_object(
        clip=_clip(pool=0.019, roof=0.50, shadow=0.13, road=0.12, driveway=0.20, lawn=0.02),
        geometry=geom,
        mask=pool,
        true_parcel=parcel,
        building_mask=_rect_mask(160, 160, 36, 70, 68, 120),
        road_mask=_rect_mask(160, 160, 120, 30, 150, 70),
        water_frac=0.12,
        centroid_xy=(float(geom["centroid_x"]), float(geom["centroid_y"])),
        building_centroid=(0.62, 0.32),
    )
    assert val.final_status != "REJECTED"
    assert val.final_status in {"UNKNOWN", "CONFIRMED"}
    assert "semantic_conflict" in " ".join(val.reason_codes) or val.final_status == "UNKNOWN"
    assert val.signals.parcel_containment is not None and val.signals.parcel_containment >= 0.9
    assert val.contour_retained is True


def test_high_roof_clip_zero_building_overlap_is_conflict_not_auto_reject():
    parcel = np.zeros((120, 120), dtype=bool)
    parcel[20:100, 20:100] = True
    pool = _rect_mask(120, 120, 55, 40, 85, 78)
    roof = _rect_mask(120, 120, 22, 50, 48, 95)
    geom = contour_geometry(pool)
    val = validate_candidate_pool_object(
        clip=_clip(pool=0.02, roof=0.49),
        geometry=geom,
        mask=pool,
        true_parcel=parcel,
        building_mask=roof,
        road_mask=np.zeros((120, 120), dtype=bool),
        water_frac=0.20,
    )
    assert float(val.signals.building_overlap or 0.0) < 0.05
    assert val.final_status != "REJECTED"
    assert val.final_status == "UNKNOWN"


def test_high_roof_clip_high_building_overlap_rejected():
    parcel = np.zeros((120, 120), dtype=bool)
    parcel[15:110, 15:110] = True
    blob = _rect_mask(120, 120, 40, 40, 80, 85)
    val = validate_candidate_pool_object(
        clip=_clip(pool=0.05, roof=0.55),
        geometry=contour_geometry(blob),
        mask=blob,
        true_parcel=parcel,
        building_mask=blob,
        water_frac=0.05,
    )
    assert val.final_status == "REJECTED"
    assert val.object_role == "roof_or_shadow"
    assert any("roof" in c for c in val.reason_codes)


def test_road_shadow_semantics_and_road_overlap_rejected():
    parcel = np.zeros((140, 140), dtype=bool)
    parcel[20:120, 20:120] = True
    blob = _rect_mask(140, 140, 90, 30, 108, 95)
    road = _rect_mask(140, 140, 88, 20, 125, 120)
    geom = contour_geometry(blob)
    val = validate_candidate_pool_object(
        clip=_clip(pool=0.017, roof=0.17, shadow=0.31, road=0.21, driveway=0.25),
        geometry=geom,
        mask=blob,
        true_parcel=parcel,
        building_mask=_rect_mask(140, 140, 30, 40, 70, 90),
        road_mask=road,
        water_frac=0.04,
    )
    assert val.final_status == "REJECTED"
    assert val.object_role == "roof_or_shadow"


def test_neighbour_inside_padded_crop_outside_true_parcel_rejected():
    crop_h, crop_w = 160, 160
    true_parcel = np.zeros((crop_h, crop_w), dtype=bool)
    true_parcel[40:120, 50:130] = True
    neighbour = _rect_mask(crop_h, crop_w, 55, 8, 95, 48)  # mostly in the 18 m pad
    val = validate_candidate_pool_object(
        clip=_clip(pool=0.55, roof=0.08),
        geometry=contour_geometry(neighbour),
        mask=neighbour,
        true_parcel=true_parcel,
        water_frac=0.4,
    )
    assert val.final_status == "REJECTED"
    assert val.object_role == "neighbouring_pool"
    assert val.signals.parcel_containment is not None
    assert val.signals.parcel_containment < 0.70


def test_candidate_crossing_true_parcel_boundary_rejected():
    true_parcel = np.zeros((150, 150), dtype=bool)
    true_parcel[40:120, 60:130] = True
    crossing = _rect_mask(150, 150, 60, 20, 100, 95)
    val = validate_candidate_pool_object(
        clip=_clip(pool=0.4),
        geometry=contour_geometry(crossing),
        mask=crossing,
        true_parcel=true_parcel,
    )
    assert val.final_status == "REJECTED"
    assert val.object_role == "neighbouring_pool"
    assert val.signals.parcel_containment is not None
    assert 0.08 <= val.signals.parcel_containment <= 0.85


def test_valid_irregular_in_parcel_confirmed():
    parcel = np.zeros((180, 180), dtype=bool)
    parcel[25:155, 25:155] = True
    kidney = _rect_mask(180, 180, 40, 50, 70, 110)
    kidney[55:85, 90:125] = True
    val = validate_candidate_pool_object(
        clip=_clip(pool=0.96, roof=0.01),
        geometry=contour_geometry(kidney),
        mask=kidney,
        true_parcel=parcel,
        building_mask=_rect_mask(180, 180, 90, 55, 140, 120),
        water_frac=0.5,
    )
    assert val.final_status == "CONFIRMED"
    assert val.principal_pool_candidate is True


def test_dark_low_semantic_pool_unknown_not_forced():
    parcel = np.zeros((140, 140), dtype=bool)
    parcel[25:120, 25:120] = True
    blob = _rect_mask(140, 140, 70, 60, 88, 110)  # elongated, modest area
    geom = contour_geometry(blob)
    val = validate_candidate_pool_object(
        clip=_clip(pool=0.03, roof=0.33, road=0.29, shadow=0.10),
        geometry=geom,
        mask=blob,
        true_parcel=parcel,
        building_mask=_rect_mask(140, 140, 30, 40, 65, 95),
        water_frac=0.05,
    )
    assert val.final_status != "CONFIRMED"
    assert val.final_status in {"UNKNOWN", "REJECTED"}


def test_missing_parcel_geometry_is_conservative_unknown():
    blob = _rect_mask(80, 80, 20, 20, 50, 55)
    val = validate_candidate_pool_object(
        clip=_clip(pool=0.2, roof=0.2),
        geometry=contour_geometry(blob),
        mask=blob,
        true_parcel=None,
    )
    assert val.final_status == "UNKNOWN"
    assert val.signals.parcel_containment is None


def test_crop_filled_parcel_mask_is_not_treated_as_true_parcel():
    blob = _rect_mask(90, 90, 30, 30, 55, 60)
    crop = np.ones((90, 90), dtype=bool)
    val = validate_candidate_pool_object(
        clip=_clip(pool=0.7),
        geometry=contour_geometry(blob),
        mask=blob,
        true_parcel=crop,
        water_frac=0.4,
    )
    assert val.final_status != "CONFIRMED"
    assert val.signals.parcel_containment is None


def test_malformed_contour_does_not_crash():
    assert mask_from_norm_contour([[0.1, 0.1], [0.2, 0.2]], 40, 40) is None
    val = validate_listing_pool_object(viewpoint="pool_overview", clip=_clip(), geometry={}, contour=[[0.1, 0.1]])
    assert val.final_status in {"UNKNOWN", "REJECTED"}


def test_tiny_aerial_border_blob_not_principal():
    val = validate_listing_pool_object(
        viewpoint="aerial_near_nadir",
        source="fastsam_fallback",
        clip=_clip(pool=0.51, deck=0.22),
        geometry={"relative_area": 0.0027, "compactness": 0.65, "solidity": 0.95, "aspect_ratio": 2.4, "n_major_indents": 1},
        relative_area=0.0027,
        centroid_xy=(0.646, 0.058),
        scoring_ready=True,
    )
    assert val.principal_pool_candidate is False
    assert val.object_role == "neighbouring_pool"
    assert val.final_status in {"REJECTED", "UNKNOWN"}
    risk, reasons = listing_border_risk(
        viewpoint="aerial_near_nadir",
        relative_area=0.0027,
        centroid_xy=(0.646, 0.058),
    )
    assert risk >= 0.7
    assert any("tiny_aerial" in r or "border" in r for r in reasons)


def test_large_ground_level_border_cropped_pool_can_be_principal():
    val = validate_listing_pool_object(
        viewpoint="pool_overview",
        source="yoloe_sam2",
        clip=_clip(pool=0.69, deck=0.30),
        geometry={"relative_area": 0.148, "compactness": 0.34, "solidity": 0.68, "aspect_ratio": 2.60, "n_major_indents": 2},
        relative_area=0.148,
        centroid_xy=(0.31, 0.81),
        contour=[[0.02, 0.60], [0.69, 0.60], [0.69, 0.99], [0.02, 0.99]],
        scoring_ready=True,
        yoloe_conf=0.6,
    )
    assert val.principal_pool_candidate is True
    assert val.final_status in {"CONFIRMED", "UNKNOWN"}
    assert val.signals.neighbour_risk < 0.4


def test_two_agreeing_overviews_beat_disagreeing_aerial_speck():
    a037 = _frame("ov-a", vp="pool_overview", area=0.065, aspect=2.60, solidity=0.65, clip=_clip(pool=0.40, deck=0.59), centroid=(0.75, 0.85), conf=0.55)
    a038 = _frame("ov-b", vp="pool_overview", area=0.148, aspect=2.601, solidity=0.68, clip=_clip(pool=0.69, deck=0.30), centroid=(0.31, 0.81), conf=0.7)
    aerial = _frame(
        "air-speck",
        vp="aerial_near_nadir",
        source="fastsam_fallback",
        area=0.0027,
        aspect=2.42,
        solidity=0.95,
        compactness=0.65,
        clip=_clip(pool=0.51, deck=0.22),
        centroid=(0.65, 0.058),
        contour=[[0.61, 0.035], [0.68, 0.035], [0.68, 0.086], [0.61, 0.086]],
        conf=0.4,
    )
    summary = combine_listing_frames([aerial, a037, a038])
    assert summary["chosen_id"] in {"ov-a", "ov-b"}
    assert summary["chosen_id"] != "air-speck"
    assert "identity" in (summary.get("frame_selection_reason") or "").lower() or "principal" in (summary.get("note") or "").lower()


def test_combine_still_prefers_valid_aerial_when_identity_agrees():
    aerial = _frame("air", vp="aerial_near_nadir", source="fastsam_fallback", area=0.02, aspect=2.1, solidity=0.9, compactness=0.6, centroid=(0.48, 0.47), clip=_clip(pool=0.7))
    oblique = _frame("obl", vp="pool_overview", source="yoloe_sam2", area=0.12, aspect=2.1, solidity=0.9, compactness=0.55, centroid=(0.5, 0.7), clip=_clip(pool=0.7), conf=0.8)
    summary = combine_listing_frames([aerial, oblique])
    assert summary["chosen_id"] == "air"


def test_spa_does_not_become_official_when_principal_exists():
    principal = _frame("pool", area=0.16, aspect=2.2, centroid=(0.45, 0.70), clip=_clip(pool=0.7))
    spa_frame = _frame(
        "spa",
        area=0.012,
        aspect=1.1,
        solidity=0.95,
        compactness=0.8,
        centroid=(0.72, 0.68),
        clip=_clip(pool=0.55),
        contour=[[0.68, 0.64], [0.76, 0.64], [0.76, 0.72], [0.68, 0.72]],
    )
    spa_frame.dominant["relative_area"] = 0.012
    role = classify_listing_water_role(
        relative_area=0.012,
        secondary_area=0.16,
        adjacent=True,
        neighbour_risk=0.1,
        validation_status="UNKNOWN",
    )
    assert role == "attached_spa"
    summary = combine_listing_frames([principal, spa_frame])
    assert summary["chosen_id"] == "pool"


def test_multiple_valid_viewpoints_same_pool_do_not_average():
    a = _frame("a", vp="pool_overview", aspect=2.55, area=0.10, centroid=(0.5, 0.75))
    b = _frame("b", vp="elevated_exterior", aspect=2.62, area=0.11, centroid=(0.48, 0.70))
    chosen, meta = select_principal_listing_pool([a, b])
    assert chosen is not None
    assert chosen.media_id in {"a", "b"}
    assert meta["multiframe_clusters"]["n_clusters"] >= 1
    assert "not averaged" in (meta["selection_reason"] or "").lower() or "not averaged" in meta["multiframe_clusters"]["note"].lower()


def test_true_parcel_raster_is_not_the_padded_crop():
    geom = {
        "rings": [[
            [28.0, -25.9800],
            [28.0008, -25.9800],
            [28.0008, -25.9808],
            [28.0, -25.9808],
            [28.0, -25.9800],
        ]]
    }
    mask = true_parcel_mask_from_geometry((200, 200), geom)
    assert mask is not None
    assert 0.05 < float(mask.mean()) < 0.55
    assert not bool(mask[2, 2])
    assert bool(mask[100, 100])


def _os(stand: str) -> tuple[dict, dict | None]:
    payload = json.loads((OS_DIR / f"{stand}.json").read_text(encoding="utf-8"))
    gis = _gis_by_stand().get(stand)
    return payload, None if gis is None else gis.get("geometry")


def test_regression_338_not_rejected_solely_by_clip():
    payload, geom = _os("338")
    assert payload["pool"]["status"] == "REJECTED"
    val = validate_os_payload(payload, gis_geometry=geom)
    assert val.final_status != "REJECTED" or "clip" not in " ".join(val.reason_codes).lower()
    assert val.final_status in {"UNKNOWN", "CONFIRMED"}
    assert val.contour_retained is True
    assert abs(float((payload["pool"]["clip"] or {}).get("pool") or 0) - 0.019) < 0.01
    reasons = " ".join(val.reason_codes)
    assert "semantic" in reasons or val.final_status == "UNKNOWN"


def test_regression_control_stands_os_json():
    rows = {}
    for stand in ("677", "612", "408", "420", "570", "370"):
        payload, geom = _os(stand)
        val = validate_os_payload(payload, gis_geometry=geom)
        rows[stand] = val.final_status
        if stand == "408":
            assert payload["pool"]["status"] == "UNKNOWN"
            assert val.final_status in {"UNKNOWN", "REJECTED"}
        if stand == "677":
            assert val.final_status == "CONFIRMED"
        if stand == "420":
            assert val.final_status in {"CONFIRMED", "UNKNOWN"}
            assert val.final_status != "REJECTED"
        if stand == "570":
            assert val.final_status == "REJECTED"
        if stand == "612":
            assert val.final_status != "CONFIRMED"
        if stand == "370":
            assert val.final_status != "CONFIRMED"
    assert rows["570"] == "REJECTED"
    assert rows["677"] == "CONFIRMED"


def _hybrid_frames(listing_id: str) -> list[FrameGeometry]:
    block = json.loads((ROOT / f"data/investigations/blind_{listing_id}_complete_estate/hybrid_block.json").read_text(encoding="utf-8"))
    out = []
    for item in block.get("frames") or []:
        dom = item.get("dominant") or {}
        geom = (dom.get("geometry") or {}) if isinstance(dom, dict) else {}
        contour = None
        if isinstance(dom, dict):
            contour = dom.get("contour_image")
        out.append(
            FrameGeometry(
                media_id=item.get("media_id") or "",
                viewpoint=item.get("viewpoint") or "",
                source=item.get("source") or "",
                source_reason=item.get("source_reason") or "",
                scoring_ready=bool(item.get("scoring_ready")),
                pool_present=bool(item.get("pool_present")),
                yoloe_conf=float(item.get("yoloe_conf") or 0.0),
                n_components=int(item.get("n_components") or 0),
                dominant=dom if isinstance(dom, dict) else None,
                secondary=item.get("secondary") if isinstance(item.get("secondary"), dict) else None,
                component_relation=item.get("component_relation") or {},
                descriptors=item.get("descriptors") or {},
                contour_image=contour,
                spa_relationship=item.get("spa_relationship"),
                geometry_quality=float(item.get("geometry_quality") or 0.0),
                scoring_ready_reason=item.get("scoring_ready_reason") or "",
            )
        )
    return out


def test_listing_116978058_keeps_irregular_official_contour():
    frames = _hybrid_frames("116978058")
    summary = combine_listing_frames(frames)
    assert summary["chosen_id"] == "116978058-026"
    chosen = next(f for f in frames if f.media_id == summary["chosen_id"])
    aspect = float((chosen.dominant.get("geometry") or {}).get("aspect_ratio") or 0)
    assert aspect >= 3.0


def test_listing_116889694_turf_not_scoring_ready():
    frames = _hybrid_frames("116889694")
    summary = combine_listing_frames(frames)
    ready = [f for f in frames if f.scoring_ready]
    assert ready == []
    assert summary["chosen_id"] is None
    turf = next(f for f in frames if str(f.media_id).endswith("-026"))
    clip = (turf.dominant or {}).get("clip") or {}
    val = validate_listing_pool_object(
        viewpoint=turf.viewpoint,
        source=turf.source,
        clip=clip,
        geometry=(turf.dominant or {}).get("geometry") or {},
        relative_area=(turf.dominant or {}).get("relative_area"),
        scoring_ready=False,
    )
    assert val.final_status == "REJECTED"
    assert val.object_role == "turf_or_deck"


def test_listing_117262832_principal_is_courtyard_not_top_border():
    frames = _hybrid_frames("117262832")
    summary = combine_listing_frames(frames)
    assert summary["chosen_id"] in {"117262832-037", "117262832-038"}
    assert summary["chosen_id"] != "117262832-039"
    assert summary["chosen_id"] != "117262832-003"
    chosen = next(f for f in frames if f.media_id == summary["chosen_id"])
    area = float((chosen.dominant or {}).get("relative_area") or 0)
    assert area >= 0.04
    speck = next(f for f in frames if f.media_id == "117262832-039")
    assert speck.principal_pool_candidate is False


def test_validation_version_constant():
    assert VALIDATION_VERSION == "pool_object_validation_v1"
