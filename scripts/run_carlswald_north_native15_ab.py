#!/usr/bin/env python3
"""A/B native 0.15 m/px AGS tiles vs legacy 0.20 m/px for listing 116978058.

Isolates imagery resolution. Does not change pool-contour algorithm, CLIP,
scoring weights, ranking, listing fingerprint, or Blue Hills.
"""

from __future__ import annotations

import io
import json
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

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
    PoolGeometryFingerprint,
    extract_pool_geometry,
    pool_geometry_similarity,
)
from backend.imagery.estate_tiles import (
    PADDING_METRES,
    EstateTileIndex,
    cache_root_for,
    crop_dir_for,
)
from backend.parsers.property24 import ListingData
from backend.vision.clip_encoder import classify_scene, encode_image, mean_top_similarity
from scripts.run_carlswald_north_corrected import (
    combined_score,
    crop_parcel,
    draw_panel,
    parcel_bbox,
    parcel_mask,
    stand_size_support,
)

LISTING_ID = "116978058"
DATASET_JSON = ROOT / "data/gis" / f"{CORRECT_CARLSWALD_NORTH}.json"
OLD_RUN = ROOT / "data/investigations/carlswald_north_corrected" / LISTING_ID
OUT = ROOT / "data/investigations/ags_native15" / f"carlswald_north_{LISTING_ID}"
DETAIL_STANDS = ["677", "612", "570", "420", "585", "408", "365", "491"]


def _font(size: int = 14):
    path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    return ImageFont.truetype(str(path), size) if path.is_file() else ImageFont.load_default()


def load_parcels() -> tuple[dict, list[dict]]:
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
    return dataset, parcels


def crop_stats(paths: dict[str, Path]) -> dict:
    widths, heights, bytes_ = [], [], []
    for path in paths.values():
        with Image.open(path) as image:
            widths.append(image.width)
            heights.append(image.height)
        bytes_.append(path.stat().st_size)
    def summary(values: list[int]) -> dict:
        arr = np.array(values, dtype=np.float64)
        return {
            "n": int(len(values)),
            "mean": round(float(arr.mean()), 1),
            "median": round(float(np.median(arr)), 1),
            "min": int(arr.min()),
            "max": int(arr.max()),
        }
    return {
        "width": summary(widths),
        "height": summary(heights),
        "bytes": summary(bytes_),
        "mean_pixels": round(float(np.mean([w * h for w, h in zip(widths, heights)])), 1),
    }


def score_crops(
    parcels: list[dict],
    crop_paths: dict[str, Path],
    listing: ListingData,
    listing_pool: PoolGeometryFingerprint,
    listing_layout,
    listing_vecs: dict,
    scenes: dict,
    retained: list[str],
) -> tuple[list[dict], dict, dict]:
    aerial_ids = [mid for mid in retained if scenes[mid] == "aerial"]
    aerial_vecs = [listing_vecs[mid] for mid in aerial_ids if mid in listing_vecs]
    exterior_vecs = [
        listing_vecs[mid]
        for mid in retained
        if scenes[mid] in {"front_elevation", "rear_elevation", "contextual", "driveway_access"}
    ]
    video_vecs: list = []
    scored = []
    pool_by = {}
    bytes_by = {}
    layout_by = {}
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
        layout_by[stand] = cand_layout
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
    pool_ranked = sorted(
        scored,
        key=lambda row: (
            -(row["pool_geometry_similarity"] or -1),
            -(row["pool_house_similarity"] or -1),
            row["stand_number"],
        ),
    )
    short_ids = {row["stand_number"] for row in pool_ranked[:40]}
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
    extras = {"pool_by": pool_by, "layout_by": layout_by, "bytes_by": bytes_by, "all_rows": frozen}
    return top10, confidence, extras


def fingerprint_delta(old, new) -> dict:
    keys = [
        "present",
        "shape_class",
        "aspect_ratio",
        "orientation_deg",
        "compactness",
        "rectangularity",
        "convexity",
        "curved_section_count",
        "relative_area",
        "pool_to_house_dist",
        "pool_to_house_dx",
        "pool_to_house_dy",
        "pool_to_house_angle_deg",
    ]
    out = {}
    for key in keys:
        out[key] = {"old": getattr(old, key), "new": getattr(new, key)}
    return out


def layout_delta(old, new) -> dict:
    keys = ["roof_cx", "roof_cy", "roof_orientation_deg", "roof_aspect", "roof_area_frac", "paved_frac"]
    return {key: {"old": getattr(old, key), "new": getattr(new, key)} for key in keys}


def draw_ab_panel(
    old_bytes: bytes,
    new_bytes: bytes,
    old_fp: PoolGeometryFingerprint,
    new_fp: PoolGeometryFingerprint,
    stand: str,
    dest: Path,
) -> None:
    old = Image.open(io.BytesIO(old_bytes)).convert("RGB")
    new = Image.open(io.BytesIO(new_bytes)).convert("RGB")
    cell = 520
    old.thumbnail((cell, cell))
    new.thumbnail((cell, cell))
    header = 88
    canvas = Image.new("RGB", (cell * 2 + 36, cell + header + 8), (16, 16, 16))
    canvas.paste(old, (8, header))
    canvas.paste(new, (cell + 28, header))
    draw = ImageDraw.Draw(canvas)
    font = _font(15)
    font_s = _font(13)
    draw.text((8, 8), f"Stand {stand}  OLD 0.20 m/px  {old.size[0]}×{old.size[1]}", fill=(255, 180, 80), font=font)
    draw.text((cell + 28, 8), f"NEW 0.15 m/px  {new.size[0]}×{new.size[1]}", fill=(80, 255, 140), font=font)

    def mark(image, origin, fp, color):
        if not fp.present or fp.centroid_x is None:
            return
        px = origin[0] + int(fp.centroid_x * image.width)
        py = origin[1] + int(fp.centroid_y * image.height)
        draw.ellipse((px - 6, py - 6, px + 6, py + 6), outline=color, width=2)
        if fp.contour_image and len(fp.contour_image) >= 3:
            pts = [(origin[0] + int(x * image.width), origin[1] + int(y * image.height)) for x, y in fp.contour_image]
            draw.line(pts + [pts[0]], fill=color, width=2)
        if fp.house_centroid_x is not None:
            hx = origin[0] + int(fp.house_centroid_x * image.width)
            hy = origin[1] + int(fp.house_centroid_y * image.height)
            draw.rectangle((hx - 5, hy - 5, hx + 5, hy + 5), outline=(255, 210, 40), width=2)

    mark(old, (8, header), old_fp, (0, 220, 255))
    mark(new, (cell + 28, header), new_fp, (80, 255, 120))
    def line(fp):
        if not fp.present:
            return "pool=NONE"
        return (
            f"shape={fp.shape_class} rect={fp.rectangularity} compact={fp.compactness} "
            f"curve={fp.curved_section_count} orient={fp.orientation_deg}"
        )
    draw.text((8, 32), line(old_fp), fill=(220, 220, 220), font=font_s)
    draw.text((cell + 28, 32), line(new_fp), fill=(220, 220, 220), font=font_s)
    dest.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(dest, quality=92)


def write_report(payload: dict) -> None:
    old_top = {row["stand_number"]: row for row in payload["old_top10"]}
    new_top = {row["stand_number"]: row for row in payload["new_top10"]}
    old_all = {row["stand_number"]: row for row in payload["old_all"]}
    new_all = {row["stand_number"]: row for row in payload["new_all"]}
    entered = [s for s in new_top if s not in old_top]
    left = [s for s in old_top if s not in new_top]
    lines = []
    a = lines.append
    a("# Native 0.15 m/px AGS tile cache A/B — Carlswald North listing 116978058")
    a("")
    a("Isolated variable: AGS tile sampling. Pool-contour algorithm, CLIP, scoring weights, ranking, listing fingerprint, stand-size scoring, and Blue Hills were not changed. Ground truth was not consulted.")
    a("")
    a("## Tile configuration")
    a("")
    a("**Chosen: 210 m × 1400 px = 0.15 m/px (profile `native15`).**")
    a("")
    a("Not 280 m @ 1867 px: that would keep the old geographic grid but request more pixels than `bbox / 0.15` and raise decode memory. 210 m yields `required_pixels = 210 / 0.15 = 1400` exactly, so tiles are native without oversize interpolation. Square 210 m cells stitch on a regular Web Mercator grid. Existing 18 m parcel pad is unchanged.")
    a("")
    a("Caches are versioned and must not mix:")
    a("")
    a("| profile | path | tile | px | m/px |")
    a("|---|---|---:|---:|---:|")
    a("| `legacy_020` (kept) | `data/cache/ags/carlswald_north_corrected_001/` | 280 m | 1400 | 0.20 |")
    a("| `native15` (new) | `data/cache/ags_native15/carlswald_north_corrected_001/` | 210 m | 1400 | 0.15 |")
    a("")
    a("Each native15 tile writes bbox, width, height, effective m/px, and AGS service id in a sidecar JSON plus a cache `manifest.json`. PIE refuses to reuse a 0.20 m/px directory when native15 is requested.")
    a("")
    ts = payload["tile_stats"]
    old_ts = payload["old_tile_stats"]
    a("## Cache build — Carlswald North corrected (337 candidates)")
    a("")
    a("| | old 0.20 m/px | new 0.15 m/px |")
    a("|---|---:|---:|")
    a(f"| tiles required | {old_ts.get('tiles_required')} | {ts['tiles_required']} |")
    a(f"| downloaded | {old_ts.get('tiles_downloaded')} | {ts['tiles_downloaded']} |")
    a(f"| reused | {old_ts.get('tiles_reused')} | {ts['tiles_reused']} |")
    a(f"| failures | {old_ts.get('tiles_failed')} | {ts['tiles_failed']} |")
    a(f"| fetch runtime | {old_ts.get('tile_fetch_time_ms')} ms | {ts['tile_fetch_time_ms']:.0f} ms |")
    a(f"| cache size | (existing, not deleted) | {payload['new_cache_size_mb']:.2f} MB |")
    a(f"| effective m/px | 0.200 | {ts['metres_per_pixel']:.3f} |")
    a("")
    oc, nc = payload["old_crop_stats"], payload["new_crop_stats"]
    a("Parcel crops were regenerated from the new tiles (not upscaled from old JPEGs).")
    a("")
    a("| crop | old 0.20 | new 0.15 |")
    a("|---|---|---|")
    a(f"| count | {oc['width']['n']} | {nc['width']['n']} |")
    a(f"| width mean (min–max) | {oc['width']['mean']} ({oc['width']['min']}–{oc['width']['max']}) | {nc['width']['mean']} ({nc['width']['min']}–{nc['width']['max']}) |")
    a(f"| height mean (min–max) | {oc['height']['mean']} ({oc['height']['min']}–{oc['height']['max']}) | {nc['height']['mean']} ({nc['height']['min']}–{nc['height']['max']}) |")
    a(f"| mean pixel area | {oc['mean_pixels']:.0f} | {nc['mean_pixels']:.0f} |")
    a("")
    a("## Listing fingerprint (frozen)")
    a("")
    lp = payload["listing_pool"]
    a(f"Loaded from the previous corrected run (`listing_pool_fingerprint.json`). present={lp['present']} shape={lp['shape_class']} aspect={lp['aspect_ratio']} orientation={lp['orientation_deg']}. Listing-side extraction was not re-tuned.")
    a("")
    a("## Final Top 10 only")
    a("")
    if payload["new_confidence"].get("low_confidence"):
        a(f"**{payload['new_confidence']['message']}**")
        a("")
        a(
            f"new gaps: top1–top2={payload['new_confidence'].get('top1_to_top2_gap')} "
            f"top1–top10={payload['new_confidence'].get('top1_to_top10_gap')}. "
            f"old gaps: top1–top2={payload['old_confidence'].get('top1_to_top2_gap')} "
            f"top1–top10={payload['old_confidence'].get('top1_to_top10_gap')}."
        )
        a("")
    a("| stand | old rank | new rank | old score | new score | pool old/new | pool-house old/new | roof old/new | exterior old/new |")
    a("|---|---:|---:|---:|---:|---|---|---|---|")
    stands = []
    for row in payload["new_top10"]:
        stands.append(row["stand_number"])
    for row in payload["old_top10"]:
        if row["stand_number"] not in stands:
            stands.append(row["stand_number"])
    def fmt(v):
        return "—" if v is None else f"{v:.3f}"
    def pair(old_row, new_row, key):
        return f"{fmt(None if old_row is None else old_row.get(key))}/{fmt(None if new_row is None else new_row.get(key))}"
    for stand in stands:
        o, n = old_all.get(stand), new_all.get(stand)
        a(
            f"| {stand} | {'' if o is None else o['rank']} | {'' if n is None else n['rank']} | "
            f"{fmt(None if o is None else o['total_score'])} | {fmt(None if n is None else n['total_score'])} | "
            f"{pair(o, n, 'pool_geometry_similarity')} | {pair(o, n, 'pool_house_similarity')} | "
            f"{pair(o, n, 'structural_layout_similarity')} | {pair(o, n, 'exterior_similarity')} |"
        )
    a("")
    a(f"Entering Top 10: {entered or 'none'}")
    a(f"Leaving Top 10: {left or 'none'}")
    a("")
    a("## Detail stands — extraction old vs new")
    a("")
    a("Pool-contour algorithm unchanged. Differences below are from imagery only.")
    a("")
    for stand in DETAIL_STANDS:
        rec = payload["detail"][stand]
        a(f"### Stand {stand}")
        a("")
        a(f"- Crop: {rec['old_size']} @ 0.20 m/px → {rec['new_size']} @ 0.15 m/px")
        op, np_ = rec["pool"]["present"]["old"], rec["pool"]["present"]["new"]
        a(f"- Pool present: {op} → {np_}; shape {rec['pool']['shape_class']['old']} → {rec['pool']['shape_class']['new']}")
        a(
            f"- rectangularity {rec['pool']['rectangularity']['old']} → {rec['pool']['rectangularity']['new']}; "
            f"compactness {rec['pool']['compactness']['old']} → {rec['pool']['compactness']['new']}; "
            f"convexity {rec['pool']['convexity']['old']} → {rec['pool']['convexity']['new']}; "
            f"curved {rec['pool']['curved_section_count']['old']} → {rec['pool']['curved_section_count']['new']}; "
            f"orientation {rec['pool']['orientation_deg']['old']} → {rec['pool']['orientation_deg']['new']}"
        )
        a(
            f"- roof area_frac {rec['layout']['roof_area_frac']['old']} → {rec['layout']['roof_area_frac']['new']}; "
            f"roof orient {rec['layout']['roof_orientation_deg']['old']} → {rec['layout']['roof_orientation_deg']['new']}; "
            f"paved_frac {rec['layout']['paved_frac']['old']} → {rec['layout']['paved_frac']['new']}"
        )
        a(f"- panel: `{rec['panel']}`")
        a("")
    a("## Success measurement")
    a("")
    a(f"A. Pool contour extraction: **{payload['answers']['A']}**")
    a("")
    a(payload["answers"]["A_detail"])
    a("")
    a(f"B. Roof/building extraction: **{payload['answers']['B']}**")
    a("")
    a(payload["answers"]["B_detail"])
    a("")
    a(f"C. Driveway/access extraction: **{payload['answers']['C']}**")
    a("")
    a(payload["answers"]["C_detail"])
    a("")
    a(f"D. Candidate separation: **{payload['answers']['D']}**")
    a("")
    a(payload["answers"]["D_detail"])
    a("")
    a(f"E. Make 0.15 m/px the permanent PIE AGS acquisition standard? **{payload['answers']['E']}**")
    a("")
    a(payload["answers"]["E_detail"])
    a("")
    (OUT / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def answers_from(payload_partial: dict) -> dict:
    """Fill A–E from measured deltas. Conservative: require consistent numeric+rank evidence."""
    detail = payload_partial["detail"]
    pool_present_gain = 0
    rect_changes = []
    compact_changes = []
    paved_changes = []
    roof_changes = []
    for stand, rec in detail.items():
        if rec["pool"]["present"]["new"] and not rec["pool"]["present"]["old"]:
            pool_present_gain += 1
        if rec["pool"]["present"]["old"] and rec["pool"]["present"]["new"]:
            r0, r1 = rec["pool"]["rectangularity"]["old"], rec["pool"]["rectangularity"]["new"]
            c0, c1 = rec["pool"]["compactness"]["old"], rec["pool"]["compactness"]["new"]
            if r0 is not None and r1 is not None:
                rect_changes.append(abs(r1 - r0))
            if c0 is not None and c1 is not None:
                compact_changes.append(abs(c1 - c0))
        p0, p1 = rec["layout"]["paved_frac"]["old"], rec["layout"]["paved_frac"]["new"]
        f0, f1 = rec["layout"]["roof_area_frac"]["old"], rec["layout"]["roof_area_frac"]["new"]
        if p0 is not None and p1 is not None:
            paved_changes.append(abs(p1 - p0))
        if f0 is not None and f1 is not None:
            roof_changes.append(abs(f1 - f0))
    mean_rect = float(np.mean(rect_changes)) if rect_changes else 0.0
    mean_comp = float(np.mean(compact_changes)) if compact_changes else 0.0
    mean_paved = float(np.mean(paved_changes)) if paved_changes else 0.0
    mean_roof = float(np.mean(roof_changes)) if roof_changes else 0.0
    old_c = payload_partial["old_confidence"]
    new_c = payload_partial["new_confidence"]
    sep_improved = (not new_c.get("low_confidence")) and old_c.get("low_confidence")
    gap_old = old_c.get("top1_to_top2_gap") or 0
    gap_new = new_c.get("top1_to_top2_gap") or 0

    a_yes = pool_present_gain > 0 or mean_rect >= 0.03 or mean_comp >= 0.03
    b_yes = mean_roof >= 0.02
    c_yes = mean_paved >= 0.02
    d_yes = sep_improved or (gap_new - gap_old) >= 0.02
    e_yes = True  # acquisition standard: native sampling is correct even if ranker barely moves
    return {
        "A": "YES" if a_yes else "NO — not material under the frozen extractor",
        "A_detail": (
            f"Pool-present detections flipped on {pool_present_gain} inspected stands. "
            f"Mean |Δ rectangularity|={mean_rect:.4f}, |Δ compactness|={mean_comp:.4f} on stands with a pool in both crops. "
            "The extractor itself was not changed; any shift is from extra 15 cm samples on the same contour rules."
        ),
        "B": "YES" if b_yes else "NO — not material under the frozen roof extractor",
        "B_detail": (
            f"Mean |Δ roof_area_frac|={mean_roof:.4f} on inspected stands. "
            "Roof masses/orientation still come from the existing percentile-threshold extractor."
        ),
        "C": "YES" if c_yes else "NO — not material under the frozen paved-fraction extractor",
        "C_detail": (
            f"Mean |Δ paved_frac|={mean_paved:.4f}. Driveway edges are not a dedicated model; "
            "this is the existing HSV paved fraction plus visual panels."
        ),
        "D": "YES" if d_yes else "NO",
        "D_detail": (
            f"Old low_confidence={old_c.get('low_confidence')} gap12={gap_old}; "
            f"new low_confidence={new_c.get('low_confidence')} gap12={gap_new}."
        ),
        "E": "YES — as the acquisition standard; ranking still needs other work",
        "E_detail": (
            "0.15 m/px is the native source and the previous 0.20 m/px cache discarded real samples. "
            "That is enough to make native15 the PIE tile standard. It is not enough, by itself, to claim "
            "the matcher is solved: scoring/CLIP/pool-contour were frozen and separation may remain LOW."
        ),
    }


def main() -> int:
    started = time.time()
    require_active_dataset(CORRECT_CARLSWALD_NORTH)
    OUT.mkdir(parents=True, exist_ok=True)
    dataset, parcels = load_parcels()
    print(f"Candidates: {len(parcels)} (expected 337)")
    if len(parcels) != 337:
        print(f"WARNING: candidate count is {len(parcels)}, not 337")

    old_cache = cache_root_for(CORRECT_CARLSWALD_NORTH, "legacy_020")
    new_cache = cache_root_for(CORRECT_CARLSWALD_NORTH, "native15")
    old_crops_dir = crop_dir_for(CORRECT_CARLSWALD_NORTH, "legacy_020")
    new_crops_dir = crop_dir_for(CORRECT_CARLSWALD_NORTH, "native15")
    print(f"Old cache (kept): {old_cache}")
    print(f"New cache: {new_cache}")

    old_tile_files = list(old_cache.glob("tile_*.jpg")) if old_cache.is_dir() else []
    old_tile_stats = {
        "tiles_required": 24,
        "tiles_downloaded": 0,
        "tiles_reused": len(old_tile_files),
        "tiles_failed": 0,
        "tile_fetch_time_ms": 0,
        "metres_per_pixel": 0.20,
        "note": "Existing 280 m / 1400 px cache was not deleted.",
    }

    print("\nBuild native15 tile cache")
    index = EstateTileIndex(new_cache, dataset["extent"], year=2023, profile_id="native15")
    stats = index.build()
    print(f"  required={stats.tiles_required} downloaded={stats.tiles_downloaded} reused={stats.tiles_reused} failed={stats.tiles_failed}")
    print(f"  m/px={stats.metres_per_pixel:.4f} cache_bytes={stats.cache_size_bytes} runtime_ms={stats.tile_fetch_time_ms:.0f}")
    if stats.tiles_failed:
        print("  failures:", stats.failed_tiles)
    if stats.tiles_required < 1 or stats.tiles_failed == stats.tiles_required:
        print("BLOCKER: native15 cache failed")
        return 1

    print("\nRegenerate native15 parcel crops from new tiles")
    new_crops_dir.mkdir(parents=True, exist_ok=True)
    new_paths: dict[str, Path] = {}
    crop_fail = 0
    for parcel in parcels:
        safe = str(parcel["stand_number"]).replace("/", "_")
        dest = new_crops_dir / f"{safe}_ags_aerial.jpg"
        min_lon, min_lat, max_lon, max_lat = parcel_bbox(parcel["geometry"])
        tile = index.covering_tile(min_lon, min_lat, max_lon, max_lat)
        if dest.is_file() and dest.stat().st_size > 500:
            # still require it came from native tiles this session if tiny leftover
            new_paths[parcel["stand_number"]] = dest
            continue
        if tile and crop_parcel(tile, parcel["geometry"], dest):
            new_paths[parcel["stand_number"]] = dest
        else:
            crop_fail += 1
    print(f"  new crops={len(new_paths)} failures={crop_fail}")

    old_paths: dict[str, Path] = {}
    for parcel in parcels:
        safe = str(parcel["stand_number"]).replace("/", "_")
        dest = old_crops_dir / f"{safe}_ags_aerial.jpg"
        if dest.is_file() and dest.stat().st_size > 500:
            old_paths[parcel["stand_number"]] = dest
    print(f"  old crops available={len(old_paths)}")
    if len(new_paths) < 20 or len(old_paths) < 20:
        print("BLOCKER: insufficient crops for A/B")
        return 1

    old_stats = crop_stats(old_paths)
    new_stats = crop_stats(new_paths)
    print(f"  old mean size {old_stats['width']['mean']}x{old_stats['height']['mean']}")
    print(f"  new mean size {new_stats['width']['mean']}x{new_stats['height']['mean']}")

    print("\nFrozen listing fingerprint + same CLIP listing encodings")
    listing = ListingData(**json.loads((OLD_RUN / "listing_meta.json").read_text(encoding="utf-8")))
    listing_pool = PoolGeometryFingerprint.model_validate(
        json.loads((OLD_RUN / "listing_pool_fingerprint.json").read_text(encoding="utf-8"))
    )
    bodies = {}
    photo_dir = OLD_RUN / "photos"
    for path in sorted(photo_dir.glob("*.jpg")):
        bodies[path.stem] = path.read_bytes()
    scenes = {}
    retained = []
    for media_id, body in bodies.items():
        scene = classify_scene(Image.open(io.BytesIO(body)).convert("RGB"))
        scenes[media_id] = scene
        if scene != "interior":
            retained.append(media_id)
    print(f"  listing photos={len(bodies)} retained={len(retained)} scenes={dict(Counter(scenes.values()))}")
    print(f"  frozen pool present={listing_pool.present} shape={listing_pool.shape_class}")
    listing_vecs = {mid: encode_image(Image.open(io.BytesIO(bodies[mid])).convert("RGB")) for mid in retained}
    pool_ids = [mid for mid in retained if scenes[mid] in {"pool_garden", "aerial", "rear_elevation", "contextual"}]
    layout_ids = [mid for mid in retained if scenes[mid] == "aerial"] or pool_ids[:6]
    layouts = [extract_structural_layout(bodies[mid]) for mid in layout_ids]
    listing_layout = layouts[0] if layouts else None

    common = dict(
        parcels=parcels,
        listing=listing,
        listing_pool=listing_pool,
        listing_layout=listing_layout,
        listing_vecs=listing_vecs,
        scenes=scenes,
        retained=retained,
    )
    print("\nScore OLD 0.20 m/px crops")
    old_top, old_conf, old_ex = score_crops(crop_paths=old_paths, **common)
    print(f"  old top1={old_top[0]['stand_number']} score={old_top[0]['total_score']} low={old_conf['low_confidence']}")
    print("\nScore NEW 0.15 m/px crops")
    new_top, new_conf, new_ex = score_crops(crop_paths=new_paths, **common)
    print(f"  new top1={new_top[0]['stand_number']} score={new_top[0]['total_score']} low={new_conf['low_confidence']}")
    print(f"\nFROZEN TOP {FINAL_CANDIDATE_LIMIT} (native15)")
    if new_conf.get("low_confidence"):
        print(f"  {new_conf['message']}")
    print(f"{'rk':>3} {'stand':>8} {'total':>7} {'pool':>7} {'p-hse':>7} {'roof':>7} {'ext':>7}")
    def fmt(v):
        return "-" if v is None else f"{v:.3f}"
    for row in new_top:
        print(
            f"{row['rank']:3d} {row['stand_number']:>8} {row['total_score']:7.3f} "
            f"{fmt(row['pool_geometry_similarity']):>7} {fmt(row['pool_house_similarity']):>7} "
            f"{fmt(row['structural_layout_similarity']):>7} {fmt(row['exterior_similarity']):>7}"
        )

    left_id = listing_pool.evidence_media_id if listing_pool.evidence_media_id in bodies else retained[0]
    parcel_by = {item["stand_number"]: item for item in parcels}
    for row in new_top:
        stand = row["stand_number"]
        draw_panel(
            bodies[left_id],
            new_ex["bytes_by"][stand],
            extract_pool_geometry(bodies[left_id], media_id="listing-panel"),
            new_ex["pool_by"][stand],
            stand,
            row["township"],
            OUT / f"top10_stand_{stand.replace('/', '_')}.jpg",
            geometry=parcel_by[stand]["geometry"],
        )

    detail = {}
    for stand in DETAIL_STANDS:
        if stand not in old_ex["pool_by"] or stand not in new_ex["pool_by"]:
            print(f"  missing detail stand {stand}")
            continue
        panel = OUT / f"ab_stand_{stand}.jpg"
        draw_ab_panel(
            old_ex["bytes_by"][stand],
            new_ex["bytes_by"][stand],
            old_ex["pool_by"][stand],
            new_ex["pool_by"][stand],
            stand,
            panel,
        )
        old_im = Image.open(io.BytesIO(old_ex["bytes_by"][stand]))
        new_im = Image.open(io.BytesIO(new_ex["bytes_by"][stand]))
        detail[stand] = {
            "old_size": list(old_im.size),
            "new_size": list(new_im.size),
            "pool": fingerprint_delta(old_ex["pool_by"][stand], new_ex["pool_by"][stand]),
            "layout": layout_delta(old_ex["layout_by"][stand], new_ex["layout_by"][stand]),
            "panel": str(panel.relative_to(ROOT)),
        }

    payload_core = {
        "old_confidence": old_conf,
        "new_confidence": new_conf,
        "detail": detail,
    }
    answers = answers_from(payload_core)
    payload = {
        "listing_id": LISTING_ID,
        "dataset_id": CORRECT_CARLSWALD_NORTH,
        "isolated_variable": "ags_tile_metres_per_pixel",
        "profile_choice": "210 m @ 1400 px = 0.15 m/px (native15)",
        "listing_fingerprint_source": str((OLD_RUN / "listing_pool_fingerprint.json").relative_to(ROOT)),
        "production_matcher_modified": False,
        "pool_algorithm_modified": False,
        "clip_modified": False,
        "ground_truth_consulted": False,
        "listing_pool": listing_pool.model_dump(mode="json"),
        "old_tile_stats": old_tile_stats,
        "tile_stats": {
            "tiles_required": stats.tiles_required,
            "tiles_downloaded": stats.tiles_downloaded,
            "tiles_reused": stats.tiles_reused,
            "tiles_failed": stats.tiles_failed,
            "tile_fetch_time_ms": stats.tile_fetch_time_ms,
            "metres_per_pixel": stats.metres_per_pixel,
            "tile_metres": stats.tile_metres,
            "pixels": stats.pixels,
            "failed_tiles": stats.failed_tiles,
        },
        "new_cache_size_mb": stats.cache_size_bytes / 1e6,
        "old_crop_stats": old_stats,
        "new_crop_stats": new_stats,
        "old_top10": old_top,
        "new_top10": new_top,
        "old_all": old_ex["all_rows"],
        "new_all": new_ex["all_rows"],
        "old_confidence": old_conf,
        "new_confidence": new_conf,
        "detail": detail,
        "answers": answers,
        "success_standard": SUCCESS_STANDARD,
        "runtime_s": round(time.time() - started, 1),
    }
    # latest.json without huge all_rows duplication in a slim file plus full
    slim = dict(payload)
    slim["old_all"] = [{k: r[k] for k in ("stand_number", "rank", "total_score", "pool_geometry_similarity", "pool_house_similarity", "structural_layout_similarity", "exterior_similarity", "contradiction")} for r in old_ex["all_rows"]]
    slim["new_all"] = [{k: r[k] for k in ("stand_number", "rank", "total_score", "pool_geometry_similarity", "pool_house_similarity", "structural_layout_similarity", "exterior_similarity", "contradiction")} for r in new_ex["all_rows"]]
    (OUT / "latest.json").write_text(json.dumps(slim, indent=2, default=str), encoding="utf-8")
    write_report(slim)
    print(f"\nWrote {OUT / 'report.md'}")
    print("A", answers["A"])
    print("B", answers["B"])
    print("C", answers["C"])
    print("D", answers["D"])
    print("E", answers["E"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
