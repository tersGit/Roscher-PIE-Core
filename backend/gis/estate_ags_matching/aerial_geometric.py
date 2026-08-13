"""Lightweight structural roof/building layout from nadir or oblique RGB."""

from __future__ import annotations

import io
import math
from dataclasses import dataclass

import numpy as np
from PIL import Image


@dataclass(frozen=True)
class StructuralLayout:
    roof_cx: float | None
    roof_cy: float | None
    roof_orientation_deg: float | None
    roof_aspect: float | None
    roof_area_frac: float | None
    paved_frac: float | None


def _cv2():
    import cv2

    return cv2


def extract_structural_layout(image_bytes: bytes) -> StructuralLayout:
    cv2 = _cv2()
    array = np.frombuffer(image_bytes, dtype=np.uint8)
    bgr = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if bgr is None:
        rgb = np.array(Image.open(io.BytesIO(image_bytes)).convert("RGB"))
        bgr = rgb[:, :, ::-1].copy()
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    height, width = gray.shape
    roof = (gray >= np.percentile(gray, 74)).astype(np.uint8) * 255
    roof = cv2.morphologyEx(roof, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    contours, _ = cv2.findContours(roof, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best = None
    for contour in contours:
        area = float(cv2.contourArea(contour))
        if best is None or area > best[0]:
            best = (area, contour)
    cx = cy = orient = aspect = frac = None
    if best is not None and best[0] > gray.size * 0.01:
        area, contour = best
        moments = cv2.moments(contour)
        if moments["m00"] > 1e-6:
            cx = float(moments["m10"] / moments["m00"] / max(width - 1, 1))
            cy = float(moments["m01"] / moments["m00"] / max(height - 1, 1))
        rect = cv2.minAreaRect(contour)
        (_, _), (rw, rh), angle = rect
        orient = float(angle % 180.0)
        aspect = float(max(rw, rh) / max(min(rw, rh), 1e-3))
        frac = float(area / max(width * height, 1))
    paved = cv2.inRange(hsv, np.array([0, 0, 40]), np.array([40, 60, 160]))
    paved_frac = float(np.count_nonzero(paved) / max(paved.size, 1))
    return StructuralLayout(cx, cy, orient, aspect, frac, paved_frac)


def structural_layout_similarity(left: StructuralLayout | None, right: StructuralLayout | None) -> float | None:
    if left is None or right is None:
        return None
    scores = []
    if left.roof_aspect and right.roof_aspect:
        scores.append(min(left.roof_aspect, right.roof_aspect) / max(left.roof_aspect, right.roof_aspect))
    if left.roof_orientation_deg is not None and right.roof_orientation_deg is not None:
        diff = abs(left.roof_orientation_deg - right.roof_orientation_deg) % 180.0
        diff = min(diff, 180.0 - diff)
        scores.append(max(0.0, 1.0 - diff / 90.0))
    if left.roof_area_frac and right.roof_area_frac:
        scores.append(min(left.roof_area_frac, right.roof_area_frac) / max(left.roof_area_frac, right.roof_area_frac))
    if left.paved_frac is not None and right.paved_frac is not None:
        scores.append(1.0 - min(1.0, abs(left.paved_frac - right.paved_frac) / 0.35))
    if not scores:
        return None
    return round(float(sum(scores) / len(scores)), 4)
