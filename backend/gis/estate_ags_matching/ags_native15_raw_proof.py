"""Isolated native15 Council/AGS raw-imagery proof helpers.

Does not modify OS v1, FastSAM, Scoring v2, Hybrid Pool Geometry, native15
cache profile, production ranking, inventory records, or the listing pool gate.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from backend.gis.dataset_registry import CORRECT_CARLSWALD_NORTH
from backend.imagery.ags_client import AGSAerialClient
from backend.imagery.estate_tiles import (
    AGS_SERVICE_ID,
    CACHE_PROFILES,
    NATIVE_PIXEL_SIZE_M,
    PADDING_METRES,
    WEB_MERCATOR_RADIUS,
    pixels_for_extent,
)
from backend.vision.object_segmentation import parcel_mask_from_geometry

REPO_ROOT = Path(__file__).resolve().parents[3]
GIS_PATH = REPO_ROOT / "data" / "gis" / f"{CORRECT_CARLSWALD_NORTH}.json"
OS_DIR = REPO_ROOT / "data" / "investigations" / "object_segmentation_v1" / "carlswald_north" / "json"
INVENTORY_PATH = REPO_ROOT / "data" / "estate_inventory" / CORRECT_CARLSWALD_NORTH / "current.jsonl"
OUT_DIR = (
    REPO_ROOT
    / "data"
    / "investigations"
    / "estate_property_inventory_v1"
    / "unknown_diagnostic"
    / "ags_raw_proof"
)
PREFERRED_STAND = "677"
AGS_IMAGESERVER_URL = (
    "https://ags.joburg.org.za/server/rest/services/"
    "AerialPhotography/2023/ImageServer"
)
PROOF_STAND_REQUIREMENTS = (
    "clearly visible house/roof",
    "swimming pool",
    "driveway",
    "garden/open ground",
    "OS v1 pool CONFIRMED (inventory YES)",
)


def _mercator(lat: float, lon: float) -> tuple[float, float]:
    x = WEB_MERCATOR_RADIUS * math.radians(lon)
    y = WEB_MERCATOR_RADIUS * math.log(math.tan(math.pi / 4.0 + math.radians(lat) / 2.0))
    return x, y


def _inv_mercator(x: float, y: float) -> tuple[float, float]:
    lon = math.degrees(x / WEB_MERCATOR_RADIUS)
    lat = math.degrees(2.0 * math.atan(math.exp(y / WEB_MERCATOR_RADIUS)) - math.pi / 2.0)
    return lat, lon


def load_dataset(path: Path | None = None) -> dict[str, Any]:
    return json.loads((path or GIS_PATH).read_text(encoding="utf-8"))


def load_os(stand_number: str, os_dir: Path | None = None) -> dict[str, Any]:
    payload = json.loads(((os_dir or OS_DIR) / f"{stand_number}.json").read_text(encoding="utf-8"))
    return payload


def inventory_row(stand_number: str, path: Path | None = None) -> dict[str, Any] | None:
    for line in (path or INVENTORY_PATH).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if str(row.get("stand_number")) == str(stand_number):
            return row
    return None


def parcel_bbox(geometry: Mapping[str, Any]) -> tuple[float, float, float, float]:
    xs, ys = [], []
    for ring in geometry.get("rings") or []:
        for x, y in ring:
            xs.append(float(x))
            ys.append(float(y))
    if not xs:
        raise ValueError("parcel geometry has no rings")
    return min(xs), min(ys), max(xs), max(ys)


def crop_parcel_from_tile(tile: Mapping[str, Any], geometry: Mapping[str, Any], dest: Path) -> bool:
    """Same integer crop as frozen native15 `crop_parcel` (JPEG quality 90)."""
    path = Path(tile["path"])
    if not path.is_file():
        return False
    image = Image.open(path).convert("RGB")
    min_lon, min_lat, max_lon, max_lat = parcel_bbox(geometry)
    pad = PADDING_METRES / 111_320
    min_lon -= pad
    max_lon += pad
    min_lat -= pad
    max_lat += pad
    w, h = image.size

    def px(lon: float, lat: float) -> tuple[int, int]:
        x = (lon - float(tile["min_lon"])) / max(float(tile["max_lon"]) - float(tile["min_lon"]), 1e-12)
        y = (float(tile["max_lat"]) - lat) / max(float(tile["max_lat"]) - float(tile["min_lat"]), 1e-12)
        return int(x * (w - 1)), int(y * (h - 1))

    x0, y1 = px(min_lon, min_lat)
    x1, y0 = px(max_lon, max_lat)
    left, right = sorted((max(0, x0), max(0, x1)))
    top, bottom = sorted((max(0, y0), max(0, y1)))
    right = min(w, max(right, left + 8))
    bottom = min(h, max(bottom, top + 8))
    crop = image.crop((left, top, right, bottom))
    if min(crop.size) < 24:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    crop.save(dest, quality=90)
    return True


def find_parcel(dataset: Mapping[str, Any], stand_number: str) -> dict[str, Any]:
    matches = [
        item
        for item in (dataset.get("parcels") or [])
        if str(item.get("stand_number")) == str(stand_number)
    ]
    if not matches:
        raise KeyError(f"stand {stand_number} not in GIS dataset")
    return matches[0]


def native15_tile_grid(extent: Mapping[str, float], year: int = 2023) -> list[dict[str, Any]]:
    """Same grid as EstateTileIndex.build() for profile native15. Does not download."""
    profile = CACHE_PROFILES["native15"]
    tile_metres = float(profile.tile_metres)
    width_px = pixels_for_extent(tile_metres, tile_metres, NATIVE_PIXEL_SIZE_M)[0]
    xmin, ymin = _mercator(extent["min_latitude"], extent["min_longitude"])
    xmax, ymax = _mercator(extent["max_latitude"], extent["max_longitude"])
    pad = tile_metres * 0.15
    xmin -= pad
    ymin -= pad
    xmax += pad
    ymax += pad
    cols = max(1, int(math.ceil((xmax - xmin) / tile_metres)))
    rows = max(1, int(math.ceil((ymax - ymin) / tile_metres)))
    tiles = []
    for row in range(rows):
        for col in range(cols):
            x0 = xmin + col * tile_metres
            y0 = ymin + row * tile_metres
            x1 = x0 + tile_metres
            y1 = y0 + tile_metres
            min_lat, min_lon = _inv_mercator(x0, y0)
            max_lat, max_lon = _inv_mercator(x1, y1)
            stem = f"tile_{year}_{profile.profile_id}_{row:02d}_{col:02d}"
            tiles.append(
                {
                    "row": row,
                    "col": col,
                    "stem": stem,
                    "min_lon": min_lon,
                    "min_lat": min_lat,
                    "max_lon": max_lon,
                    "max_lat": max_lat,
                    "xmin": x0,
                    "ymin": y0,
                    "xmax": x1,
                    "ymax": y1,
                    "width": width_px,
                    "height": width_px,
                    "metres_per_pixel": tile_metres / width_px,
                    "profile": profile.profile_id,
                    "ags_service": f"AerialPhotography/{year}",
                    "year": year,
                }
            )
    return tiles


def covering_tile(tiles: Sequence[Mapping[str, Any]], min_lon: float, min_lat: float, max_lon: float, max_lat: float) -> dict[str, Any]:
    cx = (min_lon + max_lon) / 2.0
    cy = (min_lat + max_lat) / 2.0
    for tile in tiles:
        if tile["min_lon"] <= cx <= tile["max_lon"] and tile["min_lat"] <= cy <= tile["max_lat"]:
            return dict(tile)
    if not tiles:
        raise ValueError("empty native15 tile grid")
    return dict(tiles[0])


def contour_pixel_stats(contour: Sequence[Sequence[float]], width: int, height: int) -> dict[str, Any]:
    if not contour:
        return {"present": False}
    pts = np.array(
        [[float(x) * (width - 1), float(y) * (height - 1)] for x, y in contour],
        dtype=np.float32,
    )
    xs = pts[:, 0]
    ys = pts[:, 1]
    bbox_w = float(xs.max() - xs.min())
    bbox_h = float(ys.max() - ys.min())
    area_px = float(cv2.contourArea(pts.reshape(-1, 1, 2).astype(np.int32))) if len(pts) >= 3 else 0.0
    width_px = bbox_w
    length_px = bbox_h
    min_rect_w = None
    min_rect_h = None
    if len(pts) >= 5:
        rect = cv2.minAreaRect(pts)
        rw, rh = float(rect[1][0]), float(rect[1][1])
        min_rect_w, min_rect_h = sorted((rw, rh))
        width_px, length_px = min_rect_w, min_rect_h
    return {
        "present": True,
        "bbox_px": [round(bbox_w, 1), round(bbox_h, 1)],
        "min_area_rect_px": None if min_rect_w is None else [round(min_rect_w, 1), round(min_rect_h, 1)],
        "approx_width_px": round(width_px, 1),
        "approx_length_px": round(length_px, 1),
        "area_px": round(area_px, 1),
        "centroid_xy_px": [round(float(xs.mean()), 1), round(float(ys.mean()), 1)],
    }


def object_pixel_dimensions(os_payload: Mapping[str, Any], crop_wh: tuple[int, int]) -> dict[str, Any]:
    width, height = crop_wh
    out: dict[str, Any] = {}
    for kind in ("pool", "building", "driveway"):
        block = os_payload.get(kind) or {}
        stats = contour_pixel_stats(block.get("contour") or [], width, height)
        geom = block.get("geometry") or {}
        stats["os_status"] = block.get("status")
        stats["os_area_px"] = geom.get("area_px")
        stats["os_area_m2"] = geom.get("area_m2")
        if stats.get("approx_width_px") and stats.get("approx_length_px"):
            stats["approx_width_m"] = round(float(stats["approx_width_px"]) * NATIVE_PIXEL_SIZE_M, 2)
            stats["approx_length_m"] = round(float(stats["approx_length_px"]) * NATIVE_PIXEL_SIZE_M, 2)
        out[kind] = stats
    return out


def fetch_ags_service_metadata(client: AGSAerialClient | None = None) -> dict[str, Any]:
    import httpx

    timeout = 40.0 if client is None else client.timeout_s
    with httpx.Client(timeout=timeout, follow_redirects=True) as http:
        response = http.get(AGS_IMAGESERVER_URL, params={"f": "pjson"})
        response.raise_for_status()
        payload = response.json()
    return {
        "url": AGS_IMAGESERVER_URL,
        "name": payload.get("name"),
        "description": payload.get("description"),
        "copyright": payload.get("copyrightText"),
        "current_version": payload.get("currentVersion"),
        "pixel_size_x_m": payload.get("pixelSizeX"),
        "pixel_size_y_m": payload.get("pixelSizeY"),
        "default_resampling_method": payload.get("defaultResamplingMethod"),
        "default_compression_quality": payload.get("defaultCompressionQuality"),
        "max_image_width": payload.get("maxImageWidth"),
        "max_image_height": payload.get("maxImageHeight"),
        "spatial_reference": payload.get("spatialReference"),
        "imagery_date_or_version": payload.get("description") or payload.get("copyrightText"),
        "time_info": payload.get("timeInfo"),
    }


def fetch_covering_rasters(min_lon: float, min_lat: float, max_lon: float, max_lat: float, timeout_s: float = 40.0) -> dict[str, Any]:
    import httpx

    envelope = {
        "xmin": min_lon,
        "ymin": min_lat,
        "xmax": max_lon,
        "ymax": max_lat,
        "spatialReference": {"wkid": 4326},
    }
    params = {
        "where": "1=1",
        "geometry": json.dumps(envelope, separators=(",", ":")),
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "Name,MinPS,MaxPS,LowPS,HighPS,Tag,GroupName,ProductName,Category",
        "returnGeometry": "false",
        "f": "pjson",
    }
    with httpx.Client(timeout=timeout_s, follow_redirects=True) as http:
        response = http.get(f"{AGS_IMAGESERVER_URL}/query", params=params)
        response.raise_for_status()
        payload = response.json()
    features = payload.get("features") or []
    names = []
    for feat in features:
        attrs = feat.get("attributes") or {}
        if attrs.get("Name"):
            names.append(attrs)
    return {"count": len(names), "rasters": names[:12], "error": payload.get("error")}


def download_native15_tile(tile: Mapping[str, Any], dest: Path, year: int = 2023) -> dict[str, Any]:
    dest.parent.mkdir(parents=True, exist_ok=True)
    reused = dest.is_file() and dest.stat().st_size > 1000
    if not reused:
        client = AGSAerialClient(timeout_s=60.0)
        client.export_bbox_to_file(
            dest,
            min_lon=float(tile["min_lon"]),
            min_lat=float(tile["min_lat"]),
            max_lon=float(tile["max_lon"]),
            max_lat=float(tile["max_lat"]),
            width=int(tile["width"]),
            height=int(tile["height"]),
            year=year,
        )
    sidecar = {
        "bbox": {
            "min_lon": tile["min_lon"],
            "min_lat": tile["min_lat"],
            "max_lon": tile["max_lon"],
            "max_lat": tile["max_lat"],
        },
        "bbox_3857": {
            "xmin": tile["xmin"],
            "ymin": tile["ymin"],
            "xmax": tile["xmax"],
            "ymax": tile["ymax"],
        },
        "width": tile["width"],
        "height": tile["height"],
        "effective_metres_per_pixel": {
            "x": (tile["xmax"] - tile["xmin"]) / max(int(tile["width"]), 1),
            "y": (tile["ymax"] - tile["ymin"]) / max(int(tile["height"]), 1),
        },
        "ags_service": AGS_SERVICE_ID,
        "year": year,
        "profile": "native15",
        "interpolation": "RSP_BilinearInterpolation",
        "source_url": AGS_IMAGESERVER_URL,
        "reused_local_file": reused,
    }
    dest.with_suffix(".json").write_text(json.dumps(sidecar, indent=2) + "\n", encoding="utf-8")
    with Image.open(dest) as image:
        actual_wh = list(image.size)
    return {
        "path": str(dest),
        "reused_local_file": reused,
        "requested_wh": [int(tile["width"]), int(tile["height"])],
        "actual_wh": actual_wh,
        "sidecar": sidecar,
    }


def _font(size: int) -> ImageFont.ImageFont:
    path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    return ImageFont.truetype(str(path), size) if path.is_file() else ImageFont.load_default()


def _draw_contour_rgb(image: Image.Image, contour: Sequence[Sequence[float]], color: tuple[int, int, int], width: int = 2) -> None:
    if not contour:
        return
    w, h = image.size
    pts = [(int(float(x) * (w - 1)), int(float(y) * (h - 1))) for x, y in contour]
    if len(pts) < 3:
        return
    draw = ImageDraw.Draw(image)
    draw.line(pts + [pts[0]], fill=color, width=width)


def render_proof_panel(
    raw_rgb: Image.Image,
    parcel: Mapping[str, Any],
    os_payload: Mapping[str, Any],
    meta_lines: Sequence[str],
    object_lines: Sequence[str],
) -> Image.Image:
    raw = raw_rgb.convert("RGB")
    w, h = raw.size
    boundary = raw.copy()
    analysis = raw.copy()
    mask = parcel_mask_from_geometry((w, h), parcel["geometry"])
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    def _with_boundary(src: Image.Image, thickness: int) -> Image.Image:
        bgr = cv2.cvtColor(np.array(src), cv2.COLOR_RGB2BGR)
        cv2.drawContours(bgr, contours, -1, (0, 220, 255), thickness)
        return Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))

    boundary = _with_boundary(boundary, 2)
    analysis = _with_boundary(analysis, 1)
    pool = os_payload.get("pool") or {}
    building = os_payload.get("building") or {}
    driveway = os_payload.get("driveway") or {}
    _draw_contour_rgb(analysis, driveway.get("contour") or [], (80, 200, 80), 2)
    _draw_contour_rgb(analysis, building.get("contour") or [], (220, 50, 50), 2)
    _draw_contour_rgb(analysis, pool.get("contour") or [], (40, 180, 255), 2)

    def _wrap(line: str, max_chars: int = 148) -> list[str]:
        if len(line) <= max_chars:
            return [line]
        words = line.split()
        rows: list[str] = []
        current = ""
        for word in words:
            trial = (current + " " + word).strip()
            if len(trial) <= max_chars:
                current = trial
            else:
                if current:
                    rows.append(current)
                current = word
        if current:
            rows.append(current)
        return rows or [line]

    wrapped_meta = [part for line in meta_lines for part in _wrap(line)]
    wrapped_obj = [part for line in object_lines for part in _wrap(line, 160)]
    gap = 12
    caption_h = 28
    tile_w, tile_h = w, h + caption_h
    row_w = tile_w * 3 + gap * 4
    header_h = 18 + 17 * len(wrapped_meta)
    footer_h = 18 + 17 * len(wrapped_obj)
    canvas_h = header_h + tile_h + footer_h + 24
    canvas = Image.new("RGB", (row_w, canvas_h), (16, 16, 16))
    draw = ImageDraw.Draw(canvas)
    font = _font(14)
    font_sm = _font(13)
    font_cap = _font(14)
    y = 8
    for line in wrapped_meta:
        draw.text((12, y), line, font=font, fill=(235, 235, 235))
        y += 17
    captions = (
        "1. Raw native15 parcel crop  (no overlays; analysis pixels)",
        "2. Same crop + GIS erf boundary",
        "3. OS v1 analysis  pool=cyan  building=red  driveway=green",
    )
    x = gap
    for image, caption in ((raw, captions[0]), (boundary, captions[1]), (analysis, captions[2])):
        draw.text((x, header_h), caption, font=font_cap, fill=(210, 210, 210))
        canvas.paste(image, (x, header_h + caption_h))
        x += tile_w + gap
    y = header_h + tile_h + 10
    for line in wrapped_obj:
        draw.text((12, y), line, font=font_sm, fill=(220, 220, 180))
        y += 17
    return canvas


def run_proof(stand_number: str = PREFERRED_STAND, out_dir: Path | None = None) -> dict[str, Any]:
    """Download the covering native15 AGS tile and write the labelled proof panel."""
    out = Path(out_dir or OUT_DIR)
    out.mkdir(parents=True, exist_ok=True)
    dataset = load_dataset()
    parcel = find_parcel(dataset, stand_number)
    os_payload = load_os(stand_number)
    inv = inventory_row(stand_number)
    min_lon, min_lat, max_lon, max_lat = parcel_bbox(parcel["geometry"])
    tiles = native15_tile_grid(dataset["extent"])
    tile = covering_tile(tiles, min_lon, min_lat, max_lon, max_lat)
    tile_path = out / "tiles" / f"{tile['stem']}.jpg"
    download = download_native15_tile(tile, tile_path)
    tile_for_crop = dict(tile)
    tile_for_crop["path"] = tile_path
    crop_path = out / f"{stand_number}_ags_native15_raw_crop.jpg"
    if not crop_parcel_from_tile(tile_for_crop, parcel["geometry"], crop_path):
        raise RuntimeError(f"failed to crop stand {stand_number} from {tile['stem']}")
    raw = Image.open(crop_path).convert("RGB")
    crop_wh = raw.size
    pad = PADDING_METRES / 111_320
    ground_w = (max_lon - min_lon + 2 * pad) * 111_320
    ground_h = (max_lat - min_lat + 2 * pad) * 111_320
    objects = object_pixel_dimensions(os_payload, crop_wh)
    try:
        service = fetch_ags_service_metadata()
    except Exception as exc:  # noqa: BLE001
        service = {
            "url": AGS_IMAGESERVER_URL,
            "name": AGS_SERVICE_ID,
            "description": "CoJ Aerial Photography 2023",
            "copyright": "CoJ Aerial Photography 2023",
            "imagery_date_or_version": "CoJ Aerial Photography 2023",
            "pixel_size_x_m": NATIVE_PIXEL_SIZE_M,
            "pixel_size_y_m": NATIVE_PIXEL_SIZE_M,
            "error": f"{type(exc).__name__}: {exc}",
        }
    try:
        rasters = fetch_covering_rasters(min_lon, min_lat, max_lon, max_lat)
    except Exception as exc:  # noqa: BLE001
        rasters = {"count": 0, "rasters": [], "error": f"{type(exc).__name__}: {exc}"}
    meta_lines, object_lines = build_label_lines(
        stand_number=stand_number,
        parcel=parcel,
        tile=tile,
        crop_wh=crop_wh,
        service=service,
        rasters=rasters,
        tile_download=download,
        crop_ground_m=(round(ground_w, 1), round(ground_h, 1)),
        objects=objects,
        inventory_status=None if inv is None else inv.get("pool_status"),
        os_payload=os_payload,
    )
    panel = render_proof_panel(raw, parcel, os_payload, meta_lines, object_lines)
    panel_path = out / f"{stand_number}_ags_native15_raw_proof.jpg"
    panel.save(panel_path, quality=92, subsampling=0)
    os_wh = os_payload.get("crop_wh") or []
    payload = {
        "production_ranking_modified": False,
        "inventory_current_modified": False,
        "os_v1_modified": False,
        "native15_pipeline_modified": False,
        "google_bing_or_other_satellite_used": False,
        "stand_number": stand_number,
        "estate": "Carlswald North",
        "township": parcel.get("township"),
        "gis_dataset": CORRECT_CARLSWALD_NORTH,
        "inventory_pool_status": None if inv is None else inv.get("pool_status"),
        "os_pool_status": (os_payload.get("pool") or {}).get("status"),
        "imagery_source": AGS_IMAGESERVER_URL,
        "ags_service": AGS_SERVICE_ID,
        "cache_profile": "native15",
        "source_tile_id": tile["stem"],
        "source_tile_ids": [tile["stem"]],
        "native_metres_per_pixel": {
            "x": service.get("pixel_size_x_m"),
            "y": service.get("pixel_size_y_m"),
        },
        "requested_metres_per_pixel": tile["metres_per_pixel"],
        "resampled_from_native": abs(float(tile["metres_per_pixel"]) - float(service.get("pixel_size_x_m") or 0.15))
        / 0.15
        > 0.04,
        "ags_interpolation": "RSP_BilinearInterpolation",
        "came_from_cached_production_tiles": False,
        "came_from_live_ags_exportImage": True,
        "crop_is_integer_extract_from_ags_tile": True,
        "crop_jpeg_quality": 90,
        "crop_pixel_dimensions": list(crop_wh),
        "os_v1_crop_wh": os_wh,
        "crop_matches_os_v1_wh": list(crop_wh) == list(os_wh),
        "approx_ground_dimensions_m": [round(ground_w, 1), round(ground_h, 1)],
        "imagery_date_or_version": service.get("imagery_date_or_version"),
        "ags_service_metadata": service,
        "covering_mosaic_rasters": rasters,
        "object_pixel_dimensions": objects,
        "tile": {k: tile[k] for k in ("stem", "row", "col", "width", "height", "metres_per_pixel", "ags_service")},
        "tile_download": download,
        "raw_crop_path": str(crop_path),
        "proof_panel_path": str(panel_path),
        "requirements": list(PROOF_STAND_REQUIREMENTS),
    }
    meta_path = out / f"{stand_number}_ags_native15_raw_proof.json"
    meta_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    payload["metadata_path"] = str(meta_path)
    return payload


def build_label_lines(
    *,
    stand_number: str,
    parcel: Mapping[str, Any],
    tile: Mapping[str, Any],
    crop_wh: tuple[int, int],
    service: Mapping[str, Any],
    rasters: Mapping[str, Any],
    tile_download: Mapping[str, Any],
    crop_ground_m: tuple[float, float],
    objects: Mapping[str, Any],
    inventory_status: str | None,
    os_payload: Mapping[str, Any],
) -> tuple[list[str], list[str]]:
    native_x = float(service.get("pixel_size_x_m") or NATIVE_PIXEL_SIZE_M)
    native_y = float(service.get("pixel_size_y_m") or NATIVE_PIXEL_SIZE_M)
    requested = float(tile["metres_per_pixel"])
    resampled = abs(requested - native_x) / native_x > 0.04
    raster_items = list(rasters.get("rasters") or [])
    primary = [item.get("Name") for item in raster_items if item.get("Category") == 1 and item.get("Name")]
    raster_names = primary or [item.get("Name") for item in raster_items if item.get("Name")]
    raster_txt = (
        f"primary={', '.join(primary[:2])}"
        if primary
        else (", ".join(str(name) for name in raster_names[:3]) if raster_names else "mosaic catalog Name not returned")
    )
    pool = os_payload.get("pool") or {}
    meta = [
        f"Stand {stand_number}   estate=Carlswald North   township={parcel.get('township')}   "
        f"GIS dataset={CORRECT_CARLSWALD_NORTH}   inventory={inventory_status}   "
        f"OS v1 pool={pool.get('status')} CLIP={float((pool.get('clip') or {}).get('pool') or 0):.3f}",
        f"Imagery source: City of Johannesburg AGS  {AGS_IMAGESERVER_URL}",
        f"AGS service={service.get('name')}  copyright={service.get('copyright')}  "
        f"imagery date/version={service.get('imagery_date_or_version')}  "
        f"server={service.get('current_version')}",
        f"Cache profile=native15  source tile ID={tile['stem']}  "
        f"tile request={tile['width']}x{tile['height']} px over {CACHE_PROFILES['native15'].tile_metres:.0f} m",
        f"Native AGS GSD={native_x:.6f} x {native_y:.6f} m/px   requested GSD={requested:.4f} m/px   "
        f"resampled={resampled}  interpolation=RSP_BilinearInterpolation (AGS default Bilinear)",
        f"This crop: integer extract from the AGS tile JPEG, then JPEG quality=90 via crop_parcel "
        f"(same function as frozen native15). Not Google/Bing. "
        f"Live AGS download this run={not tile_download.get('reused_local_file')}.",
        f"Crop pixels={crop_wh[0]} x {crop_wh[1]}   approx ground={crop_ground_m[0]:.1f} x {crop_ground_m[1]:.1f} m   "
        f"erf GIS area={parcel.get('area_sqm')} m2   mosaic rasters={raster_txt}",
    ]
    pool_s = objects.get("pool") or {}
    house_s = objects.get("building") or {}
    drive_s = objects.get("driveway") or {}
    obj = [
        "Visible-object pixel sizes on this crop (OS v1 contours, 1 analysis pixel = 0.15 m):",
        (
            f"  pool ≈ {pool_s.get('approx_length_px')} x {pool_s.get('approx_width_px')} px "
            f"({pool_s.get('approx_length_m')} x {pool_s.get('approx_width_m')} m)  "
            f"bbox={pool_s.get('bbox_px')}  OS area={pool_s.get('os_area_px')} px / {pool_s.get('os_area_m2')} m2"
        ),
        (
            f"  house/roof ≈ {house_s.get('approx_length_px')} x {house_s.get('approx_width_px')} px "
            f"({house_s.get('approx_length_m')} x {house_s.get('approx_width_m')} m)  "
            f"bbox={house_s.get('bbox_px')}  OS area={house_s.get('os_area_px')} px / {house_s.get('os_area_m2')} m2"
        ),
        (
            f"  driveway width ≈ {drive_s.get('approx_width_px')} px "
            f"({drive_s.get('approx_width_m')} m)  length ≈ {drive_s.get('approx_length_px')} px  "
            f"bbox={drive_s.get('bbox_px')}  OS area={drive_s.get('os_area_px')} px / {drive_s.get('os_area_m2')} m2"
        ),
        "Displayed at native crop resolution (1 panel pixel = 1 analysis pixel). No contrast stretch, sharpen, or satellite substitute.",
    ]
    return meta, obj
