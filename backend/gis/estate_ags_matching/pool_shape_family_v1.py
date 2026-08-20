"""Pool Shape Family v1 — diagnostic geometry classes. Not a production ranker.

Classifies a pool contour into a coarse visual family using measurable
geometry only. No water colour, no listing-id rules, no stand-number rules,
and no Scoring v2 weight changes.

Intended use: diagnostic compatibility between a listing contour and a
candidate contour *before* Shape v2. Production ranking must not import this
into freeze / score_v2.
"""
from __future__ import annotations

import math
from typing import Any, Mapping

import numpy as np

from backend.gis.estate_ags_matching.os_scoring_v2 import (
    _as_xy,
    contour_chamfer_sim,
    contour_descriptors,
    pca_normalize,
    shape_v2_similarity,
)

FAMILIES = (
    "RECTANGULAR",
    "LAP_ELONGATED",
    "FREEFORM",
    "KIDNEY_CURVED",
    "COMPOUND_IRREGULAR",
    "ROUND_OVAL",
    "UNKNOWN",
)

COMPATIBLE = "compatible"
PARTIAL = "partial"
INCOMPATIBLE = "incompatible"
NO_DECISION = "no_decision"

# Diagnostic multipliers applied to shape_v2 only. Not tuned to a stand.
PENALTY = {
    COMPATIBLE: 1.0,
    PARTIAL: 0.55,
    INCOMPATIBLE: 0.20,
    NO_DECISION: 1.0,
}

SHAPE_V2_WEIGHTS = {
    "elongation": 0.22,
    "chamfer": 0.18,
    "hu": 0.16,
    "solidity": 0.10,
    "n_indents": 0.08,
    "max_indent": 0.08,
    "n_corners": 0.08,
    "circularity": 0.05,
    "sharp_frac": 0.03,
    "radial_cv": 0.02,
}

WORKING_SIZE = 400.0


def _cv2():
    import cv2

    return cv2


def to_working_xy(points: Any) -> np.ndarray | None:
    """Map 0-1 image-normalised or pixel contours onto a ~400 px canvas."""
    xy = _as_xy(points)
    if xy is None:
        return None
    span = xy.max(axis=0) - xy.min(axis=0)
    scale = (WORKING_SIZE - 20.0) / max(float(span.max()), 1e-9)
    return (xy - xy.min(axis=0)) * scale + 10.0


def edge_angle_stats(xy: np.ndarray) -> dict[str, float]:
    closed = np.vstack([xy, xy[0]])
    delta = np.diff(closed, axis=0)
    weights = np.linalg.norm(delta, axis=1)
    angles = np.degrees(np.arctan2(delta[:, 1], delta[:, 0])) % 180.0
    hist, _ = np.histogram(angles, bins=18, range=(0.0, 180.0), weights=weights)
    total = float(hist.sum()) or 1.0
    prob = hist / total
    nz = prob[prob > 0]
    entropy = float(-np.sum(nz * np.log(nz)))
    entropy_norm = entropy / math.log(18.0)
    peaks = 0
    for i, value in enumerate(prob):
        if value > 0.12 and value >= prob[(i - 1) % 18] and value >= prob[(i + 1) % 18]:
            peaks += 1
    return {
        "angle_entropy": round(entropy_norm, 4),
        "n_angle_peaks": int(peaks),
    }


def scaled_geometry(points: Any) -> dict[str, Any] | None:
    """Pixel-scale geometry plus Shape v2 descriptors. Colour is not used."""
    xy = _as_xy(points)
    if xy is None:
        return None
    work = to_working_xy(xy)
    if work is None:
        return None
    cv2 = _cv2()
    contour = np.round(work).astype(np.int32).reshape(-1, 1, 2)
    area = float(cv2.contourArea(contour))
    peri = float(cv2.arcLength(contour, True))
    if area < 8.0 or peri < 16.0:
        return None
    circularity = float(4.0 * math.pi * area / max(peri * peri, 1e-6))
    hull = cv2.convexHull(contour)
    hull_area = max(float(cv2.contourArea(hull)), 1e-6)
    solidity = float(area / hull_area)
    (_cx, _cy), (rw, rh), angle = cv2.minAreaRect(contour.astype(np.float32))
    rect_area = max(float(rw) * float(rh), 1e-6)
    rectangularity = float(area / rect_area)
    elongation = float(max(rw, rh) / max(min(rw, rh), 1e-3))
    bbox = [float(work[:, 0].min()), float(work[:, 1].min()), float(work[:, 0].max()), float(work[:, 1].max())]
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    desc = contour_descriptors(xy) or {}
    angles = edge_angle_stats(work)
    sharp = float(desc.get("sharp_frac") or 0.0)
    return {
        "point_count": int(len(xy)),
        "bbox": [round(v, 4) for v in bbox],
        "width": round(width, 3),
        "height": round(height, 3),
        "aspect_ratio": round(width / max(height, 1e-6), 4),
        "area": round(area, 2),
        "perimeter": round(peri, 2),
        "solidity": round(solidity, 4),
        "convexity": round(solidity, 4),
        "circularity": round(circularity, 4),
        "rectangularity": round(rectangularity, 4),
        "orientation_deg": round(float(angle), 2),
        "elongation": round(elongation, 4),
        "min_rect_wh": [round(float(rw), 2), round(float(rh), 2)],
        "n_corners": desc.get("n_corners"),
        "n_major_indents": desc.get("n_major_indents"),
        "max_indent": desc.get("max_indent"),
        "sharp_frac": desc.get("sharp_frac"),
        "radial_cv": desc.get("radial_cv"),
        "symmetry": desc.get("symmetry"),
        "hu_log": desc.get("hu_log"),
        "curved_edge_fraction": round(max(0.0, 1.0 - sharp), 4),
        **angles,
        "shape_v2_descriptors": {key: val for key, val in desc.items() if key != "norm_xy"},
        "norm_xy": desc.get("norm_xy"),
    }


def classify_pool_shape_family(metrics: Mapping[str, Any] | None) -> dict[str, Any]:
    """Coarse family from geometry. Unknown if evidence is thin."""
    if not metrics:
        return {"family": "UNKNOWN", "confidence": 0.0, "reason": "no_geometry", "signals": {}}
    elong = float(metrics.get("elongation") or 1.0)
    rect = float(metrics.get("rectangularity") or 0.0)
    sol = float(metrics.get("solidity") or 0.0)
    circ = float(metrics.get("circularity") or 0.0)
    sharp = float(metrics.get("sharp_frac") or 0.0)
    entropy = float(metrics.get("angle_entropy") or 0.5)
    indents = int(metrics.get("n_major_indents") or 0)
    max_indent = float(metrics.get("max_indent") or 0.0)
    polygonal = entropy <= 0.52 and sharp >= 0.28
    curved = entropy >= 0.60 and sharp <= 0.24
    signals = {
        "polygonal": polygonal,
        "curved": curved,
        "elongation": round(elong, 4),
        "rectangularity": round(rect, 4),
        "solidity": round(sol, 4),
        "circularity": round(circ, 4),
        "sharp_frac": round(sharp, 4),
        "angle_entropy": round(entropy, 4),
        "n_major_indents": indents,
        "max_indent": round(max_indent, 4),
    }
    if elong >= 2.35 and (polygonal or rect >= 0.72) and sol >= 0.70:
        conf = min(0.95, 0.55 + 0.08 * (elong - 2.35) + 0.2 * rect)
        return {"family": "LAP_ELONGATED", "confidence": round(conf, 3), "reason": "high_elongation_axis_aligned", "signals": signals}
    if circ >= 0.78 and elong <= 1.40 and indents == 0 and rect < 0.88:
        return {
            "family": "ROUND_OVAL",
            "confidence": round(min(0.9, circ), 3),
            "reason": "high_circularity_low_elongation",
            "signals": signals,
        }
    if indents >= 3 or (indents >= 2 and sol < 0.88):
        conf = min(0.9, 0.55 + 0.1 * indents + (0.88 - sol))
        return {
            "family": "COMPOUND_IRREGULAR",
            "confidence": round(conf, 3),
            "reason": "multiple_indents_or_low_solidity",
            "signals": signals,
        }
    if polygonal and elong < 2.35:
        conf = min(0.93, 0.50 + 0.35 * (0.52 - entropy) + 0.4 * sharp)
        return {
            "family": "RECTANGULAR",
            "confidence": round(conf, 3),
            "reason": "low_angle_entropy_high_sharp_fraction",
            "signals": signals,
        }
    if curved:
        conf = min(0.92, 0.45 + 0.6 * (entropy - 0.60) + 0.4 * (0.24 - sharp))
        family = "KIDNEY_CURVED" if indents == 1 and 0.84 <= sol < 0.97 and max_indent >= 0.08 else "FREEFORM"
        return {
            "family": family,
            "confidence": round(conf, 3),
            "reason": "high_angle_entropy_low_sharp_fraction",
            "signals": signals,
        }
    if indents == 1 and sol < 0.93 and rect < 0.82:
        return {
            "family": "KIDNEY_CURVED",
            "confidence": 0.55,
            "reason": "single_indent_medium_solidity",
            "signals": signals,
        }
    if rect >= 0.80 and sol >= 0.88 and indents == 0 and elong < 2.35:
        return {
            "family": "RECTANGULAR",
            "confidence": round(min(0.8, rect), 3),
            "reason": "high_minarea_rectangularity",
            "signals": signals,
        }
    return {"family": "UNKNOWN", "confidence": 0.35, "reason": "mixed_or_weak_geometry", "signals": signals}


def classify_contour(points: Any) -> dict[str, Any]:
    metrics = scaled_geometry(points)
    result = classify_pool_shape_family(metrics)
    compact = None if metrics is None else {k: v for k, v in metrics.items() if k not in {"norm_xy", "shape_v2_descriptors", "hu_log"}}
    result["metrics"] = compact
    result["features"] = dict(result.get("signals") or {})
    if compact:
        for key in ("rectangularity", "solidity", "circularity", "elongation", "sharp_frac", "angle_entropy", "n_major_indents"):
            if key in compact:
                result["features"][key] = compact[key]
    return result


def contour_metrics_scaled(points: Any) -> dict[str, Any] | None:
    """Alias used by forensic dumps. Same as scaled_geometry."""
    return scaled_geometry(points)


def hard_reject(compat: str) -> bool:
    """Diagnostic A: drop only clearly incompatible families. UNKNOWN never rejects."""
    return str(compat) == INCOMPATIBLE


def compatibility(listing_family: str, candidate_family: str) -> str:
    """Coarse visual compatibility. UNKNOWN never rejects."""
    left = str(listing_family or "UNKNOWN")
    right = str(candidate_family or "UNKNOWN")
    if left not in FAMILIES:
        left = "UNKNOWN"
    if right not in FAMILIES:
        right = "UNKNOWN"
    if "UNKNOWN" in {left, right}:
        return NO_DECISION
    if left == right:
        return COMPATIBLE
    pairs = {tuple(sorted((left, right)))}
    partial_pairs = {
        tuple(sorted(("FREEFORM", "KIDNEY_CURVED"))),
        tuple(sorted(("FREEFORM", "COMPOUND_IRREGULAR"))),
        tuple(sorted(("KIDNEY_CURVED", "COMPOUND_IRREGULAR"))),
        tuple(sorted(("RECTANGULAR", "LAP_ELONGATED"))),
        tuple(sorted(("ROUND_OVAL", "KIDNEY_CURVED"))),
    }
    if pairs & partial_pairs:
        return PARTIAL
    incompatible_left = {
        "FREEFORM": {"RECTANGULAR", "LAP_ELONGATED", "ROUND_OVAL"},
        "KIDNEY_CURVED": {"RECTANGULAR", "LAP_ELONGATED"},
        "COMPOUND_IRREGULAR": {"RECTANGULAR", "LAP_ELONGATED", "ROUND_OVAL"},
        "LAP_ELONGATED": {"FREEFORM", "KIDNEY_CURVED", "ROUND_OVAL", "COMPOUND_IRREGULAR"},
        "RECTANGULAR": {"FREEFORM", "KIDNEY_CURVED", "COMPOUND_IRREGULAR"},
        "ROUND_OVAL": {"FREEFORM", "LAP_ELONGATED", "COMPOUND_IRREGULAR", "RECTANGULAR"},
    }
    if right in incompatible_left.get(left, set()):
        return INCOMPATIBLE
    return PARTIAL


def penalty_multiplier(compat: str) -> float:
    return float(PENALTY.get(compat, 1.0))


def adjusted_shape_v2(shape_v2: float | None, compat: str) -> float | None:
    if shape_v2 is None:
        return None
    return round(float(shape_v2) * penalty_multiplier(compat), 4)


def adjusted_total_score(
    frozen_total: float | None = None,
    frozen_shape_v2: float | None = None,
    compat: str = COMPATIBLE,
    *,
    shape_weight: float = 0.36,
) -> float:
    """Replace the frozen shape_v2 contribution. Other frozen contribs stay."""
    if frozen_total is None:
        return 0.0
    if frozen_shape_v2 is None:
        return round(float(frozen_total), 4)
    old_contrib = float(frozen_shape_v2) * shape_weight
    new_contrib = float(adjusted_shape_v2(frozen_shape_v2, compat) or 0.0) * shape_weight
    return round(float(frozen_total) - old_contrib + new_contrib, 4)


def decompose_shape_v2(listing_desc: Mapping[str, Any] | None, cand_desc: Mapping[str, Any] | None) -> dict[str, Any]:
    score, parts = shape_v2_similarity(listing_desc, cand_desc)
    used = {key: SHAPE_V2_WEIGHTS[key] for key, val in parts.items() if val is not None and key in SHAPE_V2_WEIGHTS}
    total_w = sum(used.values()) or 1.0
    terms = {key: (None if val is None else round(float(val), 4)) for key, val in parts.items()}
    contrib = {
        key: round(float(parts[key]) * used[key] / total_w, 4) for key in used
    }
    return {
        "shape_v2": score,
        "combined": score,
        "parts": terms,
        "terms": terms,
        "weights": dict(SHAPE_V2_WEIGHTS),
        "weighted_contrib": contrib,
        "contributions": contrib,
        "dominant_terms": sorted(contrib.items(), key=lambda item: -item[1])[:4],
    }


def stage_contours(points: Any) -> dict[str, list[list[float]] | None]:
    """Normalisation stages used by Shape v2 (pca_normalize = centre+rotate+scale+sign)."""
    xy = _as_xy(points)
    if xy is None:
        return {key: None for key in ("raw", "translated", "scale", "rotation", "resampled", "final")}
    centered = xy - xy.mean(axis=0)
    radii = np.linalg.norm(centered, axis=1)
    scale = centered / max(float(np.max(radii)), 1e-9)
    cov = np.cov(centered.T)
    rotated = centered
    if np.all(np.isfinite(cov)):
        eigvals, eigvecs = np.linalg.eigh(cov)
        axis = eigvecs[:, int(np.argmax(eigvals))]
        angle = math.atan2(axis[1], axis[0])
        cosine, sine = math.cos(-angle), math.sin(-angle)
        rot = np.array([[cosine, -sine], [sine, cosine]], dtype=np.float64)
        rotated = centered @ rot.T
    from backend.gis.estate_ags_matching.os_scoring_v2 import _resample

    resampled = _resample(xy, 64)
    final = pca_normalize(xy)
    return {
        "raw": xy.tolist(),
        "translated": centered.tolist(),
        "scale": scale.tolist(),
        "rotation": rotated.tolist(),
        "resampled": resampled.tolist(),
        "final": final.tolist(),
    }


def _unit_xy(points: Any) -> np.ndarray | None:
    xy = _as_xy(points)
    if xy is None:
        return None
    centered = xy - xy.mean(axis=0)
    scale = float(np.max(np.linalg.norm(centered, axis=1))) or 1.0
    return centered / scale


def _stage_chamfer(left: Any, right: Any, *, already_unit: bool = False) -> float | None:
    a = _as_xy(left)
    b = _as_xy(right)
    if a is None or b is None:
        return None
    if already_unit:
        return round(contour_chamfer_sim(a, b), 4)
    ua, ub = _unit_xy(a), _unit_xy(b)
    if ua is None or ub is None:
        return None
    return round(contour_chamfer_sim(ua, ub), 4)


def chamfer_at_stage(listing_points: Any, cand_points: Any) -> dict[str, float | None]:
    """Chamfer after each Shape v2 normalisation stage.

    Raw listing vs aerial contours live in different 0–1 image frames, so every
    pre-final stage is unit-scaled (translation+scale) before chamfer. The
    `final` stage uses pca_normalize output as Shape v2 does (rotation+scale+sign).
    """
    listing_stages = stage_contours(listing_points)
    cand_stages = stage_contours(cand_points)
    out: dict[str, float | None] = {}
    for key in listing_stages:
        already_unit = key in {"scale", "final"}
        out[key] = _stage_chamfer(listing_stages[key], cand_stages[key], already_unit=already_unit)
    return out


def pca_normalize_steps() -> dict[str, Any]:
    return {
        "applied": True,
        "steps": ["center", "pca_align_major_axis", "flip_heavier_half_to_+x", "scale_unit_max_radius"],
        "rotation_normalisation": True,
        "scale_normalisation": True,
        "resampling_before_comparison": "contour_descriptors resamples turning angles at 32 pts; Hybrid listing contour is already 64-pt; OS contour uses native vertices then pca_normalize",
        "chamfer_flips": ["identity", "x", "y", "xy"],
        "convexification": False,
    }
