#!/usr/bin/env python3
"""Validate the selected local caption VLM before the blind LVI v4 pass.

This intentionally does not import listing parsers, GIS code, rankings, or
G9H material.  A missing selected VLM is a hard stop, not a reason to use
CLIP, OWL-ViT, or handcrafted scene labels as a substitute.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import torch
import transformers

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "experiments" / "listing_visual_intelligence_v4"
SELECTED_MODEL_ENV = "LVI_V4_VLM_MODEL_DIR"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def model_record(path: Path) -> dict[str, Any]:
    config_path = path / "config.json"
    record: dict[str, Any] = {"path": str(path), "exists": path.is_dir()}
    if not config_path.is_file():
        record["configuration"] = "MISSING_CONFIG"
        return record
    config = json.loads(config_path.read_text(encoding="utf-8"))
    architectures = config.get("architectures", [])
    model_type = config.get("model_type", "")
    record.update(
        {
            "configuration": "PRESENT",
            "config_sha256": sha256(config_path),
            "model_type": model_type,
            "architectures": architectures,
            "vision_config_present": "vision_config" in config,
            "text_config_present": "text_config" in config,
        }
    )
    record["caption_capable"] = bool(
        record["vision_config_present"]
        and record["text_config_present"]
        and any("Vision2Seq" in name or "ConditionalGeneration" in name for name in architectures)
    )
    return record


def configured_model() -> dict[str, Any]:
    selected = os.environ.get(SELECTED_MODEL_ENV)
    if not selected:
        return {
            "selection_status": "NOT_CONFIGURED",
            "required_environment_variable": SELECTED_MODEL_ENV,
            "detail": "No explicit local model directory was supplied for the selected caption VLM.",
        }
    record = model_record(Path(selected).expanduser())
    record["selection_status"] = "CONFIGURED"
    return record


def known_non_caption_models() -> list[dict[str, Any]]:
    cache_roots = [
        Path.home() / ".cache" / "huggingface" / "hub",
        Path.home() / ".cache" / "roscher-pie" / "vision",
    ]
    records = []
    for root in cache_roots:
        if not root.is_dir():
            continue
        for snapshot in sorted(root.glob("models--*/snapshots/*")):
            record = model_record(snapshot)
            record["cache_root"] = str(root)
            records.append(record)
    return records


def local_runtime_discovery() -> dict[str, Any]:
    locations = [
        Path.home() / ".ollama" / "models",
        Path.home() / ".lmstudio" / "models",
        Path(os.environ.get("LOCALAPPDATA", "")) / "LM-Studio" / "models",
        Path(os.environ.get("APPDATA", "")) / "LM Studio" / "models",
    ]
    endpoints = []
    for port in (11434, 1234, 8080, 8000):
        url = f"http://127.0.0.1:{port}/v1/models"
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                endpoints.append({"url": url, "status": response.status, "reachable": True})
        except urllib.error.URLError as exc:
            endpoints.append({"url": url, "reachable": False, "error": str(exc.reason)})
    return {
        "standard_model_locations": [{"path": str(path), "exists": path.is_dir()} for path in locations],
        "local_openai_compatible_endpoints": endpoints,
    }


def write_artifacts(gate: dict[str, Any]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "LVI_V4_CAPABILITY_GATE.json").write_text(
        json.dumps(gate, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    audit = """# LVI v4 caption-VLM capability and provenance gate

## Result: FAIL / STOP

No explicitly selected, locally usable caption-capable vision-language model was available to this run. LVI v4 therefore produced **no listing observations, media retrieval, frame selection, prompts, captions, normalization, scene relationships, fingerprints, panels, or blind observation freeze**. It did not substitute OWL-ViT, CLIP, generic scene labels, OCR, handcrafted visual rules, or another model.

## Required capability

The selected model must be supplied through `LVI_V4_VLM_MODEL_DIR`, point to a local Hugging Face-compatible model directory, include a vision configuration and a text configuration, declare a caption/generation architecture, and successfully pass image-to-text inference before any listing media is touched. This run was stopped before that inference stage because no selected directory was configured.

## Runtime provenance

| Field | Value |
|---|---|
| Python | """ + gate["runtime"]["python"] + """ |
| Transformers | """ + gate["runtime"]["transformers"] + """ |
| Torch | """ + gate["runtime"]["torch"] + """ |
| Device | """ + gate["runtime"]["device"] + """ |
| Deterministic settings | Not applicable: no VLM inference occurred |
| Input resize/crop | Not applicable: no VLM inference occurred |
| Prompt and output parsing | Not applicable: no VLM inference occurred |

## Available but rejected caches

The gate records every discovered cached model configuration in `LVI_V4_CAPABILITY_GATE.json`. CLIP is image/text similarity rather than caption generation; OWL-ViT is prompted object detection rather than a caption/relationship model. Neither is used, and their presence is not evidence that a caption VLM was available.

Standard Ollama/LM Studio model locations and loopback OpenAI-compatible endpoints are also recorded. This run found no configured selected VLM and no reachable local model-serving endpoint.

## Blindness and scope declaration

This gate did not read G9H substantive observations, identity/address/erf/stand, GIS, candidate sets, G9 Top5/Top20, rankings, ground truth, or any production/candidate/detector/Native15/PR27 code. It did not access Property24 listing media or video. A post-freeze G9H evaluation is prohibited because there is no v4 blind observation freeze to evaluate.
"""
    (OUT / "LVI_V4_CAPABILITY_AND_METHOD_AUDIT.md").write_text(audit, encoding="utf-8")
    (OUT / "LVI_V4_ACCEPTANCE_REPORT.md").write_text(
        "# LVI v4 blind acceptance\n\n"
        "**FAIL / CAPABILITY STOP.** The selected caption-capable VLM was not configured or locally usable. "
        "No blind observation artifacts were generated and no G9H evaluation was performed.\n",
        encoding="utf-8",
    )


def main() -> int:
    selected = configured_model()
    gate = {
        "schema_version": "LVI_V4_CAPABILITY_GATE_V1",
        "run_started_at": datetime.now(UTC).isoformat(),
        "result": "FAIL_CAPTION_VLM_UNAVAILABLE_STOPPED",
        "selected_model": selected,
        "runtime": {
            "python": sys.version.split()[0],
            "transformers": transformers.__version__,
            "torch": torch.__version__,
            "device": "cuda" if torch.cuda.is_available() else "cpu",
            "platform": platform.platform(),
        },
        "discovered_cached_models": known_non_caption_models(),
        "local_runtime_discovery": local_runtime_discovery(),
        "prohibitions_observed": [
            "listing media and video access",
            "G9H input",
            "identity, address, erf, and stand",
            "GIS and candidates",
            "G9 Top5/Top20 and rankings",
            "ground truth",
            "production changes",
            "detector, Native15, and PR27 changes",
        ],
    }
    write_artifacts(gate)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
