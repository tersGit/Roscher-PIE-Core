"""Experimental ranking terms from Object Segmentation v1.

Not wired into production EvidenceFusion. REJECTED/UNKNOWN objects are
skipped (None) — they are never positive evidence and they do not apply
the listing-has-pool-candidate-has-none penalty.
"""

from __future__ import annotations

from typing import Any

from backend.gis.estate_ags_matching.pool_geometry import (
    PoolGeometryFingerprint,
    _angle_sim,
    _ratio_sim,
    _vector_sim,
)

HIGH_CONF = frozenset({"CONFIRMED", "PROBABLE"})

SHAPE_ALIASES = {
    "irregular": {"irregular", "kidney_or_curved"},
    "kidney_or_curved": {"irregular", "kidney_or_curved", "rounded"},
    "rounded": {"rounded", "kidney_or_curved"},
    "rectangular": {"rectangular", "elongated_rectangular"},
    "elongated_rectangular": {"elongated_rectangular", "rectangular"},
}

# Hybrid EvidenceFusion: OS object terms replace blob pool/roof/driveway.
# CLIP / GIS / stand-size stay on the same scale as the frozen matcher.
OS_WEIGHTS = {
    "pool_presence": 0.10,
    "pool_shape": 0.10,
    "pool_contour": 0.16,
    "pool_area": 0.08,
    "pool_house_dist": 0.10,
    "pool_house_position": 0.12,
    "building_footprint": 0.10,
    "driveway": 0.05,
    "aerial": 0.14,
    "video": 0.08,
    "exterior": 0.07,
    "gis": 0.02,
    "stand_size": 0.05,
}

PURE_OS_WEIGHTS = {
    "pool_presence": 0.14,
    "pool_shape": 0.14,
    "pool_contour": 0.22,
    "pool_area": 0.12,
    "pool_house_dist": 0.12,
    "pool_house_position": 0.14,
    "building_footprint": 0.08,
    "driveway": 0.04,
}


def is_high_conf(obj: dict | None) -> bool:
    if not obj:
        return False
    geom = obj.get("geometry") or {}
    return obj.get("status") in HIGH_CONF and bool(geom.get("present"))


def _mean(parts: list[float | None]) -> float | None:
    usable = [float(item) for item in parts if item is not None]
    if not usable:
        return None
    return float(sum(usable) / len(usable))


def _shape_sim(listing_shape: str | None, cand_shape: str | None) -> float | None:
    if not listing_shape or not cand_shape or "unknown" in {listing_shape, cand_shape}:
        return None
    if listing_shape == cand_shape:
        return 1.0
    if cand_shape in SHAPE_ALIASES.get(listing_shape, set()):
        return 0.75
    return 0.35


def os_object_features(
    listing_pool: PoolGeometryFingerprint,
    seg: dict[str, Any],
    *,
    listing_roof_area_frac: float | None = None,
    listing_roof_orientation_deg: float | None = None,
    listing_roof_aspect: float | None = None,
    listing_has_driveway: bool = False,
) -> dict[str, float | None]:
    """Return per-feature similarities. None = unused (no penalty)."""
    feats: dict[str, float | None] = {
        "pool_presence": None,
        "pool_shape": None,
        "pool_contour": None,
        "pool_area": None,
        "pool_house_dist": None,
        "pool_house_position": None,
        "building_footprint": None,
        "driveway": None,
    }
    pool = seg.get("pool") or {}
    building = seg.get("building") or {}
    driveway = seg.get("driveway") or {}
    spatial = seg.get("spatial") or {}

    if listing_pool.present and is_high_conf(pool):
        geom = pool.get("geometry") or {}
        feats["pool_presence"] = 1.0
        feats["pool_shape"] = _shape_sim(listing_pool.shape_class, geom.get("shape"))
        feats["pool_contour"] = _mean(
            [
                _ratio_sim(listing_pool.aspect_ratio, geom.get("aspect_ratio")),
                _angle_sim(listing_pool.orientation_deg, geom.get("orientation_deg")),
                _ratio_sim(listing_pool.compactness, geom.get("compactness")),
                _ratio_sim(listing_pool.rectangularity, geom.get("rectangularity")),
                _ratio_sim(listing_pool.convexity, geom.get("convexity")),
            ]
        )
        house_m2 = (building.get("geometry") or {}).get("area_m2") if is_high_conf(building) else None
        pool_m2 = geom.get("area_m2")
        listing_ratio = None
        if listing_pool.relative_area and listing_pool.relative_area < 0.9:
            listing_ratio = listing_pool.relative_area / max(1.0 - listing_pool.relative_area, 1e-3)
        cand_ratio = None
        if pool_m2 and house_m2 and house_m2 > 1:
            cand_ratio = float(pool_m2) / float(house_m2)
        feats["pool_area"] = _ratio_sim(listing_ratio, cand_ratio)
        rel = (spatial.get("relationships") or {}).get("pool_house") or {}
        feats["pool_house_dist"] = _ratio_sim(listing_pool.pool_to_house_dist, rel.get("dist"))
        feats["pool_house_position"] = _vector_sim(
            listing_pool.pool_to_house_dx,
            listing_pool.pool_to_house_dy,
            rel.get("dx"),
            rel.get("dy"),
        )

    if is_high_conf(building):
        geom = building.get("geometry") or {}
        feats["building_footprint"] = _mean(
            [
                _ratio_sim(listing_roof_area_frac, geom.get("relative_area")),
                _angle_sim(listing_roof_orientation_deg, geom.get("orientation_deg")),
                _ratio_sim(listing_roof_aspect, geom.get("aspect_ratio")),
            ]
        )

    if listing_has_driveway and is_high_conf(driveway):
        feats["driveway"] = 0.85

    return feats


def weighted_score(values: dict[str, float | None], weights: dict[str, float]) -> tuple[float, dict[str, float]]:
    used = {key: weights[key] for key in weights if values.get(key) is not None and weights[key] > 0}
    total_w = sum(used.values())
    if total_w <= 0:
        return 0.0, {}
    contrib = {key: float(values[key]) * used[key] / total_w for key in used}
    return round(float(sum(contrib.values())), 4), {key: round(val, 4) for key, val in contrib.items()}


def experimental_hybrid_score(
    os_feats: dict[str, float | None],
    *,
    aerial: float | None,
    video: float | None,
    exterior: float | None,
    stand_size: float,
) -> tuple[float, dict[str, float]]:
    values = {
        **os_feats,
        "aerial": aerial,
        "video": video,
        "exterior": exterior,
        "gis": 0.5,
        "stand_size": stand_size or 0.0,
    }
    return weighted_score(values, OS_WEIGHTS)


def experimental_pure_os_score(os_feats: dict[str, float | None]) -> tuple[float, dict[str, float]]:
    return weighted_score(os_feats, PURE_OS_WEIGHTS)
