"""Pool-boundary model benchmark v2 — listing-side, CPU, no FastSAM replacement.

Does not modify production ranking, OS v1, Scoring v2, native15, viewpoint
gates, or Pool Boundary Extraction v1. Water colour is not used as geometry.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from backend.gis.estate_ags_matching.pool_boundary_v1 import (
    clip_crop_scores,
    detect_segments,
    geometry_bundle,
    grayscale_edges,
    structural_support_frac,
)
from backend.gis.estate_ags_matching.pool_geometry import _bgr_from_bytes

CACHE = Path(__file__).resolve().parents[3] / "data/cache/models"
YOLOE_S = CACHE / "yoloe-11s-seg.pt"
YOLOE_M = CACHE / "yoloe-11m-seg.pt"
SAM21_T = CACHE / "sam2.1_t.pt"

TEXT_POOL = ["swimming pool"]
TEXT_MULTI = ["swimming pool", "hot tub", "wooden deck", "lawn"]
POOL_CLASS = "swimming pool"


@dataclass
class MaskResult:
    strategy: str
    model: str
    contour: np.ndarray | None
    mask: np.ndarray | None
    confidence: float
    n_components: int
    clip: dict[str, float] = field(default_factory=dict)
    geometry: dict[str, Any] = field(default_factory=dict)
    structural_support: float = 0.0
    runtime_s: float = 0.0
    notes: list[str] = field(default_factory=list)
    box: list[float] | None = None


def rss_mb() -> float:
    import resource

    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def _contour_from_mask(mask: np.ndarray) -> np.ndarray | None:
    import cv2

    binary = (mask.astype(np.uint8)) * 255
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    return max(contours, key=cv2.contourArea)


def _resize_mask(mask: np.ndarray, width: int, height: int) -> np.ndarray:
    import cv2

    return cv2.resize(mask.astype(np.uint8), (width, height), interpolation=cv2.INTER_NEAREST).astype(bool)


def _yoloe_masks(result, width: int, height: int) -> list[tuple[np.ndarray, float, str, list[float]]]:
    out = []
    if result.masks is None or result.boxes is None:
        return out
    names = result.names or {}
    data = result.masks.data.cpu().numpy()
    confs = result.boxes.conf.cpu().numpy()
    clss = result.boxes.cls.cpu().numpy().astype(int)
    xyxy = result.boxes.xyxy.cpu().numpy()
    for i, raw in enumerate(data):
        mask = _resize_mask(raw > 0.5, width, height)
        label = names.get(int(clss[i]), str(int(clss[i])))
        out.append((mask, float(confs[i]), str(label), [float(v) for v in xyxy[i]]))
    return out


def score_mask(
    bgr: np.ndarray,
    mask: np.ndarray,
    *,
    strategy: str,
    model: str,
    confidence: float,
    n_components: int,
    runtime_s: float,
    notes: list[str],
    box: list[float] | None,
    segments: np.ndarray,
) -> MaskResult:
    height, width = bgr.shape[:2]
    contour = _contour_from_mask(mask)
    geom: dict[str, Any] = {}
    support = 0.0
    clip = {"pool": 0.0, "wall": 0.0, "vegetation": 0.0, "furniture": 0.0, "bathtub": 0.0, "interior": 0.0, "deck": 0.0}
    if contour is not None and mask.mean() > 0:
        geom = geometry_bundle(contour, width, height)
        support = structural_support_frac(contour, segments)
        clip = clip_crop_scores(bgr, mask)
    return MaskResult(
        strategy=strategy,
        model=model,
        contour=contour,
        mask=mask,
        confidence=round(confidence, 4),
        n_components=n_components,
        clip={k: round(float(v), 4) for k, v in clip.items()},
        geometry=geom,
        structural_support=round(float(support), 4),
        runtime_s=round(runtime_s, 3),
        notes=notes,
        box=box,
    )


def public_mask(res: MaskResult | None) -> dict[str, Any] | None:
    if res is None:
        return None
    return {
        "strategy": res.strategy,
        "model": res.model,
        "confidence": res.confidence,
        "n_components": res.n_components,
        "clip": res.clip,
        "geometry": {k: v for k, v in res.geometry.items() if k not in {"contour_image", "descriptors"}},
        "contour_image": res.geometry.get("contour_image"),
        "structural_support": res.structural_support,
        "runtime_s": res.runtime_s,
        "notes": res.notes,
        "box": res.box,
        "contamination": {
            "deck": res.clip.get("deck"),
            "vegetation": res.clip.get("vegetation"),
            "furniture": res.clip.get("furniture"),
            "wall": res.clip.get("wall"),
            "bathtub": res.clip.get("bathtub"),
        },
        "edge_adherence": res.structural_support,
        "mask_completeness_rel_area": (res.geometry or {}).get("relative_area"),
        "boundary_closure": bool((res.geometry or {}).get("closed")),
        "straight_edge_proportion": (res.geometry or {}).get("straight_edge_proportion"),
        "n_corners": (res.geometry or {}).get("n_corners"),
        "n_major_indents": (res.geometry or {}).get("n_major_indents"),
        "compactness": (res.geometry or {}).get("compactness"),
        "solidity": (res.geometry or {}).get("solidity"),
    }


_yoloe: dict[str, Any] = {}
_sam = None
_load_times: dict[str, float] = {}
_yoloe_class_key: dict[int, tuple[str, ...]] = {}


def load_yoloe(which: str = "s"):
    key = which
    if key in _yoloe:
        return _yoloe[key]
    from ultralytics import YOLOE

    path = YOLOE_S if which == "s" else YOLOE_M
    t0 = time.perf_counter()
    model = YOLOE(str(path))
    model.eval()
    _load_times[f"yoloe-11{which}-seg"] = round(time.perf_counter() - t0, 3)
    _yoloe[key] = model
    return model


def load_sam21():
    global _sam
    if _sam is not None:
        return _sam
    from ultralytics import SAM

    t0 = time.perf_counter()
    _sam = SAM(str(SAM21_T))
    _load_times["sam2.1_t"] = round(time.perf_counter() - t0, 3)
    return _sam


def load_times() -> dict[str, float]:
    return dict(_load_times)


def set_yoloe_classes(model, names: list[str]) -> None:
    key = id(model)
    frozen = tuple(names)
    if _yoloe_class_key.get(key) == frozen:
        return
    model.eval()
    pe = model.get_text_pe(names)
    model.set_classes(names, pe)
    _yoloe_class_key[key] = frozen


def predict_yoloe(model, bgr: np.ndarray, names: list[str], conf: float = 0.15):
    set_yoloe_classes(model, names)
    rgb = bgr[:, :, ::-1]
    image = Image.fromarray(rgb)
    t0 = time.perf_counter()
    results = model.predict(image, device="cpu", imgsz=640, conf=conf, verbose=False, save=False)
    dt = time.perf_counter() - t0
    return results[0], dt


def best_pool_detection(items: list[tuple[np.ndarray, float, str, list[float]]]):
    pools = [item for item in items if item[2] == POOL_CLASS]
    if not pools:
        return None
    return max(pools, key=lambda item: item[1] * max(float(item[0].mean()), 1e-6))


def yoloe_text_pool(bgr: np.ndarray, which: str, segments: np.ndarray) -> MaskResult:
    model = load_yoloe(which)
    result, dt = predict_yoloe(model, bgr, TEXT_POOL)
    height, width = bgr.shape[:2]
    items = _yoloe_masks(result, width, height)
    best = best_pool_detection(items)
    notes = [f"n_dets={len(items)}"]
    if best is None:
        return MaskResult(
            strategy="text_only",
            model=f"yoloe-11{which}-seg",
            contour=None,
            mask=None,
            confidence=0.0,
            n_components=0,
            runtime_s=round(dt, 3),
            notes=notes + ["no_pool_detection"],
        )
    mask, conf, _label, box = best
    return score_mask(
        bgr,
        mask,
        strategy="text_only",
        model=f"yoloe-11{which}-seg",
        confidence=conf,
        n_components=int(sum(1 for item in items if item[2] == POOL_CLASS)),
        runtime_s=dt,
        notes=notes,
        box=box,
        segments=segments,
    )


def yoloe_text_multi(bgr: np.ndarray, which: str, segments: np.ndarray) -> MaskResult:
    model = load_yoloe(which)
    result, dt = predict_yoloe(model, bgr, TEXT_MULTI)
    height, width = bgr.shape[:2]
    items = _yoloe_masks(result, width, height)
    counts = {}
    for _m, _c, label, _b in items:
        counts[label] = counts.get(label, 0) + 1
    best = best_pool_detection(items)
    notes = [f"n_dets={len(items)}", f"classes={counts}"]
    if best is None:
        return MaskResult(
            strategy="text_multi",
            model=f"yoloe-11{which}-seg",
            contour=None,
            mask=None,
            confidence=0.0,
            n_components=0,
            runtime_s=round(dt, 3),
            notes=notes + ["no_pool_detection"],
        )
    mask, conf, _label, box = best
    others = [item for item in items if item[2] != POOL_CLASS]
    if others:
        notes.append("other_class_dets=" + ",".join(sorted({item[2] for item in others})))
    return score_mask(
        bgr,
        mask,
        strategy="text_multi",
        model=f"yoloe-11{which}-seg",
        confidence=conf,
        n_components=int(sum(1 for item in items if item[2] == POOL_CLASS)),
        runtime_s=dt,
        notes=notes,
        box=box,
        segments=segments,
    )


def sam_from_box(bgr: np.ndarray, box: list[float], segments: np.ndarray, seed_conf: float) -> MaskResult:
    sam = load_sam21()
    rgb = bgr[:, :, ::-1]
    image = Image.fromarray(rgb)
    t0 = time.perf_counter()
    results = sam.predict(
        image,
        bboxes=[box],
        device="cpu",
        imgsz=640,
        verbose=False,
        save=False,
    )
    dt = time.perf_counter() - t0
    height, width = bgr.shape[:2]
    res = results[0]
    if res.masks is None:
        return MaskResult(
            strategy="box_sam2",
            model="sam2.1_t",
            contour=None,
            mask=None,
            confidence=0.0,
            n_components=0,
            runtime_s=round(dt, 3),
            notes=["sam2_no_mask"],
            box=box,
        )
    raw = res.masks.data.cpu().numpy()[0]
    mask = _resize_mask(raw > 0.5, width, height)
    return score_mask(
        bgr,
        mask,
        strategy="box_sam2",
        model="sam2.1_t",
        confidence=seed_conf,
        n_components=1,
        runtime_s=dt,
        notes=["prompt=yoloe_box"],
        box=box,
        segments=segments,
    )


def sam_from_point(bgr: np.ndarray, mask: np.ndarray, seed_conf: float, segments: np.ndarray) -> MaskResult:
    ys, xs = np.where(mask)
    if len(xs) < 20:
        return MaskResult(
            strategy="point_sam2",
            model="sam2.1_t",
            contour=None,
            mask=None,
            confidence=0.0,
            n_components=0,
            notes=["no_seed_mask_for_point"],
        )
    # Centroid of the detector mask — automatable, not a manual click.
    px, py = float(xs.mean()), float(ys.mean())
    sam = load_sam21()
    rgb = bgr[:, :, ::-1]
    image = Image.fromarray(rgb)
    t0 = time.perf_counter()
    results = sam.predict(
        image,
        points=[[px, py]],
        labels=[1],
        device="cpu",
        imgsz=640,
        verbose=False,
        save=False,
    )
    dt = time.perf_counter() - t0
    height, width = bgr.shape[:2]
    res = results[0]
    if res.masks is None:
        return MaskResult(
            strategy="point_sam2",
            model="sam2.1_t",
            contour=None,
            mask=None,
            confidence=0.0,
            n_components=0,
            runtime_s=round(dt, 3),
            notes=["sam2_no_mask", f"point={[round(px), round(py)]}"],
        )
    raw = res.masks.data.cpu().numpy()[0]
    out = _resize_mask(raw > 0.5, width, height)
    return score_mask(
        bgr,
        out,
        strategy="point_sam2",
        model="sam2.1_t",
        confidence=seed_conf,
        n_components=1,
        runtime_s=dt,
        notes=["prompt=yoloe_mask_centroid", f"point={[round(px), round(py)]}"],
        box=None,
        segments=segments,
    )


def pick_best(results: list[MaskResult]) -> MaskResult | None:
    usable = [r for r in results if r.mask is not None and r.confidence > 0]
    if not usable:
        return None

    def rank(r: MaskResult) -> tuple:
        pool = float(r.clip.get("pool") or 0.0)
        veg = float(r.clip.get("vegetation") or 0.0)
        furn = float(r.clip.get("furniture") or 0.0)
        bath = float(r.clip.get("bathtub") or 0.0)
        area = float((r.geometry or {}).get("relative_area") or 0.0)
        plausible = 1 if 0.01 <= area <= 0.45 else 0
        return (
            plausible,
            pool - 0.4 * veg - 0.4 * furn - 0.6 * bath,
            r.structural_support,
            r.confidence,
        )

    return max(usable, key=rank)
