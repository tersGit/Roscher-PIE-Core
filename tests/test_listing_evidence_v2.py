"""Listing Evidence v2 — generic, no stand/listing hardcodes."""

from __future__ import annotations

import io

import numpy as np
from PIL import Image, ImageDraw
from pathlib import Path

from backend.gis.estate_ags_matching.listing_evidence_v2 import (
    assemble_channels,
    classify_viewpoint,
    extract_water_components,
    observe_listing_frame,
    select_shape_evidence,
)
from backend.gis.estate_ags_matching.listing_evidence_v2 import FrameEvidence


def test_module_has_no_stand_or_listing_hardcodes():
    text = Path("backend/gis/estate_ags_matching/listing_evidence_v2.py").read_text(encoding="utf-8")
    assert "365" not in text
    assert "116978058" not in text
    assert "583" not in text
    assert "051" not in text


def _png(image: Image.Image) -> bytes:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def _interior_room() -> bytes:
    image = Image.new("RGB", (240, 180), (210, 205, 198))
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, 0, 239, 28], fill=(232, 228, 222))  # ceiling
    draw.rectangle([0, 150, 239, 179], fill=(120, 118, 130))  # carpet
    for y in range(40, 110, 4):
        draw.line([(20, y), (110, y)], fill=(60, 50, 40), width=1)  # blinds
    return _png(image)


def _two_pools() -> bytes:
    image = Image.new("RGB", (320, 240), (46, 150, 62))  # lawn
    draw = ImageDraw.Draw(image)
    draw.polygon([(40, 80), (130, 70), (150, 120), (120, 170), (50, 165), (30, 120)], fill=(40, 90, 160))
    draw.ellipse([210, 90, 270, 145], fill=(50, 170, 200))
    draw.rectangle([180, 10, 310, 70], fill=(210, 195, 170))  # house
    return _png(image)


def _pool_closeup() -> bytes:
    image = Image.new("RGB", (240, 180), (210, 195, 170))
    draw = ImageDraw.Draw(image)
    draw.ellipse([20, 50, 220, 175], fill=(40, 160, 200))
    draw.rectangle([40, 0, 200, 40], fill=(200, 185, 160))
    return _png(image)


def _smear_blob() -> bytes:
    image = Image.new("RGB", (240, 180), (46, 150, 62))
    draw = ImageDraw.Draw(image)
    draw.polygon([(10, 20), (200, 25), (220, 40), (30, 160), (15, 150), (80, 90), (12, 80)], fill=(40, 90, 160))
    return _png(image)


def test_interior_is_blocked_from_spatial():
    scores = {k: 0.0 for k in (
        "aerial_near_nadir", "elevated_exterior", "ground_level_exterior",
        "pool_overview", "pool_closeup", "interior", "garden_only", "unusable_ambiguous",
    )}
    scores["interior"] = 0.92
    frame = observe_listing_frame("room", _interior_room(), clip_scores=scores)
    assert frame.viewpoint == "interior"
    assert frame.spatial_eligible is False
    assert frame.scale_eligible is False
    assert frame.pool_overview_eligible is False


def test_closeup_excluded_from_nadir_scale():
    scores = {k: 0.0 for k in (
        "aerial_near_nadir", "elevated_exterior", "ground_level_exterior",
        "pool_overview", "pool_closeup", "interior", "garden_only", "unusable_ambiguous",
    )}
    scores["pool_closeup"] = 0.80
    frame = observe_listing_frame("close", _pool_closeup(), clip_scores=scores)
    assert frame.viewpoint == "pool_closeup"
    assert frame.scale_eligible is False
    assert frame.spatial_eligible is False


def test_two_separate_water_components_are_retained():
    comps = extract_water_components(_two_pools())
    assert len(comps) >= 2
    sep = ((comps[0].centroid_xy[0] - comps[1].centroid_xy[0]) ** 2 + (comps[0].centroid_xy[1] - comps[1].centroid_xy[1]) ** 2) ** 0.5
    assert sep >= 0.08


def test_tiny_edge_cyan_scrap_is_not_a_pool_component():
    image = Image.new("RGB", (240, 180), (46, 150, 62))
    draw = ImageDraw.Draw(image)
    draw.ellipse([2, 150, 28, 178], fill=(40, 160, 200))
    comps = extract_water_components(_png(image))
    assert all(c.relative_area >= 0.006 for c in comps)


def test_low_compactness_contour_is_rejected_or_downweighted():
    comps = extract_water_components(_smear_blob())
    for comp in comps:
        assert not (comp.compactness < 0.22 and comp.quality > 0.35)


def test_cluster_sum_of_poor_frames_does_not_beat_clean_single():
    def _frame(media_id: str, quality: float, compactness: float, elong: float, overview: bool = True) -> FrameEvidence:
        return FrameEvidence(
            media_id=media_id,
            viewpoint="pool_overview",
            viewpoint_scores={},
            pool_detected=True,
            pool_overview_eligible=overview,
            spatial_eligible=False,
            scale_eligible=False,
            aerial_eligible=False,
            contour_quality=quality,
            n_components=1,
            dominant={"compactness": compactness, "elongation": elong, "aspect_ratio": elong, "n_major_indents": 1},
        )

    clean = _frame("clean", 0.72, 0.52, 1.4)
    poor_a = _frame("poor_a", 0.38, 0.16, 1.9)
    poor_b = _frame("poor_b", 0.37, 0.15, 1.85)
    poor_c = _frame("poor_c", 0.36, 0.14, 1.88)
    chosen = select_shape_evidence([poor_a, poor_b, poor_c, clean])
    assert chosen["chosen_id"] == "clean"
    assert chosen["method"] == "best_single_frame"
    assert "poor_a" in chosen["cluster_sum_ids"] or chosen["cluster_sum_quality_total"] is not None


def test_channels_are_not_collapsed_into_one_geometry():
    scores = {k: 0.0 for k in (
        "aerial_near_nadir", "elevated_exterior", "ground_level_exterior",
        "pool_overview", "pool_closeup", "interior", "garden_only", "unusable_ambiguous",
    )}
    scores["pool_overview"] = 0.7
    pool = observe_listing_frame("overview", _two_pools(), clip_scores=scores)
    scores_i = dict(scores)
    scores_i["pool_overview"] = 0.0
    scores_i["interior"] = 0.9
    interior = observe_listing_frame("inside", _interior_room(), clip_scores=scores_i)
    channels = assemble_channels([pool, interior])
    assert "shape" in channels and "spatial" in channels and "scale" in channels and "aerial" in channels
    assert interior.spatial_eligible is False
    assert channels["scale"]["nadir_compatible"] is False or channels["scale"]["source_ids"] == []


def test_covered_space_with_interior_clip_second_is_interior():
    scores = {k: 0.05 for k in (
        "aerial_near_nadir", "elevated_exterior", "ground_level_exterior",
        "pool_overview", "pool_closeup", "interior", "garden_only", "unusable_ambiguous",
    )}
    scores["ground_level_exterior"] = 0.46
    scores["interior"] = 0.38
    dummy = np.zeros((80, 100, 3), dtype=np.uint8)
    dummy[:] = (190, 185, 175)
    label, _ = classify_viewpoint(dummy, clip_scores=scores, grass_frac=0.01)
    assert label == "interior"


def test_viewpoint_interior_from_clip_scores_without_image_id():
    scores = {k: 0.02 for k in (
        "aerial_near_nadir", "elevated_exterior", "ground_level_exterior",
        "pool_overview", "pool_closeup", "interior", "garden_only", "unusable_ambiguous",
    )}
    scores["interior"] = 0.88
    dummy = np.zeros((80, 100, 3), dtype=np.uint8)
    dummy[:] = (200, 198, 190)
    label, _ = classify_viewpoint(dummy, clip_scores=scores, grass_frac=0.01)
    assert label == "interior"
