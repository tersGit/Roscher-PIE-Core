#!/usr/bin/env python3
"""Emit human-readable, neutral-only V4C benchmark evidence from raw runs."""

from __future__ import annotations

import hashlib
import json
import os
import platform
from pathlib import Path

import psutil
import torch
from transformers import __version__ as transformers_version


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "experiments" / "vlm_selection_benchmark_v4c"


def sha256(path: Path) -> str:
    hashed = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hashed.update(chunk)
    return hashed.hexdigest()


def write(name: str, text: str) -> None:
    (OUT / name).write_text(text, encoding="utf-8")


def checkpoint_manifest() -> None:
    cache = Path(os.environ.get("HF_HUB_CACHE", Path.home() / ".cache" / "huggingface" / "hub"))
    models = json.loads((OUT / "runtime_smolvlm2_2b.json").read_text(encoding="utf-8")), json.loads(
        (OUT / "runtime_qwen25vl_3b.json").read_text(encoding="utf-8")
    )
    records = []
    for model in models:
        folder = "models--" + model["model_id"].replace("/", "--")
        snapshot = cache / folder / "snapshots" / model["revision"]
        files = [
            {"path": str(path.relative_to(snapshot)).replace("\\", "/"), "bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in sorted(snapshot.rglob("*")) if path.is_file()
        ]
        records.append({"model_id": model["model_id"], "revision": model["revision"], "snapshot": str(snapshot), "files": files})
    write("checkpoint_manifests.json", json.dumps(records, indent=2, sort_keys=True) + "\n")


def main() -> None:
    checkpoint_manifest()
    disk = psutil.disk_usage(str(ROOT))
    write("resource_baseline.json", json.dumps({
        "capture_scope": "CPU-only neutral V4C environment baseline",
        "cpu": "AMD Ryzen 7 7730U with Radeon Graphics",
        "physical_cores": 8,
        "logical_processors": 16,
        "total_ram_gib": 15.31,
        "available_ram_gib_at_initial_capture": 4.48,
        "free_disk_gib_at_initial_capture": 57.71,
        "free_disk_gib_after_models": round(disk.free / 1024**3, 2),
        "python": platform.python_version(),
        "torch": torch.__version__,
        "transformers": transformers_version,
        "cuda_available": torch.cuda.is_available(),
        "ollama": "unavailable",
        "llama_cpp_python": "unavailable: no CPython 3.14 Windows binary wheel",
        "selected_runtime": "Transformers CPU; model dtype is recorded per model",
        "dependency_installations": ["accelerate 1.14.0", "qwen-vl-utils 0.0.14", "sentencepiece 0.2.2", "num2words 0.5.14"],
    }, indent=2, sort_keys=True) + "\n")
    write("candidate_comparison.md", """# Candidate comparison

| Candidate | Revision / parameters | CPU deployment | Image and multi-image | CPU assessment | Outcome |
|---|---|---|---|---|---|
| HuggingFaceTB/SmolVLM2-2.2B-Instruct | `482adb537c021c86670beed01cd58990d01e72e4`; 2.2468B | Tested Transformers float32; GGUF Q4_K_M + projector is a future lower-RAM route | Yes / yes | Fits at 8-9 GiB RSS; 76-186 s per prompt | LIMITED |
| Qwen/Qwen2.5-VL-3B-Instruct | `66285546d2b821cf421d4f5eb2576359d3770cd3`; 3.7546B | Tested Transformers bfloat16; GGUF Q4_K_M + Q8 projector is a future lower-RAM route | Yes / yes | Fits at 7.6 GiB RSS; 119-367 s per prompt | LIMITED |
| openbmb/MiniCPM-V-4 | `6f69a8235885be89608f3a71ffd40695b379e1e7`; 4.1B | Not downloaded: custom-code runtime and expected 5-8 GiB quantized working set | Yes / yes/video | Strong prospective option, but not controlled-tested here | NOT TESTED |
| google/gemma-4-E4B-it | `ee0ef6023621cff504d758262d4e04895a5af4a2`; 4.5B effective | Not downloaded: Q4 plus projector is about 5.15 GB and 24 GiB RAM is prudent | Yes / yes/video frames | Not safely practical on this 15.3 GiB host | NOT TESTED |

Sources: [SmolVLM2 model card](https://huggingface.co/HuggingFaceTB/SmolVLM2-2.2B-Instruct), [Qwen2.5-VL model card](https://huggingface.co/Qwen/Qwen2.5-VL-3B-Instruct), [MiniCPM-V 4 model card](https://huggingface.co/openbmb/MiniCPM-V-4), [Gemma 4 model card](https://huggingface.co/google/gemma-4-E4B-it), and [llama.cpp multimodal documentation](https://github.com/ggml-org/llama.cpp/blob/master/docs/multimodal.md). Download-size/RAM values are deployment estimates, not measurements from this run.
""")
    write("rubric_a_to_m.md", """# Neutral ground-truth rubric A-M

Score factual and spatial image dependence, not prose fluency. A response receives credit only for facts visibly supported by the unlabelled generated control.

| ID | Criterion |
|---|---|
| A | Red rectangle recognized as a rectangle, not a square. |
| B | Blue circle correctly located right of red rectangle. |
| C | Yellow triangle correctly located below red rectangle. |
| D | Green rectangle correctly located below blue circle. |
| E | Road recognized at the bottom/front of schematic. |
| F | Driveway recognized as the connection from road to house. |
| G | House and red roof recognized. |
| H | Pool recognized right of house. |
| I | Neighbour building recognized left of house. |
| J | Tree recognized above pool. |
| K | Boundary recognized as surrounding the scene. |
| L | Multi-view differences: pool only first view; driveway only second view; shared house/road. |
| M | Hallucination restraint and UNKNOWN discipline: no invented features; explicit unknown/non-visible only when warranted. |

Pass requires correct E-L relationships, no material hallucination, and materially better image-dependent spatial behavior than the 256M baseline. A fluent list of shapes is insufficient.
""")
    write("metric_scoring.md", """# Metric scoring

## SmolVLM2-2.2B

| Control | Factual/spatial result | Hallucination / UNKNOWN | Classification |
|---|---|---|---|
| Coloured shapes | Recognized colours/shapes but called rectangle a square and omitted relations. | Appropriate UNKNOWN for absent architecture. | LIMITED |
| Property schematic | Caption reduced scene to house/tree; spatial prompt invented door and repeated circles to cap. Targeted prompt listed elements but no relations. | Material hallucination and no relationship reasoning. | FAIL |
| Multi-view | “The house is on the ground.” | Failed to distinguish views and did not use UNKNOWN. | FAIL |

## Qwen2.5-VL-3B

| Control | Factual/spatial result | Hallucination / UNKNOWN | Classification |
|---|---|---|---|
| Coloured shapes | Correctly identified all shapes and 2x2 layout. | Correctly stated absence of requested architectural elements. | PASS |
| Property schematic | Targeted output correctly found house/red roof, pool right, neighbour left, tree above, and boundary; it falsely denied visible road/driveway and described an extra roof. | No UNKNOWN where relationships were visually clear; material false negatives. | LIMITED |
| Multi-view | Collapsed two views into one and retained the pool despite its absence from the second. | Failed view-specific restraint/UNKNOWN. | FAIL |

Qwen is materially stronger than SmolVLM2 on single-image spatial recognition, but neither candidate meets the full E-L plus restraint threshold. Full raw outputs, timings, prompts, bindings, and per-call RSS are retained in `raw_outputs_*.json`.
""")
    write("selection_and_acceptance.md", """# Selection and acceptance decision

**Decision: no model is recommended for a subsequent application phase.**

Qwen2.5-VL-3B is the stronger tested candidate: it correctly recovered five of seven principal property-schematic elements and their relationships in its targeted response, while SmolVLM2 did not. However, Qwen missed the clearly visible road-to-driveway-to-house connection and failed the two-image comparison. SmolVLM2 also hallucinated a door and repeated output until the token cap. These failures are disqualifying under the predefined neutral acceptance threshold.

Both checkpoints are content-pinned to exact Hugging Face revisions. `checkpoint_manifests.json` records SHA-256 hashes of every locally downloaded snapshot file. No unavailable runtime/model is represented as tested. The next infrastructure step is to provision a maintained quantized llama.cpp or Ollama-compatible runtime and repeat this exact neutral benchmark with MiniCPM-V 4 or Gemma 4 on a host with at least 24 GiB RAM; do not use application imagery until a neutral pass exists.

## Scope assurance

This directory was generated solely from four local synthetic PNG controls. The runner contains no input discovery and reads no repository media directories. No PIE, blind, property, identity, address, erf, GIS, candidate, ranking, native imagery, ground truth, production, scoring, detector, PR27, or frozen artifacts were accessed or modified.
""")
    write("README.md", """# V4C stronger VLM selection benchmark

Reproduce with:

```powershell
python scripts\\run_vlm_selection_benchmark_v4c.py --model smolvlm2_2b --overwrite
python scripts\\run_vlm_selection_benchmark_v4c.py --model qwen25vl_3b --overwrite
python scripts\\emit_vlm_selection_evidence_v4c.py
python -m pytest -q tests\\test_vlm_selection_benchmark_v4c_schema.py
```

The benchmark creates only unlabelled synthetic controls, runs natural captions before targeted prompts, retains raw results, and records CPU/RSS/timing. It is deliberately separate from production and frozen work.
""")


if __name__ == "__main__":
    main()
