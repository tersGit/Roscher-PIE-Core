#!/usr/bin/env python3
"""Run neutral-only diagnostics for the frozen LVI v4 SmolVLM invocation."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import time
from pathlib import Path
from typing import Any

import psutil
import torch
from PIL import Image, ImageDraw
from transformers import AutoProcessor, Idefics3ForConditionalGeneration, __version__ as transformers_version


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "experiments" / "vlm_output_failure_analysis_v4b"
MODEL_ID = "HuggingFaceTB/SmolVLM-256M-Instruct"
REVISION = "7e3e67edbbed1bf9888184d9df282b700a323964"
FROZEN_RAW = ROOT / "data" / "experiments" / "listing_visual_intelligence_v4" / "blind_execution_20260909"

PROMPTS = {
    "free_detail_caption": "Describe this image in detail. State only visible facts in complete sentences.",
    "structured_visual_inspection": (
        "Inspect this image carefully. Write a detailed visual inspection in complete sentences. "
        "Cover objects, colors, shapes, and their visible positions. Do not use JSON."
    ),
    "spatial_relations": (
        "Describe the visible spatial relationships in this image in complete sentences. "
        "Name what is in front of, beside, behind, connected to, or near other visible objects."
    ),
    "feature_value_evidence": (
        "List visible facts using exactly one line per fact in this non-JSON form: "
        "FEATURE | VALUE | EVIDENCE. Include several facts."
    ),
}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            value.update(chunk)
    return value.hexdigest()


def write_json(name: str, value: Any) -> None:
    (OUT / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def create_controls() -> list[dict[str, Any]]:
    controls = OUT / "controls"
    controls.mkdir(parents=True)

    geometry = Image.new("RGB", (800, 500), "white")
    draw = ImageDraw.Draw(geometry)
    draw.rectangle((60, 70, 280, 220), fill="#d94841", outline="black", width=4)
    draw.ellipse((490, 100, 680, 290), fill="#2878d4", outline="black", width=4)
    draw.polygon([(120, 390), (240, 280), (360, 390)], fill="#e7b416", outline="black")
    draw.rectangle((480, 350, 710, 420), fill="#3b9f54", outline="black", width=4)
    draw.text((60, 20), "Synthetic geometric control", fill="black")
    geometry_path = controls / "basic_geometric_scene.png"
    geometry.save(geometry_path)

    layout = Image.new("RGB", (1000, 700), "#dff0d8")
    draw = ImageDraw.Draw(layout)
    draw.rectangle((0, 500, 1000, 700), fill="#5c5c5c")
    draw.text((440, 610), "ROAD", fill="white")
    draw.polygon([(440, 500), (560, 500), (620, 310), (500, 310)], fill="#c8b28b", outline="black")
    draw.rectangle((350, 170, 650, 350), fill="#c98755", outline="black", width=5)
    draw.polygon([(330, 170), (500, 65), (670, 170)], fill="#9f3c36", outline="black")
    draw.ellipse((680, 220, 890, 380), fill="#3c9ee5", outline="black", width=5)
    draw.rectangle((70, 155, 250, 335), fill="#b9b9b9", outline="black", width=5)
    draw.polygon([(50, 155), (160, 70), (270, 155)], fill="#4f6f91", outline="black")
    draw.text((415, 245), "HOUSE", fill="black")
    draw.text((725, 290), "POOL", fill="white")
    draw.text((95, 235), "NEIGHBOUR", fill="black")
    draw.text((455, 410), "DRIVEWAY", fill="black")
    layout_path = controls / "road_driveway_house_pool_neighbour_layout.png"
    layout.save(layout_path)

    return [
        {
            "id": "basic_geometric_scene",
            "path": str(geometry_path.relative_to(OUT)).replace("\\", "/"),
            "provenance": "Generated locally by this script; no PIE/listing source.",
            "expected_visible_facts": ["red rectangle", "blue circle", "yellow triangle", "green rectangle"],
        },
        {
            "id": "layout_scene",
            "path": str(layout_path.relative_to(OUT)).replace("\\", "/"),
            "provenance": "Generated locally by this script; no PIE/listing source.",
            "expected_visible_facts": [
                "road at the front/bottom",
                "driveway connects road to house",
                "pool beside the house",
                "neighbour placed left of house",
            ],
        },
    ]


def inference(
    model: Any, processor: Any, image_path: Path, prompt: str, generation: dict[str, Any]
) -> dict[str, Any]:
    messages = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": prompt}]}]
    rendered = processor.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)
    with Image.open(image_path) as source:
        image = source.convert("RGB")
    inputs = processor(text=rendered, images=[image], return_tensors="pt").to("cpu")
    started = time.perf_counter()
    process = psutil.Process()
    memory_before = process.memory_info().rss
    with torch.inference_mode():
        output = model.generate(**inputs, return_dict_in_generate=True, **generation)
    elapsed = time.perf_counter() - started
    memory_after = process.memory_info().rss
    generated = output.sequences[:, inputs["input_ids"].shape[1]:]
    generated_ids = generated[0].tolist()
    decoded = processor.batch_decode(generated, skip_special_tokens=True)[0]
    eos_ids = model.generation_config.eos_token_id
    eos_set = {eos_ids} if isinstance(eos_ids, int) else set(eos_ids or [])
    return {
        "rendered_chat_template": rendered,
        "message_image_bindings": 1,
        "input_ids_length": int(inputs["input_ids"].shape[1]),
        "pixel_values_shape": list(inputs["pixel_values"].shape),
        "generation": generation,
        "raw_generated_token_ids": generated_ids,
        "raw_decoded_response": decoded,
        "generated_tokens": len(generated_ids),
        "ended_with_configured_eos": bool(generated_ids and generated_ids[-1] in eos_set),
        "configured_eos_token_ids": sorted(eos_set),
        "inference_seconds": elapsed,
        "process_rss_bytes_before": memory_before,
        "process_rss_bytes_after": memory_after,
    }


def old_raw_references() -> list[dict[str, Any]]:
    result = []
    for filename in ("LVI_V4_RAW_SINGLE_FRAME_OUTPUTS.jsonl", "LVI_V4_RAW_MULTI_FRAME_OUTPUTS.jsonl"):
        path = FROZEN_RAW / filename
        lines = path.read_text(encoding="utf-8").splitlines()
        result.append({
            "frozen_path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "sha256": digest(path),
            "record_count": len(lines),
            "representative_raw_records": [json.loads(line) for line in lines[:3]],
        })
    return result


def main() -> None:
    if OUT.exists():
        raise RuntimeError(f"refusing to overwrite V4B evidence: {OUT}")
    OUT.mkdir(parents=True)
    controls = create_controls()
    write_json("frozen_raw_forensic_references.json", old_raw_references())

    model = Idefics3ForConditionalGeneration.from_pretrained(
        MODEL_ID, revision=REVISION, torch_dtype=torch.float32
    ).eval()
    processor = AutoProcessor.from_pretrained(MODEL_ID, revision=REVISION)
    default_generation = {"do_sample": False, "num_beams": 1, "max_new_tokens": 192}
    corrected_generation = {
        "do_sample": False, "num_beams": 1, "max_new_tokens": 192, "min_new_tokens": 48,
        "repetition_penalty": 1.05,
    }
    results = []
    for control in controls:
        for prompt_id, prompt in PROMPTS.items():
            generation = corrected_generation if prompt_id == "free_detail_caption" else default_generation
            record = inference(model, processor, OUT / control["path"], prompt, generation)
            record.update({"control_id": control["id"], "prompt_id": prompt_id, "prompt": prompt})
            results.append(record)
    write_json("neutral_controls.json", controls)
    write_json("raw_neutral_generation_results.json", results)
    write_json("runtime_provenance.json", {
        "model_id": MODEL_ID, "revision": REVISION, "model_class": type(model).__name__,
        "processor_class": type(processor).__name__,
        "image_processor_class": type(processor.image_processor).__name__,
        "transformers": transformers_version, "torch": torch.__version__,
        "device": "cpu", "dtype": "float32", "python": platform.python_version(),
        "platform": platform.platform(), "pid": os.getpid(),
        "processor_image_preprocessing": str(processor.image_processor),
        "checkpoint_generation_config": model.generation_config.to_dict(),
    })


if __name__ == "__main__":
    main()
