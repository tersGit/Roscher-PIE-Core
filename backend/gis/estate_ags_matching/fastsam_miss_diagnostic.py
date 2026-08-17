"""FastSAM / OS v1 pool-miss diagnostic — read-only of production detectors.

Does not modify object_segmentation.py, FastSAM configuration, native15,
Scoring v2, Hybrid Pool Geometry, ranking, or inventory classification.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from backend.gis.dataset_registry import FROZEN_CARLSWALD_NORTH_001
from backend.gis.estate_ags_matching.ags_native15_raw_proof import (
    covering_tile,
    crop_parcel_from_tile,
    download_native15_tile,
    native15_tile_grid,
    parcel_bbox,
)
from backend.gis.estate_ags_matching.estate_property_inventory_v1 import safe_stand
from backend.imagery.estate_tiles import NATIVE_PIXEL_SIZE_M, PADDING_METRES
from backend.vision.object_segmentation import (
    NATIVE_M_PER_PX,
    _in_parcel,
    _parcel_frac,
    clip_region,
    contour_geometry,
    parcel_mask_from_geometry,
    select_pool,
    vegetation_fraction,
    water_fraction,
    water_seed_masks,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
GIS_001 = REPO_ROOT / "data" / "gis" / f"{FROZEN_CARLSWALD_NORTH_001}.json"
OS_DIR = REPO_ROOT / "data" / "investigations" / "object_segmentation_v1" / "carlswald_north" / "json"
OUT_DIR = (
    REPO_ROOT
    / "data"
    / "investigations"
    / "estate_property_inventory_v1"
    / "fastsam_miss"
)
REFERENCE_STAND = "677"
MISS_STANDS = ["339", "408", "1/437", "1/520", "1/631", "459", "462", "543", "675"]
ALL_STANDS = [REFERENCE_STAND, *MISS_STANDS]
# Known negatives for the recommended follow-up experiment — not processed here.
NEGATIVE_CONTROLS = ["570", "1/335", "1/379", "395", "547", "1/355"]


def _font(size: int) -> ImageFont.ImageFont:
    path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    return ImageFont.truetype(str(path), size) if path.is_file() else ImageFont.load_default()


def load_gis() -> dict[str, Any]:
    return json.loads(GIS_001.read_text(encoding="utf-8"))


def find_parcel(dataset: Mapping[str, Any], stand: str) -> dict[str, Any]:
    matches = [item for item in dataset.get("parcels") or [] if str(item.get("stand_number")) == stand]
    if not matches:
        raise KeyError(stand)
    return matches[-1]


def load_os(stand: str) -> dict[str, Any]:
    return json.loads((OS_DIR / f"{safe_stand(stand)}.json").read_text(encoding="utf-8"))


def reconstruct_native15_crop(
    stand: str,
    dataset: Mapping[str, Any],
    out_dir: Path,
) -> dict[str, Any]:
    parcel = find_parcel(dataset, stand)
    bbox = parcel_bbox(parcel["geometry"])
    tiles = native15_tile_grid(dataset["extent"])
    tile = covering_tile(tiles, *bbox)
    tile_path = out_dir / "tiles" / f"{tile['stem']}.jpg"
    download = download_native15_tile(tile, tile_path)
    tile["path"] = tile_path
    crop_path = out_dir / "crops" / f"{safe_stand(stand)}_native15.jpg"
    if not crop_parcel_from_tile(tile, parcel["geometry"], crop_path):
        raise RuntimeError(f"crop failed for {stand}")
    raw = Image.open(crop_path).convert("RGB")
    os_payload = load_os(stand)
    return {
        "stand_number": stand,
        "township": parcel.get("township"),
        "property_id": parcel.get("property_id"),
        "parcel": parcel,
        "crop_path": str(crop_path),
        "crop_wh": list(raw.size),
        "os_crop_wh": os_payload.get("crop_wh"),
        "crop_matches_os_v1_wh": list(raw.size) == list(os_payload.get("crop_wh") or []),
        "tile_id": tile["stem"],
        "tile_download": download,
        "os_payload": os_payload,
        "padding_metres": PADDING_METRES,
        "metres_per_pixel": NATIVE_PIXEL_SIZE_M,
    }


def os_pool_bbox_xyxy(os_payload: Mapping[str, Any], width: int, height: int) -> list[int] | None:
    contour = (os_payload.get("pool") or {}).get("contour") or []
    if not contour:
        return None
    xs = [float(pt[0]) * (width - 1) for pt in contour]
    ys = [float(pt[1]) * (height - 1) for pt in contour]
    return [int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))]


def water_blobs(bgr: np.ndarray, parcel: np.ndarray) -> list[dict[str, Any]]:
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    hue, sat, val = cv2.split(hsv)
    cyan = (hue >= 70) & (hue <= 145) & (sat >= 25) & (val >= 35)
    dark = (hue >= 80) & (hue <= 145) & (val < 110) & (sat >= 15)
    water = ((cyan | dark) & (parcel > 0)).astype(np.uint8)
    num, labels = cv2.connectedComponents(water)
    blobs = []
    for idx in range(1, num):
        comp = labels == idx
        area_px = int(comp.sum())
        area_m2 = area_px * (NATIVE_M_PER_PX ** 2)
        if area_px < 24 or area_m2 > 160:
            continue
        ys, xs = np.where(comp)
        geom = contour_geometry(comp)
        blobs.append(
            {
                "area_px": area_px,
                "area_m2": round(area_m2, 2),
                "bbox_xyxy": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())],
                "compactness": geom.get("compactness"),
                "rectangularity": geom.get("rectangularity"),
                "shape": geom.get("shape"),
                "mean_val": float(val[comp].mean()) if np.any(comp) else 0.0,
                "mean_sat": float(sat[comp].mean()) if np.any(comp) else 0.0,
            }
        )
    blobs.sort(key=lambda item: item["area_px"], reverse=True)
    return blobs


def localize_visual_pool(
    bgr: np.ndarray,
    parcel: np.ndarray,
    os_payload: Mapping[str, Any],
    *,
    stand: str,
) -> dict[str, Any]:
    h, w = bgr.shape[:2]
    os_box = os_pool_bbox_xyxy(os_payload, w, h)
    blobs = water_blobs(bgr, parcel)
    # Prefer a compact in-parcel water blob in the typical pool size band.
    typical = [
        blob
        for blob in blobs
        if 8.0 <= blob["area_m2"] <= 80.0 and float(blob.get("rectangularity") or 0) >= 0.45
    ]
    chosen = (typical or blobs or [None])[0]
    if stand == REFERENCE_STAND and os_box:
        box = os_box
        source = "os_v1_confirmed_contour"
    elif chosen:
        box = chosen["bbox_xyxy"]
        source = "in_parcel_water_blob"
    else:
        box = None
        source = "unlocalized"
    pad = 4
    if box is not None:
        box = [
            max(0, box[0] - pad),
            max(0, box[1] - pad),
            min(w - 1, box[2] + pad),
            min(h - 1, box[3] + pad),
        ]
    return {
        "bbox_xyxy": box,
        "source": source,
        "water_blobs": blobs[:8],
        "os_confirmed_bbox": os_box,
    }


def _roi_mask(shape: tuple[int, int], box: Sequence[int] | None) -> np.ndarray:
    mask = np.zeros(shape[:2], dtype=bool)
    if not box:
        return mask
    x0, y0, x1, y1 = [int(v) for v in box]
    mask[y0 : y1 + 1, x0 : x1 + 1] = True
    return mask


def _intersect_px(mask: np.ndarray, roi: np.ndarray) -> int:
    return int(np.logical_and(mask, roi).sum())


def local_contrast(bgr: np.ndarray, box: Sequence[int] | None) -> dict[str, float] | None:
    if not box:
        return None
    x0, y0, x1, y1 = box
    crop = bgr[y0 : y1 + 1, x0 : x1 + 1]
    if crop.size == 0:
        return None
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    return {
        "gray_std": round(float(gray.std()), 2),
        "gray_mean": round(float(gray.mean()), 2),
        "sat_mean": round(float(hsv[:, :, 1].mean()), 2),
        "val_mean": round(float(hsv[:, :, 2].mean()), 2),
        "val_std": round(float(hsv[:, :, 2].std()), 2),
    }


def proximity_stats(mask: np.ndarray, other: np.ndarray | None) -> dict[str, Any]:
    if other is None or not np.any(mask) or not np.any(other):
        return {"min_px": None, "touches": False}
    inv = np.logical_not(other)
    dist = cv2.distanceTransform(inv.astype(np.uint8) * 255, cv2.DIST_L2, 3)
    touching = bool(np.logical_and(mask, other).sum() > 0)
    min_px = 0.0 if touching else float(dist[mask].min()) if np.any(mask) else None
    return {"min_px": None if min_px is None else round(min_px, 1), "touches": touching}


def trace_proposals(
    bgr: np.ndarray,
    fastsam: list[np.ndarray],
    parcel: np.ndarray,
    visual_box: Sequence[int] | None,
    *,
    clip_available: bool,
) -> dict[str, Any]:
    roi = _roi_mask(bgr.shape, visual_box)
    height, width = bgr.shape[:2]
    seeds = water_seed_masks(bgr, parcel)
    traces = []
    for source, masks in (("fastsam", fastsam), ("water_seed", seeds)):
        for idx, mask in enumerate(masks):
            clipped = _in_parcel(mask, parcel)
            area_px = int(clipped.sum())
            area_m2 = float(area_px) * (NATIVE_M_PER_PX ** 2)
            inside = _parcel_frac(mask, parcel)
            overlap = _intersect_px(clipped, roi) if visual_box else 0
            record: dict[str, Any] = {
                "source": source,
                "index": idx,
                "raw_area_px": int(mask.sum()),
                "clipped_area_px": area_px,
                "area_m2": round(area_m2, 2),
                "parcel_frac": round(inside, 3),
                "overlap_visual_pool_px": overlap,
                "intersects_visual_pool": overlap >= 40 or (visual_box is not None and overlap >= 0.15 * max(int(roi.sum()), 1)),
                "discard_reason": None,
                "presented_to_clip": False,
                "survived_geometry": False,
                "clip": None,
                "water": None,
                "veg": None,
            }
            if area_px < 40:
                record["discard_reason"] = "clipped_area_lt_40px"
                traces.append(record)
                continue
            if area_m2 < 8.0 or area_m2 > 140.0:
                record["discard_reason"] = "area_m2_out_of_8_140"
                traces.append(record)
                continue
            if inside < 0.40:
                record["discard_reason"] = "parcel_frac_lt_0.40"
                traces.append(record)
                continue
            water = water_fraction(bgr, clipped)
            veg = vegetation_fraction(bgr, clipped)
            record["water"] = round(water, 3)
            record["veg"] = round(veg, 3)
            if water < 0.08 and veg > 0.45:
                record["discard_reason"] = "vegetation_not_water"
                traces.append(record)
                continue
            record["presented_to_clip"] = True
            geom = contour_geometry(clipped)
            record["geometry"] = {
                k: geom.get(k)
                for k in (
                    "area_m2",
                    "aspect_ratio",
                    "rectangularity",
                    "compactness",
                    "convexity",
                    "shape",
                )
            }
            if not clip_available:
                record["discard_reason"] = "clip_unavailable_in_this_environment"
                traces.append(record)
                continue
            clip = clip_region(bgr, clipped)
            record["clip"] = {k: round(float(clip[k]), 4) for k in clip}
            compact = float(geom.get("compactness") or 0)
            rectangularity = float(geom.get("rectangularity") or 0)
            water_shape = water >= 0.55 and compact >= 0.28 and rectangularity >= 0.50
            record["water_shape"] = water_shape
            if clip["shadow"] >= 0.40 and clip["pool"] < clip["shadow"]:
                record["discard_reason"] = "shadow_gate"
                traces.append(record)
                continue
            if clip["pool"] < 0.18 and not water_shape:
                record["discard_reason"] = "clip_pool_lt_0.18"
                traces.append(record)
                continue
            if clip["roof"] > clip["pool"] and water < 0.25:
                record["discard_reason"] = "roof_gate"
                traces.append(record)
                continue
            if clip["road"] > 0.35 and water < 0.30:
                record["discard_reason"] = "road_gate"
                traces.append(record)
                continue
            record["survived_geometry"] = True
            keep = clip["pool"] >= 0.40 and water >= 0.12
            record["would_keep"] = keep
            if not keep:
                record["discard_reason"] = "scored_but_not_kept"
            traces.append(record)
    final = None
    if clip_available:
        pool = select_pool(bgr, fastsam, parcel, building=None)
        final = {
            "status": pool.status,
            "score": pool.score,
            "notes": list(pool.notes),
            "clip": {k: round(float(v), 4) for k, v in (pool.clip or {}).items()},
            "geometry": {
                k: pool.geometry.get(k)
                for k in ("present", "area_m2", "area_px", "aspect_ratio", "rectangularity", "compactness", "shape")
            },
        }
    intersecting = [row for row in traces if row.get("intersects_visual_pool")]
    fastsam_at_pool = [row for row in intersecting if row["source"] == "fastsam"]
    seeds_at_pool = [row for row in intersecting if row["source"] == "water_seed"]
    if not visual_box:
        failure_stage = "visual_pool_unlocalized"
    elif not fastsam_at_pool:
        failure_stage = "fastsam_did_not_propose_pool"
    elif any(row.get("would_keep") for row in fastsam_at_pool):
        failure_stage = "fastsam_proposed_and_os_would_keep"
    elif any(row.get("survived_geometry") for row in fastsam_at_pool):
        failure_stage = "fastsam_proposed_os_rejected_after_clip_geometry"
    elif any(row.get("presented_to_clip") for row in fastsam_at_pool):
        failure_stage = "fastsam_proposed_discarded_at_clip_or_geometry_gate"
    else:
        failure_stage = "fastsam_proposed_discarded_before_clip"
    if seeds_at_pool and not fastsam_at_pool:
        failure_stage = "fastsam_did_not_propose_pool_water_seed_did"
    return {
        "n_fastsam_masks": len(fastsam),
        "n_water_seeds": len(seeds),
        "traces": traces,
        "intersecting_visual_pool": intersecting,
        "n_fastsam_at_pool": len(fastsam_at_pool),
        "n_water_seeds_at_pool": len(seeds_at_pool),
        "failure_stage": failure_stage,
        "final_select_pool": final,
        "image_wh": [width, height],
    }


def appearance_notes(bgr: np.ndarray, box: Sequence[int] | None, parcel: np.ndarray) -> dict[str, Any]:
    if not box:
        return {"contrast": None}
    x0, y0, x1, y1 = box
    contrast = local_contrast(bgr, box)
    roi = np.zeros(bgr.shape[:2], dtype=bool)
    roi[y0 : y1 + 1, x0 : x1 + 1] = True
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    sat = float(hsv[:, :, 1][roi].mean()) if np.any(roi) else 0
    val = float(hsv[:, :, 2][roi].mean()) if np.any(roi) else 0
    # Shadow heuristic: dark, low-sat neighbourhood vs pool ROI.
    pad = 12
    y0n, y1n = max(0, y0 - pad), min(bgr.shape[0], y1 + pad)
    x0n, x1n = max(0, x0 - pad), min(bgr.shape[1], x1 + pad)
    neigh = np.zeros(bgr.shape[:2], dtype=bool)
    neigh[y0n:y1n, x0n:x1n] = True
    neigh[roi] = False
    shadowish = False
    if np.any(neigh):
        shadowish = float(hsv[:, :, 2][neigh].mean()) < 70 and float(hsv[:, :, 1][neigh].mean()) < 40
    veg = vegetation_fraction(bgr, roi)
    return {
        "contrast": contrast,
        "roi_sat_mean": round(sat, 1),
        "roi_val_mean": round(val, 1),
        "neighbourhood_looks_shadowy": shadowish,
        "roi_vegetation_fraction": round(veg, 3),
        "low_local_contrast": bool(contrast and contrast["gray_std"] < 18),
    }


def pool_pixel_size(box: Sequence[int] | None) -> dict[str, Any] | None:
    if not box:
        return None
    w = max(1, box[2] - box[0] + 1)
    h = max(1, box[3] - box[1] + 1)
    return {
        "width_px": w,
        "height_px": h,
        "min_px": min(w, h),
        "max_px": max(w, h),
        "area_px": w * h,
        "width_m": round(w * NATIVE_M_PER_PX, 2),
        "height_m": round(h * NATIVE_M_PER_PX, 2),
        "vs_677_41x27": {
            "area_ratio": round((w * h) / (41 * 27), 3),
            "min_dim_ratio": round(min(w, h) / 27.0, 3),
            "max_dim_ratio": round(max(w, h) / 41.0, 3),
        },
    }


def diagnose_stand(
    stand: str,
    dataset: Mapping[str, Any],
    out_dir: Path,
    *,
    fastsam_fn=None,
    clip_available: bool = False,
) -> dict[str, Any]:
    rec = reconstruct_native15_crop(stand, dataset, out_dir)
    bgr = cv2.imread(rec["crop_path"])
    if bgr is None:
        raise RuntimeError(f"unreadable crop {rec['crop_path']}")
    h, w = bgr.shape[:2]
    parcel = parcel_mask_from_geometry((w, h), rec["parcel"]["geometry"])
    visual = localize_visual_pool(bgr, parcel, rec["os_payload"], stand=stand)
    box = visual.get("bbox_xyxy")
    fastsam_masks: list[np.ndarray] = []
    fastsam_error = None
    if fastsam_fn is not None:
        try:
            fastsam_masks = list(fastsam_fn(bgr))
        except Exception as exc:  # noqa: BLE001
            fastsam_error = f"{type(exc).__name__}: {exc}"
    trace = trace_proposals(bgr, fastsam_masks, parcel, box, clip_available=clip_available and fastsam_error is None)
    os_pool = rec["os_payload"].get("pool") or {}
    os_bldg = rec["os_payload"].get("building") or {}
    building_mask = None
    bldg_contour = os_bldg.get("contour") or []
    if bldg_contour:
        pts = np.array([[int(x * (w - 1)), int(y * (h - 1))] for x, y in bldg_contour], np.int32)
        building_mask = np.zeros((h, w), np.uint8)
        cv2.fillPoly(building_mask, [pts], 255)
        building_mask = building_mask > 0
    roi = _roi_mask(bgr.shape, box)
    parcel_edge = cv2.dilate((parcel == 0).astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    row = {
        "stand_number": stand,
        "is_reference": stand == REFERENCE_STAND,
        "township": rec["township"],
        "crop_wh": rec["crop_wh"],
        "os_crop_wh": rec["os_crop_wh"],
        "crop_matches_os_v1_wh": rec["crop_matches_os_v1_wh"],
        "crop_path": rec["crop_path"],
        "tile_id": rec["tile_id"],
        "visual_pool": visual,
        "pool_px_size": pool_pixel_size(box),
        "appearance": appearance_notes(bgr, box, parcel),
        "proximity_building": proximity_stats(roi, building_mask),
        "proximity_parcel_boundary": proximity_stats(roi, parcel_edge),
        "parcel_mask_frac_of_crop": round(float((parcel > 0).mean()), 3),
        "padding_metres": PADDING_METRES,
        "os_frozen": {
            "pool_status": os_pool.get("status"),
            "notes": os_pool.get("notes"),
            "clip_pool": (os_pool.get("clip") or {}).get("pool"),
            "building_status": os_bldg.get("status"),
            "building_area_m2": (os_bldg.get("geometry") or {}).get("area_m2"),
        },
        "fastsam_error": fastsam_error,
        "n_fastsam_masks": trace["n_fastsam_masks"],
        "n_water_seeds": trace["n_water_seeds"],
        "n_fastsam_at_pool": trace["n_fastsam_at_pool"],
        "n_water_seeds_at_pool": trace["n_water_seeds_at_pool"],
        "failure_stage": trace["failure_stage"],
        "final_select_pool": trace["final_select_pool"],
        "best_intersecting_clip": _best_clip(trace["intersecting_visual_pool"]),
        "intersecting_discard_reasons": [
            row["discard_reason"] for row in trace["intersecting_visual_pool"] if row.get("discard_reason")
        ],
        "trace": trace,
    }
    panel_path = render_stand_panel(bgr, parcel, box, fastsam_masks, trace, row, out_dir / "panels")
    row["panel_path"] = str(panel_path)
    return row


def _best_clip(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    scored = [row for row in rows if row.get("clip")]
    if not scored:
        return None
    best = max(scored, key=lambda item: float((item.get("clip") or {}).get("pool") or 0))
    return {
        "source": best.get("source"),
        "clip_pool": (best.get("clip") or {}).get("pool"),
        "discard_reason": best.get("discard_reason"),
        "presented_to_clip": best.get("presented_to_clip"),
        "survived_geometry": best.get("survived_geometry"),
    }


def _overlay_masks(rgb: np.ndarray, masks: Sequence[np.ndarray], color: tuple[int, int, int], alpha: float = 0.35) -> np.ndarray:
    out = rgb.copy()
    for mask in masks:
        if mask is None or not np.any(mask):
            continue
        tint = out.copy()
        tint[mask.astype(bool)] = color
        out = cv2.addWeighted(tint, alpha, out, 1.0 - alpha, 0)
        contours, _ = cv2.findContours(mask.astype(np.uint8) * 255, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(out, contours, -1, color, 1)
    return out


def render_stand_panel(
    bgr: np.ndarray,
    parcel: np.ndarray,
    box: Sequence[int] | None,
    fastsam: Sequence[np.ndarray],
    trace: Mapping[str, Any],
    row: Mapping[str, Any],
    out_dir: Path,
) -> Path:
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    h, w = rgb.shape[:2]
    boundary = rgb.copy()
    contours, _ = cv2.findContours(parcel, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(boundary, contours, -1, (0, 220, 255), 2)
    marked = boundary.copy()
    if box:
        cv2.rectangle(marked, (box[0], box[1]), (box[2], box[3]), (255, 40, 40), 2)
        cv2.putText(marked, "POOL", (box[0], max(14, box[1] - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 40, 40), 1, cv2.LINE_AA)
    intersecting = [fastsam[t["index"]] for t in trace.get("traces") or [] if t["source"] == "fastsam" and t.get("intersects_visual_pool") and t["index"] < len(fastsam)]
    clip_masks = [fastsam[t["index"]] for t in trace.get("traces") or [] if t["source"] == "fastsam" and t.get("presented_to_clip") and t["index"] < len(fastsam)]
    geom_masks = [fastsam[t["index"]] for t in trace.get("traces") or [] if t["source"] == "fastsam" and t.get("survived_geometry") and t["index"] < len(fastsam)]
    tiles = [
        (rgb, "1. Raw native15 crop"),
        (marked, "2. Visual pool location"),
        (_overlay_masks(marked, intersecting, (255, 220, 0)), "3. FastSAM ∩ pool loc"),
        (_overlay_masks(marked, clip_masks, (80, 200, 255)), "4. Masks presented to CLIP"),
        (_overlay_masks(marked, geom_masks, (80, 255, 120)), "5. Survived geometry"),
        (marked if not (row.get("final_select_pool") or {}).get("geometry", {}).get("present") else marked, "6. Final OS result"),
    ]
    final = row.get("final_select_pool") or {}
    if final.get("geometry", {}).get("present") or (final.get("status") in {"CONFIRMED", "PROBABLE", "REJECTED"} and final.get("clip")):
        # Draw frozen OS contour if present on the last tile.
        last = tiles[-1][0].copy()
        contour = ((row.get("os_frozen") or {}) and None)
        tiles[-1] = (last, f"6. Final OS {final.get('status')} {final.get('notes')}")
    caption_h = 28
    header_h = 72
    gap = 8
    canvas = Image.new("RGB", (w * 3 + gap * 4, header_h + (h + caption_h) * 2 + gap * 3), (16, 16, 16))
    draw = ImageDraw.Draw(canvas)
    font = _font(14)
    stand = row["stand_number"]
    size = row.get("pool_px_size") or {}
    lines = [
        f"Stand {stand}  crop={row.get('crop_wh')}  OS crop={row.get('os_crop_wh')}  match={row.get('crop_matches_os_v1_wh')}",
        f"Visual pool px≈{size.get('width_px')}x{size.get('height_px')}  FastSAM n={row.get('n_fastsam_masks')} at_pool={row.get('n_fastsam_at_pool')}  stage={row.get('failure_stage')}",
        f"Frozen OS {((row.get('os_frozen') or {}).get('pool_status'))} notes={((row.get('os_frozen') or {}).get('notes'))}  CLIP={((row.get('best_intersecting_clip') or {}) or {}).get('clip_pool')}",
    ]
    y = 6
    for line in lines:
        draw.text((10, y), line, font=font, fill=(235, 235, 235))
        y += 18
    positions = [(0, 0), (1, 0), (2, 0), (0, 1), (1, 1), (2, 1)]
    for (image, caption), (col, row_i) in zip(tiles, positions):
        im = Image.fromarray(image)
        x = gap + col * (w + gap)
        yy = header_h + row_i * (h + caption_h + gap)
        draw.text((x, yy), caption, font=font, fill=(210, 210, 210))
        canvas.paste(im, (x, yy + caption_h))
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{safe_stand(stand)}_fastsam_miss_panel.jpg"
    canvas.save(path, quality=92)
    return path


def comparison_table(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    table = []
    for row in rows:
        size = row.get("pool_px_size") or {}
        clip = row.get("best_intersecting_clip") or {}
        final = row.get("final_select_pool") or {}
        frozen = row.get("os_frozen") or {}
        table.append(
            {
                "stand": row["stand_number"],
                "pool_px_size": None if not size else f"{size.get('width_px')}x{size.get('height_px')}",
                "fastsam_pool_mask": bool(row.get("n_fastsam_at_pool")),
                "clip": clip.get("clip_pool"),
                "geometry": (clip.get("survived_geometry") if clip else None),
                "parcel_gate": "pass" if (row.get("parcel_mask_frac_of_crop") or 0) > 0 else "missing",
                "final_os_result": (final.get("status") or frozen.get("pool_status")),
                "failure_stage": row.get("failure_stage"),
                "n_fastsam": row.get("n_fastsam_masks"),
                "crop_wh": row.get("crop_wh"),
            }
        )
    return table


def hypothesis_report(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    misses = [row for row in rows if not row.get("is_reference")]
    ref = next((row for row in rows if row.get("is_reference")), None)
    def _flag(row, key):
        return bool((row.get("appearance") or {}).get(key))

    n = max(len(misses), 1)
    stages = {}
    for row in misses:
        stages[row.get("failure_stage")] = stages.get(row.get("failure_stage"), 0) + 1
    smaller = 0
    narrower = 0
    for row in misses:
        size = row.get("pool_px_size") or {}
        vs = size.get("vs_677_41x27") or {}
        if float(vs.get("area_ratio") or 1) < 0.7:
            smaller += 1
        if float(vs.get("min_dim_ratio") or 1) < 0.7:
            narrower += 1
    return {
        "n_misses": len(misses),
        "failure_stage_counts": stages,
        "fastsam_did_not_propose_n": sum(1 for row in misses if str(row.get("failure_stage") or "").startswith("fastsam_did_not_propose")),
        "fastsam_proposed_then_rejected_n": sum(
            1
            for row in misses
            if "proposed" in str(row.get("failure_stage") or "") and "did_not_propose" not in str(row.get("failure_stage") or "")
        ),
        "smaller_pixel_area_than_677": smaller,
        "narrower_min_dimension_than_677": narrower,
        "low_local_contrast_n": sum(1 for row in misses if _flag(row, "low_local_contrast")),
        "shadowy_neighbourhood_n": sum(1 for row in misses if _flag(row, "neighbourhood_looks_shadowy")),
        "touches_building_n": sum(1 for row in misses if (row.get("proximity_building") or {}).get("touches")),
        "touches_parcel_boundary_n": sum(1 for row in misses if (row.get("proximity_parcel_boundary") or {}).get("touches")),
        "reference_crop_wh": None if ref is None else ref.get("crop_wh"),
        "mean_miss_crop_area_px": round(
            float(np.mean([int(row["crop_wh"][0]) * int(row["crop_wh"][1]) for row in misses if row.get("crop_wh")])),
            1,
        )
        if misses
        else None,
        "reference_crop_area_px": None if ref is None or not ref.get("crop_wh") else int(ref["crop_wh"][0]) * int(ref["crop_wh"][1]),
        "pct_of_n": {k: round(100.0 * v / n, 1) for k, v in stages.items()},
    }


def recommended_experiment(hyp: Mapping[str, Any]) -> dict[str, Any]:
    no_prop = int(hyp.get("fastsam_did_not_propose_n") or 0)
    rejected = int(hyp.get("fastsam_proposed_then_rejected_n") or 0)
    if no_prop >= rejected:
        name = "fastsam_proposal_density_ab"
        rationale = (
            "Most documented misses have no FastSAM mask covering the visually identified pool. "
            "A narrowly controlled proposal-setting A/B (imgsz and/or retina/conf without changing CLIP, "
            "geometry gates, native15, or ranking) is the evidence-supported next experiment."
        )
        knobs = ["FastSAM imgsz 512→768 or 1024 on the same native15 crop", "leave CLIP/geometry/parcel gates frozen"]
    else:
        name = "downstream_mask_recovery_ab"
        rationale = (
            "FastSAM often proposed a mask at the pool but OS v1 discarded it at CLIP/geometry. "
            "Recover those proposals without loosening neighbour/shadow/roof gates."
        )
        knobs = ["inspect CLIP threshold 0.18 / keep 0.40 on proposed in-parcel masks only"]
    return {
        "experiment_id": name,
        "implement_now": False,
        "rationale": rationale,
        "controlled_knobs": knobs,
        "frozen_baseline": "OS v1 + FastSAM-s imgsz=512 retina_masks=True CPU + native15",
        "success_criterion": (
            "Recover materially more of the nine known false-negative pools without materially "
            "increasing false YES on known negative/shadow/neighbour cases "
            "(Stand 570 shadow/object, neighbour-pool 1/335 1/379 395 547, confirmed NO 1/355)."
        ),
        "negative_controls": NEGATIVE_CONTROLS,
        "do_not_change": [
            "frozen OS v1 code path used in production",
            "native15",
            "Scoring v2",
            "Hybrid Pool Geometry",
            "viewpoint gates",
            "production ranking",
            "Listing Pool Gate semantics",
            "PR #15/#16 frozen datasets",
        ],
    }
