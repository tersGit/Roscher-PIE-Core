"""Multi-image listing evidence fusion for Scoring v2.

Does not modify os_scoring_v2.py, OS v1, or production ranking.
No listing-id or stand-number rules. Incompatible views are clustered,
not averaged.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from backend.gis.estate_ags_matching.os_scoring_v2 import (
    contour_descriptors,
    spatial_v2_similarity,
)
from backend.gis.estate_ags_matching.os_v1_experimental_rank import is_high_conf
from backend.gis.estate_ags_matching.pool_geometry import (
    PoolGeometryFingerprint,
    _bgr_from_bytes,
    _ratio_sim,
    extract_pool_geometry,
    pool_mask,
)

SHAPE_SCENES = frozenset({"aerial", "pool_garden", "rear_elevation", "contextual"})
SPATIAL_SCENES = frozenset({"aerial", "contextual", "rear_elevation", "pool_garden"})
SKIP_SCENES = frozenset({"interior"})

SCENE_SHAPE_PRIOR = {
    "aerial": 1.0,
    "contextual": 0.78,
    "rear_elevation": 0.70,
    "pool_garden": 0.55,
    "front_elevation": 0.30,
    "driveway_access": 0.20,
}
SCENE_SPATIAL_PRIOR = {
    "aerial": 1.0,
    "contextual": 0.88,
    "rear_elevation": 0.72,
    "pool_garden": 0.40,
    "front_elevation": 0.25,
    "driveway_access": 0.15,
}


def _cv2():
    import cv2

    return cv2


def water_blob_count(image_bytes: bytes) -> int:
    cv2 = _cv2()
    bgr = _bgr_from_bytes(image_bytes)
    height, width = bgr.shape[:2]
    mask = pool_mask(bgr)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    min_area = max(24.0, 0.002 * width * height)
    return sum(1 for contour in contours if cv2.contourArea(contour) >= min_area)


def pool_roof_pixel_ratio(image_bytes: bytes) -> float | None:
    """Pool pixels / bright-roof pixels in the same frame. None if either is weak."""
    cv2 = _cv2()
    bgr = _bgr_from_bytes(image_bytes)
    height, width = bgr.shape[:2]
    pool = pool_mask(bgr)
    pool_px = float((pool > 0).sum())
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    threshold = float(np.percentile(gray, 74))
    roof = (gray >= threshold).astype(np.uint8)
    roof[pool > 0] = 0
    roof_px = float(roof.sum())
    frame = float(max(width * height, 1))
    if pool_px < 40 or roof_px < max(80.0, 0.04 * frame):
        return None
    pool_frac = pool_px / frame
    roof_frac = roof_px / frame
    # Close-up of water with little roof is not a pool/house scale observation.
    if pool_frac > 0.28 or roof_frac < 0.06:
        return None
    return round(pool_px / max(roof_px, 1.0), 4)


def shape_view_quality(fp: PoolGeometryFingerprint, scene: str) -> float:
    if not fp.present:
        return 0.0
    compact = float(fp.compactness or 0.0)
    aspect = float(fp.aspect_ratio or 1.0)
    rel = float(fp.relative_area or 0.0)
    prior = SCENE_SHAPE_PRIOR.get(scene, 0.15)
    # Severe perspective smear: very low compactness and stretched min-area rect.
    smeared = compact < 0.22 and aspect > 2.3
    planform = 0.12 if smeared else min(1.0, compact / 0.55)
    framed = 0.0
    if 0.015 <= rel <= 0.32:
        framed = 1.0
    elif rel > 0.32:
        framed = 0.35
    compound = 0.0
    if (fp.curved_section_count or 0) >= 1 and compact >= 0.28:
        compound = 1.0
    quality = 0.34 * prior + 0.36 * planform + 0.18 * framed + 0.12 * compound
    return round(min(1.0, quality), 4)


def spatial_view_quality(fp: PoolGeometryFingerprint, scene: str) -> float:
    if not fp.present or fp.house_centroid_x is None or fp.pool_to_house_dist is None:
        return 0.0
    prior = SCENE_SPATIAL_PRIOR.get(scene, 0.1)
    rel = float(fp.relative_area or 0.0)
    dist = float(fp.pool_to_house_dist)
    framed = 0.0
    if 0.012 <= rel <= 0.18:
        framed = 1.0
    elif rel <= 0.26:
        framed = 0.45
    dist_ok = 1.0 if 0.08 <= dist <= 0.75 else 0.25
    return round(min(1.0, 0.42 * prior + 0.33 * framed + 0.25 * dist_ok), 4)


def scale_view_quality(fp: PoolGeometryFingerprint, scene: str, ratio: float | None) -> float:
    if ratio is None or not fp.present:
        return 0.0
    prior = SCENE_SPATIAL_PRIOR.get(scene, 0.1)
    rel = float(fp.relative_area or 0.0)
    framed = 1.0 if 0.012 <= rel <= 0.20 else 0.2
    return round(min(1.0, 0.55 * prior + 0.45 * framed), 4)


def observe_listing_image(media_id: str, image_bytes: bytes, scene: str) -> dict[str, Any]:
    fp = extract_pool_geometry(image_bytes, media_id=media_id)
    n_blobs = water_blob_count(image_bytes) if scene not in SKIP_SCENES else 0
    ratio = pool_roof_pixel_ratio(image_bytes) if fp.present else None
    desc = contour_descriptors(fp.contour_normalized or fp.contour_image) if fp.present else None
    return {
        "media_id": media_id,
        "scene": scene,
        "pool_present": fp.present,
        "shape_class": fp.shape_class,
        "compactness": fp.compactness,
        "aspect_ratio": fp.aspect_ratio,
        "convexity": fp.convexity,
        "rectangularity": fp.rectangularity,
        "relative_area": fp.relative_area,
        "curved_section_count": fp.curved_section_count,
        "n_water_blobs": n_blobs,
        "pool_to_house_dist": fp.pool_to_house_dist,
        "pool_to_house_angle_deg": fp.pool_to_house_angle_deg,
        "pool_to_house_dx": fp.pool_to_house_dx,
        "pool_to_house_dy": fp.pool_to_house_dy,
        "house_visible": fp.house_centroid_x is not None,
        "pool_roof_ratio": ratio,
        "shape_quality": shape_view_quality(fp, scene),
        "spatial_quality": spatial_view_quality(fp, scene),
        "scale_quality": scale_view_quality(fp, scene, ratio),
        "fingerprint": fp,
        "descriptors": desc,
    }


def _compatible_shape(a: dict[str, Any], b: dict[str, Any]) -> bool:
    fp_a: PoolGeometryFingerprint = a["fingerprint"]
    fp_b: PoolGeometryFingerprint = b["fingerprint"]
    elong_ok = _ratio_sim(fp_a.aspect_ratio, fp_b.aspect_ratio)
    if elong_ok is None or elong_ok < 0.72:
        return False
    ca, cb = float(fp_a.compactness or 0), float(fp_b.compactness or 0)
    return abs(ca - cb) <= 0.18


def _pick_cluster(views: list[dict[str, Any]], quality_key: str, min_q: float) -> list[dict[str, Any]]:
    usable = [item for item in views if item[quality_key] >= min_q and item["pool_present"]]
    if not usable:
        return []
    usable = sorted(usable, key=lambda item: -item[quality_key])
    clusters: list[list[dict[str, Any]]] = []
    for item in usable:
        placed = False
        for cluster in clusters:
            if _compatible_shape(item, cluster[0]):
                cluster.append(item)
                placed = True
                break
        if not placed:
            clusters.append([item])
    return max(clusters, key=lambda cluster: sum(item[quality_key] for item in cluster))


def _weighted_median(pairs: list[tuple[float, float]]) -> float | None:
    if not pairs:
        return None
    pairs = sorted(pairs, key=lambda item: item[0])
    total = sum(weight for _val, weight in pairs) or 1.0
    acc = 0.0
    for val, weight in pairs:
        acc += weight
        if acc >= 0.5 * total:
            return float(val)
    return float(pairs[-1][0])


def fuse_listing_observations(observations: list[dict[str, Any]]) -> dict[str, Any]:
    """Consensus / highest-confidence fusion. Does not mean incompatible views."""
    shape_cluster = _pick_cluster(observations, "shape_quality", 0.32)
    if not shape_cluster:
        shape_cluster = sorted(
            [item for item in observations if item["pool_present"]],
            key=lambda item: -item["shape_quality"],
        )[:1]
    shape_best = shape_cluster[0] if shape_cluster else None

    spatial_usable = [
        item
        for item in observations
        if item["spatial_quality"] >= 0.35 and item["house_visible"] and item["pool_to_house_dist"]
    ]
    spatial_usable.sort(key=lambda item: -item["spatial_quality"])
    spatial_best = spatial_usable[0] if spatial_usable else None

    scale_usable = [item for item in observations if item["scale_quality"] >= 0.35 and item["pool_roof_ratio"]]
    scale_ratio = _weighted_median([(float(item["pool_roof_ratio"]), item["scale_quality"]) for item in scale_usable])

    fused_fp = None
    if shape_best is not None:
        src: PoolGeometryFingerprint = shape_best["fingerprint"]
        dist = angle = dx = dy = None
        if spatial_best is not None:
            sfp: PoolGeometryFingerprint = spatial_best["fingerprint"]
            dist = sfp.pool_to_house_dist
            angle = sfp.pool_to_house_angle_deg
            dx = sfp.pool_to_house_dx
            dy = sfp.pool_to_house_dy
        fused_fp = PoolGeometryFingerprint(
            present=True,
            unknown=False,
            shape_class=src.shape_class,
            aspect_ratio=src.aspect_ratio,
            orientation_deg=src.orientation_deg,
            compactness=src.compactness,
            rectangularity=src.rectangularity,
            convexity=src.convexity,
            curved_section_count=src.curved_section_count,
            relative_area=src.relative_area,
            centroid_x=src.centroid_x,
            centroid_y=src.centroid_y,
            house_centroid_x=None if spatial_best is None else spatial_best["fingerprint"].house_centroid_x,
            house_centroid_y=None if spatial_best is None else spatial_best["fingerprint"].house_centroid_y,
            pool_to_house_dx=dx,
            pool_to_house_dy=dy,
            pool_to_house_dist=dist,
            pool_to_house_angle_deg=angle,
            contour_normalized=src.contour_normalized,
            contour_image=src.contour_image,
            evidence_media_id=src.evidence_media_id,
            notes=[
                "multi_image_fusion",
                f"shape_from={shape_best['media_id']}",
                f"spatial_from={None if spatial_best is None else spatial_best['media_id']}",
                f"shape_cluster_n={len(shape_cluster)}",
            ],
        )

    return {
        "fused_fingerprint": fused_fp,
        "fused_shape_descriptors": None if shape_best is None else shape_best["descriptors"],
        "fused_pool_roof_ratio": scale_ratio,
        "shape_source": None if shape_best is None else shape_best["media_id"],
        "spatial_source": None if spatial_best is None else spatial_best["media_id"],
        "scale_sources": [item["media_id"] for item in scale_usable],
        "shape_cluster": [item["media_id"] for item in shape_cluster],
        "n_pool_present": sum(1 for item in observations if item["pool_present"]),
        "n_observations": len(observations),
    }


def spatial_v2_with_scale(
    listing: PoolGeometryFingerprint,
    listing_pool_roof_ratio: float | None,
    seg: dict[str, Any],
) -> tuple[float | None, dict[str, float | None]]:
    score, parts = spatial_v2_similarity(listing, seg)
    pool = seg.get("pool") or {}
    building = seg.get("building") or {}
    cand_ratio = None
    if is_high_conf(pool) and is_high_conf(building):
        pool_m2 = (pool.get("geometry") or {}).get("area_m2")
        bldg_m2 = (building.get("geometry") or {}).get("area_m2")
        if pool_m2 and bldg_m2 and bldg_m2 > 1:
            cand_ratio = float(pool_m2) / float(bldg_m2)
    parts["area_ratio"] = _ratio_sim(listing_pool_roof_ratio, cand_ratio)
    used = [val for key, val in parts.items() if key in {"sector", "centroid_dist", "area_ratio"} and val is not None]
    if not used:
        return None, parts
    return round(float(sum(used) / len(used)), 4), parts


def observation_public(item: dict[str, Any]) -> dict[str, Any]:
    skip = {"fingerprint", "descriptors"}
    out = {key: val for key, val in item.items() if key not in skip}
    desc = item.get("descriptors")
    if desc:
        out["descriptors"] = {key: val for key, val in desc.items() if key != "norm_xy"}
    return out
