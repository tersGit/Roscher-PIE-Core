import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "experiments" / "vlm_output_failure_analysis_v4b"


def test_v4b_evidence_is_neutral_only_and_complete():
    controls = json.loads((OUT / "neutral_controls.json").read_text(encoding="utf-8"))
    results = json.loads((OUT / "raw_neutral_generation_results.json").read_text(encoding="utf-8"))
    assert {control["id"] for control in controls} == {"basic_geometric_scene", "layout_scene"}
    assert len(results) == 8
    assert all(result["message_image_bindings"] == 1 for result in results)
    assert all(result["pixel_values_shape"][0] == 1 for result in results)
    assert all("listing" not in result["control_id"] for result in results)


def test_v4b_forensics_reference_but_do_not_copy_frozen_inputs():
    references = json.loads((OUT / "frozen_raw_forensic_references.json").read_text(encoding="utf-8"))
    assert {reference["record_count"] for reference in references} == {8, 32}
    assert all(len(reference["sha256"]) == 64 for reference in references)
