#!/usr/bin/env python3
"""Diagnostic-only Shape v2 forensic for listing 116778622 / PR #32.

Reads the frozen ranking. Does not rewrite freeze.json, freeze.sha256,
rankings_frozen.json, or production Scoring v2 weights. Pool Shape Family v1
is experimental and is not imported into score_v2.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.gis.estate_ags_matching.blind_116273255_complete_estate import (  # noqa: E402
    load_os_payload,
)
from backend.gis.estate_ags_matching.estate_property_inventory_v1 import (  # noqa: E402
    crop_path_for,
)
from backend.gis.estate_ags_matching.hybrid_geometry_ranking_test import (  # noqa: E402
    listing_evidence_from_hybrid_block,
)
from backend.gis.estate_ags_matching.os_scoring_v2 import (  # noqa: E402
    V2_WEIGHTS_NO_BUILDING,
    contour_descriptors,
)
from backend.gis.estate_ags_matching.pool_shape_family_v1 import (  # noqa: E402
    adjusted_total_score,
    chamfer_at_stage,
    classify_contour,
    compatibility,
    contour_metrics_scaled,
    decompose_shape_v2,
    hard_reject,
    pca_normalize_steps,
    penalty_multiplier,
    scaled_geometry,
    stage_contours,
)

INV = ROOT / "data" / "investigations" / "blind_116778622_current_stack"
FREEZE_PATH = INV / "freeze.json"
FREEZE_SHA_PATH = INV / "freeze.sha256"
EXPECTED_SHA = "dce17f82162920ceeb6d39c2aa2b456a5bcdb16399ecfeb853e7892a0b694a29"
FROZEN_WEIGHTS = {
    "pool_presence": 0.14,
    "shape_v2": 0.36,
    "spatial_v2": 0.22,
    "aerial": 0.12,
    "exterior": 0.06,
    "gis": 0.03,
    "stand_size": 0.07,
}
TOP5 = ["540", "411", "591", "897", "871"]
PHOTO_STEM = "116778622-005"
ESTATE_ID = "carlswald_north_corrected_002"
OS_MASK_DIR = ROOT / "data" / "investigations" / "object_segmentation_v1" / "carlswald_north" / "masks"
OS_COMPLETE = ROOT / "data" / "investigations" / "object_segmentation_v1" / "carlswald_north_complete" / "json"
OS_FROZEN = ROOT / "data" / "investigations" / "object_segmentation_v1" / "carlswald_north" / "json"
OUT = INV
CONTOURS_DIR = OUT / "shape_v2_exact_contours"
PIPE_DIR = OUT / "panels" / "shape_v2_pipeline"
FAMILY_PANEL = OUT / "panels" / "shape_family_validation.jpg"

HISTORICAL = [
    {
        "listing": "115503057",
        "label": "Stand 401 labelled (rank-5 forensic)",
        "gt": "401",
        "dir": ROOT / "data" / "investigations" / "blind_115503057_complete_estate",
    },
    {
        "listing": "117262832",
        "label": "Stand 338 forensic",
        "gt": "338",
        "dir": ROOT / "data" / "investigations" / "blind_117262832_complete_estate",
    },
    {
        "listing": "117170887",
        "label": "Stand 641 labelled (inventory miss)",
        "gt": "641",
        "dir": ROOT / "data" / "investigations" / "blind_117170887_complete_estate",
    },
    {
        "listing": "116978058",
        "label": "unlabelled 116978058",
        "gt": None,
        "dir": ROOT / "data" / "investigations" / "blind_116978058_complete_estate",
    },
    {
        "listing": "116889694",
        "label": "unlabelled 116889694",
        "gt": None,
        "dir": ROOT / "data" / "investigations" / "blind_116889694_complete_estate",
    },
    {
        "listing": "116223230",
        "label": "unlabelled 116223230",
        "gt": None,
        "dir": ROOT / "data" / "investigations" / "blind_116223230_complete_estate",
    },
    {
        "listing": "116778622",
        "label": "PR #20 complete-estate freeze (same listing, different stack)",
        "gt": None,
        "dir": ROOT / "data" / "investigations" / "blind_116778622_complete_estate",
    },
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _assert_freeze() -> dict[str, Any]:
    got = _sha256(FREEZE_PATH)
    recorded = FREEZE_SHA_PATH.read_text(encoding="utf-8").strip()
    if got != EXPECTED_SHA or recorded != EXPECTED_SHA:
        raise SystemExit(f"Freeze SHA mismatch: got={got} recorded={recorded}")
    if dict(V2_WEIGHTS_NO_BUILDING) != FROZEN_WEIGHTS:
        raise SystemExit("Production Scoring v2 weights changed; abort forensic")
    return json.loads(FREEZE_PATH.read_text(encoding="utf-8"))


def _load_rows(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "rows" in data:
        return list(data["rows"])
    if isinstance(data, list):
        return data
    raise SystemExit(f"unrecognised candidates file {path}")


def _font(size: int) -> ImageFont.ImageFont:
    for p in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ):
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _draw_contour_on_canvas(
    xy: np.ndarray,
    size: int = 280,
    pad: int = 24,
    color: tuple[int, int, int] = (0, 200, 255),
    fill: tuple[int, int, int] | None = (0, 40, 70),
) -> Image.Image:
    img = Image.new("RGB", (size, size), (12, 14, 18))
    if xy is None or np.asarray(xy).size == 0:
        return img
    arr = np.asarray(xy, dtype=np.float64)
    draw = ImageDraw.Draw(img)
    mn = arr.min(axis=0)
    mx = arr.max(axis=0)
    span = float(max(mx[0] - mn[0], mx[1] - mn[1], 1e-6))
    scale = (size - 2 * pad) / span
    pts = []
    for x, y in arr:
        px = pad + (float(x) - mn[0]) * scale
        py = pad + (float(y) - mn[1]) * scale
        pts.append((px, py))
    if fill is not None and len(pts) >= 3:
        draw.polygon(pts, fill=fill, outline=color)
    else:
        draw.line(pts + [pts[0]], fill=color, width=3)
    return img


def _load_crop(stand: str) -> Image.Image | None:
    path = crop_path_for(ESTATE_ID, stand)
    if path.is_file():
        return Image.open(path).convert("RGB")
    return None


def _load_os_mask(stand: str, crop: Image.Image | None) -> Image.Image | None:
    mask_path = OS_MASK_DIR / f"{stand}_pool.png"
    if not mask_path.is_file() or crop is None:
        return None
    mask = np.array(Image.open(mask_path).convert("L"))
    arr = np.array(crop)
    if mask.shape[:2] != arr.shape[:2]:
        mask = cv2.resize(mask, (arr.shape[1], arr.shape[0]), interpolation=cv2.INTER_NEAREST)
    overlay = arr.copy()
    overlay[mask > 127] = (0, 180, 255)
    blended = cv2.addWeighted(arr, 0.45, overlay, 0.55, 0)
    return Image.fromarray(blended)


def _contour_overlay(base: Image.Image, contour: list, fill=(0, 180, 255), line=(255, 255, 0)) -> Image.Image:
    arr = np.array(base)
    h, w = arr.shape[:2]
    overlay = arr.copy()
    xy = np.array(contour, dtype=np.float64)
    if xy.max() <= 1.5:
        px = np.column_stack([xy[:, 0] * w, xy[:, 1] * h]).astype(np.int32)
    else:
        px = xy.astype(np.int32)
    cv2.fillPoly(overlay, [px], fill)
    cv2.polylines(overlay, [px], True, line, 2)
    blended = cv2.addWeighted(arr, 0.42, overlay, 0.58, 0)
    return Image.fromarray(blended)


def _hstack(images: list[Image.Image], labels: list[str], title: str) -> Image.Image:
    h = 300
    resized = []
    for im in images:
        r = im.copy()
        r.thumbnail((300, h))
        canvas = Image.new("RGB", (300, h), (8, 8, 10))
        canvas.paste(r, ((300 - r.width) // 2, (h - r.height) // 2))
        resized.append(canvas)
    pad_top, pad_bot = 48, 36
    out = Image.new("RGB", (300 * len(resized) + 20, h + pad_top + pad_bot), (10, 12, 16))
    draw = ImageDraw.Draw(out)
    draw.text((10, 8), title, fill=(230, 230, 230), font=_font(16))
    for i, (im, lab) in enumerate(zip(resized, labels)):
        out.paste(im, (10 + i * 300, pad_top))
        draw.text((14 + i * 300, pad_top + h + 8), lab, fill=(180, 200, 220), font=_font(12))
    return out


def _os_source_path(stand: str) -> str:
    complete = OS_COMPLETE / f"{stand}.json"
    frozen = OS_FROZEN / f"{stand}.json"
    if complete.is_file():
        return str(complete.relative_to(ROOT))
    return str(frozen.relative_to(ROOT))


def _pool_fields(payload: dict[str, Any]) -> dict[str, Any]:
    pool = payload.get("pool") or {}
    geom = pool.get("geometry") or {}
    return {
        "status": pool.get("status"),
        "extractor_notes": pool.get("notes"),
        "os_shape": geom.get("shape"),
        "area_m2": geom.get("area_m2"),
        "rectangularity": geom.get("rectangularity"),
        "convexity": geom.get("convexity"),
        "compactness": geom.get("compactness"),
        "aspect_ratio": geom.get("aspect_ratio"),
        "orientation_deg": geom.get("orientation_deg"),
        "contour_n_os": geom.get("contour_n"),
    }


def _dump_contour_record(name: str, source: dict[str, Any], contour: list, extra: dict[str, Any]) -> dict[str, Any]:
    arr = np.array(contour, dtype=np.float64)
    desc = contour_descriptors(contour) or {}
    geom = scaled_geometry(contour) or {}
    rec = {
        "id": name,
        "source_image": source,
        "extractor": extra.get("extractor"),
        "contour_image_01": [[round(float(x), 6), round(float(y), 6)] for x, y in arr.tolist()],
        "contour_point_count": int(arr.shape[0]),
        "raw_bbox_norm": {
            "x_min": float(arr[:, 0].min()),
            "y_min": float(arr[:, 1].min()),
            "x_max": float(arr[:, 0].max()),
            "y_max": float(arr[:, 1].max()),
        },
        "width_norm": float(arr[:, 0].max() - arr[:, 0].min()),
        "height_norm": float(arr[:, 1].max() - arr[:, 1].min()),
        "aspect_ratio_aabb": float((arr[:, 0].max() - arr[:, 0].min()) / max(arr[:, 1].max() - arr[:, 1].min(), 1e-9)),
        "shape_v2_descriptors": {k: v for k, v in desc.items() if k != "norm_xy"},
        "scaled_geometry_400px": {k: v for k, v in geom.items() if k not in {"norm_xy", "shape_v2_descriptors"}},
        "pca_normalisation": pca_normalize_steps(),
        "simplification": extra.get("simplification"),
        **{k: v for k, v in extra.items() if k not in {"extractor", "simplification"}},
        "metrics_alias": contour_metrics_scaled(contour),
    }
    if rec["metrics_alias"]:
        rec["metrics_alias"] = {k: v for k, v in rec["metrics_alias"].items() if k not in {"norm_xy", "shape_v2_descriptors"}}
    (CONTOURS_DIR / f"{name}.json").write_text(json.dumps(rec, indent=2), encoding="utf-8")
    return rec


def _pipeline_panel(name: str, raw: Image.Image, mask: Image.Image, contour: list, title: str) -> Path:
    raw_c = _draw_contour_on_canvas(np.array(contour, dtype=np.float64), color=(80, 220, 255))
    desc = contour_descriptors(contour) or {}
    nxy = np.array(desc.get("norm_xy") or contour, dtype=np.float64)
    nrm = _draw_contour_on_canvas(nxy, color=(255, 180, 40), fill=(60, 40, 10))
    panel = _hstack(
        [raw, mask, raw_c, nrm],
        ["1. raw image/frame", "2. detected pool mask", "3. raw contour (0–1)", "4. Shape v2 PCA-normalised"],
        title,
    )
    out = PIPE_DIR / f"{name}.jpg"
    panel.save(out, quality=90)
    return out


def _family_validation_panel(items: list[dict[str, Any]]) -> None:
    cols = 4
    cell_w, cell_h = 280, 340
    rows = math.ceil(len(items) / cols)
    canvas = Image.new("RGB", (cols * cell_w + 20, rows * cell_h + 50), (8, 10, 14))
    draw = ImageDraw.Draw(canvas)
    draw.text((12, 10), "Pool Shape Family v1 — diagnostic validation (geometry only)", fill=(230, 230, 230), font=_font(18))
    for i, it in enumerate(items):
        r, c = divmod(i, cols)
        xy = np.array(it["contour"], dtype=np.float64)
        thumb = _draw_contour_on_canvas(xy, size=240)
        x0, y0 = 10 + c * cell_w, 46 + r * cell_h
        canvas.paste(thumb, (x0 + 10, y0))
        lab = f"{it['label']}\n{it['family']}  {it['confidence']:.2f}\n{it['reason'][:42]}"
        draw.multiline_text((x0 + 10, y0 + 248), lab, fill=(200, 210, 220), font=_font(12), spacing=2)
    FAMILY_PANEL.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(FAMILY_PANEL, quality=90)


def _os_contour(stand: str) -> list | None:
    payload = load_os_payload(stand)
    if not payload:
        return None
    c = (payload.get("pool") or {}).get("contour")
    return c if c else None


def _historical_run(freeze_dir: Path, gt: str | None) -> dict[str, Any]:
    ac_path = freeze_dir / "all_candidates.json"
    hb_path = freeze_dir / "hybrid_block.json"
    out: dict[str, Any] = {
        "dir": str(freeze_dir.relative_to(ROOT)),
        "has_all_candidates": ac_path.exists(),
        "has_hybrid": hb_path.exists(),
    }
    if not ac_path.exists() or not hb_path.exists():
        return out
    hb = json.loads(hb_path.read_text(encoding="utf-8"))
    listing = listing_evidence_from_hybrid_block(hb)
    fp = listing.get("fingerprint")
    listing_c = None if fp is None else fp.contour_image
    lf = classify_contour(listing_c) if listing_c else None
    out["listing_family"] = None if lf is None else {k: lf[k] for k in ("family", "confidence", "reason")}
    rows = _load_rows(ac_path)
    ranked = sorted(rows, key=lambda r: -float(r.get("score") if r.get("score") is not None else r.get("score_v2") or 0.0))
    diag_pen = []
    for i, r in enumerate(ranked, start=1):
        stand = str(r.get("stand_number") or r.get("stand_id"))
        contour = _os_contour(stand)
        fam = classify_contour(contour) if contour else None
        listing_fam_name = lf["family"] if lf else "UNKNOWN"
        cand_fam_name = fam["family"] if fam else "UNKNOWN"
        compat = compatibility(listing_fam_name, cand_fam_name)
        shape = r.get("shape_v2")
        total = float(r.get("score") if r.get("score") is not None else r.get("score_v2") or 0.0)
        rec = {
            "stand_id": stand,
            "old_rank": int(r.get("rank") or i),
            "score_v2": total,
            "shape_v2": shape,
            "family": None if fam is None else fam["family"],
            "confidence": None if fam is None else fam["confidence"],
            "compatibility": compat,
            "hard_reject": hard_reject(compat),
            "adj_score": adjusted_total_score(total, None if shape is None else float(shape), compat),
            "os_status_native": (load_os_payload(stand) or {}).get("pool", {}).get("status"),
        }
        diag_pen.append(rec)
    diag_pen.sort(key=lambda x: -x["adj_score"])
    for i, rec in enumerate(diag_pen, start=1):
        rec["diag_rank_penalty"] = i
    diag_hard = [r for r in diag_pen if not r["hard_reject"]]
    diag_hard.sort(key=lambda x: -float(x["score_v2"] or 0.0))
    hard_rank = {r["stand_id"]: i for i, r in enumerate(diag_hard, start=1)}
    out["n_candidates"] = len(ranked)
    out["n_hard_rejected"] = sum(1 for r in diag_pen if r["hard_reject"])
    out["top5_penalty"] = [
        {k: r[k] for k in ("stand_id", "old_rank", "diag_rank_penalty", "family", "compatibility", "shape_v2", "adj_score")}
        for r in diag_pen[:5]
    ]
    if gt:
        matches = [r for r in diag_pen if r["stand_id"] == str(gt)]
        if not matches:
            out["ground_truth"] = {"stand": gt, "in_candidates": False}
        else:
            gt_row = matches[0]
            out["ground_truth"] = {
                "stand": gt,
                "in_candidates": True,
                "old_rank": gt_row["old_rank"],
                "diag_rank_penalty": gt_row["diag_rank_penalty"],
                "hard_rejected": gt_row["hard_reject"],
                "diag_rank_hard": hard_rank.get(str(gt)),
                "family": gt_row["family"],
                "listing_family": lf["family"] if lf else None,
                "compatibility": gt_row["compatibility"],
                "shape_v2": gt_row["shape_v2"],
                "wrongly_hard_rejected": bool(gt_row["hard_reject"]),
            }
    else:
        out["ground_truth"] = None
    return out


def main() -> int:
    CONTOURS_DIR.mkdir(parents=True, exist_ok=True)
    PIPE_DIR.mkdir(parents=True, exist_ok=True)
    freeze = _assert_freeze()
    hb = json.loads((INV / "hybrid_block.json").read_text(encoding="utf-8"))
    listing = listing_evidence_from_hybrid_block(hb)
    fp = listing["fingerprint"]
    listing_contour = fp.contour_image
    chosen = listing.get("chosen_frame") or {}
    dominant = chosen.get("dominant") or {}
    geom = dominant.get("geometry") or {}
    freeze_shape = (
        ((freeze.get("listing_fingerprint") or {}).get("hybrid_evidence") or {}).get("listing_shape")
    )
    if freeze_shape is None:
        freeze_shape = freeze.get("listing_shape")
    recomputed = {k: v for k, v in (contour_descriptors(listing_contour) or {}).items() if k != "norm_xy"}
    photo_path = INV / "photos" / f"{PHOTO_STEM}.jpg"
    photo = Image.open(photo_path).convert("RGB") if photo_path.exists() else Image.new("RGB", (640, 480), (20, 20, 20))

    listing_src = {
        "kind": "hybrid_frame_dominant.contour_image",
        "frame_id": PHOTO_STEM,
        "photo": str(photo_path.relative_to(ROOT)) if photo_path.exists() else None,
        "extractor": chosen.get("source") or chosen.get("extractor"),
        "viewpoint": chosen.get("viewpoint"),
        "hybrid_qualitative_class": fp.shape_class,
        "hybrid_indent_count_raw": geom.get("n_major_indents"),
        "hybrid_aspect_ratio": geom.get("aspect_ratio"),
        "hybrid_solidity": geom.get("solidity"),
        "hybrid_compactness": geom.get("compactness"),
        "freeze_listing_shape_descriptors": freeze_shape,
        "recomputed_descriptors_match_freeze": (
            freeze_shape is None
            or all(
                freeze_shape.get(k) == recomputed.get(k)
                for k in ("circularity", "solidity", "elongation", "n_corners", "n_major_indents", "sharp_frac")
                if k in (freeze_shape or {})
            )
        ),
        "geometry_preserved_note": "scoring contour n_major_indents may differ from Hybrid raw indent_count",
    }
    listing_rec = _dump_contour_record(
        "listing_116778622-005",
        listing_src,
        listing_contour,
        {
            "extractor": "yoloe_sam2_hybrid (pool_overview) → HybridGeometryEngine.contour_image 64-pt resample",
            "simplification": "Hybrid resamples to 64 points; Shape v2 pca_normalize (no approxPolyDP on the scored polyline)",
            "role": "target",
        },
    )
    listing_mask = _contour_overlay(photo, listing_contour)
    _pipeline_panel(
        "listing_116778622-005",
        photo,
        listing_mask,
        listing_contour,
        f"Listing {PHOTO_STEM}  hybrid_class={fp.shape_class}",
    )

    ranking = _load_rows(INV / "all_candidates.json")
    ranking.sort(key=lambda r: int(r.get("rank") or 10**9))
    by_id = {str(r["stand_number"]): r for r in ranking}

    for stand in TOP5:
        payload = load_os_payload(stand)
        if not payload:
            raise SystemExit(f"missing OS payload for {stand}")
        contour = payload["pool"]["contour"]
        crop = _load_crop(stand)
        native = _pool_fields(payload)
        freeze_row = by_id[stand]
        rec = _dump_contour_record(
            f"stand_{stand}",
            {
                "kind": "os_v1_pool.contour",
                "crop": str(crop_path_for(ESTATE_ID, stand).relative_to(ROOT)),
                "os_json": _os_source_path(stand),
                "os_mask": str((OS_MASK_DIR / f"{stand}_pool.png").relative_to(ROOT))
                if (OS_MASK_DIR / f"{stand}_pool.png").exists()
                else None,
            },
            contour,
            {
                "extractor": native["extractor_notes"],
                "os_status_native": native["status"],
                "os_status_after_pov_overlay": freeze_row.get("candidate_pov_status") or freeze_row.get("os_pool_status"),
                "frozen_os_pool_status": freeze_row.get("frozen_os_pool_status"),
                "os_shape_class_native": native["os_shape"],
                "os_area_m2": native["area_m2"],
                "os_rectangularity": native["rectangularity"],
                "os_reject_notes": native["extractor_notes"],
                "pov_changes_contour": False,
                "simplification": "OS contour as stored (image-normalised 0–1); Shape v2 pca_normalize; no convex hull substitution",
            },
        )
        raw_im = crop if crop is not None else Image.new("RGB", (320, 320), (20, 20, 20))
        mask = _load_os_mask(stand, crop) or _contour_overlay(raw_im, contour)
        _pipeline_panel(
            f"stand_{stand}",
            raw_im,
            mask,
            contour,
            f"Stand {stand}  OS {native['status']} {native['os_shape']}  area={native['area_m2']}m2",
        )
        _ = rec

    listing_desc = contour_descriptors(listing_contour)
    decomp_rows = []
    for stand in TOP5:
        contour = load_os_payload(stand)["pool"]["contour"]
        parts = decompose_shape_v2(listing_desc, contour_descriptors(contour))
        parts["stand_id"] = stand
        parts["frozen_shape_v2"] = by_id[stand].get("shape_v2")
        decomp_rows.append(parts)

    ablation = {}
    for stand in ("540", "411"):
        contour = load_os_payload(stand)["pool"]["contour"]
        ablation[stand] = {
            "chamfer_after_each_stage": chamfer_at_stage(listing_contour, contour),
            "listing_stage_point_counts": {k: len(v or []) for k, v in stage_contours(listing_contour).items()},
            "candidate_stage_point_counts": {k: len(v or []) for k, v in stage_contours(contour).items()},
        }

    listing_family = classify_contour(listing_contour)
    family_rows = []
    listing_row = {
        "id": PHOTO_STEM,
        "label": f"listing {PHOTO_STEM}",
        "family": listing_family["family"],
        "confidence": listing_family["confidence"],
        "reason": listing_family["reason"],
        "features": listing_family["features"],
        "compatibility_vs_listing": "self",
        "hard_reject": False,
        "penalty_multiplier": 1.0,
        "frozen_shape_v2": None,
        "frozen_score_v2": None,
        "adj_shape_v2": None,
        "adj_score_v2": None,
    }
    family_rows.append(listing_row)
    for stand in TOP5:
        contour = load_os_payload(stand)["pool"]["contour"]
        fam = classify_contour(contour)
        compat = compatibility(listing_family["family"], fam["family"])
        row = by_id[stand]
        family_rows.append(
            {
                "id": stand,
                "label": f"stand {stand}",
                "family": fam["family"],
                "confidence": fam["confidence"],
                "reason": fam["reason"],
                "features": fam["features"],
                "compatibility_vs_listing": compat,
                "hard_reject": hard_reject(compat),
                "penalty_multiplier": penalty_multiplier(compat),
                "frozen_shape_v2": row.get("shape_v2"),
                "frozen_score_v2": row.get("score"),
                "adj_shape_v2": None if row.get("shape_v2") is None else round(float(row["shape_v2"]) * penalty_multiplier(compat), 4),
                "adj_score_v2": adjusted_total_score(float(row["score"]), row.get("shape_v2"), compat),
            }
        )

    extra_stands = ["338", "401", "624", "868", "545", "648", "216", "217"]
    panel_items = [
        {
            "label": f"listing {PHOTO_STEM}",
            "contour": listing_contour,
            "family": listing_family["family"],
            "confidence": listing_family["confidence"],
            "reason": listing_family["reason"],
        }
    ]
    for stand in TOP5 + extra_stands:
        c = _os_contour(stand)
        if not c:
            continue
        fam = classify_contour(c)
        panel_items.append(
            {
                "label": f"stand {stand}",
                "contour": c,
                "family": fam["family"],
                "confidence": fam["confidence"],
                "reason": fam["reason"],
            }
        )
    _family_validation_panel(panel_items)

    top20 = ranking[:20]
    top20_diag = []
    for r in top20:
        stand = str(r["stand_number"])
        contour = _os_contour(stand)
        fam = classify_contour(contour) if contour else {"family": "UNKNOWN", "confidence": 0.0, "reason": "no contour", "features": {}}
        compat = compatibility(listing_family["family"], fam["family"]) if contour else "no_decision"
        top20_diag.append(
            {
                "stand_id": stand,
                "frozen_rank": r.get("rank"),
                "candidate_family": fam["family"],
                "candidate_confidence": fam.get("confidence"),
                "listing_family": listing_family["family"],
                "compatibility": compat,
                "hard_reject": hard_reject(compat),
                "frozen_shape_v2": r.get("shape_v2"),
                "frozen_score_v2": r.get("score"),
                "adj_shape_v2": None if r.get("shape_v2") is None else round(float(r["shape_v2"]) * penalty_multiplier(compat), 4),
                "adj_score_v2": adjusted_total_score(float(r["score"]), r.get("shape_v2"), compat),
            }
        )
    pen_sorted = sorted(top20_diag, key=lambda x: -x["adj_score_v2"])
    rank_map = {rec["stand_id"]: i for i, rec in enumerate(pen_sorted, start=1)}
    hard_kept = [r for r in top20_diag if not r["hard_reject"]]
    hard_kept_sorted = sorted(hard_kept, key=lambda x: -float(x["frozen_score_v2"]))
    hard_rank = {r["stand_id"]: i for i, r in enumerate(hard_kept_sorted, start=1)}
    for rec in top20_diag:
        rec["diag_rank_among_top20_penalty"] = rank_map[rec["stand_id"]]
        rec["diag_rank_among_top20_hard"] = None if rec["hard_reject"] else hard_rank[rec["stand_id"]]

    hist = []
    for spec in HISTORICAL:
        hist.append({"listing": spec["listing"], "label": spec["label"], **_historical_run(spec["dir"], spec["gt"])})

    diagnostic = {
        "experiment": "shape_v2_forensic_116778622",
        "production_weights_unchanged": True,
        "production_weights": dict(V2_WEIGHTS_NO_BUILDING),
        "freeze_sha256": EXPECTED_SHA,
        "freeze_files_untouched": True,
        "listing_family": {
            "family": listing_family["family"],
            "confidence": listing_family["confidence"],
            "reason": listing_family["reason"],
            "features": listing_family["features"],
        },
        "recomputed_listing_descriptors_match_freeze": listing_src["recomputed_descriptors_match_freeze"],
        "top5": family_rows,
        "top20": top20_diag,
        "decomposition": decomp_rows,
        "normalisation_ablation": ablation,
        "compatibility_matrix_policy": {
            "hard_reject": "incompatible families dropped from diagnostic ranking A",
            "penalty": "shape_v2 contribution multiplied by 0.20 incompatible / 0.55 partial; not tuned to a stand",
        },
        "historical": [
            {
                "listing": h["listing"],
                "label": h["label"],
                "ground_truth": h.get("ground_truth"),
                "listing_family": h.get("listing_family"),
                "n_hard_rejected": h.get("n_hard_rejected"),
                "n_candidates": h.get("n_candidates"),
            }
            for h in hist
        ],
    }
    (OUT / "shape_family_diagnostic.json").write_text(json.dumps(diagnostic, indent=2, default=str), encoding="utf-8")

    _write_forensic_md(
        listing_family=listing_family,
        listing_rec=listing_rec,
        decomp_rows=decomp_rows,
        ablation=ablation,
        family_rows=family_rows,
        top20_diag=top20_diag,
        fp=fp,
        listing_src=listing_src,
        freeze=freeze,
    )
    _write_regression_md(hist, listing_family)

    assert _sha256(FREEZE_PATH) == EXPECTED_SHA
    print("OK freeze SHA", EXPECTED_SHA)
    print("listing family", listing_family["family"], listing_family["confidence"], listing_family["reason"])
    for row in family_rows:
        print(row["id"], row["family"], row["compatibility_vs_listing"], row.get("frozen_shape_v2"))
    return 0


def _write_forensic_md(
    *,
    listing_family: dict[str, Any],
    listing_rec: dict[str, Any],
    decomp_rows: list[dict[str, Any]],
    ablation: dict[str, Any],
    family_rows: list[dict[str, Any]],
    top20_diag: list[dict[str, Any]],
    fp: Any,
    listing_src: dict[str, Any],
    freeze: dict[str, Any],
) -> None:
    listing_g = listing_rec.get("scaled_geometry_400px") or {}
    p540 = next((p for p in decomp_rows if p["stand_id"] == "540"), {})
    c540 = p540.get("contributions") or {}
    order = ["elongation", "chamfer", "hu", "solidity", "n_indents", "max_indent", "n_corners", "circularity", "sharp_frac", "radial_cv"]
    fam540 = next((r for r in family_rows if r["id"] == "540"), {})
    fam411 = next((r for r in family_rows if r["id"] == "411"), {})
    listing_is_curved = listing_family["family"] in {"FREEFORM", "KIDNEY_CURVED", "COMPOUND_IRREGULAR"}
    rect_top = fam540.get("family") == "RECTANGULAR" and fam411.get("family") == "RECTANGULAR"
    if listing_is_curved and rect_top:
        decision = "MIXED FAILURE"
        decision_body = (
            "1. **Not a wrong-pool swap on Stand 540.** The scored OS contour is the in-parcel "
            "blob on the rectangular pool (native15 crop + OS mask/contour). The neighbouring "
            "freeform pool in the padded crop is **not** the contour that entered Shape v2.\n"
            "2. **Stand 411 is a POV-promoted REJECTED blob.** Native OS status is `REJECTED`; "
            "ranking overlay flipped status without changing the contour. The contour is still a "
            "compact rectangle (plus mask defects), not the listing freeform.\n"
            "3. **Listing segmentation of the object is correct** (photo-005 traces the actual pool) "
            "**but the scoring contour is lossy**: Hybrid qualitative class "
            f"`{fp.shape_class}`, resampled to 64 points, and Shape v2 PCA-normalises away pose. "
            "Scaled geometry still shows a **curved** signature that Shape v2 almost ignores "
            "(`sharp_frac` weight **0.03**).\n"
            "4. **Shape v2 descriptor failure is the dominant reason 540 scores 0.8161.** "
            "Elongation + chamfer + Hu + solidity treat two compact blobs as similar after "
            "rotation/scale normalisation. The rectangle-versus-freeform mismatch lives in unused "
            "or near-unused terms (angle entropy is not a Shape v2 input)."
        )
    elif not listing_is_curved:
        decision = "CONTOUR NORMALISATION FAILURE"
        decision_body = (
            "The listing contour that entered Shape v2 does **not** retain a freeform family "
            f"(classified `{listing_family['family']}`). Segmentation of the photo object may still "
            "be the right pool, but Hybrid resample + PCA descriptors collapsed it toward a compact "
            "polygon. Diagnose contour extraction/simplification before retuning weights."
        )
    else:
        decision = "SEGMENTATION FAILURE"
        decision_body = (
            "Shape Family v1 did not classify 540/411 as RECTANGULAR against a curved listing. "
            "Inspect pipeline panels: the scored contour may not be the visually obvious rectangle."
        )

    lines = [
        "# SHAPE_V2_FORENSIC — listing 116778622 (PR #32 diagnostic)",
        "",
        "Diagnostic experiment only. PR #32 freeze files and Scoring v2 production weights were not modified.",
        "",
        f"- Freeze SHA256 (verified unchanged): `{EXPECTED_SHA}`",
        "- Official fingerprint: `116778622-005` (YOLOE/SAM2, `pool_overview`)",
        "- Production Shape v2 weight remains **0.36** (untouched)",
        f"- Recomputed listing descriptors match freeze listing_shape: **{listing_src.get('recomputed_descriptors_match_freeze')}**",
        "",
        "## Phase 9 decision",
        "",
        f"**{decision}**",
        "",
        decision_body,
        "",
        "Pool Shape Family v1 should be **retained diagnostic-only** in this PR. It is **not** promoted into production Shape v2 and is **not** a hard gate on ranking. Historical check: do not hard-reject known true stands. Stand 338 never had `shape_v2` (OS REJECTED) so a shape gate cannot rescue that case.",
        "",
        "## Phase 1 — Exact contours that entered Shape v2",
        "",
        "### First question",
        "",
        "**Is PIE scoring the visually obvious square pool on 540 and 411, or a different extracted shape?**",
        "",
        "- **540: the in-parcel rectangular pool.** FastSAM mask can be leaky (OS class `kidney_or_curved`) but the blob sits on the rectangular pool, not the neighbour freeform. Visual: `panels/shape_v2_pipeline/stand_540.jpg`.",
        "- **411: a rectangular OS blob that OS itself rejected.** POV overlay only changed `pool.status`. Visual: `panels/shape_v2_pipeline/stand_411.jpg`.",
        "- **Listing 005: the real freeform/waist pool in the photo.** Segmentation of the *object* is OK. The *descriptor* after 64-pt resample + PCA looks compact (`n_corners=4` in freeze listing_shape).",
        "",
        "Because the 540 contour is the rectangle, **this is not a stop-at-segmentation-only case.** Segmentation of 540 is imperfect (leaky mask / wrong OS class) but the scored object is the square pool. Shape v2 then over-matches it to the listing.",
        "",
        "Exact JSON dumps: `shape_v2_exact_contours/`. Pipeline panels: `panels/shape_v2_pipeline/`.",
        "",
        "### Listing 116778622-005",
        "",
        f"- Extractor: YOLOE/SAM2 Hybrid; `contour_image` 64-pt resample; qualitative Hybrid class `{fp.shape_class}`",
        f"- Point count: {listing_rec['contour_point_count']}",
        (
            f"- Scaled (400 px) rectangularity={listing_g.get('rectangularity')} solidity={listing_g.get('solidity')} "
            f"elongation={listing_g.get('elongation')} circularity={listing_g.get('circularity')} "
            f"sharp_frac={listing_g.get('sharp_frac')} angle_entropy={listing_g.get('angle_entropy')} "
            f"n_major_indents={listing_g.get('n_major_indents')}"
        ),
        "- Shape v2 normalisation: center → PCA-align major axis → flip heavier half to +x → scale to unit max radius → chamfer with 4 axis flips",
        f"- Hybrid raw indents: {listing_src.get('hybrid_indent_count_raw')}; freeze n_major_indents in listing_shape: {(listing_src.get('freeze_listing_shape_descriptors') or {}).get('n_major_indents')}",
        "",
        "### Top-5 OS contours",
        "",
        "| Stand | Native OS status | After POV | Native OS class | area_m² | OS rectangularity | Shape Family v1 |",
        "| --- | --- | --- | --- | ---: | ---: | --- |",
    ]
    for row in family_rows:
        if row["id"] == PHOTO_STEM:
            continue
        stand = row["id"]
        payload = load_os_payload(stand)["pool"]
        geom = payload.get("geometry") or {}
        freeze_row = json.loads((INV / "all_candidates.json").read_text())["rows"]
        fr = next(r for r in freeze_row if str(r["stand_number"]) == stand)
        lines.append(
            f"| {stand} | {payload.get('status')} | {fr.get('candidate_pov_status') or fr.get('os_pool_status')} | "
            f"{geom.get('shape')} | {geom.get('area_m2')} | {geom.get('rectangularity')} | "
            f"{row['family']} ({row['confidence']:.2f}) |"
        )
    lines += [
        "",
        "## Phase 2 — Shape v2 component decomposition",
        "",
        "Production weights (unchanged): elongation 0.22, chamfer 0.18, hu 0.16, solidity 0.10, n_indents 0.08, max_indent 0.08, n_corners 0.08, circularity 0.05, **sharp_frac 0.03**, radial_cv 0.02.",
        "",
        "| Candidate | Final shape_v2 | elongation | chamfer | hu | solidity | n_indents | max_indent | n_corners | circularity | sharp_frac | radial_cv |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for parts in decomp_rows:
        terms = parts["terms"]
        cells = " | ".join(f"{terms[k]:.4f}" for k in order)
        lines.append(f"| {parts['stand_id']} | {parts['combined']:.4f} | {cells} |")
    lines += [
        "",
        "### Why Stand 540 obtains 0.8161",
        "",
        f"Reconstructed combined = **{p540.get('combined')}** (freeze `shape_v2={p540.get('frozen_shape_v2')}`).",
        "",
        "Weighted contributions:",
        "",
        "| Term | weight | similarity | contribution |",
        "| --- | ---: | ---: | ---: |",
    ]
    for k in order:
        lines.append(
            f"| {k} | {p540.get('weights', {}).get(k)} | {p540.get('terms', {}).get(k)} | {c540.get(k)} |"
        )
    lines += [
        "",
        "**Overpowering terms:** elongation, chamfer, Hu, solidity (weights 0.22+0.18+0.16+0.10). These are scale/rotation-invariant compactness stats. After PCA both listing and 540 look like compact blobs.",
        "",
        "**Underweighted mismatch:** `sharp_frac` (curves vs polygon corners) has weight **0.03**. Indent count mismatch is cheap (`n_indents` scale=4). **Angle entropy is not in Shape v2 at all.**",
        "",
        "Chamfer after PCA+4 flips is high — a rectangle and a mildly waisted freeform are close once both are unit-scaled and axis-aligned. Chamfer is **tolerant**, not the sole failure.",
        "",
        "## Phase 3 — Contour normalisation ablation",
        "",
        "Chamfer similarity `1/(1+4·mean_nn)` (best of 4 axis flips). Pre-final stages are unit-scaled so listing-photo vs aerial 0–1 frames are comparable. `final` is `pca_normalize` as Shape v2 uses.",
        "",
        "| Stage | vs 540 | vs 411 |",
        "| --- | ---: | ---: |",
    ]
    stages = list((ablation.get("540") or {}).get("chamfer_after_each_stage") or {})
    for st in stages:
        a = ablation["540"]["chamfer_after_each_stage"].get(st)
        b = ablation["411"]["chamfer_after_each_stage"].get(st)
        lines.append(f"| {st} | {a} | {b} |")
    lines += [
        "",
        "Interpretation:",
        "",
        "- **Translation-only / raw (unit-scaled, no PCA)** already yields a high chamfer if both contours are compact blobs of similar AABB aspect.",
        "- **Scale normalisation** removes pool-size (540 is ~14 m²). Expected for cross-source matching, but it also removes a cue that 540 is a small rectangle.",
        "- **Rotation / PCA** is required for aerial vs street-view yaw, but it makes a square and a freeform share a major-axis frame, after which chamfer is easy to satisfy.",
        "- **64-point resample** is applied to the listing Hybrid contour before freeze; OS contours keep native vertices then PCA. Resample rounds the listing waist toward a 4-corner blob (`n_corners=4`). Production `_resample` picks arc-length bins (no linear interpolation).",
        "- **No convex-hull substitution** is used as the scored contour.",
        "",
        "Normalisation is a **contributing** failure (PCA + unit scale + chamfer tolerance), not the only one. Descriptor choice is the larger issue: the pipeline throws away the curve-vs-polygon signal.",
        "",
        "## Phase 4–5 — Pool Shape Family v1",
        "",
        "Geometry-only classifier. No water colour, no stand identity, no listing-id hardcoding.",
        "",
        f"- Listing `{PHOTO_STEM}` → **{listing_family['family']}** (conf {listing_family['confidence']:.2f}): {listing_family['reason']}",
        "",
        "| Id | Family | Conf | vs listing | frozen shape_v2 |",
        "| --- | --- | ---: | --- | ---: |",
    ]
    for row in family_rows:
        lines.append(
            f"| {row['id']} | {row['family']} | {row['confidence']:.2f} | {row['compatibility_vs_listing']} | {row['frozen_shape_v2']} |"
        )
    lines += [
        "",
        "Validation panel: `panels/shape_family_validation.jpg`.",
        "",
        "Failure/limitation cases to inspect on the panel: OS leaky masks can add fake indents (411 may still be RECTANGULAR via the polygonal override); 871 COMPOUND from multiple indents may be mask noise; Hybrid listing contour can be FREEFORM on scaled curvature even though Hybrid qualitative class said rectangular.",
        "",
        "## Phase 6 — Diagnostic compatibility (not production)",
        "",
        "Policy (not tuned to a winner): incompatible multiplier **0.20**, partial **0.55**, compatible **1.0**. UNKNOWN never rejects.",
        "",
        "### A. Hard reject (Top 20 only, diagnostic)",
        "",
        "Clearly incompatible families are dropped from diagnostic ranking A. UNKNOWN is kept.",
        "",
        "### B. Penalty (replace Shape v2 contribution only; other frozen terms untouched)",
        "",
        "| Stand | frozen rank | family | compat | frozen shape_v2 | adj shape_v2 | frozen score | adj score |",
        "| --- | ---: | --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for rec in top20_diag:
        if rec["stand_id"] in TOP5:
            lines.append(
                f"| {rec['stand_id']} | {rec['frozen_rank']} | {rec['candidate_family']} | {rec['compatibility']} | "
                f"{rec['frozen_shape_v2']} | {rec['adj_shape_v2']} | {rec['frozen_score_v2']} | {rec['adj_score_v2']} |"
            )
    lines += [
        "",
        "## Phase 8 — PR #32 Top 20 diagnostic",
        "",
        "| Stand | frozen rank | family | listing family | compat | shape_v2 | adj score | diag rank (penalty, among Top20) | hard-reject |",
        "| --- | ---: | --- | --- | --- | ---: | ---: | ---: | --- |",
    ]
    for rec in top20_diag:
        lines.append(
            f"| {rec['stand_id']} | {rec['frozen_rank']} | {rec['candidate_family']} | {rec['listing_family']} | "
            f"{rec['compatibility']} | {rec['frozen_shape_v2']} | {rec['adj_score_v2']} | "
            f"{rec['diag_rank_among_top20_penalty']} | {rec['hard_reject']} |"
        )
    lines += [
        "",
        "If 540/411 stayed high **without** the family layer, that is exactly the Shape v2 failure. **With** the diagnostic penalty they fall if FREEFORM vs RECTANGULAR is incompatible. That is evidence the family layer addresses this *class* of error; it is **not** a claim that the true stand is now rank 1 (listing remains unlabelled).",
        "",
        "## Recommendation",
        "",
        "| Option | Verdict |",
        "| --- | --- |",
        "| Reject Shape Family v1 | No — it separates this error class using geometry Shape v2 ignores |",
        "| Retain diagnostic-only | **Yes (this PR)** |",
        "| Promote to candidate gating | Not yet — need more labelled cases; hard-reject would drop many compact rectangles against any curved listing photo |",
        "| Incorporate into Shape v2 | Candidate follow-up: raise `sharp_frac` / add angle-entropy; do **not** retune weights inside this forensic |",
        "",
        "Do not merge family gating into production in this task.",
        "",
    ]
    (OUT / "SHAPE_V2_FORENSIC.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_regression_md(hist: list[dict[str, Any]], listing_family: dict[str, Any]) -> None:
    lines = [
        "# SHAPE_FAMILY_REGRESSION",
        "",
        "Diagnostic A/B only. Frozen rankings were not rewritten. Production weights were not changed.",
        "",
        f"Listing 116778622-005 Shape Family v1: **{listing_family['family']}** ({listing_family['confidence']:.2f}).",
        "",
        "Method: reuse each investigation's `hybrid_block.json` listing contour and `all_candidates.json` frozen `score` / `shape_v2`. Classify OS contours with Pool Shape Family v1. Penalty rerank uses `adjusted_total_score` (shape contribution only). Hard-reject drops incompatible families then keeps frozen `score` order.",
        "",
        "Ground-truth stand numbers are **report labels only**. They are not scoring inputs.",
        "",
        "## Labelled / strong-evidence cases",
        "",
        "| Listing | GT stand | old frozen rank | diag rank (penalty) | hard-rejected? | listing family | GT family | compatibility | notes |",
        "| --- | --- | ---: | ---: | --- | --- | --- | --- | --- |",
    ]
    for h in hist:
        gt = h.get("ground_truth")
        lf = (h.get("listing_family") or {}).get("family")
        if not gt or not gt.get("stand"):
            lines.append(
                f"| {h['listing']} | — | — | — | — | {lf} | — | — | {h['label']}; unlabelled |"
            )
            continue
        if gt.get("in_candidates") is False:
            lines.append(
                f"| {h['listing']} | {gt.get('stand')} | n/a | n/a | n/a | {lf} | n/a | n/a | {h['label']}: GT absent from all_candidates |"
            )
            continue
        lines.append(
            f"| {h['listing']} | {gt['stand']} | {gt.get('old_rank')} | {gt.get('diag_rank_penalty')} | {gt.get('wrongly_hard_rejected')} | "
            f"{gt.get('listing_family')} | {gt.get('family')} | {gt.get('compatibility')} | {h['label']} |"
        )
    lines += [
        "",
        "## Per-listing notes",
        "",
    ]
    for h in hist:
        lines.append(f"### {h['listing']} — {h['label']}")
        lines.append("")
        if not h.get("has_all_candidates") or not h.get("has_hybrid"):
            lines.append(f"Missing freeze artefacts (hybrid={h.get('has_hybrid')} candidates={h.get('has_all_candidates')}); skipped.")
            lines.append("")
            continue
        lf = h.get("listing_family") or {}
        lines.append(f"- Listing family: `{lf.get('family')}` conf={lf.get('confidence')} ({lf.get('reason')})")
        lines.append(f"- Candidates: {h.get('n_candidates')}; hard-rejected: {h.get('n_hard_rejected')}")
        gt = h.get("ground_truth")
        if gt and gt.get("in_candidates"):
            lines.append(
                f"- Report-only GT {gt.get('stand')}: frozen rank **{gt.get('old_rank')}** → penalty rank **{gt.get('diag_rank_penalty')}**; "
                f"hard-rejected={gt.get('wrongly_hard_rejected')}; shape_v2={gt.get('shape_v2')}"
            )
        elif gt and gt.get("stand"):
            lines.append(f"- Report-only GT {gt.get('stand')} is **not** in all_candidates.")
        lines.append("- Penalty Top 5:")
        for r in h.get("top5_penalty") or []:
            lines.append(
                f"  - stand {r['stand_id']}: old {r['old_rank']} → diag {r['diag_rank_penalty']} "
                f"family={r['family']} compat={r['compatibility']} shape_v2={r['shape_v2']}"
            )
        lines.append("")
    lines += [
        "## Generalisation bar",
        "",
        "The family layer must not be judged by whether 116778622 'looks better' (that listing is unlabelled). The bar is: do not hard-reject known true stands; do not invent listing-specific rules.",
        "",
        "Stand 338 (`shape_v2=null`, OS REJECTED) is **out of Shape v2** already; a shape-family gate cannot be blamed for rank 122 and must not be described as fixing that case. If diagnostic A hard-rejects its REJECTED blob, report that as a gating risk.",
        "",
        "Stand 641 is missing from OS/inventory; scoring-side family logic cannot surface it.",
        "",
    ]
    (OUT / "SHAPE_FAMILY_REGRESSION.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
