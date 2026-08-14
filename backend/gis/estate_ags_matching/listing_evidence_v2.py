"""Listing Evidence v2 — viewpoint-compatible pool evidence, before scoring.

Does not modify production ranking, Scoring v2 weights, OS v1, native15
fingerprints, or the PR #7 multi-image fusion module.

No listing-id or stand-number rules. Evidence is kept in separate viewpoint
channels and is not collapsed into one fused geometry fingerprint.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from backend.gis.estate_ags_matching.os_scoring_v2 import contour_descriptors
from backend.gis.estate_ags_matching.pool_geometry import (
    PoolGeometryFingerprint,
    _bgr_from_bytes,
    _normalize_contour,
    _resample_contour,
    _roof_centroid,
    _shape_class,
)

VIEWPOINT_KEYS = (
    "aerial_near_nadir",
    "elevated_exterior",
    "ground_level_exterior",
    "pool_overview",
    "pool_closeup",
    "interior",
    "garden_only",
    "unusable_ambiguous",
)

VIEWPOINT_LABELS = (
    "aerial drone photograph looking straight down at house roofs gardens and a swimming pool",
    "elevated exterior photo of a house backyard taken from a second storey looking down toward a garden",
    "ground-level photo of a house exterior facade driveway garage or garden taken from standing height",
    "wide photograph showing a full swimming pool in a backyard garden with the house visible behind it",
    "close-up photograph of swimming pool water, pool tiles, or a jacuzzi filling most of the foreground",
    "interior photo of a room with carpet, furniture, ceiling, and windows taken from inside a house",
    "garden lawn plants and trees with little or no house wall or swimming pool visible",
    "headshot portrait of a person smiling at the camera, not a property photo",
)

SPATIAL_VIEWPOINTS = frozenset(
    {"aerial_near_nadir", "elevated_exterior", "ground_level_exterior", "pool_overview"}
)
SHAPE_VIEWPOINTS = frozenset(
    {"aerial_near_nadir", "elevated_exterior", "pool_overview", "ground_level_exterior"}
)
SCALE_VIEWPOINTS = frozenset({"aerial_near_nadir", "elevated_exterior"})
BLOCKED_SPATIAL = frozenset({"interior", "pool_closeup", "unusable_ambiguous", "garden_only"})

# Contour quality thresholds — generic, frozen before seeing estate ranks.
MIN_COMPACTNESS = 0.22
MIN_GOOD_COMPACTNESS = 0.30
MAX_FRAME_COVERAGE = 0.40
MAX_EDGE_CLIP = 0.12
MAX_COMPLEXITY_INDENTS = 3
MIN_WATER_CONFIDENCE = 0.22
MIN_COMPONENT_AREA_FRAC = 0.0018
MAX_COMPONENT_AREA_FRAC = 0.38


def _cv2():
    import cv2

    return cv2


@dataclass
class WaterComponent:
    contour: np.ndarray
    area: float
    compactness: float
    convexity: float
    relative_area: float
    centroid_xy: tuple[float, float]
    aspect_ratio: float
    rectangularity: float
    n_approx: int
    edge_clip: float
    water_confidence: float
    grass_adjacency: float
    cyan_frac: float
    dark_frac: float
    quality: float
    descriptors: dict[str, Any] | None
    contour_image: list[list[float]]
    contour_normalized: list[list[float]]
    shape_class: str


@dataclass
class FrameEvidence:
    media_id: str
    viewpoint: str
    viewpoint_scores: dict[str, float]
    pool_detected: bool
    pool_overview_eligible: bool
    spatial_eligible: bool
    scale_eligible: bool
    aerial_eligible: bool
    contour_quality: float
    n_components: int
    components: list[dict[str, Any]] = field(default_factory=list)
    dominant: dict[str, Any] | None = None
    secondary: dict[str, Any] | None = None
    compound: dict[str, Any] | None = None
    house_visible: bool = False
    pool_to_house_dist: float | None = None
    pool_to_house_angle_deg: float | None = None
    pool_to_house_dx: float | None = None
    pool_to_house_dy: float | None = None
    pool_roof_ratio: float | None = None
    notes: list[str] = field(default_factory=list)
    fingerprint: PoolGeometryFingerprint | None = None


def classify_viewpoint(
    bgr: np.ndarray,
    *,
    clip_scores: dict[str, float] | None = None,
    grass_frac: float | None = None,
    n_water_components: int = 0,
    dominant_cy: float | None = None,
    dominant_rel: float | None = None,
) -> tuple[str, dict[str, float]]:
    """CLIP + geometric overrides. No listing-id rules."""
    scores = dict(clip_scores or {})
    if not scores:
        scores = {key: 0.0 for key in VIEWPOINT_KEYS}
    ranked = sorted(VIEWPOINT_KEYS, key=lambda key: -scores.get(key, 0.0))
    label = ranked[0] if ranked else "unusable_ambiguous"
    gfrac = 0.0 if grass_frac is None else float(grass_frac)

    if scores.get("unusable_ambiguous", 0.0) >= 0.45:
        label = "unusable_ambiguous"
    elif scores.get("interior", 0.0) >= 0.40 and gfrac < 0.10:
        label = "interior"
    elif scores.get("interior", 0.0) >= 0.28 and gfrac < 0.06 and scores.get("pool_overview", 0.0) < 0.20:
        label = "interior"
    elif label == "garden_only" and scores.get("unusable_ambiguous", 0.0) >= 0.12 and gfrac < 0.20:
        # Green graphic behind a headshot is not a garden photograph.
        if scores.get("unusable_ambiguous", 0.0) >= 0.12 and scores.get("pool_overview", 0.0) < 0.08:
            if _portrait_cue(bgr):
                label = "unusable_ambiguous"

    if label == "pool_overview":
        close = False
        if n_water_components <= 1 and gfrac < 0.22 and dominant_cy is not None and dominant_cy >= 0.72:
            if (dominant_rel or 0.0) >= 0.03:
                close = True
        if scores.get("pool_closeup", 0.0) >= 0.18 and gfrac < 0.20 and n_water_components <= 1:
            close = True
        if close:
            label = "pool_closeup"

    if label == "pool_closeup" and n_water_components >= 2 and gfrac >= 0.14:
        label = "pool_overview"

    return label, {key: round(float(scores.get(key, 0.0)), 4) for key in VIEWPOINT_KEYS}


def _portrait_cue(bgr: np.ndarray) -> bool:
    """Generic headshot cue: skin-coloured blob near frame centre, little lawn."""
    cv2 = _cv2()
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)
    height, width = bgr.shape[:2]
    skin = ((h <= 25) & (s >= 40) & (s <= 180) & (v >= 60) & (v <= 230)).astype(np.uint8)
    cy0, cy1 = int(0.18 * height), int(0.72 * height)
    cx0, cx1 = int(0.22 * width), int(0.78 * width)
    centre = skin[cy0:cy1, cx0:cx1]
    return float(centre.mean()) >= 0.12


def _layers(bgr: np.ndarray) -> dict[str, np.ndarray]:
    cv2 = _cv2()
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    hue, sat, val = cv2.split(hsv)
    blue, green, red = cv2.split(bgr)
    height, width = bgr.shape[:2]
    yidx = np.arange(height, dtype=np.int32)[:, None]
    grass = (
        (hue >= 28)
        & (hue <= 82)
        & (sat >= 40)
        & (green.astype(np.int16) + 8 > blue.astype(np.int16))
    ).astype(np.uint8) * 255
    grass = cv2.morphologyEx(grass, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    sky = (
        (val > 150)
        & (hue >= 70)
        & (hue <= 140)
        & ((sat < 100) | (yidx < int(0.22 * height)))
    ).astype(np.uint8) * 255
    bright = ((val >= 155) & (sat <= 100) & (sky == 0)).astype(np.uint8) * 255
    cyan = (
        (hue >= 85)
        & (hue <= 125)
        & (sat >= 50)
        & (val >= 45)
        & (val <= 220)
        & (blue.astype(np.int16) + 10 >= green.astype(np.int16))
        & (sky == 0)
    ).astype(np.uint8) * 255
    dark = ((val < 105) & (sat < 110) & (grass == 0) & (sky == 0)).astype(np.uint8) * 255
    return {
        "hsv": hsv,
        "hue": hue,
        "sat": sat,
        "val": val,
        "grass": grass,
        "sky": sky,
        "bright": bright,
        "cyan": cyan,
        "dark": dark,
    }


def _component_from_contour(
    contour: np.ndarray,
    bgr: np.ndarray,
    layers: dict[str, np.ndarray],
) -> WaterComponent | None:
    cv2 = _cv2()
    height, width = bgr.shape[:2]
    area = float(cv2.contourArea(contour))
    frame = float(max(width * height, 1))
    if area < MIN_COMPONENT_AREA_FRAC * frame or area > MAX_COMPONENT_AREA_FRAC * frame:
        return None
    peri = max(float(cv2.arcLength(contour, True)), 1.0)
    compactness = float(4.0 * math.pi * area / (peri * peri))
    hull = cv2.convexHull(contour)
    hull_area = max(float(cv2.contourArea(hull)), 1.0)
    convexity = float(area / hull_area)
    rect = cv2.minAreaRect(contour)
    (_cx, _cy), (rw, rh), _ang = rect
    rect_area = max(float(rw * rh), 1e-6)
    rectangularity = float(area / rect_area)
    aspect = float(max(rw, rh) / max(min(rw, rh), 1e-3))
    moments = cv2.moments(contour)
    if moments["m00"] <= 1e-6:
        return None
    cx = float(moments["m10"] / moments["m00"] / max(width - 1, 1))
    cy = float(moments["m01"] / moments["m00"] / max(height - 1, 1))
    mask = np.zeros((height, width), np.uint8)
    cv2.drawContours(mask, [contour], -1, 255, -1)
    ring = cv2.dilate(mask, np.ones((15, 15), np.uint8))
    band = (ring > 0) & (mask == 0)
    grass_adj = float((layers["grass"][band] > 0).mean()) if band.any() else 0.0
    cyan_frac = float((layers["cyan"][mask > 0] > 0).mean()) if (mask > 0).any() else 0.0
    dark_frac = float((layers["dark"][mask > 0] > 0).mean()) if (mask > 0).any() else 0.0
    water_conf = min(1.0, cyan_frac + 0.65 * dark_frac)
    pts = contour.reshape(-1, 2)
    edge_clip = float(
        ((pts[:, 0] <= 2) | (pts[:, 0] >= width - 3) | (pts[:, 1] <= 2) | (pts[:, 1] >= height - 3)).mean()
    )
    samples = _resample_contour(contour)
    desc = contour_descriptors(
        [[float(x) / max(width - 1, 1), float(y) / max(height - 1, 1)] for x, y in samples]
    )
    n_indents = int((desc or {}).get("n_major_indents") or 0)
    leakage = compactness < 0.22 or n_indents >= 4
    quality = _contour_quality(
        compactness=compactness,
        convexity=convexity,
        relative_area=area / frame,
        edge_clip=edge_clip,
        n_indents=n_indents,
        water_conf=water_conf,
        grass_adj=grass_adj,
        leakage=leakage,
    )
    return WaterComponent(
        contour=contour,
        area=area,
        compactness=round(compactness, 4),
        convexity=round(convexity, 4),
        relative_area=round(area / frame, 4),
        centroid_xy=(round(cx, 4), round(cy, 4)),
        aspect_ratio=round(aspect, 3),
        rectangularity=round(rectangularity, 4),
        n_approx=int(len(cv2.approxPolyDP(contour, 0.03 * peri, True))),
        edge_clip=round(edge_clip, 4),
        water_confidence=round(water_conf, 4),
        grass_adjacency=round(grass_adj, 4),
        cyan_frac=round(cyan_frac, 4),
        dark_frac=round(dark_frac, 4),
        quality=quality,
        descriptors=None if desc is None else {k: v for k, v in desc.items() if k != "norm_xy"} | {"norm_xy": desc.get("norm_xy")},
        contour_image=[
            [round(float(x) / max(width - 1, 1), 4), round(float(y) / max(height - 1, 1), 4)]
            for x, y in samples
        ],
        contour_normalized=_normalize_contour(samples, align_major_axis=True),
        shape_class=_shape_class(
            rectangularity=rectangularity,
            compactness=compactness,
            convexity=convexity,
            aspect=aspect,
        ),
    )


def _contour_quality(
    *,
    compactness: float,
    convexity: float,
    relative_area: float,
    edge_clip: float,
    n_indents: int,
    water_conf: float,
    grass_adj: float,
    leakage: bool,
) -> float:
    if compactness < MIN_COMPACTNESS:
        return 0.0
    if relative_area > MAX_FRAME_COVERAGE:
        return 0.0
    if edge_clip > MAX_EDGE_CLIP:
        return round(0.15 * max(0.0, 1.0 - edge_clip), 4)
    if water_conf < MIN_WATER_CONFIDENCE:
        return 0.0
    if leakage and n_indents >= MAX_COMPLEXITY_INDENTS:
        return 0.0
    compact_term = min(1.0, compactness / 0.55)
    convex_term = min(1.0, convexity / 0.90)
    framed = 1.0 if 0.004 <= relative_area <= 0.22 else 0.35
    clip_term = max(0.0, 1.0 - edge_clip / MAX_EDGE_CLIP)
    water_term = min(1.0, water_conf / 0.55)
    context = min(1.0, grass_adj / 0.25) if grass_adj >= 0.04 else 0.35
    indent_pen = 0.55 if n_indents >= 3 else 1.0
    quality = (
        0.28 * compact_term
        + 0.18 * convex_term
        + 0.14 * framed
        + 0.14 * clip_term
        + 0.16 * water_term
        + 0.10 * context
    ) * indent_pen
    return round(min(1.0, quality), 4)


def _passes_component_filters(comp: WaterComponent, *, viewpoint_hint: str | None = None) -> bool:
    cx, cy = comp.centroid_xy
    # Window-like holes in upper/mid facade: compact dark rectangles with no lawn.
    window_like = (
        cy < 0.58
        and comp.grass_adjacency < 0.05
        and comp.cyan_frac < 0.15
        and 0.45 <= comp.rectangularity
    )
    if window_like:
        return False
    if cy < 0.18:
        return False
    if comp.quality <= 0:
        return False
    if comp.edge_clip > MAX_EDGE_CLIP:
        return False
    if comp.relative_area > MAX_FRAME_COVERAGE:
        return False
    return True


def _from_bright_holes(bgr: np.ndarray, layers: dict[str, np.ndarray]) -> list[np.ndarray]:
    cv2 = _cv2()
    bright = cv2.morphologyEx(layers["bright"], cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    bright = cv2.morphologyEx(bright, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    contours, hierarchy = cv2.findContours(bright, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if hierarchy is None:
        return []
    out = []
    for i, contour in enumerate(contours):
        if hierarchy[0][i][3] < 0:
            continue
        out.append(contour)
    return out


def _from_cyan(layers: dict[str, np.ndarray]) -> list[np.ndarray]:
    cv2 = _cv2()
    mask = layers["cyan"].copy()
    height = mask.shape[0]
    mask[: int(0.16 * height)] = 0
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return list(contours)


def _from_grass_adjacent_dark(layers: dict[str, np.ndarray]) -> list[np.ndarray]:
    cv2 = _cv2()
    grass = layers["grass"]
    dark = layers["dark"]
    cyan = layers["cyan"]
    height = grass.shape[0]
    near = cv2.dilate(grass, np.ones((27, 27), np.uint8))
    seed = (((dark > 0) | (cyan > 0)) & (near > 0)).astype(np.uint8) * 255
    seed[: int(0.14 * height)] = 0
    seed = cv2.morphologyEx(seed, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    seed = cv2.morphologyEx(seed, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    contours, _ = cv2.findContours(seed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return list(contours)


def _iou(a: WaterComponent, b: WaterComponent, shape: tuple[int, int]) -> float:
    cv2 = _cv2()
    height, width = shape
    ma = np.zeros((height, width), np.uint8)
    mb = np.zeros((height, width), np.uint8)
    cv2.drawContours(ma, [a.contour], -1, 255, -1)
    cv2.drawContours(mb, [b.contour], -1, 255, -1)
    inter = float(np.logical_and(ma > 0, mb > 0).sum())
    union = float(np.logical_or(ma > 0, mb > 0).sum())
    return 0.0 if union <= 0 else inter / union


def _merge_components(items: list[WaterComponent], shape: tuple[int, int]) -> list[WaterComponent]:
    kept: list[WaterComponent] = []
    for item in sorted(items, key=lambda c: -c.quality):
        if item.quality <= 0:
            continue
        duplicate = False
        for other in kept:
            if _iou(item, other, shape) >= 0.45:
                duplicate = True
                break
            dist = math.hypot(item.centroid_xy[0] - other.centroid_xy[0], item.centroid_xy[1] - other.centroid_xy[1])
            if dist < 0.06 and min(item.area, other.area) / max(item.area, other.area) > 0.35:
                duplicate = True
                break
        if not duplicate:
            kept.append(item)
    return kept


def extract_water_components(image_bytes: bytes) -> list[WaterComponent]:
    bgr = _bgr_from_bytes(image_bytes)
    layers = _layers(bgr)
    raw: list[np.ndarray] = []
    raw.extend(_from_bright_holes(bgr, layers))
    raw.extend(_from_cyan(layers))
    raw.extend(_from_grass_adjacent_dark(layers))
    comps: list[WaterComponent] = []
    for contour in raw:
        comp = _component_from_contour(contour, bgr, layers)
        if comp is None or not _passes_component_filters(comp):
            continue
        comps.append(comp)
    return _merge_components(comps, bgr.shape[:2])


def _component_public(comp: WaterComponent) -> dict[str, Any]:
    desc = comp.descriptors or {}
    return {
        "compactness": comp.compactness,
        "convexity": comp.convexity,
        "relative_area": comp.relative_area,
        "centroid_xy": list(comp.centroid_xy),
        "aspect_ratio": comp.aspect_ratio,
        "rectangularity": comp.rectangularity,
        "n_approx": comp.n_approx,
        "edge_clip": comp.edge_clip,
        "water_confidence": comp.water_confidence,
        "grass_adjacency": comp.grass_adjacency,
        "cyan_frac": comp.cyan_frac,
        "quality": comp.quality,
        "shape_class": comp.shape_class,
        "circularity": desc.get("circularity"),
        "solidity": desc.get("solidity"),
        "elongation": desc.get("elongation"),
        "n_corners": desc.get("n_corners"),
        "n_major_indents": desc.get("n_major_indents"),
        "sharp_frac": desc.get("sharp_frac"),
        "contour_image": comp.contour_image,
        "contour_normalized": comp.contour_normalized,
    }


def _compound_stats(comps: list[WaterComponent]) -> dict[str, Any] | None:
    if len(comps) < 2:
        return None
    primary, secondary = comps[0], comps[1]
    sep = math.hypot(
        primary.centroid_xy[0] - secondary.centroid_xy[0],
        primary.centroid_xy[1] - secondary.centroid_xy[1],
    )
    size_ratio = secondary.area / max(primary.area, 1.0)
    cv2 = _cv2()
    pa = cv2.boundingRect(primary.contour)
    pb = cv2.boundingRect(secondary.contour)
    ax, ay, aw, ah = pa
    bx, by, bw, bh = pb
    inter_w = max(0, min(ax + aw, bx + bw) - max(ax, bx))
    inter_h = max(0, min(ay + ah, by + bh) - max(ay, by))
    overlap = inter_w > 2 and inter_h > 2
    touch = sep < 0.04 or overlap
    return {
        "n_components": len(comps),
        "size_ratio": round(float(size_ratio), 4),
        "centroid_separation": round(float(sep), 4),
        "touch_or_overlap": bool(touch),
        "dominant_shape_class": primary.shape_class,
        "secondary_shape_class": secondary.shape_class,
        "separable": bool((not touch) and 0.04 <= size_ratio <= 0.85 and sep >= 0.08),
    }


def _fingerprint_from_component(
    comp: WaterComponent,
    *,
    media_id: str,
    house: tuple[float, float] | None,
) -> PoolGeometryFingerprint:
    cx, cy = comp.centroid_xy
    dx = dy = dist = angle = None
    hx = hy = None
    if house is not None:
        hx, hy = house
        dx = cx - hx
        dy = cy - hy
        dist = float(math.hypot(dx, dy))
        angle = float(math.degrees(math.atan2(dy, dx)))
    return PoolGeometryFingerprint(
        present=True,
        unknown=False,
        shape_class=comp.shape_class,
        aspect_ratio=comp.aspect_ratio,
        compactness=comp.compactness,
        rectangularity=comp.rectangularity,
        convexity=comp.convexity,
        relative_area=comp.relative_area,
        centroid_x=cx,
        centroid_y=cy,
        house_centroid_x=None if hx is None else round(hx, 4),
        house_centroid_y=None if hy is None else round(hy, 4),
        pool_to_house_dx=None if dx is None else round(dx, 4),
        pool_to_house_dy=None if dy is None else round(dy, 4),
        pool_to_house_dist=None if dist is None else round(dist, 4),
        pool_to_house_angle_deg=None if angle is None else round(angle, 2),
        contour_normalized=comp.contour_normalized,
        contour_image=comp.contour_image,
        evidence_media_id=media_id,
        notes=["listing_evidence_v2"],
    )


def observe_listing_frame(
    media_id: str,
    image_bytes: bytes,
    *,
    clip_scores: dict[str, float] | None = None,
) -> FrameEvidence:
    bgr = _bgr_from_bytes(image_bytes)
    layers = _layers(bgr)
    grass_frac = float((layers["grass"] > 0).mean())
    comps = extract_water_components(image_bytes)
    dominant = comps[0] if comps else None
    viewpoint, scores = classify_viewpoint(
        bgr,
        clip_scores=clip_scores,
        grass_frac=grass_frac,
        n_water_components=len(comps),
        dominant_cy=None if dominant is None else dominant.centroid_xy[1],
        dominant_rel=None if dominant is None else dominant.relative_area,
    )
    notes: list[str] = []
    if viewpoint in {"interior", "unusable_ambiguous"}:
        comps = []
        dominant = None
        notes.append(f"skipped_extraction_viewpoint={viewpoint}")

    house = None
    if viewpoint not in BLOCKED_SPATIAL:
        union = layers["cyan"].copy()
        if comps:
            cv2 = _cv2()
            mask = np.zeros(bgr.shape[:2], np.uint8)
            for comp in comps:
                cv2.drawContours(mask, [comp.contour], -1, 255, -1)
            union = mask
        house = _roof_centroid(bgr, union)

    pool_detected = bool(comps)
    overview_ok = viewpoint in SHAPE_VIEWPOINTS and pool_detected and (dominant.quality if dominant else 0) >= 0.35
    spatial_ok = (
        viewpoint in SPATIAL_VIEWPOINTS
        and pool_detected
        and house is not None
        and dominant is not None
        and dominant.relative_area <= 0.22
        and dominant.quality >= 0.35
    )
    scale_ok = (
        viewpoint in SCALE_VIEWPOINTS
        and pool_detected
        and house is not None
        and dominant is not None
        and 0.008 <= dominant.relative_area <= 0.20
    )
    aerial_ok = viewpoint == "aerial_near_nadir" and pool_detected

    fp = None
    dist = angle = dx = dy = None
    if dominant is not None:
        fp = _fingerprint_from_component(dominant, media_id=media_id, house=house if spatial_ok else None)
        if spatial_ok:
            dist = fp.pool_to_house_dist
            angle = fp.pool_to_house_angle_deg
            dx = fp.pool_to_house_dx
            dy = fp.pool_to_house_dy

    ratio = None
    if scale_ok and dominant is not None:
        ratio = _pool_roof_ratio_nadir(bgr, dominant)

    return FrameEvidence(
        media_id=media_id,
        viewpoint=viewpoint,
        viewpoint_scores=scores,
        pool_detected=pool_detected,
        pool_overview_eligible=bool(overview_ok),
        spatial_eligible=bool(spatial_ok),
        scale_eligible=bool(scale_ok),
        aerial_eligible=bool(aerial_ok),
        contour_quality=0.0 if dominant is None else dominant.quality,
        n_components=len(comps),
        components=[_component_public(c) for c in comps],
        dominant=None if dominant is None else _component_public(dominant),
        secondary=None if len(comps) < 2 else _component_public(comps[1]),
        compound=_compound_stats(comps),
        house_visible=house is not None,
        pool_to_house_dist=dist,
        pool_to_house_angle_deg=angle,
        pool_to_house_dx=dx,
        pool_to_house_dy=dy,
        pool_roof_ratio=ratio,
        notes=notes,
        fingerprint=fp,
    )


def _pool_roof_ratio_nadir(bgr: np.ndarray, comp: WaterComponent) -> float | None:
    """Pool/roof pixel ratio only for aerial-compatible frames."""
    cv2 = _cv2()
    height, width = bgr.shape[:2]
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    threshold = float(np.percentile(gray, 74))
    roof = (gray >= threshold).astype(np.uint8)
    mask = np.zeros((height, width), np.uint8)
    cv2.drawContours(mask, [comp.contour], -1, 255, -1)
    roof[mask > 0] = 0
    pool_px = float((mask > 0).sum())
    roof_px = float(roof.sum())
    frame = float(max(width * height, 1))
    if pool_px < 40 or roof_px < max(80.0, 0.04 * frame):
        return None
    if pool_px / frame > 0.22:
        return None
    return round(pool_px / max(roof_px, 1.0), 4)


def clip_viewpoint_scores(image) -> dict[str, float]:
    from backend.vision.clip_encoder import load_clip

    model, preprocess, tokenizer, torch = load_clip()
    image_t = preprocess(image.convert("RGB")).unsqueeze(0)
    text = tokenizer(list(VIEWPOINT_LABELS))
    with torch.no_grad():
        image_f = model.encode_image(image_t)
        text_f = model.encode_text(text)
        image_f = image_f / image_f.norm(dim=-1, keepdim=True)
        text_f = text_f / text_f.norm(dim=-1, keepdim=True)
        scores = (100.0 * image_f @ text_f.T).softmax(dim=-1)[0]
    vals = scores.detach().cpu().numpy()
    return {key: float(vals[i]) for i, key in enumerate(VIEWPOINT_KEYS)}


def _compatible_shape(a: FrameEvidence, b: FrameEvidence) -> bool:
    if not a.dominant or not b.dominant:
        return False
    ea = float(a.dominant.get("elongation") or a.dominant.get("aspect_ratio") or 1.0)
    eb = float(b.dominant.get("elongation") or b.dominant.get("aspect_ratio") or 1.0)
    if min(ea, eb) / max(ea, eb) < 0.72:
        return False
    return abs(float(a.dominant["compactness"]) - float(b.dominant["compactness"])) <= 0.18


def select_shape_evidence(frames: list[FrameEvidence]) -> dict[str, Any]:
    """Best independently-good frame beats a cluster-sum of poor frames."""
    eligible = [f for f in frames if f.pool_overview_eligible and f.dominant]
    good = [f for f in eligible if f.contour_quality >= 0.45 and f.dominant["compactness"] >= MIN_GOOD_COMPACTNESS]
    usable = good or [f for f in eligible if f.contour_quality >= 0.35]
    best_single = None if not usable else max(usable, key=lambda f: f.contour_quality)

    clusters: list[list[FrameEvidence]] = []
    for item in sorted(eligible, key=lambda f: -f.contour_quality):
        placed = False
        for cluster in clusters:
            if _compatible_shape(item, cluster[0]):
                cluster.append(item)
                placed = True
                break
        if not placed:
            clusters.append([item])
    cluster_sum = None
    if clusters:
        cluster_sum = max(clusters, key=lambda c: sum(f.contour_quality for f in c))

    consensus = []
    if good:
        seed = max(good, key=lambda f: f.contour_quality)
        consensus = [f for f in good if _compatible_shape(f, seed)]

    chosen = best_single
    method = "best_single_frame" if best_single is not None else "none"
    if chosen is None and consensus:
        chosen = max(consensus, key=lambda f: f.contour_quality)
        method = "consensus_good_frames"
    # Cluster-sum of poor frames is recorded, never preferred over a cleaner single frame.
    return {
        "method": method,
        "best_single_id": None if best_single is None else best_single.media_id,
        "best_single_quality": None if best_single is None else best_single.contour_quality,
        "consensus_ids": [f.media_id for f in consensus],
        "cluster_sum_ids": [] if cluster_sum is None else [f.media_id for f in cluster_sum],
        "cluster_sum_quality_total": None if cluster_sum is None else round(sum(f.contour_quality for f in cluster_sum), 4),
        "cluster_sum_best_id": None if cluster_sum is None else cluster_sum[0].media_id,
        "chosen_id": None if chosen is None else chosen.media_id,
        "chosen_quality": None if chosen is None else chosen.contour_quality,
        "chosen_frame": chosen,
    }


def assemble_channels(frames: list[FrameEvidence]) -> dict[str, Any]:
    shape = select_shape_evidence(frames)
    spatial_frames = [f for f in frames if f.spatial_eligible]
    spatial_best = None if not spatial_frames else max(spatial_frames, key=lambda f: f.contour_quality)
    scale_frames = [f for f in frames if f.scale_eligible and f.pool_roof_ratio]
    aerial_frames = [f for f in frames if f.aerial_eligible]
    compound_frames = [
        f
        for f in frames
        if f.pool_overview_eligible and f.compound and f.compound.get("separable")
    ]
    return {
        "shape": {
            "eligible": shape["chosen_id"] is not None,
            "source_ids": [] if shape["chosen_id"] is None else [shape["chosen_id"]],
            "viewpoint": None if shape["chosen_frame"] is None else shape["chosen_frame"].viewpoint,
            "selection": {k: v for k, v in shape.items() if k != "chosen_frame"},
            "dominant": None if shape["chosen_frame"] is None else shape["chosen_frame"].dominant,
            "secondary": None if shape["chosen_frame"] is None else shape["chosen_frame"].secondary,
            "n_components": 0 if shape["chosen_frame"] is None else shape["chosen_frame"].n_components,
        },
        "spatial": {
            "eligible": spatial_best is not None,
            "source_ids": [] if spatial_best is None else [spatial_best.media_id],
            "viewpoint": None if spatial_best is None else spatial_best.viewpoint,
            "dist": None if spatial_best is None else spatial_best.pool_to_house_dist,
            "angle_deg": None if spatial_best is None else spatial_best.pool_to_house_angle_deg,
            "dx": None if spatial_best is None else spatial_best.pool_to_house_dx,
            "dy": None if spatial_best is None else spatial_best.pool_to_house_dy,
        },
        "scale": {
            "eligible": bool(scale_frames),
            "nadir_compatible": bool(scale_frames),
            "source_ids": [f.media_id for f in scale_frames],
            "pool_roof_ratio": None
            if not scale_frames
            else round(float(np.median([f.pool_roof_ratio for f in scale_frames])), 4),
        },
        "aerial": {
            "eligible": bool(aerial_frames),
            "source_ids": [f.media_id for f in aerial_frames],
        },
        "compound_pool": {
            "detected": bool(compound_frames),
            "source_ids": [f.media_id for f in compound_frames],
        },
    }


def scoring_fingerprint_from_channels(channels: dict[str, Any], frames: list[FrameEvidence]) -> PoolGeometryFingerprint | None:
    """Adapter for the frozen PR #6 scorer. Does not average incompatible views."""
    by_id = {f.media_id: f for f in frames}
    shape_id = (channels.get("shape") or {}).get("source_ids") or []
    if not shape_id:
        return None
    shape_frame = by_id.get(shape_id[0])
    if shape_frame is None or shape_frame.fingerprint is None:
        return None
    src = shape_frame.fingerprint
    spatial_id = (channels.get("spatial") or {}).get("source_ids") or []
    spatial_frame = by_id.get(spatial_id[0]) if spatial_id else None
    dist = angle = dx = dy = hx = hy = None
    if spatial_frame is not None and spatial_frame.spatial_eligible:
        dist = spatial_frame.pool_to_house_dist
        angle = spatial_frame.pool_to_house_angle_deg
        dx = spatial_frame.pool_to_house_dx
        dy = spatial_frame.pool_to_house_dy
        if spatial_frame.fingerprint is not None:
            hx = spatial_frame.fingerprint.house_centroid_x
            hy = spatial_frame.fingerprint.house_centroid_y
    return PoolGeometryFingerprint(
        present=True,
        unknown=False,
        shape_class=src.shape_class,
        aspect_ratio=src.aspect_ratio,
        compactness=src.compactness,
        rectangularity=src.rectangularity,
        convexity=src.convexity,
        relative_area=src.relative_area,
        centroid_x=src.centroid_x,
        centroid_y=src.centroid_y,
        house_centroid_x=hx,
        house_centroid_y=hy,
        pool_to_house_dx=dx,
        pool_to_house_dy=dy,
        pool_to_house_dist=dist,
        pool_to_house_angle_deg=angle,
        contour_normalized=src.contour_normalized,
        contour_image=src.contour_image,
        evidence_media_id=src.evidence_media_id,
        notes=[
            "listing_evidence_v2_channels",
            f"shape_from={shape_frame.media_id}",
            f"spatial_from={None if spatial_frame is None else spatial_frame.media_id}",
            f"shape_viewpoint={shape_frame.viewpoint}",
        ],
    )


def frame_public(frame: FrameEvidence) -> dict[str, Any]:
    return {
        "media_id": frame.media_id,
        "viewpoint": frame.viewpoint,
        "viewpoint_scores": frame.viewpoint_scores,
        "pool_detected": frame.pool_detected,
        "pool_overview_eligible": frame.pool_overview_eligible,
        "spatial_eligible": frame.spatial_eligible,
        "scale_eligible": frame.scale_eligible,
        "aerial_eligible": frame.aerial_eligible,
        "contour_quality": frame.contour_quality,
        "n_components": frame.n_components,
        "dominant": None if frame.dominant is None else {k: v for k, v in frame.dominant.items() if k not in {"contour_image", "contour_normalized", "norm_xy"}},
        "secondary": None if frame.secondary is None else {k: v for k, v in frame.secondary.items() if k not in {"contour_image", "contour_normalized", "norm_xy"}},
        "compound": frame.compound,
        "house_visible": frame.house_visible,
        "pool_to_house_dist": frame.pool_to_house_dist,
        "pool_to_house_angle_deg": frame.pool_to_house_angle_deg,
        "pool_roof_ratio": frame.pool_roof_ratio,
        "notes": frame.notes,
    }
