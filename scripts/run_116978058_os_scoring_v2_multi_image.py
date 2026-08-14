#!/usr/bin/env python3
"""Reproduce PR #6, then run a multi-listing-image Scoring v2 diagnostic.

Does not write into the PR #6 investigation directory except the new
rerun_multi_image/ subdirectory. Production ranking, OS v1, native15 crops,
and Scoring v2 weights are unchanged.
"""

from __future__ import annotations

import io
import json
import sys
import time
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.gis.estate_ags_matching.final_candidates import assess_separation
from backend.gis.estate_ags_matching.os_scoring_v2 import (
    OS_KEYS_NO_BUILDING,
    V2_WEIGHTS_NO_BUILDING,
    contour_descriptors,
    score_v2,
    shape_v2_similarity,
    v2_object_features,
)
from backend.gis.estate_ags_matching.os_scoring_v2_multi_image import (
    fuse_listing_observations,
    observation_public,
    observe_listing_image,
    spatial_v2_with_scale,
)
from backend.gis.estate_ags_matching.os_v1_experimental_rank import is_high_conf
from backend.gis.estate_ags_matching.pool_geometry import PoolGeometryFingerprint
from backend.vision.clip_encoder import classify_scene
from scripts.run_carlswald_north_corrected import stand_size_support

LISTING_ID = "116978058"
EVAL_STAND = "365"  # evaluation only; not an input to scoring
PR6_DIR = ROOT / "data/investigations/os_scoring_v2" / f"carlswald_north_{LISTING_ID}"
PR5_ALL = ROOT / "data/investigations/os_v1_ranking_experiment" / f"carlswald_north_{LISTING_ID}" / "all_candidates.json"
FROZEN_LISTING = ROOT / "data/investigations/carlswald_north_corrected" / LISTING_ID / "listing_pool_fingerprint.json"
FROZEN_PHOTOS = ROOT / "data/investigations/carlswald_north_corrected" / LISTING_ID / "photos"
SEG_DIR = ROOT / "data/investigations/object_segmentation_v1/carlswald_north/json"
OUT = PR6_DIR / "rerun_multi_image"
LISTING_STAND_SQM = 972.0
SKIP_SCENES = {"interior"}


def _safe(stand: str) -> str:
    return str(stand).replace("/", "_")


def _font(size: int = 14):
    path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    return ImageFont.truetype(str(path), size) if path.is_file() else ImageFont.load_default()


def _load_seg(stand: str) -> dict:
    path = SEG_DIR / f"{_safe(stand)}.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def reproduce_pr6() -> dict:
    """Confirm saved PR #6 ranks and recompute Scoring v2 with the frozen listing."""
    saved = json.loads((PR6_DIR / "latest.json").read_text(encoding="utf-8"))
    saved_ranks = {
        "baseline": saved["frozen_baseline"]["eval"]["rank"],
        "pr5_neutral": saved["pr5_neutral_0.5"]["eval"]["rank"],
        "scoring_v2": saved["variants"]["v2_neutral_nobuilding"]["eval"]["rank"],
    }
    listing = PoolGeometryFingerprint.model_validate(json.loads(FROZEN_LISTING.read_text(encoding="utf-8")))
    listing_shape = contour_descriptors(listing.contour_normalized or listing.contour_image)
    frozen_rows = json.loads(PR5_ALL.read_text(encoding="utf-8"))["rows"]
    scored = []
    for item in frozen_rows:
        seg = _load_seg(str(item["stand_number"]))
        feats = v2_object_features(
            listing,
            seg,
            listing_shape=listing_shape,
            listing_has_driveway=True,
            listing_driveway_side=None,
            include_building_coarse=False,
        )
        score, _contrib, _cov, _fac = score_v2(
            feats,
            aerial=item.get("aerial_similarity"),
            exterior=item.get("exterior_similarity"),
            stand_size=stand_size_support(LISTING_STAND_SQM, item.get("area_sqm")),
            weights=V2_WEIGHTS_NO_BUILDING,
            os_keys=OS_KEYS_NO_BUILDING,
            missing="neutral",
        )
        scored.append(
            {
                "stand_number": str(item["stand_number"]),
                "score": score,
                "baseline_rank": item["baseline_rank"],
                "pr5_neutral_rank": item["hybrid_neutral_rank"],
            }
        )
    v2_ranked = sorted(scored, key=lambda row: (-row["score"], row["stand_number"]))
    recomputed = next(i for i, row in enumerate(v2_ranked, start=1) if row["stand_number"] == EVAL_STAND)
    baseline = next(row["baseline_rank"] for row in scored if row["stand_number"] == EVAL_STAND)
    pr5 = next(row["pr5_neutral_rank"] for row in scored if row["stand_number"] == EVAL_STAND)
    expected = {"baseline": 17, "pr5_neutral": 2, "scoring_v2": 3}
    recomputed_ranks = {"baseline": baseline, "pr5_neutral": pr5, "scoring_v2": recomputed}
    ok = saved_ranks == expected and recomputed_ranks == expected
    return {
        "ok": ok,
        "expected": expected,
        "saved_pr6_latest": saved_ranks,
        "recomputed": recomputed_ranks,
        "eval_stand": EVAL_STAND,
        "note": "Recompute uses frozen listing fingerprint + frozen OS v1 JSON + PR #5 CLIP/stand-size. Does not rewrite PR #6 artefacts.",
    }


def _draw_listing_contours(observations: list[dict], fused, dest: Path) -> None:
    chosen = [item for item in observations if item["pool_present"] and item["descriptors"]]
    chosen.sort(key=lambda item: -item["shape_quality"])
    chosen = chosen[:8]
    if not chosen:
        return
    w, h = 1400, 280
    canvas = Image.new("RGB", (w, h), (18, 18, 22))
    draw = ImageDraw.Draw(canvas)
    font = _font(12)
    cell = w // max(len(chosen), 1)
    fused_xy = None
    if fused.get("fused_shape_descriptors") and fused["fused_shape_descriptors"].get("norm_xy"):
        import numpy as np

        fused_xy = fused["fused_shape_descriptors"]["norm_xy"]
    for i, item in enumerate(chosen):
        x0 = i * cell
        draw.text((x0 + 8, 6), f"{item['media_id'][-3:]} {item['scene'][:8]} q={item['shape_quality']:.2f}", fill=(230, 230, 230), font=font)
        xy = item["descriptors"].get("norm_xy")
        if not xy:
            continue
        box = [x0 + 10, 28, x0 + cell - 10, h - 10]
        cx, cy = (box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0
        scale = 0.40 * min(box[2] - box[0], box[3] - box[1])
        color = (255, 196, 64) if item["media_id"] == fused.get("shape_source") else (120, 180, 220)
        pts = [(int(cx + p[0] * scale), int(cy + p[1] * scale)) for p in xy]
        draw.line(pts + [pts[0]], fill=color, width=2)
    dest.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(dest)


def main() -> int:
    started = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "panels").mkdir(exist_ok=True)

    print("Reproducing PR #6 ranks (no overwrite of PR #6 artefacts)")
    repro = reproduce_pr6()
    print(f"  saved={repro['saved_pr6_latest']} recomputed={repro['recomputed']} ok={repro['ok']}")
    if not repro["ok"]:
        print("BLOCKER: PR #6 ranks did not reproduce")
        (OUT / "pr6_reproduce.json").write_text(json.dumps(repro, indent=2), encoding="utf-8")
        return 1
    (OUT / "pr6_reproduce.json").write_text(json.dumps(repro, indent=2), encoding="utf-8")

    print("Extracting listing-image pool evidence")
    bodies = {path.stem: path.read_bytes() for path in sorted(FROZEN_PHOTOS.glob("*.jpg"))}
    observations = []
    scenes = {}
    for media_id, body in bodies.items():
        try:
            image = Image.open(io.BytesIO(body)).convert("RGB")
        except Exception:
            continue
        if min(image.size) < 80:
            continue
        scene = classify_scene(image)
        scenes[media_id] = scene
        if scene in SKIP_SCENES:
            continue
        observations.append(observe_listing_image(media_id, body, scene))
    print(f"  photos={len(bodies)} scenes={dict(Counter(scenes.values()))} exterior_obs={len(observations)}")
    fused = fuse_listing_observations(observations)
    listing = fused["fused_fingerprint"]
    listing_shape = fused["fused_shape_descriptors"]
    print(
        f"  pool_present_frames={fused['n_pool_present']} "
        f"shape_from={fused['shape_source']} spatial_from={fused['spatial_source']} "
        f"scale={fused['fused_pool_roof_ratio']}"
    )
    if listing is None or listing_shape is None:
        print("BLOCKER: no fused listing pool evidence")
        return 1

    frozen_rows = json.loads(PR5_ALL.read_text(encoding="utf-8"))["rows"]
    rows = []
    for item in frozen_rows:
        stand = str(item["stand_number"])
        seg = _load_seg(stand)
        feats = v2_object_features(
            listing,
            seg,
            listing_shape=listing_shape,
            listing_has_driveway=True,
            listing_driveway_side=None,
            include_building_coarse=False,
        )
        spatial_score, spatial_parts = spatial_v2_with_scale(listing, fused["fused_pool_roof_ratio"], seg)
        feats["spatial_v2"] = spatial_score
        score, contrib, coverage, factor = score_v2(
            feats,
            aerial=item.get("aerial_similarity"),
            exterior=item.get("exterior_similarity"),
            stand_size=stand_size_support(LISTING_STAND_SQM, item.get("area_sqm")),
            weights=V2_WEIGHTS_NO_BUILDING,
            os_keys=OS_KEYS_NO_BUILDING,
            missing="neutral",
        )
        shape_score, shape_parts = shape_v2_similarity(
            listing_shape,
            contour_descriptors((seg.get("pool") or {}).get("contour")) if is_high_conf(seg.get("pool")) else None,
        )
        rows.append(
            {
                "stand_number": stand,
                "township": item.get("township"),
                "area_sqm": item.get("area_sqm"),
                "baseline_rank": item["baseline_rank"],
                "pr5_neutral_rank": item["hybrid_neutral_rank"],
                "pr6_v2_rank": item.get("v2_neutral_nobuilding_rank"),
                "pr6_v2_score": item.get("v2_neutral_nobuilding_score"),
                "score": score,
                "contrib": contrib,
                "coverage": coverage,
                "os_pool_status": item.get("os_pool_status"),
                "os_building_status": item.get("os_building_status"),
                "shape_v2": feats["shape_v2"],
                "spatial_v2": feats["spatial_v2"],
                "shape_parts": {k: v for k, v in (shape_parts or {}).items() if k != "norm_xy"},
                "spatial_parts": spatial_parts,
                "blob_pool_present": item.get("blob_pool_present"),
            }
        )

    ranked = sorted(rows, key=lambda row: (-float(row["score"]), str(row["stand_number"])))
    for index, row in enumerate(ranked, start=1):
        row["rank"] = index

    by = {row["stand_number"]: row for row in ranked}
    eval_row = by[EVAL_STAND]
    top1, top2 = ranked[0], ranked[1]
    named = {stand: by[stand] for stand in ("365", "583", "428", "404", "348", "420") if stand in by}
    conf = assess_separation([row["score"] for row in ranked])

    pr6_all = json.loads((PR6_DIR / "all_candidates.json").read_text(encoding="utf-8"))
    pr6_by = {row["stand_number"]: row for row in pr6_all["rows"]}
    for row in rows:
        prev = pr6_by.get(row["stand_number"])
        if prev:
            row["pr6_v2_rank"] = prev["v2_neutral_nobuilding_rank"]
            row["pr6_v2_score"] = prev["v2_neutral_nobuilding_score"]

    def slim(row):
        return {
            "rank": row["rank"],
            "stand_number": row["stand_number"],
            "score": row["score"],
            "os_pool_status": row["os_pool_status"],
            "coverage": row["coverage"],
            "shape_v2": row["shape_v2"],
            "spatial_v2": row["spatial_v2"],
            "contrib": row["contrib"],
            "spatial_parts": row["spatial_parts"],
            "baseline_rank": row["baseline_rank"],
            "pr5_neutral_rank": row["pr5_neutral_rank"],
            "pr6_v2_rank": row.get("pr6_v2_rank"),
        }

    payload = {
        "listing_id": LISTING_ID,
        "diagnostic": "multi_listing_image_scoring_v2",
        "production_ranking_modified": False,
        "os_v1_modified": False,
        "pr6_modified": False,
        "weight_tuning_after_results": False,
        "stand_specific_rules": False,
        "pr6_reproduce": repro,
        "scene_counts": dict(Counter(scenes.values())),
        "fusion": {
            "shape_source": fused["shape_source"],
            "spatial_source": fused["spatial_source"],
            "scale_sources": fused["scale_sources"],
            "shape_cluster": fused["shape_cluster"],
            "fused_pool_roof_ratio": fused["fused_pool_roof_ratio"],
            "n_pool_present": fused["n_pool_present"],
            "fused_notes": listing.notes,
            "fused_shape_descriptors": {k: v for k, v in listing_shape.items() if k != "norm_xy"},
            "fused_spatial": {
                "dist": listing.pool_to_house_dist,
                "angle_deg": listing.pool_to_house_angle_deg,
                "dx": listing.pool_to_house_dx,
                "dy": listing.pool_to_house_dy,
            },
        },
        "listing_observations": [observation_public(item) for item in observations],
        "comparison": {
            "baseline_365_rank": 17,
            "pr5_neutral_365_rank": 2,
            "pr6_v2_365_rank": 3,
            "multi_image_365_rank": eval_row["rank"],
            "multi_image_365_score": eval_row["score"],
            "top1_stand": top1["stand_number"],
            "top1_score": top1["score"],
            "top2_stand": top2["stand_number"],
            "top2_score": top2["score"],
            "gap_1_2": round(float(top1["score"]) - float(top2["score"]), 4),
            "gap_365_vs_top1": round(float(eval_row["score"]) - float(top1["score"]), 4),
            "583_still_beats_365": named.get("583", {}).get("rank", 999) < eval_row["rank"],
            "428_still_beats_365": named.get("428", {}).get("rank", 999) < eval_row["rank"],
            "named": {
                stand: {"rank": row["rank"], "score": row["score"], "shape_v2": row["shape_v2"], "spatial_v2": row["spatial_v2"]}
                for stand, row in named.items()
            },
            "confidence": conf,
        },
        "top10": [slim(row) for row in ranked[:10]],
        "eval_365": slim(eval_row) | {"shape_parts": eval_row["shape_parts"], "spatial_parts": eval_row["spatial_parts"]},
        "runtime_s": round(time.time() - started, 2),
    }
    (OUT / "latest.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (OUT / "all_candidates.json").write_text(
        json.dumps({"n": len(ranked), "rows": [slim(row) for row in ranked]}, indent=2),
        encoding="utf-8",
    )
    _draw_listing_contours(observations, fused, OUT / "panels" / "listing_shape_views.png")

    print("\nRANKS")
    print(f"  baseline #{17}  PR5-neutral #{2}  PR6 Scoring v2 #{3}  multi-image #{eval_row['rank']}")
    print(f"  top1={top1['stand_number']} {top1['score']:.3f}  365={eval_row['score']:.3f}  gap12={payload['comparison']['gap_1_2']:.4f}")
    print(f"  583 rank={named.get('583', {}).get('rank')}  428 rank={named.get('428', {}).get('rank')}")
    print("TOP 10")
    for row in ranked[:10]:
        print(
            f"  {row['rank']:2d} {row['stand_number']:>6} {row['score']:.3f} os={row['os_pool_status']} "
            f"shape={row['shape_v2']} spat={row['spatial_v2']} pr6={row.get('pr6_v2_rank')}"
        )
    print(f"\nwrote {OUT / 'latest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
