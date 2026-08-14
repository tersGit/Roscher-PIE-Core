#!/usr/bin/env python3
"""Scoring v2 A/B for listing 116978058.

Frozen inputs: PR #5 baseline ranks, listing pool fingerprint, OS v1 JSON,
native15 crops (panels only). Production ranking is not modified.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.gis.dataset_registry import CORRECT_CARLSWALD_NORTH
from backend.gis.estate_ags_matching.final_candidates import assess_separation
from backend.gis.estate_ags_matching.os_scoring_v2 import (
    OS_KEYS_BUILDING,
    OS_KEYS_NO_BUILDING,
    V2_WEIGHTS_BUILDING_COARSE,
    V2_WEIGHTS_NO_BUILDING,
    candidate_spatial_record,
    contour_descriptors,
    listing_shape_descriptors,
    score_v2,
    shape_v2_similarity,
    spatial_v2_similarity,
    v2_object_features,
)
from backend.gis.estate_ags_matching.os_v1_experimental_rank import is_high_conf
from backend.gis.estate_ags_matching.pool_geometry import PoolGeometryFingerprint
from backend.imagery.estate_tiles import crop_dir_for
from scripts.run_carlswald_north_corrected import stand_size_support

LISTING_ID = "116978058"
EVAL_STAND = "365"
PR5_ALL = ROOT / "data/investigations/os_v1_ranking_experiment" / f"carlswald_north_{LISTING_ID}" / "all_candidates.json"
FROZEN_LISTING = ROOT / "data/investigations/carlswald_north_corrected" / LISTING_ID / "listing_pool_fingerprint.json"
SEG_DIR = ROOT / "data/investigations/object_segmentation_v1/carlswald_north/json"
CROP_DIR = crop_dir_for(CORRECT_CARLSWALD_NORTH, "native15")
OUT = ROOT / "data/investigations/os_scoring_v2" / f"carlswald_north_{LISTING_ID}"
LISTING_STAND_SQM = 972.0
BLOB_FP_STATUSES = frozenset({"REJECTED", "UNKNOWN"})

VARIANTS = {
    "v2_neutral_nobuilding": {
        "missing": "neutral",
        "building": False,
        "note": "0.5-neutral OS terms; building term removed; driveway omitted (no listing spatial).",
    },
    "v2_coverage_nobuilding": {
        "missing": "coverage",
        "building": False,
        "note": "Coverage factor 0.5+0.5*coverage on top of 0.5-neutral; building removed.",
    },
    "v2_neutral_building_coarse": {
        "missing": "neutral",
        "building": True,
        "note": "0.5-neutral; building = presence only (no oblique roof-fraction vs nadir area).",
    },
    "v2_coverage_building_coarse": {
        "missing": "coverage",
        "building": True,
        "note": "Coverage factor + coarse building presence.",
    },
    "v2_neutral_noshape": {
        "missing": "neutral",
        "building": False,
        "ablate": "shape",
        "note": "Ablation: drop shape_v2 (keep spatial). Isolates contour descriptors.",
    },
    "v2_neutral_nospatial": {
        "missing": "neutral",
        "building": False,
        "ablate": "spatial",
        "note": "Ablation: drop spatial_v2 (keep shape). Isolates pool-house geometry.",
    },
}


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


def _rank(rows: list[dict], key: str) -> list[dict]:
    ordered = sorted(rows, key=lambda row: (-float(row[key]), str(row["stand_number"])))
    for index, row in enumerate(ordered, start=1):
        row[f"{key}_rank"] = index
    return ordered


def _compact(row: dict, score_key: str, rank_key: str, variant: str) -> dict:
    return {
        "rank": row.get(rank_key),
        "stand_number": row["stand_number"],
        "township": row.get("township"),
        "area_sqm": row.get("area_sqm"),
        "score": row.get(score_key),
        "baseline_rank": row["baseline_rank"],
        "pr5_neutral_rank": row["pr5_neutral_rank"],
        "os_pool_status": row["os_pool_status"],
        "os_building_status": row["os_building_status"],
        "os_driveway_status": row["os_driveway_status"],
        "blob_pool_present": row["blob_pool_present"],
        "coverage": row["v2"][variant]["coverage"] if variant in row.get("v2", {}) else row.get("coverage"),
        "contrib": row["v2"][variant]["contrib"] if variant in row.get("v2", {}) else None,
        "shape_v2": (row.get("v2_feats") or {}).get("shape_v2"),
        "spatial_v2": (row.get("v2_feats") or {}).get("spatial_v2"),
        "shape_parts": row.get("shape_parts"),
        "spatial_parts": row.get("spatial_parts"),
        "spatial_record": row.get("spatial_record"),
        "aerial_similarity": row.get("aerial_similarity"),
        "exterior_similarity": row.get("exterior_similarity"),
    }


def _draw_contour_panel(listing_xy: np.ndarray, items: list[tuple[str, np.ndarray | None, str]], dest: Path) -> None:
    w, h = 1100, 280
    canvas = Image.new("RGB", (w, h), (18, 18, 22))
    draw = ImageDraw.Draw(canvas)
    font = _font(13)
    n = max(len(items), 1)
    cell_w = w // n
    for i, (label, xy, color) in enumerate(items):
        x0 = i * cell_w
        box = [x0 + 8, 28, x0 + cell_w - 8, h - 12]
        draw.rectangle(box, outline=(60, 60, 70), width=1)
        draw.text((x0 + 12, 6), label, fill=(230, 230, 230), font=font)
        if xy is None or len(xy) < 3:
            draw.text((x0 + 16, h // 2), "no contour", fill=(160, 80, 80), font=font)
            continue
        pts = np.asarray(xy, dtype=np.float64)
        cx, cy = (box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0
        scale = 0.42 * min(box[2] - box[0], box[3] - box[1])
        pix = [(int(cx + p[0] * scale), int(cy + p[1] * scale)) for p in pts]
        if listing_xy is not None and len(listing_xy) >= 3:
            lpix = [(int(cx + p[0] * scale), int(cy + p[1] * scale)) for p in listing_xy]
            draw.line(lpix + [lpix[0]], fill=(90, 90, 110), width=2)
        draw.line(pix + [pix[0]], fill=color, width=2)
    dest.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(dest)


def _draw_crop_overlay(stand: str, seg: dict, dest: Path, title: str) -> None:
    crop_path = CROP_DIR / f"{_safe(stand)}_ags_aerial.jpg"
    if not crop_path.is_file():
        return
    image = Image.open(crop_path).convert("RGBA")
    draw = ImageDraw.Draw(image, "RGBA")
    w, h = image.size

    def _poly(contour, fill, outline):
        if not contour:
            return
        pts = [(int(p[0] * (w - 1)), int(p[1] * (h - 1))) for p in contour]
        if len(pts) >= 3:
            draw.polygon(pts, fill=fill, outline=outline)

    pool = seg.get("pool") or {}
    building = seg.get("building") or {}
    driveway = seg.get("driveway") or {}
    if is_high_conf(driveway):
        _poly(driveway.get("contour"), (180, 180, 180, 50), (200, 200, 200))
    if is_high_conf(building):
        _poly(building.get("contour"), (40, 80, 255, 60), (80, 140, 255))
    if is_high_conf(pool):
        _poly(pool.get("contour"), (255, 180, 40, 90), (255, 220, 80))
    draw = ImageDraw.Draw(image)
    draw.text((8, 8), title, fill=(255, 255, 255), font=_font(16))
    dest.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(dest)


def main() -> int:
    started = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "panels").mkdir(exist_ok=True)
    listing = PoolGeometryFingerprint.model_validate(json.loads(FROZEN_LISTING.read_text(encoding="utf-8")))
    listing_shape = listing_shape_descriptors(listing)
    frozen = json.loads(PR5_ALL.read_text(encoding="utf-8"))
    rows = []
    for item in frozen["rows"]:
        stand = str(item["stand_number"])
        seg = _load_seg(stand)
        size_score = stand_size_support(LISTING_STAND_SQM, item.get("area_sqm"))
        feats = v2_object_features(
            listing,
            seg,
            listing_shape=listing_shape,
            listing_has_driveway=True,
            listing_driveway_side=None,
            include_building_coarse=True,
        )
        cand_desc = None
        pool = seg.get("pool") or {}
        if is_high_conf(pool):
            cand_desc = contour_descriptors(pool.get("contour"))
        shape_score, shape_parts = shape_v2_similarity(listing_shape, cand_desc)
        spatial_score, spatial_parts = spatial_v2_similarity(listing, seg)
        feats_nb = dict(feats)
        feats_nb["building_coarse"] = None
        row = {
            **item,
            "pr5_neutral_score": item["hybrid_neutral_score"],
            "pr5_neutral_rank": item["hybrid_neutral_rank"],
            "size_score": size_score,
            "v2_feats": feats,
            "shape_parts": {k: v for k, v in shape_parts.items() if k != "chamfer" or v is not None},
            "spatial_parts": spatial_parts,
            "spatial_record": candidate_spatial_record(seg),
            "cand_desc": None if cand_desc is None else {k: v for k, v in cand_desc.items() if k != "norm_xy"},
            "v2": {},
        }
        # keep chamfer in parts for contrib tables
        if shape_parts.get("chamfer") is not None:
            row["shape_parts"]["chamfer"] = shape_parts["chamfer"]
        for name, spec in VARIANTS.items():
            use_building = bool(spec.get("building"))
            weights = V2_WEIGHTS_BUILDING_COARSE if use_building else V2_WEIGHTS_NO_BUILDING
            os_keys = OS_KEYS_BUILDING if use_building else OS_KEYS_NO_BUILDING
            use_feats = dict(feats if use_building else feats_nb)
            ablate = spec.get("ablate")
            if ablate == "shape":
                use_feats["shape_v2"] = None
            elif ablate == "spatial":
                use_feats["spatial_v2"] = None
            score, contrib, coverage, factor = score_v2(
                use_feats,
                aerial=item.get("aerial_similarity"),
                exterior=item.get("exterior_similarity"),
                stand_size=size_score,
                weights=weights,
                os_keys=os_keys,
                missing=spec["missing"],
            )
            row["v2"][name] = {
                "score": score,
                "contrib": contrib,
                "coverage": coverage,
                "factor": factor,
                "feats": use_feats,
            }
            row[f"{name}_score"] = score
        rows.append(row)

    baseline_sorted = sorted(rows, key=lambda r: int(r["baseline_rank"]))
    pr5_sorted = sorted(rows, key=lambda r: int(r["pr5_neutral_rank"]))
    ranked = {name: _rank(rows, f"{name}_score") for name in VARIANTS}

    def eval_of(rank_key: str, score_key: str) -> dict | None:
        by = {row["stand_number"]: row for row in rows}
        row = by.get(EVAL_STAND)
        if row is None:
            return None
        ordered = sorted(rows, key=lambda item: (-float(item[score_key]), str(item["stand_number"])))
        top1 = ordered[0]
        top2 = ordered[1]
        rank = next(i for i, item in enumerate(ordered, start=1) if item["stand_number"] == EVAL_STAND)
        # nearest competing high-conf pool that is not 365
        rivals = [
            item
            for item in ordered
            if item["stand_number"] != EVAL_STAND and item.get("os_high_conf_pool")
        ]
        nearest = rivals[0] if rivals else None
        # visually similar distractors called out in prior work
        named = {item["stand_number"]: item for item in ordered}
        return {
            "stand_number": EVAL_STAND,
            "rank": rank,
            "score": row[score_key],
            "top1_stand": top1["stand_number"],
            "top1_score": top1[score_key],
            "top2_stand": top2["stand_number"],
            "top2_score": top2[score_key],
            "margin_1_2": round(float(top1[score_key]) - float(top2[score_key]), 4),
            "margin_365_nearest_highconf": None
            if nearest is None
            else round(float(row[score_key]) - float(nearest[score_key]), 4),
            "nearest_highconf_stand": None if nearest is None else nearest["stand_number"],
            "nearest_highconf_rank": None
            if nearest is None
            else next(i for i, item in enumerate(ordered, start=1) if item["stand_number"] == nearest["stand_number"]),
            "named_rivals": {
                stand: {
                    "rank": next(i for i, item in enumerate(ordered, start=1) if item["stand_number"] == stand),
                    "score": named[stand][score_key],
                    "os_pool_status": named[stand]["os_pool_status"],
                }
                for stand in ("404", "348", "420", "611")
                if stand in named
            },
        }

    blob_fp_baseline = [
        row["stand_number"]
        for row in baseline_sorted[:20]
        if row["blob_pool_present"] and row["os_pool_status"] in BLOB_FP_STATUSES
    ]

    def fp_removed(ordered: list[dict]) -> dict:
        top20_ids = {row["stand_number"] for row in ordered[:20]}
        still = [stand for stand in blob_fp_baseline if stand in top20_ids]
        gone = [stand for stand in blob_fp_baseline if stand not in top20_ids]
        rejected_in_top20 = sum(1 for row in ordered[:20] if row["os_pool_status"] in BLOB_FP_STATUSES)
        return {
            "blob_fp_in_baseline_top20": blob_fp_baseline,
            "still_in_top20": still,
            "removed_from_top20": gone,
            "n_removed": len(gone),
            "n_rejected_or_unknown_in_new_top20": rejected_in_top20,
        }

    variant_payload = {}
    for name, spec in VARIANTS.items():
        ordered = ranked[name]
        score_key = f"{name}_score"
        rank_key = f"{score_key}_rank"
        top20 = [_compact(row, score_key, rank_key, name) for row in ordered[:20]]
        scores = [row[score_key] for row in ordered]
        variant_payload[name] = {
            "note": spec["note"],
            "missing": spec["missing"],
            "building": spec.get("building"),
            "ablate": spec.get("ablate"),
            "eval": eval_of(rank_key, score_key),
            "confidence": assess_separation(scores),
            "top20": top20,
            "false_positives": fp_removed(ordered),
        }

    eval_365 = {row["stand_number"]: row for row in rows}[EVAL_STAND]
    payload = {
        "listing_id": LISTING_ID,
        "os_version": "object_segmentation_v1",
        "scoring_version": "os_scoring_v2",
        "production_ranking_modified": False,
        "os_v1_modified": False,
        "native15_crops_modified": False,
        "frozen_baseline_modified": False,
        "listing_specific_rules": False,
        "stand_specific_rules": False,
        "ags_downloads": 0,
        "n_candidates": len(rows),
        "evaluation_stand": EVAL_STAND,
        "listing_shape_descriptors": None if listing_shape is None else {k: v for k, v in listing_shape.items() if k != "norm_xy"},
        "listing_driveway_spatial": None,
        "building_term": "removed vs presence-only coarse; never listing-oblique roof fraction vs nadir area",
        "driveway_term": "omitted; frozen listing fingerprint has no driveway side/approach",
        "frozen_baseline": {
            "source": str(PR5_ALL.relative_to(ROOT)),
            "eval": eval_of("baseline_rank", "baseline_score"),
            "top20": [
                {
                    "rank": row["baseline_rank"],
                    "stand_number": row["stand_number"],
                    "score": row["baseline_score"],
                    "os_pool_status": row["os_pool_status"],
                    "blob_pool_present": row["blob_pool_present"],
                }
                for row in baseline_sorted[:20]
            ],
            "false_positives": fp_removed(baseline_sorted),
        },
        "pr5_neutral_0.5": {
            "eval": eval_of("pr5_neutral_rank", "pr5_neutral_score"),
            "top20": [
                {
                    "rank": row["pr5_neutral_rank"],
                    "stand_number": row["stand_number"],
                    "score": row["pr5_neutral_score"],
                    "os_pool_status": row["os_pool_status"],
                    "coverage_note": "PR5 0.5-fill of OS v1 coarse features",
                    "os_features": row.get("os_features"),
                }
                for row in pr5_sorted[:20]
            ],
            "false_positives": fp_removed(pr5_sorted),
        },
        "variants": variant_payload,
        "eval_stand_features": {
            "stand_number": EVAL_STAND,
            "v2_feats": eval_365["v2_feats"],
            "shape_parts": eval_365["shape_parts"],
            "spatial_parts": eval_365["spatial_parts"],
            "spatial_record": eval_365["spatial_record"],
            "cand_desc": eval_365["cand_desc"],
            "baseline_rank": eval_365["baseline_rank"],
            "pr5_neutral_rank": eval_365["pr5_neutral_rank"],
            "variant_scores": {name: eval_365[f"{name}_score"] for name in VARIANTS},
            "variant_contrib": {name: eval_365["v2"][name] for name in VARIANTS},
        },
        "runtime_s": round(time.time() - started, 2),
    }
    (OUT / "latest.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    slim = [
        {
            "stand_number": row["stand_number"],
            "baseline_rank": row["baseline_rank"],
            "pr5_neutral_rank": row["pr5_neutral_rank"],
            **{f"{name}_rank": row[f"{name}_score_rank"] for name in VARIANTS},
            **{f"{name}_score": row[f"{name}_score"] for name in VARIANTS},
            "os_pool_status": row["os_pool_status"],
            "coverage_neutral_nobuilding": row["v2"]["v2_neutral_nobuilding"]["coverage"],
            "shape_v2": row["v2_feats"]["shape_v2"],
            "spatial_v2": row["v2_feats"]["spatial_v2"],
        }
        for row in baseline_sorted
    ]
    (OUT / "all_candidates.json").write_text(json.dumps({"n": len(slim), "rows": slim}, indent=2), encoding="utf-8")

    # Panels
    listing_xy = None if listing_shape is None else np.asarray(listing_shape["norm_xy"], dtype=np.float64)
    panel_stands = []
    seen = set()
    for stand in [EVAL_STAND, "404", "348", "420"] + [
        row["stand_number"] for row in ranked["v2_neutral_nobuilding"][:5]
    ]:
        if stand in seen:
            continue
        seen.add(stand)
        panel_stands.append(stand)
    items = []
    colors = [(255, 196, 64), (80, 180, 255), (255, 110, 110), (160, 220, 120), (200, 160, 255)]
    items.append(("listing contour (frozen)", listing_xy, (220, 220, 230)))
    for i, stand in enumerate(panel_stands[:6]):
        seg = _load_seg(stand)
        desc = contour_descriptors((seg.get("pool") or {}).get("contour")) if is_high_conf(seg.get("pool")) else None
        xy = None if desc is None else np.asarray(desc["norm_xy"], dtype=np.float64)
        status = (seg.get("pool") or {}).get("status")
        items.append((f"{stand} {status}", xy, colors[i % len(colors)]))
    _draw_contour_panel(listing_xy, items, OUT / "panels" / "shape_contours.png")

    for stand in panel_stands[:8]:
        seg = _load_seg(stand)
        row = next(item for item in rows if item["stand_number"] == stand)
        title = (
            f"{stand} pool={row['os_pool_status']} "
            f"shape={row['v2_feats']['shape_v2']} spatial={row['v2_feats']['spatial_v2']}"
        )
        _draw_crop_overlay(stand, seg, OUT / "panels" / f"crop_{_safe(stand)}.jpg", title)

    print("Scoring v2 A/B — listing", LISTING_ID)
    print(f"  n={len(rows)} frozen listing contour={listing_shape is not None}")
    print(f"  EVAL {EVAL_STAND}: baseline #{eval_365['baseline_rank']}  PR5-neutral #{eval_365['pr5_neutral_rank']}")
    for name in VARIANTS:
        ev = variant_payload[name]["eval"]
        conf = variant_payload[name]["confidence"]
        print(
            f"  {name:32s} 365=#{ev['rank']:<3} score={ev['score']:.3f} "
            f"top1={ev['top1_stand']}@{ev['top1_score']:.3f}  "
            f"gap12={ev['margin_1_2']:.4f}  low_conf={conf['low_confidence']}"
        )
    print(f"\nwrote {OUT / 'latest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
