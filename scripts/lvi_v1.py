"""Listing Visual Intelligence v1 generic, blind media extraction.

The extractor deliberately uses only listing HTML/media and deterministic image
measurements. It does not know candidate, GIS, or prior human-review labels.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import shutil
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageStat

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.parsers.property24 import ListingData, download_images, fetch_listing

OUT = ROOT / "data" / "experiments" / "listing_visual_intelligence_v1"
LISTINGS = {
    "117539389": "https://www.property24.com/for-sale/carlswald-north-estate/midrand/gauteng/12743/117539389",
    "117255083": "https://www.property24.com/for-sale/carlswald-north-estate/midrand/gauteng/12743/117255083",
}

FRAME_FIELDS = [
    "listing_id", "frame_id", "media_type", "source_url", "sha256",
    "width", "height", "scene_labels", "structure_labels", "analysis_method",
    "confidence",
]
OBS_FIELDS = [
    "listing_id", "observation_id", "subject", "feature", "value",
    "confidence", "provenance", "frame_ids", "notes",
]
REL_FIELDS = [
    "listing_id", "relationship_id", "from_observation", "relation",
    "to_observation", "confidence", "provenance", "frame_ids", "notes",
]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _text_evidence(listing: ListingData) -> list[dict[str, Any]]:
    text = listing.description or ""
    terms = {
        "pool": r"\bpool|swimming pool\b",
        "patio": r"\bpatio\b",
        "solar": r"\bsolar|solar panels|pv|photovoltaic\b",
        "backup_power": r"\binverter|battery|backup power|ups\b",
    }
    evidence = []
    for feature, pattern in terms.items():
        if re.search(pattern, text, re.I):
            evidence.append(
                {
                    "feature": feature,
                    "value": "YES",
                    "confidence": "MEDIUM",
                    "provenance": "LISTING_TEXT",
                    "excerpt": text[:240],
                }
            )
    return evidence


def _image_metrics(image: Image.Image) -> dict[str, float]:
    rgb = image.convert("RGB").resize((80, 80))
    pixels = list(rgb.getdata())
    green = sum(1 for r, g, b in pixels if g > r * 1.08 and g > b * 1.08) / len(pixels)
    cyan = sum(1 for r, g, b in pixels if b > r * 1.18 and g > g * 0.95 and g > r * 1.12) / len(pixels)
    dark = sum(1 for r, g, b in pixels if max(r, g, b) < 95) / len(pixels)
    bright = sum(1 for r, g, b in pixels if min(r, g, b) > 165) / len(pixels)
    upper = ImageStat.Stat(rgb.crop((0, 0, 80, 35))).mean
    lower = ImageStat.Stat(rgb.crop((0, 42, 80, 80))).mean
    return {
        "green_fraction": round(green, 4),
        "cyan_fraction": round(cyan, 4),
        "dark_fraction": round(dark, 4),
        "bright_fraction": round(bright, 4),
        "upper_luma": round(sum(upper) / 3, 2),
        "lower_luma": round(sum(lower) / 3, 2),
    }


def _classify(metrics: dict[str, float], width: int, height: int) -> tuple[list[str], str]:
    labels: list[str] = ["OTHER"]
    if metrics["green_fraction"] > 0.16:
        labels += ["GARDEN"]
    if metrics["cyan_fraction"] > 0.035:
        labels += ["POOL"]
    if metrics["dark_fraction"] > 0.18 and metrics["upper_luma"] < metrics["lower_luma"] * 0.92:
        labels += ["ROOF_VISIBLE", "HOUSE_EXTERIOR"]
    if metrics["bright_fraction"] > 0.25 and metrics["lower_luma"] > 125:
        labels += ["INTERIOR"]
    if metrics["green_fraction"] > 0.08 and metrics["cyan_fraction"] > 0.02:
        labels += ["POOL_AND_HOUSE"]
    if width / max(height, 1) > 1.6:
        labels += ["AERIAL_VIEW"]
    return list(dict.fromkeys(labels)), "deterministic_rgb_layout_heuristics"


def _confidence(value: bool) -> str:
    return "MEDIUM" if value else "LOW"


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fields} for row in rows)


def _contact_sheet(listing_id: str, frames: list[dict[str, Any]], images: dict[str, Image.Image]) -> None:
    destination = OUT / listing_id / "EVIDENCE_CONTACT_SHEETS"
    destination.mkdir(parents=True, exist_ok=True)
    page_size = 12
    for page, start in enumerate(range(0, len(frames), page_size), start=1):
        subset = frames[start : start + page_size]
        sheet = Image.new("RGB", (960, math.ceil(len(subset) / 4) * 190), "white")
        draw = ImageDraw.Draw(sheet)
        for index, frame in enumerate(subset):
            image = images[frame["frame_id"]].copy()
            image.thumbnail((225, 145))
            x = (index % 4) * 240 + 7
            y = (index // 4) * 190 + 5
            sheet.paste(image, (x, y))
            label = f"{listing_id} {frame['frame_id']} | {frame['scene_labels']} | {frame['confidence']}"
            draw.text((x, y + 150), label[:55], fill="black")
        sheet.save(destination / f"CONTACT_SHEET_{page:02d}.jpg", quality=88)


def extract_listing(listing_id: str, url: str, cache_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    listing = fetch_listing(url, listing_id)
    cache = cache_root / listing_id
    bodies = download_images(listing.image_urls, cache, listing_id)
    frames: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    relationships: list[dict[str, Any]] = []
    images: dict[str, Image.Image] = {}
    for index, (frame_id, body) in enumerate(bodies.items(), start=1):
        with Image.open(cache / f"{frame_id}.jpg") as source:
            image = source.convert("RGB")
        images[frame_id] = image
        metrics = _image_metrics(image)
        labels, method = _classify(metrics, image.width, image.height)
        confidence = "MEDIUM" if len(labels) > 1 else "LOW"
        frames.append(
            {
                "listing_id": listing_id,
                "frame_id": frame_id,
                "media_type": "PHOTO",
                "source_url": listing.image_urls[index - 1] if index <= len(listing.image_urls) else "",
                "sha256": _sha256(body),
                "width": image.width,
                "height": image.height,
                "scene_labels": "|".join(labels),
                "structure_labels": "UNKNOWN_STRUCTURE",
                "analysis_method": method,
                "confidence": confidence,
            }
        )
        for label in labels:
            if label == "POOL":
                observations.append(
                    {"listing_id": listing_id, "observation_id": f"{frame_id}-pool",
                     "subject": "TARGET_PROPERTY", "feature": "pool.presence",
                     "value": "YES", "confidence": "LOW", "provenance": f"PHOTO_{frame_id}",
                     "frame_ids": frame_id, "notes": "RGB layout cue; geometry requires human confirmation."}
                )
            elif label == "ROOF_VISIBLE":
                observations.append(
                    {"listing_id": listing_id, "observation_id": f"{frame_id}-roof",
                     "subject": "UNKNOWN_STRUCTURE", "feature": "roof.visible",
                     "value": "YES", "confidence": "LOW", "provenance": f"PHOTO_{frame_id}",
                     "frame_ids": frame_id, "notes": "Structure ownership is unresolved."}
                )
            elif label == "INTERIOR":
                observations.append(
                    {"listing_id": listing_id, "observation_id": f"{frame_id}-interior",
                     "subject": "UNKNOWN_STRUCTURE", "feature": "interior_with_exterior_view",
                     "value": "POSSIBLE", "confidence": "LOW", "provenance": f"PHOTO_{frame_id}",
                     "frame_ids": frame_id, "notes": "Generic brightness cue; retain for review."}
                )
    text_evidence = _text_evidence(listing)
    for evidence in text_evidence:
        observations.append(
            {"listing_id": listing_id, "observation_id": f"text-{evidence['feature']}",
             "subject": "LISTING", "feature": evidence["feature"], "value": evidence["value"],
             "confidence": evidence["confidence"], "provenance": "LISTING_TEXT",
             "frame_ids": "", "notes": "Text evidence is not visual evidence."}
        )
    pool_ids = [row["observation_id"] for row in observations if row["feature"] == "pool.presence"]
    if len(pool_ids) > 1:
        relationships.append(
            {"listing_id": listing_id, "relationship_id": f"{listing_id}-pool-fusion",
             "from_observation": pool_ids[0], "relation": "CORROBORATED_BY",
             "to_observation": pool_ids[1], "confidence": "LOW",
             "provenance": "MULTI_FRAME_FUSION", "frame_ids": "|".join(pool_ids),
             "notes": "Repeated generic visual cue; not a shape or identity claim."}
        )
    fingerprint = {
        "schema_version": "LVI_V1",
        "listing": {"listing_id": listing_id, "url": url, "media_count": len(frames), "video_count": len(listing.video_urls)},
        "text_evidence": text_evidence,
        "frames": frames,
        "target_property": {
            "house": {"footprint": "UNKNOWN", "storeys": "UNKNOWN", "confidence": "UNKNOWN"},
            "roof": {"form": "UNKNOWN", "colour": "UNKNOWN", "material": "UNKNOWN", "confidence": "UNKNOWN"},
            "pool": {"presence": "UNKNOWN", "geometry": "UNKNOWN", "house_relation": "UNKNOWN", "confidence": "UNKNOWN"},
            "driveway": {"visibility": "UNKNOWN", "geometry": "UNKNOWN", "confidence": "UNKNOWN"},
            "garage": {"visibility": "UNKNOWN", "relationship": "UNKNOWN", "confidence": "UNKNOWN"},
            "road_relationship": {"visibility": "UNKNOWN", "geometry": "UNKNOWN", "confidence": "UNKNOWN"},
            "solar": {"panels": "UNKNOWN", "backup_power": "UNKNOWN", "confidence": "UNKNOWN"},
            "other": {},
        },
        "neighbours": [{"neighbour_id": "N1", "classification": "UNKNOWN_STRUCTURE", "confidence": "UNKNOWN"}],
        "relationships": relationships,
        "observations": observations,
        "distinctive_features": [],
        "unknowns": ["Target/neighbour ownership, roof geometry, pool contour, driveway, garage, road and solar remain unresolved by deterministic extraction."],
        "provenance": {"visual": "PHOTO_*", "text": "LISTING_TEXT", "fusion": "MULTI_FRAME_FUSION", "identity": "WITHHELD"},
    }
    _contact_sheet(listing_id, frames, images)
    return frames, observations, relationships, fingerprint


def main() -> None:
    global OUT
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    OUT = args.output
    OUT.mkdir(parents=True, exist_ok=True)
    cache_root = Path(tempfile.mkdtemp(prefix="lvi-v1-"))
    frame_rows: list[dict[str, Any]] = []
    observation_rows: list[dict[str, Any]] = []
    relationship_rows: list[dict[str, Any]] = []
    fingerprints: dict[str, dict[str, Any]] = {}
    try:
        for listing_id, url in LISTINGS.items():
            (OUT / listing_id).mkdir(parents=True, exist_ok=True)
            frames, observations, relationships, fingerprint = extract_listing(listing_id, url, cache_root)
            frame_rows.extend(frames)
            observation_rows.extend(observations)
            relationship_rows.extend(relationships)
            fingerprints[listing_id] = fingerprint
            (OUT / listing_id / "SCENE_FINGERPRINT.json").write_text(
                json.dumps(fingerprint, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            report = [
                f"# Scene report: {listing_id}",
                "",
                "This report is generated from Property24 listing media and listing text only.",
                "",
                "## Target house",
                "The deterministic extractor retains all frames but cannot assign a visible structure to the target with high confidence.",
                "",
                "## Roof, pool, driveway, garage and road",
                "These feature families are represented in the schema. Values not established by the generic visual pass remain UNKNOWN rather than being invented.",
                "",
                "## Neighbours and solar",
                "Visible structures are retained as UNKNOWN_STRUCTURE until ownership is defensible. Solar panels and backup power are separate concepts; neither is inferred from the other.",
                "",
                "## Evidence limits",
                f"{len(frames)} photo frames were inventoried. Contact sheets retain frame provenance and deterministic scene cues for human review.",
            ]
            (OUT / listing_id / "SCENE_REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    finally:
        shutil.rmtree(cache_root, ignore_errors=True)
    _write_csv(OUT / "LVI_V1_FRAME_INVENTORY.csv", frame_rows, FRAME_FIELDS)
    _write_csv(OUT / "LVI_V1_OBSERVATIONS.csv", observation_rows, OBS_FIELDS)
    _write_csv(OUT / "LVI_V1_RELATIONSHIPS.csv", relationship_rows, REL_FIELDS)
    (OUT / "LVI_V1_RUN_METADATA.json").write_text(
        json.dumps({"listings": list(LISTINGS), "extractor": "scripts/lvi_v1.py", "fingerprint_ids": list(fingerprints)}, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
