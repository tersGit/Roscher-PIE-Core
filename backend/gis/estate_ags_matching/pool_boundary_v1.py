"""Pool Boundary Extraction v1 — listing-photo coping/perimeter.

Stage A: is a swimming pool present? (CLIP object class + frozen viewpoint)
Stage B: given presence, recover the physical perimeter from structure
(coping, deck-to-pool edges, corners, LSD segments). Water colour is not
used to define the polygon.

Does not modify production ranking, OS v1, Scoring v2, native15 crops,
Listing Evidence v2 viewpoint gates, or PR #10 object-heatmap code.
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
    classify_viewpoint,
)
from backend.gis.estate_ags_matching.os_scoring_v2 import contour_descriptors
from backend.gis.estate_ags_matching.pool_geometry import _bgr_from_bytes, _resample_contour
from backend.vision.object_segmentation import FASTSAM_WEIGHTS

PROPOSAL_KEYS = ("pool", "wall", "vegetation", "furniture", "bathtub", "interior", "deck")
PROPOSAL_LABELS = (
    "a swimming pool or jacuzzi water feature in a backyard",
    "a house exterior wall pillar window or balcony",
    "trees hedges or garden vegetation",
    "outdoor furniture chairs table or patio heater",
    "a bathtub or bathroom shower interior",
    "an interior living room or landing",
    "paving timber deck or pool coping stones",
)

OVERVIEW_VIEWS = frozenset({"pool_overview", "elevated_exterior", "ground_level_exterior", "aerial_near_nadir"})
SKIP_VIEWS = frozenset({"interior", "unusable_ambiguous"})


def _cv2():
    import cv2

    return cv2


@dataclass
class BoundaryProposal:
    method: str
    contour: np.ndarray
    mask: np.ndarray | None
    pool_clip: float
    wall_clip: float
    veg_clip: float
    furniture_clip: float
    bathtub_clip: float
    structural_support: float
    edge_clip: float
    closed: bool
    wall_climb: bool
    relative_area: float
    descriptors: dict[str, Any]
    rectification: dict[str, Any]
    accepted: bool
    reject_reason: str | None
    confidence: float
    notes: list[str] = field(default_factory=list)


@dataclass
class FrameBoundary:
    media_id: str
    viewpoint: str
    pool_present: bool
    proposals: list[BoundaryProposal]
    best: BoundaryProposal | None
    scoring_ready: bool
    gate_reasons: list[str]
    accepted_segments: np.ndarray | None = None
    rejected_segments: np.ndarray | None = None


def _resize_mask(mask: np.ndarray, width: int, height: int) -> np.ndarray:
    cv2 = _cv2()
    return cv2.resize(mask.astype(np.uint8), (width, height), interpolation=cv2.INTER_NEAREST).astype(bool)


_fastsam = None


def _load_fastsam():
    global _fastsam
    if _fastsam is not None:
        return _fastsam
    from ultralytics import FastSAM

    path = str(FASTSAM_WEIGHTS if FASTSAM_WEIGHTS.is_file() else "FastSAM-s.pt")
    _fastsam = FastSAM(path)
    return _fastsam


def fastsam_masks(bgr: np.ndarray) -> list[np.ndarray]:
    height, width = bgr.shape[:2]
    result = _load_fastsam().predict(
        bgr, device="cpu", imgsz=512, retina_masks=True, verbose=False, save=False
    )[0]
    if result.masks is None:
        return []
    raw = result.masks.data.cpu().numpy()
    return [_resize_mask(item, width, height) for item in raw]


def _encode_images(images: list[Image.Image], batch: int = 16) -> np.ndarray:
    from backend.vision.clip_encoder import load_clip

    model, preprocess, _, torch = load_clip()
    if not images:
        return np.zeros((0, 512), np.float32)
    chunks = []
    for start in range(0, len(images), batch):
        tensor = torch.stack([preprocess(im.convert("RGB")) for im in images[start : start + batch]])
        with torch.no_grad():
            feat = model.encode_image(tensor)
            feat = feat / feat.norm(dim=-1, keepdim=True)
        chunks.append(feat.detach().cpu().numpy())
    return np.concatenate(chunks, axis=0)


@lru_cache(maxsize=1)
def _proposal_text() -> np.ndarray:
    from backend.vision.clip_encoder import load_clip

    model, _, tokenizer, torch = load_clip()
    text = tokenizer(list(PROPOSAL_LABELS))
    with torch.no_grad():
        feat = model.encode_text(text)
        feat = feat / feat.norm(dim=-1, keepdim=True)
    return feat.detach().cpu().numpy()


def clip_softmax(feat: np.ndarray) -> dict[str, float]:
    text = _proposal_text()
    if feat.ndim == 1:
        feat = feat[None, :]
    logits = 100.0 * feat @ text.T
    logits = logits - logits.max(axis=1, keepdims=True)
    exp = np.exp(logits)
    prob = exp / np.clip(exp.sum(axis=1, keepdims=True), 1e-9, None)
    return {key: round(float(prob[0, i]), 4) for i, key in enumerate(PROPOSAL_KEYS)}


def clip_crop_scores(bgr: np.ndarray, mask: np.ndarray) -> dict[str, float]:
    cv2 = _cv2()
    ys, xs = np.where(mask)
    if len(xs) < 20:
        return {key: 0.0 for key in PROPOSAL_KEYS}
    y0, y1 = max(0, ys.min() - 8), min(bgr.shape[0], ys.max() + 8)
    x0, x1 = max(0, xs.min() - 8), min(bgr.shape[1], xs.max() + 8)
    crop = cv2.cvtColor(bgr[y0:y1, x0:x1], cv2.COLOR_BGR2RGB)
    image = Image.fromarray(crop)
    feat = _encode_images([image])[0]
    return clip_softmax(feat)


def grayscale_edges(bgr: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Intensity structure only — not a water-hue classifier."""
    cv2 = _cv2()
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    gray_s = cv2.GaussianBlur(gray, (5, 5), 0)
    mag_x = cv2.Sobel(gray_s, cv2.CV_32F, 1, 0, ksize=3)
    mag_y = cv2.Sobel(gray_s, cv2.CV_32F, 0, 1, ksize=3)
    mag = np.hypot(mag_x, mag_y)
    canny = cv2.Canny(gray_s, 50, 140)
    return gray_s, mag, canny


def detect_segments(gray: np.ndarray) -> np.ndarray:
    cv2 = _cv2()
    lsd = cv2.createLineSegmentDetector(cv2.LSD_REFINE_STD)
    detected = lsd.detect(gray)
    if not detected or detected[0] is None:
        return np.zeros((0, 4), np.float32)
    return np.asarray(detected[0], np.float32).reshape(-1, 4)


def _contour_from_mask(mask: np.ndarray) -> np.ndarray | None:
    cv2 = _cv2()
    binary = (mask.astype(np.uint8)) * 255
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    return max(contours, key=cv2.contourArea)


def coping_ring(mask: np.ndarray, inner: int = 2, outer: int = 22) -> np.ndarray:
    cv2 = _cv2()
    u8 = mask.astype(np.uint8) * 255
    dil = cv2.dilate(u8, np.ones((outer, outer), np.uint8))
    ero = cv2.erode(u8, np.ones((max(inner, 1), max(inner, 1)), np.uint8))
    return ((dil > 0) & (ero == 0)).astype(np.uint8) * 255


def segments_in_ring(segments: np.ndarray, ring: np.ndarray) -> np.ndarray:
    if len(segments) == 0:
        return segments
    height, width = ring.shape
    kept = []
    for x1, y1, x2, y2 in segments:
        mx, my = int((x1 + x2) / 2), int((y1 + y2) / 2)
        if 0 <= mx < width and 0 <= my < height and ring[my, mx] > 0:
            kept.append((x1, y1, x2, y2))
    return np.asarray(kept, np.float32).reshape(-1, 4) if kept else np.zeros((0, 4), np.float32)


def reject_wall_segments(segments: np.ndarray, mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Drop near-vertical segments that climb above the pool object."""
    if len(segments) == 0:
        return segments, np.zeros((0, 4), np.float32)
    ys, xs = np.where(mask)
    top = float(ys.min()) if len(ys) else 0.0
    mid_y = float(ys.mean()) if len(ys) else 0.0
    keep, drop = [], []
    for x1, y1, x2, y2 in segments:
        dx, dy = x2 - x1, y2 - y1
        ang = abs(math.degrees(math.atan2(dy, dx)))
        vertical = min(abs(ang - 90.0), abs(ang - 270.0)) <= 22.0
        y_min = min(y1, y2)
        climbs = vertical and y_min < top + 0.08 * mask.shape[0] and y_min < mid_y - 12
        if climbs:
            drop.append((x1, y1, x2, y2))
        else:
            keep.append((x1, y1, x2, y2))
    kept = np.asarray(keep, np.float32).reshape(-1, 4) if keep else np.zeros((0, 4), np.float32)
    dropped = np.asarray(drop, np.float32).reshape(-1, 4) if drop else np.zeros((0, 4), np.float32)
    return kept, dropped


def chain_segments_to_contour(segments: np.ndarray, width: int, height: int) -> np.ndarray | None:
    """Greedy endpoint chaining into a closed-ish polyline. Generic, not shape-classed."""
    if len(segments) < 3:
        return None
    segs = [((float(x1), float(y1)), (float(x2), float(y2))) for x1, y1, x2, y2 in segments]
    used = [False] * len(segs)
    start = 0
    used[start] = True
    pts = [segs[start][0], segs[start][1]]
    for _ in range(len(segs) - 1):
        tail = pts[-1]
        best_i, best_d, best_end = -1, 18.0, None
        for i, (a, b) in enumerate(segs):
            if used[i]:
                continue
            da = math.hypot(tail[0] - a[0], tail[1] - a[1])
            db = math.hypot(tail[0] - b[0], tail[1] - b[1])
            if da < best_d:
                best_i, best_d, best_end = i, da, b
            if db < best_d:
                best_i, best_d, best_end = i, db, a
        if best_i < 0:
            break
        used[best_i] = True
        pts.append(best_end)
    if len(pts) < 4:
        return None
    arr = np.array(pts, np.int32).reshape(-1, 1, 2)
    return arr


def local_ridge_snap(contour: np.ndarray, mag: np.ndarray, gx: np.ndarray, gy: np.ndarray, max_r: int = 16) -> np.ndarray:
    """Move each vertex a short distance along its outward normal to an intensity ridge."""
    pts = contour.reshape(-1, 2).astype(np.float32)
    if len(pts) < 5:
        return contour
    nxt = np.roll(pts, -1, axis=0)
    tan = nxt - pts
    tan /= np.clip(np.linalg.norm(tan, axis=1, keepdims=True), 1e-6, None)
    nrm = np.stack([tan[:, 1], -tan[:, 0]], axis=1)
    centre = pts.mean(axis=0)
    inward = ((centre - pts) * nrm).sum(axis=1) > 0
    nrm[inward] *= -1
    height, width = mag.shape
    out = np.zeros_like(pts)
    for i, (p, n) in enumerate(zip(pts, nrm)):
        best_s, best = 0.0, -1.0
        for step in range(0, max_r + 1):
            x = int(round(p[0] + n[0] * step))
            y = int(round(p[1] + n[1] * step))
            if x < 1 or y < 1 or x >= width - 1 or y >= height - 1:
                break
            g = np.array([gx[y, x], gy[y, x]], np.float32)
            gnorm = float(np.linalg.norm(g)) + 1e-6
            align = abs(float(np.dot(g, n))) / gnorm
            score = float(mag[y, x]) * (0.4 + 0.6 * align)
            if score > best:
                best, best_s = score, float(step)
        out[i] = p + n * best_s
    return out.reshape(-1, 1, 2).astype(np.int32)


def wall_climb_fraction(contour: np.ndarray, mask: np.ndarray) -> float:
    ys, xs = np.where(mask)
    if len(ys) == 0:
        return 1.0
    top = float(ys.min())
    pts = contour.reshape(-1, 2)
    if len(pts) == 0:
        return 1.0
    climbed = (pts[:, 1] < top - 4).mean()
    return float(climbed)


def edge_clip_frac(contour: np.ndarray, width: int, height: int) -> float:
    pts = contour.reshape(-1, 2)
    if len(pts) == 0:
        return 1.0
    return float(
        ((pts[:, 0] <= 2) | (pts[:, 0] >= width - 3) | (pts[:, 1] <= 2) | (pts[:, 1] >= height - 3)).mean()
    )


def structural_support_frac(contour: np.ndarray, segments: np.ndarray, max_dist: float = 6.0) -> float:
    if len(segments) == 0:
        return 0.0
    pts = contour.reshape(-1, 2).astype(np.float32)
    if len(pts) < 3:
        return 0.0
    nxt = np.roll(pts, -1, axis=0)
    mid = 0.5 * (pts + nxt)
    tan = nxt - pts
    ang = (np.degrees(np.arctan2(tan[:, 1], tan[:, 0])) + 180.0) % 180.0
    hits = 0
    for m, a in zip(mid, ang):
        ok = False
        for x1, y1, x2, y2 in segments:
            cx, cy = 0.5 * (x1 + x2), 0.5 * (y1 + y2)
            if math.hypot(m[0] - cx, m[1] - cy) > max_dist + 0.5 * math.hypot(x2 - x1, y2 - y1):
                continue
            sa = (math.degrees(math.atan2(y2 - y1, x2 - x1)) + 180.0) % 180.0
            delta = min(abs(a - sa), 180.0 - abs(a - sa))
            if delta <= 18.0:
                ok = True
                break
        hits += int(ok)
    return float(hits / max(len(mid), 1))


def vanishing_rectification(segments: np.ndarray, contour: np.ndarray, width: int, height: int) -> dict[str, Any]:
    """Attempt a local pool-plane homography from two line families. Generic."""
    empty = {"reliable": False, "reason": "insufficient_structural_lines", "confidence": 0.0}
    if len(segments) < 6 or contour is None or len(contour) < 4:
        return empty
    cv2 = _cv2()
    angs = []
    for x1, y1, x2, y2 in segments:
        angs.append((math.degrees(math.atan2(y2 - y1, x2 - x1)) + 180.0) % 180.0)
    angs = np.asarray(angs)
    # Two circular clusters around median and median+90.
    a0 = float(np.median(angs))
    fam_a = segments[np.array([min(abs(a - a0), 180 - abs(a - a0)) <= 20 for a in angs])]
    fam_b = segments[np.array([min(abs(a - a0), 180 - abs(a - a0)) > 20 for a in angs])]
    if len(fam_a) < 3 or len(fam_b) < 3:
        return {**empty, "reason": "no_two_line_families"}
    rect = cv2.minAreaRect(contour.reshape(-1, 2).astype(np.float32))
    box = cv2.boxPoints(rect).astype(np.float32)
    dst = np.array([[0, 0], [200, 0], [200, 120], [0, 120]], np.float32)
    try:
        hmat = cv2.getPerspectiveTransform(box, dst)
        warped = cv2.perspectiveTransform(contour.reshape(-1, 1, 2).astype(np.float32), hmat)
    except cv2.error:
        return {**empty, "reason": "homography_failed"}
    # minAreaRect-from-contour is a weak plane estimate; treat as low-confidence
    # unless the two families are near-orthogonal.
    b0 = float(np.median(
        [(math.degrees(math.atan2(y2 - y1, x2 - x1)) + 180.0) % 180.0 for x1, y1, x2, y2 in fam_b]
    ))
    delta = min(abs(b0 - a0), 180.0 - abs(b0 - a0))
    reliable = 70.0 <= delta <= 110.0 and len(fam_a) >= 4 and len(fam_b) >= 4
    desc = contour_descriptors(warped.reshape(-1, 2) / np.array([200.0, 120.0]))
    return {
        "reliable": bool(reliable),
        "reason": "orthogonal_line_families" if reliable else "weak_minarea_proxy",
        "confidence": round(0.55 if reliable else 0.18, 3),
        "principal_angle_delta_deg": round(float(delta), 1),
        "rectified_descriptors": None if desc is None else {k: v for k, v in desc.items() if k != "norm_xy"},
        "oblique": not reliable,
    }


def geometry_bundle(contour: np.ndarray, width: int, height: int) -> dict[str, Any]:
    cv2 = _cv2()
    pts = contour.reshape(-1, 2)
    area = float(cv2.contourArea(contour))
    peri = max(float(cv2.arcLength(contour, True)), 1.0)
    compactness = float(4.0 * math.pi * area / (peri * peri))
    hull = cv2.convexHull(contour)
    hull_area = max(float(cv2.contourArea(hull)), 1.0)
    solidity = float(area / hull_area)
    (_cx, _cy), (rw, rh), ang = cv2.minAreaRect(contour.astype(np.float32))
    aspect = float(max(rw, rh) / max(min(rw, rh), 1e-3))
    samples = _resample_contour(contour)
    desc = contour_descriptors(
        [[float(x) / max(width - 1, 1), float(y) / max(height - 1, 1)] for x, y in samples]
    ) or {}
    sharp = float(desc.get("sharp_frac") or 0.0)
    n_approx = int(len(cv2.approxPolyDP(contour, 0.02 * peri, True)))
    return {
        "relative_area": round(area / max(width * height, 1), 4),
        "compactness": round(compactness, 4),
        "solidity": round(solidity, 4),
        "aspect_ratio": round(aspect, 3),
        "orientation_deg": round(float(ang), 2),
        "n_corners": desc.get("n_corners"),
        "n_major_indents": desc.get("n_major_indents"),
        "max_indent": desc.get("max_indent"),
        "sharp_frac": desc.get("sharp_frac"),
        "circularity": desc.get("circularity"),
        "straight_edge_proportion": round(min(1.0, sharp * 2.2), 4),
        "curved_edge_proportion": round(max(0.0, 1.0 - min(1.0, sharp * 2.2)), 4),
        "n_approx": n_approx,
        "closed": True,
        "descriptors": {k: v for k, v in desc.items() if k != "norm_xy"},
        "contour_image": [
            [round(float(x) / max(width - 1, 1), 4), round(float(y) / max(height - 1, 1), 4)]
            for x, y in samples
        ],
    }


def score_and_gate(
    *,
    viewpoint: str,
    geom: dict[str, Any],
    clip: dict[str, float],
    structural_support: float,
    edge_clip: float,
    climb: float,
    corroborated: bool,
    method: str = "",
) -> tuple[bool, str | None, float, list[str]]:
    """Stricter generic gate. A large closed polygon is never sufficient.

    Multi-frame corroboration may raise confidence but must not promote a
    contour that fails structural or object-mask tests.
    """
    reasons = []
    pool = float(clip.get("pool") or 0.0)
    wall = float(clip.get("wall") or 0.0)
    veg = float(clip.get("vegetation") or 0.0)
    furn = float(clip.get("furniture") or 0.0)
    bath = float(clip.get("bathtub") or 0.0)
    interior = float(clip.get("interior") or 0.0)
    area = float(geom.get("relative_area") or 0.0)
    if viewpoint in SKIP_VIEWS:
        return False, "blocked_viewpoint", 0.0, ["blocked_viewpoint"]
    if viewpoint == "pool_closeup":
        return False, "closeup_not_overview", 0.0, ["closeup_not_overview"]
    if bath >= 0.22 and bath >= pool:
        return False, "bathtub_or_bathroom", 0.0, ["bathtub_or_bathroom"]
    if interior >= 0.30 and pool < 0.25:
        return False, "interior_scene", 0.0, ["interior_scene"]
    # Stage A object masks are not Stage B perimeters.
    if method == "fastsam_contour":
        reasons.append("object_mask_is_not_perimeter")
    if pool < 0.22:
        reasons.append("low_pool_object_confidence")
    if structural_support < 0.32:
        reasons.append("weak_structural_edge_support")
    if (wall + veg + furn) > pool + 0.05:
        reasons.append("contamination_exceeds_pool")
    if veg >= 0.28 and veg >= pool:
        reasons.append("vegetation_contour")
    if wall >= 0.30 and climb >= 0.08:
        reasons.append("wall_climb")
    if climb >= 0.12:
        reasons.append("contour_leaves_pool_object")
    if edge_clip >= 0.20:
        reasons.append("frame_edge_clipping")
    if area < 0.015 or area > 0.38:
        reasons.append("implausible_perimeter_area")
    # Corroboration never waives the structure floor.
    if structural_support < 0.48:
        reasons.append("needs_stronger_structure")
    # Large closed polygon with only CLIP/area: fail.
    if structural_support < 0.32:
        reasons.append("closed_polygon_without_structure")
    conf = (
        0.28 * min(1.0, pool / 0.40)
        + 0.34 * min(1.0, structural_support / 0.60)
        + 0.14 * max(0.0, 1.0 - edge_clip / 0.25)
        + 0.12 * max(0.0, 1.0 - climb / 0.15)
        + 0.12 * (1.0 if corroborated else 0.35)
    )
    conf = round(float(max(0.0, min(1.0, conf))), 4)
    accepted = not reasons and viewpoint in OVERVIEW_VIEWS and pool >= 0.22
    if accepted:
        notes = ["scoring_ready"]
        if corroborated:
            notes.append("multiframe_corroborated=True")
        return True, None, conf, notes
    return False, reasons[0] if reasons else "failed_gate", conf, reasons


def _proposal(
    method: str,
    contour: np.ndarray,
    mask: np.ndarray,
    bgr: np.ndarray,
    keep_seg: np.ndarray,
    mag_x: np.ndarray,
    mag_y: np.ndarray,
    mag: np.ndarray,
    clip: dict[str, float],
    corroborated: bool,
    viewpoint: str,
) -> BoundaryProposal:
    height, width = bgr.shape[:2]
    geom = geometry_bundle(contour, width, height)
    support = structural_support_frac(contour, keep_seg)
    clip_frac = edge_clip_frac(contour, width, height)
    climb = wall_climb_fraction(contour, mask)
    rect = vanishing_rectification(keep_seg, contour, width, height)
    accepted, reason, conf, notes = score_and_gate(
        viewpoint=viewpoint,
        geom=geom,
        clip=clip,
        structural_support=support,
        edge_clip=clip_frac,
        climb=climb,
        corroborated=corroborated,
        method=method,
    )
    return BoundaryProposal(
        method=method,
        contour=contour,
        mask=mask,
        pool_clip=float(clip.get("pool") or 0),
        wall_clip=float(clip.get("wall") or 0),
        veg_clip=float(clip.get("vegetation") or 0),
        furniture_clip=float(clip.get("furniture") or 0),
        bathtub_clip=float(clip.get("bathtub") or 0),
        structural_support=round(support, 4),
        edge_clip=round(clip_frac, 4),
        closed=True,
        wall_climb=climb >= 0.08,
        relative_area=geom["relative_area"],
        descriptors=geom,
        rectification=rect,
        accepted=accepted,
        reject_reason=reason,
        confidence=conf,
        notes=notes,
    )


def merge_masks(masks: list[np.ndarray]) -> np.ndarray | None:
    if not masks:
        return None
    out = np.zeros_like(masks[0], dtype=np.uint8)
    for mask in masks:
        out |= mask.astype(np.uint8)
    return out.astype(bool)


def extract_frame_boundary(
    media_id: str,
    image_bytes: bytes,
    *,
    viewpoint: str,
    clip_scores: dict[str, float] | None = None,
    corroborated: bool = False,
) -> FrameBoundary:
    bgr = _bgr_from_bytes(image_bytes)
    height, width = bgr.shape[:2]
    if viewpoint is None:
        viewpoint, clip_scores = classify_viewpoint(bgr, clip_scores=clip_scores)
    present = viewpoint not in SKIP_VIEWS
    if viewpoint in SKIP_VIEWS:
        return FrameBoundary(media_id, viewpoint, False, [], None, False, ["blocked_viewpoint"])

    gray, mag, canny = grayscale_edges(bgr)
    cv2 = _cv2()
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    segments = detect_segments(gray)
    masks = fastsam_masks(bgr)

    scored_masks: list[tuple[float, np.ndarray, dict[str, float]]] = []
    for mask in masks:
        frac = float(mask.mean())
        if frac < 0.008 or frac > 0.55:
            continue
        scores = clip_crop_scores(bgr, mask)
        if scores["bathtub"] >= 0.28 and scores["bathtub"] >= scores["pool"]:
            continue
        if scores["interior"] >= 0.40 and scores["pool"] < 0.20:
            continue
        if scores["pool"] < 0.16 and scores["deck"] < 0.20:
            continue
        rank = scores["pool"] + 0.35 * scores["deck"] - 0.6 * scores["vegetation"] - 0.5 * scores["wall"]
        scored_masks.append((rank, mask, scores))
    scored_masks.sort(key=lambda item: -item[0])
    pool_masks = [m for r, m, s in scored_masks[:4] if s["pool"] >= 0.18 or (s["deck"] >= 0.22 and s["pool"] >= 0.12)]
    present = present and bool(pool_masks)
    if not pool_masks:
        return FrameBoundary(media_id, viewpoint, False, [], None, False, ["no_pool_object_proposal"])

    union = merge_masks(pool_masks[:3])
    clip = clip_crop_scores(bgr, union)
    ring = coping_ring(union)
    ring_seg = segments_in_ring(segments, ring)
    keep_seg, drop_seg = reject_wall_segments(ring_seg, union)
    raw_contour = _contour_from_mask(union)
    proposals: list[BoundaryProposal] = []

    if raw_contour is not None:
        proposals.append(
            _proposal("fastsam_contour", raw_contour, union, bgr, keep_seg, gx, gy, mag, clip, corroborated, viewpoint)
        )
        snapped = local_ridge_snap(raw_contour, mag, gx, gy, max_r=14)
        # Do not allow snap to travel onto walls: clip snapped points back if they left the dilated union.
        dil = cv2.dilate(union.astype(np.uint8) * 255, np.ones((25, 25), np.uint8))
        pts = snapped.reshape(-1, 2)
        for i, (x, y) in enumerate(pts):
            xi, yi = int(np.clip(x, 0, width - 1)), int(np.clip(y, 0, height - 1))
            if dil[yi, xi] == 0:
                pts[i] = raw_contour.reshape(-1, 2)[min(i, len(raw_contour) - 1)]
        snapped = pts.reshape(-1, 1, 2).astype(np.int32)
        proposals.append(
            _proposal("local_ridge_snap", snapped, union, bgr, keep_seg, gx, gy, mag, clip, corroborated, viewpoint)
        )

    chained = chain_segments_to_contour(keep_seg, width, height)
    if chained is not None:
        proposals.append(
            _proposal("coping_ring_lsd", chained, union, bgr, keep_seg, gx, gy, mag, clip, corroborated, viewpoint)
        )

    if not proposals:
        return FrameBoundary(media_id, viewpoint, present, [], None, False, ["no_perimeter_proposal"])

    best = _select_best(proposals)
    return FrameBoundary(
        media_id=media_id,
        viewpoint=viewpoint,
        pool_present=present,
        proposals=proposals,
        best=best,
        scoring_ready=bool(best.accepted),
        gate_reasons=best.notes,
        accepted_segments=keep_seg,
        rejected_segments=drop_seg,
    )


def _select_best(proposals: list[BoundaryProposal]) -> BoundaryProposal:
    """Prefer accepted structural perimeters over object-mask contours."""
    accepted = [p for p in proposals if p.accepted]
    pool = accepted or proposals
    return max(
        pool,
        key=lambda p: (
            int(p.accepted),
            0 if p.method == "fastsam_contour" else 1,
            p.structural_support,
            p.confidence,
        ),
    )


def corroborate_axes(frames: list[FrameBoundary]) -> dict[str, bool]:
    """Multi-frame support via dominant-axis agreement, not image-space merge."""
    usable = []
    for frame in frames:
        if frame.best is None or frame.viewpoint not in OVERVIEW_VIEWS:
            continue
        ang = frame.best.descriptors.get("orientation_deg")
        if ang is None:
            continue
        usable.append((frame.media_id, float(ang) % 180.0, frame.best.structural_support))
    flags = {frame.media_id: False for frame in frames}
    for i, (mid, ang, _sup) in enumerate(usable):
        partners = 0
        for j, (oid, oang, osup) in enumerate(usable):
            if i == j:
                continue
            delta = min(abs(ang - oang), 180.0 - abs(ang - oang), abs((ang + 90) % 180 - oang))
            if delta <= 22.0 and osup >= 0.20:
                partners += 1
        flags[mid] = partners >= 1
    return flags


def reapply_corroboration(frames: list[FrameBoundary], flags: dict[str, bool]) -> None:
    """Second pass: multi-frame axis agreement can raise a structurally decent contour."""
    for frame in frames:
        corr = bool(flags.get(frame.media_id, False))
        if not frame.proposals:
            continue
        updated: list[BoundaryProposal] = []
        for prop in frame.proposals:
            accepted, reason, conf, notes = score_and_gate(
                viewpoint=frame.viewpoint,
                geom=prop.descriptors,
                clip={
                    "pool": prop.pool_clip,
                    "wall": prop.wall_clip,
                    "vegetation": prop.veg_clip,
                    "furniture": prop.furniture_clip,
                    "bathtub": prop.bathtub_clip,
                    "interior": 0.0,
                },
                structural_support=prop.structural_support,
                edge_clip=prop.edge_clip,
                climb=0.12 if prop.wall_climb else 0.0,
                corroborated=corr,
                method=prop.method,
            )
            prop.accepted = accepted
            prop.reject_reason = reason
            prop.confidence = conf
            extra = [f"multiframe_corroborated={corr}"]
            prop.notes = notes + [item for item in extra if item not in notes]
            updated.append(prop)
        frame.proposals = updated
        frame.best = _select_best(updated)
        frame.scoring_ready = bool(frame.best.accepted)
        frame.gate_reasons = frame.best.notes


def listing_gate(frames: list[FrameBoundary]) -> dict[str, Any]:
    ready = [f for f in frames if f.scoring_ready and f.best is not None]
    overviews = [f for f in ready if f.viewpoint in {"pool_overview", "elevated_exterior", "aerial_near_nadir"}]
    chosen = None
    if overviews:
        chosen = max(overviews, key=lambda f: (f.best.structural_support, f.best.confidence))
    elif ready:
        chosen = max(ready, key=lambda f: (f.best.structural_support, f.best.confidence))
    return {
        "passed": chosen is not None,
        "n_scoring_ready": len(ready),
        "n_overview_ready": len(overviews),
        "chosen_id": None if chosen is None else chosen.media_id,
        "chosen_method": None if chosen is None else chosen.best.method,
        "chosen_confidence": None if chosen is None else chosen.best.confidence,
        "ready_ids": [f.media_id for f in ready],
        "note": "Visual inspection is still required before treating a pass as genuine.",
    }


def proposal_public(prop: BoundaryProposal | None) -> dict[str, Any] | None:
    if prop is None:
        return None
    return {
        "method": prop.method,
        "pool_clip": prop.pool_clip,
        "wall_clip": prop.wall_clip,
        "veg_clip": prop.veg_clip,
        "furniture_clip": prop.furniture_clip,
        "bathtub_clip": prop.bathtub_clip,
        "structural_support": prop.structural_support,
        "edge_clip": prop.edge_clip,
        "wall_climb": prop.wall_climb,
        "relative_area": prop.relative_area,
        "accepted": prop.accepted,
        "reject_reason": prop.reject_reason,
        "confidence": prop.confidence,
        "notes": prop.notes,
        "rectification": {k: v for k, v in prop.rectification.items() if k != "rectified_descriptors"}
        | {"rectified_descriptors": prop.rectification.get("rectified_descriptors")},
        "descriptors": {k: v for k, v in prop.descriptors.items() if k not in {"contour_image", "descriptors"}},
        "contour_image": prop.descriptors.get("contour_image"),
    }


def frame_public(frame: FrameBoundary) -> dict[str, Any]:
    return {
        "media_id": frame.media_id,
        "viewpoint": frame.viewpoint,
        "pool_present": frame.pool_present,
        "scoring_ready": frame.scoring_ready,
        "gate_reasons": frame.gate_reasons,
        "n_proposals": len(frame.proposals),
        "best": proposal_public(frame.best),
        "methods": [
            {
                "method": p.method,
                "accepted": p.accepted,
                "confidence": p.confidence,
                "structural_support": p.structural_support,
                "reject_reason": p.reject_reason,
                "wall_climb": p.wall_climb,
            }
            for p in frame.proposals
        ],
    }
