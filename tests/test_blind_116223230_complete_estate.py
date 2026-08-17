"""Blind 116223230 complete-estate benchmark: freeze-before-GT."""

from __future__ import annotations

import ast
from pathlib import Path

from backend.gis.estate_ags_matching.blind_116273255_complete_estate import (
    FROZEN_001_GIS,
    FROZEN_001_GIS_SHA256,
    FROZEN_001_INVENTORY,
    FROZEN_001_INVENTORY_SHA256,
    classify_listing_pool_status,
    compare_repeat_candidates,
    load_or_extract_hybrid_block,
    ranking_separation,
    redact_identity,
    sha256_file,
)
from backend.gis.estate_ags_matching.listing_pool_gate_v1 import apply_listing_pool_gate
from backend.gis.estate_ags_matching.estate_property_inventory_v1 import pass1_parcels
from backend.gis.estate_ags_matching.blind_116273255_complete_estate import load_gis_002, load_inventory_002

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_blind_116223230_complete_estate.py"
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


def test_redact_identity_strips_erf_as_well_as_stand():
    cleaned = redact_identity("Erf 1234, Stand 99, 12 Fake Street. Private pool.")
    assert "1234" not in cleaned
    assert "99" not in cleaned
    assert "Fake Street" not in cleaned
    assert "Private pool" in cleaned


def test_script_has_no_hardcoded_ground_truth_stand():
    source = SCRIPT.read_text(encoding="utf-8") + "\n" + MODULE.read_text(encoding="utf-8")
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    assigned = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assigned.append(target.id)
    assert {"EVAL_STAND", "TRUE_STAND", "GROUND_TRUTH_STAND", "GT_STAND"}.isdisjoint(assigned)
    assert "116223230" in SCRIPT.read_text(encoding="utf-8")
    assert "freeze.json missing; refuse to look up ground truth" in source


def test_hybrid_extract_is_used_when_listing_absent_from_frozen_json():
    try:
        load_or_extract_hybrid_block("116223230")
        raise AssertionError("expected KeyError without photos")
    except KeyError:
        pass


def test_ranking_separation_flags_neutral_padding():
    rows = [
        {
            "hybrid_v2_rank": 1,
            "stand_number": "A",
            "hybrid_v2": 0.72,
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
        },
        {"hybrid_v2_rank": 2, "stand_number": "B", "hybrid_v2": 0.71, "hybrid_v2_contrib": {}},
        {"hybrid_v2_rank": 3, "stand_number": "C", "hybrid_v2": 0.70, "hybrid_v2_contrib": {}},
        {"hybrid_v2_rank": 4, "stand_number": "D", "hybrid_v2": 0.69, "hybrid_v2_contrib": {}},
        {"hybrid_v2_rank": 5, "stand_number": "E", "hybrid_v2": 0.68, "hybrid_v2_contrib": {}},
    ]
    sep = ranking_separation(rows)
    assert sep["gap_1_2"] == 0.01
    terms = {item["term"] for item in sep["top1_neutral_padding"]}
    assert "spatial_v2" in terms
    assert "aerial" in terms
    assert "gis" in terms
    drivers = {item["term"] for item in sep["top1_genuine_drivers"]}
    assert "shape_v2" in drivers


def test_compare_repeat_candidates_flags_overlap():
    previous = ROOT / "data/investigations/blind_116273255_complete_estate/freeze.json"
    if not previous.is_file():
        return
    current = [{"stand_number": "1/334"}, {"stand_number": "1/373"}, {"stand_number": "999"}]
    # pad to look like top5
    current += [{"stand_number": str(i)} for i in range(10, 27)]
    result = compare_repeat_candidates(current, previous)
    assert result["previous_freeze_found"] is True
    assert "1/334" in result["overlap_top20"] or result["watch_families"]["334_family"]["previous_ranks"]
