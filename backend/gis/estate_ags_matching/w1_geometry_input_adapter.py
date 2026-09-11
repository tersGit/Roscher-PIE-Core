"""Fail-closed W1 inputs for the opt-in parcel-bound geometry module.

The W1 builder created each crop from a frozen CoJ polygon's recorded
centroid, expressed in EPSG:3857, at 0.15 metres per pixel.  This adapter
replays that documented input contract; it neither detects image objects nor
changes geometry scoring.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import cv2
import numpy as np

W1_GEOJSON_SHA256 = "6a375bf542bcff28c6a3ee862f9e0c3c9a5395d0497b4159027c40b75cf7be3a"
CROP_SIZE_PX = 900
METRES_PER_PIXEL = 0.15
CROP_SIZE_METRES = CROP_SIZE_PX * METRES_PER_PIXEL
WEB_MERCATOR_RADIUS = 6378137.0


class W1InputError(RuntimeError):
    """Raised when an authoritative W1 input cannot be proven complete."""


@dataclass(frozen=True)
class CropGeoreference:
    property_id: str
    extension: int
    crop_path: str
    centroid_x_3857: float
    centroid_y_3857: float
    xmin_3857: float
    ymin_3857: float
    xmax_3857: float
    ymax_3857: float

    @property
    def affine(self) -> tuple[float, float, float, float, float, float]:
        return (METRES_PER_PIXEL, 0.0, self.xmin_3857, 0.0, -METRES_PER_PIXEL, self.ymax_3857)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mercator(latitude: float, longitude: float) -> tuple[float, float]:
    return (
        WEB_MERCATOR_RADIUS * math.radians(longitude),
        WEB_MERCATOR_RADIUS * math.log(math.tan(math.pi / 4 + math.radians(latitude) / 2)),
    )


def pixel_to_world(georef: CropGeoreference, pixel_x: float, pixel_y: float) -> tuple[float, float]:
    return georef.xmin_3857 + pixel_x * METRES_PER_PIXEL, georef.ymax_3857 - pixel_y * METRES_PER_PIXEL


def world_to_pixel(georef: CropGeoreference, x: float, y: float) -> tuple[float, float]:
    return (x - georef.xmin_3857) / METRES_PER_PIXEL, (georef.ymax_3857 - y) / METRES_PER_PIXEL


def _rings(geometry: dict[str, Any]) -> Iterable[list[list[float]]]:
    if geometry.get("rings"):
        yield from geometry["rings"]
    elif geometry.get("type") == "Polygon":
        yield from geometry["coordinates"]
    elif geometry.get("type") == "MultiPolygon":
        for polygon in geometry["coordinates"]:
            yield from polygon


def _ring_pixels(ring: list[list[float]], georef: CropGeoreference) -> np.ndarray:
    points = []
    for longitude, latitude in ring:
        points.append(world_to_pixel(georef, *mercator(float(latitude), float(longitude))))
    return np.rint(np.asarray(points, dtype=np.float64)).astype(np.int32)


def stored_centre_inside_polygon(geometry: dict[str, Any], longitude: float, latitude: float) -> bool:
    """Apply the polygon's even-odd rule at the unrounded stored centre."""
    inside = False
    for ring in _rings(geometry):
        for start, end in zip(ring, ring[1:] + ring[:1]):
            x1, y1 = map(float, start)
            x2, y2 = map(float, end)
            if (y1 > latitude) != (y2 > latitude):
                intersection_x = (x2 - x1) * (latitude - y1) / (y2 - y1) + x1
                if longitude < intersection_x:
                    inside = not inside
    return inside


def rasterize_parcel(geometry: dict[str, Any], georef: CropGeoreference) -> np.ndarray:
    """Rasterize polygon rings at source resolution, preserving holes.

    CoJ ArcGIS ``rings`` uses orientation for outer/inner rings.  A robust
    even-odd fill is independent of source winding and handles multipart
    geometries and clipped edges deterministically.
    """
    mask = np.zeros((CROP_SIZE_PX, CROP_SIZE_PX), dtype=np.uint8)
    for ring in _rings(geometry):
        pixels = _ring_pixels(ring, georef)
        if len(pixels) >= 3:
            cv2.fillPoly(mask, [pixels], 1)
    # Even-odd composition: drawing all rings by XOR makes inner rings holes.
    parity = np.zeros_like(mask)
    for ring in _rings(geometry):
        pixels = _ring_pixels(ring, georef)
        if len(pixels) >= 3:
            layer = np.zeros_like(mask)
            cv2.fillPoly(layer, [pixels], 1)
            parity ^= layer
    return parity.astype(bool)


def georeference_for(feature: dict[str, Any], crop_path: str) -> CropGeoreference:
    props = feature["properties"]
    latitude = float(props["centroid_latitude"])
    longitude = float(props["centroid_longitude"])
    x, y = mercator(latitude, longitude)
    half = CROP_SIZE_METRES / 2
    return CropGeoreference(
        str(props["pie_property_id"]), int(props["extension"]), crop_path, x, y,
        x - half, y - half, x + half, y + half,
    )


def validate_georeference(georef: CropGeoreference) -> None:
    """Reject anything other than the frozen W1 crop transform."""
    values = (
        georef.centroid_x_3857, georef.centroid_y_3857, georef.xmin_3857,
        georef.ymin_3857, georef.xmax_3857, georef.ymax_3857,
    )
    if not all(math.isfinite(value) for value in values):
        raise W1InputError(f"Non-finite W1 crop georeference for {georef.property_id}.")
    if not (
        math.isclose(georef.xmax_3857 - georef.xmin_3857, CROP_SIZE_METRES)
        and math.isclose(georef.ymax_3857 - georef.ymin_3857, CROP_SIZE_METRES)
        and math.isclose(georef.centroid_x_3857, (georef.xmin_3857 + georef.xmax_3857) / 2)
        and math.isclose(georef.centroid_y_3857, (georef.ymin_3857 + georef.ymax_3857) / 2)
    ):
        raise W1InputError(f"Invalid frozen W1 crop bounds for {georef.property_id}.")
    if georef.affine != (
        METRES_PER_PIXEL, 0.0, georef.xmin_3857, 0.0, -METRES_PER_PIXEL, georef.ymax_3857
    ):
        raise W1InputError(f"Invalid frozen W1 crop affine for {georef.property_id}.")


def load_authoritative_inputs(repo_root: Path, crop_root: Path) -> list[tuple[dict[str, Any], CropGeoreference]]:
    geojson = repo_root / "data/estates/waterfall_country_estate/waterfall_country_estate_w1.geojson"
    if sha256(geojson) != W1_GEOJSON_SHA256:
        raise W1InputError("W1 GeoJSON hash differs from frozen e86b156 artifact.")
    collection = json.loads(geojson.read_text(encoding="utf-8"))
    features = collection.get("features", [])
    if len(features) != 1010:
        raise W1InputError(f"Expected 1010 frozen W1 features, found {len(features)}.")
    rows = []
    for feature in features:
        props = feature.get("properties") or {}
        property_id, extension = props.get("pie_property_id"), props.get("extension")
        if property_id is None or extension is None or not feature.get("geometry"):
            raise W1InputError("Frozen W1 feature lacks property ID, extension, or geometry.")
        # Original W1 builder's exact output template; this is a verified
        # producer contract, not an assumption that a filename itself is an ID.
        name = f"{extension}_{property_id}_ags_aerial.jpg"
        crop = crop_root / name
        if not crop.is_file():
            raise W1InputError(f"Missing original W1 crop for property {property_id}: {crop}")
        georef = georeference_for(feature, str(crop))
        validate_georeference(georef)
        image = cv2.imread(str(crop), cv2.IMREAD_COLOR)
        if image is None or image.shape[:2] != (CROP_SIZE_PX, CROP_SIZE_PX):
            raise W1InputError(f"Invalid original W1 crop dimensions for property {property_id}: {crop}")
        rows.append((feature, georef))
    ids = [row[1].property_id for row in rows]
    names = [row[1].crop_path for row in rows]
    if len(set(ids)) != len(ids) or len(set(names)) != len(names) or len(rows) != 1010:
        raise W1InputError("W1 property-to-crop mapping is not a 1010/1010 bijection.")
    return rows
