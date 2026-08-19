"""Harness checks for the 115503057 freeze-only blind. No ground-truth identity."""

from __future__ import annotations

import ast
from pathlib import Path

from backend.gis.estate_ags_matching.blind_116273255_complete_estate import (
    scan_prior_listing_artifacts,
)
from backend.gis.estate_ags_matching.os_scoring_v2 import V2_WEIGHTS_NO_BUILDING
from backend.gis.estate_ags_matching.pool_inventory_no_unknown_safety_v1 import OVERLAY_ROOT

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_blind_115503057_complete_estate.py"
MODULE = ROOT / "backend/gis/estate_ags_matching/blind_116273255_complete_estate.py"


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
    prior = scan_prior_listing_artifacts("115503057")
    assert prior["workspace_path_hits_excluded"] == []
    assert prior["frozen_hybrid_json_contains_listing"] is False


def test_script_is_freeze_only_and_uses_safety_overlay():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "apply_corner_gate=True" in source
    assert "apply_candidate_pov=True" in source
    assert "load_inventory_pool_obs_v1_1_0" in source
    assert "run_after_freeze" not in source
    assert "extract_identity_from_html" not in source
    assert "confirm_ground_truth" not in source
    assert "COLOR_BGR2HSV" not in source
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
    overlay = OVERLAY_ROOT / "current.jsonl"
    assert overlay.is_file()


def test_run_freeze_defaults_do_not_enable_new_gates():
    source = MODULE.read_text(encoding="utf-8")
    freeze = source[source.index("def run_freeze") : source.index("def extract_identity_from_html")]
    assert "apply_corner_gate: bool = False" in freeze
    assert "apply_candidate_pov: bool = False" in freeze
