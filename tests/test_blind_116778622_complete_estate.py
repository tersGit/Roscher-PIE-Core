"""Blind 116778622 complete-estate benchmark: freeze-before-GT."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from backend.gis.estate_ags_matching.blind_116273255_complete_estate import (
    FROZEN_001_GIS,
    FROZEN_001_GIS_SHA256,
    FROZEN_001_INVENTORY,
    FROZEN_001_INVENTORY_SHA256,
    compare_three_complete_estate_blinds,
    load_or_extract_hybrid_block,
    ranking_separation,
    redact_identity,
    scan_prior_listing_artifacts,
    sha256_file,
    write_freeze,
)
from backend.gis.estate_ags_matching.listing_pool_gate_v1 import apply_listing_pool_gate
from backend.gis.estate_ags_matching.estate_property_inventory_v1 import pass1_parcels
from backend.gis.estate_ags_matching.blind_116273255_complete_estate import load_gis_002, load_inventory_002

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_blind_116778622_complete_estate.py"
MODULE = ROOT / "backend/gis/estate_ags_matching/blind_116273255_complete_estate.py"


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


def test_no_prior_116778622_ranking_artifacts_in_repo():
    scan = scan_prior_listing_artifacts("116778622")
    assert scan["frozen_hybrid_json_contains_listing"] is False
    assert scan["frozen_hybrid_json_used_as_ranking_input"] is False
    assert scan["workspace_path_hits_excluded"] == []


def test_script_forces_fresh_hybrid_and_photos():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "force_fresh_photos=True" in source
    assert "ignore_frozen_hybrid_json=True" in source
    assert "116778622" in source


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
        load_or_extract_hybrid_block("116778622", ignore_frozen_hybrid_json=True)
        raise AssertionError("expected KeyError without photos")
    except KeyError:
        pass


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
    digest = write_freeze({"listing_id": "116778622", "rankings_frozen": True}, rows, dest=dest)
    assert sha256_file(dest) == digest
    assert (tmp_path / "freeze.sha256").read_text(encoding="utf-8").strip() == digest
    payload = json.loads(dest.read_text(encoding="utf-8"))
    assert "sha256" not in payload


def test_ranking_separation_includes_top10_and_top20():
    rows = [
        {
            "hybrid_v2_rank": i,
            "stand_number": str(i),
            "hybrid_v2": round(0.80 - 0.01 * (i - 1), 4),
            "hybrid_v2_contrib": {
                "pool_presence": 0.14,
                "shape_v2": 0.29,
                "spatial_v2": 0.11,
                "aerial": 0.06,
                "exterior": 0.0438,
                "gis": 0.015,
                "stand_size": 0.0638,
            },
            "aerial_similarity": None,
            "hybrid_v2_spatial_v2": None,
            "os_high_conf_pool": True,
        }
        for i in range(1, 21)
    ]
    sep = ranking_separation(rows)
    assert sep["top10_score"] == 0.71
    assert sep["top20_score"] == 0.61
    assert sep["gap_1_10"] == 0.09
    assert sep["gap_1_20"] == 0.19
    assert "spatial_v2" in {item["term"] for item in sep["top1_neutral_padding"]}
    assert sep["top1_padding_share_of_score"] is not None


def test_compare_three_blind_tests_loads_pr18_and_pr19():
    current = [{"stand_number": f"x{i}"} for i in range(20)]
    result = compare_three_complete_estate_blinds(current, "116778622")
    assert "116273255" in result["listings"]
    assert "116223230" in result["listings"]
    assert result["intersection_top5_all_three"] == []
