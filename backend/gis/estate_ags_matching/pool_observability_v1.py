"""Yard observability for inventory NO vs UNKNOWN.

Absence of a FastSAM pool candidate is not evidence of no pool unless the
likely backyard is adequately visible. This module does not score pools,
does not apply colour ranking rules, and does not change FastSAM / Hybrid /
Scoring v2.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
from PIL import Image, ImageDraw

PADDING_METRES = 18.0

# Fractions of the non-building parcel (yard) that block a confident NO.
MAX_CANOPY_FRACTION_FOR_NO = 0.38
MAX_SHADOW_FRACTION_FOR_NO = 0.32
MAX_ROOF_FRACTION_OF_PARCEL = 0.78
MIN_VISIBLE_OPEN_FRACTION_FOR_NO = 0.30
MIN_YARD_PIXELS_FOR_NO = 400
MIN_PARCEL_PIXELS = 800
MIN_CROP_SIDE_PX = 48
MIN_MEAN_VALUE_FOR_QUALITY = 38.0


@dataclass
class PoolObservability:
    adequate_for_absence: bool
    crop_present: bool
    imagery_quality_ok: bool
    backyard_observable: bool
    canopy_occludes: bool
    shadow_occludes: bool
    roof_occludes: bool
    visible_open_fraction: float
    canopy_fraction: float
    shadow_fraction: float
    roof_fraction: float
    yard_pixels: int
    parcel_pixels: int
    flags: list[str] = field(default_factory=list)
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "adequate_for_absence": self.adequate_for_absence,
            "crop_present": self.crop_present,
            "imagery_quality_ok": self.imagery_quality_ok,
            "backyard_observable": self.backyard_observable,
            "canopy_occludes": self.canopy_occludes,
            "shadow_occludes": self.shadow_occludes,
            "roof_occludes": self.roof_occludes,
            "visible_open_fraction": round(self.visible_open_fraction, 4),
            "canopy_fraction": round(self.canopy_fraction, 4),
            "shadow_fraction": round(self.shadow_fraction, 4),
            "roof_fraction": round(self.roof_fraction, 4),
            "yard_pixels": self.yard_pixels,
            "parcel_pixels": self.parcel_pixels,
            "flags": list(self.flags),
            "reason": self.reason,
        }


def missing_crop_observability(reason: str = "crop_missing") -> PoolObservability:
    return PoolObservability(
        adequate_for_absence=False,
        crop_present=False,
        imagery_quality_ok=False,
        backyard_observable=False,
        canopy_occludes=False,
        shadow_occludes=False,
        roof_occludes=False,
        visible_open_fraction=0.0,
        canopy_fraction=0.0,
        shadow_fraction=0.0,
        roof_fraction=0.0,
        yard_pixels=0,
        parcel_pixels=0,
        flags=["pool_observability_inadequate", "crop_missing_or_unassessed"],
        reason=reason,
    )


def load_rgb(path: Path | None) -> np.ndarray | None:
    if path is None or not Path(path).is_file():
        return None
    try:
        image = Image.open(path).convert("RGB")
    except (OSError, ValueError):
        return None
    return np.asarray(image, dtype=np.uint8)


def rgb_to_hsv_cv(rgb: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """OpenCV-compatible HSV: H in [0, 180), S/V in [0, 255]."""
    rgb_f = rgb.astype(np.float32) / 255.0
    red, green, blue = rgb_f[..., 0], rgb_f[..., 1], rgb_f[..., 2]
    maxc = np.maximum(np.maximum(red, green), blue)
    minc = np.minimum(np.minimum(red, green), blue)
    delta = maxc - minc
    value = maxc
    sat = np.where(maxc < 1e-8, 0.0, delta / np.maximum(maxc, 1e-8))
    hue = np.zeros_like(maxc)
    nz = delta > 1e-8
    red_max = nz & (maxc == red)
    green_max = nz & (maxc == green) & ~red_max
    blue_max = nz & ~red_max & ~green_max
    hue[red_max] = (60.0 * ((green[red_max] - blue[red_max]) / delta[red_max]) + 360.0) % 360.0
    hue[green_max] = (60.0 * ((blue[green_max] - red[green_max]) / delta[green_max]) + 120.0) % 360.0
    hue[blue_max] = (60.0 * ((red[blue_max] - green[blue_max]) / delta[blue_max]) + 240.0) % 360.0
    return hue / 2.0, sat * 255.0, value * 255.0


def rasterize_normalized_contour(
    contour: Sequence[Sequence[float]] | None,
    width: int,
    height: int,
) -> np.ndarray:
    mask = Image.new("L", (width, height), 0)
    if not contour or len(contour) < 3:
        return np.zeros((height, width), dtype=bool)
    pts = []
    for point in contour:
        if len(point) < 2:
            continue
        x = int(round(float(point[0]) * (width - 1)))
        y = int(round(float(point[1]) * (height - 1)))
        pts.append((x, y))
    if len(pts) >= 3:
        ImageDraw.Draw(mask).polygon(pts, fill=255)
    return np.asarray(mask, dtype=np.uint8) > 0


def parcel_mask_from_geometry(
    image_size: tuple[int, int],
    geometry: Mapping[str, Any] | None,
    *,
    pad_metres: float = PADDING_METRES,
) -> np.ndarray:
    """Map GIS rings onto a padded parcel crop. image_size is (width, height)."""
    width, height = image_size
    if not geometry:
        return np.ones((height, width), dtype=bool)
    xs: list[float] = []
    ys: list[float] = []
    rings = geometry.get("rings") or []
    for ring in rings:
        for x, y in ring:
            xs.append(float(x))
            ys.append(float(y))
    if not xs:
        return np.ones((height, width), dtype=bool)
    pad = pad_metres / 111_320
    bbox = (min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad)
    outer = rings[0] if rings else []
    pts = []
    for lon, lat in outer:
        x = (float(lon) - bbox[0]) / max(bbox[2] - bbox[0], 1e-12) * (width - 1)
        y = (bbox[3] - float(lat)) / max(bbox[3] - bbox[1], 1e-12) * (height - 1)
        pts.append((int(round(x)), int(round(y))))
    mask = Image.new("L", (width, height), 0)
    if len(pts) >= 3:
        ImageDraw.Draw(mask).polygon(pts, fill=255)
        return np.asarray(mask, dtype=np.uint8) > 0
    return np.ones((height, width), dtype=bool)


def building_mask_from_os(
    os_payload: Mapping[str, Any] | None,
    width: int,
    height: int,
) -> np.ndarray:
    if not os_payload:
        return np.zeros((height, width), dtype=bool)
    building = os_payload.get("building") or {}
    contour = building.get("contour")
    return rasterize_normalized_contour(contour, width, height)


def assess_pool_observability(
    rgb: np.ndarray | None,
    *,
    parcel_mask: np.ndarray | None = None,
    building_mask: np.ndarray | None = None,
) -> PoolObservability:
    """Decide whether imagery can support a confident inventory NO.

    Yard = parcel interior minus building footprint. Canopy, hard shadow, and
    roof covering the remaining yard block absence certification.
    """
    if rgb is None or rgb.ndim != 3 or rgb.shape[2] < 3:
        return missing_crop_observability("crop_missing")
    height, width = rgb.shape[:2]
    if min(height, width) < MIN_CROP_SIDE_PX:
        result = missing_crop_observability("crop_too_small")
        result.crop_present = True
        result.flags = ["pool_observability_inadequate", "imagery_quality_inadequate"]
        return result

    if parcel_mask is None or parcel_mask.shape[:2] != (height, width):
        parcel = np.ones((height, width), dtype=bool)
    else:
        parcel = parcel_mask.astype(bool)
    if building_mask is None or building_mask.shape[:2] != (height, width):
        building = np.zeros((height, width), dtype=bool)
    else:
        building = building_mask.astype(bool) & parcel

    parcel_pixels = int(parcel.sum())
    roof_fraction = float(building.sum() / parcel_pixels) if parcel_pixels else 0.0
    yard = parcel & ~building
    yard_pixels = int(yard.sum())
    hue, sat, val = rgb_to_hsv_cv(rgb)
    mean_val = float(val[parcel].mean()) if parcel_pixels else 0.0

    flags: list[str] = []
    imagery_quality_ok = mean_val >= MIN_MEAN_VALUE_FOR_QUALITY and parcel_pixels >= MIN_PARCEL_PIXELS
    if not imagery_quality_ok:
        flags.append("imagery_quality_inadequate")

    roof_occludes = roof_fraction >= MAX_ROOF_FRACTION_OF_PARCEL or yard_pixels < MIN_YARD_PIXELS_FOR_NO
    if roof_occludes:
        flags.append("roof_occludes_likely_pool_area")

    if yard_pixels <= 0:
        canopy_frac = shadow_frac = open_frac = 0.0
        canopy_occludes = shadow_occludes = True
        flags.append("backyard_not_adequately_observable")
        backyard_observable = False
    else:
        yard_h, yard_s, yard_v = hue[yard], sat[yard], val[yard]
        vegetation = (yard_h >= 35) & (yard_h <= 85) & (yard_s >= 40) & (yard_v >= 40)
        dark_canopy = vegetation & (yard_v <= 130) & (yard_s >= 50)
        shadow = yard_v < 45
        paving = (yard_s <= 55) & (yard_v >= 50) & (yard_v <= 210)
        bright_lawn = (yard_h >= 35) & (yard_h <= 85) & (yard_s >= 25) & (yard_v >= 145)
        visible_open = paving | bright_lawn | ((yard_s <= 80) & (yard_v >= 120) & ~dark_canopy & ~shadow)
        canopy_frac = float(dark_canopy.mean())
        shadow_frac = float(shadow.mean())
        open_frac = float(visible_open.mean())
        canopy_occludes = canopy_frac >= MAX_CANOPY_FRACTION_FOR_NO
        shadow_occludes = shadow_frac >= MAX_SHADOW_FRACTION_FOR_NO
        if canopy_occludes:
            flags.append("canopy_occludes_likely_pool_area")
        if shadow_occludes:
            flags.append("shadow_occludes_likely_pool_area")
        backyard_observable = (
            imagery_quality_ok
            and not roof_occludes
            and not canopy_occludes
            and not shadow_occludes
            and open_frac >= MIN_VISIBLE_OPEN_FRACTION_FOR_NO
        )
        if not backyard_observable and "backyard_not_adequately_observable" not in flags:
            flags.append("backyard_not_adequately_observable")

    adequate = backyard_observable and imagery_quality_ok and not canopy_occludes and not shadow_occludes and not roof_occludes
    if adequate:
        flags = ["pool_observability_adequate"]
        reason = None
    else:
        flags = ["pool_observability_inadequate"] + [item for item in flags if item != "pool_observability_adequate"]
        if canopy_occludes:
            reason = "canopy_occlusion"
        elif shadow_occludes:
            reason = "shadow_occlusion"
        elif roof_occludes:
            reason = "roof_or_building_occlusion"
        elif not imagery_quality_ok:
            reason = "imagery_quality_inadequate"
        else:
            reason = "backyard_not_adequately_observable"

    return PoolObservability(
        adequate_for_absence=adequate,
        crop_present=True,
        imagery_quality_ok=imagery_quality_ok,
        backyard_observable=backyard_observable,
        canopy_occludes=canopy_occludes,
        shadow_occludes=shadow_occludes,
        roof_occludes=roof_occludes,
        visible_open_fraction=open_frac if yard_pixels else 0.0,
        canopy_fraction=canopy_frac if yard_pixels else 0.0,
        shadow_fraction=shadow_frac if yard_pixels else 0.0,
        roof_fraction=roof_fraction,
        yard_pixels=yard_pixels,
        parcel_pixels=parcel_pixels,
        flags=sorted(set(flags)),
        reason=reason,
    )


def observability_from_crop(
    crop_path: Path | None,
    *,
    geometry: Mapping[str, Any] | None = None,
    os_payload: Mapping[str, Any] | None = None,
    rgb: np.ndarray | None = None,
) -> PoolObservability:
    array = rgb if rgb is not None else load_rgb(crop_path)
    if array is None:
        return missing_crop_observability("crop_missing")
    height, width = array.shape[:2]
    parcel = parcel_mask_from_geometry((width, height), geometry)
    building = building_mask_from_os(os_payload, width, height)
    return assess_pool_observability(array, parcel_mask=parcel, building_mask=building)
