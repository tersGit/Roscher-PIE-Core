"""Hybrid geometry ranking adapter — no listing/stand/colour rules."""

from pathlib import Path

from backend.gis.estate_ags_matching.hybrid_geometry_ranking_test import (
    BLOCKED_SOURCES,
    SCORING_SOURCES,
    fingerprint_from_hybrid_frame,
    listing_evidence_from_hybrid_block,
    score_one_candidate,
    scoring_ready_frames,
)
from backend.gis.estate_ags_matching.os_scoring_v2 import contour_descriptors


def _rect_contour():
    return [[0.2, 0.4], [0.7, 0.4], [0.7, 0.7], [0.2, 0.7], [0.2, 0.4]]


def _ready_frame(media_id="img-008", source="yoloe_sam2", secondary=False):
    frame = {
        "media_id": media_id,
        "viewpoint": "pool_overview",
        "source": source,
        "scoring_ready": True,
        "dominant": {
            "contour_image": _rect_contour(),
            "centroid_xy": [0.45, 0.55],
            "structural_support": 0.6,
            "geometry": {
                "compactness": 0.55,
                "solidity": 0.96,
                "aspect_ratio": 2.4,
                "n_major_indents": 0,
                "orientation_deg": -90.0,
            },
        },
        "secondary": None,
        "component_relation": {"component_count": 1},
        "descriptors": {"oblique": True, "nadir_area_manufactured": False},
        "contour_image": _rect_contour(),
    }
    if secondary:
        frame["secondary"] = {
            "contour_image": [[0.75, 0.75], [0.82, 0.75], [0.82, 0.82], [0.75, 0.82], [0.75, 0.75]],
            "centroid_xy": [0.78, 0.78],
            "geometry": {
                "compactness": 0.8,
                "solidity": 0.99,
                "aspect_ratio": 1.1,
                "n_major_indents": 0,
            },
        }
        frame["component_relation"] = {"component_count": 2, "relative_size": 0.2, "adjacent": True}
    return frame


def test_module_has_no_stand_listing_colour_or_l_rules():
    text = Path("backend/gis/estate_ags_matching/hybrid_geometry_ranking_test.py").read_text(encoding="utf-8")
    assert "365" not in text
    assert "116978058" not in text
    assert "116273255" not in text
    assert "jacuzzi" not in text.lower()
    assert "octagon" not in text.lower()
    assert "l-shaped" not in text.lower()
    assert "COLOR_BGR2HSV" not in text
    assert "inRange" not in text
    assert "pool_mask" not in text
    assert "extract_pool_geometry" not in text
    assert "V2_WEIGHTS_NO_BUILDING" in text
    assert 'missing="neutral"' in text or "missing=\"neutral\"" in text


def test_fastsam_and_presence_cannot_enter_scoring():
    frames = [
        _ready_frame("ok", "yoloe_sam2"),
        {
            "media_id": "fb",
            "source": "fastsam_fallback",
            "scoring_ready": False,
            "dominant": {"contour_image": _rect_contour(), "geometry": {}},
        },
        {
            "media_id": "pr",
            "source": "presence_only",
            "scoring_ready": False,
            "dominant": {"contour_image": _rect_contour(), "geometry": {}},
        },
        {
            "media_id": "lie",
            "source": "fastsam_fallback",
            "scoring_ready": True,
            "dominant": {"contour_image": _rect_contour(), "geometry": {"compactness": 0.5, "solidity": 0.9, "aspect_ratio": 1.2}},
        },
    ]
    ready = scoring_ready_frames(frames)
    assert [f["media_id"] for f in ready] == ["ok"]
    assert "fastsam_fallback" in BLOCKED_SOURCES
    assert "yoloe_sam2" in SCORING_SOURCES


def test_oblique_area_and_pool_house_are_omitted():
    fp = fingerprint_from_hybrid_frame(_ready_frame())
    assert fp.relative_area is None
    assert fp.pool_to_house_dist is None
    assert fp.pool_to_house_angle_deg is None
    assert fp.orientation_deg is None
    assert fp.present is True
    assert "relative_area_omitted_not_nadir" in fp.notes
    assert "colour_not_used" in fp.notes


def test_official_evidence_uses_chosen_yoloe_not_fallback():
    block = {
        "listing": {"chosen_id": "img-008", "chosen_source": "yoloe_sam2"},
        "frames": [
            _ready_frame("img-008", "yoloe_sam2", secondary=True),
            {
                "media_id": "img-003",
                "source": "fastsam_fallback",
                "scoring_ready": False,
                "dominant": {"contour_image": _rect_contour(), "geometry": {}},
            },
        ],
    }
    evidence = listing_evidence_from_hybrid_block(block)
    assert evidence["chosen_id"] == "img-008"
    assert evidence["feature_sources"]["fastsam_used"] is False
    assert evidence["feature_sources"]["colour_used"] is False
    assert evidence["feature_sources"]["relative_area_used"] is False
    assert evidence["feature_sources"]["spatial_from"] is None
    assert evidence["feature_sources"]["secondary_recorded"] is True
    assert evidence["feature_sources"]["secondary_in_official_contour"] is False
    assert evidence["fingerprint"].evidence_media_id == "img-008"


def test_rejected_os_pool_does_not_receive_shape_credit():
    listing = fingerprint_from_hybrid_frame(_ready_frame())
    shape = contour_descriptors(listing.contour_image)
    rejected = {
        "pool": {"status": "REJECTED", "geometry": {"present": True}, "contour": _rect_contour()},
        "building": {"status": "CONFIRMED", "geometry": {"present": True}},
        "driveway": {"status": "UNKNOWN", "geometry": {}},
        "spatial": {},
    }
    confirmed = {
        "pool": {
            "status": "CONFIRMED",
            "geometry": {"present": True, "area_m2": 40},
            "contour": _rect_contour(),
        },
        "building": {"status": "CONFIRMED", "geometry": {"present": True, "area_m2": 200}},
        "driveway": {"status": "UNKNOWN", "geometry": {}},
        "spatial": {"relationships": {"pool_house": {"dx": 0.1, "dy": 0.1, "dist": 0.2, "angle_deg": 45}}},
    }
    bad = score_one_candidate(listing, shape, rejected, aerial=None, exterior=None, stand_size=0.5)
    good = score_one_candidate(listing, shape, confirmed, aerial=None, exterior=None, stand_size=0.5)
    assert bad["feats"]["pool_presence"] is None
    assert bad["feats"]["shape_v2"] is None
    assert bad["spatial_v2"] is None
    assert good["feats"]["pool_presence"] == 1.0
    assert good["shape_v2"] is not None
    assert good["spatial_v2"] is None  # listing spatial omitted → neutral, not a match
    assert good["score"] > bad["score"]


def test_secondary_contour_is_not_the_official_fingerprint():
    frame = _ready_frame(secondary=True)
    official = fingerprint_from_hybrid_frame(frame)
    spa = fingerprint_from_hybrid_frame(frame, use_secondary=True)
    assert official.contour_image != spa.contour_image
    assert "role=dominant" in official.notes
    assert "role=secondary" in spa.notes
