#!/usr/bin/env python3
"""Run the V4C neutral-only CPU VLM selection benchmark."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import time
from pathlib import Path
from typing import Any

import psutil
import torch
from PIL import Image, ImageDraw
from transformers import AutoModelForImageTextToText, AutoProcessor, __version__ as transformers_version


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "experiments" / "vlm_selection_benchmark_v4c"
MODELS = {
    "smolvlm2_2b": {
        "model_id": "HuggingFaceTB/SmolVLM2-2.2B-Instruct",
        "revision": "482adb537c021c86670beed01cd58990d01e72e4",
        "parameters": "2.2468B",
        "runtime": "Transformers CPU float32",
        "dtype": torch.float32,
        "multi_image_supported": True,
    },
    "qwen25vl_3b": {
        "model_id": "Qwen/Qwen2.5-VL-3B-Instruct",
        "revision": "66285546d2b821cf421d4f5eb2576359d3770cd3",
        "parameters": "3.7546B",
        "runtime": "Transformers CPU bfloat16",
        "dtype": torch.bfloat16,
        "multi_image_supported": True,
    },
}
PROMPTS = {
    "natural_caption": "Describe only what is visibly present in this image. Do not infer hidden details.",
    "spatial_inspection": (
        "Describe visible objects and their spatial relationships. State UNKNOWN when a requested "
        "relationship is not visible. Do not infer hidden details."
    ),
    "targeted_architecture": (
        "Inspect this diagram as a neutral scene. Say whether a road, driveway, house, pool, "
        "neighbour building, roof, tree, or boundary is visibly present, and describe only "
        "visible spatial relations. Use UNKNOWN for anything not visible."
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
    controls_dir = OUT / "controls"
    controls_dir.mkdir(parents=True, exist_ok=True)

    shapes = Image.new("RGB", (640, 400), "white")
    draw = ImageDraw.Draw(shapes)
    draw.rectangle((55, 60, 235, 190), fill="#d94841", outline="black", width=4)
    draw.ellipse((390, 80, 555, 245), fill="#2878d4", outline="black", width=4)
    draw.polygon([(100, 350), (200, 220), (300, 350)], fill="#e7b416", outline="black")
    draw.rectangle((390, 300, 590, 360), fill="#3b9f54", outline="black", width=4)
    shapes.save(controls_dir / "coloured_shapes.png")

    schematic = Image.new("RGB", (1000, 700), "#dff0d8")
    draw = ImageDraw.Draw(schematic)
    draw.rectangle((0, 520, 1000, 700), fill="#5c5c5c")
    draw.polygon([(445, 520), (555, 520), (620, 330), (500, 330)], fill="#c8b28b", outline="black")
    draw.rectangle((350, 185, 650, 370), fill="#c98755", outline="black", width=5)
    draw.polygon([(330, 185), (500, 70), (670, 185)], fill="#9f3c36", outline="black")
    draw.ellipse((690, 225, 900, 390), fill="#3c9ee5", outline="black", width=5)
    draw.rectangle((70, 165, 250, 350), fill="#b9b9b9", outline="black", width=5)
    draw.polygon([(50, 165), (160, 75), (270, 165)], fill="#4f6f91", outline="black")
    draw.ellipse((765, 65, 865, 165), fill="#397a3d", outline="black", width=4)
    draw.rectangle((300, 35, 935, 465), outline="#202020", width=4)
    schematic.save(controls_dir / "unlabelled_property_schematic.png")

    view_a = Image.new("RGB", (600, 400), "#dff0d8")
    draw = ImageDraw.Draw(view_a)
    draw.rectangle((0, 310, 600, 400), fill="#5c5c5c")
    draw.rectangle((190, 115, 410, 285), fill="#c98755", outline="black", width=4)
    draw.polygon([(170, 115), (300, 35), (430, 115)], fill="#9f3c36", outline="black")
    draw.ellipse((430, 155, 570, 275), fill="#3c9ee5", outline="black", width=4)
    view_a.save(controls_dir / "neutral_multiview_a.png")

    view_b = Image.new("RGB", (600, 400), "#dff0d8")
    draw = ImageDraw.Draw(view_b)
    draw.rectangle((0, 310, 600, 400), fill="#5c5c5c")
    draw.polygon([(265, 310), (335, 310), (390, 115), (300, 115)], fill="#c8b28b", outline="black")
    draw.rectangle((190, 115, 410, 285), fill="#c98755", outline="black", width=4)
    draw.polygon([(170, 115), (300, 35), (430, 115)], fill="#9f3c36", outline="black")
    view_b.save(controls_dir / "neutral_multiview_b.png")

    return [
        {"id": "coloured_shapes", "path": "controls/coloured_shapes.png", "truth": ["red rectangle", "blue circle right of red rectangle", "yellow triangle below red rectangle", "green rectangle below blue circle"]},
        {"id": "property_schematic", "path": "controls/unlabelled_property_schematic.png", "truth": ["road at bottom", "driveway connects road to house", "house with red roof", "pool right of house", "neighbour building left of house", "tree above pool", "boundary surrounds scene"]},
        {"id": "neutral_multiview", "path": "controls/neutral_multiview_a.png|controls/neutral_multiview_b.png", "truth": ["both views show house with red roof", "pool is visible only in first view", "driveway is visible only in second view", "road is at bottom in both views"]},
    ]


def messages_for(paths: list[Path], prompt: str) -> list[dict[str, Any]]:
    content = [{"type": "image", "path": str(path)} for path in paths]
    content.append({"type": "text", "text": prompt})
    return [{"role": "user", "content": content}]


def run_one(model: Any, processor: Any, paths: list[Path], prompt: str) -> dict[str, Any]:
    messages = messages_for(paths, prompt)
    rendered = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    images = [Image.open(path).convert("RGB") for path in paths]
    inputs = processor(text=rendered, images=images, return_tensors="pt").to("cpu")
    process = psutil.Process()
    before = process.memory_info().rss
    started = time.perf_counter()
    with torch.inference_mode():
        output = model.generate(**inputs, do_sample=False, num_beams=1, max_new_tokens=180)
    elapsed = time.perf_counter() - started
    after = process.memory_info().rss
    suffix = output[:, inputs["input_ids"].shape[1]:]
    return {
        "prompt": prompt,
        "image_paths": [str(path.relative_to(OUT)).replace("\\", "/") for path in paths],
        "message_image_bindings": len(paths),
        "raw_decoded_response": processor.batch_decode(suffix, skip_special_tokens=True)[0],
        "generated_tokens": int(suffix.shape[1]),
        "inference_seconds": elapsed,
        "rss_before_bytes": before,
        "rss_after_bytes": after,
    }


def score(response: str, truth: list[str]) -> dict[str, Any]:
    lowered = response.lower()
    concepts = {
        "red rectangle": ("red", "rectangle"),
        "blue circle right of red rectangle": ("blue", "circle", "right", "red", "rectangle"),
        "yellow triangle below red rectangle": ("yellow", "triangle", "below", "red", "rectangle"),
        "green rectangle below blue circle": ("green", "rectangle", "below", "blue", "circle"),
        "road at bottom": ("road", "bottom"),
        "driveway connects road to house": ("driveway", "road", "house", "connect"),
        "house with red roof": ("house", "roof", "red"),
        "pool right of house": ("pool", "right", "house"),
        "neighbour building left of house": ("neighbour", "building", "left", "house"),
        "tree above pool": ("tree", "above", "pool"),
        "boundary surrounds scene": ("boundary", "surround"),
        "both views show house with red roof": ("both", "house", "roof", "red"),
        "pool is visible only in first view": ("pool", "only", "first"),
        "driveway is visible only in second view": ("driveway", "only", "second"),
        "road is at bottom in both views": ("road", "bottom", "both"),
    }
    matched = [fact for fact in truth if all(word in lowered for word in concepts[fact])]
    unknown = "unknown" in lowered
    hallucination_terms = ("bedroom", "person", "car", "window", "door", "fence")
    hallucinations = [term for term in hallucination_terms if term in lowered]
    return {
        "matched_truth": matched,
        "truth_count": len(truth),
        "factual_score": len(matched),
        "unknown_used": unknown,
        "hallucination_terms": hallucinations,
        "hallucination_count": len(hallucinations),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=MODELS, required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if OUT.exists() and not args.overwrite:
        raise RuntimeError(f"refusing to overwrite evidence: {OUT}; use --overwrite only for the same controlled benchmark")
    OUT.mkdir(parents=True, exist_ok=True)
    controls = create_controls()
    config = MODELS[args.model]
    started = time.perf_counter()
    model = AutoModelForImageTextToText.from_pretrained(
        config["model_id"], revision=config["revision"], dtype=config["dtype"]
    ).eval()
    processor = AutoProcessor.from_pretrained(config["model_id"], revision=config["revision"])
    results = []
    for control in controls:
        paths = [OUT / item for item in control["path"].split("|")]
        for prompt_id, prompt in PROMPTS.items():
            if len(paths) > 1 and prompt_id != "spatial_inspection":
                continue
            record = run_one(model, processor, paths, prompt)
            record.update({"model_key": args.model, "control_id": control["id"], "prompt_id": prompt_id})
            record["score"] = score(record["raw_decoded_response"], control["truth"])
            results.append(record)
    write_json("neutral_controls_and_truth_rubric.json", controls)
    write_json(f"raw_outputs_{args.model}.json", results)
    write_json(f"runtime_{args.model}.json", {
        **config,
        "device": "cpu",
        "dtype": str(config["dtype"]).replace("torch.", ""),
        "python": platform.python_version(),
        "torch": torch.__version__,
        "transformers": transformers_version,
        "model_load_seconds": time.perf_counter() - started,
        "model_files": [{"path": str(path), "sha256": digest(path)} for path in (OUT / "controls").glob("*.png")],
        "free_disk_bytes_after": shutil.disk_usage(ROOT).free,
    })


if __name__ == "__main__":
    main()
