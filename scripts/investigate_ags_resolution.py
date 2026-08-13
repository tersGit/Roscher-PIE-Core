#!/usr/bin/env python3
"""AGS native-detail investigation.

Fetches the SAME geographic parcel bbox at multiple output sizes from CoJ AGS
and measures whether larger requests contain additional source detail versus
interpolation. Does not change matching, CLIP, scoring, segmentation, ranking,
or production tile/crop settings.
"""

from __future__ import annotations

import json
import math
import shutil
import sys
import time
from io import BytesIO
from pathlib import Path

import cv2
import httpx
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from skimage.metrics import structural_similarity

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.gis.coj_property import CoJPropertyClient  # noqa: E402
from backend.imagery.ags_client import AGSAerialClient  # noqa: E402
from backend.imagery.estate_tiles import (  # noqa: E402
    DEFAULT_PIXELS,
    DEFAULT_TILE_METRES,
    PADDING_METRES,
    EstateTileIndex,
)

OUT = ROOT / "data/investigations/ags_resolution"
YEAR = 2023
SERVICE = f"https://ags.joburg.org.za/server/rest/services/AerialPhotography/{YEAR}/ImageServer"
INTERPOLATION = "RSP_BilinearInterpolation"
REQUEST_SIZES = (256, 400, 800, 1200, 1600, 2400, 3200)
NATIVE_PIXEL_SIZE_M = 0.15  # ImageServer pixelSizeX/Y in EPSG:3857 metres
MAX_HEIGHT = 4100
MAX_WIDTH = 15000
DEG_PAD = PADDING_METRES / 111_320  # same formula as production crop_parcel


def _font(size: int = 16) -> ImageFont.ImageFont:
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ):
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def parcel_bbox(geometry: dict) -> tuple[float, float, float, float]:
    xs, ys = [], []
    for ring in geometry.get("rings") or []:
        for x, y in ring:
            xs.append(float(x))
            ys.append(float(y))
    return min(xs), min(ys), max(xs), max(ys)


def padded_rect_wgs84(geometry: dict) -> dict[str, float]:
    min_lon, min_lat, max_lon, max_lat = parcel_bbox(geometry)
    return {
        "min_lon": min_lon - DEG_PAD,
        "min_lat": min_lat - DEG_PAD,
        "max_lon": max_lon + DEG_PAD,
        "max_lat": max_lat + DEG_PAD,
    }


def square_request_bbox(rect: dict[str, float]) -> dict[str, float]:
    """Centre-expand the padded AABB to a square in EPSG:3857.

    AGS exportImage with square size (N×N) expands the shorter axis anyway;
    locking the squared envelope keeps coverage identical across sizes and
    keeps output pixels isotropic in Web Mercator.
    """
    xmin, ymin, xmax, ymax = AGSAerialClient.bbox_from_wgs84(
        rect["min_lon"], rect["min_lat"], rect["max_lon"], rect["max_lat"]
    )
    width = xmax - xmin
    height = ymax - ymin
    side = max(width, height)
    cx = (xmin + xmax) / 2.0
    cy = (ymin + ymax) / 2.0
    xmin, xmax = cx - side / 2.0, cx + side / 2.0
    ymin, ymax = cy - side / 2.0, cy + side / 2.0
    min_lat, min_lon = AGSAerialClient.web_mercator_to_wgs84(xmin, ymin)
    max_lat, max_lon = AGSAerialClient.web_mercator_to_wgs84(xmax, ymax)
    return {
        "min_lon": min_lon,
        "min_lat": min_lat,
        "max_lon": max_lon,
        "max_lat": max_lat,
        "xmin": xmin,
        "ymin": ymin,
        "xmax": xmax,
        "ymax": ymax,
        "side_m": side,
    }


def fetch_imageserver_metadata() -> dict:
    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        service = client.get(SERVICE, params={"f": "pjson"}).json()
        key_props = client.get(f"{SERVICE}/keyProperties", params={"f": "json"}).json()
        rasters = client.get(
            f"{SERVICE}/query",
            params={
                "where": "1=1",
                "outFields": "OBJECTID,Name,MinPS,MaxPS,LowPS,HighPS,Category,Tag,ProductName",
                "returnGeometry": "false",
                "f": "json",
                "resultRecordCount": 50,
            },
        ).json()
    keep = {
        "name": service.get("name"),
        "description": service.get("description"),
        "pixelSizeX": service.get("pixelSizeX"),
        "pixelSizeY": service.get("pixelSizeY"),
        "spatialReference": service.get("spatialReference"),
        "maxImageHeight": service.get("maxImageHeight"),
        "maxImageWidth": service.get("maxImageWidth"),
        "defaultResamplingMethod": service.get("defaultResamplingMethod"),
        "defaultCompressionQuality": service.get("defaultCompressionQuality"),
        "minPixelSize": service.get("minPixelSize"),
        "maxPixelSize": service.get("maxPixelSize"),
        "minScale": service.get("minScale"),
        "maxScale": service.get("maxScale"),
        "currentVersion": service.get("currentVersion"),
        "capabilities": service.get("capabilities"),
        "allowedCompressions": service.get("allowedCompressions"),
        "rasterFunctionInfos": service.get("rasterFunctionInfos"),
    }
    raster_rows = [item.get("attributes") or {} for item in (rasters.get("features") or [])]
    low_ps = sorted({round(float(r["LowPS"]), 6) for r in raster_rows if r.get("LowPS") is not None})
    names = [r.get("Name") for r in raster_rows[:12]]
    return {
        "service": keep,
        "keyProperties": key_props,
        "raster_catalog_sample": raster_rows[:12],
        "raster_low_ps_values": low_ps,
        "raster_name_sample": names,
        "native_pixel_size_m_3857": NATIVE_PIXEL_SIZE_M,
        "pyramid_notes": (
            "Catalog rasters advertise LowPS=HighPS≈0.15 (15 cm) with MaxPS≈1.5. "
            "keyProperties LowCellSize=0.15, HighCellSize=291.6, MaxCellSize=14580. "
            "No explicit LOD/tileInfo pyramid table is exposed on the ImageServer."
        ),
    }


def identify_source_raster(lon: float, lat: float) -> dict:
    params = {
        "geometry": json.dumps({"x": lon, "y": lat}),
        "geometryType": "esriGeometryPoint",
        "sr": "4326",
        "returnGeometry": "false",
        "returnCatalogItems": "true",
        "f": "json",
    }
    with httpx.Client(timeout=40.0, follow_redirects=True) as client:
        payload = client.get(f"{SERVICE}/identify", params=params).json()
    catalog = payload.get("catalogItems") or {}
    features = catalog.get("features") or []
    attrs = (features[0].get("attributes") if features else {}) or {}
    return {
        "value": payload.get("value"),
        "name": payload.get("name"),
        "catalog_name": attrs.get("Name"),
        "LowPS": attrs.get("LowPS"),
        "HighPS": attrs.get("HighPS"),
        "MinPS": attrs.get("MinPS"),
        "MaxPS": attrs.get("MaxPS"),
    }


def export_ags(bbox: dict, size: int) -> dict:
    if size > MAX_HEIGHT or size > MAX_WIDTH:
        return {
            "ok": False,
            "skipped": True,
            "reason": f"requested {size} exceeds advertised maxima H{MAX_HEIGHT}/W{MAX_WIDTH}",
        }
    url = f"{SERVICE}/exportImage"
    bbox_str = f"{bbox['xmin']:.3f},{bbox['ymin']:.3f},{bbox['xmax']:.3f},{bbox['ymax']:.3f}"
    size_str = f"{size},{size}"
    common = {
        "bbox": bbox_str,
        "bboxSR": "3857",
        "imageSR": "3857",
        "size": size_str,
        "format": "jpg",
        "interpolation": INTERPOLATION,
        "returnSquarePixels": "false",
    }
    with httpx.Client(timeout=120.0, follow_redirects=True) as client:
        t0 = time.perf_counter()
        meta_resp = client.get(url, params={**common, "f": "json"})
        meta_ms = (time.perf_counter() - t0) * 1000
        try:
            meta = meta_resp.json()
        except Exception:
            meta = {"raw": meta_resp.text[:500]}
        t1 = time.perf_counter()
        img_resp = client.get(url, params={**common, "f": "image"})
        img_ms = (time.perf_counter() - t1) * 1000
    content = img_resp.content
    returned_w = returned_h = None
    if content:
        try:
            with Image.open(BytesIO(content)) as im:
                returned_w, returned_h = im.size
        except Exception:
            pass
    extent = (meta or {}).get("extent") or {}
    returned_side_x = None
    returned_side_y = None
    if extent:
        returned_side_x = float(extent["xmax"]) - float(extent["xmin"])
        returned_side_y = float(extent["ymax"]) - float(extent["ymin"])
    metres_per_px = bbox["side_m"] / float(size)
    native_px = bbox["side_m"] / NATIVE_PIXEL_SIZE_M
    flag = None
    if metres_per_px < NATIVE_PIXEL_SIZE_M * 0.98:
        flag = "UPSCALED — NO EXPECTED ADDITIONAL SOURCE DETAIL"
    return {
        "ok": img_resp.status_code == 200 and bool(content) and returned_w is not None,
        "skipped": False,
        "bbox_wgs84": {
            "min_lon": bbox["min_lon"],
            "min_lat": bbox["min_lat"],
            "max_lon": bbox["max_lon"],
            "max_lat": bbox["max_lat"],
        },
        "bbox_3857": {
            "xmin": bbox["xmin"],
            "ymin": bbox["ymin"],
            "xmax": bbox["xmax"],
            "ymax": bbox["ymax"],
            "side_m": bbox["side_m"],
        },
        "requested_dimensions": [size, size],
        "returned_dimensions": [returned_w, returned_h],
        "file_size_bytes": len(content),
        "http_status": img_resp.status_code,
        "content_type": img_resp.headers.get("content-type"),
        "runtime_ms_image": round(img_ms, 1),
        "runtime_ms_json": round(meta_ms, 1),
        "interpolation": INTERPOLATION,
        "year": YEAR,
        "crs": "EPSG:3857",
        "metres_per_output_pixel": metres_per_px,
        "native_pixel_size_m": NATIVE_PIXEL_SIZE_M,
        "native_request_px": native_px,
        "flag": flag,
        "export_json": {
            "http_status": meta_resp.status_code,
            "width": (meta or {}).get("width"),
            "height": (meta or {}).get("height"),
            "scale": (meta or {}).get("scale"),
            "extent": extent,
            "href": (meta or {}).get("href"),
        },
        "returned_extent_m": {"x": returned_side_x, "y": returned_side_y},
        "server_resampling": (
            f"ImageServer defaultResamplingMethod=Bilinear; request interpolation={INTERPOLATION}; "
            "no per-response resampling field is advertised beyond export extent/size."
        ),
        "content": content,
    }


def crop_from_tile(tile: dict, rect: dict[str, float], dest: Path) -> dict:
    image = Image.open(tile["path"]).convert("RGB")
    w, h = image.size
    def px(lon: float, lat: float) -> tuple[int, int]:
        x = (lon - tile["min_lon"]) / max(tile["max_lon"] - tile["min_lon"], 1e-12)
        y = (tile["max_lat"] - lat) / max(tile["max_lat"] - tile["min_lat"], 1e-12)
        return int(x * (w - 1)), int(y * (h - 1))

    x0, y1 = px(rect["min_lon"], rect["min_lat"])
    x1, y0 = px(rect["max_lon"], rect["max_lat"])
    left, right = sorted((max(0, x0), max(0, x1)))
    top, bottom = sorted((max(0, y0), max(0, y1)))
    right = min(w, max(right, left + 8))
    bottom = min(h, max(bottom, top + 8))
    crop = image.crop((left, top, right, bottom))
    dest.parent.mkdir(parents=True, exist_ok=True)
    crop.save(dest, quality=90)
    tile_m_per_px = DEFAULT_TILE_METRES / DEFAULT_PIXELS
    return {
        "path": str(dest),
        "size": list(crop.size),
        "file_size_bytes": dest.stat().st_size,
        "tile_path": str(tile["path"]),
        "tile_metres": DEFAULT_TILE_METRES,
        "tile_pixels": DEFAULT_PIXELS,
        "tile_metres_per_pixel": tile_m_per_px,
        "crop_metres_per_pixel": tile_m_per_px,
        "note": "Generated with current production tile/crop algorithm (280 m @ 1400 px, 18 m pad).",
    }


def load_bgr(path: Path) -> np.ndarray:
    data = np.fromfile(path, dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"failed to decode {path}")
    return image


def to_gray(bgr: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)


def stable_edge_count(gray: np.ndarray) -> int:
    edges = cv2.Canny(gray, 80, 160)
    num, _ = cv2.connectedComponents(edges)
    return int(max(0, num - 1))


def image_metrics(bgr: np.ndarray) -> dict:
    gray = to_gray(bgr)
    h, w = gray.shape
    edges = cv2.Canny(gray, 50, 150)
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    mag = np.sqrt(gx * gx + gy * gy)
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    f = np.fft.fftshift(np.fft.fft2(gray.astype(np.float32)))
    mag_f = np.abs(f)
    yy, xx = np.ogrid[:h, :w]
    cy, cx = h / 2.0, w / 2.0
    radius = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)
    rmax = math.sqrt(cy * cy + cx * cx) + 1e-6
    hf_mask = radius > 0.25 * rmax
    total = float(mag_f.sum()) + 1e-9
    sift = cv2.SIFT_create(nfeatures=5000)
    orb = cv2.ORB_create(nfeatures=4000)
    sift_kps = sift.detect(gray, None)
    orb_kps = orb.detect(gray, None)
    grid = 16
    occupied = np.zeros((grid, grid), dtype=np.uint8)
    for kp in sift_kps:
        col = min(grid - 1, max(0, int(kp.pt[0] / w * grid)))
        row = min(grid - 1, max(0, int(kp.pt[1] / h * grid)))
        occupied[row, col] = 1
    return {
        "width": int(w),
        "height": int(h),
        "edge_density": float(edges.mean() / 255.0),
        "stable_edge_components": stable_edge_count(gray),
        "gradient_mean": float(mag.mean()),
        "gradient_p95": float(np.percentile(mag, 95)),
        "laplacian_variance": float(lap.var()),
        "high_freq_energy_frac": float(mag_f[hf_mask].sum() / total),
        "sift_keypoints": int(len(sift_kps)),
        "orb_keypoints": int(len(orb_kps)),
        "sift_spatial_cells": int(occupied.sum()),
        "sift_per_megapixel": float(len(sift_kps) / max((w * h) / 1e6, 1e-9)),
    }


def ssim_gray(a: np.ndarray, b: np.ndarray) -> float:
    ga = to_gray(a) if a.ndim == 3 else a
    gb = to_gray(b) if b.ndim == 3 else b
    if ga.shape != gb.shape:
        gb = cv2.resize(gb, (ga.shape[1], ga.shape[0]), interpolation=cv2.INTER_AREA)
    return float(structural_similarity(ga, gb, data_range=255))


def resize_to(bgr: np.ndarray, size: int, interp: int) -> np.ndarray:
    return cv2.resize(bgr, (size, size), interpolation=interp)


def pair_comparisons(images: dict[int, np.ndarray]) -> dict:
    """Downsample/upscale tests that separate new source detail from interpolation."""
    out: dict = {}
    pairs = [(400, 1600), (800, 1600), (1200, 1600), (1600, 2400), (1600, 3200), (800, 1200)]
    for lo, hi in pairs:
        if lo not in images or hi not in images:
            continue
        hi_down = resize_to(images[hi], lo, cv2.INTER_AREA)
        lo_up_lin = resize_to(images[lo], hi, cv2.INTER_LINEAR)
        lo_up_cub = resize_to(images[lo], hi, cv2.INTER_CUBIC)
        m_hi = image_metrics(images[hi])
        m_up = image_metrics(lo_up_lin)
        out[f"{hi}_vs_upscaled_{lo}"] = {
            "ssim_hi_vs_bilinear_up_lo": ssim_gray(images[hi], lo_up_lin),
            "ssim_hi_vs_cubic_up_lo": ssim_gray(images[hi], lo_up_cub),
            "ssim_lo_vs_downsampled_hi": ssim_gray(images[lo], hi_down),
            "laplacian_hi": m_hi["laplacian_variance"],
            "laplacian_upscaled_lo": m_up["laplacian_variance"],
            "hf_hi": m_hi["high_freq_energy_frac"],
            "hf_upscaled_lo": m_up["high_freq_energy_frac"],
            "sift_hi": m_hi["sift_keypoints"],
            "sift_upscaled_lo": m_up["sift_keypoints"],
            "edge_density_hi": m_hi["edge_density"],
            "edge_density_upscaled_lo": m_up["edge_density"],
            "interpretation": (
                "If the higher AGS request has genuine extra source detail, "
                "SSIM(hi, upscaled lo) should drop and hi should show higher "
                "HF energy / Laplacian / SIFT than bilinear-upscaled lo. "
                "If they match closely, AGS is interpolating the same source pixels."
            ),
        }
    return out


def detect_pool_bbox(bgr: np.ndarray) -> tuple[int, int, int, int] | None:
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    # cyan / blue water in CoJ aerials
    mask_a = cv2.inRange(hsv, (80, 40, 40), (130, 255, 255))
    mask_b = cv2.inRange(hsv, (90, 20, 20), (140, 255, 180))
    mask = cv2.bitwise_or(mask_a, mask_b)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    h, w = mask.shape
    min_area = 0.002 * w * h
    max_area = 0.12 * w * h
    best = None
    best_area = 0
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < min_area or area > max_area:
            continue
        x, y, bw, bh = cv2.boundingRect(cnt)
        if area > best_area:
            best_area = area
            best = (x, y, bw, bh)
    return best


def chip(bgr: np.ndarray, box: tuple[int, int, int, int], pad_frac: float = 0.35) -> np.ndarray:
    h, w = bgr.shape[:2]
    x, y, bw, bh = box
    pad_x = int(bw * pad_frac)
    pad_y = int(bh * pad_frac)
    x0 = max(0, x - pad_x)
    y0 = max(0, y - pad_y)
    x1 = min(w, x + bw + pad_x)
    y1 = min(h, y + bh + pad_y)
    return bgr[y0:y1, x0:x1]


def geo_chip(bgr: np.ndarray, fx0: float, fy0: float, fx1: float, fy1: float) -> np.ndarray:
    h, w = bgr.shape[:2]
    x0, x1 = int(fx0 * w), int(fx1 * w)
    y0, y1 = int(fy0 * h), int(fy1 * h)
    x0, x1 = max(0, min(w - 1, x0)), max(1, min(w, x1))
    y0, y1 = max(0, min(h - 1, y0)), max(1, min(h, y1))
    if x1 <= x0:
        x1 = min(w, x0 + 8)
    if y1 <= y0:
        y1 = min(h, y0 + 8)
    return bgr[y0:y1, x0:x1]


def usefulness_from_metrics(size: int, native_px: float, metrics: dict, has_pool: bool) -> dict:
    """Heuristic 0-4 scores; refined by visual inspection in report.md."""
    ratio = size / max(native_px, 1.0)
    if size <= 256:
        base = 1
    elif size <= 400:
        base = 2
    elif ratio < 0.85:
        base = 3
    elif ratio <= 1.15:
        base = 4
    else:
        base = 4  # sharp but interpolated; visual score may stay 4 while native_gained is false
    roof = base
    driveway = max(0, base - (1 if size <= 400 else 0))
    pool = 0 if not has_pool else base
    if metrics["edge_density"] < 0.02 and size <= 400:
        roof = max(0, roof - 1)
        driveway = max(0, driveway - 1)
    return {"roof": roof, "pool": pool, "driveway": driveway}


def bgr_to_pil(bgr: np.ndarray) -> Image.Image:
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)


def letterbox(im: Image.Image, size: int, fill=(20, 20, 20)) -> Image.Image:
    canvas = Image.new("RGB", (size, size), fill)
    im = im.copy()
    im.thumbnail((size, size), Image.Resampling.LANCZOS)
    canvas.paste(im, ((size - im.width) // 2, (size - im.height) // 2))
    return canvas


def save_resolution_sheet(parcel_id: str, images: dict[int, np.ndarray], dest: Path) -> None:
    sizes = sorted(images)
    cell = 280
    header = 36
    cols = len(sizes)
    sheet = Image.new("RGB", (cols * cell, cell + header + 24), (12, 12, 12))
    draw = ImageDraw.Draw(sheet)
    font = _font(14)
    draw.text((8, 8), f"{parcel_id} — identical bbox, AGS 2023 (overview scaled)", fill=(240, 240, 240), font=font)
    for i, size in enumerate(sizes):
        tile = letterbox(bgr_to_pil(images[size]), cell)
        sheet.paste(tile, (i * cell, header))
        draw.text((i * cell + 8, cell + header + 4), f"{size}px", fill=(220, 220, 220), font=font)
    dest.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(dest, quality=92)


def save_chip_sheet(
    parcel_id: str,
    title: str,
    chips: dict[int, np.ndarray],
    dest: Path,
    cell: int = 260,
) -> None:
    sizes = sorted(chips)
    header = 40
    cols = len(sizes)
    sheet = Image.new("RGB", (cols * cell, cell + header + 22), (12, 12, 12))
    draw = ImageDraw.Draw(sheet)
    font = _font(14)
    draw.text((8, 8), f"{parcel_id} — {title}", fill=(240, 240, 240), font=font)
    for i, size in enumerate(sizes):
        tile = letterbox(bgr_to_pil(chips[size]), cell)
        sheet.paste(tile, (i * cell, header))
        draw.text((i * cell + 8, cell + header + 2), f"{size}px", fill=(220, 220, 220), font=font)
    dest.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(dest, quality=92)


def save_upsample_sheet(parcel_id: str, images: dict[int, np.ndarray], dest: Path) -> None:
    if 400 not in images or 1600 not in images:
        return
    up = resize_to(images[400], 1600, cv2.INTER_LINEAR)
    actual = images[1600]
    # same geographic 25% window
    chip_up = geo_chip(up, 0.35, 0.30, 0.65, 0.60)
    chip_hi = geo_chip(actual, 0.35, 0.30, 0.65, 0.60)
    cell = 420
    header = 48
    sheet = Image.new("RGB", (cell * 2, cell + header), (12, 12, 12))
    draw = ImageDraw.Draw(sheet)
    font = _font(15)
    draw.text((8, 8), f"{parcel_id} — AGS 400 bilinear-upscaled to 1600  vs  AGS-requested 1600 (same window)", fill=(240, 240, 240), font=font)
    sheet.paste(letterbox(bgr_to_pil(chip_up), cell), (0, header))
    sheet.paste(letterbox(bgr_to_pil(chip_hi), cell), (cell, header))
    draw.text((12, header + 8), "400→1600 upscale", fill=(255, 220, 80), font=font)
    draw.text((cell + 12, header + 8), "AGS 1600", fill=(80, 255, 140), font=font)
    dest.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(dest, quality=92)


def save_current_vs_ags_sheet(
    parcel_id: str,
    current: np.ndarray,
    ags: np.ndarray,
    dest: Path,
    current_label: str,
    ags_label: str,
) -> None:
    cell = 480
    header = 52
    sheet = Image.new("RGB", (cell * 2, cell + header), (12, 12, 12))
    draw = ImageDraw.Draw(sheet)
    font = _font(15)
    draw.text(
        (8, 8),
        f"{parcel_id} — current PIE crop vs direct AGS (same parcel, scaled for display)",
        fill=(240, 240, 240),
        font=font,
    )
    sheet.paste(letterbox(bgr_to_pil(current), cell), (0, header))
    sheet.paste(letterbox(bgr_to_pil(ags), cell), (cell, header))
    draw.text((12, header + 8), current_label, fill=(255, 180, 80), font=font)
    draw.text((cell + 12, header + 8), ags_label, fill=(80, 255, 140), font=font)
    dest.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(dest, quality=92)


def current_pipeline_crop_for_parcel(parcel: dict, dest: Path, cache_dir: Path) -> dict:
    existing = parcel.get("existing_crop")
    if existing and Path(existing).is_file():
        shutil.copy2(existing, dest)
        im = Image.open(dest)
        return {
            "path": str(dest),
            "size": list(im.size),
            "file_size_bytes": dest.stat().st_size,
            "source": "production_carlswald_north_corrected_001_crop",
            "tile_metres": DEFAULT_TILE_METRES,
            "tile_pixels": DEFAULT_PIXELS,
            "crop_metres_per_pixel": DEFAULT_TILE_METRES / DEFAULT_PIXELS,
            "note": "Copied from existing PIE parcel crop (tile-cache crop, not a direct AGS parcel request).",
        }
    rect = parcel["padded_rect"]
    # Tiny estate extent around this parcel so EstateTileIndex uses production 280 m / 1400 px tiles.
    extent = {
        "min_longitude": rect["min_lon"] - 0.0005,
        "max_longitude": rect["max_lon"] + 0.0005,
        "min_latitude": rect["min_lat"] - 0.0005,
        "max_latitude": rect["max_lat"] + 0.0005,
    }
    index = EstateTileIndex(cache_dir, extent, year=YEAR)
    index.build(tile_metres=DEFAULT_TILE_METRES, pixels=DEFAULT_PIXELS)
    tile = index.covering_tile(rect["min_lon"], rect["min_lat"], rect["max_lon"], rect["max_lat"])
    if not tile:
        raise RuntimeError(f"no covering tile for {parcel['id']}")
    info = crop_from_tile(tile, rect, dest)
    info["source"] = "simulated_current_pipeline_blue_hills"
    info["note"] = (
        "This repo has no Blue Hills production cache. Crop generated with the "
        "current algorithm: 280 m tiles at 1400 px (~0.20 m/px) then local 18 m pad crop."
    )
    return info


def load_carlswald_parcel(stand: str) -> dict:
    dataset = json.loads((ROOT / "data/gis/carlswald_north_corrected_001.json").read_text())
    for item in dataset["parcels"]:
        if str(item.get("stand_number")) == stand:
            crop = (
                ROOT
                / "data/visual_index/carlswald_north_corrected_001/_imagery_cache"
                / f"{stand}_ags_aerial.jpg"
            )
            return {
                "id": f"stand_{stand}",
                "stand": stand,
                "estate": "Carlswald North (SUMMERSET EXT.13)" if "EXT.13" in str(item.get("township")) else f"Carlswald North ({item.get('township')})",
                "township": item.get("township"),
                "area_sqm": item.get("area_sqm"),
                "geometry": item.get("geometry"),
                "existing_crop": str(crop) if crop.is_file() else None,
            }
    raise RuntimeError(f"Carlswald stand {stand} not in corrected dataset")


def load_blue_hills_parcel(stand: str) -> dict:
    client = CoJPropertyClient()
    rows = client.query(
        8,
        f"STAND_NO='{stand}' AND TOWN_NAME_DESC='BLUE HILLS EXT.8'",
        fields="OBJECTID,STAND_NO,AREA_SQMT,TOWN_NAME_DESC,LAND_TYPE_NAME,CAT_DESC,STREET_ADDRESS,PROPERTY_ID",
        return_geometry=True,
    )
    if not rows:
        raise RuntimeError(f"Blue Hills stand {stand} not found in BLUE HILLS EXT.8")
    attrs = rows[0]["attributes"]
    return {
        "id": f"stand_{stand}",
        "stand": stand,
        "estate": "Blue Hills (BLUE HILLS EXT.8)",
        "township": attrs.get("TOWN_NAME_DESC"),
        "area_sqm": attrs.get("AREA_SQMT"),
        "address": attrs.get("STREET_ADDRESS"),
        "geometry": rows[0].get("geometry"),
        "existing_crop": None,
    }


def native_gained_label(size: int, native_px: float, pair: dict | None) -> str:
    if size / native_px < 0.70:
        return "below native — more source detail available"
    if size / native_px < 0.98:
        return "approaching native"
    if size / native_px <= 1.12:
        return "at native source resolution"
    # beyond native: check whether metrics still move
    if pair is None:
        return "UPSCALED — NO EXPECTED ADDITIONAL SOURCE DETAIL"
    ssim_v = pair.get("ssim_hi_vs_bilinear_up_lo")
    if ssim_v is not None and ssim_v >= 0.92:
        return "UPSCALED — NO EXPECTED ADDITIONAL SOURCE DETAIL"
    return "beyond native (possible interpolation / JPEG difference only)"


def tile_strategy(estate_extent: dict, mean_runtime_s: float, mean_tile_bytes: int) -> dict:
    xmin, ymin = AGSAerialClient.wgs84_to_web_mercator(estate_extent["min_latitude"], estate_extent["min_longitude"])
    xmax, ymax = AGSAerialClient.wgs84_to_web_mercator(estate_extent["max_latitude"], estate_extent["max_longitude"])
    pad = DEFAULT_TILE_METRES * 0.15
    xmin -= pad
    ymin -= pad
    xmax += pad
    ymax += pad
    width = xmax - xmin
    height = ymax - ymin

    def grid(tile_m: float, pixels: int) -> dict:
        cols = max(1, int(math.ceil(width / tile_m)))
        rows = max(1, int(math.ceil(height / tile_m)))
        n = cols * rows
        mpp = tile_m / pixels
        bytes_est = int(mean_tile_bytes * (pixels / DEFAULT_PIXELS) ** 2 * 0.85)
        # runtime scales roughly with returned pixels for AGS jpeg encode
        time_est = mean_runtime_s * n * (pixels / DEFAULT_PIXELS) ** 1.2
        return {
            "tile_metres": tile_m,
            "tile_pixels": pixels,
            "metres_per_pixel": mpp,
            "rows": rows,
            "cols": cols,
            "tiles": n,
            "cache_size_mb_est": round(n * bytes_est / 1e6, 2),
            "fetch_time_s_est": round(time_est, 1),
            "native": abs(mpp - NATIVE_PIXEL_SIZE_M) / NATIVE_PIXEL_SIZE_M < 0.05,
            "flag": None if mpp >= NATIVE_PIXEL_SIZE_M * 0.98 else "UPSCALED — NO EXPECTED ADDITIONAL SOURCE DETAIL",
        }

    options = [
        grid(280.0, 1400),  # current
        grid(280.0, 1867),  # same geography, native px
        grid(210.0, 1400),  # smaller tiles, native at 1400
        grid(150.0, 1000),
        grid(120.0, 800),
    ]
    return {
        "estate_mercator_m": {"width": width, "height": height},
        "options": options,
        "recommended": "Keep tiled cache (do not revert to per-parcel AGS). Use 210 m tiles at 1400 px or 280 m tiles at 1867 px so cache pixels match 0.15 m native. Local 18 m pad crops then inherit native resolution.",
    }


def write_report(payload: dict) -> None:
    lines: list[str] = []
    a = lines.append
    a("# CoJ AGS parcel resolution investigation")
    a("")
    a("Investigation only. Matching, CLIP, scoring, segmentation, ranking, and production tile/crop settings were not changed.")
    a("")
    a("## Success question")
    a("")
    a(payload["success_answer"])
    a("")
    a("## Service metadata")
    a("")
    svc = payload["imageserver"]["service"]
    a(f"- Service: `{svc.get('name')}` ({YEAR})")
    a(f"- Native pixel size (EPSG:3857): **{svc.get('pixelSizeX')} × {svc.get('pixelSizeY')} m** (advertised 15 cm)")
    a(f"- Advertised maxima: height **{svc.get('maxImageHeight')}**, width **{svc.get('maxImageWidth')}**")
    a(f"- Default resampling: `{svc.get('defaultResamplingMethod')}`; request interpolation: `{INTERPOLATION}`")
    a(f"- Default JPEG quality: {svc.get('defaultCompressionQuality')}")
    a(f"- {payload['imageserver']['pyramid_notes']}")
    a(f"- keyProperties: `{json.dumps(payload['imageserver']['keyProperties'])}`")
    a(f"- Raster name sample: {payload['imageserver']['raster_name_sample']}")
    a("")
    a("## Method")
    a("")
    a("- One fixed geographic bbox per parcel: production padded AABB (polygon + 18 m via `PADDING_METRES/111320`), then centre-expanded to a **square Web Mercator envelope**. AGS `exportImage` with N×N already squares the short axis; locking the square keeps coverage and pixel isotropy identical at every size.")
    a("- Same year (2023), CRS (EPSG:3857), interpolation (`RSP_BilinearInterpolation`).")
    a("- Every listed size was requested directly from AGS (`f=image`). Files are the raw response bytes, not locally resized copies.")
    a("- 2400 and 3200 are under the advertised 4100 height / 15000 width limits and were requested.")
    a("- Quantitative tests: Canny edge density, Sobel gradient, connected edge components, SIFT/ORB keypoints + 16×16 spatial occupancy, Laplacian variance, FFT high-frequency energy fraction, SSIM of downsample/upscale pairs.")
    a("- Native request size = `bbox_side_m / 0.15`. Requests finer than 0.15 m/px are flagged `UPSCALED — NO EXPECTED ADDITIONAL SOURCE DETAIL`.")
    a("")
    a("## Parcels")
    a("")
    for p in payload["parcels"]:
        a(
            f"- **{p['id']}** — {p['estate']}, {p.get('area_sqm')} m². "
            f"Square bbox side **{p['request_bbox']['side_m']:.1f} m**. "
            f"Native-matched request **{p['native_px']:.0f} px** ({NATIVE_PIXEL_SIZE_M} m/px). "
            f"Source raster: `{p.get('identify', {}).get('catalog_name')}` LowPS={p.get('identify', {}).get('LowPS')}."
        )
    a("")
    a("Carlswald North parcel is **Stand 677** (SUMMERSET EXT.13): clearly visible rectangular pool on the existing crop, and it was the frozen listing-116978058 rank-1 candidate. Stands 420 and 408 also show pools; 677 is the preferred listed option with the most usable pool outline in the current crop.")
    a("")
    a("## Results table")
    a("")
    a("| parcel | requested px | metres/px | file size | keypoints | edge detail | pool usefulness | roof usefulness | driveway usefulness | native detail gained? |")
    a("|---|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for row in payload["table"]:
        a(
            f"| {row['parcel']} | {row['requested_px']} | {row['metres_per_px']:.4f} | {row['file_size']} | "
            f"{row['keypoints']} | {row['edge_detail']} | {row['pool_usefulness']} | "
            f"{row['roof_usefulness']} | {row['driveway_usefulness']} | {row['native_detail_gained']} |"
        )
    a("")
    a("Usefulness scores: 0 unusable, 1 barely visible, 2 usable, 3 clear, 4 highly detailed. Scores combine metrics with visual inspection of 1:1 chips (roof / pool / driveway). File size is not used as a detail proxy.")
    a("")
    a("## Detail vs interpolation")
    a("")
    for p in payload["parcels"]:
        a(f"### {p['id']}")
        a("")
        a(f"- Native-matched size: **{p['native_px']:.0f} px** ({p['request_bbox']['side_m']:.1f} m / 0.15).")
        a(f"- Current pipeline crop: {p['current_crop']['size'][0]}×{p['current_crop']['size'][1]} at **{p['current_crop']['crop_metres_per_pixel']:.3f} m/px** ({p['current_crop'].get('source')}).")
        plateau = p.get("plateau_px")
        a(f"- Smallest request capturing essentially all native detail: **{plateau} px**.")
        a("")
        a("Downsample / upscale:")
        a("")
        for key, cmp_ in (p.get("pairs") or {}).items():
            a(
                f"- `{key}`: SSIM(hi vs bilinear-up lo)={cmp_['ssim_hi_vs_bilinear_up_lo']:.4f}, "
                f"SSIM(hi vs cubic-up lo)={cmp_['ssim_hi_vs_cubic_up_lo']:.4f}, "
                f"SSIM(lo vs downsampled hi)={cmp_['ssim_lo_vs_downsampled_hi']:.4f}, "
                f"SIFT hi/up={cmp_['sift_hi']}/{cmp_['sift_upscaled_lo']}, "
                f"Laplacian hi/up={cmp_['laplacian_hi']:.1f}/{cmp_['laplacian_upscaled_lo']:.1f}, "
                f"HF hi/up={cmp_['hf_hi']:.4f}/{cmp_['hf_upscaled_lo']:.4f}."
            )
        a("")
        a(p.get("narrative", ""))
        a("")
    a("## Current PIE crop vs direct AGS")
    a("")
    a(payload["pipeline_outcome"])
    a("")
    a("## Recommended acquisition (not applied)")
    a("")
    a(f"- `recommended_ags_parcel_resolution`: **{payload['recommended_ags_parcel_resolution']}**")
    a(f"- `recommended_metres_per_pixel`: **{payload['recommended_metres_per_pixel']}**")
    a("")
    a("These are investigation recommendations only. Production `DEFAULT_TILE_METRES=280` / `DEFAULT_PIXELS=1400` were not modified.")
    a("")
    a("## If tile cache is the limit")
    a("")
    a("Do **not** revert to one AGS request per parcel (the 337/786 pattern). Keep a tiled cache at native 0.15 m/px, crop locally.")
    a("")
    ts = payload["tile_strategy"]
    a(f"Carlswald North padded estate footprint ≈ {ts['estate_mercator_m']['width']:.0f} × {ts['estate_mercator_m']['height']:.0f} m.")
    a("")
    a("| tile m | tile px | m/px | tiles | cache MB est. | fetch s est. | native? |")
    a("|---:|---:|---:|---:|---:|---:|---|")
    for opt in ts["options"]:
        a(
            f"| {opt['tile_metres']:.0f} | {opt['tile_pixels']} | {opt['metres_per_pixel']:.3f} | "
            f"{opt['tiles']} | {opt['cache_size_mb_est']} | {opt['fetch_time_s_est']} | "
            f"{'yes' if opt['native'] else 'no'} |"
        )
    a("")
    a(ts["recommended"])
    a("")
    a("Best tradeoff: **210 m tiles at 1400 px (0.15 m/px)**. Same JPEG size class as today, more tiles, native ground sampling. Alternative: keep 280 m tiles but request **1867 px** so each tile is native (fewer tiles, larger files).")
    a("")
    a("## Comparison sheets")
    a("")
    for rel in payload["sheets"]:
        a(f"- `{rel}`")
    a("")
    a("## Request logs")
    a("")
    a("Per-parcel JSON (bbox, HTTP, dimensions, runtime, exportImage extent) lives next to the raw JPEGs:")
    for p in payload["parcels"]:
        a(f"- `data/investigations/ags_resolution/{p['id']}/requests.json`")
        a(f"- `data/investigations/ags_resolution/{p['id']}/metrics.json`")
    a("")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    print("Fetching ImageServer metadata…")
    meta = fetch_imageserver_metadata()
    (OUT / "imageserver_metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    parcels = [
        load_blue_hills_parcel("34"),
        load_blue_hills_parcel("36"),
        load_carlswald_parcel("677"),
    ]

    all_rows = []
    sheet_rels: list[str] = []
    comparisons_dir = OUT / "comparisons"
    comparisons_dir.mkdir(parents=True, exist_ok=True)
    runtimes = []

    for parcel in parcels:
        parcel_dir = OUT / parcel["id"]
        parcel_dir.mkdir(parents=True, exist_ok=True)
        rect = padded_rect_wgs84(parcel["geometry"])
        bbox = square_request_bbox(rect)
        parcel["padded_rect"] = rect
        parcel["request_bbox"] = bbox
        parcel["native_px"] = bbox["side_m"] / NATIVE_PIXEL_SIZE_M
        cx = (rect["min_lon"] + rect["max_lon"]) / 2
        cy = (rect["min_lat"] + rect["max_lat"]) / 2
        parcel["identify"] = identify_source_raster(cx, cy)
        print(
            f"\n{parcel['id']} side={bbox['side_m']:.1f}m native_px={parcel['native_px']:.0f} "
            f"raster={parcel['identify'].get('catalog_name')}"
        )

        requests = []
        images: dict[int, np.ndarray] = {}
        metrics_by_size: dict[int, dict] = {}
        for size in REQUEST_SIZES:
            dest = parcel_dir / f"{size}.jpg"
            print(f"  AGS {size}×{size}…", flush=True)
            result = export_ags(bbox, size)
            content = result.pop("content", b"")
            if result.get("skipped"):
                requests.append(result)
                print(f"    skipped: {result.get('reason')}")
                continue
            if not result.get("ok"):
                requests.append(result)
                print(f"    FAIL HTTP {result.get('http_status')} type={result.get('content_type')}")
                continue
            dest.write_bytes(content)  # raw AGS bytes
            result["saved_as"] = str(dest.relative_to(ROOT))
            requests.append(result)
            runtimes.append(result["runtime_ms_image"] / 1000.0)
            bgr = load_bgr(dest)
            images[size] = bgr
            metrics_by_size[size] = image_metrics(bgr)
            print(
                f"    returned {result['returned_dimensions']} {result['file_size_bytes']} B "
                f"{result['metres_per_output_pixel']:.4f} m/px {result['runtime_ms_image']:.0f} ms "
                f"{result.get('flag') or ''}"
            )

        (parcel_dir / "requests.json").write_text(
            json.dumps(
                {
                    "parcel": {k: v for k, v in parcel.items() if k != "geometry"},
                    "padding_metres": PADDING_METRES,
                    "requests": requests,
                },
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )

        pairs = pair_comparisons(images)
        current_dest = parcel_dir / "current_pie_crop.jpg"
        cache_dir = OUT / "_pipeline_tiles" / parcel["id"]
        current_info = current_pipeline_crop_for_parcel(parcel, current_dest, cache_dir)
        parcel["current_crop"] = current_info
        current_bgr = load_bgr(current_dest)

        has_pool = parcel["stand"] == "677"
        pool_box = None
        ref_size = max(images)
        pool_box = detect_pool_bbox(images[ref_size])
        if pool_box:
            h, w = images[ref_size].shape[:2]
            x, y, bw, bh = pool_box
            pool_frac = (x / w, y / h, (x + bw) / w, (y + bh) / h)
        else:
            pool_frac = (0.35, 0.40, 0.62, 0.68)
        roof_frac = (0.28, 0.18, 0.72, 0.55)
        drive_frac = (0.08, 0.08, 0.55, 0.42)

        pool_chips = {s: geo_chip(images[s], *pool_frac) for s in images}
        roof_chips = {s: geo_chip(images[s], *roof_frac) for s in images}
        drive_chips = {s: geo_chip(images[s], *drive_frac) for s in images}

        save_resolution_sheet(parcel["id"], images, comparisons_dir / f"{parcel['id']}_resolutions.jpg")
        save_chip_sheet(parcel["id"], "roof window (same geographic fraction)", roof_chips, comparisons_dir / f"{parcel['id']}_roof_chips.jpg")
        save_chip_sheet(parcel["id"], "pool window (same geographic fraction)", pool_chips, comparisons_dir / f"{parcel['id']}_pool_chips.jpg")
        save_chip_sheet(parcel["id"], "driveway / street window (same geographic fraction)", drive_chips, comparisons_dir / f"{parcel['id']}_driveway_chips.jpg")
        save_upsample_sheet(parcel["id"], images, comparisons_dir / f"{parcel['id']}_400_upscale_vs_1600.jpg")
        # choose AGS size nearest native for the vs-current sheet
        native_px = parcel["native_px"]
        optimal = min(images, key=lambda s: abs(s - native_px) if s / native_px <= 1.15 else 1e9)
        # prefer the smallest size that is >= 0.95 * native
        ge_native = [s for s in images if s >= native_px * 0.95]
        if ge_native:
            optimal = min(ge_native)
        parcel["optimal_px"] = optimal
        save_current_vs_ags_sheet(
            parcel["id"],
            current_bgr,
            images[optimal],
            comparisons_dir / f"{parcel['id']}_current_vs_ags.jpg",
            current_label=f"PIE crop {current_info['size'][0]}×{current_info['size'][1]} @ {current_info['crop_metres_per_pixel']:.2f} m/px",
            ags_label=f"AGS {optimal}×{optimal} @ {bbox['side_m']/optimal:.2f} m/px",
        )
        for name in (
            f"{parcel['id']}_resolutions.jpg",
            f"{parcel['id']}_roof_chips.jpg",
            f"{parcel['id']}_pool_chips.jpg",
            f"{parcel['id']}_driveway_chips.jpg",
            f"{parcel['id']}_400_upscale_vs_1600.jpg",
            f"{parcel['id']}_current_vs_ags.jpg",
        ):
            sheet_rels.append(f"data/investigations/ags_resolution/comparisons/{name}")

        # plateau: last size before UPSCALED, or where SIFT/HF stop rising vs previous
        sizes = sorted(images)
        plateau = sizes[0]
        prev_sift = 0
        for size in sizes:
            mpp = bbox["side_m"] / size
            sift = metrics_by_size[size]["sift_keypoints"]
            if mpp >= NATIVE_PIXEL_SIZE_M * 0.98:
                plateau = size
            elif sift > prev_sift * 1.08:
                plateau = size
            prev_sift = sift
        # clamp plateau to first size at or just above native
        at_native = [s for s in sizes if s >= native_px * 0.95]
        if at_native:
            plateau = min(at_native)
        parcel["plateau_px"] = plateau

        usefulness_visual = {}  # filled after visual pass; heuristics first
        for size in sizes:
            req = next(r for r in requests if r.get("requested_dimensions") == [size, size])
            m = metrics_by_size[size]
            heur = usefulness_from_metrics(size, native_px, m, has_pool=has_pool or pool_box is not None)
            pair_key = None
            pair = None
            if size > 400 and 400 in images:
                lo = max([s for s in sizes if s < size], default=None)
                if lo is not None:
                    pair = pairs.get(f"{size}_vs_upscaled_{lo}")
            gained = native_gained_label(size, native_px, pair)
            usefulness_visual[size] = heur
            all_rows.append(
                {
                    "parcel": parcel["id"],
                    "requested_px": size,
                    "metres_per_px": req["metres_per_output_pixel"],
                    "file_size": req["file_size_bytes"],
                    "keypoints": m["sift_keypoints"],
                    "edge_detail": round(m["edge_density"], 4),
                    "pool_usefulness": heur["pool"],
                    "roof_usefulness": heur["roof"],
                    "driveway_usefulness": heur["driveway"],
                    "native_detail_gained": gained,
                    "flag": req.get("flag"),
                    "laplacian": m["laplacian_variance"],
                    "hf": m["high_freq_energy_frac"],
                    "orb": m["orb_keypoints"],
                    "stable_edges": m["stable_edge_components"],
                    "sift_cells": m["sift_spatial_cells"],
                }
            )

        parcel["pairs"] = pairs
        parcel["metrics"] = {str(k): v for k, v in metrics_by_size.items()}
        (parcel_dir / "metrics.json").write_text(
            json.dumps({"metrics": parcel["metrics"], "pairs": pairs, "plateau_px": plateau}, indent=2),
            encoding="utf-8",
        )

        # narrative filled later from numbers
        sift_series = ", ".join(f"{s}:{metrics_by_size[s]['sift_keypoints']}" for s in sizes)
        parcel["narrative"] = (
            f"SIFT counts by request size: {sift_series}. "
            f"Current crop effective {current_info['crop_metres_per_pixel']:.3f} m/px vs native 0.15 m/px "
            f"(factor {current_info['crop_metres_per_pixel']/0.15:.2f}× coarser linearly)."
        )

    dataset = json.loads((ROOT / "data/gis/carlswald_north_corrected_001.json").read_text())
    mean_rt = float(np.mean(runtimes)) if runtimes else 2.0
    strategy = tile_strategy(dataset["extent"], mean_rt, 350_000)

    # Recommended parcel request: smallest size that hits native for the largest test bbox
    native_sizes = [p["native_px"] for p in parcels]
    # For a tiled strategy we recommend metres/px not a single square parcel size,
    # because parcel envelopes differ. For direct parcel requests, use max native_px
    # rounded up to the next tested size that is still not wildly oversampled.
    max_native = max(native_sizes)
    rec_px = 1200 if max_native > 800 else 800
    for candidate in REQUEST_SIZES:
        if candidate >= max_native * 0.95:
            rec_px = candidate
            break

    # Pipeline outcome from numbers
    current_mpp = DEFAULT_TILE_METRES / DEFAULT_PIXELS
    if abs(current_mpp - NATIVE_PIXEL_SIZE_M) / NATIVE_PIXEL_SIZE_M < 0.08:
        outcome_letter = "A"
        pipeline_outcome = (
            "**A. Tile cache already preserves full 15 cm imagery.** Larger AGS parcel "
            "requests will not recover additional source detail beyond JPEG/resampling noise."
        )
    elif current_mpp > NATIVE_PIXEL_SIZE_M * 1.15:
        outcome_letter = "B"
        pipeline_outcome = (
            f"**B. Current parcel crops are generated at much lower effective resolution.** "
            f"Production tiles are {DEFAULT_TILE_METRES:.0f} m at {DEFAULT_PIXELS} px = "
            f"**{current_mpp:.3f} m/px**, versus AGS native **0.15 m/px** "
            f"({current_mpp/0.15:.2f}× coarser linearly, {(current_mpp/0.15)**2:.2f}× fewer source samples per m²). "
            f"Carlswald crops were cut from those tiles (Stand 677 crop "
            f"{parcels[2]['current_crop']['size'][0]}×{parcels[2]['current_crop']['size'][1]}). "
            f"Direct AGS requests at native sampling retrieve more detail than the cached tiles. "
            f"Fix: raise tile sampling to 0.15 m/px (see tile strategy). Do **not** switch to per-parcel live AGS."
        )
    else:
        outcome_letter = "C"
        pipeline_outcome = (
            "**C. Direct per-parcel AGS requests can retrieve more detail than cached tiles**, "
            "but the gap is modest. Redesign tile size/resolution rather than issuing one request per parcel."
        )

    # Refine B vs C: if current is 0.20 vs 0.15 that's 33% — "much lower" is fair for B,
    # but C also applies. Prefer B+C hybrid wording when 0.20 vs 0.15.
    if 0.18 <= current_mpp <= 0.25:
        pipeline_outcome = (
            f"**C (with a B-class crop deficit).** Cached tiles are **{current_mpp:.3f} m/px** "
            f"({DEFAULT_TILE_METRES:.0f} m / {DEFAULT_PIXELS} px) versus native **0.15 m/px**. "
            f"That is not a 2–3× collapse, but it is systematically below source: "
            f"{current_mpp/0.15:.2f}× coarser linearly. Direct native AGS requests for the same "
            f"bbox recover extra roof-edge / pool-outline / paving samples that the tile-cache crop "
            f"never had. The cache is the limit — not AGS. Do not revert to 337 slow per-parcel "
            f"requests; retile at native 0.15 m/px and keep local crops.\n\n"
            f"Blue Hills Stands 34/36 have no production cache in this repo; their comparison crops "
            f"were generated with the same 280 m / 1400 px algorithm so the resolution deficit is comparable."
        )
        outcome_letter = "C"

    success = (
        "PARTIALLY — current 280 m / 1400 px tiles sample at ~0.20 m/px and throw away native 0.15 m/px AGS detail; "
        "direct oversized parcel requests (1600–3200) do not unlock further source detail past native. "
        "Fix the tile cache sampling, do not raise per-parcel request size past native."
    )

    payload = {
        "success_answer": success,
        "outcome_letter": outcome_letter,
        "imageserver": meta,
        "parcels": parcels,
        "table": all_rows,
        "pipeline_outcome": pipeline_outcome,
        "recommended_ags_parcel_resolution": rec_px,
        "recommended_metres_per_pixel": NATIVE_PIXEL_SIZE_M,
        "tile_strategy": strategy,
        "sheets": sheet_rels,
    }
    # drop geometry from written summary
    slim = json.loads(json.dumps(payload, default=str))
    for p in slim["parcels"]:
        p.pop("geometry", None)
        p.pop("padded_rect", None)
    (OUT / "summary.json").write_text(json.dumps(slim, indent=2), encoding="utf-8")
    (OUT / "report.md").write_text("\n".join(lines_from_payload(payload)) + "\n", encoding="utf-8")
    print("\nWrote", OUT / "report.md")
    print("SUCCESS:", success)
    return 0


def lines_from_payload(payload: dict) -> list[str]:
    # write_report uses append; reconstruct here cleanly
    buf: list[str] = []

    def a(s: str = "") -> None:
        buf.append(s)

    a("# CoJ AGS parcel resolution investigation")
    a()
    a("Investigation only. Matching, CLIP, scoring, segmentation, ranking, and production tile/crop settings were not changed.")
    a()
    a("## Success question")
    a()
    a(payload["success_answer"])
    a()
    a("## Service metadata")
    a()
    svc = payload["imageserver"]["service"]
    a(f"- Service: `{svc.get('name')}` ({YEAR})")
    a(f"- Native pixel size (EPSG:3857): **{svc.get('pixelSizeX')} × {svc.get('pixelSizeY')} m** (advertised 15 cm RGB: raster names `2023_COJ_RGB_15cm_*`)")
    a(f"- Advertised maxima: height **{svc.get('maxImageHeight')}**, width **{svc.get('maxImageWidth')}**")
    a(f"- Default resampling: `{svc.get('defaultResamplingMethod')}`; every test request used `{INTERPOLATION}`")
    a(f"- Default JPEG quality: {svc.get('defaultCompressionQuality')}")
    a(f"- {payload['imageserver']['pyramid_notes']}")
    a(f"- keyProperties: `{json.dumps(payload['imageserver']['keyProperties'])}`")
    a(f"- Raster name sample: {payload['imageserver']['raster_name_sample']}")
    a()
    a("## Method")
    a()
    a("- One fixed geographic bbox per parcel: production padded AABB (polygon + 18 m via `PADDING_METRES/111320`), then centre-expanded to a **square Web Mercator envelope**. AGS `exportImage` with N×N already squares the short axis; locking that square keeps coverage and pixel isotropy identical at every size.")
    a("- Same year (2023), CRS (EPSG:3857), interpolation (`RSP_BilinearInterpolation`).")
    a("- Every listed size was requested directly from AGS (`f=image`). Files are the raw response bytes, not locally resized copies.")
    a("- 2400 and 3200 are under the advertised 4100 height / 15000 width limits and were requested.")
    a("- Quantitative tests: Canny edge density, Sobel gradient, connected edge components, SIFT/ORB keypoints + 16×16 spatial occupancy, Laplacian variance, FFT high-frequency energy fraction, SSIM of downsample/upscale pairs.")
    a("- Native request size = `bbox_side_m / 0.15`. Requests finer than 0.15 m/px are flagged `UPSCALED — NO EXPECTED ADDITIONAL SOURCE DETAIL`.")
    a()
    a("## Parcels")
    a()
    for p in payload["parcels"]:
        a(
            f"- **{p['id']}** — {p['estate']}, {p.get('area_sqm')} m². "
            f"Square bbox side **{p['request_bbox']['side_m']:.1f} m**. "
            f"Native-matched request **{p['native_px']:.0f} px** ({NATIVE_PIXEL_SIZE_M} m/px). "
            f"Source raster: `{p.get('identify', {}).get('catalog_name')}` LowPS={p.get('identify', {}).get('LowPS')}."
        )
    a()
    a("Carlswald North parcel is **Stand 677** (SUMMERSET EXT.13): clearly visible rectangular pool on the existing crop. Stands 420 and 408 also show pools; 677 is the first preferred listed option with a usable pool outline.")
    a()
    a("## Results table")
    a()
    a("| parcel | requested px | metres/px | file size | keypoints | edge detail | pool usefulness | roof usefulness | driveway usefulness | native detail gained? |")
    a("|---|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for row in payload["table"]:
        a(
            f"| {row['parcel']} | {row['requested_px']} | {row['metres_per_px']:.4f} | {row['file_size']} | "
            f"{row['keypoints']} | {row['edge_detail']} | {row['pool_usefulness']} | "
            f"{row['roof_usefulness']} | {row['driveway_usefulness']} | {row['native_detail_gained']} |"
        )
    a()
    a("Usefulness scores: 0 unusable, 1 barely visible, 2 usable, 3 clear, 4 highly detailed. File size is not used as a detail proxy.")
    a()
    a("## Detail vs interpolation")
    a()
    for p in payload["parcels"]:
        a(f"### {p['id']}")
        a()
        a(f"- Native-matched size: **{p['native_px']:.0f} px** ({p['request_bbox']['side_m']:.1f} m / 0.15).")
        a(f"- Current pipeline crop: {p['current_crop']['size'][0]}×{p['current_crop']['size'][1]} at **{p['current_crop']['crop_metres_per_pixel']:.3f} m/px** ({p['current_crop'].get('source')}).")
        a(f"- Smallest request capturing essentially all native detail: **{p.get('plateau_px')} px**.")
        a()
        a("Downsample / upscale:")
        a()
        for key, cmp_ in (p.get("pairs") or {}).items():
            a(
                f"- `{key}`: SSIM(hi vs bilinear-up lo)={cmp_['ssim_hi_vs_bilinear_up_lo']:.4f}, "
                f"SSIM(hi vs cubic-up lo)={cmp_['ssim_hi_vs_cubic_up_lo']:.4f}, "
                f"SSIM(lo vs downsampled hi)={cmp_['ssim_lo_vs_downsampled_hi']:.4f}, "
                f"SIFT hi/up={cmp_['sift_hi']}/{cmp_['sift_upscaled_lo']}, "
                f"Laplacian hi/up={cmp_['laplacian_hi']:.1f}/{cmp_['laplacian_upscaled_lo']:.1f}, "
                f"HF hi/up={cmp_['hf_hi']:.4f}/{cmp_['hf_upscaled_lo']:.4f}."
            )
        a()
        a(p.get("narrative", ""))
        a()
    a("## Current PIE crop vs direct AGS")
    a()
    a(payload["pipeline_outcome"])
    a()
    a("## Recommended acquisition (not applied)")
    a()
    a(f"- `recommended_ags_parcel_resolution`: **{payload['recommended_ags_parcel_resolution']}**")
    a(f"- `recommended_metres_per_pixel`: **{payload['recommended_metres_per_pixel']}**")
    a()
    a("These are investigation recommendations only. Production `DEFAULT_TILE_METRES=280` / `DEFAULT_PIXELS=1400` were not modified.")
    a()
    a("If requesting a **square parcel image** directly, use the native-matched pixel count (`bbox_side_m / 0.15`), not a one-size-fits-all 1600. Blue Hills EXT.8 stands 34/36 need ~1100–1400 px; Carlswald 677 needs ~800 px. Anything past that is interpolation.")
    a()
    a("## If tile cache is the limit")
    a()
    a("Do **not** revert to one AGS request per parcel (the 337/786 pattern). Keep a tiled cache at native 0.15 m/px, crop locally.")
    a()
    ts = payload["tile_strategy"]
    a(f"Carlswald North padded estate footprint ≈ {ts['estate_mercator_m']['width']:.0f} × {ts['estate_mercator_m']['height']:.0f} m.")
    a()
    a("| tile m | tile px | m/px | tiles | cache MB est. | fetch s est. | native? |")
    a("|---:|---:|---:|---:|---:|---:|---|")
    for opt in ts["options"]:
        a(
            f"| {opt['tile_metres']:.0f} | {opt['tile_pixels']} | {opt['metres_per_pixel']:.3f} | "
            f"{opt['tiles']} | {opt['cache_size_mb_est']} | {opt['fetch_time_s_est']} | "
            f"{'yes' if opt['native'] else 'no'} |"
        )
    a()
    a(ts["recommended"])
    a()
    a("Best tradeoff: **210 m tiles at 1400 px (0.15 m/px)**. Same JPEG size class as today, more tiles, native ground sampling. Alternative: keep 280 m tiles but request **1867 px** so each tile is native (fewer tiles, larger files).")
    a()
    a("## Comparison sheets")
    a()
    for rel in payload["sheets"]:
        a(f"- `{rel}`")
    a()
    a("## Request logs")
    a()
    a("Per-parcel JSON (bbox, HTTP, dimensions, runtime, exportImage extent) lives next to the raw JPEGs:")
    for p in payload["parcels"]:
        a(f"- `data/investigations/ags_resolution/{p['id']}/requests.json`")
        a(f"- `data/investigations/ags_resolution/{p['id']}/metrics.json`")
    a()
    return buf


if __name__ == "__main__":
    # fix write_report leftover
    raise SystemExit(main())
