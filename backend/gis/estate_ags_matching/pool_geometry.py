"""Numerical swimming-pool geometry fingerprints for experimental matching."""

from __future__ import annotations

import io
import math

import numpy as np
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field

POOL_GEOMETRY_VERSION = "1.0.0"
NORMALIZED_POINTS = 64
MIN_POOL_AREA_FRACTION = 0.002
MAX_POOL_AREA_FRACTION = 0.45


class PoolGeometryFingerprint(BaseModel):
    model_config = ConfigDict(frozen=True)

    present: bool = False
    unknown: bool = True
    shape_class: str = "unknown"
    aspect_ratio: float | None = None
    orientation_deg: float | None = None
    compactness: float | None = None
    rectangularity: float | None = None
    convexity: float | None = None
    curved_section_count: int = 0
    relative_area: float | None = None
    centroid_x: float | None = None
    centroid_y: float | None = None
    house_centroid_x: float | None = None
    house_centroid_y: float | None = None
    pool_to_house_dx: float | None = None
    pool_to_house_dy: float | None = None
    pool_to_house_dist: float | None = None
    pool_to_house_angle_deg: float | None = None
    contour_normalized: list[list[float]] = Field(default_factory=list)
    contour_image: list[list[float]] = Field(default_factory=list)
    evidence_media_id: str | None = None
    notes: list[str] = Field(default_factory=list)


def _cv2():
    import cv2

    return cv2


def _bgr_from_bytes(image_bytes: bytes) -> np.ndarray:
    cv2 = _cv2()
    array = np.frombuffer(image_bytes, dtype=np.uint8)
    decoded = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if decoded is None:
        rgb = np.array(Image.open(io.BytesIO(image_bytes)).convert("RGB"))
        return rgb[:, :, ::-1].copy()
    return decoded


def pool_mask(bgr: np.ndarray, extra_mask: np.ndarray | None = None) -> np.ndarray:
    cv2 = _cv2()
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    cyan = cv2.inRange(hsv, np.array([72, 40, 55]), np.array([145, 255, 255]))
    deep = cv2.inRange(hsv, np.array([90, 25, 40]), np.array([140, 255, 230]))
    mask = cv2.bitwise_or(cyan, deep)
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    if extra_mask is not None:
        mask = cv2.bitwise_and(mask, extra_mask)
    return mask


def _roof_centroid(bgr: np.ndarray, pool: np.ndarray | None) -> tuple[float, float] | None:
    gray = _cv2().cvtColor(bgr, _cv2().COLOR_BGR2GRAY)
    height, width = gray.shape
    threshold = float(np.percentile(gray, 74))
    roof = (gray >= threshold).astype(np.uint8) * 255
    if pool is not None:
        roof[pool > 0] = 0
    ys, xs = np.where(roof > 0)
    if len(xs) < max(40, gray.size * 0.01):
        return None
    return float(xs.mean() / max(width - 1, 1)), float(ys.mean() / max(height - 1, 1))


def _point_along_contour(contour: np.ndarray, distance: float) -> tuple[float, float]:
    pts = contour.reshape(-1, 2).astype(np.float32)
    if len(pts) < 2:
        return float(pts[0, 0]), float(pts[0, 1])
    segs = np.sqrt(((np.roll(pts, -1, axis=0) - pts) ** 2).sum(axis=1))
    travelled = 0.0
    remain = distance
    for i, length in enumerate(segs):
        if travelled + length >= remain:
            t = 0.0 if length <= 1e-6 else (remain - travelled) / length
            nxt = pts[(i + 1) % len(pts)]
            x = pts[i, 0] + t * (nxt[0] - pts[i, 0])
            y = pts[i, 1] + t * (nxt[1] - pts[i, 1])
            return float(x), float(y)
        travelled += length
        remain = distance
    return float(pts[-1, 0]), float(pts[-1, 1])


def _resample_contour(contour: np.ndarray, count: int = NORMALIZED_POINTS) -> np.ndarray:
    cv2 = _cv2()
    peri = float(cv2.arcLength(contour, True))
    if peri < 8:
        return np.zeros((count, 2), np.float32)
    step = peri / count
    return np.array([_point_along_contour(contour, i * step) for i in range(count)], dtype=np.float32)


def _normalize_contour(points: np.ndarray, *, align_major_axis: bool) -> list[list[float]]:
    if len(points) == 0:
        return []
    centered = points - points.mean(axis=0)
    if align_major_axis:
        cov = np.cov(centered.T)
        eigvals, eigvecs = np.linalg.eigh(cov)
        axis = eigvecs[:, int(np.argmax(eigvals))]
        angle = math.atan2(axis[1], axis[0])
        c, s = math.cos(-angle), math.sin(-angle)
        rot = np.array([[c, -s], [s, c]], dtype=np.float32)
        centered = centered @ rot.T
    scale = float(np.max(np.linalg.norm(centered, axis=1)))
    if scale < 1e-6:
        return [[0.0, 0.0] for _ in points]
    normalized = centered / scale
    return [[round(float(x), 4), round(float(y), 4)] for x, y in normalized]


def _shape_class(*, rectangularity: float, compactness: float, convexity: float, aspect: float) -> str:
    if rectangularity >= 0.78 and compactness >= 0.55 and aspect < 2.3:
        return "rectangular"
    if aspect >= 2.2 and rectangularity >= 0.68:
        return "elongated_rectangular"
    if convexity < 0.86 or compactness < 0.42:
        return "irregular"
    if compactness >= 0.7 and rectangularity < 0.72:
        return "rounded"
    return "kidney_or_curved"


def _curved_sections(contour: np.ndarray, hull: np.ndarray) -> int:
    cv2 = _cv2()
    if len(hull) < 3 or len(contour) < 5:
        return 0
    defects = cv2.convexityDefects(contour, cv2.convexHull(contour, returnPoints=False))
    if defects is None:
        return 0
    count = 0
    peri = max(float(cv2.arcLength(contour, True)), 1.0)
    for item in defects:
        rec = np.array(item).reshape(-1)
        if rec.size < 4:
            continue
        depth = float(rec[3]) / 256.0
        if depth > peri * 0.03:
            count += 1
    return count


def extract_pool_geometry(
    image_bytes: bytes,
    *,
    media_id: str | None = None,
    parcel_mask: np.ndarray | None = None,
) -> PoolGeometryFingerprint:
    cv2 = _cv2()
    bgr = _bgr_from_bytes(image_bytes)
    height, width = bgr.shape[:2]
    mask = pool_mask(bgr, extra_mask=parcel_mask)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    min_area = max(24.0, MIN_POOL_AREA_FRACTION * width * height)
    max_area = MAX_POOL_AREA_FRACTION * width * height
    best = None
    for contour in contours:
        area = float(cv2.contourArea(contour))
        if area < min_area or area > max_area:
            continue
        if best is None or area > best[0]:
            best = (area, contour)
    if best is None:
        return PoolGeometryFingerprint(present=False, unknown=False, evidence_media_id=media_id)

    area, contour = best
    peri = float(cv2.arcLength(contour, True))
    compactness = float(4.0 * math.pi * area / max(peri * peri, 1e-6))
    rect = cv2.minAreaRect(contour)
    (_, _), (rw, rh), angle = rect
    rect_area = max(float(rw * rh), 1e-6)
    rectangularity = float(area / rect_area)
    hull = cv2.convexHull(contour)
    hull_area = max(float(cv2.contourArea(hull)), 1e-6)
    convexity = float(area / hull_area)
    aspect = max(rw, rh) / max(min(rw, rh), 1e-3)
    moments = cv2.moments(contour)
    if moments["m00"] <= 1e-6:
        return PoolGeometryFingerprint(present=False, unknown=True, evidence_media_id=media_id)
    cx = float(moments["m10"] / moments["m00"] / max(width - 1, 1))
    cy = float(moments["m01"] / moments["m00"] / max(height - 1, 1))
    samples = _resample_contour(contour)
    house = _roof_centroid(bgr, mask)
    dx = dy = dist = rel_angle = None
    hx = hy = None
    if house is not None:
        hx, hy = house
        dx = cx - hx
        dy = cy - hy
        dist = float(math.hypot(dx, dy))
        rel_angle = float(math.degrees(math.atan2(dy, dx)))
    return PoolGeometryFingerprint(
        present=True,
        unknown=False,
        shape_class=_shape_class(
            rectangularity=rectangularity,
            compactness=compactness,
            convexity=convexity,
            aspect=float(aspect),
        ),
        aspect_ratio=round(float(aspect), 3),
        orientation_deg=round(float(angle) % 180.0, 2),
        compactness=round(compactness, 4),
        rectangularity=round(rectangularity, 4),
        convexity=round(convexity, 4),
        curved_section_count=_curved_sections(contour, hull),
        relative_area=round(float(area / max(width * height, 1)), 4),
        centroid_x=round(cx, 4),
        centroid_y=round(cy, 4),
        house_centroid_x=None if hx is None else round(hx, 4),
        house_centroid_y=None if hy is None else round(hy, 4),
        pool_to_house_dx=None if dx is None else round(dx, 4),
        pool_to_house_dy=None if dy is None else round(dy, 4),
        pool_to_house_dist=None if dist is None else round(dist, 4),
        pool_to_house_angle_deg=None if rel_angle is None else round(rel_angle, 2),
        contour_normalized=_normalize_contour(samples, align_major_axis=True),
        contour_image=[
            [round(float(x) / max(width - 1, 1), 4), round(float(y) / max(height - 1, 1), 4)]
            for x, y in samples
        ],
        evidence_media_id=media_id,
    )


def consensus_pool_fingerprint(items: list[PoolGeometryFingerprint]) -> PoolGeometryFingerprint:
    present = [item for item in items if item.present]
    if not present:
        return PoolGeometryFingerprint(present=False, unknown=True, notes=["no_pool_detected_on_listing"])

    def _median(attr: str) -> float | None:
        values = [getattr(item, attr) for item in present if getattr(item, attr) is not None]
        if not values:
            return None
        values = sorted(values)
        return float(values[len(values) // 2])

    classes = [item.shape_class for item in present]
    shape = max(set(classes), key=classes.count)
    contours = [item.contour_normalized for item in present if item.contour_normalized]
    contour = contours[0] if contours else []
    if len(contours) > 1:
        stacked = np.mean(
            [np.array(item, dtype=np.float32) for item in contours if len(item) == NORMALIZED_POINTS],
            axis=0,
        )
        contour = [[round(float(x), 4), round(float(y), 4)] for x, y in stacked]
    image_contours = [item.contour_image for item in present if item.contour_image]
    image_contour = image_contours[0] if image_contours else []
    notes = [f"consensus_from_{len(present)}_pool_frames"]
    return PoolGeometryFingerprint(
        present=True,
        unknown=False,
        shape_class=shape,
        aspect_ratio=_median("aspect_ratio"),
        orientation_deg=_median("orientation_deg"),
        compactness=_median("compactness"),
        rectangularity=_median("rectangularity"),
        convexity=_median("convexity"),
        curved_section_count=int(round(_median("curved_section_count") or 0)),
        relative_area=_median("relative_area"),
        centroid_x=_median("centroid_x"),
        centroid_y=_median("centroid_y"),
        house_centroid_x=_median("house_centroid_x"),
        house_centroid_y=_median("house_centroid_y"),
        pool_to_house_dx=_median("pool_to_house_dx"),
        pool_to_house_dy=_median("pool_to_house_dy"),
        pool_to_house_dist=_median("pool_to_house_dist"),
        pool_to_house_angle_deg=_median("pool_to_house_angle_deg"),
        contour_normalized=contour,
        contour_image=image_contour,
        evidence_media_id=present[0].evidence_media_id,
        notes=notes,
    )


def _angle_sim(left: float | None, right: float | None, period: float = 180.0) -> float | None:
    if left is None or right is None:
        return None
    diff = abs(left - right) % period
    diff = min(diff, period - diff)
    return max(0.0, 1.0 - diff / (period / 2))


def _ratio_sim(left: float | None, right: float | None) -> float | None:
    if left is None or right is None or left <= 0 or right <= 0:
        return None
    return min(left, right) / max(left, right)


def _vector_sim(ax: float | None, ay: float | None, bx: float | None, by: float | None) -> float | None:
    if None in {ax, ay, bx, by}:
        return None
    da = math.hypot(ax, ay)
    db = math.hypot(bx, by)
    if da < 0.02 and db < 0.02:
        return 1.0
    if da < 0.02 or db < 0.02:
        return 0.15
    cos = max(-1.0, min(1.0, (ax * bx + ay * by) / (da * db)))
    mag = min(da, db) / max(da, db)
    return float(max(0.0, 0.5 * (cos + 1.0) * mag))


def pool_geometry_similarity(listing: PoolGeometryFingerprint, candidate: PoolGeometryFingerprint) -> dict:
    if listing.present and (not candidate.present) and (not candidate.unknown):
        return {
            "status": "contradiction",
            "contradiction": "listing_has_pool_candidate_has_none",
            "pool_geometry_similarity": 0.0,
            "pool_house_similarity": None,
        }
    if not listing.present or not candidate.present:
        return {
            "status": "unknown",
            "contradiction": None,
            "pool_geometry_similarity": None,
            "pool_house_similarity": None,
        }
    parts = [
        _ratio_sim(listing.aspect_ratio, candidate.aspect_ratio),
        _angle_sim(listing.orientation_deg, candidate.orientation_deg),
        _ratio_sim(listing.compactness, candidate.compactness),
        _ratio_sim(listing.rectangularity, candidate.rectangularity),
        _ratio_sim(listing.convexity, candidate.convexity),
    ]
    usable = [item for item in parts if item is not None]
    geom = float(sum(usable) / max(len(usable), 1))
    if listing.shape_class != "unknown" and candidate.shape_class != "unknown":
        geom = 0.7 * geom + 0.3 * (1.0 if listing.shape_class == candidate.shape_class else 0.35)
    house = _vector_sim(
        listing.pool_to_house_dx,
        listing.pool_to_house_dy,
        candidate.pool_to_house_dx,
        candidate.pool_to_house_dy,
    )
    contradiction = None
    if house is not None and house < 0.2:
        contradiction = "pool_on_opposite_side_of_house"
    return {
        "status": "compared",
        "contradiction": contradiction,
        "pool_geometry_similarity": round(geom, 4),
        "pool_house_similarity": None if house is None else round(house, 4),
    }
