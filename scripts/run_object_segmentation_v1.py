#!/usr/bin/env python3
"""Experimental object segmentation on native15 Carlswald North crops.

Does not change ranking, CLIP listing extraction, or frozen extractors.
Diagnostic set first; estate-wide only with --estate-wide after quality gate.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.gis.estate_ags_matching.aerial_geometric import extract_structural_layout
from backend.gis.estate_ags_matching.pool_geometry import extract_pool_geometry
from backend.gis.estate_ags_matching.spatial_fingerprint import (
    SEGMENTATION_VERSION,
    save_fingerprint,
)
from backend.vision.object_segmentation import (
    ObjectMask,
    ParcelObjects,
    objects_to_json,
    parcel_mask_from_geometry,
    segment_parcel_bgr,
)

DIAGNOSTIC_STANDS = [
    "677", "612", "570", "420", "585", "408", "365", "491", "447", "370",
]
DATASET = "carlswald_north_corrected_001"
GIS_PATH = Path("data/gis/carlswald_north_corrected_001.json")
CROP_DIR = Path("data/visual_index") / DATASET / "_imagery_cache_native15"
OUT_ROOT = Path("data/investigations/object_segmentation_v1/carlswald_north")


def _safe_stand(stand: str) -> str:
    return str(stand).replace("/", "_")


def _load_parcels_last_wins() -> dict[str, dict]:
    """Match crop overwrite order: later GIS parcels win for duplicate stands.

    Crop filenames replace '/' with '_', so index by the safe name.
    """
    gis = json.loads(GIS_PATH.read_text(encoding="utf-8"))
    by_safe: dict[str, dict] = {}
    for p in gis["parcels"]:
        by_safe[_safe_stand(p["stand_number"])] = p
    return by_safe


def _old_extractors(image_bytes: bytes, parcel_mask: np.ndarray) -> dict:
    pool = extract_pool_geometry(image_bytes, parcel_mask=parcel_mask)
    layout = extract_structural_layout(image_bytes)
    return {
        "old_pool_present": bool(pool.present),
        "old_pool_shape": pool.shape_class,
        "old_pool_aspect": pool.aspect_ratio,
        "old_pool_rectangularity": pool.rectangularity,
        "old_pool_compactness": pool.compactness,
        "old_pool_centroid": (
            [pool.centroid_x, pool.centroid_y] if pool.centroid_x is not None else None
        ),
        "old_pool_to_house_dist": pool.pool_to_house_dist,
        "old_roof_area_frac": layout.roof_area_frac,
        "old_roof_orientation_deg": layout.roof_orientation_deg,
        "old_paved_frac": layout.paved_frac,
    }


def _uint8_mask(mask: np.ndarray | None) -> np.ndarray | None:
    if mask is None:
        return None
    return (mask > 0).astype(np.uint8) * 255


def _draw_mask(overlay: np.ndarray, mask: np.ndarray | None, color: tuple[int, int, int], alpha: float = 0.45) -> None:
    binary = _uint8_mask(mask)
    if binary is None or not np.any(binary):
        return
    tint = overlay.copy()
    tint[binary > 0] = color
    cv2.addWeighted(tint, alpha, overlay, 1.0 - alpha, 0, overlay)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(overlay, contours, -1, color, 2)


def _centroid_px(obj: ObjectMask | None) -> tuple[float, float] | None:
    if obj is None or not obj.geometry.get("present"):
        return None
    xy = obj.geometry.get("centroid_xy_px")
    if xy:
        return float(xy[0]), float(xy[1])
    return None


def _save_mask_png(path: Path, mask: np.ndarray | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    binary = _uint8_mask(mask)
    if binary is None:
        binary = np.zeros((8, 8), np.uint8)
    cv2.imwrite(str(path), binary)


def _draw_panel(
    crop_bgr: np.ndarray,
    parcel_mask: np.ndarray,
    objects: ParcelObjects,
    old: dict,
    stand: str,
) -> np.ndarray:
    h, w = crop_bgr.shape[:2]
    orig = crop_bgr.copy()
    parcel_vis = crop_bgr.copy()
    contours, _ = cv2.findContours(parcel_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(parcel_vis, contours, -1, (0, 255, 255), 2)

    pool_vis = crop_bgr.copy()
    pool_status = objects.pool.status if objects.pool else "UNKNOWN"
    if pool_status in {"CONFIRMED", "PROBABLE"}:
        _draw_mask(pool_vis, objects.pool.mask, (255, 180, 40))
    elif pool_status == "REJECTED":
        _draw_mask(pool_vis, objects.pool.mask, (40, 40, 200), 0.25)

    bld_vis = crop_bgr.copy()
    _draw_mask(bld_vis, objects.building.mask if objects.building else None, (40, 80, 255))
    drv_vis = crop_bgr.copy()
    _draw_mask(drv_vis, objects.driveway.mask if objects.driveway else None, (200, 200, 200))

    combo = crop_bgr.copy()
    _draw_mask(combo, objects.driveway.mask if objects.driveway else None, (180, 180, 180), 0.35)
    _draw_mask(combo, objects.building.mask if objects.building else None, (40, 80, 255), 0.40)
    if pool_status in {"CONFIRMED", "PROBABLE"}:
        _draw_mask(combo, objects.pool.mask, (255, 180, 40), 0.50)
    cv2.drawContours(combo, contours, -1, (0, 255, 255), 1)

    def _dot(img, xy, color, label):
        if not xy:
            return
        pt = (int(xy[0]), int(xy[1]))
        cv2.circle(img, pt, 6, color, -1)
        cv2.circle(img, pt, 7, (0, 0, 0), 1)
        cv2.putText(img, label, (pt[0] + 8, pt[1] - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)

    pool_xy = _centroid_px(objects.pool) if pool_status in {"CONFIRMED", "PROBABLE"} else None
    house_xy = _centroid_px(objects.building)
    drv_xy = _centroid_px(objects.driveway) if objects.driveway and objects.driveway.status in {"CONFIRMED", "PROBABLE"} else None
    _dot(combo, pool_xy, (255, 180, 40), "P")
    _dot(combo, house_xy, (40, 80, 255), "H")
    _dot(combo, drv_xy, (220, 220, 220), "D")
    if pool_xy and house_xy:
        cv2.line(
            combo,
            (int(house_xy[0]), int(house_xy[1])),
            (int(pool_xy[0]), int(pool_xy[1])),
            (0, 255, 0),
            2,
        )
    entry = None if objects.driveway is None else objects.driveway.geometry.get("entry")
    if entry and house_xy:
        ex = int(entry["x"] * (w - 1))
        ey = int(entry["y"] * (h - 1))
        cv2.line(combo, (ex, ey), (int(house_xy[0]), int(house_xy[1])), (255, 255, 255), 1)
        _dot(combo, (ex, ey), (255, 255, 255), "E")

    tiles = [orig, parcel_vis, pool_vis, bld_vis, drv_vis, combo]
    n_masses = (objects.spatial or {}).get("n_building_masses", 0)
    labels = [
        f"{stand} native15 original",
        "parcel boundary",
        f"pool {pool_status}",
        f"building masses={n_masses}",
        f"driveway {objects.driveway.status if objects.driveway else 'UNKNOWN'}",
        "centroids + pool-house vector",
    ]
    row = np.concatenate(tiles, axis=1)
    bar = np.zeros((36, row.shape[1], 3), dtype=np.uint8)
    tw = w
    for i, lab in enumerate(labels):
        cv2.putText(bar, lab, (i * tw + 8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (230, 230, 230), 1, cv2.LINE_AA)
    footer = np.zeros((28, row.shape[1], 3), dtype=np.uint8)
    rel = (objects.spatial or {}).get("relationships") or {}
    ph = rel.get("pool_house") or {}
    drv_side = ((objects.spatial or {}).get("driveway") or {}).get("driveway_side")
    pool_area = None if objects.pool is None else objects.pool.geometry.get("area_m2")
    foot = (
        f"{SEGMENTATION_VERSION}  old_pool={old.get('old_pool_present')}  "
        f"new_pool={pool_status} area={pool_area}  "
        f"pool->house {ph.get('direction')} {ph.get('distance_m')}m  "
        f"driveway={drv_side}"
    )
    cv2.putText(footer, foot, (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (200, 200, 200), 1, cv2.LINE_AA)
    return np.concatenate([bar, row, footer], axis=0)


def _process_one(stand: str, parcel: dict, crop_path: Path, out_dir: Path, write_panel: bool) -> dict:
    crop = cv2.imread(str(crop_path))
    if crop is None:
        raise FileNotFoundError(crop_path)
    geom = parcel["geometry"]
    h, w = crop.shape[:2]
    t0 = time.perf_counter()
    objects = segment_parcel_bgr(
        crop, stand_number=str(parcel.get("stand_number") or stand), geometry=geom
    )
    elapsed = time.perf_counter() - t0
    pmask = parcel_mask_from_geometry((w, h), geom)
    old = _old_extractors(crop_path.read_bytes(), pmask)
    payload = objects_to_json(objects)
    payload["township"] = parcel.get("township")
    payload["elapsed_s"] = round(elapsed, 3)
    payload["old_extractor"] = old
    payload["crop_path"] = str(crop_path)
    payload["crop_wh"] = [int(w), int(h)]
    save_fingerprint(out_dir / "json" / f"{stand}.json", payload)
    _save_mask_png(out_dir / "masks" / f"{stand}_pool.png", objects.pool.mask if objects.pool else None)
    _save_mask_png(out_dir / "masks" / f"{stand}_building.png", objects.building.mask if objects.building else None)
    _save_mask_png(out_dir / "masks" / f"{stand}_driveway.png", objects.driveway.mask if objects.driveway else None)
    if write_panel:
        panel = _draw_panel(crop, pmask, objects, old, stand)
        panel_path = out_dir / "panels" / f"{stand}_segmentation_panel.jpg"
        panel_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(panel_path), panel, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--estate-wide", action="store_true")
    args = parser.parse_args()

    if not GIS_PATH.is_file():
        print(f"missing GIS {GIS_PATH}", file=sys.stderr)
        return 1
    if not CROP_DIR.is_dir():
        print(f"missing native15 crops {CROP_DIR}", file=sys.stderr)
        return 1

    parcels = _load_parcels_last_wins()
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    (OUT_ROOT / "json").mkdir(parents=True, exist_ok=True)
    (OUT_ROOT / "masks").mkdir(parents=True, exist_ok=True)
    (OUT_ROOT / "panels").mkdir(parents=True, exist_ok=True)

    stands = DIAGNOSTIC_STANDS
    write_panel = True
    if args.estate_wide:
        stands = sorted(
            {p.name.replace("_ags_aerial.jpg", "") for p in CROP_DIR.glob("*_ags_aerial.jpg")}
        )
        write_panel = False

    print(f"{SEGMENTATION_VERSION} n={len(stands)} crops={CROP_DIR} panels={write_panel}", flush=True)
    rows = []
    t_all = time.perf_counter()
    for i, stand in enumerate(stands, 1):
        parcel = parcels.get(stand)
        crop_path = CROP_DIR / f"{stand}_ags_aerial.jpg"
        if parcel is None or not crop_path.is_file():
            print(f"  skip {stand} missing parcel or crop", flush=True)
            continue
        print(f"  [{i}/{len(stands)}] {stand} …", flush=True)
        payload = _process_one(stand, parcel, crop_path, OUT_ROOT, write_panel=write_panel)
        rows.append(payload)
        pool = payload.get("pool") or {}
        drv = payload.get("driveway") or {}
        print(
            f"      pool={pool.get('status')} "
            f"area={ (pool.get('geometry') or {}).get('area_m2') } "
            f"bldg={ (payload.get('spatial') or {}).get('n_building_masses') } "
            f"drv={drv.get('status')} "
            f"{payload['elapsed_s']}s",
            flush=True,
        )
    total = time.perf_counter() - t_all
    summary = {
        "version": SEGMENTATION_VERSION,
        "n": len(rows),
        "estate_wide": bool(args.estate_wide),
        "ags_downloads": 0,
        "total_s": round(total, 2),
        "mean_s": round(total / max(len(rows), 1), 3),
        "stands": [
            {
                "stand": r["stand_number"],
                "pool_status": (r.get("pool") or {}).get("status"),
                "pool_area_m2": ((r.get("pool") or {}).get("geometry") or {}).get("area_m2"),
                "pool_shape": ((r.get("pool") or {}).get("geometry") or {}).get("shape"),
                "old_pool_present": r["old_extractor"]["old_pool_present"],
                "building_status": (r.get("building") or {}).get("status"),
                "building_n_masses": (r.get("spatial") or {}).get("n_building_masses"),
                "building_area_m2": ((r.get("building") or {}).get("geometry") or {}).get("area_m2"),
                "driveway_status": (r.get("driveway") or {}).get("status"),
                "driveway_side": ((r.get("spatial") or {}).get("driveway") or {}).get("driveway_side"),
                "pool_to_house": ((r.get("spatial") or {}).get("relationships") or {}).get("pool_house"),
                "elapsed_s": r["elapsed_s"],
            }
            for r in rows
        ],
    }
    name = "estate_summary.json" if args.estate_wide else "diagnostic_summary.json"
    save_fingerprint(OUT_ROOT / name, summary)
    print(json.dumps({k: summary[k] for k in ("n", "total_s", "mean_s", "ags_downloads")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
