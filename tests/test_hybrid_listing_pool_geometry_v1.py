"""Hybrid listing pool geometry v1 — generic, no listing/stand/colour rules."""

from pathlib import Path

import numpy as np

from backend.gis.estate_ags_matching.hybrid_listing_pool_geometry_v1 import (
    SOURCE_RANK,
    VIEW_GEOMETRY_RANK,
    FrameGeometry,
    PoolComponent,
    combine_listing_frames,
    fastsam_candidate_score,
    hybrid_geometry_from_mask,
    sam2_geometry_collapsed,
    semantic_reject_reason,
    spa_relationship_from,
    split_dominant_secondary,
    yoloe_validate,
    _presence_evidence,
)


def _clip(**over):
    base = {
        "pool": 0.6,
        "wall": 0.02,
        "vegetation": 0.02,
        "furniture": 0.02,
        "bathtub": 0.0,
        "interior": 0.0,
        "deck": 0.1,
    }
    base.update(over)
    return base


def test_module_has_no_listing_hardcodes_or_colour_thresholds():
    text = Path("backend/gis/estate_ags_matching/hybrid_listing_pool_geometry_v1.py").read_text(encoding="utf-8")
    assert "116978058" not in text
    assert "116889694" not in text
    assert "116273255" not in text
    assert "365" not in text
    assert "inRange" not in text
    assert "COLOR_BGR2HSV" not in text
    assert "cyan_frac" not in text
    assert "octagon" not in text.lower()
    assert "l-shaped" not in text.lower()
    assert "jacuzzi" not in text.lower()
    assert "ground_truth" not in text
    assert "expected_stand" not in text


def test_yoloe_text_hit_is_not_sufficient_without_geometry():
    ok, _reason, notes = yoloe_validate(
        viewpoint="pool_overview",
        conf=0.9,
        geom={"relative_area": 0.002, "compactness": 0.5},
        clip=_clip(pool=0.8),
        edge_clip=0.0,
        role="dominant",
    )
    assert ok is False
    assert "candidate below minimum area" in notes


def test_aerial_small_pool_can_pass_area_gate():
    ok, reason, notes = yoloe_validate(
        viewpoint="aerial_near_nadir",
        conf=0.4,
        geom={"relative_area": 0.006, "compactness": 0.55},
        clip=_clip(pool=0.55),
        edge_clip=0.0,
        role="dominant",
    )
    assert ok is True
    assert reason == "ok"
    assert "candidate below minimum area" not in notes


def test_bathtub_cannot_become_geometry():
    ok, reason, notes = yoloe_validate(
        viewpoint="pool_overview",
        conf=0.8,
        geom={"relative_area": 0.12, "compactness": 0.5},
        clip=_clip(pool=0.2, bathtub=0.55, interior=0.1),
        edge_clip=0.0,
    )
    assert ok is False
    assert reason == "bathtub_or_bathroom"
    assert any("CLIP semantic rejection" in n for n in notes)


def test_closeup_cannot_be_overview_ready():
    ok, _reason, notes = yoloe_validate(
        viewpoint="pool_closeup",
        conf=0.8,
        geom={"relative_area": 0.12, "compactness": 0.5},
        clip=_clip(pool=0.9),
        edge_clip=0.0,
    )
    assert ok is False
    assert "closeup_not_overview" in notes


def test_fastsam_rank_below_yoloe():
    assert SOURCE_RANK["yoloe_sam2"] > SOURCE_RANK["yoloe"] > SOURCE_RANK["fastsam_fallback"]
    assert SOURCE_RANK["fastsam_fallback"] > SOURCE_RANK["presence_only"]
    assert VIEW_GEOMETRY_RANK["aerial_near_nadir"] > VIEW_GEOMETRY_RANK["pool_overview"]


def test_combine_prefers_one_clean_yoloe_over_weak_fallback():
    def _f(mid, source, ready=True, vp="pool_overview", struct=0.5, conf=0.4, clip=None, geom=None):
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
                "structural_support": struct,
                "confidence": conf,
                "clip": clip or _clip(),
                "geometry": geom or {"solidity": 0.9, "n_major_indents": 0, "aspect_ratio": 2.0},
            },
            secondary=None,
            component_relation={},
            descriptors={"orientation_deg": 10.0, "oblique": vp != "aerial_near_nadir"},
        )

    weak = [_f(f"w{i}", "fastsam_fallback", struct=0.2, conf=0.1) for i in range(4)]
    clean = _f("clean", "yoloe_sam2", struct=0.6, conf=0.7)
    summary = combine_listing_frames(weak + [clean])
    assert summary["chosen_id"] == "clean"
    assert summary["chosen_source"] == "yoloe_sam2"


def test_combine_prefers_valid_aerial_over_oblique_overview():
    def _f(mid, source, vp, conf=0.5):
        return FrameGeometry(
            media_id=mid,
            viewpoint=vp,
            source=source,
            source_reason="t",
            scoring_ready=True,
            pool_present=True,
            yoloe_conf=conf,
            n_components=1,
            dominant={
                "structural_support": 0.5,
                "confidence": conf,
                "clip": _clip(pool=0.7),
                "geometry": {"solidity": 0.9, "n_major_indents": 0, "aspect_ratio": 2.1},
            },
            secondary=None,
            component_relation={},
            descriptors={"orientation_deg": 10.0, "oblique": vp != "aerial_near_nadir"},
        )

    aerial = _f("air", "fastsam_fallback", "aerial_near_nadir", conf=0.4)
    oblique = _f("obl", "yoloe_sam2", "pool_overview", conf=0.8)
    summary = combine_listing_frames([aerial, oblique])
    assert summary["chosen_id"] == "air"
    assert "not averaged" in summary["note"].lower() or "not averaged" in (summary.get("frame_selection_reason") or "").lower()


def test_dominant_is_largest_plausible_not_tiny_secondary():
    h, w = 80, 80
    big = np.zeros((h, w), dtype=bool)
    big[20:60, 10:70] = True
    tiny = np.zeros((h, w), dtype=bool)
    tiny[5:12, 60:70] = True
    geom_big = {
        "relative_area": 0.18,
        "compactness": 0.45,
        "solidity": 0.9,
        "straight_edge_proportion": 0.4,
        "n_corners": 4,
        "n_major_indents": 1,
    }
    geom_tiny = {
        "relative_area": 0.008,
        "compactness": 0.5,
        "solidity": 0.95,
        "straight_edge_proportion": 0.3,
        "n_corners": 4,
        "n_major_indents": 0,
    }
    clip = _clip()
    large = PoolComponent(big, None, [10, 20, 70, 60], 0.4, 0.18, (0.4, 0.5), clip, geom_big, 0.5, "yoloe-11s-seg", "swimming pool")
    small = PoolComponent(tiny, None, [60, 5, 70, 12], 0.7, 0.008, (0.81, 0.1), clip, geom_tiny, 0.4, "yoloe-11s-seg", "swimming pool")
    dom, sec, rel = split_dominant_secondary([small, large], "pool_overview")
    assert dom is large
    assert sec is small
    assert rel["relative_size"] < 0.55


def test_fastsam_scoring_ready_is_aerial_only():
    from backend.gis.estate_ags_matching.hybrid_listing_pool_geometry_v1 import fastsam_may_be_scoring_ready

    water = _clip(pool=0.55, vegetation=0.02, deck=0.18)
    turf_dom = _clip(pool=0.22, vegetation=0.11, deck=0.62)
    assert fastsam_may_be_scoring_ready("aerial_near_nadir", water) is True
    assert fastsam_may_be_scoring_ready("elevated_exterior", water) is False
    assert fastsam_may_be_scoring_ready("pool_overview", water) is False
    assert fastsam_may_be_scoring_ready("aerial_near_nadir", turf_dom) is False


def test_fastsam_prefers_pool_clip_over_deck_turf():
    turf = _clip(pool=0.22, vegetation=0.11, deck=0.62)
    water = _clip(pool=0.55, vegetation=0.02, deck=0.18)
    assert semantic_reject_reason(turf, mode="fastsam_candidate") == "wrong-object rejection: deck_or_turf"
    assert semantic_reject_reason(water, mode="fastsam_candidate") is None
    assert semantic_reject_reason(turf, mode="yoloe") is None  # coping/deck must not reject YOLOE
    assert fastsam_candidate_score(water) > fastsam_candidate_score(turf)


def test_l_shaped_mask_keeps_a_major_indent_after_64pt():
    mask = np.zeros((90, 90), dtype=bool)
    mask[12:78, 14:34] = True
    mask[58:78, 14:76] = True
    packed = hybrid_geometry_from_mask(mask)
    assert packed["ok"] is True
    score = packed["stage_metrics"]["normalized_64"]
    raw = packed["stage_metrics"]["raw"]
    assert raw["n_major_indents"] >= 1 or raw["solidity"] < 0.93
    assert score["n_major_indents"] >= 1 or score["solidity"] < 0.94
    assert packed["loss"]["verdict"] in {"GEOMETRY PRESERVED", "PARTIALLY LOST"}
    assert packed["loss"]["verdict"] != "COLLAPSED"


def test_kidney_mask_is_not_collapsed_to_a_rectangle():
    import cv2

    canvas = np.zeros((80, 120), np.uint8)
    cv2.ellipse(canvas, (50, 40), (36, 22), 0, 0, 360, 1, -1)
    cv2.ellipse(canvas, (78, 40), (22, 16), 0, 0, 360, 1, -1)
    packed = hybrid_geometry_from_mask(canvas.astype(bool))
    assert packed["ok"] is True
    score = packed["stage_metrics"]["normalized_64"]
    rect = np.zeros((80, 120), np.uint8)
    rect[18:62, 20:100] = 1
    rect_score = hybrid_geometry_from_mask(rect.astype(bool))["stage_metrics"]["normalized_64"]
    assert score["n_corners"] >= rect_score["n_corners"] or score["max_indent"] >= rect_score["max_indent"]
    assert packed["loss"]["verdict"] != "COLLAPSED"


def test_spa_blob_is_not_merged_into_dominant_hull():
    mask = np.zeros((100, 100), dtype=bool)
    mask[25:70, 15:70] = True
    mask[30:42, 82:96] = True
    packed = hybrid_geometry_from_mask(mask)
    assert packed["ok"] is True
    assert len(packed["extras"]) >= 1
    main = PoolComponent(
        mask[25:70, 15:70],
        None,
        [15, 25, 70, 70],
        0.5,
        0.2,
        (0.4, 0.45),
        _clip(),
        packed["geometry"],
        0.5,
        "yoloe",
        "swimming pool",
    )
    spa = PoolComponent(
        mask[30:42, 82:96],
        None,
        [82, 30, 96, 42],
        0.4,
        0.02,
        (0.89, 0.36),
        _clip(),
        {"relative_area": 0.02, "compactness": 0.7},
        0.4,
        "yoloe",
        "swimming pool",
    )
    rel = spa_relationship_from(main, spa, packed["extras"])
    assert rel["secondary_present"] is True
    assert rel["merged_into_main_contour"] is False
    assert "not a ranking weight" in rel["note"].lower()


def test_sam2_convex_fill_is_rejected():
    seed = PoolComponent(
        np.zeros((10, 10), dtype=bool),
        None,
        [0, 0, 1, 1],
        0.4,
        0.1,
        (0.5, 0.5),
        _clip(),
        {"n_major_indents": 2, "solidity": 0.86, "max_indent": 0.12},
        0.5,
        "yoloe",
        "swimming pool",
    )
    refined = PoolComponent(
        np.zeros((10, 10), dtype=bool),
        None,
        [0, 0, 1, 1],
        0.4,
        0.12,
        (0.5, 0.5),
        _clip(),
        {"n_major_indents": 0, "solidity": 0.97, "max_indent": 0.02},
        0.5,
        "sam2",
        "swimming pool",
    )
    assert sam2_geometry_collapsed(seed, refined) is not None


def test_presence_evidence_retains_mask_fields_without_scoring_ready():
    mask = np.zeros((40, 40), dtype=bool)
    mask[10:30, 8:32] = True
    packed = hybrid_geometry_from_mask(mask)
    comp = PoolComponent(
        mask,
        packed["contour"],
        [8, 10, 32, 30],
        0.33,
        float(mask.mean()),
        (0.5, 0.5),
        _clip(pool=0.4),
        packed["geometry"],
        0.4,
        "fastsam-s",
        "fastsam_presence",
        detector="fastsam-s",
        eligibility_reason="presence_mask_retained",
        raw_contour=packed["raw_contour"],
    )
    ev = _presence_evidence(comp, source="presence_only", reason="candidate below minimum area")
    assert ev is not None
    assert ev["scoring_ready"] is False
    assert ev["raw_contour"]
    assert ev["bounding_box"] == [8, 10, 32, 30]
    assert ev["source_detector"] == "presence_only"
    assert ev["mask_confidence"] == 0.33
    assert ev["semantic_confidence"] == 0.4
    assert "candidate below minimum area" in ev["geometry_eligibility_reason"]
