"""Blind 116978058 distinctive-pool complete-estate benchmark: freeze-before-GT."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from backend.gis.estate_ags_matching.blind_116273255_complete_estate import (
    FROZEN_001_GIS,
    FROZEN_001_GIS_SHA256,
    FROZEN_001_INVENTORY,
    FROZEN_001_INVENTORY_SHA256,
    WATCH_REPEAT_STANDS,
    compare_three_complete_estate_blinds,
    distinctive_pool_fingerprint,
    load_or_extract_hybrid_block,
    ranking_separation,
    scan_prior_listing_artifacts,
    shape_discrimination,
    sha256_file,
    write_freeze,
)
from backend.gis.estate_ags_matching.listing_pool_gate_v1 import apply_listing_pool_gate
from backend.gis.estate_ags_matching.estate_property_inventory_v1 import pass1_parcels
from backend.gis.estate_ags_matching.blind_116273255_complete_estate import load_gis_002, load_inventory_002
from backend.gis.estate_ags_matching.os_scoring_v2 import V2_WEIGHTS_NO_BUILDING, contour_descriptors

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_blind_116978058_complete_estate.py"
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


def test_prior_116978058_artifacts_are_inventoried_and_excluded():
    scan = scan_prior_listing_artifacts("116978058")
    assert scan["excluded_from_ranking_input"] is True
    assert scan["frozen_hybrid_json_used_as_ranking_input"] is False
    assert scan["hybrid_source"] == "extract_frame_geometry_frozen_hybrid_v1_fresh"
    assert scan["frozen_hybrid_json_contains_listing"] is True
    assert any("116978058" in path for path in scan["workspace_path_hits_excluded"])
    current = "blind_116978058_complete_estate"
    assert all(current not in path for path in scan["workspace_path_hits_excluded"])


def test_script_forces_fresh_hybrid_and_photos():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "force_fresh_photos=True" in source
    assert "ignore_frozen_hybrid_json=True" in source
    assert "116978058" in source


def test_script_has_no_hardcoded_ground_truth_stand():
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    assigned = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(node, ast.Name):
                    assigned.append(target.id)
                if isinstance(target, ast.Name):
                    assigned.append(target.id)
    assert {"EVAL_STAND", "TRUE_STAND", "GROUND_TRUTH_STAND", "GT_STAND"}.isdisjoint(assigned)
    assert "freeze.json missing; refuse to look up ground truth" in MODULE.read_text(encoding="utf-8")


def test_hybrid_extract_skips_frozen_json_when_ignored():
    try:
        load_or_extract_hybrid_block("116978058", ignore_frozen_hybrid_json=True)
        raise AssertionError("expected KeyError without photos")
    except KeyError:
        pass


def test_scoring_v2_weights_unchanged():
    assert V2_WEIGHTS_NO_BUILDING["shape_v2"] == 0.36
    assert V2_WEIGHTS_NO_BUILDING["stand_size"] == 0.07
    assert V2_WEIGHTS_NO_BUILDING["spatial_v2"] == 0.22


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
    digest = write_freeze({"listing_id": "116978058", "rankings_frozen": True}, rows, dest=dest)
    assert sha256_file(dest) == digest
    assert (tmp_path / "freeze.sha256").read_text(encoding="utf-8").strip() == digest
    payload = json.loads(dest.read_text(encoding="utf-8"))
    assert "sha256" not in payload


def test_distinctive_fingerprint_reports_l_planform_without_ranking():
    # Coarse L: two rectangles sharing a corner, sampled as a polygon.
    contour = (
        [[0.0, 0.0], [4.0, 0.0], [4.0, 1.2], [1.2, 1.2], [1.2, 4.0], [0.0, 4.0]]
        + [[0.0, y] for y in [3.5, 3.0, 2.5, 2.0, 1.5, 1.0, 0.5]]
    )
    desc = contour_descriptors(contour)
    assert desc is not None
    fingerprint = {
        "hybrid_evidence": {
            "chosen_id": "x-001",
            "fingerprint": {
                "present": True,
                "shape_class": "irregular",
                "aspect_ratio": desc["elongation"],
                "convexity": desc["solidity"],
            },
        },
        "qualitative": {"hybrid_chosen_id": "x-001", "hybrid_chosen_source": "yoloe_sam2"},
        "listing_shape_obj": desc,
        "evidence_obj": {"chosen_frame": {"dominant": {"geometry": {"n_major_indents": desc["n_major_indents"]}}}},
    }
    distinctive = distinctive_pool_fingerprint(fingerprint)
    assert distinctive["present"] is True
    assert distinctive["colour_used"] is False
    assert distinctive["used_as_ranking_input_change"] is False
    assert distinctive["normalized_contour_point_count"] >= 5
    assert distinctive["relative_limb_lengths"] is not None
    assert distinctive["pool_to_house_relationship"].startswith("not_genuinely_measurable")


def test_shape_discrimination_flags_broad_cluster_vs_subset():
    cluster = [
        {
            "hybrid_v2_rank": i,
            "stand_number": str(600 + i),
            "hybrid_v2": 0.70 - 0.001 * i,
            "hybrid_v2_shape_v2": 0.82,
            "inventory_pool_status": "YES",
        }
        for i in range(1, 21)
    ]
    clustered = shape_discrimination(cluster)
    assert clustered["discrimination_mode"] == "BROAD_CLUSTER"
    assert clustered["n_genuinely_similar_geometry"] == 20
    subset = [
        {
            "hybrid_v2_rank": i,
            "stand_number": str(i),
            "hybrid_v2": 0.80 - 0.01 * i,
            "hybrid_v2_shape_v2": 0.91 if i == 1 else (0.84 if i == 2 else (0.70 if i <= 5 else 0.55)),
            "inventory_pool_status": "YES",
        }
        for i in range(1, 21)
    ]
    isolated = shape_discrimination(subset)
    assert isolated["top1_top2_shape_gap"] == 0.07
    assert isolated["n_high_rank_despite_weak_geometry"] >= 1


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
    assert sep["gap_1_20"] == 0.19


def test_compare_includes_previous_three_and_watch_cluster():
    current = [{"stand_number": str(stand)} for stand in [900, 901, 902, 903, 904] + list(range(10, 25))]
    result = compare_three_complete_estate_blinds(current, "116978058")
    assert "116273255" in result["listings"]
    assert "116223230" in result["listings"]
    assert "116778622" in result["listings"]
    assert "116978058" in result["listings"]
    assert result["n_listings_compared"] == 4
    assert set(WATCH_REPEAT_STANDS) == {"605", "444", "573", "446", "401"}
    assert "yes_pool_cluster" in result["watch_families"]
    assert result["distinctive_shape_dropped_repeat_cluster"] is True
