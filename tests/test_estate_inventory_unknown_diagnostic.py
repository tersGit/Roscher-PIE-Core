"""UNKNOWN diagnostic is read-only and does not retune inventory or ranking."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from backend.gis.estate_ags_matching.estate_inventory_unknown_diagnostic import (
    analyse_unknowns,
    conservative_v11_simulation,
    coverage_report,
    diagnose_unknown_os,
    load_gis,
    load_inventory_rows,
)
from backend.gis.estate_ags_matching.estate_property_inventory_v1 import classify_pool_from_os
from backend.gis.estate_ags_matching.listing_pool_gate_v1 import apply_listing_pool_gate

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "data/estate_inventory/carlswald_north_corrected_001/current.jsonl"
OS_DIR = ROOT / "data/investigations/object_segmentation_v1/carlswald_north/json"


def test_coverage_explains_330_without_changing_boundaries():
    dataset = load_gis()
    rows = load_inventory_rows()
    report = coverage_report(dataset, rows)
    assert report["source_parcel_count"] == 416
    assert report["pass1_rows_before_dedup"] == 337
    assert report["unique_erven_after_property_id_dedup"] == 330
    assert report["duplicate_gis_rows_removed"] == 7
    assert report["inventory_rows"] == 330
    assert report["os_v1_fingerprints_for_pass1"] == 330
    assert "SUMMERSET EXT.6" in report["townships_in_dataset"]
    assert "SUMMERSET EXT.13" in report["townships_in_dataset"]
    assert "SUMMERSET EXT.3" not in report["townships_in_dataset"]
    assert "CARLSWALD ESTATE" in report["excluded_wrong_estate_townships"]


def test_unknown_reasons_cover_all_179():
    rows = load_inventory_rows()
    analysis = analyse_unknowns(rows)
    assert analysis["unknown_n"] == 179
    assert sum(analysis["primary_reason_counts"].values()) == 179
    assert analysis["rejected_n"] == 132
    assert analysis["unknown_solely_building_inadequate_n"] == 43
    assert analysis["good_full_parcel_imagery_n"] == 179


def test_rejected_is_not_converted_to_no():
    payload = json.loads((OS_DIR / "370.json").read_text(encoding="utf-8"))
    inv = {
        "stand_number": "370",
        "pool_status": "UNKNOWN",
        "unknown_reason": "os_rejected_weak_evidence_not_absence",
        "diagnostic_flags": [],
    }
    diag = diagnose_unknown_os(payload, inv)
    assert classify_pool_from_os(payload).pool_status == "UNKNOWN"
    assert diag["inventory_pool_status"] == "UNKNOWN"
    assert diag["os_pool_status"] == "REJECTED"
    assert diag["primary_reason"] in {"os_rejected", "pool_candidate_confidence_insufficient"}


def test_neighbour_examples_are_not_yes():
    rows = load_inventory_rows()
    by = {r["stand_number"]: r for r in rows}
    for stand in ("408", "612", "658", "633", "1/334", "1105"):
        assert by[stand]["pool_status"] != "YES"


def test_simulation_does_not_change_current_inventory_bytes():
    before = hashlib.sha256(INVENTORY.read_bytes()).hexdigest()
    rows = load_inventory_rows()
    analysis = analyse_unknowns(rows)
    sim = conservative_v11_simulation(rows, analysis)
    after = hashlib.sha256(INVENTORY.read_bytes()).hexdigest()
    assert before == after
    assert sim["current_v1"]["counts"]["YES"] == 91
    assert sim["current_v1"]["counts"]["NO"] == 60
    assert sim["current_v1"]["counts"]["UNKNOWN"] == 179
    assert sim["current_v1"]["gate_listing_yes"]["total_survivors"] == 270
    assert sim["current_v1"]["gate_listing_no"]["total_survivors"] == 239
    assert sim["upper_bound_if_building_gate_dropped_for_no"]["counts"]["NO"] == 103
    assert sim["upper_bound_if_building_gate_dropped_for_no"]["classified_pct"] < 80
    assert sim["unsafe_visual_empty_as_no"]["counts"]["NO"] == 91
    assert sim["conservative_v1_1_no_rule_change"]["counts"] == sim["current_v1"]["counts"]


def test_gate_semantics_unchanged():
    records = [
        {"parcel_id": "1", "pool_status": "YES"},
        {"parcel_id": "2", "pool_status": "NO"},
        {"parcel_id": "3", "pool_status": "UNKNOWN"},
    ]
    yes = apply_listing_pool_gate(records, records, "YES")
    no = apply_listing_pool_gate(records, records, "NO")
    assert {r["parcel_id"] for r in yes.survivors} == {"1", "3"}
    assert {r["parcel_id"] for r in no.survivors} == {"2", "3"}


def test_safe_no_visual_review_covers_all_43_and_does_not_auto_convert():
    rows = load_inventory_rows()
    analysis = analyse_unknowns(rows)
    safe = analysis["safe_no"]
    assert safe["good_full_parcel_imagery_n"] == 179
    assert safe["good_imagery_and_os_zero_candidate_n"] == 43
    assert safe["visual_no_credible_in_parcel_pool_n"] == 31
    assert safe["visual_missed_or_dark_pool_n"] == 10
    assert safe["visual_occlusion_cannot_certify_n"] == 2
    assert safe["visual_no_credible_in_parcel_pool_n"] + safe["visual_missed_or_dark_pool_n"] + safe["visual_occlusion_cannot_certify_n"] == 43
    assert safe["automated_safe_no_from_the_43"] == 0
    assert "339" in safe["missed_pool_stands"]
    assert "408" in safe["missed_pool_stands"]
    assert "370" not in safe["potential_visual_no_stands"]


def test_report_reasons_sum_to_179():
    rows = load_inventory_rows()
    analysis = analyse_unknowns(rows)
    assert analysis["unknown_n"] == 179
    assert sum(analysis["report_reason_counts"].values()) == 179
    assert analysis["report_reason_counts"]["os_rejected"] == 116
    assert analysis["report_reason_counts"]["good_imagery_no_pool_candidate"] == 43
    assert analysis["report_reason_counts"]["weak_ambiguous_pool_candidate"] == 16
    assert analysis["report_reason_counts"]["partially_outside_parcel"] == 4
    assert analysis["poor_imagery_coverage_n"] == 0
    assert analysis["inadequate_parcel_mask_n"] == 0


def test_stand_339_no_candidate_is_not_safe_no():
    """Bright in-parcel pool missed by OS; building gate is the only reason it is not NO."""
    rows = load_inventory_rows()
    row = next(item for item in rows if item["stand_number"] == "339")
    assert row["pool_status"] == "UNKNOWN"
    assert row["unknown_reason"] == "no_candidate_with_poor_segmentation"
    os_payload = json.loads((OS_DIR / "339.json").read_text(encoding="utf-8"))
    assert os_payload["pool"]["status"] == "UNKNOWN"
    assert "no_pool_candidate" in os_payload["pool"]["notes"]


def test_diagnostic_modules_do_not_touch_frozen_ranking():
    text = Path("backend/gis/estate_ags_matching/estate_inventory_unknown_diagnostic.py").read_text(
        encoding="utf-8"
    )
    script = Path("scripts/run_estate_inventory_unknown_diagnostic.py").read_text(encoding="utf-8")
    for src in (text, script):
        assert "combined_score" not in src
        assert "V2_WEIGHTS" not in src
    assert "def classify_pool_from_os" not in text
    frozen = Path("backend/vision/object_segmentation.py").read_text(encoding="utf-8")
    assert 'SEGMENTATION_VERSION = "object_segmentation_v1"' in frozen
