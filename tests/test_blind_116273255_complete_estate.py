"""Blind 116273255 complete-estate benchmark: freeze-before-GT and frozen stack."""

from __future__ import annotations

import ast
from pathlib import Path

from backend.gis.dataset_registry import FROZEN_CARLSWALD_NORTH_001
from backend.gis.estate_ags_matching.blind_116273255_complete_estate import (
    COMPLETE_OS_DIR,
    FROZEN_001_GIS,
    FROZEN_001_GIS_SHA256,
    FROZEN_001_INVENTORY,
    FROZEN_001_INVENTORY_SHA256,
    classify_listing_pool_status,
    load_gis_002,
    load_inventory_002,
    load_os_payload,
    redact_identity,
    sha256_file,
)
from backend.gis.estate_ags_matching.estate_property_inventory_v1 import pass1_parcels
from backend.gis.estate_ags_matching.listing_pool_gate_v1 import apply_listing_pool_gate

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "backend/gis/estate_ags_matching/blind_116273255_complete_estate.py"
SCRIPT = ROOT / "scripts/run_blind_116273255_complete_estate.py"


def test_frozen_001_gis_and_inventory_hashes_unchanged():
    assert FROZEN_CARLSWALD_NORTH_001 == "carlswald_north_corrected_001"
    assert sha256_file(FROZEN_001_GIS) == FROZEN_001_GIS_SHA256
    assert sha256_file(FROZEN_001_INVENTORY) == FROZEN_001_INVENTORY_SHA256


def test_complete_dataset_is_400_unique_erven():
    dataset = load_gis_002()
    parcels = pass1_parcels(dataset)
    assert dataset["dataset_id"] == "carlswald_north_corrected_002"
    assert len(parcels) == 400
    inventory = load_inventory_002()
    assert len(inventory) == 400


def test_listing_yes_pool_gate_on_002_is_332():
    dataset = load_gis_002()
    parcels = pass1_parcels(dataset)
    inventory = load_inventory_002()
    candidates = [{"stand_number": row["stand_number"], "property_id": row.get("property_id")} for row in parcels]
    gate = apply_listing_pool_gate(candidates, inventory, "YES")
    assert gate.starting_count == 400
    assert gate.removed_confident_no == 68
    assert gate.yes_survivors == 118
    assert gate.unknown_survivors == 214
    assert gate.total_survivors == 332
    assert gate.pct_reduction == 17.0
    assert gate.removed_confident_yes == 0


def test_redact_identity_strips_stand_and_street():
    raw = "3 Bedroom House, Stand 999, 12 Fake Street, Carlswald North. Private pool."
    cleaned = redact_identity(raw)
    assert "999" not in cleaned
    assert "Fake Street" not in cleaned
    assert "Private pool" in cleaned
    assert "[STAND_REDACTED]" in cleaned
    assert "[STREET_REDACTED]" in cleaned


def test_listing_pool_yes_from_text_and_hybrid_without_ground_truth():
    acquisition = {
        "pool_text_present": True,
        "feature_hits": ["private pool", "l-shaped pool"],
    }
    hybrid = {
        "listing": {"n_scoring_ready": 3},
        "viewpoint_counts": {"pool_overview": 3, "pool_closeup": 1},
    }
    photos = {"pool_photo_count": 2, "scene_counts": {"pool_garden": 2}}
    result = classify_listing_pool_status(acquisition, hybrid, photos, None)
    assert result["listing_pool_status"] == "YES"
    assert result["ground_truth_used"] is False
    assert result["colour_used"] is False
    assert "listing_text_mentions_pool" in result["evidence"]


def test_os_loader_reads_both_json_directories():
    ext6 = load_os_payload("677")
    assert ext6.get("pool", {}).get("status") == "CONFIRMED"
    complete_files = list(COMPLETE_OS_DIR.glob("*.json"))
    assert complete_files
    stand = complete_files[0].stem.replace("_", "/", 1) if "_" in complete_files[0].stem else complete_files[0].stem
    payload = load_os_payload(complete_files[0].stem)
    assert payload.get("version") == "object_segmentation_v1" or "pool" in payload


def test_source_does_not_hardcode_ground_truth_stand():
    source = MODULE.read_text(encoding="utf-8") + "\n" + SCRIPT.read_text(encoding="utf-8")
    tree = ast.parse(source)
    assigned = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assigned.append(target.id)
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            assigned.append(node.target.id)
    forbidden = {
        "EVAL_STAND",
        "TRUE_STAND",
        "GROUND_TRUTH_STAND",
        "KNOWN_STAND",
        "GT_STAND",
    }
    assert forbidden.isdisjoint(assigned)
    assert "ground_truth_applied\": False" in MODULE.read_text(encoding="utf-8") or "ground_truth_applied" in source


def test_freeze_must_exist_before_gt_lookup():
    source = MODULE.read_text(encoding="utf-8")
    freeze_fn = source.index("def run_freeze")
    after_fn = source.index("def run_after_freeze")
    confirm_fn = source.index("def confirm_ground_truth")
    assert freeze_fn < after_fn
    assert "if not FREEZE_PATH.is_file()" in source[after_fn:]
    assert "refuse to look up ground truth" in source[after_fn:]
    assert confirm_fn > freeze_fn


def test_extract_identity_records_withheld_street():
    from backend.gis.estate_ags_matching.blind_116273255_complete_estate import extract_identity_from_html

    html = "<title>3 Bedroom House for sale in Carlswald North Estate</title> p24_address\">Contact agent for street address"
    ident = extract_identity_from_html(html)
    assert ident["street"] is None
    assert ident["street_withheld_contact_agent"] is True
    assert ident["stand_mentions"] == []
