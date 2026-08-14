"""Colour-independent listing pool object extractor — generic, no listing hardcodes."""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from backend.gis.estate_ags_matching.listing_pool_object import (
    classify_geometry,
    intensity_edge_map,
    object_mask_from_probability,
    observe_pool_object,
    quality_gate,
    rectilinear_compound_geometry,
    snap_mask_to_intensity_edges,
)


def test_module_has_no_stand_or_listing_hardcodes_or_colour_thresholds():
    text = Path("backend/gis/estate_ags_matching/listing_pool_object.py").read_text(encoding="utf-8")
    assert "365" not in text
    assert "116978058" not in text
    assert "116273255" not in text
    assert "inRange" not in text
    assert "COLOR_BGR2HSV" not in text
    assert "COLOR_RGB2HSV" not in text
    assert "cyan_frac" not in text


def _png(image: Image.Image) -> bytes:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def _l_pool(water_rgb: tuple[int, int, int]) -> Image.Image:
    """Generic L-planform: two perpendicular arms, beige coping, grey house."""
    image = Image.new("RGB", (320, 240), (46, 140, 58))
    draw = ImageDraw.Draw(image)
    draw.rectangle([140, 10, 310, 95], fill=(160, 160, 165))  # house
    draw.rectangle([20, 100, 300, 230], fill=(196, 188, 172))  # coping/patio
    # L: horizontal arm + vertical arm meeting at inner corner.
    draw.polygon([(40, 120), (250, 120), (250, 165), (120, 165), (120, 210), (40, 210)], fill=water_rgb)
    return image


def test_intensity_boundary_is_stable_across_water_fill_colours():
    fills = [(18, 18, 18), (40, 170, 200), (30, 90, 40), (12, 40, 90)]
    contours = []
    for fill in fills:
        image = np.array(_l_pool(fill))[:, :, ::-1].copy()
        prior = np.zeros(image.shape[:2], np.float32)
        prior[120:210, 40:250] = 0.8
        mask = object_mask_from_probability(prior, min_score=0.4)
        snapped = snap_mask_to_intensity_edges(mask, intensity_edge_map(image))
        contours.append((snapped > 0).astype(np.uint8))
    base = contours[0]
    for other in contours[1:]:
        inter = float(np.logical_and(base > 0, other > 0).sum())
        union = float(np.logical_or(base > 0, other > 0).sum())
        assert union > 0
        assert inter / union >= 0.80


def test_l_contour_reports_perpendicular_arms_and_inner_corner():
    import cv2

    mask = np.zeros((240, 320), np.uint8)
    pts = np.array([[40, 120], [250, 120], [250, 165], [120, 165], [120, 210], [40, 210]], np.int32)
    cv2.fillPoly(mask, [pts], 255)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    assert contours
    geom = rectilinear_compound_geometry(contours[0], 320, 240)
    assert geom["strong_concave_inner_corner"] is True
    assert geom["two_dominant_arms"] is True
    assert geom["arms_approximately_perpendicular"] is True
    assert geom["rectilinear_not_kidney"] is True


def test_frozen_interior_viewpoint_skips_object_extraction():
    image = Image.new("RGB", (240, 180), (210, 205, 198))
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, 0, 239, 28], fill=(232, 228, 222))
    scores = {k: 0.0 for k in (
        "aerial_near_nadir", "elevated_exterior", "ground_level_exterior",
        "pool_overview", "pool_closeup", "interior", "garden_only", "unusable_ambiguous",
    )}
    scores["interior"] = 0.93
    obs = observe_pool_object("room", _png(image), clip_scores=scores, viewpoint="interior")
    assert obs.viewpoint == "interior"
    assert obs.pool_object_detected is False
    assert obs.shape_eligible is False
    assert obs.spatial_eligible is False
    assert obs.scale_eligible is False
    assert obs.geometry_class == "no_usable_pool_geometry"


def test_quality_gate_requires_usable_boundary():
    from backend.gis.estate_ags_matching.listing_pool_object import PoolObjectObservation

    empty = PoolObjectObservation(
        media_id="a",
        viewpoint="pool_overview",
        viewpoint_scores={},
        pool_object_detected=False,
        geometry_class="no_usable_pool_geometry",
        full_boundary_recovered=False,
        partial_object=False,
        component_count=0,
        contour_quality=0.0,
        edge_clip=0.0,
        shape_eligible=False,
        spatial_eligible=False,
        scale_eligible=False,
        house_visible=False,
    )
    gate = quality_gate([empty])
    assert gate["passed"] is False


def test_fragment_is_not_full_planform():
    cls = classify_geometry(
        detected=True,
        comps=[{"relative_area": 0.005, "compactness": 0.55, "edge_clip": 0.02, "n_major_indents": 0}],
        clip_pool=0.4,
        viewpoint="pool_overview",
    )
    assert cls == "reflection_or_highlight"
