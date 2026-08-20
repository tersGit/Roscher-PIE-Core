"""Guards for the 116778622 Shape v2 forensic (diagnostic only).

Must not rewrite PR #32 freeze hashes or change production Scoring v2 weights.
"""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path

from backend.gis.estate_ags_matching.os_scoring_v2 import V2_WEIGHTS_NO_BUILDING

ROOT = Path(__file__).resolve().parents[1]
INV = ROOT / "data/investigations/blind_116778622_current_stack"
SCRIPT = ROOT / "scripts/run_shape_v2_forensic_116778622.py"
FAMILY = ROOT / "backend/gis/estate_ags_matching/pool_shape_family_v1.py"
LOCK = "dce17f82162920ceeb6d39c2aa2b456a5bcdb16399ecfeb853e7892a0b694a29"
PR20_SHA = ROOT / "data/investigations/blind_116778622_complete_estate/freeze.sha256"

FROZEN_V2_WEIGHTS = {
    "pool_presence": 0.14,
    "shape_v2": 0.36,
    "spatial_v2": 0.22,
    "aerial": 0.12,
    "exterior": 0.06,
    "gis": 0.03,
    "stand_size": 0.07,
}


def test_production_weights_unchanged():
    assert dict(V2_WEIGHTS_NO_BUILDING) == FROZEN_V2_WEIGHTS


def test_pr32_freeze_hash_unchanged():
    freeze = INV / "freeze.json"
    sha_path = INV / "freeze.sha256"
    rankings = INV / "rankings_frozen.json"
    digest = hashlib.sha256(freeze.read_bytes()).hexdigest()
    assert digest == LOCK
    assert sha_path.read_text(encoding="utf-8").strip() == LOCK
    recorded = rankings.read_text(encoding="utf-8")
    assert LOCK in recorded


def test_pr20_historical_freeze_untouched():
    digest = PR20_SHA.read_text(encoding="utf-8").strip()
    assert digest.startswith("3eb8f54d")


def test_script_is_diagnostic_only():
    src = SCRIPT.read_text(encoding="utf-8")
    assert "Does not rewrite freeze.json" in src or "does not rewrite freeze.json" in src.lower() or "Does not rewrite" in src
    assert "EXPECTED_SHA" in src
    lowered = src.lower()
    assert "water_colour" not in lowered
    assert "water color" not in lowered
    tree = ast.parse(src)
    assigned = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assigned.append(target.id)
    assert "GT_STAND" not in assigned
    assert "V2_WEIGHTS_NO_BUILDING" not in assigned


def test_family_module_not_wired_into_score_v2():
    scoring = (ROOT / "backend/gis/estate_ags_matching/os_scoring_v2.py").read_text(encoding="utf-8")
    assert "pool_shape_family_v1" not in scoring
    freeze_runner = (ROOT / "backend/gis/estate_ags_matching/blind_116273255_complete_estate.py").read_text(
        encoding="utf-8"
    )
    assert "pool_shape_family_v1" not in freeze_runner


def test_family_module_has_no_listing_hardcodes():
    text = FAMILY.read_text(encoding="utf-8")
    assert "116778622" not in text
    assert "GT_STAND" not in text


def test_forensic_artefacts_when_present():
    report = INV / "SHAPE_V2_FORENSIC.md"
    if not report.is_file():
        return
    text = report.read_text(encoding="utf-8")
    assert LOCK in text
    assert "Phase 9" in text
    assert (INV / "shape_family_diagnostic.json").is_file()
    assert (INV / "SHAPE_FAMILY_REGRESSION.md").is_file()
    assert (INV / "shape_v2_exact_contours" / "listing_116778622-005.json").is_file()
    assert (INV / "panels" / "shape_v2_pipeline" / "listing_116778622-005.jpg").is_file()
    assert (INV / "panels" / "shape_family_validation.jpg").is_file()
    # freeze files still locked after artefact write
    digest = hashlib.sha256((INV / "freeze.json").read_bytes()).hexdigest()
    assert digest == LOCK
