import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "experiments" / "listing_visual_intelligence_v4" / "blind_execution_20260909"


def test_blind_execution_freeze_has_required_provenance():
    manifest = json.loads((OUT / "LVI_V4_BLIND_FREEZE_MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "BLIND_VLM_OBSERVATIONS_FROZEN_NO_G9H_READ"
    assert manifest["model"]["revision"] == "7e3e67edbbed1bf9888184d9df282b700a323964"
    assert manifest["files"]


def test_raw_outputs_are_preserved_when_no_semantic_normalization_is_possible():
    raw = (OUT / "LVI_V4_RAW_SINGLE_FRAME_OUTPUTS.jsonl").read_text(encoding="utf-8").splitlines()
    normalized = json.loads((OUT / "LVI_V4_NORMALIZED_OBSERVATIONS.json").read_text(encoding="utf-8"))
    assert raw
    # The pinned model's raw responses are the source of truth.  An empty
    # normalized set is valid when no response has the requested structure.
    assert normalized == []
