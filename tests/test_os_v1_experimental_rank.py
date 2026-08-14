"""Object Segmentation v1 experimental ranking — no production penalty on miss."""

from __future__ import annotations

from backend.gis.estate_ags_matching.os_v1_experimental_rank import (
    experimental_hybrid_score,
    experimental_pure_os_score,
    is_high_conf,
    os_object_features,
)
from backend.gis.estate_ags_matching.pool_geometry import PoolGeometryFingerprint


def _listing() -> PoolGeometryFingerprint:
    return PoolGeometryFingerprint(
        present=True,
        unknown=False,
        shape_class="irregular",
        aspect_ratio=1.93,
        orientation_deg=90.0,
        compactness=0.16,
        rectangularity=0.56,
        convexity=0.76,
        relative_area=0.11,
        pool_to_house_dx=0.16,
        pool_to_house_dy=0.19,
        pool_to_house_dist=0.41,
    )


def test_rejected_is_not_positive_and_not_a_penalty():
    listing = _listing()
    seg = {
        "pool": {"status": "REJECTED", "geometry": {"present": True, "area_m2": 12}},
        "building": {"status": "UNKNOWN", "geometry": {}},
        "driveway": {"status": "UNKNOWN", "geometry": {}},
        "spatial": {},
    }
    feats = os_object_features(listing, seg, listing_has_driveway=True)
    assert feats["pool_presence"] is None
    assert feats["pool_contour"] is None
    assert feats["driveway"] is None
    score, contrib = experimental_pure_os_score(feats)
    assert contrib == {}
    assert score == 0.0


def test_unknown_pool_does_not_penalise_hybrid_clip_terms():
    listing = _listing()
    feats = os_object_features(listing, {"pool": {"status": "UNKNOWN", "geometry": {}}})
    score, contrib = experimental_hybrid_score(
        feats, aerial=0.8, video=None, exterior=0.7, stand_size=0.9
    )
    assert "pool_presence" not in contrib
    assert contrib["aerial"] > 0
    assert contrib["stand_size"] > 0
    assert score > 0.5


def test_confirmed_pool_is_positive_evidence():
    listing = _listing()
    seg = {
        "pool": {
            "status": "CONFIRMED",
            "geometry": {
                "present": True,
                "shape": "kidney_or_curved",
                "aspect_ratio": 1.77,
                "orientation_deg": 135.0,
                "compactness": 0.67,
                "rectangularity": 0.70,
                "convexity": 0.93,
                "area_m2": 32.5,
            },
        },
        "building": {
            "status": "CONFIRMED",
            "geometry": {
                "present": True,
                "area_m2": 225.0,
                "relative_area": 0.08,
                "orientation_deg": 160.0,
                "aspect_ratio": 1.4,
            },
        },
        "driveway": {"status": "PROBABLE", "geometry": {"present": True}},
        "spatial": {"relationships": {"pool_house": {"dx": 0.17, "dy": 0.49, "dist": 0.51}}},
    }
    feats = os_object_features(
        listing,
        seg,
        listing_roof_area_frac=0.04,
        listing_roof_orientation_deg=160.0,
        listing_roof_aspect=1.5,
        listing_has_driveway=True,
    )
    assert feats["pool_presence"] == 1.0
    assert feats["pool_shape"] == 0.75
    assert feats["pool_contour"] is not None and feats["pool_contour"] > 0.3
    assert feats["driveway"] == 0.85
    assert is_high_conf(seg["pool"])
    score, contrib = experimental_pure_os_score(feats)
    assert contrib["pool_presence"] > 0
    assert score > 0.4
