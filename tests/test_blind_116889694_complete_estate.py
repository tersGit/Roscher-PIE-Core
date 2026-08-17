"""Blind 116889694 complete-estate benchmark: freeze-before-GT; Distinctive Contour v2 diagnostic-only."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import numpy as np

from backend.gis.estate_ags_matching.blind_116273255_complete_estate import (
    FROZEN_001_GIS,
    FROZEN_001_GIS_SHA256,
    FROZEN_001_INVENTORY,
    FROZEN_001_INVENTORY_SHA256,
    WATCH_FALSE_POSITIVE_116978058,
    compare_three_complete_estate_blinds,
    load_or_extract_hybrid_block,
    scan_prior_listing_artifacts,
    shape_discrimination,
    sha256_file,
    write_freeze,
)
from backend.gis.estate_ags_matching.distinctive_contour_v2 import (
    USED_IN_RANKING,
    analyze_mask_contour_pipeline,
    classify_stage_loss,
)
from backend.gis.estate_ags_matching.listing_pool_gate_v1 import apply_listing_pool_gate
from backend.gis.estate_ags_matching.estate_property_inventory_v1 import pass1_parcels
from backend.gis.estate_ags_matching.blind_116273255_complete_estate import load_gis_002, load_inventory_002
from backend.gis.estate_ags_matching.os_scoring_v2 import V2_WEIGHTS_NO_BUILDING

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_blind_116889694_complete_estate.py"
MODULE = ROOT / "backend/gis/estate_ags_matching/blind_116273255_complete_estate.py"
DCV2 = ROOT / "backend/gis/estate_ags_matching/distinctive_contour_v2.py"


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


def test_no_prior_116889694_ranking_artifacts():
    scan = scan_prior_listing_artifacts("116889694")
    assert scan["excluded_from_ranking_input"] is True
    assert scan["frozen_hybrid_json_used_as_ranking_input"] is False
    assert scan["frozen_hybrid_json_contains_listing"] is False
    assert scan["workspace_path_hits_excluded"] == []


def test_script_forces_fresh_hybrid_and_photos():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "force_fresh_photos=True" in source
    assert "ignore_frozen_hybrid_json=True" in source
    assert "116889694" in source


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
        load_or_extract_hybrid_block("116889694", ignore_frozen_hybrid_json=True)
        raise AssertionError("expected KeyError without photos")
    except KeyError:
        pass


def test_scoring_v2_weights_unchanged():
    assert V2_WEIGHTS_NO_BUILDING["shape_v2"] == 0.36
    assert V2_WEIGHTS_NO_BUILDING["stand_size"] == 0.07


def test_distinctive_contour_v2_is_not_a_ranking_input():
    assert USED_IN_RANKING is False
    text = DCV2.read_text(encoding="utf-8")
    assert "Does not enter ranking" in text
    assert "run_distinctive_contour_v2" in MODULE.read_text(encoding="utf-8")
    assert "distinctive_contour_v2=dcv2" in MODULE.read_text(encoding="utf-8")


def test_distinctive_contour_v2_detects_l_indent_on_raw_mask():
    mask = np.zeros((220, 220), np.uint8)
    mask[30:90, 30:190] = 255
    mask[30:190, 30:90] = 255
    result = analyze_mask_contour_pipeline(mask)
    assert result["used_in_ranking"] is False
    assert result["n_mask_components"] == 1
    raw = result["raw_contour"]
    assert raw is not None
    assert int(raw["n_raw_vertices"]) > 64
    assert result["official_scoring_contour"]["normalized_contour_point_count"] == 64


def test_distinctive_contour_v2_flags_indent_collapse():
    raw = {
        "n_major_indents": 2,
        "max_indent": 0.18,
        "solidity": 0.82,
        "n_major_directional_changes": 12,
        "elongation": 2.1,
    }
    scoring = {
        "n_major_indents": 0,
        "max_indent": 0.02,
        "solidity": 0.97,
        "n_major_directional_changes": 3,
        "elongation": 2.0,
    }
    loss = classify_stage_loss(raw, raw, scoring, n_mask_components=1, secondary_present=False)
    assert loss["verdict"] == "COLLAPSED"
    assert "major_indents" in loss["features_lost"]


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
    digest = write_freeze({"listing_id": "116889694", "rankings_frozen": True}, rows, dest=dest)
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


def test_compare_includes_116978058_and_false_positive_watch():
    current = [{"stand_number": str(i)} for i in range(20)]
    result = compare_three_complete_estate_blinds(current, "116889694")
    assert "116978058" in result["listings"]
    assert "116778622" in result["listings"]
    assert result["n_listings_compared"] >= 5
    assert set(WATCH_FALSE_POSITIVE_116978058) == {"351", "380", "468", "463", "461"}
    assert "false_positive_116978058_cluster" in result["watch_families"]
