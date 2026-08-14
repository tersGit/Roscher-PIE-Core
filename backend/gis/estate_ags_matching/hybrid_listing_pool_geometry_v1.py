"""Hybrid listing-side pool geometry v1.

Preferred source: YOLOE-11s-seg (text: swimming pool), optionally SAM 2.1 tiny
from automatic YOLOE box/centroid prompts. FastSAM is fallback/presence only
and never overrides a valid YOLOE/SAM2 boundary.

Does not modify production ranking, OS v1, Scoring v2, native15, viewpoint-gate
rules, FastSAM implementation, or PR #12 benchmark outputs.
Water colour is not used as geometry or matching evidence.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from PIL import Image

from backend.gis.estate_ags_matching.listing_evidence_v2 import (
    classify_viewpoint,
)
from backend.gis.estate_ags_matching.pool_boundary_model_benchmark_v2 import (
    POOL_CLASS,
    _resize_mask,
    _yoloe_masks,
    load_sam21,
    load_times,
    load_yoloe,
    score_mask,
    set_yoloe_classes,
)
from backend.gis.estate_ags_matching.pool_boundary_v1 import (
    OVERVIEW_VIEWS,
    SKIP_VIEWS,
    clip_crop_scores,
    detect_segments,
    edge_clip_frac,
    fastsam_masks,
    geometry_bundle,
    grayscale_edges,
)
from backend.gis.estate_ags_matching.pool_geometry import _bgr_from_bytes

SOURCE_RANK = {
    "yoloe_sam2": 4,
    "yoloe": 3,
    "fastsam_fallback": 1,
    "presence_only": 0,
    "no_usable_geometry": -1,
}

PRIMARY_PROMPT = ["swimming pool"]
RECALL_PROMPTS = (
    ["swimming pool"],
    ["outdoor swimming pool"],
    ["residential swimming pool"],
)
RECALL_IMGSZ = (640, 800, 1024)
RECALL_CONF = (0.08, 0.04)


@dataclass
class PoolComponent:
    mask: np.ndarray
    contour: np.ndarray | None
    box: list[float]
    confidence: float
    relative_area: float
    centroid_xy: tuple[float, float]
    clip: dict[str, float]
    geometry: dict[str, Any]
    structural_support: float
    model: str
    prompt: str


@dataclass
class FrameGeometry:
    media_id: str
    viewpoint: str
    source: str
    source_reason: str
    scoring_ready: bool
    pool_present: bool
    yoloe_conf: float
    n_components: int
    dominant: dict[str, Any] | None
    secondary: dict[str, Any] | None
    component_relation: dict[str, Any]
    descriptors: dict[str, Any]
    gate_notes: list[str] = field(default_factory=list)
    recall_tried: list[str] = field(default_factory=list)
    runtime_s: float = 0.0
    oblique: bool = True
    contour_image: list | None = None
    mask: np.ndarray | None = None


def predict_yoloe_cfg(model, bgr: np.ndarray, names: list[str], *, conf: float, imgsz: int):
    set_yoloe_classes(model, names)
    image = Image.fromarray(bgr[:, :, ::-1])
    t0 = time.perf_counter()
    result = model.predict(image, device="cpu", imgsz=imgsz, conf=conf, verbose=False, save=False)[0]
    return result, time.perf_counter() - t0


def _centroid(mask: np.ndarray) -> tuple[float, float]:
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return 0.5, 0.5
    h, w = mask.shape
    return float(xs.mean() / max(w - 1, 1)), float(ys.mean() / max(h - 1, 1))


def _iou(a: np.ndarray, b: np.ndarray) -> float:
    inter = float(np.logical_and(a, b).sum())
    union = float(np.logical_or(a, b).sum())
    return inter / union if union else 0.0


def _box_from_mask(mask: np.ndarray) -> list[float]:
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return [0.0, 0.0, 1.0, 1.0]
    return [float(xs.min()), float(ys.min()), float(xs.max()), float(ys.max())]


def yoloe_validate(
    *,
    viewpoint: str,
    conf: float,
    geom: dict[str, Any],
    clip: dict[str, float],
    edge_clip: float,
    role: str = "dominant",
) -> tuple[bool, str, list[str]]:
    """Generic YOLOE/SAM2 gate. A text-prompt hit is not sufficient."""
    notes = []
    pool = float(clip.get("pool") or 0.0)
    wall = float(clip.get("wall") or 0.0)
    veg = float(clip.get("vegetation") or 0.0)
    furn = float(clip.get("furniture") or 0.0)
    bath = float(clip.get("bathtub") or 0.0)
    interior = float(clip.get("interior") or 0.0)
    area = float(geom.get("relative_area") or 0.0)
    compact = float(geom.get("compactness") or 0.0)
    if viewpoint in SKIP_VIEWS:
        return False, "blocked_viewpoint", ["blocked_viewpoint"]
    if bath >= 0.22 and bath >= pool:
        return False, "bathtub_or_bathroom", ["bathtub_or_bathroom"]
    if interior >= 0.30 and pool < 0.25:
        return False, "interior_scene", ["interior_scene"]
    if veg >= 0.32 and veg >= pool:
        notes.append("vegetation_contour")
    if (wall + veg + furn) > pool + 0.25 and pool < 0.20:
        notes.append("contamination_exceeds_pool")
    if edge_clip >= 0.28:
        notes.append("frame_edge_clipping")
    if compact < 0.08:
        notes.append("smear_compactness")
    min_area = 0.004 if role == "secondary" else 0.015
    max_area = 0.45 if viewpoint != "pool_closeup" else 0.70
    if area < min_area or area > max_area:
        notes.append("implausible_perimeter_area")
    if conf < 0.08:
        notes.append("low_detector_confidence")
    # Low detector conf is acceptable only with plausible area + pool CLIP.
    if conf < 0.18 and not (area >= 0.04 and pool >= 0.22):
        notes.append("weak_object_evidence")
    if viewpoint == "pool_closeup" and role == "dominant":
        notes.append("closeup_not_overview")
    accepted = not notes and viewpoint in OVERVIEW_VIEWS
    if role == "secondary":
        accepted = not [n for n in notes if n not in {"closeup_not_overview", "weak_object_evidence", "implausible_perimeter_area"}]
        if area < 0.004:
            accepted = False
            notes.append("secondary_too_small")
    reason = None if accepted else (notes[0] if notes else "failed_gate")
    return accepted, reason or "ok", notes


def _components_from_items(
    bgr: np.ndarray,
    items: list[tuple[np.ndarray, float, str, list[float]]],
    segments: np.ndarray,
    model: str,
    prompt: str,
) -> list[PoolComponent]:
    out = []
    height, width = bgr.shape[:2]
    for mask, conf, label, box in items:
        if label != POOL_CLASS and "pool" not in label.lower():
            continue
        scored = score_mask(
            bgr,
            mask,
            strategy="yoloe",
            model=model,
            confidence=conf,
            n_components=1,
            runtime_s=0.0,
            notes=[],
            box=box,
            segments=segments,
        )
        if scored.mask is None:
            continue
        out.append(
            PoolComponent(
                mask=mask,
                contour=scored.contour,
                box=box,
                confidence=conf,
                relative_area=float((scored.geometry or {}).get("relative_area") or mask.mean()),
                centroid_xy=_centroid(mask),
                clip=scored.clip,
                geometry=scored.geometry,
                structural_support=scored.structural_support,
                model=model,
                prompt=prompt,
            )
        )
    return out


def split_dominant_secondary(
    comps: list[PoolComponent],
    viewpoint: str,
) -> tuple[PoolComponent | None, PoolComponent | None, dict[str, Any]]:
    """Keep multiple water objects separate. Dominant is the largest plausible pool."""
    ranked = sorted(comps, key=lambda c: (c.relative_area, c.confidence), reverse=True)
    relation = {
        "component_count": len(ranked),
        "dominant_index": None,
        "secondary_index": None,
        "relative_size": None,
        "centroid_separation": None,
        "adjacent": None,
        "dominant_confidence": None,
        "secondary_confidence": None,
    }
    if not ranked:
        return None, None, relation
    height = ranked[0].mask.shape[0]
    width = ranked[0].mask.shape[1]
    diag = math.hypot(width, height)
    dominant = None
    for i, comp in enumerate(ranked):
        edge = 0.0
        if comp.contour is not None:
            edge = edge_clip_frac(comp.contour, width, height)
        ok, _reason, _notes = yoloe_validate(
            viewpoint=viewpoint if viewpoint != "pool_closeup" else "pool_overview",
            conf=comp.confidence,
            geom=comp.geometry or {"relative_area": comp.relative_area},
            clip=comp.clip,
            edge_clip=edge,
            role="dominant",
        )
        # Close-ups are allowed as a recorded dominant object, not overview-ready.
        if ok or (viewpoint == "pool_closeup" and comp.relative_area >= 0.02 and "bathtub_or_bathroom" not in _notes):
            if viewpoint != "pool_closeup" and not ok:
                continue
            dominant = comp
            relation["dominant_index"] = i
            relation["dominant_confidence"] = round(comp.confidence, 4)
            break
    if dominant is None:
        return None, None, relation
    secondary = None
    for j, comp in enumerate(ranked):
        if comp is dominant:
            continue
        size_ratio = comp.relative_area / max(dominant.relative_area, 1e-6)
        dist = math.hypot(
            comp.centroid_xy[0] - dominant.centroid_xy[0],
            comp.centroid_xy[1] - dominant.centroid_xy[1],
        )
        if size_ratio >= 0.55:
            continue
        if dist < 0.10:
            continue
        edge = 0.0
        if comp.contour is not None:
            edge = edge_clip_frac(comp.contour, width, height)
        ok, _reason, _notes = yoloe_validate(
            viewpoint=viewpoint,
            conf=comp.confidence,
            geom=comp.geometry or {"relative_area": comp.relative_area},
            clip=comp.clip,
            edge_clip=edge,
            role="secondary",
        )
        if not ok and "closeup_not_overview" not in _notes and "weak_object_evidence" not in _notes:
            if "bathtub_or_bathroom" in _notes or "vegetation_contour" in _notes:
                continue
        secondary = comp
        relation["secondary_index"] = j
        relation["secondary_confidence"] = round(comp.confidence, 4)
        relation["relative_size"] = round(size_ratio, 4)
        relation["centroid_separation"] = round(dist, 4)
        relation["adjacent"] = bool(dist < 0.35)
        break
    return dominant, secondary, relation


def _public_comp(comp: PoolComponent | None) -> dict[str, Any] | None:
    if comp is None:
        return None
    return {
        "model": comp.model,
        "prompt": comp.prompt,
        "confidence": round(comp.confidence, 4),
        "relative_area": round(comp.relative_area, 4),
        "centroid_xy": [round(comp.centroid_xy[0], 4), round(comp.centroid_xy[1], 4)],
        "clip": comp.clip,
        "structural_support": comp.structural_support,
        "geometry": {k: v for k, v in (comp.geometry or {}).items() if k not in {"contour_image", "descriptors"}},
        "contour_image": (comp.geometry or {}).get("contour_image"),
        "box": comp.box,
    }


def sam2_refine(bgr: np.ndarray, seed: PoolComponent, segments: np.ndarray) -> PoolComponent | None:
    sam = load_sam21()
    image = Image.fromarray(bgr[:, :, ::-1])
    result = sam.predict(
        image,
        bboxes=[seed.box],
        device="cpu",
        imgsz=640,
        verbose=False,
        save=False,
    )[0]
    if result.masks is None:
        return None
    height, width = bgr.shape[:2]
    mask = _resize_mask(result.masks.data.cpu().numpy()[0] > 0.5, width, height)
    if _iou(mask, seed.mask) < 0.45:
        return None
    if float(mask.mean()) > 1.6 * max(seed.relative_area, 1e-6):
        return None
    scored = score_mask(
        bgr,
        mask,
        strategy="yoloe_sam2",
        model="sam2.1_t",
        confidence=seed.confidence,
        n_components=1,
        runtime_s=0.0,
        notes=["prompt=yoloe_box"],
        box=seed.box,
        segments=segments,
    )
    return PoolComponent(
        mask=mask,
        contour=scored.contour,
        box=seed.box,
        confidence=seed.confidence,
        relative_area=float((scored.geometry or {}).get("relative_area") or mask.mean()),
        centroid_xy=_centroid(mask),
        clip=scored.clip,
        geometry=scored.geometry,
        structural_support=scored.structural_support,
        model="yoloe+sam2.1_t",
        prompt=seed.prompt,
    )


def collect_yoloe(
    bgr: np.ndarray,
    segments: np.ndarray,
    *,
    which: str,
    prompt: list[str],
    conf: float,
    imgsz: int,
) -> list[PoolComponent]:
    model = load_yoloe(which)
    result, _dt = predict_yoloe_cfg(model, bgr, prompt, conf=conf, imgsz=imgsz)
    items = _yoloe_masks(result, bgr.shape[1], bgr.shape[0])
    return _components_from_items(bgr, items, segments, f"yoloe-11{which}-seg", prompt[0])


def recall_ladder(bgr: np.ndarray, segments: np.ndarray) -> tuple[list[PoolComponent], list[str]]:
    """Generic automatable recall only when the primary pass finds no dominant pool."""
    tried = []
    found: list[PoolComponent] = []
    steps = (
        ("s", PRIMARY_PROMPT, 0.04, 640),
        ("m", PRIMARY_PROMPT, 0.04, 640),
        ("s", PRIMARY_PROMPT, 0.08, 1024),
        ("m", PRIMARY_PROMPT, 0.08, 1024),
        ("s", ["outdoor swimming pool"], 0.08, 640),
        ("m", ["outdoor swimming pool"], 0.08, 640),
        ("s", ["residential swimming pool"], 0.08, 640),
        ("m", ["residential swimming pool"], 0.08, 640),
        ("s", PRIMARY_PROMPT, 0.04, 1024),
        ("m", PRIMARY_PROMPT, 0.04, 1024),
    )
    for which, prompt, conf, imgsz in steps:
        key = f"11{which}/{prompt[0]}/imgsz={imgsz}/conf={conf}"
        tried.append(key)
        comps = collect_yoloe(bgr, segments, which=which, prompt=prompt, conf=conf, imgsz=imgsz)
        if comps:
            found.extend(comps)
            # Stop only on a detector-confident, dominant-sized pool — a low-conf
            # large blob must not block later prompt/resolution steps.
            if any(c.relative_area >= 0.015 and c.confidence >= 0.18 for c in comps):
                return found, tried
    return found, tried


def fastsam_presence_and_fallback(
    bgr: np.ndarray,
    segments: np.ndarray,
    viewpoint: str,
) -> tuple[str, PoolComponent | None, bool, list[str]]:
    """FastSAM is presence evidence. Box→SAM2 may be fallback geometry, never YOLOE override."""
    notes = []
    masks = fastsam_masks(bgr)
    ranked = []
    for mask in masks:
        frac = float(mask.mean())
        if frac < 0.008 or frac > 0.55:
            continue
        clip = clip_crop_scores(bgr, mask)
        if clip.get("bathtub", 0) >= 0.28 and clip.get("bathtub", 0) >= clip.get("pool", 0):
            continue
        if clip.get("pool", 0) < 0.16:
            continue
        ranked.append((clip.get("pool", 0) - 0.5 * clip.get("vegetation", 0), mask, clip))
    ranked.sort(key=lambda item: -item[0])
    if not ranked:
        return "no_usable_geometry", None, False, ["fastsam_no_pool_proposal"]
    notes.append("fastsam_pool_presence")
    _score, mask, clip = ranked[0]
    box = _box_from_mask(mask)
    sam = load_sam21()
    image = Image.fromarray(bgr[:, :, ::-1])
    result = sam.predict(image, bboxes=[box], device="cpu", imgsz=640, verbose=False, save=False)[0]
    if result.masks is None:
        return "presence_only", None, True, notes + ["fastsam_sam2_no_mask"]
    height, width = bgr.shape[:2]
    sam_mask = _resize_mask(result.masks.data.cpu().numpy()[0] > 0.5, width, height)
    scored = score_mask(
        bgr,
        sam_mask,
        strategy="fastsam_box_sam2",
        model="fastsam+sam2.1_t",
        confidence=float(clip.get("pool") or 0.0),
        n_components=1,
        runtime_s=0.0,
        notes=["prompt=fastsam_box"],
        box=box,
        segments=segments,
    )
    edge = 0.0 if scored.contour is None else edge_clip_frac(scored.contour, width, height)
    ok, reason, gnotes = yoloe_validate(
        viewpoint=viewpoint,
        conf=max(0.2, float(clip.get("pool") or 0.0)),
        geom=scored.geometry or {"relative_area": float(sam_mask.mean())},
        clip=scored.clip,
        edge_clip=edge,
        role="dominant",
    )
    if not ok:
        return "presence_only", None, True, notes + [reason or "fastsam_fallback_failed"] + gnotes
    compact = float((scored.geometry or {}).get("compactness") or 0.0)
    if compact < 0.20 or scored.structural_support < 0.35:
        return "presence_only", None, True, notes + ["fastsam_fallback_not_stronger_than_presence"]
    comp = PoolComponent(
        mask=sam_mask,
        contour=scored.contour,
        box=box,
        confidence=float(clip.get("pool") or 0.0),
        relative_area=float((scored.geometry or {}).get("relative_area") or sam_mask.mean()),
        centroid_xy=_centroid(sam_mask),
        clip=scored.clip,
        geometry=scored.geometry,
        structural_support=scored.structural_support,
        model="fastsam+sam2.1_t",
        prompt="fastsam_box",
    )
    return "fastsam_fallback", comp, True, notes + ["fastsam_box_sam2_accepted"]


def descriptors_from(comp: PoolComponent, viewpoint: str) -> dict[str, Any]:
    geom = dict(comp.geometry or {})
    sharp = float(geom.get("straight_edge_proportion") or 0.0)
    n_indents = int(geom.get("n_major_indents") or 0)
    n_corners = int(geom.get("n_corners") or 0)
    return {
        "component_count": 1,
        "straight_edge_proportion": geom.get("straight_edge_proportion"),
        "curved_edge_proportion": geom.get("curved_edge_proportion"),
        "major_corners": n_corners,
        "concavity": n_indents,
        "visible_rectilinear_structure": bool(n_corners >= 4 and sharp >= 0.25 and n_indents >= 0),
        "solidity": geom.get("solidity"),
        "compactness": geom.get("compactness"),
        "aspect_ratio": geom.get("aspect_ratio"),
        "orientation_deg": geom.get("orientation_deg"),
        "relative_area": geom.get("relative_area"),
        "viewpoint": viewpoint,
        "viewpoint_confidence": 1.0 if viewpoint in OVERVIEW_VIEWS else 0.3,
        "oblique": viewpoint != "aerial_near_nadir",
        "nadir_area_manufactured": False,
    }


def extract_frame_geometry(media_id: str, image_bytes: bytes, *, viewpoint: str | None = None) -> FrameGeometry:
    bgr = _bgr_from_bytes(image_bytes)
    t0 = time.perf_counter()
    if viewpoint is None:
        from backend.gis.estate_ags_matching.listing_evidence_v2 import clip_viewpoint_scores

        image = Image.fromarray(bgr[:, :, ::-1])
        scores = clip_viewpoint_scores(image)
        viewpoint, _ = classify_viewpoint(bgr, clip_scores=scores)
    if viewpoint in SKIP_VIEWS:
        return FrameGeometry(
            media_id=media_id,
            viewpoint=viewpoint,
            source="no_usable_geometry",
            source_reason="blocked_viewpoint",
            scoring_ready=False,
            pool_present=False,
            yoloe_conf=0.0,
            n_components=0,
            dominant=None,
            secondary=None,
            component_relation={"component_count": 0},
            descriptors={"oblique": True, "nadir_area_manufactured": False},
            gate_notes=["blocked_viewpoint"],
            runtime_s=round(time.perf_counter() - t0, 3),
        )

    gray, _mag, _canny = grayscale_edges(bgr)
    segments = detect_segments(gray)
    recall_tried: list[str] = []
    comps: list[PoolComponent] = []
    comps.extend(collect_yoloe(bgr, segments, which="s", prompt=PRIMARY_PROMPT, conf=0.08, imgsz=640))
    comps.extend(collect_yoloe(bgr, segments, which="m", prompt=PRIMARY_PROMPT, conf=0.08, imgsz=640))
    recall_tried.append("primary:11s+11m/swimming pool/imgsz=640/conf=0.08")

    dominant, secondary, relation = split_dominant_secondary(comps, viewpoint)
    if dominant is None:
        extra, tried = recall_ladder(bgr, segments)
        recall_tried.extend(tried)
        comps.extend(extra)
        dominant, secondary, relation = split_dominant_secondary(comps, viewpoint)

    source = "no_usable_geometry"
    reason = "no_valid_yoloe_pool"
    present = bool(comps)
    chosen = dominant
    if dominant is not None and viewpoint in OVERVIEW_VIEWS:
        refined = sam2_refine(bgr, dominant, segments)
        if refined is not None:
            chosen = refined
            source = "yoloe_sam2"
            reason = "yoloe_valid_sam2_iou_ok"
        else:
            source = "yoloe"
            reason = "yoloe_valid_sam2_rejected_or_unhelpful"
    elif dominant is not None and viewpoint == "pool_closeup":
        source = "yoloe"
        reason = "closeup_recorded_not_overview"
        chosen = dominant
    else:
        fb_source, fb_comp, present_fb, fb_notes = fastsam_presence_and_fallback(bgr, segments, viewpoint)
        present = present or present_fb
        if fb_source == "fastsam_fallback" and fb_comp is not None:
            # FastSAM must not override a stronger valid YOLOE boundary — none exists here.
            chosen = fb_comp
            source = "fastsam_fallback"
            reason = "no_valid_yoloe_fastsam_box_sam2"
            relation = {**relation, "fallback_notes": fb_notes}
        elif present_fb:
            source = "presence_only"
            reason = "fastsam_presence_without_valid_boundary"
            relation = {**relation, "fallback_notes": fb_notes}
        else:
            source = "no_usable_geometry"
            reason = "no_yoloe_no_fastsam"
            relation = {**relation, "fallback_notes": fb_notes}

    scoring_ready = source in {"yoloe_sam2", "yoloe"} and viewpoint in OVERVIEW_VIEWS and chosen is not None
    desc = descriptors_from(chosen, viewpoint) if chosen is not None else {"oblique": True, "nadir_area_manufactured": False}
    if secondary is not None:
        desc["component_count"] = 2
        desc["relative_component_geometry"] = {
            "size_ratio": relation.get("relative_size"),
            "centroid_separation": relation.get("centroid_separation"),
            "adjacent": relation.get("adjacent"),
        }
    return FrameGeometry(
        media_id=media_id,
        viewpoint=viewpoint,
        source=source,
        source_reason=reason,
        scoring_ready=scoring_ready,
        pool_present=present or chosen is not None,
        yoloe_conf=0.0 if chosen is None else chosen.confidence,
        n_components=int(relation.get("component_count") or 0),
        dominant=_public_comp(chosen),
        secondary=_public_comp(secondary),
        component_relation=relation,
        descriptors=desc,
        gate_notes=[reason],
        recall_tried=recall_tried,
        runtime_s=round(time.perf_counter() - t0, 3),
        oblique=bool(desc.get("oblique", True)),
        contour_image=None if chosen is None else (chosen.geometry or {}).get("contour_image"),
        mask=None if chosen is None else chosen.mask,
    )


def combine_listing_frames(frames: list[FrameGeometry]) -> dict[str, Any]:
    """Independent descriptors; do not merge image-space masks. Weak must not outweigh clean."""
    ready = [f for f in frames if f.scoring_ready and f.dominant is not None]
    overviews = [f for f in ready if f.viewpoint in OVERVIEW_VIEWS]
    pool = overviews or ready
    chosen = None
    if pool:
        chosen = max(
            pool,
            key=lambda f: (
                SOURCE_RANK.get(f.source, -1),
                float(f.dominant.get("structural_support") or 0.0) if f.dominant else 0.0,
                float(f.yoloe_conf or 0.0),
            ),
        )
    axes = []
    for f in overviews:
        ang = (f.descriptors or {}).get("orientation_deg")
        if ang is not None:
            axes.append((f.media_id, float(ang) % 180.0, SOURCE_RANK.get(f.source, 0)))
    partners = 0
    if chosen is not None and axes:
        cang = float((chosen.descriptors or {}).get("orientation_deg") or 0.0) % 180.0
        for mid, ang, rank in axes:
            if mid == chosen.media_id:
                continue
            delta = min(abs(cang - ang), 180.0 - abs(cang - ang))
            if delta <= 22.0 and rank >= SOURCE_RANK["yoloe"]:
                partners += 1
    return {
        "n_frames": len(frames),
        "n_scoring_ready": len(ready),
        "n_overview_ready": len(overviews),
        "chosen_id": None if chosen is None else chosen.media_id,
        "chosen_source": None if chosen is None else chosen.source,
        "chosen_reason": None if chosen is None else chosen.source_reason,
        "multiframe_axis_partners": partners,
        "note": "Masks are not merged. One clean YOLOE/SAM2 frame outweighs several weak detections.",
        "oblique": True if chosen is None else chosen.oblique,
        "nadir_area_manufactured": False,
    }


def frame_public(frame: FrameGeometry) -> dict[str, Any]:
    return {
        "media_id": frame.media_id,
        "viewpoint": frame.viewpoint,
        "source": frame.source,
        "source_reason": frame.source_reason,
        "scoring_ready": frame.scoring_ready,
        "pool_present": frame.pool_present,
        "yoloe_conf": frame.yoloe_conf,
        "n_components": frame.n_components,
        "dominant": frame.dominant,
        "secondary": frame.secondary,
        "component_relation": frame.component_relation,
        "descriptors": frame.descriptors,
        "gate_notes": frame.gate_notes,
        "recall_tried": frame.recall_tried,
        "runtime_s": frame.runtime_s,
        "oblique": frame.oblique,
        "contour_image": frame.contour_image,
    }
