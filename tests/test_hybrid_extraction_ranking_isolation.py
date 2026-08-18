"""Ranking/scoring isolation after Hybrid adapter eligibility change.

Adapter eligibility may now accept Hybrid scoring_ready FastSAM contours.
Production ranking weights, Scoring v2 formula, Pool Gate, OS v1, GIS inventory,
and stand-size contribution must stay frozen. Historical blind rankings are not rerun.
"""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

from backend.gis.estate_ags_matching.hybrid_geometry_ranking_test import (
    BLOCKED_SOURCES,
    SCORING_SOURCES,
    scoring_ready_frames,
)
from backend.gis.estate_ags_matching.listing_pool_gate_v1 import survives_listing_pool_gate
from backend.gis.estate_ags_matching.os_scoring_v2 import V2_WEIGHTS_NO_BUILDING, score_v2

ROOT = Path(__file__).resolve().parents[1]
FROZEN_001_GIS_SHA = "1bab3126fdfa9d397857f67f2d0cb65ddc410fc5d82afaf1a823c63018f56608"
FROZEN_001_INV_SHA = "3bc02c09c293d011b8f2d866b2075e3e9863cc9af9db5c054faa0dc722aca861"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_scoring_v2_weights_and_neutral_defaults_frozen():
    assert V2_WEIGHTS_NO_BUILDING == {
        "pool_presence": 0.14,
        "shape_v2": 0.36,
        "spatial_v2": 0.22,
        "aerial": 0.12,
        "exterior": 0.06,
        "gis": 0.03,
        "stand_size": 0.07,
    }
    source = (ROOT / "backend/gis/estate_ags_matching/os_scoring_v2.py").read_text(encoding="utf-8")
    assert 'missing="neutral"' in source or "missing=\"neutral\"" in source or 'missing: str = "neutral"' in source
    tree = ast.parse(source)
    assigns = [
        node
        for node in tree.body
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "V2_WEIGHTS_NO_BUILDING" for t in node.targets)
    ]
    assert assigns


def test_score_v2_formula_still_uses_frozen_weights():
    feats = {"pool_presence": 1.0, "shape_v2": 0.5, "spatial_v2": None}
    _total, contrib, _cov, _ = score_v2(
        feats,
        aerial=None,
        exterior=None,
        stand_size=0.5,
        weights=V2_WEIGHTS_NO_BUILDING,
        os_keys=("pool_presence", "shape_v2", "spatial_v2"),
        missing="neutral",
    )
    assert abs(contrib["stand_size"] - 0.07 * 0.5) < 1e-6
    assert abs(contrib["shape_v2"] - 0.36 * 0.5) < 1e-6
    assert abs(contrib["spatial_v2"] - 0.22 * 0.5) < 1e-6  # missing → 0.5-neutral
    assert abs(contrib["aerial"] - 0.12 * 0.5) < 1e-6


def test_pool_gate_unchanged_and_adapter_accepts_scoring_ready_fastsam():
    assert survives_listing_pool_gate("NO", "YES") is False
    assert survives_listing_pool_gate("YES", "YES") is True
    assert survives_listing_pool_gate("UNKNOWN", "YES") is True
    assert survives_listing_pool_gate("YES", "UNKNOWN") is True
    assert SCORING_SOURCES == frozenset({"yoloe", "yoloe_sam2", "fastsam_fallback"})
    assert BLOCKED_SOURCES == frozenset({"presence_only", "no_usable_geometry"})
    contour = [[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]
    frames = [
        {"media_id": "ok", "source": "yoloe_sam2", "scoring_ready": True, "dominant": {"contour_image": contour}},
        {"media_id": "fb", "source": "fastsam_fallback", "scoring_ready": True, "dominant": {"contour_image": contour}},
        {"media_id": "pr", "source": "presence_only", "scoring_ready": True, "dominant": {"contour_image": contour}},
        {"media_id": "no", "source": "fastsam_fallback", "scoring_ready": False, "dominant": {"contour_image": contour}},
    ]
    ready = scoring_ready_frames(frames)
    assert [f["media_id"] for f in ready] == ["ok", "fb"]


def test_gis_inventory_and_os_v1_bytes_untouched():
    gis = ROOT / "data/gis/carlswald_north_corrected_001.json"
    inv = ROOT / "data/estate_inventory/carlswald_north_corrected_001/current.jsonl"
    assert _sha(gis) == FROZEN_001_GIS_SHA
    assert _sha(inv) == FROZEN_001_INV_SHA
    os_src = (ROOT / "backend/vision/object_segmentation.py").read_text(encoding="utf-8")
    assert "def select_pool" in os_src
    assert "SEGMENTATION_VERSION = \"object_segmentation_v1\"" in os_src
    gate_src = (ROOT / "backend/gis/estate_ags_matching/listing_pool_gate_v1.py").read_text(encoding="utf-8")
    assert "Hard gate: discard only the opposite confident class" in gate_src


def test_hybrid_extraction_has_no_listing_or_gt_exceptions():
    text = (ROOT / "backend/gis/estate_ags_matching/hybrid_listing_pool_geometry_v1.py").read_text(encoding="utf-8")
    for token in ("116978058", "116889694", "ground_truth", "expected_stand", "carlswald"):
        assert token not in text.lower() if token == "carlswald" else token not in text
    rank_src = (ROOT / "backend/gis/estate_ags_matching/hybrid_geometry_ranking_test.py").read_text(encoding="utf-8")
    assert "fastsam_fallback" in rank_src
    assert "V2_WEIGHTS_NO_BUILDING" in rank_src
    assert "presence_only" in rank_src
    assert "corner" not in V2_WEIGHTS_NO_BUILDING
    assert "116889694" not in rank_src
    assert "116978058" not in rank_src


def test_os_v1_control_stands_remain_frozen():
    os_dir = ROOT / "data/investigations/object_segmentation_v1/carlswald_north/json"
    expected = {
        "677": "CONFIRMED",
        "612": "REJECTED",
        "408": "UNKNOWN",
        "420": "CONFIRMED",
        "570": "REJECTED",
        "370": "REJECTED",
    }
    for stand, status in expected.items():
        payload = json.loads((os_dir / f"{stand}.json").read_text(encoding="utf-8"))
        assert payload["pool"]["status"] == status
    notes_570 = json.loads((os_dir / "570.json").read_text(encoding="utf-8"))["pool"]["notes"]
    assert any("road" in str(n) or "shadow" in str(n) for n in notes_570)
    notes_612 = json.loads((os_dir / "612.json").read_text(encoding="utf-8"))["pool"]["notes"]
    assert "low_pool_evidence" in notes_612
    shape_420 = (json.loads((os_dir / "420.json").read_text(encoding="utf-8"))["pool"].get("geometry") or {}).get("shape")
    assert shape_420 in {"irregular", "kidney_or_curved"}
    notes_408 = json.loads((os_dir / "408.json").read_text(encoding="utf-8"))["pool"]["notes"]
    assert "no_pool_candidate" in notes_408
    convex_420 = (json.loads((os_dir / "420.json").read_text(encoding="utf-8"))["pool"].get("geometry") or {}).get("convexity")
    assert convex_420 is not None and float(convex_420) < 0.85
