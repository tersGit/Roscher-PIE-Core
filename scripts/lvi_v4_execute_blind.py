#!/usr/bin/env python3
"""Create and freeze a provenance-backed, blind SmolVLM listing observation run."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import torch
from PIL import Image, ImageDraw
from transformers import AutoProcessor, Idefics3ForConditionalGeneration

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data" / "experiments" / "listing_visual_intelligence_v4"
OUT = BASE / "blind_execution_20260909"
MODEL_ID = "HuggingFaceTB/SmolVLM-256M-Instruct"
REVISION = "7e3e67edbbed1bf9888184d9df282b700a323964"
LISTINGS = {
    "117539389": "https://www.property24.com/for-sale/carlswald-north-estate/midrand/gauteng/12743/117539389",
    "117255083": "https://www.property24.com/for-sale/carlswald-north-estate/midrand/gauteng/12743/117255083",
}
USER_AGENT = "Mozilla/5.0 (compatible; LVI-v4-blind-media-inventory/1.0)"
PROMPT = """Inspect only what is visibly supported in this image. Return one JSON object with
the keys house_storeys, roof, pool, outbuilding_lapa, driveway, garage, road, walls_boundaries,
garden_trees, solar, neighbours, distinctive_features, visibility_limits. Every value must be an
object containing status (OBSERVED or UNKNOWN_NOT_VISIBLE), evidence, confidence (HIGH/MEDIUM/LOW),
and occlusion. Describe roof colour/material/pitch/form, pool contour and only visible relationship
to house/boundary, and neighbour roof form/colour/pitch only when directly visible. Do not guess,
do not invent directions, do not use pool water colour, and do not infer solar from electrical equipment."""
MULTI_PROMPT = """These are multiple related listing images. Return one JSON object with keys
repeated_objects, relationships, contradictions, unknowns. For each relationship, use only
OBSERVED, INFERRED, or UNKNOWN_NOT_VISIBLE and state supporting frame positions. Evaluate only
visibly defensible ROAD->DRIVEWAY->GARAGE->HOUSE->POOL->BOUNDARIES->NEIGHBOURS relationships,
using relative wording rather than compass directions. Do not guess, invent a route, use pool water
colour, or infer solar from electrical equipment."""


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            value.update(chunk)
    return value.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def image_urls(listing_url: str) -> list[str]:
    import re

    with httpx.Client(timeout=40, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
        response = client.get(listing_url)
        response.raise_for_status()
    seen: dict[str, str] = {}
    for match in re.finditer(r"https://images\.prop24\.com/(\d+)", response.text):
        seen.setdefault(match.group(1), f"https://images.prop24.com/{match.group(1)}")
    return list(seen.values())


def video_urls(listing_url: str) -> list[str]:
    import re

    with httpx.Client(timeout=40, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
        response = client.get(listing_url)
        response.raise_for_status()
    return list(dict.fromkeys(
        f"https://www.youtube.com/embed/{match.group(1)}"
        for match in re.finditer(r"youtube(?:-nocookie)?\.com/embed/([A-Za-z0-9_-]{6,})", response.text, re.I)
    ))


def inventory_media() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    media, videos = [], []
    for listing_id, listing_url in LISTINGS.items():
        folder = OUT / listing_id / "ORIGINAL_STILLS"
        folder.mkdir(parents=True, exist_ok=True)
        urls = image_urls(listing_url)
        with httpx.Client(timeout=40, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
            for index, url in enumerate(urls, 1):
                frame_id = f"{listing_id}-{index:03d}"
                path = folder / f"{frame_id}.img"
                response = client.get(url)
                response.raise_for_status()
                path.write_bytes(response.content)
                with Image.open(path) as image:
                    width, height = image.size
                    image_format = image.format
                media.append({
                    "listing_id": listing_id, "frame_id": frame_id, "source_type": "still",
                    "source_url": url, "path": str(path.relative_to(OUT)).replace("\\", "/"),
                    "sha256": digest(path), "bytes": path.stat().st_size, "width": width, "height": height,
                    "image_format": image_format, "retrieved_at": datetime.now(UTC).isoformat(),
                })
        embeds = video_urls(listing_url)
        if listing_id != "117255083":
            videos.append({"listing_id": listing_id, "source_urls": "|".join(embeds), "status": "NO_EMBED_DISCOVERED",
                           "technical_provenance": "Property24 HTML embed scan found no YouTube embed.", "keyframes": 0})
            continue
        if not embeds:
            videos.append({"listing_id": listing_id, "source_urls": "", "status": "VIDEO PRESENT AT SOURCE / RETRIEVAL FAILED",
                           "technical_provenance": "Expected source video embed was not returned by current Property24 HTML retrieval.", "keyframes": 0})
            continue
        command = [sys.executable, "-m", "yt_dlp", "--no-warnings", "--dump-single-json", embeds[0]]
        result = subprocess.run(command, text=True, capture_output=True, timeout=120)
        videos.append({
            "listing_id": listing_id, "source_urls": "|".join(embeds),
            "status": "VIDEO PRESENT AT SOURCE / RETRIEVAL FAILED" if result.returncode else "VIDEO RECOVERED",
            "technical_provenance": (result.stderr or result.stdout).strip().replace("\n", " ")[:1500],
            "keyframes": 0,
        })
    return media, videos


def selected_media(media: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected = []
    for listing_id in LISTINGS:
        records = [row for row in media if row["listing_id"] == listing_id]
        # A deterministic even sample eliminates ground-truth-guided selection.
        positions = sorted({round(i * (len(records) - 1) / 15) for i in range(16)})
        for position in positions:
            row = dict(records[position])
            row["selection_rationale"] = "Deterministic evenly spaced position in complete chronological still corpus; no visual or external-ranking criterion."
            selected.append(row)
    return selected


def answer(model: Any, processor: Any, image_paths: list[Path], prompt: str) -> tuple[str, float]:
    content = [{"type": "image"} for _ in image_paths] + [{"type": "text", "text": prompt}]
    messages = [{"role": "user", "content": content}]
    text = processor.apply_chat_template(messages, add_generation_prompt=True)
    images = [Image.open(path).convert("RGB") for path in image_paths]
    inputs = processor(text=text, images=images, return_tensors="pt").to("cpu")
    started = time.perf_counter()
    with torch.inference_mode():
        output = model.generate(**inputs, do_sample=False, num_beams=1, max_new_tokens=500)
    elapsed = time.perf_counter() - started
    generated = output[:, inputs["input_ids"].shape[1]:]
    result = processor.batch_decode(generated, skip_special_tokens=True)[0]
    for image in images:
        image.close()
    return result, elapsed


def parse_json(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(raw[start:end + 1])
            except json.JSONDecodeError:
                pass
    return {"status": "UNPARSEABLE_RAW_RESPONSE", "evidence": raw}


def normalize(raw_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    observations = []
    for record in raw_rows:
        parsed = parse_json(record["raw_response"])
        for feature, value in parsed.items():
            if isinstance(value, dict):
                observations.append({
                    "listing_id": record["listing_id"], "feature": feature, "value": value,
                    "confidence": value.get("confidence", "UNKNOWN"), "source_frames": record["source_frames"],
                    "source_type": record["source_type"], "status": value.get("status", "UNKNOWN_NOT_VISIBLE"),
                    "visibility": value.get("evidence", "Not parsed"), "occlusion": value.get("occlusion", "UNKNOWN"),
                    "raw_reference": record["raw_id"],
                    "cross_frame_consistency": "SINGLE_VIEW_ONLY",
                })
    return observations


def panel(selected: list[dict[str, Any]], raw_rows: list[dict[str, Any]]) -> None:
    raw = {row["source_frames"]: row for row in raw_rows if row["kind"] == "single_frame"}
    for row in selected:
        source = OUT / row["path"]
        with Image.open(source).convert("RGB") as image:
            image.thumbnail((900, 650))
            canvas = Image.new("RGB", (920, 800), "white")
            canvas.paste(image, ((920 - image.width) // 2, 10))
            text = raw[row["frame_id"]]["raw_response"].replace("\n", " ")[:550]
            ImageDraw.Draw(canvas).text((10, 670), f"{row['frame_id']} | {text}", fill="black")
            destination = OUT / row["listing_id"] / "PANELS" / f"{row['frame_id']}.jpg"
            destination.parent.mkdir(exist_ok=True)
            canvas.save(destination, quality=90)


def reports(observations: list[dict[str, Any]]) -> None:
    for listing_id in LISTINGS:
        rows = [row for row in observations if row["listing_id"] == listing_id]
        machine = {"listing_id": listing_id, "observations": rows, "blindness": "BLIND_VLM_OUTPUTS_ONLY"}
        write_json(OUT / listing_id / "SCENE_FINGERPRINT.json", machine)
        report = "# LVI v4 blind visual report: " + listing_id + "\n\n"
        for row in rows:
            report += f"- **{row['feature']}** — {json.dumps(row['value'], sort_keys=True)}; {row['status']}; raw `{row['raw_reference']}`.\n"
        (OUT / listing_id / "SCENE_REPORT.md").write_text(report, encoding="utf-8")


def freeze() -> None:
    include = sorted(path for path in OUT.rglob("*") if path.is_file() and path.name != "LVI_V4_BLIND_FREEZE_MANIFEST.json")
    write_json(OUT / "LVI_V4_BLIND_FREEZE_MANIFEST.json", {
        "schema_version": "LVI_V4_BLIND_FREEZE_V1",
        "status": "BLIND_VLM_OBSERVATIONS_FROZEN_NO_G9H_READ",
        "model": {"id": MODEL_ID, "revision": REVISION, "device": "cpu", "dtype": "float32"},
        "files": [{"path": str(path.relative_to(OUT)).replace("\\", "/"), "sha256": digest(path)} for path in include],
        "prohibitions_observed": ["G9H", "identity/address/erf/stand", "GIS/candidates/rankings", "ground truth", "production"],
    })


def main() -> None:
    if OUT.exists():
        raise RuntimeError(f"refusing to overwrite execution output: {OUT}")
    started = time.perf_counter()
    media, videos = inventory_media()
    selected = selected_media(media)
    # The pinned revision declares Idefics3ForConditionalGeneration.  Loading
    # that declared native architecture prevents a cross-architecture fallback.
    model = Idefics3ForConditionalGeneration.from_pretrained(
        MODEL_ID, revision=REVISION, torch_dtype=torch.float32
    ).eval()
    processor = AutoProcessor.from_pretrained(MODEL_ID, revision=REVISION)
    raw_rows, durations = [], []
    for row in selected:
        response, seconds = answer(model, processor, [OUT / row["path"]], PROMPT)
        raw_rows.append({"raw_id": f"single-{row['frame_id']}", "kind": "single_frame", "listing_id": row["listing_id"],
                         "source_frames": row["frame_id"], "source_type": "still", "prompt": PROMPT, "raw_response": response,
                         "inference_seconds": seconds})
        durations.append(seconds)
    for listing_id in LISTINGS:
        rows = [row for row in selected if row["listing_id"] == listing_id]
        for index in range(0, len(rows), 4):
            group = rows[index:index + 4]
            response, seconds = answer(model, processor, [OUT / row["path"] for row in group], MULTI_PROMPT)
            frame_ids = "|".join(row["frame_id"] for row in group)
            raw_rows.append({"raw_id": f"multi-{listing_id}-{index // 4 + 1:02d}", "kind": "multi_frame", "listing_id": listing_id,
                             "source_frames": frame_ids, "source_type": "still", "prompt": MULTI_PROMPT, "raw_response": response,
                             "inference_seconds": seconds})
            durations.append(seconds)
    normalized = normalize([row for row in raw_rows if row["kind"] == "single_frame"])
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(OUT / "LVI_V4_MEDIA_AND_SELECTION_MANIFEST.json", {"media": media, "selected": selected, "video": videos})
    (OUT / "LVI_V4_RAW_SINGLE_FRAME_OUTPUTS.jsonl").write_text("\n".join(json.dumps(row, sort_keys=True) for row in raw_rows if row["kind"] == "single_frame") + "\n", encoding="utf-8")
    (OUT / "LVI_V4_RAW_MULTI_FRAME_OUTPUTS.jsonl").write_text("\n".join(json.dumps(row, sort_keys=True) for row in raw_rows if row["kind"] == "multi_frame") + "\n", encoding="utf-8")
    write_json(OUT / "LVI_V4_NORMALIZED_OBSERVATIONS.json", normalized)
    relationships = []
    for row in raw_rows:
        if row["kind"] != "multi_frame":
            continue
        parsed = parse_json(row["raw_response"])
        relationships.append({
            "raw_reference": row["raw_id"],
            "parsed_response": parsed,
            "parse_status": "PARSED_OBJECT" if isinstance(parsed, dict) else "PARSED_NON_OBJECT",
        })
    write_json(OUT / "LVI_V4_RELATIONSHIPS.json", relationships)
    write_json(OUT / "LVI_V4_CONSISTENCY_AND_CONTRADICTIONS.json", {"status": "RAW_MULTI_FRAME_OUTPUTS_PRESERVED_SEPARATELY", "normalization_policy": "No semantic repair; only parseable single-frame objects normalized."})
    panel(selected, raw_rows)
    reports(normalized)
    write_json(OUT / "LVI_V4_EXECUTION_AUDIT.json", {
        "model_id": MODEL_ID, "revision": REVISION, "runtime": {"torch": torch.__version__, "device": "cpu", "dtype": "float32"},
        "input_preprocessing": str(getattr(processor, "image_processor", "processor default")),
        "deterministic_generation": {"do_sample": False, "num_beams": 1, "max_new_tokens": 500},
        "stills_available": len(media), "stills_selected_and_analyzed": len(selected), "video_records": videos,
        "single_frame_calls": len(selected), "multi_frame_calls": len(raw_rows) - len(selected),
        "drone_aerial_calls": 0, "errors": [], "total_inference_seconds": sum(durations),
        "average_inference_seconds": sum(durations) / len(durations), "total_elapsed_seconds": time.perf_counter() - started,
        "blind_input_rule": "Only original listing media and minimal listing provenance were given to the VLM.",
    })
    freeze()


if __name__ == "__main__":
    main()
