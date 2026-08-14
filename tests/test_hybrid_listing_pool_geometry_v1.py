"""Hybrid listing pool geometry v1 — generic, no listing/stand/colour rules."""

from pathlib import Path

import numpy as np

from backend.gis.estate_ags_matching.hybrid_listing_pool_geometry_v1 import (
    SOURCE_RANK,
    FrameGeometry,
    PoolComponent,
    combine_listing_frames,
    split_dominant_secondary,
    yoloe_validate,
)


def test_module_has_no_listing_hardcodes_or_colour_thresholds():
    text = Path("backend/gis/estate_ags_matching/hybrid_listing_pool_geometry_v1.py").read_text(encoding="utf-8")
    assert "116978058" not in text
    assert "116273255" not in text
    assert "365" not in text
    assert "inRange" not in text
    assert "COLOR_BGR2HSV" not in text
    assert "cyan_frac" not in text
    assert "octagon" not in text.lower()
    assert "l-shaped" not in text.lower()
    assert "jacuzzi" not in text.lower()


def test_yoloe_text_hit_is_not_sufficient_without_geometry():
    ok, _reason, notes = yoloe_validate(
        viewpoint="pool_overview",
        conf=0.9,
        geom={"relative_area": 0.002, "compactness": 0.5},
        clip={"pool": 0.8, "wall": 0.0, "vegetation": 0.0, "furniture": 0.0, "bathtub": 0.0, "interior": 0.0},
        edge_clip=0.0,
        role="dominant",
    )
    assert ok is False
    assert "implausible_perimeter_area" in notes


def test_bathtub_cannot_become_geometry():
    ok, reason, *_ = yoloe_validate(
        viewpoint="pool_overview",
        conf=0.8,
        geom={"relative_area": 0.12, "compactness": 0.5},
        clip={"pool": 0.2, "wall": 0.0, "vegetation": 0.0, "furniture": 0.0, "bathtub": 0.55, "interior": 0.1},
        edge_clip=0.0,
    )
    assert ok is False
    assert reason == "bathtub_or_bathroom"


def test_closeup_cannot_be_overview_ready():
    ok, _reason, notes = yoloe_validate(
        viewpoint="pool_closeup",
        conf=0.8,
        geom={"relative_area": 0.12, "compactness": 0.5},
        clip={"pool": 0.9, "wall": 0.0, "vegetation": 0.0, "furniture": 0.0, "bathtub": 0.0, "interior": 0.0},
        edge_clip=0.0,
    )
    assert ok is False
    assert "closeup_not_overview" in notes


def test_fastsam_rank_below_yoloe():
    assert SOURCE_RANK["yoloe_sam2"] > SOURCE_RANK["yoloe"] > SOURCE_RANK["fastsam_fallback"]
    assert SOURCE_RANK["fastsam_fallback"] > SOURCE_RANK["presence_only"]


def test_combine_prefers_one_clean_yoloe_over_weak_fallback():
    def _f(mid, source, ready=True, vp="pool_overview", struct=0.5, conf=0.4):
        return FrameGeometry(
            media_id=mid,
            viewpoint=vp,
            source=source,
            source_reason="t",
            scoring_ready=ready,
            pool_present=True,
            yoloe_conf=conf,
            n_components=1,
            dominant={"structural_support": struct, "confidence": conf},
            secondary=None,
            component_relation={},
            descriptors={"orientation_deg": 10.0, "oblique": True},
        )

    weak = [_f(f"w{i}", "fastsam_fallback", struct=0.2, conf=0.1) for i in range(4)]
    clean = _f("clean", "yoloe_sam2", struct=0.6, conf=0.7)
    summary = combine_listing_frames(weak + [clean])
    assert summary["chosen_id"] == "clean"
    assert summary["chosen_source"] == "yoloe_sam2"


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
    clip = {"pool": 0.6, "wall": 0.02, "vegetation": 0.02, "furniture": 0.02, "bathtub": 0.0, "interior": 0.0}
    large = PoolComponent(big, None, [10, 20, 70, 60], 0.4, 0.18, (0.4, 0.5), clip, geom_big, 0.5, "yoloe-11s-seg", "swimming pool")
    small = PoolComponent(tiny, None, [60, 5, 70, 12], 0.7, 0.008, (0.81, 0.1), clip, geom_tiny, 0.4, "yoloe-11s-seg", "swimming pool")
    dom, sec, rel = split_dominant_secondary([small, large], "pool_overview")
    assert dom is large
    assert sec is small
    assert rel["relative_size"] < 0.55
