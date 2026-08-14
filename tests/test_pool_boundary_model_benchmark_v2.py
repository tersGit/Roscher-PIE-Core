"""Pool boundary model benchmark v2 — no listing/stand hardcodes in the model module."""

from pathlib import Path

from backend.gis.estate_ags_matching.pool_boundary_model_benchmark_v2 import (
    TEXT_MULTI,
    TEXT_POOL,
    pick_best,
    MaskResult,
)


def test_benchmark_module_has_no_listing_or_colour_rules():
    text = Path("backend/gis/estate_ags_matching/pool_boundary_model_benchmark_v2.py").read_text(encoding="utf-8")
    assert "116978058" not in text
    assert "116273255" not in text
    assert "365" not in text
    assert "inRange" not in text
    assert "COLOR_BGR2HSV" not in text
    assert "octagon" not in text.lower()
    assert "l-shaped" not in text.lower()
    assert "l_shaped" not in text.lower()


def test_text_prompts_are_generic_object_names():
    assert TEXT_POOL == ["swimming pool"]
    assert "swimming pool" in TEXT_MULTI
    assert "lawn" in TEXT_MULTI
    assert "wooden deck" in TEXT_MULTI


def test_pick_best_prefers_plausible_pool_over_empty():
    empty = MaskResult("text_only", "yoloe-11s-seg", None, None, 0.0, 0)
    good = MaskResult(
        "text_only",
        "yoloe-11s-seg",
        contour=None,
        mask=__import__("numpy").ones((4, 4), dtype=bool),
        confidence=0.6,
        n_components=1,
        clip={"pool": 0.7, "vegetation": 0.05, "furniture": 0.02, "bathtub": 0.0},
        geometry={"relative_area": 0.12, "closed": True},
        structural_support=0.4,
    )
    assert pick_best([empty, good]) is good
