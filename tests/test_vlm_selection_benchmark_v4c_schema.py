import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "experiments" / "vlm_selection_benchmark_v4c"


def test_v4c_runner_is_neutral_only_and_compiles():
    source = (ROOT / "scripts" / "run_vlm_selection_benchmark_v4c.py").read_text(encoding="utf-8")
    ast.parse(source)
    forbidden = ("listing_visual_intelligence", "117539389", "117255083", "G9H", "candidate", "ranking")
    assert not any(value in source for value in forbidden)


def test_v4c_evidence_uses_only_local_synthetic_controls():
    controls = json.loads((OUT / "neutral_controls_and_truth_rubric.json").read_text(encoding="utf-8"))
    assert {item["id"] for item in controls} == {"coloured_shapes", "property_schematic", "neutral_multiview"}
    assert all("listing" not in item["path"] for item in controls)
    assert all("pie" not in item["path"].lower() for item in controls)


def test_v4c_evidence_has_reproducible_reports_and_raw_results():
    required = {
        "README.md", "resource_baseline.json", "candidate_comparison.md", "checkpoint_manifests.json",
        "rubric_a_to_m.md", "metric_scoring.md", "selection_and_acceptance.md",
        "raw_outputs_smolvlm2_2b.json", "raw_outputs_qwen25vl_3b.json",
    }
    assert required <= {path.name for path in OUT.iterdir()}
