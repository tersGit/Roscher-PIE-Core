"""Raw AGS native15 proof is isolated and uses Council imagery metadata."""

from __future__ import annotations

import json
from pathlib import Path

from backend.gis.estate_ags_matching.ags_native15_raw_proof import (
    AGS_IMAGESERVER_URL,
    PREFERRED_STAND,
    contour_pixel_stats,
    covering_tile,
    load_dataset,
    load_os,
    native15_tile_grid,
    object_pixel_dimensions,
    parcel_bbox,
)
from backend.gis.estate_ags_matching.estate_property_inventory_v1 import classify_pool_from_os
from backend.imagery.estate_tiles import NATIVE_PIXEL_SIZE_M


def test_preferred_stand_is_confirmed_yes():
    payload = load_os(PREFERRED_STAND)
    assert payload["pool"]["status"] == "CONFIRMED"
    assert float(payload["pool"]["clip"]["pool"]) > 0.9
    assert classify_pool_from_os(payload).pool_status == "YES"
    assert payload["building"]["status"] == "CONFIRMED"
    assert payload["driveway"]["geometry"]["present"] is True


def test_object_pixels_are_measurable_on_os_crop():
    payload = load_os(PREFERRED_STAND)
    width, height = payload["crop_wh"]
    dims = object_pixel_dimensions(payload, (width, height))
    assert dims["pool"]["approx_width_px"] > 20
    assert dims["pool"]["approx_length_px"] > 20
    assert dims["building"]["approx_length_px"] > 80
    assert dims["driveway"]["approx_width_px"] > 5
    pool = contour_pixel_stats(payload["pool"]["contour"], width, height)
    assert abs(pool["area_px"] - float(payload["pool"]["geometry"]["area_px"])) / payload["pool"]["geometry"]["area_px"] < 0.15


def test_covering_tile_is_native15_named_from_estate_extent():
    dataset = load_dataset()
    parcel = next(item for item in dataset["parcels"] if item["stand_number"] == PREFERRED_STAND)
    tiles = native15_tile_grid(dataset["extent"])
    assert len(tiles) >= 20
    min_lon, min_lat, max_lon, max_lat = parcel_bbox(parcel["geometry"])
    tile = covering_tile(tiles, min_lon, min_lat, max_lon, max_lat)
    assert tile["stem"].startswith("tile_2023_native15_")
    assert tile["width"] == 1400
    assert abs(tile["metres_per_pixel"] - NATIVE_PIXEL_SIZE_M) < 1e-9
    assert tile["min_lon"] <= (min_lon + max_lon) / 2 <= tile["max_lon"]


def test_written_proof_is_ags_native15_605x402():
    crop = Path(
        "data/investigations/estate_property_inventory_v1/unknown_diagnostic/"
        "ags_raw_proof/677_ags_native15_raw_crop.jpg"
    )
    panel = Path(
        "data/investigations/estate_property_inventory_v1/unknown_diagnostic/"
        "ags_raw_proof/677_ags_native15_raw_proof.jpg"
    )
    meta = Path(
        "data/investigations/estate_property_inventory_v1/unknown_diagnostic/"
        "ags_raw_proof/677_ags_native15_raw_proof.json"
    )
    if not crop.is_file():
        return
    from PIL import Image

    with Image.open(crop) as image:
        assert image.size == (605, 402)
    payload = json.loads(meta.read_text(encoding="utf-8"))
    assert payload["source_tile_id"] == "tile_2023_native15_04_03"
    assert payload["google_bing_or_other_satellite_used"] is False
    assert payload["crop_matches_os_v1_wh"] is True
    assert "ags.joburg.org.za" in payload["imagery_source"]
    assert panel.is_file() and panel.stat().st_size > 10_000


def test_proof_module_does_not_touch_frozen_pipelines():
    text = Path("backend/gis/estate_ags_matching/ags_native15_raw_proof.py").read_text(encoding="utf-8")
    assert "ags.joburg.org.za" in text
    assert "maps.google" not in text.lower()
    assert "googleapis" not in text.lower()
    assert "virtualearth" not in text.lower()
    assert "bing.com" not in text.lower()
    assert "def classify_pool_from_os" not in text
    assert "V2_WEIGHTS" not in text
    assert AGS_IMAGESERVER_URL.endswith("AerialPhotography/2023/ImageServer")
    frozen = Path("backend/vision/object_segmentation.py").read_text(encoding="utf-8")
    assert 'SEGMENTATION_VERSION = "object_segmentation_v1"' in frozen
    tiles = Path("backend/imagery/estate_tiles.py").read_text(encoding="utf-8")
    assert "native15" in tiles

