#!/usr/bin/env python3
"""Baseline vs experimental OS v1 ranking for listing 116978058.

Uses PR #4 Object Segmentation v1 outputs unchanged.
Does not modify production combined_score / ranking weights.
"""

from __future__ import annotations

import io
import json
import sys
import time
from collections import Counter
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.gis.dataset_registry import CORRECT_CARLSWALD_NORTH
from backend.gis.estate_ags_matching.aerial_geometric import (
    extract_structural_layout,
    structural_layout_similarity,
)
from backend.gis.estate_ags_matching.final_candidates import (
    FINAL_CANDIDATE_LIMIT,
    assess_separation,
    freeze_final_candidates,
)
from backend.gis.estate_ags_matching.os_v1_experimental_rank import (
    experimental_hybrid_neutral_score,
    experimental_hybrid_score,
    experimental_pure_os_neutral_score,
    experimental_pure_os_score,
    is_high_conf,
    os_object_features,
)
from backend.gis.estate_ags_matching.pool_geometry import (
    PoolGeometryFingerprint,
    extract_pool_geometry,
    pool_geometry_similarity,
)
from backend.imagery.estate_tiles import crop_dir_for
from backend.parsers.property24 import fetch_listing
from backend.vision.clip_encoder import classify_scene, encode_image, mean_top_similarity
from scripts.run_carlswald_north_corrected import combined_score, parcel_mask, stand_size_support

LISTING_ID = "116978058"
LISTING_URL = "https://www.property24.com/for-sale/carlswald-north-estate/midrand/gauteng/12743/116978058"
EVAL_STAND = "365"  # visual match of listing pool/jacuzzi/pavilion/powerlines vs native15; not used in ranking
GIS_PATH = ROOT / "data/gis" / f"{CORRECT_CARLSWALD_NORTH}.json"
CROP_DIR = crop_dir_for(CORRECT_CARLSWALD_NORTH, "native15")
SEG_DIR = ROOT / "data/investigations/object_segmentation_v1/carlswald_north/json"
FROZEN_LISTING = ROOT / "data/investigations/carlswald_north_corrected" / LISTING_ID / "listing_pool_fingerprint.json"
FROZEN_PHOTOS = ROOT / "data/investigations/carlswald_north_corrected" / LISTING_ID / "photos"
OUT = ROOT / "data/investigations/os_v1_ranking_experiment" / f"carlswald_north_{LISTING_ID}"


def _safe(stand: str) -> str:
    return str(stand).replace("/", "_")


def _load_parcels_last_wins() -> list[dict]:
    gis = json.loads(GIS_PATH.read_text(encoding="utf-8"))
    by_safe: dict[str, dict] = {}
    for item in gis["parcels"]:
        if item.get("land_type") != "Erven":
            continue
        if item.get("class") in {"non_residential"}:
            continue
        if (item.get("area_sqm") or 0) >= 8000:
            continue
        if not item.get("geometry") or not item.get("stand_number"):
            continue
        if str(item["stand_number"]).startswith("RE/"):
            continue
        by_safe[_safe(item["stand_number"])] = item
    return list(by_safe.values())


def _load_seg(stand: str) -> dict:
    path = SEG_DIR / f"{_safe(stand)}.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _rank_rows(rows: list[dict], score_key: str) -> list[dict]:
    ranked = sorted(rows, key=lambda row: (-float(row[score_key]), str(row["stand_number"])))
    for index, row in enumerate(ranked, start=1):
        row["rank"] = index
    return ranked


def main() -> int:
    started = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    parcels = _load_parcels_last_wins()
    listing_pool = PoolGeometryFingerprint.model_validate(json.loads(FROZEN_LISTING.read_text(encoding="utf-8")))

    print("Listing 116978058 — baseline vs OS v1 experimental ranking")
    print(f"  frozen listing pool present={listing_pool.present} shape={listing_pool.shape_class} aspect={listing_pool.aspect_ratio}")
    print(f"  unique crop stands={len(parcels)} crops={CROP_DIR}")

    listing = None
    try:
        listing = fetch_listing(LISTING_URL, LISTING_ID)
    except Exception as exc:  # noqa: BLE001
        print(f"  live listing fetch failed ({exc}); using cached stand size 972")
    stand_sqm = (listing.stand_size_sqm if listing else None) or 972.0
    # Same listing photos as the native15 A/B baseline. Do not re-extract the
    # frozen pool fingerprint; CLIP/layout still need the listing JPEGs.
    bodies: dict[str, bytes] = {}
    photo_dir = FROZEN_PHOTOS if FROZEN_PHOTOS.is_dir() else OUT / "photos"
    if photo_dir.is_dir():
        for path in sorted(photo_dir.glob("*.jpg")):
            bodies[path.stem] = path.read_bytes()
    print(f"  listing images: {len(bodies)} from {photo_dir}")

    scenes = {}
    retained = []
    for media_id, body in bodies.items():
        try:
            image = Image.open(io.BytesIO(body)).convert("RGB")
        except Exception:
            continue
        if min(image.size) < 80:
            continue
        scene = classify_scene(image)
        scenes[media_id] = scene
        if scene != "interior":
            retained.append(media_id)
    print(f"  scene counts: {dict(Counter(scenes.values()))}")
    listing_has_driveway = any(scenes.get(mid) == "driveway_access" for mid in retained)
    aerial_ids = [mid for mid in retained if scenes.get(mid) == "aerial"]
    listing_layout = None
    layout_ids = aerial_ids or [mid for mid in retained if scenes.get(mid) in {"pool_garden", "rear_elevation", "contextual"}][:6]
    if layout_ids:
        listing_layout = extract_structural_layout(bodies[layout_ids[0]])

    listing_vecs = {}
    for mid in retained:
        listing_vecs[mid] = encode_image(Image.open(io.BytesIO(bodies[mid])).convert("RGB"))
    aerial_vecs = [listing_vecs[mid] for mid in aerial_ids if mid in listing_vecs]
    exterior_vecs = [
        listing_vecs[mid]
        for mid in retained
        if scenes.get(mid) in {"front_elevation", "rear_elevation", "contextual", "driveway_access"}
    ]

    scored = []
    bytes_by = {}
    for parcel in parcels:
        stand = str(parcel["stand_number"])
        crop_path = CROP_DIR / f"{_safe(stand)}_ags_aerial.jpg"
        if not crop_path.is_file():
            continue
        body = crop_path.read_bytes()
        bytes_by[stand] = body
        image = Image.open(io.BytesIO(body)).convert("RGB")
        mask = parcel_mask(image.size, parcel["geometry"], None)
        cand_pool = extract_pool_geometry(body, media_id=f"cand-{stand}", parcel_mask=mask)
        compared = pool_geometry_similarity(listing_pool, cand_pool)
        cand_layout = extract_structural_layout(body)
        structural = structural_layout_similarity(listing_layout, cand_layout) if listing_layout else None
        size_score = stand_size_support(stand_sqm, parcel.get("area_sqm"))
        scored.append(
            {
                "stand_number": stand,
                "township": parcel.get("township"),
                "area_sqm": parcel.get("area_sqm"),
                "pool_geometry_similarity": compared.get("pool_geometry_similarity"),
                "pool_house_similarity": compared.get("pool_house_similarity"),
                "structural_layout_similarity": structural,
                "driveway_similarity": structural,
                "size_score": size_score,
                "contradiction": compared.get("contradiction"),
                "pool_present": cand_pool.present,
            }
        )

    pool_ranked = sorted(
        scored,
        key=lambda row: (-(row["pool_geometry_similarity"] or -1), -(row["pool_house_similarity"] or -1), str(row["stand_number"])),
    )
    short_ids = {row["stand_number"] for row in pool_ranked[:40]}
    print(f"  baseline pass-2 shortlist n={len(short_ids)}")

    clip_cache = {}
    for row in scored:
        stand = row["stand_number"]
        aerial = exterior = video = None
        if stand in short_ids:
            image = Image.open(io.BytesIO(bytes_by[stand])).convert("RGB")
            cand_vecs = [encode_image(image)]
            clip_cache[stand] = cand_vecs
            aerial = mean_top_similarity(aerial_vecs, cand_vecs)
            exterior = mean_top_similarity(exterior_vecs, cand_vecs)
            video = mean_top_similarity([], cand_vecs)
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
        row["total_score"] = total
        row["aerial_similarity"] = None if aerial is None else round(aerial, 4)
        row["exterior_similarity"] = None if exterior is None else round(exterior, 4)
        row["video_similarity"] = None if video is None else round(video, 4)

    baseline = _rank_rows(scored, "total_score")
    base_top10, base_conf = freeze_final_candidates(baseline, limit=FINAL_CANDIDATE_LIMIT)
    print(f"  baseline Top1={baseline[0]['stand_number']} score={baseline[0]['total_score']} low_conf={base_conf.get('low_confidence')}")

    for row in scored:
        seg = _load_seg(row["stand_number"])
        row["os_pool_status"] = (seg.get("pool") or {}).get("status")
        row["os_building_status"] = (seg.get("building") or {}).get("status")
        row["os_driveway_status"] = (seg.get("driveway") or {}).get("status")
        row["os_high_conf_pool"] = is_high_conf(seg.get("pool"))
        feats = os_object_features(
            listing_pool,
            seg,
            listing_roof_area_frac=None if listing_layout is None else listing_layout.roof_area_frac,
            listing_roof_orientation_deg=None if listing_layout is None else listing_layout.roof_orientation_deg,
            listing_roof_aspect=None if listing_layout is None else listing_layout.roof_aspect,
            listing_has_driveway=listing_has_driveway,
        )
        row["os_features"] = feats
        hybrid, hybrid_c = experimental_hybrid_score(
            feats,
            aerial=row["aerial_similarity"],
            video=row["video_similarity"],
            exterior=row["exterior_similarity"],
            stand_size=row["size_score"],
        )
        hybrid_n, hybrid_n_c = experimental_hybrid_neutral_score(
            feats,
            aerial=row["aerial_similarity"],
            video=row["video_similarity"],
            exterior=row["exterior_similarity"],
            stand_size=row["size_score"],
        )
        pure, pure_c = experimental_pure_os_score(feats)
        pure_n, pure_n_c = experimental_pure_os_neutral_score(feats)
        row["hybrid_score"] = hybrid
        row["hybrid_contrib"] = hybrid_c
        row["hybrid_neutral_score"] = hybrid_n
        row["hybrid_neutral_contrib"] = hybrid_n_c
        row["pure_os_score"] = pure
        row["pure_os_contrib"] = pure_c
        row["pure_os_neutral_score"] = pure_n
        row["pure_os_neutral_contrib"] = pure_n_c

    baseline = _rank_rows(scored, "total_score")
    hybrid_sorted = sorted(scored, key=lambda r: (-float(r["hybrid_score"]), str(r["stand_number"])))
    pure_sorted = sorted(scored, key=lambda r: (-float(r["pure_os_score"]), str(r["stand_number"])))
    hybrid_neutral_sorted = sorted(scored, key=lambda r: (-float(r["hybrid_neutral_score"]), str(r["stand_number"])))
    pure_neutral_sorted = sorted(scored, key=lambda r: (-float(r["pure_os_neutral_score"]), str(r["stand_number"])))
    high_conf_pool = [row for row in scored if row.get("os_high_conf_pool")]
    high_conf_sorted = sorted(high_conf_pool, key=lambda r: (-float(r["pure_os_score"]), str(r["stand_number"])))
    for row in scored:
        row["baseline_rank"] = row["rank"]
    for index, row in enumerate(hybrid_sorted, start=1):
        row["hybrid_rank"] = index
    for index, row in enumerate(pure_sorted, start=1):
        row["pure_os_rank"] = index
    for index, row in enumerate(hybrid_neutral_sorted, start=1):
        row["hybrid_neutral_rank"] = index
    for index, row in enumerate(pure_neutral_sorted, start=1):
        row["pure_os_neutral_rank"] = index
    for index, row in enumerate(high_conf_sorted, start=1):
        row["high_conf_pool_rank"] = index

    def compact(row, score_key, rank_key):
        return {
            "rank": row.get(rank_key),
            "stand_number": row["stand_number"],
            "township": row["township"],
            "area_sqm": row["area_sqm"],
            "score": row[score_key],
            "blob_pool_present": row["pool_present"],
            "os_pool_status": row["os_pool_status"],
            "os_building_status": row["os_building_status"],
            "os_driveway_status": row["os_driveway_status"],
            "os_high_conf_pool": row.get("os_high_conf_pool"),
            "pool_geometry_similarity": row["pool_geometry_similarity"],
            "os_features": row["os_features"],
            "hybrid_contrib": row.get("hybrid_contrib"),
            "hybrid_neutral_contrib": row.get("hybrid_neutral_contrib"),
            "contradiction": row["contradiction"],
            "aerial_similarity": row["aerial_similarity"],
            "exterior_similarity": row["exterior_similarity"],
            "baseline_rank": row["baseline_rank"],
            "hybrid_rank": row["hybrid_rank"],
            "hybrid_neutral_rank": row.get("hybrid_neutral_rank"),
            "pure_os_rank": row["pure_os_rank"],
            "pure_os_neutral_rank": row.get("pure_os_neutral_rank"),
            "high_conf_pool_rank": row.get("high_conf_pool_rank"),
        }

    base_top20 = [compact(row, "total_score", "baseline_rank") for row in baseline[:20]]
    hybrid_top20 = [compact(row, "hybrid_score", "hybrid_rank") for row in hybrid_sorted[:20]]
    pure_top20 = [compact(row, "pure_os_score", "pure_os_rank") for row in pure_sorted[:20]]
    hybrid_neutral_top20 = [compact(row, "hybrid_neutral_score", "hybrid_neutral_rank") for row in hybrid_neutral_sorted[:20]]
    pure_neutral_top20 = [compact(row, "pure_os_neutral_score", "pure_os_neutral_rank") for row in pure_neutral_sorted[:20]]
    high_conf_top20 = [compact(row, "pure_os_score", "high_conf_pool_rank") for row in high_conf_sorted[:20]]

    by_stand = {row["stand_number"]: row for row in scored}
    rank_lists = {
        "hybrid_rank": hybrid_sorted,
        "pure_os_rank": pure_sorted,
        "hybrid_neutral_rank": hybrid_neutral_sorted,
        "pure_os_neutral_rank": pure_neutral_sorted,
    }

    def movement(n: int, rank_key: str) -> dict:
        base_ids = [row["stand_number"] for row in baseline[:n]]
        new_ids = [row["stand_number"] for row in rank_lists[rank_key][:n]]
        return {
            "entering": [s for s in new_ids if s not in base_ids],
            "leaving": [s for s in base_ids if s not in new_ids],
        }

    fp_removed = []
    for row in baseline[:20]:
        if row["pool_present"] and not row.get("os_high_conf_pool"):
            fp_removed.append(
                {
                    "stand_number": row["stand_number"],
                    "baseline_rank": row["baseline_rank"],
                    "hybrid_rank": row["hybrid_rank"],
                    "hybrid_neutral_rank": row.get("hybrid_neutral_rank"),
                    "os_pool_status": row["os_pool_status"],
                    "blob_pool_geom": row["pool_geometry_similarity"],
                }
            )

    eval_row = by_stand.get(EVAL_STAND)
    eval_payload = None
    if eval_row:
        eval_payload = {
            "stand_number": EVAL_STAND,
            "identification": "visual: listing rear pool is dark faceted octagon + circular jacuzzi + pavilion + powerlines; native15 365 matches. GIS area 970 vs listing 972 is corroboration only, not a ranking input.",
            "baseline_rank": eval_row["baseline_rank"],
            "hybrid_rank": eval_row["hybrid_rank"],
            "hybrid_neutral_rank": eval_row.get("hybrid_neutral_rank"),
            "pure_os_rank": eval_row["pure_os_rank"],
            "pure_os_neutral_rank": eval_row.get("pure_os_neutral_rank"),
            "high_conf_pool_rank": eval_row.get("high_conf_pool_rank"),
            "n_high_conf_pools": len(high_conf_sorted),
            "baseline_score": eval_row["total_score"],
            "hybrid_score": eval_row["hybrid_score"],
            "hybrid_neutral_score": eval_row.get("hybrid_neutral_score"),
            "pure_os_score": eval_row["pure_os_score"],
            "os_features": eval_row["os_features"],
            "hybrid_contrib": eval_row["hybrid_contrib"],
            "hybrid_neutral_contrib": eval_row.get("hybrid_neutral_contrib"),
            "blob_pool_geom": eval_row["pool_geometry_similarity"],
            "os_pool_status": eval_row["os_pool_status"],
        }

    def feature_movers(rank_key="hybrid_rank"):
        rows = rank_lists.get(rank_key, hybrid_sorted)
        interesting = []
        seen = set()
        for row in rows[:20] + baseline[:20] + ([eval_row] if eval_row else []):
            stand = row["stand_number"]
            if stand in seen:
                continue
            seen.add(stand)
            delta = row["baseline_rank"] - row[rank_key]
            if abs(delta) < 3 and stand != EVAL_STAND:
                continue
            interesting.append(
                {
                    "stand_number": stand,
                    "baseline_rank": row["baseline_rank"],
                    "new_rank": row[rank_key],
                    "delta": delta,
                    "os_pool_status": row["os_pool_status"],
                    "blob_pool_present": row["pool_present"],
                    "os_features": row["os_features"],
                    "hybrid_contrib": row["hybrid_contrib"],
                    "hybrid_neutral_contrib": row.get("hybrid_neutral_contrib"),
                    "pure_os_contrib": row["pure_os_contrib"],
                    "contradiction": row["contradiction"],
                }
            )
        interesting.sort(key=lambda item: -abs(item["delta"]))
        return interesting[:25]

    all_candidates = [
        {
            "stand_number": row["stand_number"],
            "township": row["township"],
            "area_sqm": row["area_sqm"],
            "baseline_score": row["total_score"],
            "baseline_rank": row["baseline_rank"],
            "hybrid_score": row["hybrid_score"],
            "hybrid_rank": row["hybrid_rank"],
            "hybrid_neutral_score": row["hybrid_neutral_score"],
            "hybrid_neutral_rank": row["hybrid_neutral_rank"],
            "pure_os_score": row["pure_os_score"],
            "pure_os_rank": row["pure_os_rank"],
            "pure_os_neutral_score": row["pure_os_neutral_score"],
            "pure_os_neutral_rank": row["pure_os_neutral_rank"],
            "high_conf_pool_rank": row.get("high_conf_pool_rank"),
            "blob_pool_present": row["pool_present"],
            "os_pool_status": row["os_pool_status"],
            "os_building_status": row["os_building_status"],
            "os_driveway_status": row["os_driveway_status"],
            "os_high_conf_pool": row.get("os_high_conf_pool"),
            "os_features": row["os_features"],
            "contradiction": row["contradiction"],
            "pool_geometry_similarity": row["pool_geometry_similarity"],
            "aerial_similarity": row["aerial_similarity"],
            "exterior_similarity": row["exterior_similarity"],
        }
        for row in baseline
    ]

    hybrid_conf = assess_separation([row["hybrid_score"] for row in hybrid_sorted])
    hybrid_neutral_conf = assess_separation([row["hybrid_neutral_score"] for row in hybrid_neutral_sorted])
    payload = {
        "listing_id": LISTING_ID,
        "os_version": "object_segmentation_v1",
        "production_ranking_modified": False,
        "ags_downloads": 0,
        "n_candidates": len(scored),
        "n_high_conf_pools": len(high_conf_sorted),
        "evaluation_stand": EVAL_STAND,
        "evaluation": eval_payload,
        "baseline": {
            "confidence": base_conf,
            "top20": base_top20,
            "eval_rank": None if eval_row is None else eval_row["baseline_rank"],
        },
        "experimental_hybrid": {
            "note": "EvidenceFusion with blob pool/roof/driveway replaced by high-confidence OS v1. UNKNOWN/REJECTED skipped, not penalised. CLIP and stand-size unchanged.",
            "confidence": hybrid_conf,
            "top20": hybrid_top20,
            "eval_rank": None if eval_row is None else eval_row["hybrid_rank"],
            "movement_top5": movement(5, "hybrid_rank"),
            "movement_top10": movement(10, "hybrid_rank"),
            "movement_top20": movement(20, "hybrid_rank"),
        },
        "experimental_hybrid_neutral": {
            "note": "Diagnostic only: missing OS object terms imputed at 0.5 so skip-and-renormalize cannot reward segmentation failure. Still not a production ranking.",
            "confidence": hybrid_neutral_conf,
            "top20": hybrid_neutral_top20,
            "eval_rank": None if eval_row is None else eval_row.get("hybrid_neutral_rank"),
            "movement_top5": movement(5, "hybrid_neutral_rank"),
            "movement_top10": movement(10, "hybrid_neutral_rank"),
            "movement_top20": movement(20, "hybrid_neutral_rank"),
        },
        "experimental_pure_os": {
            "note": "OS v1 object features only (no CLIP). Diagnostic, not a production proposal. Skip-None; REJECTED stands can rank on building/driveway alone.",
            "top20": pure_top20,
            "eval_rank": None if eval_row is None else eval_row["pure_os_rank"],
        },
        "experimental_pure_os_neutral": {
            "note": "Pure OS with missing object terms at 0.5.",
            "top20": pure_neutral_top20,
            "eval_rank": None if eval_row is None else eval_row.get("pure_os_neutral_rank"),
        },
        "among_high_conf_pools": {
            "note": "Pure OS ranking restricted to CONFIRMED/PROBABLE pools. Tests whether the pool fingerprint discriminates when localisation succeeded.",
            "n": len(high_conf_sorted),
            "top20": high_conf_top20,
            "eval_rank": None if eval_row is None else eval_row.get("high_conf_pool_rank"),
        },
        "false_positives_removed_from_baseline_top20": fp_removed,
        "feature_movers": feature_movers(),
        "feature_movers_neutral": feature_movers("hybrid_neutral_rank"),
        "runtime_s": round(time.time() - started, 1),
    }
    (OUT / "baseline_top20.json").write_text(json.dumps({"top20": base_top20, "confidence": base_conf, "n": len(scored)}, indent=2), encoding="utf-8")
    (OUT / "all_candidates.json").write_text(json.dumps({"n": len(all_candidates), "rows": all_candidates}, indent=2), encoding="utf-8")
    (OUT / "latest.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print("\nBASELINE TOP 20")
    for row in baseline[:20]:
        print(f"  {row['baseline_rank']:2d} {row['stand_number']:>8} {row['total_score']:.3f} blob_pool={row['pool_present']} os={row['os_pool_status']}")
    print("\nHYBRID TOP 20 (skip-None)")
    for row in hybrid_sorted[:20]:
        print(f"  {row['hybrid_rank']:2d} {row['stand_number']:>8} {row['hybrid_score']:.3f} os={row['os_pool_status']} Δ {row['baseline_rank']-row['hybrid_rank']:+d}")
    print("\nHYBRID NEUTRAL TOP 20 (missing OS = 0.5)")
    for row in hybrid_neutral_sorted[:20]:
        print(f"  {row['hybrid_neutral_rank']:2d} {row['stand_number']:>8} {row['hybrid_neutral_score']:.3f} os={row['os_pool_status']} Δ {row['baseline_rank']-row['hybrid_neutral_rank']:+d}")
    if eval_row:
        print(
            f"\nEVAL STAND {EVAL_STAND}: baseline #{eval_row['baseline_rank']} "
            f"→ hybrid #{eval_row['hybrid_rank']} "
            f"→ hybrid-neutral #{eval_row.get('hybrid_neutral_rank')} "
            f"→ pure-OS #{eval_row['pure_os_rank']} "
            f"→ among-high-conf-pools #{eval_row.get('high_conf_pool_rank')} / {len(high_conf_sorted)}"
        )
    print(f"\nwrote {OUT / 'latest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
