#!/usr/bin/env python3
"""Blind W2 execution for MyProperty RL5480 against the immutable W1 estate.

The ``listing-only`` phase must be committed before ``rank`` is run.  The
script never opens a listing map, reads listing metadata, or resolves identity.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
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
W1_MANIFEST = ROOT / "data" / "estates" / "waterfall_country_estate" / "manifest.w1.json"
W1_GEOJSON = ROOT / "data" / "estates" / "waterfall_country_estate" / "waterfall_country_estate_w1.geojson"
W1_GEOJSON_SHA256 = "6a375bf542bcff28c6a3ee862f9e0c3c9a5395d0497b4159027c40b75cf7be3a"
ESTATE_ID = "waterfall_w2_blind"
# Frozen Scoring v2 terms, with stand size reduced from 0.07 to 0.05 and the
# released 0.02 reported as independent open-space context rather than identity.
W2_EXPERIMENTAL_WEIGHTS = {
    "pool_presence": 0.14, "shape_v2": 0.36, "spatial_v2": 0.22,
    "aerial": 0.12, "exterior": 0.06, "gis": 0.03, "stand_size": 0.05,
    "greenbelt_context": 0.02,
}


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


def w1_dataset() -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Adapt immutable W1 features to the generic inventory interface.

    The synthetic stand key prevents same-number collisions between extensions;
    the original stand number and extension remain separately retained for
    review output.  No source GIS field beyond the frozen W1 files is used.
    """
    if sha256(W1_GEOJSON) != W1_GEOJSON_SHA256:
        raise RuntimeError("immutable W1 GeoJSON hash mismatch")
    manifest = json.loads(W1_MANIFEST.read_text(encoding="utf-8"))
    if int(manifest["total_erven"]) != 1010:
        raise RuntimeError("W1 candidate count is not 1,010")
    collection = json.loads(W1_GEOJSON.read_text(encoding="utf-8"))
    parcels, display = [], {}
    for feature in collection["features"]:
        props = feature["properties"]
        extension, property_id = int(props["extension"]), str(props["pie_property_id"])
        key = f"{extension}_{property_id}"
        parcels.append({
            "property_id": property_id,
            "stand_number": key,
            "township": f"JUKSKEI VIEW EXTENSION {extension}",
            "extension": extension,
            "area_sqm": float(props["area_sqm"]),
            "land_type": "Erven",
            "class": None,
            "geometry": feature["geometry"],
        })
        display[property_id] = {
            "property_id": property_id,
            "stand_number": props["stand_number"],
            "extension": extension,
            "area_sqm": float(props["area_sqm"]),
            "geometry": feature["geometry"],
        }
    if len(parcels) != 1010 or len({item["property_id"] for item in parcels}) != 1010:
        raise RuntimeError("W1 parcel identity uniqueness check failed")
    return {"extent": manifest["extent"], "parcels": parcels}, display


def build_w1_candidate_imagery(dataset: dict[str, Any]) -> dict[str, Any]:
    """Acquire W1's declared 2023 native15 source and create derived crops."""
    from build_waterfall_country_estate_gis import _crop_tiles
    from backend.imagery.estate_tiles import EstateTileIndex

    index = EstateTileIndex(
        ROOT / "data" / "cache" / "ags_native15" / ESTATE_ID,
        dataset["extent"],
        profile_id="native15",
    )
    stats = index.build()
    crop_root = ROOT / "data" / "visual_index" / ESTATE_ID / "_imagery_cache_native15"
    features = [
        {
            "properties": {
                "extension": parcel["extension"],
                "pie_property_id": parcel["property_id"],
                "centroid_latitude": sum(point[1] for ring in parcel["geometry"]["rings"] for point in ring) / sum(len(ring) for ring in parcel["geometry"]["rings"]),
                "centroid_longitude": sum(point[0] for ring in parcel["geometry"]["rings"] for point in ring) / sum(len(ring) for ring in parcel["geometry"]["rings"]),
            },
            "geometry": parcel["geometry"],
        }
        for parcel in dataset["parcels"]
    ]
    results = [_crop_tiles(feature, index.tiles, crop_root) for feature in features]
    if any(item["status"] != "READY" for item in results):
        raise RuntimeError(f"candidate imagery incomplete: {sum(item['status'] != 'READY' for item in results)} crops failed")
    return {
        "source": "W1-declared AGS AerialPhotography/2023 native15",
        "tile_stats": stats.__dict__,
        "crop_count": len(results),
        "crop_dimensions": [900, 900],
    }


def fixed_crop_parcel_mask(geometry: dict[str, Any], width: int, height: int) -> np.ndarray:
    """Rasterise a W1 polygon onto its W1 135 m centroid crop."""
    import cv2
    from backend.imagery.estate_tiles import _mercator

    points = [point for ring in geometry["rings"] for point in ring]
    cx, cy = _mercator(sum(point[1] for point in points) / len(points), sum(point[0] for point in points) / len(points))
    mask = np.zeros((height, width), dtype=np.uint8)
    rings = []
    for ring in geometry["rings"]:
        pixels = []
        for lon, lat in ring:
            x, y = _mercator(lat, lon)
            pixels.append((round((x - (cx - 67.5)) / 135 * width), round(((cy + 67.5) - y) / 135 * height)))
        if len(pixels) >= 3:
            rings.append(np.asarray(pixels, dtype=np.int32))
    if rings:
        cv2.fillPoly(mask, rings, 255)
    return mask


def listing_pool_descriptor() -> dict[str, Any]:
    """Extract a normal-view pool contour using the established generic seed."""
    import cv2
    from backend.gis.estate_ags_matching.os_scoring_v2 import contour_descriptors
    from backend.vision.object_segmentation import contour_geometry, water_seed_masks

    image = cv2.imread(str(MEDIA / "02_01.jpg"))
    if image is None:
        raise RuntimeError("frozen listing pool image missing")
    mask = np.full(image.shape[:2], 255, dtype=np.uint8)
    seeds = water_seed_masks(image, mask)
    if not seeds:
        raise RuntimeError("generic listing pool seed extraction found no candidate")
    geometry = contour_geometry(max(seeds, key=lambda item: int(item.sum())))
    desc = contour_descriptors(geometry.get("contour_image"))
    if desc is None:
        raise RuntimeError("generic listing pool contour descriptor unavailable")
    return {"geometry": geometry, "descriptor": desc}


def stand_size_score(area_sqm: float) -> float:
    return round(math.exp(-abs(area_sqm - 1035.0) / 1035.0), 4)


def greenbelt_state(mask: np.ndarray, image: np.ndarray) -> tuple[str, float]:
    """Generic aerial context, never a named-place lookup or a rank gate."""
    import cv2
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    hue, sat, value = cv2.split(hsv)
    vegetation = (hue >= 35) & (hue <= 85) & (sat >= 40) & (value >= 40)
    ring = cv2.dilate(mask, np.ones((41, 41), np.uint8)) > 0
    outside = ring & ~(mask > 0)
    fraction = float(vegetation[outside].mean()) if outside.any() else 0.0
    if fraction >= 0.62:
        return "possibly", fraction
    return "unknown", fraction


def rank_candidates() -> None:
    """Run generic colour/roof/contour evidence over every immutable W1 crop."""
    import cv2
    from backend.gis.estate_ags_matching.os_scoring_v2 import contour_descriptors, shape_v2_similarity
    from backend.vision.object_segmentation import contour_geometry, roof_seed_masks, water_seed_masks

    observation_path = OUT / "listing_visual_observations.json"
    if not observation_path.is_file() or not (OUT / "listing_visual_observations.sha256").is_file():
        raise RuntimeError("listing-only visual freeze is required before candidate ranking")
    if (OUT / "listing_visual_observations.sha256").read_text(encoding="ascii").strip() != sha256(observation_path):
        raise RuntimeError("listing-only visual freeze hash mismatch")
    dataset, display = w1_dataset()
    listing = listing_pool_descriptor()
    rows = []
    for parcel in dataset["parcels"]:
        path = ROOT / "data" / "visual_index" / ESTATE_ID / "_imagery_cache_native15" / f"{parcel['stand_number']}_ags_aerial.jpg"
        image = cv2.imread(str(path))
        if image is None:
            raise RuntimeError(f"missing W1 crop: {path.name}")
        parcel_mask = fixed_crop_parcel_mask(parcel["geometry"], image.shape[1], image.shape[0])
        pool_seeds = water_seed_masks(image, parcel_mask)
        pool_geometry = contour_geometry(max(pool_seeds, key=lambda item: int(item.sum()))) if pool_seeds else {"present": False}
        candidate_desc = contour_descriptors(pool_geometry.get("contour_image")) if pool_geometry.get("present") else None
        shape, _shape_parts = shape_v2_similarity(listing["descriptor"], candidate_desc)
        roof_seeds = roof_seed_masks(image, parcel_mask, max(pool_seeds, key=lambda item: int(item.sum())) if pool_seeds else None)
        roof_fraction = sum(int(item.sum()) for item in roof_seeds) / max(int((parcel_mask > 0).sum()), 1)
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        paved = (hsv[:, :, 1] <= 55) & (hsv[:, :, 2] >= 50) & (hsv[:, :, 2] <= 200)
        driveway_fraction = float(paved[parcel_mask > 0].mean()) if (parcel_mask > 0).any() else 0.0
        greenbelt, green_fraction = greenbelt_state(parcel_mask, image)
        pool_state = "YES" if pool_geometry.get("present") else "UNKNOWN"
        components = {
            "pool_presence": 1.0 if pool_state == "YES" else 0.5,
            "shape_v2": 0.5 if shape is None else shape,
            "spatial_v2": 0.5,
            "aerial": min(1.0, 0.45 + min(roof_fraction, 0.35) + (0.20 if pool_state == "YES" else 0.0)),
            "exterior": min(1.0, 0.45 + min(roof_fraction, 0.25) + min(driveway_fraction, 0.20)),
            "gis": 0.5,
            "stand_size": stand_size_score(float(parcel["area_sqm"])),
            "greenbelt_context": 0.7 if greenbelt == "possibly" else 0.5,
        }
        score = round(sum(W2_EXPERIMENTAL_WEIGHTS[key] * components[key] for key in W2_EXPERIMENTAL_WEIGHTS), 4)
        item = display[parcel["property_id"]]
        rows.append({
            "property_id": item["property_id"], "stand_number": item["stand_number"],
            "extension": item["extension"], "area_sqm": item["area_sqm"], "total_score": score,
            "components": {key: round(value, 4) for key, value in components.items()},
            "pool_state": pool_state, "pool_geometry": {key: pool_geometry.get(key) for key in ("shape", "area_m2", "aspect_ratio", "compactness", "convexity")},
            "house_roof": {"state": "YES" if roof_seeds else "UNKNOWN", "roof_fraction": round(roof_fraction, 4)},
            "driveway": {"state": "YES" if driveway_fraction >= 0.08 else "UNKNOWN", "paved_fraction": round(driveway_fraction, 4)},
            "greenbelt": {"state": greenbelt, "aerial_vegetation_ring_fraction": round(green_fraction, 4)},
            "neighbour_context": "UNKNOWN",
            "missing_or_unknown": [name for name, value in {"pool": pool_state, "roof": "YES" if roof_seeds else "UNKNOWN", "driveway": "YES" if driveway_fraction >= 0.08 else "UNKNOWN", "neighbour": "UNKNOWN"}.items() if value == "UNKNOWN"],
            "crop_path": relative(path),
        })
    rows.sort(key=lambda item: (-item["total_score"], str(item["extension"]), str(item["stand_number"]), str(item["property_id"])))
    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank
    (OUT / "ranking_full.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    (OUT / "ranking_full.csv").write_text(
        "rank,extension,stand_number,property_id,area_sqm,total_score,pool_state,pool_shape,roof_state,driveway_state,greenbelt_state,missing_or_unknown\n" +
        "\n".join(f"{r['rank']},{r['extension']},{r['stand_number']},{r['property_id']},{r['area_sqm']},{r['total_score']},{r['pool_state']},{r['pool_geometry']['shape']},{r['house_roof']['state']},{r['driveway']['state']},{r['greenbelt']['state']},{'|'.join(r['missing_or_unknown'])}" for r in rows) + "\n",
        encoding="utf-8",
    )
    review = {"top50": rows[:50], "top20": rows[:20], "top10": rows[:10], "top5": rows[:5]}
    (OUT / "ranking_review.json").write_text(json.dumps(review, indent=2) + "\n", encoding="utf-8")
    render_top5(rows[:5], {parcel["property_id"]: parcel["geometry"] for parcel in dataset["parcels"]})
    freeze = {
        "schema_version": "waterfall-w2-ranking-freeze-v1", "created_utc": now(),
        "base_w1_commit": "e86b156b3f8ac099cd386b9de2b3b2ba609c0635",
        "base_w1_geojson_sha256": W1_GEOJSON_SHA256, "candidate_count": len(rows),
        "listing_visual_freeze_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "ranking_algorithm": "generic_existing_pie_object_segmentation_seed_roof_contour_plus_scoring_v2_derived_experimental_weights",
        "weights": W2_EXPERIMENTAL_WEIGHTS, "stand_size_weight_constraint": "0.05",
        "ground_truth_recovery": "NOT_STARTED", "artifacts": {name: {"path": relative(OUT / name), "sha256": sha256(OUT / name)} for name in ("ranking_full.json", "ranking_full.csv", "ranking_review.json", "top5_contact_sheet.jpg")},
    }
    path = OUT / "ranking_freeze.json"
    path.write_text(json.dumps(freeze, indent=2) + "\n", encoding="utf-8")
    (OUT / "ranking_freeze.sha256").write_text(sha256(path) + "\n", encoding="ascii")
    write_report(rows, freeze)
    print(json.dumps({"ranking_sha256": sha256(path), "candidate_count": len(rows), "top10": rows[:10]}, indent=2))


def write_report(rows: list[dict[str, Any]], freeze: dict[str, Any]) -> None:
    observations = json.loads((OUT / "listing_visual_observations.json").read_text(encoding="utf-8"))
    lines = [
        "# Waterfall W2 blind ranking freeze - RL5480",
        "",
        "## Blind firewall",
        "",
        f"- W1 immutable evidence commit: `e86b156`; GeoJSON SHA256: `{W1_GEOJSON_SHA256}`.",
        "- W1 candidate universe: exactly 1,010 parcels from extensions 19, 38, 39, 40, 43, and 105.",
        f"- Listing-only evidence commit: `{freeze['listing_visual_freeze_commit']}`.",
        "- No candidate crop was accessed before that commit. No address, coordinate, agent, portal, price, reverse-image, duplicate-listing, or ground-truth recovery was used.",
        "",
        "## Listing extraction and visual freeze",
        "",
        "- Normal rendered gallery: 48 original images, each recorded with source order, URL, dimensions, and SHA256 in `listing_media_manifest.json`.",
        "- Standard rendered embeds/assets: **NO VIDEO FOUND**.",
        f"- Listing visual-freeze SHA256: `{sha256(OUT / 'listing_visual_observations.json')}`.",
        "",
        "| Feature | State | Confidence | Expected aerial visibility | Listing-only observation |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for item in observations["observations"]:
        lines.append(f"| {item['feature']} | {item['state']} | {item['confidence']} | {item['expected_aerial_visibility']} | {item['detail']} |")
    lines.extend([
        "",
        "The 1,035 m2 land size is weak supporting evidence only (experimental contribution 5%). The green-belt phrase is retained as listing evidence and never used as identity.",
        "",
        "## Candidate ranking",
        "",
        "- All 1,010 W1 crops were generated from the W1-declared 2023 native15 source after the visual freeze.",
        "- Generic existing PIE colour seed, roof seed, contour descriptor, and Scoring v2-derived experimental weights were applied uniformly. No candidate was eliminated for pool NO/UNKNOWN; this run emits YES or UNKNOWN only.",
        "- Greenbelt context is independently marked `possibly` or `unknown` from W1 aerial context only; it is not a hard gate.",
        f"- Ranking freeze SHA256: `{sha256(OUT / 'ranking_freeze.json')}`.",
        "",
        "### Top 10",
        "",
        "| Rank | Stand | Ext | Property ID | Total | Pool / geometry | Roof | Driveway | Greenbelt | Area m2 | Missing / unknown |",
        "| ---: | --- | ---: | --- | ---: | --- | --- | --- | --- | ---: | --- |",
    ])
    for row in rows[:10]:
        lines.append(
            f"| {row['rank']} | {row['stand_number']} | {row['extension']} | {row['property_id']} | {row['total_score']} | "
            f"{row['pool_state']} / {row['pool_geometry']['shape']} | {row['house_roof']['state']} | {row['driveway']['state']} | "
            f"{row['greenbelt']['state']} | {row['area_sqm']} | {', '.join(row['missing_or_unknown']) or 'none'} |"
        )
    lines.extend([
        "",
        "## Review package",
        "",
        "- `ranking_full.csv` and `ranking_full.json`: complete 1,010-parcel ranking.",
        "- `ranking_review.json`: Top 50, Top 20, Top 10, and Top 5.",
        "- `top5_contact_sheet.jpg`: native15 candidate crops with parcel boundaries and score overlays plus three listing exterior references.",
        "",
        "**GROUND TRUTH RECOVERY = NOT STARTED**",
        "",
    ])
    (OUT / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def render_top5(rows: list[dict[str, Any]], geometries: dict[str, dict[str, Any]]) -> None:
    import cv2

    cells = []
    for row in rows:
        image_array = cv2.imread(str(ROOT / row["crop_path"]))
        mask = fixed_crop_parcel_mask(geometries[row["property_id"]], image_array.shape[1], image_array.shape[0])
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(image_array, contours, -1, (0, 255, 0), 3)
        image = Image.fromarray(cv2.cvtColor(image_array, cv2.COLOR_BGR2RGB))
        image.thumbnail((500, 500))
        panel = Image.new("RGB", (500, 560), "white")
        panel.paste(image, ((500 - image.width) // 2, 0))
        draw = ImageDraw.Draw(panel)
        draw.text((10, 505), f"#{row['rank']} stand {row['stand_number']} ext {row['extension']} ID {row['property_id']}", fill="black")
        draw.text((10, 525), f"score={row['total_score']} pool={row['pool_state']}/{row['pool_geometry']['shape']} greenbelt={row['greenbelt']['state']}", fill="black")
        draw.text((10, 542), f"roof={row['house_roof']['state']} driveway={row['driveway']['state']} area={row['area_sqm']}", fill="black")
        cells.append(panel)
    sheet = Image.new("RGB", (1500, 1680), "white")
    for index, cell in enumerate(cells):
        sheet.paste(cell, ((index % 2) * 500, (index // 2) * 560))
    for index, name in enumerate(("01_25.jpg", "02_01.jpg", "08_02.jpg")):
        image = Image.open(MEDIA / name).convert("RGB")
        image.thumbnail((500, 360))
        x = 1000
        y = index * 560
        sheet.paste(image, (x, y))
        ImageDraw.Draw(sheet).text((x + 10, y + 370), f"listing exterior reference {index + 1}", fill="black")
    sheet.save(OUT / "top5_contact_sheet.jpg", quality=92)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("listing-only", "build-candidate-imagery", "rank"))
    args = parser.parse_args()
    if args.phase == "listing-only":
        listing_only()
    elif args.phase == "build-candidate-imagery":
        dataset, _display = w1_dataset()
        print(json.dumps(build_w1_candidate_imagery(dataset), indent=2))
    elif args.phase == "rank":
        rank_candidates()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
