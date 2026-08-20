"""Guards for listing 116778622 current-stack regression (not a first-time blind).

This listing was previously frozen under PR #20 as UNAVAILABLE / UNLABELLED.
The current-stack run must:

* use a NEW output directory so the historical freeze is not overwritten
* ignore frozen Hybrid JSON (listing_id 116778622 is not in that JSON anyway)
* enable Corner Gate + Pool Object Validation
* overlay Estate Property Inventory v1.1.0
* freeze with current Scoring v2 weights (no PR #31 scoring changes)
* NOT call run_after_freeze and NOT set GT_STAND
* NOT use water colour
* NOT import historical ranking / shortlist / candidate identities as inputs
"""
from __future__ import annotations

import ast
import hashlib
import json
import unittest
from pathlib import Path

from backend.gis.estate_ags_matching.os_scoring_v2 import V2_WEIGHTS_NO_BUILDING

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_blind_116778622_current_stack.py"
HISTORICAL_FREEZE_SHA = ROOT / "data/investigations/blind_116778622_complete_estate/freeze.sha256"
CURRENT_OUT = ROOT / "data/investigations/blind_116778622_current_stack"

FROZEN_V2_WEIGHTS = {
    "pool_presence": 0.14,
    "shape_v2": 0.36,
    "spatial_v2": 0.22,
    "aerial": 0.12,
    "exterior": 0.06,
    "gis": 0.03,
    "stand_size": 0.07,
}


class TestBlind116778622CurrentStack(unittest.TestCase):
    def test_script_exists(self):
        self.assertTrue(SCRIPT.is_file())

    def test_historical_pr20_freeze_is_preserved_on_disk(self):
        self.assertTrue(HISTORICAL_FREEZE_SHA.is_file())
        digest = HISTORICAL_FREEZE_SHA.read_text(encoding="utf-8").strip()
        self.assertTrue(digest.startswith("3eb8f54d"), digest[:16])

    def test_new_output_dir_does_not_overwrite_historical_freeze(self):
        src = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("blind_116778622_current_stack", src)
        self.assertNotIn('OUT_DIR = ROOT / "data/investigations/blind_116778622_complete_estate"', src)

    def test_listing_id_and_url(self):
        src = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("116778622", src)
        self.assertIn("property24.com/for-sale/carlswald-north-estate/midrand/gauteng/12743/116778622", src)

    def test_freeze_only_no_after_freeze_no_gt(self):
        src = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("run_after_freeze", src)
        self.assertNotIn("GT_STAND", src)
        self.assertNotIn("evaluate_gt", src)
        self.assertIn("STOP after freeze", src)

    def test_current_stack_flags(self):
        src = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("ignore_frozen_hybrid_json=True", src)
        self.assertIn("apply_corner_gate=True", src)
        self.assertIn("apply_candidate_pov=True", src)
        self.assertIn("load_inventory_pool_obs_v1_1_0()", src)
        self.assertIn("estate_property_inventory_v1.1.0_pool_obs", src)
        self.assertIn("force_fresh_photos=True", src)

    def test_does_not_load_historical_ranking_as_input(self):
        src = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("blind_116778622_complete_estate/freeze.json", src)
        self.assertNotIn("blind_116778622_complete_estate/rankings_frozen.json", src)
        self.assertNotIn("json.loads((HISTORICAL_PR20_DIR", src)
        tree = ast.parse(src)
        loaded_historical = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if "blind_116778622_complete_estate" in node.value and (
                    "rankings_frozen" in node.value or node.value.endswith("freeze.json")
                ):
                    loaded_historical.append(node.value)
        self.assertEqual(loaded_historical, [])

    def test_no_water_colour(self):
        src = SCRIPT.read_text(encoding="utf-8")
        lowered = src.lower()
        self.assertNotIn("water_colour", lowered)
        self.assertNotIn("water color", lowered)

    def test_scoring_v2_weights_unchanged(self):
        src = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("if dict(V2_WEIGHTS_NO_BUILDING) != FROZEN_WEIGHTS", src)
        self.assertEqual(dict(V2_WEIGHTS_NO_BUILDING), FROZEN_V2_WEIGHTS)

    def test_no_pr31_scoring_changes_in_script(self):
        src = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("missing='omit'", src)
        self.assertNotIn('missing="omit"', src)
        self.assertIn("are **not** implemented", src)
        self.assertIn("PR #31", src)

    def test_native15_and_distinctive_reporting_only(self):
        src = SCRIPT.read_text(encoding="utf-8")
        freeze_mod = (ROOT / "backend/gis/estate_ags_matching/blind_116273255_complete_estate.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("run_freeze(", src)
        self.assertIn("def ensure_native15_crops", freeze_mod)
        self.assertIn('"used_in_ranking": False', freeze_mod)
        self.assertIn("distinctive_contour_v2", freeze_mod)

    def test_frozen_files_sha256_match_when_present(self):
        freeze = CURRENT_OUT / "freeze.json"
        rankings = CURRENT_OUT / "rankings_frozen.json"
        sha_path = CURRENT_OUT / "freeze.sha256"
        if not freeze.is_file():
            self.skipTest("current-stack freeze not written yet")
        digest = hashlib.sha256(freeze.read_bytes()).hexdigest()
        on_disk = sha_path.read_text(encoding="utf-8").strip()
        self.assertEqual(digest, on_disk)
        self.assertTrue(rankings.is_file())
        payload = json.loads(freeze.read_text(encoding="utf-8"))
        self.assertEqual(payload["listing_id"], "116778622")
        self.assertTrue(payload["rankings_frozen"])
        self.assertFalse(payload["ground_truth_applied"])
        self.assertFalse(payload["colour_used_in_ranking"])
        self.assertFalse(payload["scoring_v2_weights_modified"])
        self.assertNotEqual(digest, HISTORICAL_FREEZE_SHA.read_text(encoding="utf-8").strip())


if __name__ == "__main__":
    unittest.main()
