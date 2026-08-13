#!/usr/bin/env python3
"""Blind visual match of listing 116978058 against SUMMERSET EXT.6 + EXT.13 only."""

from __future__ import annotations

import io
import json
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.gis.dataset_registry import CORRECT_CARLSWALD_NORTH, require_active_dataset
from backend.gis.estate_ags_matching.aerial_geometric import (
    extract_structural_layout,
    structural_layout_similarity,
)
from backend.gis.estate_ags_matching.final_candidates import (
    FINAL_CANDIDATE_LIMIT,
    SUCCESS_STANDARD,
    freeze_final_candidates,
)
from backend.gis.estate_ags_matching.pool_geometry import (
    consensus_pool_fingerprint,
    extract_pool_geometry,
    pool_geometry_similarity,
)
from backend.imagery.estate_tiles import (
    PADDING_METRES,
    EstateTileIndex,
    cache_root_for,
    crop_dir_for,
)
from backend.parsers.property24 import download_images, fetch_listing
from backend.vision.clip_encoder import classify_scene, encode_image, mean_top_similarity

LISTING_URL = "https://www.property24.com/for-sale/carlswald-north-estate/midrand/gauteng/12743/116978058"
LISTING_ID = "116978058"
OUTPUT = ROOT / "data/investigations/carlswald_north_corrected" / LISTING_ID
DATASET_JSON = ROOT / "data/gis" / f"{CORRECT_CARLSWALD_NORTH}.json"
TILE_CACHE = cache_root_for(CORRECT_CARLSWALD_NORTH, "native15")
CROP_DIR = crop_dir_for(CORRECT_CARLSWALD_NORTH, "native15")

IDENT_SCENES = {
    "aerial",
    "pool_garden",
    "front_elevation",
    "rear_elevation",
    "driveway_access",
    "contextual",
}


def combined_score(**kwargs) -> float:
    weights = {
        "pool_geom": 0.30 if kwargs["pool_geom"] is not None else 0.0,
        "pool_house": 0.18 if kwargs["pool_house"] is not None else 0.0,
        "structural": 0.16 if kwargs["structural"] is not None else 0.0,
        "aerial": 0.14 if kwargs["aerial"] is not None else 0.0,
        "video": 0.08 if kwargs["video"] is not None else 0.0,
        "exterior": 0.07 if kwargs["exterior"] is not None else 0.0,
        "driveway": 0.05 if kwargs["driveway"] is not None else 0.0,
        "gis": 0.02 if kwargs["gis"] is not None else 0.0,
        "stand_size": 0.05,
    }
    values = {key: (kwargs[key] or 0.0) for key in weights}
    values["stand_size"] = kwargs["stand_size"] or 0.0
    total_w = sum(weights.values())
    score = sum(values[key] * weights[key] for key in weights) / max(total_w, 1e-6)
    if kwargs.get("contradiction") == "listing_has_pool_candidate_has_none":
        score *= 0.25
    elif kwargs.get("contradiction"):
        score *= 0.7
    return round(float(max(0.0, min(1.0, score))), 4)


def stand_size_support(listing_sqm: float | None, candidate_sqm: float | None) -> float:
    if not listing_sqm or not candidate_sqm or listing_sqm <= 0:
        return 0.0
    rel = abs(float(candidate_sqm) - float(listing_sqm)) / float(listing_sqm)
    return float(max(0.0, min(1.0, 1.0 - rel / 0.45)))


def parcel_bbox(geometry: dict) -> tuple[float, float, float, float]:
    xs, ys = [], []
    for ring in geometry.get("rings") or []:
        for x, y in ring:
            xs.append(x)
            ys.append(y)
    return min(xs), min(ys), max(xs), max(ys)


def crop_parcel(tile: dict, geometry: dict, dest: Path) -> bool:
    if not tile["path"].is_file():
        return False
    image = Image.open(tile["path"]).convert("RGB")
    min_lon, min_lat, max_lon, max_lat = parcel_bbox(geometry)
    # pad in degrees ~ 18 m
    pad = PADDING_METRES / 111_320
    min_lon -= pad
    max_lon += pad
    min_lat -= pad
    max_lat += pad
    w, h = image.size
    def px(lon, lat):
        x = (lon - tile["min_lon"]) / max(tile["max_lon"] - tile["min_lon"], 1e-12)
        y = (tile["max_lat"] - lat) / max(tile["max_lat"] - tile["min_lat"], 1e-12)
        return int(x * (w - 1)), int(y * (h - 1))
    x0, y1 = px(min_lon, min_lat)
    x1, y0 = px(max_lon, max_lat)
    left, right = sorted((max(0, x0), max(0, x1)))
    top, bottom = sorted((max(0, y0), max(0, y1)))
    right = min(w, max(right, left + 8))
    bottom = min(h, max(bottom, top + 8))
    crop = image.crop((left, top, right, bottom))
    if min(crop.size) < 24:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    crop.save(dest, quality=90)
    return True


def parcel_mask(image_size, geometry, tile) -> np.ndarray:
    import cv2

    width, height = image_size
    min_lon, min_lat, max_lon, max_lat = parcel_bbox(geometry)
    pad = PADDING_METRES / 111_320
    bbox = (min_lon - pad, min_lat - pad, max_lon + pad, max_lat + pad)
    pts = []
    for ring in geometry.get("rings") or []:
        for lon, lat in ring:
            x = (lon - bbox[0]) / max(bbox[2] - bbox[0], 1e-12) * width
            y = (bbox[3] - lat) / max(bbox[3] - bbox[1], 1e-12) * height
            pts.append((int(x), int(y)))
        break
    mask = np.zeros((height, width), dtype=np.uint8)
    if len(pts) >= 3:
        cv2.fillPoly(mask, [np.array(pts, dtype=np.int32)], 255)
    else:
        mask[:] = 255
    return mask


def draw_panel(listing_bytes, cand_bytes, listing_fp, cand_fp, stand, township, dest, geometry=None):
    listing = Image.open(io.BytesIO(listing_bytes)).convert("RGB")
    candidate = Image.open(io.BytesIO(cand_bytes)).convert("RGB")
    listing.thumbnail((640, 480))
    candidate.thumbnail((640, 480))
    canvas = Image.new("RGB", (listing.width + candidate.width + 40, max(listing.height, candidate.height) + 90), (18, 18, 18))
    canvas.paste(listing, (10, 50))
    canvas.paste(candidate, (listing.width + 30, 50))
    draw = ImageDraw.Draw(canvas)

    def mark(image, origin, fp, color):
        if not fp.present or fp.centroid_x is None:
            return
        px = origin[0] + int(fp.centroid_x * image.width)
        py = origin[1] + int(fp.centroid_y * image.height)
        draw.ellipse((px - 6, py - 6, px + 6, py + 6), outline=color, width=2)
        if fp.house_centroid_x is not None:
            hx = origin[0] + int(fp.house_centroid_x * image.width)
            hy = origin[1] + int(fp.house_centroid_y * image.height)
            draw.rectangle((hx - 5, hy - 5, hx + 5, hy + 5), outline=(255, 210, 40), width=2)
            draw.line((hx, hy, px, py), fill=color, width=2)
        if fp.contour_image and len(fp.contour_image) >= 3:
            pts = [(origin[0] + int(x * image.width), origin[1] + int(y * image.height)) for x, y in fp.contour_image]
            draw.line(pts + [pts[0]], fill=color, width=2)

    if geometry:
        origin = (listing.width + 30, 50)
        min_lon, min_lat, max_lon, max_lat = parcel_bbox(geometry)
        pad = PADDING_METRES / 111_320
        bbox = (min_lon - pad, min_lat - pad, max_lon + pad, max_lat + pad)
        for ring in geometry.get("rings") or []:
            pts = []
            for lon, lat in ring:
                x = origin[0] + int((lon - bbox[0]) / max(bbox[2] - bbox[0], 1e-12) * candidate.width)
                y = origin[1] + int((bbox[3] - lat) / max(bbox[3] - bbox[1], 1e-12) * candidate.height)
                pts.append((x, y))
            if len(pts) >= 3:
                draw.line(pts + [pts[0]], fill=(255, 90, 90), width=2)
            break
    mark(listing, (10, 50), listing_fp, (0, 220, 255))
    mark(candidate, (listing.width + 30, 50), cand_fp, (80, 255, 120))
    draw.text((10, 10), f"Listing shape={listing_fp.shape_class} orient={listing_fp.orientation_deg}", fill=(230, 230, 230))
    draw.text((listing.width + 30, 10), f"{township} stand {stand} shape={cand_fp.shape_class}", fill=(230, 230, 230))
    dest.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(dest, quality=90)


def main() -> int:
    started = time.time()
    require_active_dataset(CORRECT_CARLSWALD_NORTH)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    dataset = json.loads(DATASET_JSON.read_text(encoding="utf-8"))
    parcels = [
        item
        for item in dataset["parcels"]
        if item.get("land_type") == "Erven"
        and item.get("class") not in {"non_residential"}
        and (item.get("area_sqm") or 0) < 8000
        and item.get("geometry")
        and item.get("stand_number")
        and not str(item["stand_number"]).startswith("RE/")
    ]
    print("TASK 5 — AGS tile cache")
    print(f"  candidate parcels after GIS pass 1: {len(parcels)} (excluded non-residential / huge remainders)")
    index = EstateTileIndex(TILE_CACHE, dataset["extent"], year=2023, profile_id="native15")
    stats = index.build()
    print(f"  tiles required: {stats.tiles_required}")
    print(f"  tiles downloaded: {stats.tiles_downloaded}")
    print(f"  tiles reused: {stats.tiles_reused}")
    print(f"  tiles failed: {stats.tiles_failed}")
    print(f"  tile runtime_ms: {stats.tile_fetch_time_ms:.0f}")
    CROP_DIR.mkdir(parents=True, exist_ok=True)
    crops = 0
    failures = 0
    crop_paths = {}
    for parcel in parcels:
        safe = str(parcel["stand_number"]).replace("/", "_")
        dest = CROP_DIR / f"{safe}_ags_aerial.jpg"
        if dest.is_file() and dest.stat().st_size > 500:
            crop_paths[parcel["stand_number"]] = dest
            crops += 1
            continue
        min_lon, min_lat, max_lon, max_lat = parcel_bbox(parcel["geometry"])
        tile = index.covering_tile(min_lon, min_lat, max_lon, max_lat)
        if tile and crop_parcel(tile, parcel["geometry"], dest):
            crop_paths[parcel["stand_number"]] = dest
            crops += 1
        else:
            failures += 1
    print(f"  parcel crops: {crops}")
    print(f"  imagery failures: {failures}")
    print(f"  imagery coverage: {crops}/{len(parcels)}")
    if crops < 20:
        print("BLOCKER: insufficient parcel imagery")
        return 1

    print("\nTASK 6 — listing 116978058 acquire (blind, no GT)")
    listing = None
    try:
        listing = fetch_listing(LISTING_URL, LISTING_ID)
        (OUTPUT / "listing_meta.json").write_text(
            json.dumps(listing.__dict__, indent=2),
            encoding="utf-8",
        )
    except Exception as exc:  # noqa: BLE001
        meta_path = OUTPUT / "listing_meta.json"
        if meta_path.is_file():
            print(f"  live fetch failed ({exc}); using cached listing metadata")
            raw = json.loads(meta_path.read_text(encoding="utf-8"))
            listing = fetch_listing.__annotations__.get("return")
            from backend.parsers.property24 import ListingData

            listing = ListingData(**raw)
        else:
            raise
    print(f"  title: {listing.title}")
    print(f"  estate: {listing.estate}")
    print(f"  property_type: {listing.property_type}")
    print(f"  stand_size: {listing.stand_size_sqm} ({listing.stand_size_raw})")
    print(f"  image urls found: {len(listing.image_urls)}")
    print(f"  video URLs: {listing.video_urls or None}")
    bodies = download_images(listing.image_urls, OUTPUT / "photos", LISTING_ID)
    photo_dir = OUTPUT / "photos"
    if photo_dir.is_dir():
        for path in sorted(photo_dir.glob("*.jpg")):
            bodies[path.stem] = path.read_bytes()
    print(f"  images acquired: {len(bodies)}")
    print(f"  video downloaded: NO")
    if not bodies:
        print("BLOCKER: no listing photographs")
        return 1

    print("\nListing visual fingerprint")
    scenes = {}
    retained = []
    for media_id, body in bodies.items():
        image = Image.open(io.BytesIO(body)).convert("RGB")
        scene = classify_scene(image)
        scenes[media_id] = scene
        if scene != "interior":
            retained.append(media_id)
    counts = Counter(scenes.values())
    print(f"  scene counts: {dict(counts)}")
    print(f"  retained exterior/identification frames: {len(retained)}")
    print(f"  aerial retained: {counts.get('aerial', 0)}")
    print(f"  pool_garden retained: {counts.get('pool_garden', 0)}")
    print(f"  driveway/garage retained: {counts.get('driveway_access', 0)}")

    pool_ids = [mid for mid in retained if scenes[mid] in {"pool_garden", "aerial", "rear_elevation", "contextual"}]
    if not pool_ids:
        pool_ids = list(retained)
    frames = [extract_pool_geometry(bodies[mid], media_id=mid) for mid in pool_ids]
    listing_pool = consensus_pool_fingerprint(frames)
    print(f"  pool-positive frames: {sum(1 for item in frames if item.present)}/{len(frames)}")
    print(f"  present={listing_pool.present} shape={listing_pool.shape_class} aspect={listing_pool.aspect_ratio}")
    print(f"  orientation={listing_pool.orientation_deg} curved={listing_pool.curved_section_count}")
    print(f"  pool-house dist={listing_pool.pool_to_house_dist} dx={listing_pool.pool_to_house_dx} dy={listing_pool.pool_to_house_dy}")
    (OUTPUT / "listing_pool_fingerprint.json").write_text(
        json.dumps(listing_pool.model_dump(mode="json"), indent=2), encoding="utf-8"
    )
    listing_layout = None
    aerial_ids = [mid for mid in retained if scenes[mid] == "aerial"]
    layout_ids = aerial_ids or pool_ids[:6]
    layouts = [extract_structural_layout(bodies[mid]) for mid in layout_ids]
    if layouts:
        listing_layout = layouts[0]

    listing_vecs = {mid: encode_image(Image.open(io.BytesIO(bodies[mid])).convert("RGB")) for mid in retained}
    aerial_vecs = [listing_vecs[mid] for mid in aerial_ids if mid in listing_vecs]
    exterior_vecs = [
        listing_vecs[mid]
        for mid in retained
        if scenes[mid] in {"front_elevation", "rear_elevation", "contextual", "driveway_access"}
    ]
    video_vecs: list = []

    print("\nTASK 6/7 — visual-first rank on corrected estate only")
    scored = []
    pool_by = {}
    bytes_by = {}
    parcel_by = {item["stand_number"]: item for item in parcels}
    for parcel in parcels:
        stand = parcel["stand_number"]
        path = crop_paths.get(stand)
        if path is None:
            continue
        body = path.read_bytes()
        bytes_by[stand] = body
        image = Image.open(io.BytesIO(body)).convert("RGB")
        mask = parcel_mask(image.size, parcel["geometry"], None)
        cand_pool = extract_pool_geometry(body, media_id=f"cand-{stand}", parcel_mask=mask)
        pool_by[stand] = cand_pool
        compared = pool_geometry_similarity(listing_pool, cand_pool)
        cand_layout = extract_structural_layout(body)
        structural = structural_layout_similarity(listing_layout, cand_layout) if listing_layout else None
        size_score = stand_size_support(listing.stand_size_sqm, parcel.get("area_sqm"))
        scored.append(
            {
                "stand_number": stand,
                "township": parcel["township"],
                "area_sqm": parcel.get("area_sqm"),
                "pool_geometry_similarity": compared.get("pool_geometry_similarity"),
                "pool_house_similarity": compared.get("pool_house_similarity"),
                "structural_layout_similarity": structural,
                "driveway_similarity": structural,
                "stand_size_contribution": round(0.05 * size_score, 4),
                "size_score": size_score,
                "contradiction": compared.get("contradiction"),
                "pool_present": cand_pool.present,
            }
        )

    obvious = sum(1 for row in scored if listing_pool.present and row["contradiction"] == "listing_has_pool_candidate_has_none")
    print(f"  Pass 1 listing-has-pool vs candidate-has-none: {obvious}/{len(scored)}")
    pool_ranked = sorted(
        scored,
        key=lambda row: (-(row["pool_geometry_similarity"] or -1), -(row["pool_house_similarity"] or -1), row["stand_number"]),
    )
    shortlist = pool_ranked[:40]
    short_ids = {row["stand_number"] for row in shortlist}
    print("  Pass 2 Top 15 by pool geometry:")
    for i, row in enumerate(shortlist[:15], 1):
        print(
            f"  {i:2d} {row['township']:<18} {row['stand_number']:>8} "
            f"geom={row['pool_geometry_similarity']} house={row['pool_house_similarity']}"
        )

    final_rows = []
    for row in scored:
        aerial = exterior = video = None
        if row["stand_number"] in short_ids:
            image = Image.open(io.BytesIO(bytes_by[row["stand_number"]])).convert("RGB")
            cand_vecs = [encode_image(image)]
            aerial = mean_top_similarity(aerial_vecs, cand_vecs)
            exterior = mean_top_similarity(exterior_vecs, cand_vecs)
            video = mean_top_similarity(video_vecs, cand_vecs)
        total = combined_score(
            pool_geom=row["pool_geometry_similarity"],
            pool_house=row["pool_house_similarity"],
            structural=row["structural_layout_similarity"],
            aerial=aerial,
            video=video,
            exterior=exterior,
            driveway=row["driveway_similarity"],
            gis=0.5,
            stand_size=row["size_score"],
            contradiction=row["contradiction"],
        )
        positives = []
        if row["pool_geometry_similarity"]:
            positives.append(f"pool_geom {row['pool_geometry_similarity']:.3f}")
        if row["pool_house_similarity"]:
            positives.append(f"pool-house {row['pool_house_similarity']:.3f}")
        if exterior:
            positives.append(f"exterior {exterior:.3f}")
        final_rows.append(
            {
                **row,
                "total_score": total,
                "aerial_similarity": None if aerial is None else round(aerial, 4),
                "exterior_similarity": None if exterior is None else round(exterior, 4),
                "video_similarity": None if video is None else round(video, 4),
                "strongest_match": "; ".join(positives[:3]),
            }
        )

    frozen = sorted(final_rows, key=lambda row: (-row["total_score"], row["stand_number"]))
    for index, row in enumerate(frozen, start=1):
        row["rank"] = index
    top10, confidence = freeze_final_candidates(frozen, limit=FINAL_CANDIDATE_LIMIT)
    print(f"\nFROZEN TOP {FINAL_CANDIDATE_LIMIT} (SUMMERSET EXT.6 + EXT.13 only)")
    if confidence.get("low_confidence"):
        print(f"  {confidence['message']}")
        print(
            f"  top1-top2 gap={confidence['top1_to_top2_gap']}  "
            f"top1-top10 gap={confidence['top1_to_top10_gap']}  "
            f"next excluded={confidence.get('next_excluded_stand')} "
            f"({confidence.get('next_excluded_score')})"
        )
    print(
        f"{'rk':>3} {'stand':>10} {'township':<18} {'area':>7} {'total':>7} "
        f"{'pool':>7} {'p-hse':>7} {'roof':>7} {'ext':>7} {'air':>7} {'vid':>7}"
    )
    def fmt(v):
        return "-" if v is None else f"{v:.3f}"
    for row in top10:
        print(
            f"{row['rank']:3d} {row['stand_number']:>10} {row['township']:<18} "
            f"{int(row['area_sqm'] or 0):7d} {row['total_score']:7.3f} "
            f"{fmt(row['pool_geometry_similarity']):>7} {fmt(row['pool_house_similarity']):>7} "
            f"{fmt(row['structural_layout_similarity']):>7} {fmt(row['exterior_similarity']):>7} "
            f"{fmt(row['aerial_similarity']):>7} {fmt(row['video_similarity']):>7}  "
            f"{row['strongest_match']}  {row['contradiction'] or 'none'}"
        )

    print("\nTOP 10 DETAIL")
    for row in top10:
        print(f"  #{row['rank']} {row['township']} stand {row['stand_number']} score={row['total_score']:.3f}")
        print(f"     GIS area {row['area_sqm']}  match: {row['strongest_match']}")
        print(f"     contradiction: {row['contradiction'] or 'none'}")

    print("\nTASK 8 — visual proof (all Top 10)")
    left_id = listing_pool.evidence_media_id if listing_pool.evidence_media_id in bodies else retained[0]
    left_body = bodies[left_id]
    left_fp = extract_pool_geometry(left_body, media_id="listing-panel")
    for row in top10:
        stand = row["stand_number"]
        dest = OUTPUT / f"top10_stand_{stand.replace('/', '_')}.jpg"
        draw_panel(
            left_body,
            bytes_by[stand],
            left_fp if left_fp.present else listing_pool,
            pool_by[stand],
            stand,
            row["township"],
            dest,
            geometry=parcel_by[stand]["geometry"],
        )
        print(f"  wrote {dest}")

    payload = {
        "listing_id": LISTING_ID,
        "listing_url": LISTING_URL,
        "dataset_id": CORRECT_CARLSWALD_NORTH,
        "townships": dataset["townships"],
        "excluded_wrong_mapping": "carlswald_north_001 / CARLSWALD ESTATE*",
        "summerset_ext_2": "not_present_in_coj_gis",
        "tile_stats": vars(stats),
        "parcel_crops": crops,
        "imagery_failures": failures,
        "candidate_parcels": len(parcels),
        "listing_pool": listing_pool.model_dump(mode="json"),
        "scene_counts": dict(counts),
        "images_acquired": len(bodies),
        "video_downloaded": "NO",
        "address_gps_erf_used_in_ranking": False,
        "previous_stand_59_used": False,
        "ground_truth_consulted": False,
        "production_matcher_modified": False,
        "final_candidate_limit": FINAL_CANDIDATE_LIMIT,
        "success_standard": SUCCESS_STANDARD,
        "confidence": confidence,
        "frozen_top10": top10,
        "runtime_s": round(time.time() - started, 1),
    }
    out = OUTPUT / "latest.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nFrozen ranking written to {out}")
    print("Ground truth was not consulted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
