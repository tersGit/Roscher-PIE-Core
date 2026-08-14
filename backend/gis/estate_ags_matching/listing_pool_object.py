"""Colour-independent listing pool *object* extraction.

Reuses frozen Listing Evidence v2 viewpoint gates. Does not modify
listing_evidence_v2.py, production ranking, OS v1, or Scoring v2.

Water colour is not evidence. Explicit RGB/HSV thresholds, colour blobs,
and listing-to-aerial colour similarity are not used to form the pool
boundary or a candidate score. A pretrained CLIP model may use colour
internally as part of object recognition. Once a region is labelled
pool/water-feature vs not, colour is discarded. Discrimination uses
boundary geometry only.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import numpy as np
from PIL import Image

from backend.gis.estate_ags_matching.listing_evidence_v2 import (
    BLOCKED_SPATIAL,
    SCALE_VIEWPOINTS,
    SHAPE_VIEWPOINTS,
    SPATIAL_VIEWPOINTS,
    classify_viewpoint,
)
from backend.gis.estate_ags_matching.os_scoring_v2 import contour_descriptors
from backend.gis.estate_ags_matching.pool_geometry import (
    PoolGeometryFingerprint,
    _bgr_from_bytes,
    _normalize_contour,
    _resample_contour,
    _roof_centroid,
    _shape_class,
)

OBJECT_KEYS = ("pool", "house", "paving", "garden", "interior", "person")
OBJECT_LABELS = (
    "a swimming pool or jacuzzi water feature",
    "a house exterior wall roof window or balcony",
    "paved driveway patio tiles or timber decking",
    "garden plants lawn and trees",
    "an interior room with furniture",
    "a portrait of a person",
)

GEOMETRY_CLASSES = (
    "full_pool_planform",
    "partial_pool_boundary",
    "water_fragment",
    "reflection_or_highlight",
    "coping_or_background",
    "no_usable_pool_geometry",
)

SKIP_OBJECT_VIEWPOINTS = frozenset({"interior", "unusable_ambiguous"})


def _cv2():
    import cv2

    return cv2


@dataclass
class PoolObjectObservation:
    media_id: str
    viewpoint: str
    viewpoint_scores: dict[str, float]
    pool_object_detected: bool
    geometry_class: str
    full_boundary_recovered: bool
    partial_object: bool
    component_count: int
    contour_quality: float
    edge_clip: float
    shape_eligible: bool
    spatial_eligible: bool
    scale_eligible: bool
    house_visible: bool
    pool_to_house_dist: float | None = None
    pool_to_house_angle_deg: float | None = None
    pool_to_house_dx: float | None = None
    pool_to_house_dy: float | None = None
    nearest_pool_building_edge: float | None = None
    pool_orientation_deg: float | None = None
    pool_roof_ratio: float | None = None
    l_geometry: dict[str, Any] = field(default_factory=dict)
    dominant: dict[str, Any] | None = None
    components: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    fingerprint: PoolGeometryFingerprint | None = None
    contour_image: list[list[float]] = field(default_factory=list)


def _encode_images(images: list[Image.Image], batch: int = 16) -> np.ndarray:
    from backend.vision.clip_encoder import load_clip

    model, preprocess, _, torch = load_clip()
    if not images:
        return np.zeros((0, 512), dtype=np.float32)
    chunks = []
    for start in range(0, len(images), batch):
        tensor = torch.stack(
            [preprocess(image.convert("RGB")) for image in images[start : start + batch]]
        )
        with torch.no_grad():
            feat = model.encode_image(tensor)
            feat = feat / feat.norm(dim=-1, keepdim=True)
        chunks.append(feat.detach().cpu().numpy())
    return np.concatenate(chunks, axis=0)


@lru_cache(maxsize=1)
def _object_text_features() -> np.ndarray:
    from backend.vision.clip_encoder import load_clip

    model, _, tokenizer, torch = load_clip()
    text = tokenizer(list(OBJECT_LABELS))
    with torch.no_grad():
        feat = model.encode_text(text)
        feat = feat / feat.norm(dim=-1, keepdim=True)
    return feat.detach().cpu().numpy()


def clip_object_scores(image: Image.Image) -> dict[str, float]:
    feat = _encode_images([image])[0]
    text = _object_text_features()
    logits = 100.0 * feat @ text.T
    logits = logits - logits.max()
    exp = np.exp(logits)
    prob = exp / max(float(exp.sum()), 1e-9)
    return {key: round(float(prob[i]), 4) for i, key in enumerate(OBJECT_KEYS)}


def pool_object_probability_map(bgr: np.ndarray, *, rows: int = 5, cols: int = 7) -> np.ndarray:
    """Coarse CLIP pool-vs-not map. Colour is not thresholded; CLIP classifies objects."""
    cv2 = _cv2()
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    height, width = rgb.shape[:2]
    pil = Image.fromarray(rgb)
    images: list[Image.Image] = []
    boxes: list[tuple[int, int, int, int]] = []
    patch_w = max(32, width // 4)
    patch_h = max(32, height // 4)
    for row in range(rows):
        for col in range(cols):
            cx = int((col + 0.5) * width / cols)
            cy = int((row + 0.5) * height / rows)
            x0 = max(0, cx - patch_w // 2)
            y0 = max(0, cy - patch_h // 2)
            x1 = min(width, x0 + patch_w)
            y1 = min(height, y0 + patch_h)
            x0 = max(0, x1 - patch_w)
            y0 = max(0, y1 - patch_h)
            images.append(pil.crop((x0, y0, x1, y1)))
            boxes.append((x0, y0, x1, y1))
    feats = _encode_images(images)
    text = _object_text_features()
    logits = 100.0 * feats @ text.T
    logits = logits - logits.max(axis=1, keepdims=True)
    exp = np.exp(logits)
    prob = exp / np.clip(exp.sum(axis=1, keepdims=True), 1e-9, None)
    pool = prob[:, 0].astype(np.float32)
    accum = np.zeros((height, width), np.float32)
    weight = np.zeros((height, width), np.float32)
    for score, (x0, y0, x1, y1) in zip(pool, boxes):
        accum[y0:y1, x0:x1] += float(score)
        weight[y0:y1, x0:x1] += 1.0
    return accum / np.clip(weight, 1e-6, None)


def object_mask_from_probability(prob: np.ndarray, *, min_score: float = 0.18) -> np.ndarray:
    cv2 = _cv2()
    binary = (prob >= min_score).astype(np.uint8) * 255
    kernel = np.ones((9, 9), np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    return binary


def intensity_edge_map(bgr: np.ndarray) -> np.ndarray:
    """Grayscale gradient edges. Not a hue/saturation water detector."""
    cv2 = _cv2()
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    return cv2.Canny(gray, 40, 120)


def snap_mask_to_intensity_edges(mask: np.ndarray, edges: np.ndarray) -> np.ndarray:
    cv2 = _cv2()
    if mask.max() == 0:
        return mask
    band = cv2.dilate(mask, np.ones((11, 11), np.uint8))
    snapped = cv2.bitwise_and(edges, band)
    snapped = cv2.dilate(snapped, np.ones((3, 3), np.uint8))
    snapped = cv2.morphologyEx(snapped, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    # Keep the component overlapping the original object mask most.
    contours, _ = cv2.findContours(snapped, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return mask
    best = None
    best_overlap = -1.0
    mask_px = float((mask > 0).sum())
    for contour in contours:
        cand = np.zeros_like(mask)
        cv2.drawContours(cand, [contour], -1, 255, -1)
        overlap = float(np.logical_and(cand > 0, mask > 0).sum())
        if overlap > best_overlap:
            best_overlap = overlap
            best = cand
    if best is None or best_overlap < 0.25 * max(mask_px, 1.0):
        return mask
    return best


def _edge_clip(contour: np.ndarray, width: int, height: int) -> float:
    pts = contour.reshape(-1, 2)
    if len(pts) == 0:
        return 1.0
    return float(
        ((pts[:, 0] <= 2) | (pts[:, 0] >= width - 3) | (pts[:, 1] <= 2) | (pts[:, 1] >= height - 3)).mean()
    )


def _contour_public(contour: np.ndarray, width: int, height: int) -> dict[str, Any] | None:
    cv2 = _cv2()
    area = float(cv2.contourArea(contour))
    frame = float(max(width * height, 1))
    if area < 0.004 * frame:
        return None
    peri = max(float(cv2.arcLength(contour, True)), 1.0)
    compactness = float(4.0 * math.pi * area / (peri * peri))
    hull = cv2.convexHull(contour)
    hull_area = max(float(cv2.contourArea(hull)), 1.0)
    convexity = float(area / hull_area)
    (_cx, _cy), (rw, rh), angle = cv2.minAreaRect(contour)
    rect_area = max(float(rw * rh), 1e-6)
    rectangularity = float(area / rect_area)
    aspect = float(max(rw, rh) / max(min(rw, rh), 1e-3))
    samples = _resample_contour(contour)
    desc = contour_descriptors(
        [[float(x) / max(width - 1, 1), float(y) / max(height - 1, 1)] for x, y in samples]
    ) or {}
    moments = cv2.moments(contour)
    if moments["m00"] <= 1e-6:
        return None
    cx = float(moments["m10"] / moments["m00"] / max(width - 1, 1))
    cy = float(moments["m01"] / moments["m00"] / max(height - 1, 1))
    return {
        "relative_area": round(area / frame, 4),
        "compactness": round(compactness, 4),
        "convexity": round(convexity, 4),
        "rectangularity": round(rectangularity, 4),
        "aspect_ratio": round(aspect, 3),
        "orientation_deg": round(float(angle), 2),
        "centroid_xy": [round(cx, 4), round(cy, 4)],
        "edge_clip": round(_edge_clip(contour, width, height), 4),
        "n_approx": int(len(cv2.approxPolyDP(contour, 0.02 * peri, True))),
        "shape_class": _shape_class(
            rectangularity=rectangularity,
            compactness=compactness,
            convexity=convexity,
            aspect=aspect,
        ),
        "circularity": desc.get("circularity"),
        "solidity": desc.get("solidity"),
        "elongation": desc.get("elongation"),
        "n_corners": desc.get("n_corners"),
        "n_major_indents": desc.get("n_major_indents"),
        "max_indent": desc.get("max_indent"),
        "sharp_frac": desc.get("sharp_frac"),
        "turn_std": desc.get("turn_std"),
        "contour_image": [
            [round(float(x) / max(width - 1, 1), 4), round(float(y) / max(height - 1, 1), 4)]
            for x, y in samples
        ],
        "contour_normalized": _normalize_contour(samples, align_major_axis=True),
        "descriptors": {k: v for k, v in desc.items() if k != "norm_xy"},
        "_contour": contour,
    }


def rectilinear_compound_geometry(contour: np.ndarray, width: int, height: int) -> dict[str, Any]:
    """Generic two-arm / concave-corner descriptors. Not a listing-specific L class."""
    cv2 = _cv2()
    empty = {
        "two_dominant_arms": False,
        "arms_approximately_perpendicular": False,
        "strong_concave_inner_corner": False,
        "predominantly_straight_outer": False,
        "rectilinear_not_kidney": False,
        "arm_length_ratio": None,
        "arm_width_ratio": None,
        "principal_angle_delta_deg": None,
        "n_major_indents": 0,
        "max_indent": 0.0,
        "sharp_frac": None,
        "consistent_with_l_planform": False,
    }
    if contour is None or len(contour) < 5:
        return empty
    peri = max(float(cv2.arcLength(contour, True)), 1.0)
    approx = cv2.approxPolyDP(contour, 0.02 * peri, True).reshape(-1, 2)
    hull_idx = cv2.convexHull(contour, returnPoints=False)
    depths: list[float] = []
    indent_pts: list[np.ndarray] = []
    if hull_idx is not None and len(hull_idx) >= 3:
        try:
            defects = cv2.convexityDefects(contour, hull_idx)
        except cv2.error:
            defects = None
        if defects is not None:
            area = max(float(cv2.contourArea(contour)), 1.0)
            pts = contour.reshape(-1, 2)
            for item in np.asarray(defects).reshape(-1, 4):
                rel = float(item[3]) / 256.0 / max(math.sqrt(area), 1.0)
                depths.append(rel)
                indent_pts.append(pts[int(item[2])])
    n_major = sum(1 for depth in depths if depth >= 0.08)
    max_indent = max(depths) if depths else 0.0
    # Edge orientations of the simplified polygon.
    if len(approx) >= 4:
        edges = np.roll(approx, -1, axis=0) - approx
        lengths = np.linalg.norm(edges, axis=1)
        angles = (np.degrees(np.arctan2(edges[:, 1], edges[:, 0])) + 180.0) % 180.0
        order = np.argsort(-lengths)
        keep = order[: min(6, len(order))]
        long_angles = angles[keep]
        # Cluster into up to two principal directions.
        a0 = float(long_angles[0])
        group_a = [a for a in long_angles if min(abs(a - a0), 180.0 - abs(a - a0)) <= 25.0]
        group_b = [a for a in long_angles if min(abs(a - a0), 180.0 - abs(a - a0)) > 25.0]
        delta = None
        if group_b:
            b0 = float(np.median(group_b))
            delta = min(abs(b0 - a0), 180.0 - abs(b0 - a0))
        two_arms = len(group_a) >= 1 and len(group_b) >= 1 and n_major >= 1
        perp = delta is not None and 60.0 <= delta <= 120.0
        arm_len_ratio = None
        if group_b:
            len_a = float(sum(lengths[keep][i] for i, a in enumerate(long_angles) if a in group_a or min(abs(a - a0), 180 - abs(a - a0)) <= 25))
            len_b = float(sum(lengths[keep][i] for i, a in enumerate(long_angles) if min(abs(a - a0), 180 - abs(a - a0)) > 25))
            arm_len_ratio = round(min(len_a, len_b) / max(max(len_a, len_b), 1.0), 4)
    else:
        two_arms = False
        perp = False
        delta = None
        arm_len_ratio = None
    desc = contour_descriptors(
        [[float(x) / max(width - 1, 1), float(y) / max(height - 1, 1)] for x, y in contour.reshape(-1, 2)]
    ) or {}
    sharp = float(desc.get("sharp_frac") or 0.0)
    circularity = float(desc.get("circularity") or 1.0)
    solidity = float(desc.get("solidity") or 1.0)
    straight = sharp >= 0.12 and int(desc.get("n_corners") or 0) >= 5
    rectilinear = circularity <= 0.55 and solidity <= 0.92
    not_kidney = circularity <= 0.62 and sharp >= 0.08
    strong_corner = n_major >= 1 and max_indent >= 0.10
    consistent = bool(two_arms and perp and strong_corner and rectilinear)
    return {
        "two_dominant_arms": bool(two_arms),
        "arms_approximately_perpendicular": bool(perp),
        "strong_concave_inner_corner": bool(strong_corner),
        "predominantly_straight_outer": bool(straight),
        "rectilinear_not_kidney": bool(rectilinear and not_kidney),
        "arm_length_ratio": arm_len_ratio,
        "arm_width_ratio": None,
        "principal_angle_delta_deg": None if delta is None else round(float(delta), 1),
        "n_major_indents": n_major,
        "max_indent": round(float(max_indent), 4),
        "sharp_frac": None if desc.get("sharp_frac") is None else round(float(desc["sharp_frac"]), 4),
        "consistent_with_l_planform": consistent,
    }


def classify_geometry(
    *,
    detected: bool,
    comps: list[dict[str, Any]],
    clip_pool: float,
    viewpoint: str,
) -> str:
    if not detected or not comps:
        return "no_usable_pool_geometry"
    dom = comps[0]
    area = float(dom.get("relative_area") or 0.0)
    compact = float(dom.get("compactness") or 0.0)
    clip = float(dom.get("edge_clip") or 0.0)
    indents = int(dom.get("n_major_indents") or 0)
    if viewpoint == "pool_closeup" and area >= 0.18:
        return "partial_pool_boundary"
    if area < 0.008 and compact >= 0.40:
        return "reflection_or_highlight"
    if compact < 0.08 and indents >= 4:
        return "water_fragment"
    if clip_pool < 0.12 and area >= 0.02:
        return "coping_or_background"
    if clip >= 0.22 or area < 0.02:
        return "partial_pool_boundary"
    if area >= 0.02 and compact >= 0.08:
        return "full_pool_planform"
    return "partial_pool_boundary"


def _quality(comp: dict[str, Any], clip_pool: float, geom_class: str) -> float:
    if geom_class in {"no_usable_pool_geometry", "coping_or_background", "water_fragment", "reflection_or_highlight"}:
        return 0.0
    compact = float(comp.get("compactness") or 0.0)
    clip = float(comp.get("edge_clip") or 0.0)
    area = float(comp.get("relative_area") or 0.0)
    # L-like compound shapes are allowed to have modest compactness.
    compact_term = min(1.0, compact / 0.28) if compact >= 0.08 else 0.0
    clip_term = max(0.0, 1.0 - clip / 0.35)
    area_term = 1.0 if 0.015 <= area <= 0.35 else 0.4
    obj_term = min(1.0, clip_pool / 0.35)
    return round(0.30 * compact_term + 0.25 * clip_term + 0.20 * area_term + 0.25 * obj_term, 4)


def extract_pool_object_components(image_bytes: bytes) -> tuple[list[dict[str, Any]], dict[str, float], np.ndarray]:
    bgr = _bgr_from_bytes(image_bytes)
    height, width = bgr.shape[:2]
    rgb = _cv2().cvtColor(bgr, _cv2().COLOR_BGR2RGB)
    whole = clip_object_scores(Image.fromarray(rgb))
    if whole.get("pool", 0.0) < 0.08 and whole.get("person", 0.0) >= 0.25:
        return [], whole, np.zeros((height, width), np.uint8)
    prob = pool_object_probability_map(bgr)
    mask = object_mask_from_probability(prob, min_score=max(0.16, 0.55 * float(prob.max())))
    mask = snap_mask_to_intensity_edges(mask, intensity_edge_map(bgr))
    cv2 = _cv2()
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    comps = []
    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:4]:
        public = _contour_public(contour, width, height)
        if public is None:
            continue
        comps.append(public)
    return comps, whole, mask


def observe_pool_object(
    media_id: str,
    image_bytes: bytes,
    *,
    clip_scores: dict[str, float] | None = None,
    viewpoint: str | None = None,
) -> PoolObjectObservation:
    bgr = _bgr_from_bytes(image_bytes)
    # Viewpoint labels come from frozen PR #8 classify_viewpoint. This module
    # does not retune those rules; it only consumes the frozen label.
    if viewpoint is None:
        vp, scores = classify_viewpoint(bgr, clip_scores=clip_scores)
    else:
        vp, scores = viewpoint, dict(clip_scores or {})

    notes: list[str] = []
    if vp in SKIP_OBJECT_VIEWPOINTS:
        notes.append(f"skipped_object_extraction_viewpoint={vp}")
        return PoolObjectObservation(
            media_id=media_id,
            viewpoint=vp,
            viewpoint_scores=scores,
            pool_object_detected=False,
            geometry_class="no_usable_pool_geometry",
            full_boundary_recovered=False,
            partial_object=False,
            component_count=0,
            contour_quality=0.0,
            edge_clip=0.0,
            shape_eligible=False,
            spatial_eligible=False,
            scale_eligible=False,
            house_visible=False,
            notes=notes,
        )

    comps, whole, mask = extract_pool_object_components(image_bytes)
    detected = bool(comps) and float(whole.get("pool") or 0.0) >= 0.10
    if not detected:
        comps = []
        notes.append("clip_pool_object_not_detected")
    geom_class = classify_geometry(
        detected=detected,
        comps=comps,
        clip_pool=float(whole.get("pool") or 0.0),
        viewpoint=vp,
    )
    dominant = comps[0] if comps else None
    quality = 0.0 if dominant is None else _quality(dominant, float(whole.get("pool") or 0.0), geom_class)
    l_geom = {}
    if dominant is not None:
        l_geom = rectilinear_compound_geometry(dominant["_contour"], bgr.shape[1], bgr.shape[0])
        if len(comps) >= 2:
            l_geom["component_count"] = len(comps)
            # Adjacent components can be two arms of a compound rectilinear pool.
            c0, c1 = comps[0]["centroid_xy"], comps[1]["centroid_xy"]
            sep = math.hypot(c0[0] - c1[0], c0[1] - c1[1])
            l_geom["second_component_separation"] = round(sep, 4)
            if sep <= 0.35:
                l_geom["two_dominant_arms"] = True

    house = None
    if vp not in BLOCKED_SPATIAL:
        house = _roof_centroid(bgr, mask if mask.max() else None)

    usable = geom_class in {"full_pool_planform", "partial_pool_boundary"} and quality >= 0.28
    shape_ok = vp in SHAPE_VIEWPOINTS and usable
    spatial_ok = (
        vp in SPATIAL_VIEWPOINTS
        and usable
        and house is not None
        and dominant is not None
        and float(dominant["relative_area"]) <= 0.28
        and float(dominant["relative_area"]) >= 0.008
    )
    scale_ok = False
    ratio = None
    if vp in SCALE_VIEWPOINTS and usable and house is not None and dominant is not None:
        if 0.008 <= float(dominant["relative_area"]) <= 0.20:
            scale_ok = True
            ratio = _pool_roof_ratio(bgr, dominant["_contour"])

    dist = angle = dx = dy = nearest = None
    hx = hy = None
    fp = None
    if dominant is not None and usable:
        cx, cy = dominant["centroid_xy"]
        if house is not None and spatial_ok:
            hx, hy = house
            dx = cx - hx
            dy = cy - hy
            dist = float(math.hypot(dx, dy))
            angle = float(math.degrees(math.atan2(dy, dx)))
            nearest = _nearest_edge_norm(dominant["_contour"], house, bgr.shape[1], bgr.shape[0])
        fp = PoolGeometryFingerprint(
            present=True,
            unknown=False,
            shape_class=dominant["shape_class"],
            aspect_ratio=dominant["aspect_ratio"],
            orientation_deg=dominant.get("orientation_deg"),
            compactness=dominant["compactness"],
            rectangularity=dominant["rectangularity"],
            convexity=dominant["convexity"],
            relative_area=dominant["relative_area"],
            centroid_x=cx,
            centroid_y=cy,
            house_centroid_x=None if hx is None else round(hx, 4),
            house_centroid_y=None if hy is None else round(hy, 4),
            pool_to_house_dx=None if dx is None else round(dx, 4),
            pool_to_house_dy=None if dy is None else round(dy, 4),
            pool_to_house_dist=None if dist is None else round(dist, 4),
            pool_to_house_angle_deg=None if angle is None else round(angle, 2),
            contour_normalized=dominant["contour_normalized"],
            contour_image=dominant["contour_image"],
            evidence_media_id=media_id,
            notes=["listing_pool_object_colour_independent", f"geometry_class={geom_class}"],
        )

    clean_comps = [{k: v for k, v in item.items() if k != "_contour"} for item in comps]
    clean_dom = None if dominant is None else {k: v for k, v in dominant.items() if k != "_contour"}
    return PoolObjectObservation(
        media_id=media_id,
        viewpoint=vp,
        viewpoint_scores=scores,
        pool_object_detected=detected,
        geometry_class=geom_class,
        full_boundary_recovered=geom_class == "full_pool_planform",
        partial_object=geom_class == "partial_pool_boundary",
        component_count=len(comps),
        contour_quality=quality,
        edge_clip=0.0 if dominant is None else float(dominant["edge_clip"]),
        shape_eligible=bool(shape_ok),
        spatial_eligible=bool(spatial_ok),
        scale_eligible=bool(scale_ok),
        house_visible=house is not None,
        pool_to_house_dist=None if dist is None else round(dist, 4),
        pool_to_house_angle_deg=None if angle is None else round(angle, 2),
        pool_to_house_dx=None if dx is None else round(dx, 4),
        pool_to_house_dy=None if dy is None else round(dy, 4),
        nearest_pool_building_edge=nearest,
        pool_orientation_deg=None if dominant is None else dominant.get("orientation_deg"),
        pool_roof_ratio=ratio,
        l_geometry=l_geom,
        dominant=clean_dom,
        components=clean_comps,
        notes=notes,
        fingerprint=fp,
        contour_image=[] if dominant is None else dominant["contour_image"],
    )


def _nearest_edge_norm(
    contour: np.ndarray,
    house: tuple[float, float],
    width: int,
    height: int,
) -> float | None:
    pts = contour.reshape(-1, 2).astype(np.float64)
    if len(pts) == 0:
        return None
    hx, hy = house[0] * (width - 1), house[1] * (height - 1)
    dist = float(np.min(np.hypot(pts[:, 0] - hx, pts[:, 1] - hy)))
    span = float(np.max(np.linalg.norm(pts - pts.mean(axis=0), axis=1))) or 1.0
    return round(dist / span, 4)


def _pool_roof_ratio(bgr: np.ndarray, contour: np.ndarray) -> float | None:
    cv2 = _cv2()
    height, width = bgr.shape[:2]
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    threshold = float(np.percentile(gray, 74))
    roof = (gray >= threshold).astype(np.uint8)
    mask = np.zeros((height, width), np.uint8)
    cv2.drawContours(mask, [contour], -1, 255, -1)
    roof[mask > 0] = 0
    pool_px = float((mask > 0).sum())
    roof_px = float(roof.sum())
    frame = float(max(width * height, 1))
    if pool_px < 40 or roof_px < max(80.0, 0.04 * frame):
        return None
    if pool_px / frame > 0.22:
        return None
    return round(pool_px / max(roof_px, 1.0), 4)


def observation_public(obs: PoolObjectObservation) -> dict[str, Any]:
    dominant = None
    if obs.dominant is not None:
        dominant = {k: v for k, v in obs.dominant.items() if k not in {"contour_image", "contour_normalized", "descriptors"}}
    return {
        "media_id": obs.media_id,
        "viewpoint": obs.viewpoint,
        "pool_object_detected": obs.pool_object_detected,
        "geometry_class": obs.geometry_class,
        "full_boundary_recovered": obs.full_boundary_recovered,
        "partial_object": obs.partial_object,
        "component_count": obs.component_count,
        "contour_quality": obs.contour_quality,
        "edge_clip": obs.edge_clip,
        "shape_eligible": obs.shape_eligible,
        "spatial_eligible": obs.spatial_eligible,
        "scale_eligible": obs.scale_eligible,
        "house_visible": obs.house_visible,
        "pool_to_house_dist": obs.pool_to_house_dist,
        "pool_to_house_angle_deg": obs.pool_to_house_angle_deg,
        "nearest_pool_building_edge": obs.nearest_pool_building_edge,
        "pool_orientation_deg": obs.pool_orientation_deg,
        "pool_roof_ratio": obs.pool_roof_ratio,
        "l_geometry": obs.l_geometry,
        "dominant": dominant,
        "notes": obs.notes,
    }


def quality_gate(observations: list[PoolObjectObservation]) -> dict[str, Any]:
    """Rerank only if at least one genuinely usable pool boundary exists."""
    usable = [
        obs
        for obs in observations
        if obs.shape_eligible
        and obs.geometry_class in {"full_pool_planform", "partial_pool_boundary"}
        and obs.fingerprint is not None
        and obs.contour_quality >= 0.28
    ]
    full = [obs for obs in usable if obs.geometry_class == "full_pool_planform"]
    chosen = None
    if full:
        chosen = max(full, key=lambda obs: obs.contour_quality)
    elif usable:
        chosen = max(usable, key=lambda obs: obs.contour_quality)
    return {
        "passed": chosen is not None,
        "reason": "usable_pool_boundary" if chosen is not None else "no_usable_pool_boundary",
        "n_usable": len(usable),
        "n_full_planform": len(full),
        "chosen_id": None if chosen is None else chosen.media_id,
        "chosen_class": None if chosen is None else chosen.geometry_class,
        "chosen_quality": None if chosen is None else chosen.contour_quality,
        "usable_ids": [obs.media_id for obs in usable],
    }


def scoring_fingerprint(observations: list[PoolObjectObservation], gate: dict[str, Any]) -> PoolGeometryFingerprint | None:
    if not gate.get("passed"):
        return None
    by_id = {obs.media_id: obs for obs in observations}
    chosen = by_id.get(gate.get("chosen_id"))
    if chosen is None:
        return None
    return chosen.fingerprint
