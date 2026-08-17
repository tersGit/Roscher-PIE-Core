"""Blind 117262832 complete-estate freeze-only: PR #23 + PR #24, no ground truth."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from backend.gis.estate_ags_matching.blind_116273255_complete_estate import (
    FROZEN_001_GIS,
    FROZEN_001_GIS_SHA256,
    FROZEN_001_INVENTORY,
    FROZEN_001_INVENTORY_SHA256,
    load_or_extract_hybrid_block,
    scan_prior_listing_artifacts,
    shape_discrimination,
    sha256_file,
    write_freeze,
)
from backend.gis.estate_ags_matching.hybrid_geometry_ranking_test import (
    BLOCKED_SOURCES,
    SCORING_SOURCES,
)
from backend.gis.estate_ags_matching.listing_pool_gate_v1 import apply_listing_pool_gate
from backend.gis.estate_ags_matching.estate_property_inventory_v1 import pass1_parcels
from backend.gis.estate_ags_matching.blind_116273255_complete_estate import load_gis_002, load_inventory_002
from backend.gis.estate_ags_matching.os_scoring_v2 import V2_WEIGHTS_NO_BUILDING

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_blind_117262832_complete_estate.py"
MODULE = ROOT / "backend/gis/estate_ags_matching/blind_116273255_complete_estate.py"
ADAPTER = ROOT / "backend/gis/estate_ags_matching/hybrid_geometry_ranking_test.py"
HISTORICAL = (
    "116978058",
    "116889694",
    "116778622",
    "116273255",
    "116223230",
)


def test_frozen_001_hashes_still_untouched():
    assert sha256_file(FROZEN_001_GIS) == FROZEN_001_GIS_SHA256
    assert sha256_file(FROZEN_001_INVENTORY) == FROZEN_001_INVENTORY_SHA256


def test_listing_yes_gate_still_332():
    parcels = pass1_parcels(load_gis_002())
    inventory = load_inventory_002()
    candidates = [{"stand_number": row["stand_number"], "property_id": row.get("property_id")} for row in parcels]
    gate = apply_listing_pool_gate(candidates, inventory, "YES")
    assert gate.starting_count == 400
    assert gate.total_survivors == 332


def test_no_prior_117262832_ranking_artifacts():
    scan = scan_prior_listing_artifacts("117262832")
    assert scan["excluded_from_ranking_input"] is True
    assert scan["frozen_hybrid_json_used_as_ranking_input"] is False
    assert scan["frozen_hybrid_json_contains_listing"] is False
    assert scan["workspace_path_hits_excluded"] == []
    assert scan["hybrid_source"] == "extract_frame_geometry_frozen_hybrid_v1_fresh"


def test_script_forces_fresh_hybrid_and_photos():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "force_fresh_photos=True" in source
    assert "ignore_frozen_hybrid_json=True" in source
    assert "117262832" in source
    assert "run_after_freeze" not in source
    assert "STOP after freeze" in source


def test_script_has_no_hardcoded_ground_truth_stand():
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    assigned = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assigned.append(target.id)
    assert {"EVAL_STAND", "TRUE_STAND", "GROUND_TRUTH_STAND", "GT_STAND"}.isdisjoint(assigned)
    assert "freeze.json missing; refuse to look up ground truth" in MODULE.read_text(encoding="utf-8")


def test_hybrid_extract_skips_frozen_json_when_ignored():
    try:
        load_or_extract_hybrid_block("117262832", ignore_frozen_hybrid_json=True)
        raise AssertionError("expected KeyError without photos")
    except KeyError:
        pass


def test_scoring_v2_weights_unchanged():
    assert V2_WEIGHTS_NO_BUILDING == {
        "pool_presence": 0.14,
        "shape_v2": 0.36,
        "spatial_v2": 0.22,
        "aerial": 0.12,
        "exterior": 0.06,
        "gis": 0.03,
        "stand_size": 0.07,
    }


def test_pr24_adapter_allows_scoring_ready_fastsam():
    assert SCORING_SOURCES == frozenset({"yoloe", "yoloe_sam2", "fastsam_fallback"})
    assert BLOCKED_SOURCES == frozenset({"presence_only", "no_usable_geometry"})
    text = ADAPTER.read_text(encoding="utf-8")
    assert "fastsam_fallback" in text
    assert "Detector identity is not an eligibility filter" in text


def test_historical_blind_freezes_untouched():
    import subprocess

    for listing_id in HISTORICAL:
        dest = ROOT / f"data/investigations/blind_{listing_id}_complete_estate"
        freeze = dest / "freeze.json"
        recorded = dest / "freeze.sha256"
        assert freeze.is_file(), listing_id
        assert recorded.is_file(), listing_id
        rel = str(dest.relative_to(ROOT))
        diff = subprocess.check_output(
            ["git", "diff", "--name-only", "--", rel],
            cwd=ROOT,
            text=True,
        ).strip()
        assert diff == "", f"historical freeze tree modified for {listing_id}: {diff}"


def test_write_freeze_on_disk_hash_matches_recorded(tmp_path: Path):
    dest = tmp_path / "freeze.json"
    rows = [
        {
            "hybrid_v2_rank": 1,
            "stand_number": "A",
            "hybrid_v2": 0.72,
            "inventory_pool_status": "YES",
            "os_pool_status": "CONFIRMED",
            "os_high_conf_pool": True,
            "hybrid_v2_shape_v2": 0.8,
            "hybrid_v2_spatial_v2": None,
            "hybrid_v2_coverage": 0.6,
            "aerial_similarity": None,
            "exterior_similarity": 0.7,
            "hybrid_v2_contrib": {"pool_presence": 0.14},
        }
    ]
    digest = write_freeze({"listing_id": "117262832", "rankings_frozen": True}, rows, dest=dest)
    assert sha256_file(dest) == digest
    payload = json.loads(dest.read_text(encoding="utf-8"))
    assert "sha256" not in payload


def test_shape_discrimination_class_includes_user_labels():
    cluster = [
        {
            "hybrid_v2_rank": i,
            "stand_number": str(i),
            "hybrid_v2": 0.70,
            "hybrid_v2_shape_v2": 0.82,
            "inventory_pool_status": "YES",
        }
        for i in range(1, 21)
    ]
    result = shape_discrimination(cluster)
    assert result["discrimination_class"] == "BROAD_CLUSTER"
