"""Experimental object segmentation for nadir AGS parcel crops.

Architecture (CPU, no SAM2):
    FastSAM-s region proposals
        → CLIP + geometry validation
        → object masks (pool, building, driveway)
        → parcel-relative spatial fingerprint

Does not change ranking, CLIP scene labels used for listing photos, or
the legacy colour-blob pool extractor. Results are stored separately so
the experiment can be rolled back.

Pool colour is supporting evidence only. Roof/shadow/road/neighbour
rejection is mandatory.
"""

from __future__ import annotations

import io
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image

SEGMENTATION_VERSION = "object_segmentation_v1"
NATIVE_M_PER_PX = 0.15
FASTSAM_WEIGHTS = Path(__file__).resolve().parents[2] / "data/cache/models/FastSAM-s.pt"
FASTSAM_URL = "https://github.com/ultralytics/assets/releases/download/v8.3.0/FastSAM-s.pt"

CLIP_PROMPTS = [
    "overhead aerial photo of a backyard swimming pool",
    "overhead aerial photo of a house roof",
    "overhead aerial photo of tree shadow on lawn",
    "overhead aerial photo of asphalt road",
    "overhead aerial photo of paved driveway",
    "overhead aerial photo of green lawn and garden",
]
CLIP_KEYS = ["pool", "roof", "shadow", "road", "driveway", "lawn"]


@dataclass
class ObjectMask:
    kind: str
    mask: np.ndarray
    status: str = "UNKNOWN"
    score: float = 0.0
    clip: dict[str, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    geometry: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParcelObjects:
    stand_number: str
    version: str = SEGMENTATION_VERSION
    pool: ObjectMask | None = None
    building: ObjectMask | None = None
    outbuildings: list[ObjectMask] = field(default_factory=list)
    driveway: ObjectMask | None = None
    spatial: dict[str, Any] = field(default_factory=dict)
    runtime_s: float = 0.0


_fastsam = None
_clip_text = None


def _load_fastsam():
    global _fastsam
    if _fastsam is not None:
        return _fastsam
    FASTSAM_WEIGHTS.parent.mkdir(parents=True, exist_ok=True)
    from ultralytics import FastSAM

    _fastsam = FastSAM(str(FASTSAM_WEIGHTS if FASTSAM_WEIGHTS.is_file() else "FastSAM-s.pt"))
    return _fastsam


def _clip_text_features():
    global _clip_text
    if _clip_text is not None:
        return _clip_text
    from backend.vision.clip_encoder import load_clip

    model, preprocess, tokenizer, torch = load_clip()
    with torch.no_grad():
        text = tokenizer(CLIP_PROMPTS)
        feat = model.encode_text(text)
        feat = feat / feat.norm(dim=-1, keepdim=True)
    _clip_text = (model, preprocess, tokenizer, torch, feat)
    return _clip_text


def clip_region(bgr: np.ndarray, mask: np.ndarray) -> dict[str, float]:
    model, preprocess, _, torch, text_f = _clip_text_features()
    ys, xs = np.where(mask)
    if len(xs) < 12:
        return {key: 0.0 for key in CLIP_KEYS}
    pad = 10
    x0, x1 = max(0, int(xs.min()) - pad), min(bgr.shape[1], int(xs.max()) + pad)
    y0, y1 = max(0, int(ys.min()) - pad), min(bgr.shape[0], int(ys.max()) + pad)
    crop = bgr[y0:y1, x0:x1, ::-1]
    if crop.size == 0:
        return {key: 0.0 for key in CLIP_KEYS}
    tensor = preprocess(Image.fromarray(crop)).unsqueeze(0)
    with torch.no_grad():
        feat = model.encode_image(tensor)
        feat = feat / feat.norm(dim=-1, keepdim=True)
        scores = (100.0 * feat @ text_f.T).softmax(dim=-1)[0].cpu().numpy()
    return {key: float(val) for key, val in zip(CLIP_KEYS, scores)}


def parcel_mask_from_geometry(image_size: tuple[int, int], geometry: dict, pad_metres: float = 18.0) -> np.ndarray:
    """Map GIS rings onto a padded parcel crop. image_size is (width, height)."""
    width, height = image_size
    xs, ys = [], []
    rings = geometry.get("rings") or []
    for ring in rings:
        for x, y in ring:
            xs.append(float(x))
            ys.append(float(y))
    if not xs:
        return np.full((height, width), 255, np.uint8)
    pad = pad_metres / 111_320
    bbox = (min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad)
    # Crops are padded on the full bbox, then the outer ring is filled — same as
    # scripts/run_carlswald_north_corrected.parcel_mask.
    outer = rings[0] if rings else []
    pts = []
    for lon, lat in outer:
        x = (float(lon) - bbox[0]) / max(bbox[2] - bbox[0], 1e-12) * width
        y = (bbox[3] - float(lat)) / max(bbox[3] - bbox[1], 1e-12) * height
        pts.append((int(x), int(y)))
    mask = np.zeros((height, width), np.uint8)
    if len(pts) >= 3:
        cv2.fillPoly(mask, [np.array(pts, np.int32)], 255)
    else:
        mask[:] = 255
    return mask


def _resize_mask(mask: np.ndarray, width: int, height: int) -> np.ndarray:
    if mask.shape[:2] == (height, width):
        return mask.astype(bool)
    return cv2.resize(mask.astype(np.uint8), (width, height), interpolation=cv2.INTER_NEAREST).astype(bool)


def fastsam_masks(bgr: np.ndarray) -> list[np.ndarray]:
    height, width = bgr.shape[:2]
    result = _load_fastsam().predict(
        bgr,
        device="cpu",
        imgsz=512,
        retina_masks=True,
        verbose=False,
        save=False,
    )[0]
    if result.masks is None:
        return []
    raw = result.masks.data.cpu().numpy()
    return [_resize_mask(item, width, height) for item in raw]


def water_fraction(bgr: np.ndarray, mask: np.ndarray) -> float:
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    hue, sat, val = cv2.split(hsv)
    m = mask.astype(bool)
    if not np.any(m):
        return 0.0
    cyan = (hue >= 70) & (hue <= 145) & (sat >= 25) & (val >= 35)
    dark_water = (hue >= 80) & (hue <= 145) & (val < 95) & (sat >= 15)
    return float((cyan | dark_water)[m].mean())


def vegetation_fraction(bgr: np.ndarray, mask: np.ndarray) -> float:
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    hue, sat, val = cv2.split(hsv)
    m = mask.astype(bool)
    if not np.any(m):
        return 0.0
    veg = (hue >= 35) & (hue <= 85) & (sat >= 40) & (val >= 40)
    return float(veg[m].mean())


def paved_fraction(bgr: np.ndarray, mask: np.ndarray) -> float:
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    hue, sat, val = cv2.split(hsv)
    m = mask.astype(bool)
    if not np.any(m):
        return 0.0
    paved = (sat <= 55) & (val >= 50) & (val <= 200) & ((hue <= 40) | (hue >= 160))
    return float(paved[m].mean())


def _curvature_signature(contour: np.ndarray, n: int = 16) -> list[float]:
    pts = contour.reshape(-1, 2).astype(np.float64)
    if len(pts) < 3:
        return []
    closed = np.vstack([pts, pts[0]])
    seglen = np.hypot(np.diff(closed[:, 0]), np.diff(closed[:, 1]))
    cum = np.concatenate([[0.0], np.cumsum(seglen)])
    total = float(cum[-1])
    if total < 1.0:
        return []
    samples = np.zeros((n, 2), dtype=np.float64)
    for i in range(n):
        t = (i / n) * total
        j = int(np.searchsorted(cum, t) - 1)
        j = min(max(j, 0), len(pts) - 1)
        samples[i] = pts[j]
    prev = np.roll(samples, 1, axis=0)
    nxt = np.roll(samples, -1, axis=0)
    v1 = samples - prev
    v2 = nxt - samples
    ang1 = np.arctan2(v1[:, 1], v1[:, 0])
    ang2 = np.arctan2(v2[:, 1], v2[:, 0])
    turn = (ang2 - ang1 + np.pi) % (2.0 * np.pi) - np.pi
    return [round(float(a), 3) for a in turn]


def contour_geometry(mask: np.ndarray) -> dict[str, Any]:
    binary = (mask > 0).astype(np.uint8) * 255
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return {"present": False}
    contour = max(contours, key=cv2.contourArea)
    area = float(cv2.contourArea(contour))
    peri = float(cv2.arcLength(contour, True))
    compactness = float(4.0 * math.pi * area / max(peri * peri, 1e-6))
    (_cx, _cy), (rw, rh), angle = cv2.minAreaRect(contour)
    rectangularity = float(area / max(rw * rh, 1e-6))
    hull = cv2.convexHull(contour)
    convexity = float(area / max(cv2.contourArea(hull), 1e-6))
    aspect = float(max(rw, rh) / max(min(rw, rh), 1e-3))
    moments = cv2.moments(contour)
    height, width = mask.shape[:2]
    if moments["m00"] <= 1e-6:
        return {"present": False}
    cx_px = float(moments["m10"] / moments["m00"])
    cy_px = float(moments["m01"] / moments["m00"])
    cx = cx_px / max(width - 1, 1)
    cy = cy_px / max(height - 1, 1)
    pts = contour.reshape(-1, 2)
    image_contour = [
        [round(float(x) / max(width - 1, 1), 4), round(float(y) / max(height - 1, 1), 4)]
        for x, y in pts[:: max(1, len(pts) // 64)]
    ]
    if rectangularity >= 0.78 and compactness >= 0.55 and aspect < 2.3:
        shape = "rectangular"
    elif aspect >= 2.2 and rectangularity >= 0.68:
        shape = "elongated_rectangular"
    elif convexity < 0.86 or compactness < 0.42:
        shape = "irregular"
    elif compactness >= 0.7 and rectangularity < 0.72:
        shape = "rounded"
    else:
        shape = "kidney_or_curved"
    curvature = _curvature_signature(contour)
    return {
        "present": True,
        "area_px": area,
        "area_m2": round(area * (NATIVE_M_PER_PX ** 2), 2),
        "relative_area": float(area / max(width * height, 1)),
        "centroid_x": round(cx, 4),
        "centroid_y": round(cy, 4),
        "centroid_xy_px": [round(cx_px, 1), round(cy_px, 1)],
        "orientation_deg": round(float(angle) % 180.0, 2),
        "aspect_ratio": round(aspect, 3),
        "rectangularity": round(rectangularity, 4),
        "convexity": round(convexity, 4),
        "compactness": round(compactness, 4),
        "shape": shape,
        "curvature_signature": curvature,
        "contour_image": image_contour,
    }


def _overlap(a: np.ndarray, b: np.ndarray) -> float:
    inter = np.logical_and(a, b).sum()
    return float(inter / max(a.sum(), 1))


def _merge_bool(masks: list[np.ndarray]) -> np.ndarray:
    out = np.zeros_like(masks[0], dtype=bool)
    for item in masks:
        out |= item
    return out


def _components(mask: np.ndarray, min_area: int) -> list[np.ndarray]:
    num, labels = cv2.connectedComponents(mask.astype(np.uint8))
    out = []
    for idx in range(1, num):
        comp = labels == idx
        if int(comp.sum()) >= min_area:
            out.append(comp)
    return out


def _parcel_frac(mask: np.ndarray, parcel: np.ndarray) -> float:
    return float(np.logical_and(mask, parcel > 0).sum() / max(mask.sum(), 1))


def select_pool(
    bgr: np.ndarray,
    masks: list[np.ndarray],
    parcel: np.ndarray,
    building: np.ndarray | None,
) -> ObjectMask:
    height, width = bgr.shape[:2]
    parcel_bool = parcel > 0
    scored: list[tuple[float, np.ndarray, dict, dict]] = []
    for mask in masks:
        area = float(mask.mean())
        if area < 0.0012 or area > 0.14:
            continue
        inside = _parcel_frac(mask, parcel)
        if inside < 0.55:
            continue
        if building is not None and _overlap(mask, building) > 0.35:
            continue
        water = water_fraction(bgr, mask)
        veg = vegetation_fraction(bgr, mask)
        if water < 0.10 and veg > 0.45:
            continue
        clip = clip_region(bgr, mask)
        rival = max(clip["roof"], clip["shadow"], clip["road"], clip["driveway"], clip["lawn"])
        gap = clip["pool"] - rival
        if clip["pool"] < 0.20:
            continue
        score = 0.55 * clip["pool"] + 0.25 * gap + 0.15 * water + 0.05 * inside
        scored.append((score, mask, clip, {"water": water, "veg": veg, "inside": inside, "gap": gap}))
    empty = ObjectMask(kind="pool", mask=np.zeros((height, width), bool), status="UNKNOWN", notes=["no_pool_candidate"])
    if not scored:
        return empty
    scored.sort(key=lambda item: item[0], reverse=True)
    keep = [item for item in scored if item[2]["pool"] >= 0.55 and item[3]["gap"] >= 0.15]
    if not keep:
        best = scored[0]
        clip = best[2]
        status = "REJECTED"
        notes = ["low_pool_evidence"]
        if clip["road"] > 0.2 or clip["shadow"] > 0.35 or clip["roof"] > 0.4:
            notes = ["rejected_as_road_shadow_or_roof"]
        geom = contour_geometry(best[1])
        return ObjectMask(kind="pool", mask=best[1], status=status, score=best[0], clip=clip, notes=notes, geometry=geom)
    merged = _merge_bool([item[1] for item in keep[:4]])
    # keep only the component mostly inside the parcel
    best_comp = None
    best_inside = -1.0
    for comp in _components(merged, min_area=40):
        inside = _parcel_frac(comp, parcel)
        if inside > best_inside:
            best_inside = inside
            best_comp = comp
    mask = best_comp if best_comp is not None else merged
    clip = clip_region(bgr, mask)
    water = water_fraction(bgr, mask)
    geom = contour_geometry(mask)
    notes = ["fastsam+clip"]
    if best_inside < 0.7:
        notes.append("partially_outside_parcel")
    if building is not None and _overlap(mask, building) > 0.2:
        notes.append("touches_building")
    status = "PROBABLE"
    if clip["pool"] >= 0.75 and water >= 0.18 and best_inside >= 0.65:
        status = "CONFIRMED"
    elif clip["pool"] < 0.45:
        status = "UNKNOWN"
    area_m2 = geom.get("area_m2") or 0
    if area_m2 < 8 or area_m2 > 220:
        notes.append(f"unusual_area_m2={area_m2:.1f}")
        if status == "CONFIRMED":
            status = "PROBABLE"
    return ObjectMask(kind="pool", mask=mask, status=status, score=float(clip["pool"]), clip=clip, notes=notes, geometry=geom)


def select_buildings(
    bgr: np.ndarray,
    masks: list[np.ndarray],
    parcel: np.ndarray,
    pool: np.ndarray | None,
) -> tuple[ObjectMask, list[ObjectMask]]:
    height, width = bgr.shape[:2]
    prelim = []
    for mask in masks:
        area = float(mask.mean())
        if area < 0.01 or area > 0.45:
            continue
        if _parcel_frac(mask, parcel) < 0.55:
            continue
        if pool is not None and _overlap(mask, pool) > 0.4:
            continue
        veg = vegetation_fraction(bgr, mask)
        if veg > 0.5:
            continue
        prelim.append((area, 1.0 - veg, mask))
    prelim.sort(key=lambda item: item[0], reverse=True)
    roof_masks = []
    for area, inv_veg, mask in prelim[:12]:
        clip = clip_region(bgr, mask)
        if clip["roof"] < 0.25 and clip["pool"] > clip["roof"]:
            continue
        if clip["lawn"] > 0.5:
            continue
        roof_masks.append((clip["roof"] + 0.3 * inv_veg + 0.2 * area, mask, clip))
    empty = ObjectMask(kind="building", mask=np.zeros((height, width), bool), status="UNKNOWN", notes=["no_building"])
    if not roof_masks:
        return empty, []
    roof_masks.sort(key=lambda item: item[0], reverse=True)
    merged = _merge_bool([item[1] for item in roof_masks[:12]])
    merged = np.logical_and(merged, parcel > 0)
    comps = sorted(_components(merged, min_area=80), key=lambda m: m.sum(), reverse=True)
    if not comps:
        return empty, []
    main = comps[0]
    # absorb touching smaller masses into main
    kernel = np.ones((9, 9), np.uint8)
    main_d = cv2.dilate(main.astype(np.uint8), kernel, 1).astype(bool)
    outbuildings = []
    for comp in comps[1:]:
        if np.logical_and(comp, main_d).any():
            main = np.logical_or(main, comp)
            main_d = cv2.dilate(main.astype(np.uint8), kernel, 1).astype(bool)
        else:
            geom = contour_geometry(comp)
            outbuildings.append(
                ObjectMask(
                    kind="outbuilding",
                    mask=comp,
                    status="PROBABLE",
                    geometry=geom,
                    notes=["detached_mass"],
                )
            )
    geom = contour_geometry(main)
    clip = clip_region(bgr, main)
    status = "CONFIRMED" if geom.get("present") and geom.get("relative_area", 0) >= 0.03 else "PROBABLE"
    building = ObjectMask(kind="building", mask=main, status=status, score=clip.get("roof", 0), clip=clip, geometry=geom, notes=["fastsam+clip"])
    return building, outbuildings


def select_driveway(
    bgr: np.ndarray,
    masks: list[np.ndarray],
    parcel: np.ndarray,
    building: np.ndarray | None,
    pool: np.ndarray | None,
) -> ObjectMask:
    height, width = bgr.shape[:2]
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    hue, sat, val = cv2.split(hsv)
    paved = ((sat <= 60) & (val >= 55) & (val <= 210) & ((hue <= 45) | (hue >= 155))).astype(np.uint8)
    veg = ((hue >= 35) & (hue <= 85) & (sat >= 40)).astype(np.uint8)
    paved[veg > 0] = 0
    if building is not None:
        paved[building] = 0
    if pool is not None:
        paved[pool] = 0
    paved[parcel == 0] = 0
    paved = cv2.morphologyEx(paved, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    paved = cv2.morphologyEx(paved, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    sam_drive = []
    for mask in masks:
        if _parcel_frac(mask, parcel) < 0.5:
            continue
        area = float(mask.mean())
        if area < 0.004 or area > 0.28:
            continue
        if paved_fraction(bgr, mask) < 0.22:
            continue
        sam_drive.append((area, mask))
    sam_drive.sort(key=lambda item: item[0], reverse=True)
    for _, mask in sam_drive[:6]:
        clip = clip_region(bgr, mask)
        if clip["driveway"] >= 0.35 and clip["driveway"] >= clip["roof"]:
            paved[np.logical_and(mask, parcel > 0)] = 255
    if building is not None:
        paved[building] = 0
    if pool is not None:
        paved[pool] = 0
    boundary = cv2.dilate(parcel, np.ones((7, 7), np.uint8)) - parcel
    comps = _components(paved > 0, min_area=80)
    usable = []
    for comp in comps:
        if np.logical_and(comp, boundary > 0).sum() >= 8:
            usable.append(comp)
        elif building is not None and _overlap(cv2.dilate(comp.astype(np.uint8), np.ones((11, 11), np.uint8)).astype(bool), building) > 0.02:
            usable.append(comp)
    empty = ObjectMask(kind="driveway", mask=np.zeros((height, width), bool), status="UNKNOWN", notes=["no_access"])
    if not usable:
        return empty
    mask = _merge_bool(usable)
    geom = contour_geometry(mask)
    ys, xs = np.where(np.logical_and(mask, boundary > 0))
    entry = None
    if len(xs):
        entry = {
            "x": round(float(xs.mean()) / max(width - 1, 1), 4),
            "y": round(float(ys.mean()) / max(height - 1, 1), 4),
        }
    geom["entry"] = entry
    entry_clusters = _components(np.logical_and(mask, boundary > 0), min_area=4)
    geom["n_entry_clusters"] = len(entry_clusters)
    geom["n_paved_components"] = len(usable)
    geom["branching_evidence"] = bool(len(usable) >= 2 or len(entry_clusters) >= 2)
    hole_cnts, hole_hier = cv2.findContours(
        mask.astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE
    )
    geom["circular_evidence"] = bool(
        hole_hier is not None and len(hole_hier) and any(int(h[3]) >= 0 for h in hole_hier[0])
    )
    status = "PROBABLE" if entry else "UNKNOWN"
    if entry and geom.get("relative_area", 0) >= 0.02:
        status = "CONFIRMED"
    return ObjectMask(kind="driveway", mask=mask, status=status, geometry=geom, notes=["paved+boundary+fastsam"])


def _xy_parcel(px: float, py: float, parcel: np.ndarray) -> tuple[float, float] | None:
    ys, xs = np.where(parcel > 0)
    if len(xs) < 4:
        return None
    x0, x1 = float(xs.min()), float(xs.max())
    y0, y1 = float(ys.min()), float(ys.max())
    height, width = parcel.shape
    x = px * (width - 1)
    y = py * (height - 1)
    return round((x - x0) / max(x1 - x0, 1e-6), 4), round((y - y0) / max(y1 - y0, 1e-6), 4)


def _compass(dx: float, dy: float) -> str:
    """Image coordinates: +x east, +y south."""
    angle = math.degrees(math.atan2(dy, dx))
    names = ["E", "SE", "S", "SW", "W", "NW", "N", "NE"]
    idx = int(((angle + 22.5) % 360.0) // 45.0)
    return names[idx]


def _cardinal_side(dx: float, dy: float) -> str:
    if abs(dx) >= abs(dy):
        return "east" if dx >= 0 else "west"
    return "south" if dy >= 0 else "north"


def spatial_fingerprint(objects: ParcelObjects, parcel: np.ndarray) -> dict[str, Any]:
    def node(obj: ObjectMask | None, extra: dict | None = None) -> dict:
        if obj is None or not obj.geometry.get("present"):
            return {"present": False, "status": None if obj is None else obj.status}
        cx, cy = obj.geometry.get("centroid_x"), obj.geometry.get("centroid_y")
        rel = _xy_parcel(cx, cy, parcel) if cx is not None else None
        payload = {
            "present": True,
            "status": obj.status,
            "centroid_image": [cx, cy],
            "centroid_xy_px": obj.geometry.get("centroid_xy_px"),
            "centroid_parcel": list(rel) if rel else None,
            "orientation_deg": obj.geometry.get("orientation_deg"),
            "footprint_m2": obj.geometry.get("area_m2"),
            "shape": obj.geometry.get("shape"),
            "contour": obj.geometry.get("contour_image"),
        }
        if extra:
            payload.update(extra)
        return payload

    house = node(objects.building)
    if objects.pool is not None and objects.pool.status not in {"CONFIRMED", "PROBABLE"}:
        pool = {"present": False, "status": objects.pool.status}
    else:
        pool = node(objects.pool)
    if objects.driveway is not None and objects.driveway.status in {"CONFIRMED", "PROBABLE"}:
        drive = node(
            objects.driveway,
            extra={
                "entry": objects.driveway.geometry.get("entry"),
                "branching_evidence": objects.driveway.geometry.get("branching_evidence"),
                "circular_evidence": objects.driveway.geometry.get("circular_evidence"),
            },
        )
    else:
        drive = {
            "present": False,
            "status": None if objects.driveway is None else objects.driveway.status,
            "entry": None if objects.driveway is None else objects.driveway.geometry.get("entry"),
        }
    outs = [node(item) for item in objects.outbuildings]

    def vec(a, b):
        if not a.get("present") or not b.get("present"):
            return None
        pa, pb = a.get("centroid_parcel"), b.get("centroid_parcel")
        if not pa or not pb:
            return None
        dx, dy = pb[0] - pa[0], pb[1] - pa[1]
        dist_m = None
        ca, cb = a.get("centroid_xy_px"), b.get("centroid_xy_px")
        if ca and cb:
            dist_m = round(math.hypot(cb[0] - ca[0], cb[1] - ca[1]) * NATIVE_M_PER_PX, 2)
        return {
            "dx": round(dx, 4),
            "dy": round(dy, 4),
            "dist": round(float(math.hypot(dx, dy)), 4),
            "distance_m": dist_m,
            "angle_deg": round(float(math.degrees(math.atan2(dy, dx))), 2),
            "direction": _compass(dx, dy),
        }

    house_parcel = house.get("centroid_parcel")
    pool_parcel = pool.get("centroid_parcel")
    drive_entry = drive.get("entry")
    driveway_house = None
    if drive.get("present") and house.get("present"):
        hx, hy = house["centroid_image"]
        entry_vec = None
        if drive_entry:
            entry_vec = {
                "dx": round(hx - drive_entry["x"], 4),
                "dy": round(hy - drive_entry["y"], 4),
            }
        side = "unknown"
        if house_parcel and drive.get("centroid_parcel"):
            dx = drive["centroid_parcel"][0] - house_parcel[0]
            dy = drive["centroid_parcel"][1] - house_parcel[1]
            side = _cardinal_side(dx, dy)
        driveway_house = {
            "from_entry_to_house": entry_vec,
            "driveway_side": side,
            "vector": vec(house, drive),
        }

    return {
        "parcel": {"present": True},
        "house": house,
        "pool": pool,
        "driveway": {**drive, **(driveway_house or {})},
        "outbuildings": outs,
        "n_outbuildings": len(outs),
        "n_building_masses": 1 + len(outs) if house.get("present") else len(outs),
        "relationships": {
            "pool_house": vec(house, pool),
            "driveway_house": driveway_house,
            "pool_outbuilding": vec(pool, outs[0]) if outs else None,
            "house_parcel": {"centroid_parcel": house_parcel},
            "pool_parcel": {"centroid_parcel": pool_parcel},
        },
    }


def segment_parcel_bgr(
    bgr: np.ndarray,
    *,
    stand_number: str,
    geometry: dict | None,
) -> ParcelObjects:
    started = time.perf_counter()
    height, width = bgr.shape[:2]
    parcel = (
        parcel_mask_from_geometry((width, height), geometry)
        if geometry
        else np.full((height, width), 255, np.uint8)
    )
    masks = fastsam_masks(bgr)
    building, outbuildings = select_buildings(bgr, masks, parcel, pool=None)
    pool = select_pool(bgr, masks, parcel, building.mask if building.geometry.get("present") else None)
    if pool.status in {"CONFIRMED", "PROBABLE"}:
        building, outbuildings = select_buildings(bgr, masks, parcel, pool=pool.mask)
    driveway = select_driveway(
        bgr,
        masks,
        parcel,
        building.mask if building.geometry.get("present") else None,
        pool.mask if pool.status in {"CONFIRMED", "PROBABLE"} else None,
    )
    result = ParcelObjects(
        stand_number=stand_number,
        pool=pool,
        building=building,
        outbuildings=outbuildings,
        driveway=driveway,
        runtime_s=round(time.perf_counter() - started, 3),
    )
    result.spatial = spatial_fingerprint(result, parcel)
    return result


def segment_parcel(
    image_bytes: bytes,
    *,
    stand_number: str,
    geometry: dict | None,
) -> ParcelObjects:
    array = np.frombuffer(image_bytes, dtype=np.uint8)
    bgr = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if bgr is None:
        rgb = np.array(Image.open(io.BytesIO(image_bytes)).convert("RGB"))
        bgr = rgb[:, :, ::-1].copy()
    return segment_parcel_bgr(bgr, stand_number=stand_number, geometry=geometry)


def objects_to_json(result: ParcelObjects) -> dict[str, Any]:
    def dump_obj(obj: ObjectMask | None) -> dict | None:
        if obj is None:
            return None
        return {
            "kind": obj.kind,
            "status": obj.status,
            "score": obj.score,
            "clip": obj.clip,
            "notes": obj.notes,
            "geometry": {k: v for k, v in obj.geometry.items() if k != "contour_image"}
            | {"contour_n": len(obj.geometry.get("contour_image") or [])},
            "contour": obj.geometry.get("contour_image"),
        }

    return {
        "stand_number": result.stand_number,
        "version": result.version,
        "runtime_s": result.runtime_s,
        "pool": dump_obj(result.pool),
        "building": dump_obj(result.building),
        "outbuildings": [dump_obj(item) for item in result.outbuildings],
        "driveway": dump_obj(result.driveway),
        "spatial": result.spatial,
    }
