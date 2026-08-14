"""Scoring v2 — experimental OS comparison, not production EvidenceFusion.

Uses frozen Object Segmentation v1 JSON and the frozen listing pool
fingerprint. Does not modify ranking weights in combined_score, does not
retouch OS v1, and contains no listing-id or stand-number rules.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from backend.gis.estate_ags_matching.os_v1_experimental_rank import is_high_conf
from backend.gis.estate_ags_matching.pool_geometry import (
    PoolGeometryFingerprint,
    _angle_sim,
    _ratio_sim,
)

# Image convention matches OS v1: +x east, +y south.
SECTORS = ("E", "SE", "S", "SW", "W", "NW", "N", "NE")

# Designed-out driveway (no listing-side spatial in the frozen fingerprint)
# is omitted from weights rather than 0.5-filled, so it cannot move ranks.
V2_WEIGHTS_NO_BUILDING = {
    "pool_presence": 0.14,
    "shape_v2": 0.36,
    "spatial_v2": 0.22,
    "aerial": 0.12,
    "exterior": 0.06,
    "gis": 0.03,
    "stand_size": 0.07,
}

V2_WEIGHTS_BUILDING_COARSE = {
    "pool_presence": 0.13,
    "shape_v2": 0.32,
    "spatial_v2": 0.20,
    "building_coarse": 0.08,
    "aerial": 0.12,
    "exterior": 0.06,
    "gis": 0.03,
    "stand_size": 0.06,
}

OS_KEYS_NO_BUILDING = ("pool_presence", "shape_v2", "spatial_v2")
OS_KEYS_BUILDING = ("pool_presence", "shape_v2", "spatial_v2", "building_coarse")


def _cv2():
    import cv2

    return cv2


def _as_xy(points: Any) -> np.ndarray | None:
    if points is None:
        return None
    array = np.asarray(points, dtype=np.float64)
    if array.ndim != 2 or array.shape[0] < 5 or array.shape[1] < 2:
        return None
    return array[:, :2]


def pca_normalize(points: np.ndarray) -> np.ndarray:
    """Centre, align major axis, scale to unit max radius. Rotation/scale invariant."""
    centered = points - points.mean(axis=0)
    cov = np.cov(centered.T)
    if not np.all(np.isfinite(cov)):
        return centered
    eigvals, eigvecs = np.linalg.eigh(cov)
    axis = eigvecs[:, int(np.argmax(eigvals))]
    angle = math.atan2(axis[1], axis[0])
    cosine, sine = math.cos(-angle), math.sin(-angle)
    rot = np.array([[cosine, -sine], [sine, cosine]], dtype=np.float64)
    aligned = centered @ rot.T
    # Flip so the heavier half is +x (sign invariant without a class label).
    if float(aligned[:, 0].mean()) < 0:
        aligned[:, 0] *= -1
    if float(np.median(aligned[:, 1])) < 0:
        aligned[:, 1] *= -1
    scale = float(np.max(np.linalg.norm(aligned, axis=1)))
    if scale < 1e-9:
        return aligned
    return aligned / scale


def _to_cv_contour(norm_xy: np.ndarray, radius: float = 200.0) -> np.ndarray:
    scaled = np.round(norm_xy * radius).astype(np.int32)
    return scaled.reshape(-1, 1, 2)


def contour_descriptors(points: Any) -> dict[str, float | int | list[float]] | None:
    """Scalar + distribution descriptors from a raw contour. No semantic class."""
    xy = _as_xy(points)
    if xy is None:
        return None
    cv2 = _cv2()
    norm = pca_normalize(xy)
    contour = _to_cv_contour(norm)
    area = float(cv2.contourArea(contour))
    peri = float(cv2.arcLength(contour, True))
    if area < 1.0 or peri < 8.0:
        return None
    circularity = float(4.0 * math.pi * area / max(peri * peri, 1e-6))
    hull = cv2.convexHull(contour)
    hull_area = max(float(cv2.contourArea(hull)), 1e-6)
    solidity = float(area / hull_area)
    (_cx, _cy), (rw, rh), _ang = cv2.minAreaRect(contour.astype(np.float32))
    elongation = float(max(rw, rh) / max(min(rw, rh), 1e-3))
    n_corners = int(len(cv2.approxPolyDP(contour.astype(np.float32), 0.03 * peri, True)))
    depths: list[float] = []
    hull_idx = cv2.convexHull(contour, returnPoints=False)
    if hull_idx is not None and len(hull_idx) >= 3 and len(contour) >= 4:
        try:
            defects = cv2.convexityDefects(contour, hull_idx)
        except cv2.error:
            defects = None
        if defects is not None:
            for item in np.asarray(defects).reshape(-1, 4):
                rel = float(item[3]) / 256.0 / max(math.sqrt(area), 1.0)
                depths.append(rel)
    major_indent = sum(1 for depth in depths if depth >= 0.08)
    max_indent = max(depths) if depths else 0.0
    # Turning-angle distribution on 32 arc-length samples of the normalised contour.
    samples = _resample(norm, 32)
    prev = np.roll(samples, 1, axis=0)
    nxt = np.roll(samples, -1, axis=0)
    v1 = samples - prev
    v2 = nxt - samples
    ang1 = np.arctan2(v1[:, 1], v1[:, 0])
    ang2 = np.arctan2(v2[:, 1], v2[:, 0])
    turn = (ang2 - ang1 + math.pi) % (2.0 * math.pi) - math.pi
    sharp_frac = float(np.mean(np.abs(turn) > math.radians(40.0)))
    turn_std = float(np.std(np.abs(turn)))
    radii = np.linalg.norm(norm, axis=1)
    radial_cv = float(np.std(radii) / max(float(np.mean(radii)), 1e-6))
    reflected = norm.copy()
    reflected[:, 1] *= -1
    chamfer = 0.0
    for point in norm:
        chamfer += float(np.min(np.linalg.norm(reflected - point, axis=1)))
    symmetry = max(0.0, 1.0 - (chamfer / max(len(norm), 1)) / 0.35)
    hu = cv2.HuMoments(cv2.moments(contour)).flatten()
    hu_log = [-math.copysign(math.log10(abs(float(val)) + 1e-30), float(val)) for val in hu[:4]]
    return {
        "circularity": round(circularity, 4),
        "solidity": round(solidity, 4),
        "elongation": round(elongation, 4),
        "n_corners": n_corners,
        "n_major_indents": major_indent,
        "max_indent": round(float(max_indent), 4),
        "sharp_frac": round(sharp_frac, 4),
        "turn_std": round(turn_std, 4),
        "radial_cv": round(radial_cv, 4),
        "symmetry": round(symmetry, 4),
        "hu_log": [round(val, 4) for val in hu_log],
        "norm_xy": norm.tolist(),
    }


def _resample(points: np.ndarray, count: int) -> np.ndarray:
    closed = np.vstack([points, points[0]])
    seglen = np.hypot(np.diff(closed[:, 0]), np.diff(closed[:, 1]))
    cum = np.concatenate([[0.0], np.cumsum(seglen)])
    total = float(cum[-1]) or 1.0
    out = np.zeros((count, 2), dtype=np.float64)
    for i in range(count):
        target = (i / count) * total
        j = int(np.searchsorted(cum, target) - 1)
        j = min(max(j, 0), len(points) - 1)
        out[i] = points[j]
    return out


def _unit_sim(left: float | None, right: float | None, scale: float) -> float | None:
    if left is None or right is None:
        return None
    return max(0.0, 1.0 - abs(float(left) - float(right)) / max(scale, 1e-6))


def _hu_sim(left: list[float] | None, right: list[float] | None) -> float | None:
    if not left or not right:
        return None
    dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(left, right)))
    return float(1.0 / (1.0 + dist))


def contour_chamfer_sim(listing_norm: np.ndarray, cand_norm: np.ndarray) -> float:
    """Min mean nearest-neighbour distance after 0/180° flips. Scale-free."""

    def _mean_nn(a: np.ndarray, b: np.ndarray) -> float:
        total = 0.0
        for point in a:
            total += float(np.min(np.linalg.norm(b - point, axis=1)))
        return total / max(len(a), 1)

    best = 1e9
    for flip in (np.array([1.0, 1.0]), np.array([-1.0, 1.0]), np.array([1.0, -1.0]), np.array([-1.0, -1.0])):
        flipped = cand_norm * flip
        dist = 0.5 * (_mean_nn(listing_norm, flipped) + _mean_nn(flipped, listing_norm))
        best = min(best, dist)
    return float(1.0 / (1.0 + 4.0 * best))


def shape_v2_similarity(
    listing_desc: dict[str, Any] | None,
    cand_desc: dict[str, Any] | None,
) -> tuple[float | None, dict[str, float | None]]:
    if not listing_desc or not cand_desc:
        return None, {}
    parts: dict[str, float | None] = {
        "elongation": _ratio_sim(listing_desc.get("elongation"), cand_desc.get("elongation")),
        "solidity": _unit_sim(listing_desc.get("solidity"), cand_desc.get("solidity"), 0.45),
        "circularity": _unit_sim(listing_desc.get("circularity"), cand_desc.get("circularity"), 0.55),
        "n_corners": _unit_sim(float(listing_desc.get("n_corners") or 0), float(cand_desc.get("n_corners") or 0), 8.0),
        "n_indents": _unit_sim(
            float(listing_desc.get("n_major_indents") or 0),
            float(cand_desc.get("n_major_indents") or 0),
            4.0,
        ),
        "max_indent": _unit_sim(listing_desc.get("max_indent"), cand_desc.get("max_indent"), 0.5),
        "sharp_frac": _unit_sim(listing_desc.get("sharp_frac"), cand_desc.get("sharp_frac"), 0.45),
        "radial_cv": _unit_sim(listing_desc.get("radial_cv"), cand_desc.get("radial_cv"), 0.4),
        "hu": _hu_sim(listing_desc.get("hu_log"), cand_desc.get("hu_log")),
        "chamfer": None,
    }
    listing_xy = np.asarray(listing_desc.get("norm_xy") or [], dtype=np.float64)
    cand_xy = np.asarray(cand_desc.get("norm_xy") or [], dtype=np.float64)
    if listing_xy.ndim == 2 and cand_xy.ndim == 2 and len(listing_xy) >= 5 and len(cand_xy) >= 5:
        parts["chamfer"] = contour_chamfer_sim(listing_xy, cand_xy)
    weights = {
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
    used = {key: weights[key] for key, val in parts.items() if val is not None and key in weights}
    total = sum(used.values())
    if total <= 0:
        return None, parts
    score = sum(float(parts[key]) * used[key] for key in used) / total
    return round(float(score), 4), parts


def sector_index(angle_deg: float | None) -> int | None:
    if angle_deg is None:
        return None
    return int(((float(angle_deg) + 22.5) % 360.0) // 45.0)


def sector_similarity(left_deg: float | None, right_deg: float | None) -> float | None:
    a = sector_index(left_deg)
    b = sector_index(right_deg)
    if a is None or b is None:
        return None
    delta = min((a - b) % 8, (b - a) % 8)
    return (1.0, 0.65, 0.25, 0.05, 0.0)[min(int(delta), 4)]


def _angle_from_dx_dy(dx: float | None, dy: float | None) -> float | None:
    if dx is None or dy is None:
        return None
    if abs(dx) < 1e-9 and abs(dy) < 1e-9:
        return None
    return float(math.degrees(math.atan2(dy, dx)))


def nearest_edge_norm(
    pool_contour: Any,
    building_contour: Any,
    building_area_m2: float | None,
) -> float | None:
    """Nearest pool-vertex to building-vertex distance / sqrt(building area)."""
    pool = _as_xy(pool_contour)
    building = _as_xy(building_contour)
    if pool is None or building is None:
        return None
    # Contours are in image-normalised [0,1]; convert to a relative length.
    min_d = 1e9
    for point in pool[:: max(1, len(pool) // 24)]:
        min_d = min(min_d, float(np.min(np.linalg.norm(building - point, axis=1))))
    if min_d > 1e8:
        return None
    char = math.sqrt(max(float(building_area_m2 or 0.0), 1.0))
    # Image-normalised distance has no metres; keep dimensionless vs building bbox.
    b_span = float(np.max(np.linalg.norm(building - building.mean(axis=0), axis=1))) or 1.0
    return round(min_d / b_span, 4) if char else None


def spatial_v2_similarity(
    listing: PoolGeometryFingerprint,
    seg: dict[str, Any],
) -> tuple[float | None, dict[str, float | None]]:
    if not listing.present:
        return None, {}
    pool = seg.get("pool") or {}
    building = seg.get("building") or {}
    if not is_high_conf(pool) or not is_high_conf(building):
        return None, {}
    rel = ((seg.get("spatial") or {}).get("relationships") or {}).get("pool_house") or {}
    cand_angle = rel.get("angle_deg")
    if cand_angle is None:
        cand_angle = _angle_from_dx_dy(rel.get("dx"), rel.get("dy"))
    listing_angle = listing.pool_to_house_angle_deg
    if listing_angle is None:
        listing_angle = _angle_from_dx_dy(listing.pool_to_house_dx, listing.pool_to_house_dy)
    parts: dict[str, float | None] = {
        "sector": sector_similarity(listing_angle, cand_angle),
        "centroid_dist": _ratio_sim(listing.pool_to_house_dist, rel.get("dist")),
        "dist_over_building": None,
        "nearest_edge": None,
        "axis_rel": None,
        "area_ratio": None,
    }
    # Listing fingerprint has no house metres / house contour / house orientation,
    # so building-normalised distance, edge distance, relative long-axis, and
    # pool/building area cannot be compared across views. Record candidate-only
    # values for the report; they do not enter the score.
    used = {key: val for key, val in (("sector", parts["sector"]), ("centroid_dist", parts["centroid_dist"])) if val is not None}
    if not used:
        return None, parts
    score = float(sum(used.values()) / len(used))
    return round(score, 4), parts


def building_coarse_similarity(seg: dict[str, Any]) -> float | None:
    """Presence-only. Does not compare listing oblique roof fraction to nadir area."""
    if is_high_conf(seg.get("building")):
        return 0.7
    return None


def driveway_spatial_similarity(
    listing_driveway_side: str | None,
    listing_has_driveway: bool,
    seg: dict[str, Any],
) -> float | None:
    """Only when a listing-side spatial relation exists. Else None (neutral)."""
    if not listing_has_driveway or not listing_driveway_side:
        return None
    driveway = seg.get("driveway") or {}
    if not is_high_conf(driveway):
        return None
    rel = ((seg.get("spatial") or {}).get("relationships") or {}).get("driveway_house") or {}
    side = (rel.get("driveway_side") or "").lower()
    if not side or side == "unknown":
        return None
    listing_side = listing_driveway_side.lower()
    if side == listing_side:
        return 0.9
    opposite = {"north": "south", "south": "north", "east": "west", "west": "east"}
    if opposite.get(listing_side) == side:
        return 0.25
    return 0.55


def listing_shape_descriptors(listing: PoolGeometryFingerprint) -> dict[str, Any] | None:
    # Prefer major-axis-normalised consensus contour; it is the frozen listing evidence.
    return contour_descriptors(listing.contour_normalized or listing.contour_image)


def v2_object_features(
    listing: PoolGeometryFingerprint,
    seg: dict[str, Any],
    *,
    listing_shape: dict[str, Any] | None,
    listing_has_driveway: bool = False,
    listing_driveway_side: str | None = None,
    include_building_coarse: bool = False,
) -> dict[str, float | None]:
    feats: dict[str, float | None] = {
        "pool_presence": None,
        "shape_v2": None,
        "spatial_v2": None,
        "building_coarse": None,
        "driveway": None,
    }
    pool = seg.get("pool") or {}
    if listing.present and is_high_conf(pool):
        feats["pool_presence"] = 1.0
        cand_desc = contour_descriptors((pool.get("contour") or (pool.get("geometry") or {}).get("contour_image")))
        shape_score, _parts = shape_v2_similarity(listing_shape, cand_desc)
        feats["shape_v2"] = shape_score
        spatial_score, _spatial_parts = spatial_v2_similarity(listing, seg)
        feats["spatial_v2"] = spatial_score
    if include_building_coarse:
        feats["building_coarse"] = building_coarse_similarity(seg)
    feats["driveway"] = driveway_spatial_similarity(listing_driveway_side, listing_has_driveway, seg)
    return feats


def evidence_coverage(values: dict[str, float | None], os_keys: tuple[str, ...]) -> float:
    if not os_keys:
        return 0.0
    return float(sum(1 for key in os_keys if values.get(key) is not None) / len(os_keys))


def score_v2(
    os_feats: dict[str, float | None],
    *,
    aerial: float | None,
    exterior: float | None,
    stand_size: float,
    weights: dict[str, float],
    os_keys: tuple[str, ...],
    missing: str = "neutral",
    fill: float = 0.5,
) -> tuple[float, dict[str, float], float, float]:
    """Always keep designed weights in play. missing='neutral' or 'coverage'."""
    values = {
        **os_feats,
        "aerial": aerial,
        "exterior": exterior,
        "gis": 0.5,
        "stand_size": stand_size or 0.0,
    }
    filled = {}
    for key, weight in weights.items():
        if weight <= 0:
            continue
        val = values.get(key)
        filled[key] = fill if val is None else float(val)
    total_w = sum(weights[key] for key in filled)
    contrib = {key: filled[key] * weights[key] / total_w for key in filled}
    raw = float(sum(contrib.values()))
    coverage = evidence_coverage(os_feats, os_keys)
    factor = 1.0
    if missing == "coverage":
        factor = 0.5 + 0.5 * coverage
        raw *= factor
    contrib = {key: round(val, 4) for key, val in contrib.items()}
    return round(raw, 4), contrib, round(coverage, 4), round(factor, 4)


def candidate_spatial_record(seg: dict[str, Any]) -> dict[str, Any]:
    """Candidate-only geometry for the report (not all of it is scored)."""
    pool = seg.get("pool") or {}
    building = seg.get("building") or {}
    rel = ((seg.get("spatial") or {}).get("relationships") or {}).get("pool_house") or {}
    pool_geom = pool.get("geometry") or {}
    bldg_geom = building.get("geometry") or {}
    pool_m2 = pool_geom.get("area_m2")
    bldg_m2 = bldg_geom.get("area_m2")
    dist_m = rel.get("distance_m")
    dist_over = None
    if dist_m and bldg_m2 and bldg_m2 > 1:
        dist_over = round(float(dist_m) / math.sqrt(float(bldg_m2)), 4)
    area_ratio = None
    if pool_m2 and bldg_m2 and bldg_m2 > 1:
        area_ratio = round(float(pool_m2) / float(bldg_m2), 4)
    axis_rel = _angle_sim(pool_geom.get("orientation_deg"), bldg_geom.get("orientation_deg"))
    edge = nearest_edge_norm(pool.get("contour"), building.get("contour"), bldg_m2)
    return {
        "pool_status": pool.get("status"),
        "building_status": building.get("status"),
        "driveway_status": (seg.get("driveway") or {}).get("status"),
        "direction": rel.get("direction"),
        "angle_deg": rel.get("angle_deg"),
        "parcel_dist": rel.get("dist"),
        "distance_m": dist_m,
        "dist_over_building": dist_over,
        "area_ratio": area_ratio,
        "axis_rel": None if axis_rel is None else round(axis_rel, 4),
        "nearest_edge_norm": edge,
        "driveway_side": (((seg.get("spatial") or {}).get("relationships") or {}).get("driveway_house") or {}).get(
            "driveway_side"
        ),
        "high_conf_pool": is_high_conf(pool),
        "high_conf_building": is_high_conf(building),
        "high_conf_driveway": is_high_conf(seg.get("driveway")),
    }
