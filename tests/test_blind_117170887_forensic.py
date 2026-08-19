"""Forensic artefacts for listing 117170887 must not touch the freeze."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INV = ROOT / "data/investigations/blind_117170887_complete_estate"
FREEZE = INV / "freeze.json"
SHA = INV / "freeze.sha256"
FORENSIC = INV / "FORENSIC.md"
FORENSIC_JSON = INV / "forensic.json"
GT = INV / "ground_truth.json"
PANEL = INV / "panels/forensic_listing_641_top5.jpg"
RANKINGS = INV / "rankings_frozen.json"


def test_freeze_hash_still_matches_lock():
    recorded = SHA.read_text(encoding="utf-8").strip()
    on_disk = hashlib.sha256(FREEZE.read_bytes()).hexdigest()
    assert recorded == "96a66c8b240d8cab317d861d94582f1ba0bec84531c876fba4aaf090b4e82aa3"
    assert on_disk == recorded


def test_freeze_still_has_no_ground_truth_applied():
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    rankings = json.loads(RANKINGS.read_text(encoding="utf-8"))
    assert freeze["ground_truth_applied"] is False
    assert rankings["ground_truth_applied"] is False
    assert rankings["sha256"] == "96a66c8b240d8cab317d861d94582f1ba0bec84531c876fba4aaf090b4e82aa3"
    top5 = [row["stand_number"] for row in freeze["ranking"]["top20"][:5]]
    assert top5 == ["545", "868", "568", "572", "897"]


def test_forensic_recovers_641_without_claiming_a_rerank():
    forensic = json.loads(FORENSIC_JSON.read_text(encoding="utf-8"))
    gt = json.loads(GT.read_text(encoding="utf-8"))
    report = FORENSIC.read_text(encoding="utf-8")
    assert forensic["not_a_rerank"] is True
    assert forensic["pie_modified"] is False
    assert forensic["official_fingerprint_replaced"] is False
    assert forensic["true_stand"] == "641"
    assert forensic["primary_failure"] == "ESTATE POOL DETECTION"
    assert forensic["listing_fingerprint"]["verdict"] == "PARTIAL"
    assert gt["confirmed_stand"] == "641"
    assert gt["inferred_from_pie_rank"] is False
    assert gt["freeze_modified"] is False
    assert "641" in report
    assert "ESTATE POOL DETECTION" in report
    assert PANEL.is_file() and PANEL.stat().st_size > 1000
    assert gt["confirmed_stand"] != "545"
