"""Hybrid listing-side pool geometry v1.

Preferred source: YOLOE-11s-seg (text: swimming pool), optionally SAM 2.1 tiny
from automatic YOLOE box/centroid prompts. FastSAM is fallback/presence only
and never overrides a valid YOLOE/SAM2 boundary.

Extraction may mark a FastSAM mask scoring-ready when viewpoint quality and
CLIP pool evidence support a real water object. Presence-only detections
retain mask/contour evidence for later evaluation but are not scoring-ready.

Does not modify production ranking, OS v1, Scoring v2, native15, viewpoint-gate
rules, FastSAM implementation, Pool Gate, GIS inventory, or PR #12 outputs.
Water colour is not used as geometry or matching evidence. CLIP "deck" is used
only inside FastSAM candidate selection to reject turf/balcony objects; it is
not a ranking feature. Coping stones can score as deck, so YOLOE paths do not
reject on deck.
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
from backend.gis.estate_ags_matching.os_scoring_v2 import contour_descriptors
from backend.gis.estate_ags_matching.pool_boundary_model_benchmark_v2 import (
    POOL_CLASS,
    _resize_mask,
    _yoloe_masks,
    load_sam21,
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
from backend.gis.estate_ags_matching.pool_geometry import NORMALIZED_POINTS, _bgr_from_bytes, _resample_contour

SOURCE_RANK = {
    "yoloe_sam2": 4,
    "yoloe": 3,
    "fastsam_fallback": 1,
    "presence_only": 0,
    "no_usable_geometry": -1,
}

# Near-nadir planform outranks oblique ground-level overviews when both are valid.
VIEW_GEOMETRY_RANK = {
    "aerial_near_nadir": 5,
    "aerial_oblique": 4,
    "elevated_exterior": 3,
    "pool_overview": 2,
    "ground_level_exterior": 1,
    "garden_only": 0,
    "pool_closeup": 0,
}
AERIAL_VIEWS = frozenset({"aerial_near_nadir", "aerial_oblique"})
SCORING_READY_SOURCES = frozenset({"yoloe_sam2", "yoloe", "fastsam_fallback"})

PRIMARY_PROMPT = ["swimming pool"]
RECALL_PROMPTS = (
    ["swimming pool"],
    ["outdoor swimming pool"],
    ["residential swimming pool"],
)
RECALL_IMGSZ = (640, 800, 1024)
RECALL_CONF = (0.08, 0.04)

# Extraction-only. Not ranking weights.
AERIAL_MIN_AREA = 0.002
OVERVIEW_MIN_AREA = 0.015
SECONDARY_MIN_AREA = 0.004
MAX_AREA = 0.45
CLOSEUP_MAX_AREA = 0.70
FASTSAM_MIN_AREA = 0.002
FASTSAM_MAX_AREA = 0.55


def _cv2():
    import cv2

    return cv2


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
    detector: str = ""
    eligibility_reason: str = ""
    raw_contour: np.ndarray | None = None
    geometry_loss: dict[str, Any] = field(default_factory=dict)


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
    extraction_trace: list[dict[str, Any]] = field(default_factory=list)
    presence_evidence: dict[str, Any] | None = None
    geometry_loss: dict[str, Any] | None = None
    spa_relationship: dict[str, Any] | None = None
    geometry_quality: float = 0.0
    scoring_ready_reason: str = ""


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


def _trace(stages: list[dict[str, Any]], stage: str, status: str, reason: str, **detail: Any) -> None:
    row = {"stage": stage, "status": status, "reason": reason}
    if detail:
        row["detail"] = {k: v for k, v in detail.items() if v is not None}
    stages.append(row)


def min_area_for_viewpoint(viewpoint: str, role: str = "dominant") -> float:
    if role == "secondary":
        return SECONDARY_MIN_AREA
    if viewpoint in AERIAL_VIEWS:
        return AERIAL_MIN_AREA
    return OVERVIEW_MIN_AREA


def max_area_for_viewpoint(viewpoint: str) -> float:
    return CLOSEUP_MAX_AREA if viewpoint == "pool_closeup" else MAX_AREA


def semantic_reject_reason(
    clip: dict[str, float] | None,
    *,
    mode: str = "yoloe",
) -> str | None:
    """CLIP/object rejection. Colour is not used. Deck is FastSAM-only.

    CLIP deck includes coping stones, so YOLOE must not reject on deck.
    FastSAM has no class label; a deck-dominant blob is typically turf/balcony.
    """
    clip = clip or {}
    pool = float(clip.get("pool") or 0.0)
    wall = float(clip.get("wall") or 0.0)
    veg = float(clip.get("vegetation") or 0.0)
    furn = float(clip.get("furniture") or 0.0)
    bath = float(clip.get("bathtub") or 0.0)
    interior = float(clip.get("interior") or 0.0)
    deck = float(clip.get("deck") or 0.0)
    if bath >= 0.22 and bath >= pool:
        return "CLIP semantic rejection: bathtub_or_bathroom"
    if interior >= 0.30 and pool < 0.25:
        return "CLIP semantic rejection: interior_scene"
    if veg >= 0.32 and veg >= pool:
        return "wrong-object rejection: vegetation"
    if (wall + veg + furn) > pool + 0.25 and pool < 0.20:
        return "CLIP semantic rejection: contamination_exceeds_pool"
    if mode == "fastsam_candidate":
        if deck >= 0.40 and deck >= pool + 0.12:
            return "wrong-object rejection: deck_or_turf"
        if furn >= 0.35 and furn >= pool:
            return "wrong-object rejection: furniture"
        if pool < 0.16:
            return "CLIP semantic rejection: pool_score_below_minimum"
    return None


def fastsam_candidate_score(clip: dict[str, float] | None) -> float:
    """Rank FastSAM blobs by water/pool CLIP, not area or convenience.

    Deck is a small bonus only when it is below pool (coping). When deck
    outranks pool it is a penalty (turf/balcony). Not a ranking feature.
    """
    clip = clip or {}
    pool = float(clip.get("pool") or 0.0)
    veg = float(clip.get("vegetation") or 0.0)
    deck = float(clip.get("deck") or 0.0)
    wall = float(clip.get("wall") or 0.0)
    furn = float(clip.get("furniture") or 0.0)
    deck_term = 0.12 * deck if deck < pool else -0.65 * (deck - pool)
    return pool - 0.55 * veg + deck_term - 0.25 * wall - 0.30 * furn


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
    area = float(geom.get("relative_area") or 0.0)
    compact = float(geom.get("compactness") or 0.0)
    if viewpoint in SKIP_VIEWS:
        return False, "viewpoint gate rejection: blocked_viewpoint", ["blocked_viewpoint"]
    semantic = semantic_reject_reason(clip, mode="yoloe")
    if semantic:
        key = semantic.split(": ", 1)[-1]
        return False, key, [key, semantic]
    if edge_clip >= 0.28:
        notes.append("excessive edge contact")
    if compact < 0.08:
        notes.append("smear_compactness")
    min_area = min_area_for_viewpoint(viewpoint, role)
    max_area = max_area_for_viewpoint(viewpoint)
    if area < min_area:
        notes.append("candidate below minimum area")
    elif area > max_area:
        notes.append("candidate above maximum area")
    if conf < 0.08:
        notes.append("low_detector_confidence")
    if conf < 0.18 and not (area >= 0.04 and pool >= 0.22):
        notes.append("weak_object_evidence")
    if viewpoint == "pool_closeup" and role == "dominant":
        notes.append("closeup_not_overview")
    accepted = not notes and viewpoint in OVERVIEW_VIEWS
    if role == "secondary":
        accepted = not [n for n in notes if n not in {"closeup_not_overview", "weak_object_evidence", "candidate below minimum area", "candidate above maximum area"}]
        if area < SECONDARY_MIN_AREA:
            accepted = False
            notes.append("secondary_too_small")
    reason = None if accepted else (notes[0] if notes else "failed_gate")
    return accepted, reason or "ok", notes


def raw_contours_from_mask(mask: np.ndarray) -> tuple[np.ndarray | None, list[np.ndarray]]:
    cv2 = _cv2()
    binary = (np.asarray(mask) > 0).astype(np.uint8) * 255
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    contours = [c for c in contours if cv2.contourArea(c) >= 40]
    contours.sort(key=lambda c: -float(cv2.contourArea(c)))
    if not contours:
        return None, []
    return contours[0], contours[1:]


def _simplify_keep_structure(raw: np.ndarray) -> tuple[np.ndarray, str]:
    cv2 = _cv2()
    peri = max(float(cv2.arcLength(raw, True)), 1.0)
    approx = cv2.approxPolyDP(raw, 0.008 * peri, True)
    if len(approx) < 5:
        return raw, "simplification destroyed geometry: too few vertices; kept raw"
    raw_area = float(cv2.contourArea(raw))
    simple_area = float(cv2.contourArea(approx))
    if raw_area > 0 and abs(simple_area - raw_area) / raw_area > 0.18:
        return raw, "simplification destroyed geometry: area drift; kept raw"
    return approx, "ok"


def _xy_norm(contour: np.ndarray, width: int, height: int) -> list[list[float]]:
    pts = np.asarray(contour).reshape(-1, 2)
    return [
        [round(float(x) / max(width - 1, 1), 4), round(float(y) / max(height - 1, 1), 4)]
        for x, y in pts
    ]


def _indent_metrics(xy: list[list[float]] | None) -> dict[str, Any]:
    desc = contour_descriptors(xy) if xy and len(xy) >= 5 else None
    if not desc:
        return {
            "n_major_indents": 0,
            "max_indent": 0.0,
            "solidity": 1.0,
            "elongation": 1.0,
            "n_corners": 0,
            "circularity": 0.0,
        }
    return {
        "n_major_indents": int(desc.get("n_major_indents") or 0),
        "max_indent": float(desc.get("max_indent") or 0.0),
        "solidity": float(desc.get("solidity") or 1.0),
        "elongation": float(desc.get("elongation") or 1.0),
        "n_corners": int(desc.get("n_corners") or 0),
        "circularity": float(desc.get("circularity") or 0.0),
    }


def geometry_loss_between(raw_m: dict[str, Any], score_m: dict[str, Any], *, extra_blobs: int) -> dict[str, Any]:
    lost: list[str] = []
    raw_ind = int(raw_m.get("n_major_indents") or 0)
    score_ind = int(score_m.get("n_major_indents") or 0)
    raw_sol = float(raw_m.get("solidity") or 1.0)
    score_sol = float(score_m.get("solidity") or 1.0)
    raw_max = float(raw_m.get("max_indent") or 0.0)
    score_max = float(score_m.get("max_indent") or 0.0)
    if raw_ind >= 1 and score_ind == 0:
        lost.append("major_indents")
    if raw_sol <= 0.90 and score_sol >= 0.95:
        lost.append("freeform_collapsed_to_convex")
    if raw_max >= 0.08 and score_max < 0.04:
        lost.append("concavities_kinks")
    if extra_blobs:
        lost.append("spa_or_secondary_not_in_dominant_contour")
    if not score_m:
        verdict = "COLLAPSED"
        lost.append("no_scoring_contour")
    elif "major_indents" in lost and "freeform_collapsed_to_convex" in lost:
        verdict = "COLLAPSED"
    elif lost:
        verdict = "PARTIALLY LOST"
    else:
        verdict = "GEOMETRY PRESERVED"
    return {
        "verdict": verdict,
        "features_lost": lost,
        "raw_vs_scoring": {
            "n_major_indents": [raw_ind, score_ind],
            "max_indent": [round(raw_max, 4), round(score_max, 4)],
            "solidity": [round(raw_sol, 4), round(score_sol, 4)],
            "elongation": [
                round(float(raw_m.get("elongation") or 1.0), 4),
                round(float(score_m.get("elongation") or 1.0), 4),
            ],
        },
    }


def hybrid_geometry_from_mask(mask: np.ndarray) -> dict[str, Any]:
    """Mask → raw contour → conservative simplify → 64-pt scoring contour.

    Does not convex-hull merge spa/secondary blobs into the dominant outline.
    """
    height, width = mask.shape[:2]
    raw, extras = raw_contours_from_mask(mask)
    if raw is None:
        return {"ok": False, "reason": "contour invalid", "extras": extras}
    simplified, simple_reason = _simplify_keep_structure(raw)
    samples = _resample_contour(simplified, NORMALIZED_POINTS)
    if samples is None or len(samples) < 5:
        return {"ok": False, "reason": "simplification destroyed geometry", "raw": raw, "extras": extras}
    geom = geometry_bundle(simplified, width, height)
    geom["contour_image"] = [
        [round(float(x) / max(width - 1, 1), 4), round(float(y) / max(height - 1, 1), 4)]
        for x, y in samples
    ]
    raw_xy = _xy_norm(raw, width, height)
    simple_xy = _xy_norm(simplified, width, height)
    score_xy = geom["contour_image"]
    raw_m = _indent_metrics(raw_xy)
    simple_m = _indent_metrics(simple_xy)
    score_m = _indent_metrics(score_xy)
    loss = geometry_loss_between(raw_m, score_m, extra_blobs=len(extras))
    if simple_reason != "ok":
        loss.setdefault("features_lost", [])
        if "simplification destroyed geometry" not in loss["features_lost"]:
            loss["notes"] = [simple_reason]
    return {
        "ok": True,
        "reason": "ok",
        "contour": simplified,
        "raw_contour": raw,
        "extras": extras,
        "geometry": geom,
        "loss": loss,
        "stage_metrics": {"raw": raw_m, "simplified": simple_m, "normalized_64": score_m},
        "simple_reason": simple_reason,
    }


def apply_hybrid_geometry(comp: PoolComponent) -> PoolComponent:
    if comp.mask is None:
        return comp
    packed = hybrid_geometry_from_mask(comp.mask)
    if not packed.get("ok"):
        if not comp.eligibility_reason:
            comp.eligibility_reason = str(packed.get("reason") or "contour invalid")
        return comp
    comp.contour = packed["contour"]
    comp.raw_contour = packed["raw_contour"]
    geom = dict(comp.geometry or {})
    geom.update(packed["geometry"])
    comp.geometry = geom
    comp.geometry_loss = packed.get("loss") or {}
    return comp


def sam2_geometry_collapsed(seed: PoolComponent, refined: PoolComponent) -> str | None:
    """Reject SAM2 when it replaces irregular pool structure with a convex hull."""
    s = seed.geometry or {}
    r = refined.geometry or {}
    s_ind = int(s.get("n_major_indents") or 0)
    r_ind = int(r.get("n_major_indents") or 0)
    s_sol = float(s.get("solidity") or 1.0)
    r_sol = float(r.get("solidity") or 1.0)
    s_max = float(s.get("max_indent") or 0.0)
    r_max = float(r.get("max_indent") or 0.0)
    if s_ind >= 1 and r_ind == 0 and (r_sol - s_sol) >= 0.02:
        return "sam2_collapsed_major_indents"
    if s_sol <= 0.94 and r_sol >= 0.98:
        return "sam2_collapsed_to_convex"
    if s_max >= 0.05 and r_max < 0.03:
        return "sam2_lost_concavities"
    if r_sol >= 0.995 and s_sol <= 0.97:
        return "sam2_collapsed_to_convex"
    return None


def detach_secondary_from_dominant(dominant: PoolComponent, secondary: PoolComponent | None) -> PoolComponent:
    """Keep spa/secondary water out of the main-pool contour when they are separable."""
    if dominant is None or secondary is None or dominant.mask is None or secondary.mask is None:
        return dominant
    if dominant.mask.shape != secondary.mask.shape:
        return dominant
    cv2 = _cv2()
    dilated = cv2.dilate(secondary.mask.astype(np.uint8), np.ones((9, 9), np.uint8))
    new_mask = np.logical_and(dominant.mask, dilated == 0)
    if float(new_mask.mean()) < 0.45 * max(float(dominant.mask.mean()), 1e-6):
        return dominant
    if float(new_mask.mean()) < min_area_for_viewpoint("pool_overview"):
        return dominant
    dominant.mask = new_mask
    return apply_hybrid_geometry(dominant)


def fastsam_may_be_scoring_ready(viewpoint: str, clip: dict[str, float] | None) -> bool:
    """FastSAM planform is only scoring-ready from aerial/near-nadir frames.

    Elevated/oblique FastSAM is retained as presence evidence but is not
    promoted: balcony turf and similar high-solidity objects otherwise pass.
    """
    if viewpoint not in AERIAL_VIEWS:
        return False
    if semantic_reject_reason(clip, mode="fastsam_candidate"):
        return False
    return float((clip or {}).get("pool") or 0.0) >= 0.22


def spa_relationship_from(
    dominant: PoolComponent | None,
    secondary: PoolComponent | None,
    extra_contours: list[np.ndarray] | None = None,
) -> dict[str, Any]:
    extras = extra_contours or []
    present = secondary is not None or bool(extras)
    rel: dict[str, Any] = {
        "secondary_present": present,
        "merged_into_main_contour": False,
        "relative_location": None,
        "relative_size": None,
        "adjacent": None,
        "note": "Diagnostic geometry metadata only. Not a ranking weight.",
    }
    if dominant is None or secondary is None:
        if extras and dominant is not None:
            rel["same_mask_extra_blobs"] = len(extras)
        return rel
    dx = secondary.centroid_xy[0] - dominant.centroid_xy[0]
    dy = secondary.centroid_xy[1] - dominant.centroid_xy[1]
    dist = math.hypot(dx, dy)
    rel["relative_location"] = {
        "dx": round(dx, 4),
        "dy": round(dy, 4),
        "centroid_separation": round(dist, 4),
    }
    rel["relative_size"] = round(secondary.relative_area / max(dominant.relative_area, 1e-6), 4)
    rel["adjacent"] = bool(dist < 0.35)
    return rel


def _components_from_items(
    bgr: np.ndarray,
    items: list[tuple[np.ndarray, float, str, list[float]]],
    segments: np.ndarray,
    model: str,
    prompt: str,
) -> list[PoolComponent]:
    out = []
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
        comp = PoolComponent(
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
            detector=model,
            eligibility_reason="yoloe_candidate",
        )
        out.append(apply_hybrid_geometry(comp))
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
        "rejected": [],
    }
    if not ranked:
        return None, None, relation
    height = ranked[0].mask.shape[0]
    width = ranked[0].mask.shape[1]
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
        if ok or (viewpoint == "pool_closeup" and comp.relative_area >= 0.02 and "bathtub_or_bathroom" not in _notes):
            if viewpoint != "pool_closeup" and not ok:
                relation["rejected"].append({"index": i, "reason": _reason})
                continue
            dominant = comp
            relation["dominant_index"] = i
            relation["dominant_confidence"] = round(comp.confidence, 4)
            break
        relation["rejected"].append({"index": i, "reason": _reason})
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
            relation["rejected"].append({"index": j, "reason": "secondary comparable to dominant; not spa-sized"})
            continue
        if dist < 0.10:
            relation["rejected"].append({"index": j, "reason": "centroid too close; likely same object"})
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
            if "bathtub_or_bathroom" in _notes or "vegetation" in " ".join(_notes):
                relation["rejected"].append({"index": j, "reason": _reason})
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
    packed = hybrid_geometry_from_mask(comp.mask) if comp.mask is not None else {}
    extras = packed.get("extras") or []
    return {
        "model": comp.model,
        "prompt": comp.prompt,
        "detector": comp.detector or comp.model,
        "confidence": round(comp.confidence, 4),
        "relative_area": round(comp.relative_area, 4),
        "centroid_xy": [round(comp.centroid_xy[0], 4), round(comp.centroid_xy[1], 4)],
        "clip": comp.clip,
        "structural_support": comp.structural_support,
        "geometry": {k: v for k, v in (comp.geometry or {}).items() if k not in {"contour_image", "descriptors"}},
        "contour_image": (comp.geometry or {}).get("contour_image"),
        "raw_contour_image": None if packed.get("raw_contour") is None else _xy_norm(
            packed["raw_contour"], comp.mask.shape[1], comp.mask.shape[0]
        ),
        "box": comp.box,
        "eligibility_reason": comp.eligibility_reason,
        "geometry_loss": comp.geometry_loss or packed.get("loss"),
        "n_extra_mask_blobs": len(extras),
        "semantic_confidence": round(float((comp.clip or {}).get("pool") or 0.0), 4),
    }


def _presence_evidence(comp: PoolComponent | None, *, source: str, reason: str) -> dict[str, Any] | None:
    if comp is None or comp.mask is None:
        return None
    pub = _public_comp(comp) or {}
    return {
        "source_detector": source,
        "mask_confidence": round(comp.confidence, 4),
        "bounding_box": comp.box,
        "raw_contour": pub.get("raw_contour_image"),
        "contour_image": pub.get("contour_image"),
        "semantic_confidence": pub.get("semantic_confidence"),
        "clip": comp.clip,
        "relative_area": round(comp.relative_area, 4),
        "geometry_eligibility_reason": reason,
        "scoring_ready": False,
        "note": "Retained for evaluation. Not automatically scoring-ready.",
    }


def _component_from_mask(
    bgr: np.ndarray,
    mask: np.ndarray,
    segments: np.ndarray,
    *,
    clip: dict[str, float],
    model: str,
    prompt: str,
    strategy: str,
) -> PoolComponent | None:
    if mask is None or float(mask.mean()) <= 0:
        return None
    box = _box_from_mask(mask)
    scored = score_mask(
        bgr,
        mask,
        strategy=strategy,
        model=model,
        confidence=float(clip.get("pool") or 0.0),
        n_components=1,
        runtime_s=0.0,
        notes=[f"prompt={prompt}"],
        box=box,
        segments=segments,
    )
    comp = PoolComponent(
        mask=mask,
        contour=scored.contour,
        box=box,
        confidence=float(clip.get("pool") or 0.0),
        relative_area=float((scored.geometry or {}).get("relative_area") or mask.mean()),
        centroid_xy=_centroid(mask),
        clip=scored.clip or clip,
        geometry=scored.geometry,
        structural_support=scored.structural_support,
        model=model,
        prompt=prompt,
        detector=model,
    )
    return apply_hybrid_geometry(comp)


def sam2_from_box(bgr: np.ndarray, box: list[float]) -> np.ndarray | None:
    sam = load_sam21()
    image = Image.fromarray(bgr[:, :, ::-1])
    result = sam.predict(
        image,
        bboxes=[box],
        device="cpu",
        imgsz=640,
        verbose=False,
        save=False,
    )[0]
    if result.masks is None:
        return None
    height, width = bgr.shape[:2]
    return _resize_mask(result.masks.data.cpu().numpy()[0] > 0.5, width, height)


def sam2_from_points(bgr: np.ndarray, mask: np.ndarray) -> np.ndarray | None:
    ys, xs = np.where(mask)
    if len(xs) < 20:
        return None
    cv2 = _cv2()
    eroded = cv2.erode((mask.astype(np.uint8) * 255), np.ones((5, 5), np.uint8))
    ey, ex = np.where(eroded > 0)
    if len(ex) < 10:
        ex, ey = xs, ys
    pts = [
        [float(xs.mean()), float(ys.mean())],
        [float(np.percentile(ex, 25)), float(np.percentile(ey, 50))],
        [float(np.percentile(ex, 75)), float(np.percentile(ey, 50))],
    ]
    sam = load_sam21()
    image = Image.fromarray(bgr[:, :, ::-1])
    result = sam.predict(
        image,
        points=pts,
        labels=[1, 1, 1],
        device="cpu",
        imgsz=640,
        verbose=False,
        save=False,
    )[0]
    if result.masks is None:
        return None
    height, width = bgr.shape[:2]
    return _resize_mask(result.masks.data.cpu().numpy()[0] > 0.5, width, height)


def sam2_refine(bgr: np.ndarray, seed: PoolComponent, segments: np.ndarray) -> tuple[PoolComponent | None, str]:
    """Box and interior-point SAM2. Reject refinements that convexify the seed."""
    seed = apply_hybrid_geometry(seed)
    candidates: list[tuple[str, PoolComponent]] = []
    box_mask = sam2_from_box(bgr, seed.box)
    if box_mask is None:
        box_reason = "sam2_box_no_mask"
    elif _iou(box_mask, seed.mask) < 0.45:
        box_reason = "sam2_box_iou_below_seed"
    elif float(box_mask.mean()) > 1.6 * max(seed.relative_area, 1e-6):
        box_reason = "sam2_box_area_expanded"
    else:
        box_reason = "ok"
        box_comp = _component_from_mask(
            bgr, box_mask, segments, clip=seed.clip, model="yoloe+sam2.1_t", prompt=seed.prompt, strategy="yoloe_sam2"
        )
        if box_comp is not None:
            box_comp.confidence = seed.confidence
            collapse = sam2_geometry_collapsed(seed, box_comp)
            if collapse:
                box_reason = collapse
            else:
                candidates.append(("box", box_comp))
    point_mask = sam2_from_points(bgr, seed.mask)
    point_reason = "sam2_points_no_mask"
    if point_mask is not None:
        if _iou(point_mask, seed.mask) < 0.45:
            point_reason = "sam2_points_iou_below_seed"
        elif float(point_mask.mean()) > 1.6 * max(seed.relative_area, 1e-6):
            point_reason = "sam2_points_area_expanded"
        else:
            point_comp = _component_from_mask(
                bgr,
                point_mask,
                segments,
                clip=seed.clip,
                model="yoloe+sam2.1_t",
                prompt=seed.prompt,
                strategy="yoloe_sam2_points",
            )
            if point_comp is not None:
                point_comp.confidence = seed.confidence
                collapse = sam2_geometry_collapsed(seed, point_comp)
                if collapse:
                    point_reason = collapse
                else:
                    point_reason = "ok"
                    candidates.append(("points", point_comp))
    if not candidates:
        return None, f"sam2_rejected:{box_reason};{point_reason}"

    def _keep_structure(item: tuple[str, PoolComponent]) -> tuple[float, float, float]:
        _kind, comp = item
        geom = comp.geometry or {}
        seed_ind = int((seed.geometry or {}).get("n_major_indents") or 0)
        ind = int(geom.get("n_major_indents") or 0)
        sol = float(geom.get("solidity") or 1.0)
        return (ind - seed_ind, -sol, float((comp.clip or {}).get("pool") or 0.0))

    kind, best = max(candidates, key=_keep_structure)
    best.prompt = seed.prompt
    best.model = "yoloe+sam2.1_t"
    best.detector = f"yoloe_sam2_{kind}"
    best.eligibility_reason = f"yoloe_valid_sam2_{kind}"
    return best, f"yoloe_valid_sam2_{kind}"


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
            if any(c.relative_area >= min_area_for_viewpoint("pool_overview") and c.confidence >= 0.18 for c in comps):
                return found, tried
    return found, tried


def fastsam_presence_and_fallback(
    bgr: np.ndarray,
    segments: np.ndarray,
    viewpoint: str,
    stages: list[dict[str, Any]] | None = None,
) -> tuple[str, PoolComponent | None, bool, list[str], PoolComponent | None]:
    """Evaluate every FastSAM mask. Never accept the largest blob blindly.

    Returns (source, geometry_comp, present, notes, presence_comp).
    presence_comp is retained even when geometry is not scoring-ready.
    """
    notes: list[str] = []
    stages = stages if stages is not None else []
    masks = fastsam_masks(bgr)
    _trace(stages, "candidate_masks", "recorded", "fastsam_proposals", n=len(masks))
    ranked: list[tuple[float, np.ndarray, dict[str, float], str | None]] = []
    for mask in masks:
        frac = float(mask.mean())
        if frac < FASTSAM_MIN_AREA:
            _trace(stages, "mask_selection", "rejected", "candidate below minimum area", area=round(frac, 4))
            continue
        if frac > FASTSAM_MAX_AREA:
            _trace(stages, "mask_selection", "rejected", "candidate above maximum area", area=round(frac, 4))
            continue
        clip = clip_crop_scores(bgr, mask)
        reject = semantic_reject_reason(clip, mode="fastsam_candidate")
        score = fastsam_candidate_score(clip)
        ranked.append((score, mask, clip, reject))
        _trace(
            stages,
            "mask_selection",
            "rejected" if reject else "kept",
            reject or "fastsam_candidate_kept",
            area=round(frac, 4),
            clip_pool=clip.get("pool"),
            clip_veg=clip.get("vegetation"),
            clip_deck=clip.get("deck"),
            rank_score=round(score, 4),
        )
    ranked.sort(key=lambda item: -item[0])
    plausible = [item for item in ranked if item[3] is None]
    presence_src = plausible[0] if plausible else (ranked[0] if ranked else None)
    if presence_src is None:
        _trace(stages, "pool_detection", "rejected", "no candidate mask")
        return "no_usable_geometry", None, False, notes + ["no candidate mask"], None
    _score, pmask, pclip, preject = presence_src
    presence_comp = _component_from_mask(
        bgr,
        pmask,
        segments,
        clip=pclip,
        model="fastsam-s",
        prompt="fastsam_presence",
        strategy="fastsam_presence",
    )
    notes.append("fastsam_pool_presence")
    if presence_comp is not None:
        presence_comp.eligibility_reason = preject or "presence_mask_retained"
        presence_comp.detector = "fastsam-s"
    if not plausible:
        reason = preject or "wrong-object rejection"
        _trace(stages, "mask_selection", "rejected", reason)
        return "presence_only", None, True, notes + [reason], presence_comp

    chosen_comp: PoolComponent | None = None
    chosen_notes: list[str] = []
    for score, mask, clip, _rej in plausible:
        box = _box_from_mask(mask)
        sam_mask = sam2_from_box(bgr, box)
        seed_comp = _component_from_mask(
            bgr, mask, segments, clip=clip, model="fastsam-s", prompt="fastsam_mask", strategy="fastsam"
        )
        if sam_mask is None:
            use_mask, method = mask, "fastsam_mask_no_sam2"
            _trace(stages, "sam2_refine", "rejected", "fastsam_sam2_no_mask")
        elif float(sam_mask.mean()) > max_area_for_viewpoint(viewpoint):
            use_mask, method = mask, "fastsam_mask_sam2_too_large"
            _trace(stages, "sam2_refine", "rejected", "candidate above maximum area", area=round(float(sam_mask.mean()), 4))
        elif seed_comp is not None and _iou(sam_mask, seed_comp.mask) < 0.30:
            use_mask, method = mask, "fastsam_mask_sam2_iou_low"
            _trace(stages, "sam2_refine", "rejected", "sam2_iou_below_fastsam_seed")
        else:
            use_mask, method = sam_mask, "fastsam_box_sam2"
        comp = _component_from_mask(
            bgr,
            use_mask,
            segments,
            clip=clip,
            model="fastsam+sam2.1_t" if method == "fastsam_box_sam2" else "fastsam-s",
            prompt=method,
            strategy="fastsam_box_sam2" if method == "fastsam_box_sam2" else "fastsam",
        )
        if comp is None:
            _trace(stages, "raw_mask", "rejected", "contour invalid")
            continue
        if seed_comp is not None and method == "fastsam_box_sam2":
            collapse = sam2_geometry_collapsed(seed_comp, comp)
            if collapse:
                _trace(stages, "contour_cleanup", "rejected", collapse)
                comp = seed_comp
                method = "fastsam_mask_kept_after_sam2_collapse"
        height, width = bgr.shape[:2]
        edge = 0.0 if comp.contour is None else edge_clip_frac(comp.contour, width, height)
        ok, reason, gnotes = yoloe_validate(
            viewpoint=viewpoint,
            conf=max(0.2, float((comp.clip or {}).get("pool") or 0.0)),
            geom=comp.geometry or {"relative_area": float(comp.relative_area)},
            clip=comp.clip,
            edge_clip=edge,
            role="dominant",
        )
        semantic = semantic_reject_reason(comp.clip, mode="fastsam_candidate")
        if semantic:
            _trace(stages, "mask_selection", "rejected", semantic)
            chosen_notes.append(semantic)
            continue
        if not ok:
            _trace(stages, "scoring_ready_decision", "rejected", reason or "fastsam_fallback_failed", notes=gnotes)
            chosen_notes.append(reason or "fastsam_fallback_failed")
            if chosen_comp is None:
                chosen_comp = comp
                chosen_comp.eligibility_reason = reason or "not_scoring_ready"
            continue
        compact = float((comp.geometry or {}).get("compactness") or 0.0)
        if compact < 0.10:
            _trace(stages, "scoring_ready_decision", "rejected", "smear_compactness", compactness=compact)
            chosen_notes.append("smear_compactness")
            continue
        pool_clip = float((comp.clip or {}).get("pool") or 0.0)
        if fastsam_may_be_scoring_ready(viewpoint, comp.clip) and pool_clip >= 0.22:
            comp.eligibility_reason = f"{method}_scoring_ready"
            comp.detector = method
            _trace(stages, "scoring_ready_decision", "accepted", comp.eligibility_reason, clip_pool=pool_clip)
            return "fastsam_fallback", comp, True, notes + ["fastsam_box_sam2_accepted", method], presence_comp or comp
        if viewpoint not in AERIAL_VIEWS:
            comp.eligibility_reason = "viewpoint gate rejection: fastsam_not_aerial_planform"
        else:
            comp.eligibility_reason = "semantic_confidence_below_scoring_ready"
        _trace(stages, "scoring_ready_decision", "rejected", comp.eligibility_reason)
        chosen_comp = comp
        chosen_notes.append(comp.eligibility_reason)
        break
    keep = chosen_comp or presence_comp
    reason = chosen_notes[0] if chosen_notes else "fastsam_presence_without_valid_boundary"
    _trace(stages, "scoring_ready_decision", "rejected", reason)
    return "presence_only", keep, True, notes + [reason], presence_comp or keep


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
        "oblique": viewpoint not in AERIAL_VIEWS,
        "nadir_area_manufactured": False,
        "n_major_indents": n_indents,
        "max_indent": geom.get("max_indent"),
        "geometry_loss": comp.geometry_loss,
    }


def extraction_quality(frame: FrameGeometry) -> float:
    if frame.dominant is None:
        return 0.0
    clip = frame.dominant.get("clip") or {}
    pool = float(clip.get("pool") or 0.0)
    veg = float(clip.get("vegetation") or 0.0)
    deck = float(clip.get("deck") or 0.0)
    view = VIEW_GEOMETRY_RANK.get(frame.viewpoint, 0)
    src = SOURCE_RANK.get(frame.source, -1)
    ready = 20.0 if frame.scoring_ready else 0.0
    deck_pen = 2.0 * max(0.0, deck - pool) if deck >= pool + 0.12 else 0.0
    geom = frame.dominant.get("geometry") or {}
    n_indents = int(geom.get("n_major_indents") or 0)
    solidity = float(geom.get("solidity") or 1.0)
    max_indent = float(geom.get("max_indent") or 0.0)
    collapse = 0.0
    if n_indents == 0 and solidity >= 0.97:
        collapse = 1.6
    structure = min(2.4, 0.7 * n_indents + 1.2 * max(0.0, 0.96 - solidity) + 0.8 * max(0.0, max_indent - 0.04))
    return ready + 8.0 * view + src + 3.0 * pool - veg - deck_pen - collapse + structure + float(
        frame.dominant.get("structural_support") or 0.0
    )


def extract_frame_geometry(media_id: str, image_bytes: bytes, *, viewpoint: str | None = None) -> FrameGeometry:
    bgr = _bgr_from_bytes(image_bytes)
    t0 = time.perf_counter()
    stages: list[dict[str, Any]] = []
    _trace(stages, "source_image", "recorded", "loaded", media_id=media_id, shape=list(bgr.shape))
    if viewpoint is None:
        from backend.gis.estate_ags_matching.listing_evidence_v2 import clip_viewpoint_scores

        image = Image.fromarray(bgr[:, :, ::-1])
        scores = clip_viewpoint_scores(image)
        viewpoint, _ = classify_viewpoint(bgr, clip_scores=scores)
    _trace(stages, "viewpoint_classification", "recorded", viewpoint or "unknown")
    if viewpoint in SKIP_VIEWS:
        _trace(stages, "scoring_ready_decision", "rejected", "viewpoint gate rejection: blocked_viewpoint")
        return FrameGeometry(
            media_id=media_id,
            viewpoint=viewpoint,
            source="no_usable_geometry",
            source_reason="viewpoint gate rejection: blocked_viewpoint",
            scoring_ready=False,
            scoring_ready_reason="viewpoint gate rejection: blocked_viewpoint",
            pool_present=False,
            yoloe_conf=0.0,
            n_components=0,
            dominant=None,
            secondary=None,
            component_relation={"component_count": 0},
            descriptors={"oblique": True, "nadir_area_manufactured": False},
            gate_notes=["viewpoint gate rejection: blocked_viewpoint"],
            runtime_s=round(time.perf_counter() - t0, 3),
            extraction_trace=stages,
        )

    gray, _mag, _canny = grayscale_edges(bgr)
    segments = detect_segments(gray)
    recall_tried: list[str] = []
    comps: list[PoolComponent] = []
    comps.extend(collect_yoloe(bgr, segments, which="s", prompt=PRIMARY_PROMPT, conf=0.08, imgsz=640))
    comps.extend(collect_yoloe(bgr, segments, which="m", prompt=PRIMARY_PROMPT, conf=0.08, imgsz=640))
    recall_tried.append("primary:11s+11m/swimming pool/imgsz=640/conf=0.08")
    _trace(stages, "pool_detection", "recorded", "yoloe_primary", n_candidates=len(comps))

    dominant, secondary, relation = split_dominant_secondary(comps, viewpoint)
    if dominant is None:
        extra, tried = recall_ladder(bgr, segments)
        recall_tried.extend(tried)
        comps.extend(extra)
        _trace(stages, "pool_detection", "recorded", "yoloe_recall_ladder", n_extra=len(extra))
        dominant, secondary, relation = split_dominant_secondary(comps, viewpoint)

    source = "no_usable_geometry"
    reason = "no_valid_yoloe_pool"
    present = bool(comps)
    chosen = dominant
    presence_comp: PoolComponent | None = None
    if dominant is not None:
        _trace(
            stages,
            "mask_selection",
            "accepted",
            "yoloe_dominant",
            area=round(dominant.relative_area, 4),
            clip_pool=(dominant.clip or {}).get("pool"),
        )
        _trace(stages, "raw_mask", "recorded", "yoloe_mask")
        _trace(stages, "raw_contour", "recorded", "hybrid_raw_contour")
        if viewpoint in OVERVIEW_VIEWS:
            refined, sam_reason = sam2_refine(bgr, dominant, segments)
            if refined is not None:
                chosen = refined
                source = "yoloe_sam2"
                reason = sam_reason
                _trace(stages, "contour_cleanup", "accepted", sam_reason)
            else:
                source = "yoloe"
                reason = "yoloe_valid_sam2_rejected_or_unhelpful"
                chosen = dominant
                _trace(stages, "contour_cleanup", "rejected", sam_reason, kept="yoloe_mask")
            if chosen is not None and secondary is not None:
                chosen = detach_secondary_from_dominant(chosen, secondary)
        elif viewpoint == "pool_closeup":
            source = "yoloe"
            reason = "closeup_recorded_not_overview"
            chosen = dominant
            _trace(stages, "scoring_ready_decision", "rejected", "viewpoint gate rejection: closeup_not_overview")
        else:
            source = "yoloe"
            reason = "yoloe_recorded_non_overview"
            chosen = dominant
            _trace(stages, "scoring_ready_decision", "rejected", "viewpoint gate rejection")
    else:
        _trace(stages, "pool_detection", "rejected", "no_valid_yoloe_pool", rejected=relation.get("rejected"))
        fb_source, fb_comp, present_fb, fb_notes, presence_comp = fastsam_presence_and_fallback(
            bgr, segments, viewpoint, stages
        )
        present = present or present_fb
        if fb_source == "fastsam_fallback" and fb_comp is not None:
            chosen = fb_comp
            source = "fastsam_fallback"
            reason = "no_valid_yoloe_fastsam_selected"
            relation = {**relation, "fallback_notes": fb_notes}
        elif present_fb:
            source = "presence_only"
            reason = fb_notes[-1] if fb_notes else "fastsam_presence_without_valid_boundary"
            chosen = fb_comp
            relation = {**relation, "fallback_notes": fb_notes}
        else:
            source = "no_usable_geometry"
            reason = fb_notes[-1] if fb_notes else "no candidate mask"
            relation = {**relation, "fallback_notes": fb_notes}

    if chosen is not None:
        chosen = apply_hybrid_geometry(chosen)
        packed = hybrid_geometry_from_mask(chosen.mask)
        extras = packed.get("extras") or []
        spa = spa_relationship_from(chosen, secondary, extras)
        loss = chosen.geometry_loss or packed.get("loss")
        _trace(stages, "simplification", "recorded", packed.get("simple_reason") or "ok", loss=loss)
        _trace(stages, "normalized_64_point_contour", "recorded" if packed.get("ok") else "rejected", packed.get("reason") or "ok")
    else:
        spa = spa_relationship_from(None, secondary, [])
        loss = None
        extras = []

    scoring_ready = (
        source in SCORING_READY_SOURCES
        and viewpoint in OVERVIEW_VIEWS
        and chosen is not None
        and (chosen.geometry or {}).get("contour_image")
        and semantic_reject_reason(chosen.clip, mode="fastsam_candidate" if source == "fastsam_fallback" else "yoloe")
        is None
    )
    if source == "presence_only":
        scoring_ready = False
    if source == "fastsam_fallback" and not fastsam_may_be_scoring_ready(viewpoint, None if chosen is None else chosen.clip):
        scoring_ready = False
        if reason in {"no_valid_yoloe_fastsam_selected", "ok"}:
            reason = "viewpoint gate rejection: fastsam_not_aerial_planform"
    if scoring_ready:
        scoring_reason = reason
        _trace(stages, "scoring_ready_decision", "accepted", scoring_reason)
    else:
        scoring_reason = reason if reason not in {"ok", ""} else "not_scoring_ready"
        if not any(s["stage"] == "scoring_ready_decision" for s in stages):
            _trace(stages, "scoring_ready_decision", "rejected", scoring_reason)

    desc = descriptors_from(chosen, viewpoint) if chosen is not None else {"oblique": True, "nadir_area_manufactured": False}
    if secondary is not None:
        desc["component_count"] = 2
        desc["relative_component_geometry"] = {
            "size_ratio": relation.get("relative_size"),
            "centroid_separation": relation.get("centroid_separation"),
            "adjacent": relation.get("adjacent"),
        }
    presence = None
    if source == "presence_only":
        presence = _presence_evidence(presence_comp or chosen, source=source, reason=reason)
    quality_frame = FrameGeometry(
        media_id=media_id,
        viewpoint=viewpoint,
        source=source,
        source_reason=reason,
        scoring_ready=scoring_ready,
        scoring_ready_reason=scoring_reason,
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
        extraction_trace=stages,
        presence_evidence=presence,
        geometry_loss=loss,
        spa_relationship=spa,
    )
    quality_frame.geometry_quality = round(extraction_quality(quality_frame), 4)
    return quality_frame


def _frame_agreement(frames: list[FrameGeometry]) -> dict[str, Any]:
    ready = [f for f in frames if f.scoring_ready and f.dominant]
    if len(ready) < 2:
        return {"n_compared": len(ready), "agree": True, "note": "insufficient_scoring_ready_frames"}
    aspects = [float((f.dominant.get("geometry") or {}).get("aspect_ratio") or 0.0) for f in ready]
    sols = [float((f.dominant.get("geometry") or {}).get("solidity") or 0.0) for f in ready]
    inds = [int((f.dominant.get("geometry") or {}).get("n_major_indents") or 0) for f in ready]
    aspect_span = max(aspects) - min(aspects)
    agree = aspect_span < 1.2 and (max(sols) - min(sols)) < 0.12
    return {
        "n_compared": len(ready),
        "agree": agree,
        "aspect_span": round(aspect_span, 3),
        "solidity_span": round(max(sols) - min(sols), 3),
        "indent_values": inds,
        "note": "Incompatible perspective-distorted contours are not averaged.",
    }


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
                VIEW_GEOMETRY_RANK.get(f.viewpoint, 0),
                extraction_quality(f),
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
    agreement = _frame_agreement(frames)
    qualities = [
        {
            "media_id": f.media_id,
            "viewpoint": f.viewpoint,
            "source": f.source,
            "scoring_ready": f.scoring_ready,
            "extraction_quality": round(extraction_quality(f), 4),
            "source_reason": f.source_reason,
        }
        for f in frames
    ]
    return {
        "n_frames": len(frames),
        "n_scoring_ready": len(ready),
        "n_overview_ready": len(overviews),
        "chosen_id": None if chosen is None else chosen.media_id,
        "chosen_source": None if chosen is None else chosen.source,
        "chosen_reason": None if chosen is None else chosen.source_reason,
        "chosen_viewpoint": None if chosen is None else chosen.viewpoint,
        "frame_selection_reason": None
        if chosen is None
        else (
            f"best_valid_geometry viewpoint={chosen.viewpoint} source={chosen.source} "
            f"quality={round(extraction_quality(chosen), 3)}; aerial/near-nadir outranks oblique when both valid; "
            "incompatible contours are not averaged"
        ),
        "multiframe_axis_partners": partners,
        "multiframe_agreement": agreement,
        "per_frame_extraction_quality": qualities,
        "note": "Masks are not merged. One clean YOLOE/SAM2 frame outweighs several weak detections. Near-nadir outranks oblique.",
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
        "scoring_ready_reason": frame.scoring_ready_reason,
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
        "extraction_trace": frame.extraction_trace,
        "presence_evidence": frame.presence_evidence,
        "geometry_loss": frame.geometry_loss,
        "spa_relationship": frame.spa_relationship,
        "geometry_quality": frame.geometry_quality,
    }
