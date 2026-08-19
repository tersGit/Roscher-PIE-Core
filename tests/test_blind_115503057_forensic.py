"""Forensic artefacts for listing 115503057 must not touch the freeze."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INV = ROOT / "data/investigations/blind_115503057_complete_estate"
FREEZE = INV / "freeze.json"
SHA = INV / "freeze.sha256"
FORENSIC = INV / "FORENSIC.md"
FORENSIC_JSON = INV / "forensic.json"
GT = INV / "ground_truth.json"
PANEL = INV / "panels/forensic_listing_401_top5.jpg"
RANKINGS = INV / "rankings_frozen.json"
LOCK = "a6465002f681268391d4a87f3039532f47fd97e76d9a43217a8a45c841604ff6"
LOCK_COMMIT = "5aa42ec266a0c515a75e9b7f4da623b0be84dc66"


def test_freeze_hash_still_matches_lock():
    recorded = SHA.read_text(encoding="utf-8").strip()
    on_disk = hashlib.sha256(FREEZE.read_bytes()).hexdigest()
    assert recorded == LOCK
    assert on_disk == recorded


def test_freeze_still_has_no_ground_truth_applied():
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    rankings = json.loads(RANKINGS.read_text(encoding="utf-8"))
    assert freeze["ground_truth_applied"] is False
    assert rankings["ground_truth_applied"] is False
    assert rankings["sha256"] == LOCK
    top5 = [row["stand_number"] for row in freeze["ranking"]["top20"][:5]]
    assert top5 == ["868", "624", "648", "545", "401"]
    assert freeze["ranking_configuration"]["scoring_v2_weights"]["shape_v2"] == 0.36
    assert freeze["ranking_configuration"]["scoring_v2_weights"]["spatial_v2"] == 0.22


def test_forensic_recovers_401_without_claiming_a_rerank():
    forensic = json.loads(FORENSIC_JSON.read_text(encoding="utf-8"))
    gt = json.loads(GT.read_text(encoding="utf-8"))
    report = FORENSIC.read_text(encoding="utf-8")
    assert forensic["not_a_rerank"] is True
    assert forensic["pie_modified"] is False
    assert forensic["official_fingerprint_replaced"] is False
    assert forensic["scores_recomputed"] is False
    assert forensic["historical_freeze_sha256"] == LOCK
    assert forensic["historical_freeze_commit"] == LOCK_COMMIT
    assert forensic["true_stand"] == "401"
    assert forensic["classification"] == "BLIND HIT — TOP 5"
    assert forensic["blind_rank"] == 5
    assert forensic["true_stand_401"]["final_frozen_rank"] == 5
    assert forensic["true_stand_401"]["spatial_v2"] is None
    assert forensic["why_rank_5"]["spatial_v2_uniquely_suppressed_401"] is False
    assert gt["confirmed_stand"] == "401"
    assert gt["inferred_from_pie_rank"] is False
    assert gt["freeze_modified"] is False
    assert gt["identity"]["street_address"] == "6 BUFFALO THORN DRIVE"
    assert "BLIND HIT — TOP 5" in report
    assert LOCK in report
    assert PANEL.is_file() and PANEL.stat().st_size > 1000
    assert gt["confirmed_stand"] != "868"
    assert "897" in report
    assert "919" in report
