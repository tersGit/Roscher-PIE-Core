import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "experiments" / "listing_visual_intelligence_v4"


def test_capability_failure_is_explicit_and_provenanced():
    gate = json.loads((OUT / "LVI_V4_CAPABILITY_GATE.json").read_text(encoding="utf-8"))

    assert gate["schema_version"] == "LVI_V4_CAPABILITY_GATE_V1"
    assert gate["result"] == "FAIL_CAPTION_VLM_UNAVAILABLE_STOPPED"
    assert gate["selected_model"]["selection_status"] == "NOT_CONFIGURED"
    assert gate["runtime"]["device"] == "cpu"
    assert gate["discovered_cached_models"]
    assert all(not endpoint["reachable"] for endpoint in gate["local_runtime_discovery"]["local_openai_compatible_endpoints"])
    assert "G9H input" in gate["prohibitions_observed"]


def test_capability_stop_does_not_claim_vlm_outputs():
    prohibited_outputs = [
        "LVI_V4_MEDIA_INVENTORY.csv",
        "LVI_V4_SELECTED_FRAMES.csv",
        "LVI_V4_RAW_VLM_OBSERVATIONS.jsonl",
        "LVI_V4_NORMALIZED_FRAME_OBSERVATIONS.jsonl",
        "LVI_V4_BLIND_FREEZE_MANIFEST.json",
        "LVI_V4_POST_FREEZE_G9H_EVALUATION.md",
    ]

    assert all(not (OUT / filename).exists() for filename in prohibited_outputs)
