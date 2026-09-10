#!/usr/bin/env python3
"""Blind W2 execution for MyProperty RL5480 against the immutable W1 estate.

The ``listing-only`` phase must be committed before ``rank`` is run.  The
script never opens a listing map, reads listing metadata, or resolves identity.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "investigations" / "waterfall_w2_rl5480_blind"
MEDIA = OUT / "listing_media"
LISTING_URL = (
    "https://www.myproperty.co.za/en-za/for-sale/house/gauteng/midrand/"
    "waterfall-country-estate/5-bedroom/rl5480"
)
# This is the normal rendered-gallery order, captured from the site's 48-photo
# gallery.  It contains only image asset identifiers, never a location.
GALLERY_ORDER = (
    25, 1, 4, 20, 39, 26, 23, 2, 3, 24, 7, 44, 46, 43, 15, 16, 13, 18,
    41, 36, 33, 32, 28, 30, 5, 42, 40, 38, 31, 29, 48, 47, 45, 37, 34,
    35, 27, 14, 12, 8, 9, 22, 21, 19, 11, 10, 17, 6,
)
ASSET_PREFIX = "https://s3.entegral.net/flex/property/24/RL5480/1785563963239-"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def relative(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def image_record(order: int, asset: int) -> dict[str, Any]:
    path = MEDIA / f"{order:02d}_{asset:02d}.jpg"
    if not path.is_file():
        request = urllib.request.Request(f"{ASSET_PREFIX}{asset}.jpg", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=60) as response:
            path.write_bytes(response.read())
    with Image.open(path) as image:
        width, height = image.size
    return {
        "source_order": order,
        "source_url": f"{ASSET_PREFIX}{asset}.jpg",
        "path": relative(path),
        "dimensions": [width, height],
        "sha256": sha256(path),
    }


def contact_sheet(records: list[dict[str, Any]]) -> Path:
    thumb_w, thumb_h, cols = 240, 180, 6
    rows = (len(records) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * thumb_w, rows * (thumb_h + 24)), "white")
    draw = ImageDraw.Draw(sheet)
    for index, record in enumerate(records):
        with Image.open(ROOT / record["path"]) as image:
            image = image.convert("RGB")
            image.thumbnail((thumb_w, thumb_h))
            x = (index % cols) * thumb_w + (thumb_w - image.width) // 2
            y = (index // cols) * (thumb_h + 24)
            sheet.paste(image, (x, y))
        draw.text((x + 4, y + thumb_h + 4), f"{record['source_order']:02d}", fill="black")
    output = OUT / "listing_contact_sheet.jpg"
    sheet.save(output, quality=92)
    return output


def listing_observations(records: list[dict[str, Any]], sheet: Path) -> dict[str, Any]:
    """Listing-only visual assertions; UNKNOWN avoids claims from obscured views."""
    source = {
        "pool": [2, 8, 9, 10, 11, 12, 34, 35, 48],
        "front": [1, 6, 7],
        "rear": [8, 9, 10, 11, 12, 34, 35, 48],
    }
    return {
        "schema_version": "waterfall-w2-listing-observations-v1",
        "created_utc": now(),
        "blind_scope": {
            "candidate_imagery_accessed_before_freeze": False,
            "listing_reference": "RL5480",
            "listing_url": LISTING_URL,
            "prohibited_identity_recovery": True,
        },
        "listing_facts": {
            "land_sqm": 1035,
            "land_size_role": "weak_supporting_evidence_only; experimental_weight_at_most_0.05",
            "green_belt_text": "listing_claim_only_not_identity",
            "video": "NO_VIDEO_FOUND",
        },
        "observations": [
            {
                "feature": "pool",
                "state": "YES",
                "confidence": 0.99,
                "source_images": source["pool"],
                "expected_aerial_visibility": "HIGH",
                "detail": "A private in-ground pool is repeatedly visible behind the house.",
            },
            {
                "feature": "pool_shape",
                "state": "YES",
                "confidence": 0.84,
                "source_images": source["pool"],
                "expected_aerial_visibility": "HIGH",
                "detail": "Multiple elevated oblique views support a broad curvilinear/kidney-like pool outline; exact nadir contour remains uncertain.",
            },
            {
                "feature": "house_roof_structure",
                "state": "YES",
                "confidence": 0.78,
                "source_images": source["front"] + source["rear"],
                "expected_aerial_visibility": "MEDIUM",
                "detail": "Large two-storey residence with multi-plane pitched tiled roof and rear covered entertainment patio.",
            },
            {
                "feature": "driveway_garage",
                "state": "YES",
                "confidence": 0.9,
                "source_images": source["front"],
                "expected_aerial_visibility": "MEDIUM",
                "detail": "Paved front approach leads directly to three adjacent automated garage doors; complete driveway extent is not visible.",
            },
            {
                "feature": "boundary_street",
                "state": "YES",
                "confidence": 0.7,
                "source_images": [1, 6, 7],
                "expected_aerial_visibility": "LOW",
                "detail": "Brick perimeter wall, mature landscaped front garden, and broad paved street-side approach are visible; full street geometry is incomplete.",
            },
            {
                "feature": "neighbours",
                "state": "UNKNOWN",
                "confidence": 0.2,
                "source_images": source["front"] + source["rear"],
                "expected_aerial_visibility": "MEDIUM",
                "detail": "Listing views do not provide sufficient unobscured neighbouring-parcel evidence.",
            },
            {
                "feature": "landscape_open_space",
                "state": "YES",
                "confidence": 0.68,
                "source_images": source["rear"],
                "expected_aerial_visibility": "MEDIUM",
                "detail": "Established garden and lawn are visible. The green-belt setting is retained as a listing claim, not identity evidence.",
            },
            {
                "feature": "aerial_visible_features",
                "state": "YES",
                "confidence": 0.7,
                "source_images": source["pool"] + source["rear"],
                "expected_aerial_visibility": "HIGH",
                "detail": "Pool, large roof mass, rear patio/deck, and substantial garden should be aerially discernible.",
            },
        ],
        "media_manifest_sha256": None,
        "listing_contact_sheet": {"path": relative(sheet), "sha256": sha256(sheet)},
        "image_count": len(records),
    }


def listing_only() -> None:
    if len(GALLERY_ORDER) != 48 or len(set(GALLERY_ORDER)) != 48:
        raise RuntimeError("gallery order must contain each of the 48 normal listing photos exactly once")
    MEDIA.mkdir(parents=True, exist_ok=True)
    records = [image_record(index, asset) for index, asset in enumerate(GALLERY_ORDER, start=1)]
    manifest = {
        "schema_version": "waterfall-w2-listing-media-v1",
        "created_utc": now(),
        "listing_reference": "RL5480",
        "listing_url": LISTING_URL,
        "normal_gallery_photo_count": 48,
        "video_check": {
            "method": "normal_rendered_listing_embeds_and_assets",
            "result": "NO_VIDEO_FOUND",
            "video_count": 0,
        },
        "images": records,
    }
    media_manifest = OUT / "listing_media_manifest.json"
    media_manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    sheet = contact_sheet(records)
    observations = listing_observations(records, sheet)
    observations["media_manifest_sha256"] = sha256(media_manifest)
    observation_path = OUT / "listing_visual_observations.json"
    observation_path.write_text(json.dumps(observations, indent=2) + "\n", encoding="utf-8")
    (OUT / "listing_visual_observations.sha256").write_text(sha256(observation_path) + "\n", encoding="ascii")
    print(json.dumps({
        "media_manifest": relative(media_manifest),
        "media_manifest_sha256": sha256(media_manifest),
        "observations": relative(observation_path),
        "observations_sha256": sha256(observation_path),
        "images": len(records),
    }, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("listing-only",))
    args = parser.parse_args()
    if args.phase == "listing-only":
        listing_only()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
