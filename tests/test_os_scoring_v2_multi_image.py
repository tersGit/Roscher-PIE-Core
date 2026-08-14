"""Multi-image listing fusion — generic, no stand/listing hardcodes."""

from __future__ import annotations

from pathlib import Path

from backend.gis.estate_ags_matching.os_scoring_v2_multi_image import (
    fuse_listing_observations,
    shape_view_quality,
    spatial_view_quality,
)
from backend.gis.estate_ags_matching.pool_geometry import PoolGeometryFingerprint


def test_module_has_no_stand_or_listing_hardcodes():
    text = Path("backend/gis/estate_ags_matching/os_scoring_v2_multi_image.py").read_text(encoding="utf-8")
    assert "365" not in text
    assert "116978058" not in text
    assert "583" not in text


def _fp(**kwargs) -> PoolGeometryFingerprint:
    base = dict(
        present=True,
        unknown=False,
        shape_class="irregular",
        aspect_ratio=1.8,
        compactness=0.50,
        convexity=0.85,
        relative_area=0.08,
        pool_to_house_dist=0.40,
        pool_to_house_angle_deg=80.0,
        house_centroid_x=0.4,
        house_centroid_y=0.4,
        contour_normalized=[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0], [0.0, 0.2]],
    )
    base.update(kwargs)
    return PoolGeometryFingerprint(**base)


def test_smeared_perspective_is_downweighted_for_shape():
    clean = _fp(compactness=0.55, aspect_ratio=1.7, relative_area=0.08)
    smear = _fp(compactness=0.14, aspect_ratio=3.1, relative_area=0.12)
    assert shape_view_quality(clean, "pool_garden") > shape_view_quality(smear, "pool_garden")


def test_closeup_without_house_is_weak_spatial():
    wide = _fp(relative_area=0.07, pool_to_house_dist=0.41)
    close = _fp(relative_area=0.40, pool_to_house_dist=0.05, house_centroid_x=None, house_centroid_y=None)
    assert spatial_view_quality(wide, "contextual") > spatial_view_quality(close, "pool_garden")


def test_fusion_does_not_average_incompatible_shape_clusters():
    compact = {
        "media_id": "a",
        "pool_present": True,
        "shape_quality": 0.80,
        "spatial_quality": 0.2,
        "scale_quality": 0.0,
        "house_visible": False,
        "pool_to_house_dist": None,
        "pool_roof_ratio": None,
        "fingerprint": _fp(compactness=0.58, aspect_ratio=1.6, evidence_media_id="a"),
        "descriptors": {"elongation": 1.6},
    }
    stretched = {
        "media_id": "b",
        "pool_present": True,
        "shape_quality": 0.40,
        "spatial_quality": 0.2,
        "scale_quality": 0.0,
        "house_visible": False,
        "pool_to_house_dist": None,
        "pool_roof_ratio": None,
        "fingerprint": _fp(compactness=0.16, aspect_ratio=3.2, evidence_media_id="b"),
        "descriptors": {"elongation": 3.2},
    }
    fused = fuse_listing_observations([compact, stretched])
    assert fused["shape_source"] == "a"
    assert fused["shape_cluster"] == ["a"]
    assert fused["fused_fingerprint"].evidence_media_id == "a"
    assert fused["fused_fingerprint"].compactness == 0.58
