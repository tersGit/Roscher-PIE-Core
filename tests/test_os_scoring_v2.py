"""Scoring v2 comparison — no listing-specific or stand-specific rules."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from backend.gis.estate_ags_matching.os_scoring_v2 import (
    OS_KEYS_NO_BUILDING,
    V2_WEIGHTS_NO_BUILDING,
    contour_descriptors,
    driveway_spatial_similarity,
    pca_normalize,
    score_v2,
    sector_similarity,
    shape_v2_similarity,
    v2_object_features,
)
from backend.gis.estate_ags_matching.pool_geometry import PoolGeometryFingerprint


def _octagon_with_lobe() -> np.ndarray:
    """Generic faceted pool + smaller attached lobe. Not a named property."""
    angles = np.linspace(0, 2 * np.pi, 9)[:-1]
    main = np.stack([1.15 * np.cos(angles), 0.72 * np.sin(angles)], axis=1)
    lobe_a = np.linspace(-0.6, 0.6, 8)
    lobe = np.stack([1.35 + 0.28 * np.cos(lobe_a), 0.35 * np.sin(lobe_a) - 0.15], axis=1)
    return np.vstack([main, lobe])


def _kidney() -> np.ndarray:
    t = np.linspace(0, 2 * np.pi, 40)
    x = np.cos(t) * (1.0 + 0.35 * np.sin(t))
    y = 0.55 * np.sin(t)
    return np.stack([x, y], axis=1)


def _rectangle() -> np.ndarray:
    return np.array([[-1, -0.45], [1, -0.45], [1, 0.45], [-1, 0.45], [-1, -0.45]], dtype=float)


def _listing() -> PoolGeometryFingerprint:
    octagon = pca_normalize(_octagon_with_lobe()).tolist()
    return PoolGeometryFingerprint(
        present=True,
        unknown=False,
        shape_class="irregular",
        aspect_ratio=2.1,
        orientation_deg=90.0,
        compactness=0.5,
        rectangularity=0.7,
        convexity=0.85,
        pool_to_house_dx=0.16,
        pool_to_house_dy=0.19,
        pool_to_house_dist=0.41,
        pool_to_house_angle_deg=54.0,
        contour_normalized=octagon,
    )


def test_module_has_no_stand_or_listing_hardcodes():
    text = Path("backend/gis/estate_ags_matching/os_scoring_v2.py").read_text(encoding="utf-8")
    assert "365" not in text
    assert "116978058" not in text


def test_elongated_faceted_beats_compact_kidney_and_rectangle():
    listing = contour_descriptors(_octagon_with_lobe())
    octagon = contour_descriptors(_octagon_with_lobe())
    kidney = contour_descriptors(_kidney())
    rect = contour_descriptors(_rectangle())
    s_self, _ = shape_v2_similarity(listing, octagon)
    s_kidney, _ = shape_v2_similarity(listing, kidney)
    s_rect, _ = shape_v2_similarity(listing, rect)
    assert s_self is not None and s_kidney is not None and s_rect is not None
    assert s_self > s_kidney
    assert s_self > s_rect


def test_adjacent_sectors_outrank_opposite():
    assert sector_similarity(54.0, 81.0) > sector_similarity(54.0, -114.0)
    assert sector_similarity(0.0, 10.0) == 1.0


def test_rejected_cannot_beat_confirmed_via_renormalise():
    listing = _listing()
    listing_shape = contour_descriptors(listing.contour_normalized)
    rejected = {
        "pool": {"status": "REJECTED", "geometry": {"present": True}, "contour": []},
        "building": {
            "status": "CONFIRMED",
            "geometry": {"present": True, "area_m2": 200, "relative_area": 0.2, "aspect_ratio": 1.2},
            "contour": pca_normalize(_rectangle()).tolist(),
        },
        "driveway": {"status": "PROBABLE", "geometry": {"present": True}},
        "spatial": {},
    }
    confirmed = {
        "pool": {
            "status": "CONFIRMED",
            "geometry": {"present": True, "area_m2": 32, "shape": "kidney_or_curved"},
            "contour": pca_normalize(_octagon_with_lobe()).tolist(),
        },
        "building": {
            "status": "CONFIRMED",
            "geometry": {"present": True, "area_m2": 220, "orientation_deg": 0},
            "contour": pca_normalize(_rectangle()).tolist(),
        },
        "driveway": {"status": "UNKNOWN", "geometry": {}},
        "spatial": {"relationships": {"pool_house": {"dx": 0.16, "dy": 0.20, "dist": 0.41, "angle_deg": 51.0}}},
    }
    feats_r = v2_object_features(listing, rejected, listing_shape=listing_shape)
    feats_c = v2_object_features(listing, confirmed, listing_shape=listing_shape)
    assert feats_r["pool_presence"] is None
    assert feats_r["shape_v2"] is None
    neu_r, _, cov_r, _ = score_v2(
        feats_r,
        aerial=None,
        exterior=None,
        stand_size=0.95,
        weights=V2_WEIGHTS_NO_BUILDING,
        os_keys=OS_KEYS_NO_BUILDING,
        missing="neutral",
    )
    neu_c, _, cov_c, _ = score_v2(
        feats_c,
        aerial=None,
        exterior=None,
        stand_size=0.95,
        weights=V2_WEIGHTS_NO_BUILDING,
        os_keys=OS_KEYS_NO_BUILDING,
        missing="neutral",
    )
    assert cov_r == 0.0
    assert cov_c == 1.0
    assert neu_c > neu_r
    cov_score_r, _, _, factor_r = score_v2(
        feats_r,
        aerial=None,
        exterior=None,
        stand_size=0.95,
        weights=V2_WEIGHTS_NO_BUILDING,
        os_keys=OS_KEYS_NO_BUILDING,
        missing="coverage",
    )
    cov_score_c, _, _, factor_c = score_v2(
        feats_c,
        aerial=None,
        exterior=None,
        stand_size=0.95,
        weights=V2_WEIGHTS_NO_BUILDING,
        os_keys=OS_KEYS_NO_BUILDING,
        missing="coverage",
    )
    assert factor_r == 0.5
    assert factor_c == 1.0
    assert cov_score_c - cov_score_r > neu_c - neu_r


def test_driveway_without_listing_side_is_neutral():
    listing = _listing()
    seg = {
        "pool": {"status": "UNKNOWN", "geometry": {}},
        "building": {"status": "CONFIRMED", "geometry": {"present": True}},
        "driveway": {"status": "PROBABLE", "geometry": {"present": True}},
        "spatial": {"relationships": {"driveway_house": {"driveway_side": "south"}}},
    }
    feats = v2_object_features(
        listing, seg, listing_shape=None, listing_has_driveway=True, listing_driveway_side=None
    )
    assert feats["driveway"] is None
    assert driveway_spatial_similarity(None, True, seg) is None


def test_building_coarse_ignores_relative_area():
    listing = _listing()
    listing_shape = contour_descriptors(listing.contour_normalized)
    small = {
        "pool": {"status": "UNKNOWN", "geometry": {}},
        "building": {"status": "CONFIRMED", "geometry": {"present": True, "relative_area": 0.01, "area_m2": 80}},
        "driveway": {"status": "UNKNOWN", "geometry": {}},
        "spatial": {},
    }
    large = {
        "pool": {"status": "UNKNOWN", "geometry": {}},
        "building": {"status": "CONFIRMED", "geometry": {"present": True, "relative_area": 0.40, "area_m2": 900}},
        "driveway": {"status": "UNKNOWN", "geometry": {}},
        "spatial": {},
    }
    a = v2_object_features(listing, small, listing_shape=listing_shape, include_building_coarse=True)
    b = v2_object_features(listing, large, listing_shape=listing_shape, include_building_coarse=True)
    assert a["building_coarse"] == b["building_coarse"] == 0.7
