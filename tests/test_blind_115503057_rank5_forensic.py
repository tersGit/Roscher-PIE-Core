"""Rank-5 forensic must not touch the 115503057 freeze or Scoring v2."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

from backend.gis.estate_ags_matching.os_scoring_v2 import V2_WEIGHTS_NO_BUILDING

ROOT = Path(__file__).resolve().parents[1]
INV = ROOT / "data/investigations/blind_115503057_complete_estate"
FREEZE = INV / "freeze.json"
SHA = INV / "freeze.sha256"
RANKINGS = INV / "rankings_frozen.json"
CANDS = INV / "all_candidates.json"
REPORT = INV / "RANK5_FORENSIC.md"
JSON_OUT = INV / "rank5_forensic.json"
PANEL = INV / "panels/rank5_top5_forensic_proof.jpg"
SCRIPT = ROOT / "scripts/run_blind_115503057_rank5_forensic.py"
LOCK = "a6465002f681268391d4a87f3039532f47fd97e76d9a43217a8a45c841604ff6"
LOCK_COMMIT = "5aa42ec266a0c515a75e9b7f4da623b0be84dc66"
TOP5 = ["868", "624", "648", "545", "401"]


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


def test_freeze_hash_still_matches_lock():
    recorded = SHA.read_text(encoding="utf-8").strip()
    on_disk = hashlib.sha256(FREEZE.read_bytes()).hexdigest()
    assert recorded == LOCK
    assert on_disk == recorded
    rankings = json.loads(RANKINGS.read_text(encoding="utf-8"))
    assert rankings["sha256"] == LOCK


def test_frozen_top5_and_401_rank_unchanged():
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    assert freeze["ground_truth_applied"] is False
    assert freeze["scoring_v2_weights_modified"] is False
    assert freeze["colour_used_in_ranking"] is False
    top5 = [str(row["stand_number"]) for row in freeze["ranking"]["top20"][:5]]
    assert top5 == TOP5
    row401 = next(row for row in freeze["ranking"]["top20"] if str(row["stand_number"]) == "401")
    assert row401["rank"] == 5
    assert row401["score"] == 0.7152


def test_script_is_diagnostic_only():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "Does not" in source or "does not" in source
    assert "LOCK_COMMIT" in source
    tree = ast.parse(source)
    assigned = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assigned.append(target.id)
    assert assigned  # sanity
    assert "COLOR_BGR2HSV" not in source


def test_rank5_artefacts_exist_and_do_not_claim_rerank():
    assert REPORT.is_file()
    assert JSON_OUT.is_file()
    assert PANEL.is_file()
    payload = json.loads(JSON_OUT.read_text(encoding="utf-8"))
    assert payload["not_a_rerank"] is True
    assert payload["production_scoring_modified"] is False
    assert payload["freeze_integrity"]["sha256"] == LOCK
    assert payload["freeze_integrity"]["freeze_commit"] == LOCK_COMMIT
    assert payload["freeze_integrity"]["401_frozen_rank"] == 5
    report = REPORT.read_text(encoding="utf-8")
    assert "868 / 624 / 648 / 545 / 401" in report
    assert "GO for another freeze-only blind" in report
    assert "NO-GO for a scoring-changed" in report


def test_all_candidates_untouched_401():
    payload = json.loads(CANDS.read_text(encoding="utf-8"))
    row = next(item for item in payload["rows"] if str(item["stand_number"]) == "401")
    assert row["rank"] == 5
    assert row["score"] == 0.7152
