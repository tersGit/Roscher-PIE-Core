"""Harness checks for the 117170887 freeze-only blind. No ground-truth identity."""

from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path

from backend.gis.estate_ags_matching.blind_116273255_complete_estate import (
    overlay_os_payload_with_pov,
    ranking_quality_report,
    scan_prior_listing_artifacts,
)
from backend.gis.estate_ags_matching.os_scoring_v2 import V2_WEIGHTS_NO_BUILDING

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_blind_117170887_complete_estate.py"
MODULE = ROOT / "backend/gis/estate_ags_matching/blind_116273255_complete_estate.py"
OS_DIR = ROOT / "data/investigations/object_segmentation_v1/carlswald_north/json"


def test_scoring_v2_weights_unchanged():
    assert dict(V2_WEIGHTS_NO_BUILDING) == {
        "pool_presence": 0.14,
        "shape_v2": 0.36,
        "spatial_v2": 0.22,
        "aerial": 0.12,
        "exterior": 0.06,
        "gis": 0.03,
        "stand_size": 0.07,
    }


def test_listing_is_clean_before_freeze():
    prior = scan_prior_listing_artifacts("117170887")
    assert prior["workspace_path_hits_excluded"] == []
    assert prior["frozen_hybrid_json_contains_listing"] is False


def test_script_is_freeze_only_and_enables_new_gates():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "apply_corner_gate=True" in source
    assert "apply_candidate_pov=True" in source
    assert "run_after_freeze" not in source
    assert "extract_identity_from_html" not in source
    assert "confirm_ground_truth" not in source
    tree = ast.parse(source)
    assigned = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assigned.append(target.id)
    assert {
        "EVAL_STAND",
        "TRUE_STAND",
        "GROUND_TRUTH_STAND",
        "KNOWN_STAND",
        "GT_STAND",
    }.isdisjoint(assigned)


def test_run_freeze_defaults_do_not_enable_new_gates():
    source = MODULE.read_text(encoding="utf-8")
    freeze = source[source.index("def run_freeze") : source.index("def extract_identity_from_html")]
    assert "apply_corner_gate: bool = False" in freeze
    assert "apply_candidate_pov: bool = False" in freeze


def test_pov_overlay_does_not_rewrite_os_json(tmp_path):
    sample = next(OS_DIR.glob("*.json"), None)
    if sample is None:
        sample = next((ROOT / "data/investigations/object_segmentation_v1").glob("**/*.json"), None)
    if sample is None:
        payload = {"pool": {"status": "CONFIRMED", "geometry": {"present": True, "centroid_x": 0.9, "centroid_y": 0.9}}}
        before = deepcopy(payload)
        overlay, summary = overlay_os_payload_with_pov(payload, None)
        assert payload == before
        assert overlay is not payload
        assert summary["frozen_os_status"] == "CONFIRMED"
        return
    mtime = sample.stat().st_mtime_ns
    original = sample.read_text(encoding="utf-8")
    payload = __import__("json").loads(original)
    overlay, summary = overlay_os_payload_with_pov(payload, None)
    assert sample.read_text(encoding="utf-8") == original
    assert sample.stat().st_mtime_ns == mtime
    assert overlay is not payload
    assert summary["pov_status"] in {"CONFIRMED", "UNKNOWN", "REJECTED"}
    assert (payload.get("pool") or {}).get("status") == summary["frozen_os_status"]


def test_ranking_quality_no_shape_signal():
    report = ranking_quality_report([], listing_shape_available=False)
    assert report["class"] == "NO_SHAPE_SIGNAL"
