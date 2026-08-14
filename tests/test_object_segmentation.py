"""Unit tests for object_segmentation_v1 — no FastSAM / no network."""

from __future__ import annotations

import numpy as np

from backend.vision.object_segmentation import (
    ObjectMask,
    ParcelObjects,
    contour_geometry,
    objects_to_json,
    parcel_mask_from_geometry,
    spatial_fingerprint,
    water_fraction,
)


def test_contour_geometry_square():
    mask = np.zeros((100, 100), dtype=np.uint8)
    mask[20:80, 20:80] = 255
    g = contour_geometry(mask)
    assert g["area_px"] > 3400
    assert g["area_m2"] > 70
    assert g["rectangularity"] >= 0.98
    assert g["convexity"] >= 0.98
    assert abs(g["aspect_ratio"] - 1.0) < 0.05
    assert g["centroid_xy_px"] is not None
    assert len(g["curvature_signature"]) == 16


def test_parcel_mask_covers_centre():
    geom = {
        "rings": [[
            [28.0, -25.98],
            [28.001, -25.98],
            [28.001, -25.981],
            [28.0, -25.981],
            [28.0, -25.98],
        ]]
    }
    mask = parcel_mask_from_geometry((200, 200), geom)
    assert mask[100, 100] > 0
    assert mask[0, 0] == 0
    assert mask.dtype == np.uint8


def test_water_fraction_cyan_blob():
    img = np.zeros((50, 50, 3), dtype=np.uint8)
    img[:, :] = (40, 80, 40)
    img[10:30, 10:30] = (180, 160, 40)
    mask = np.zeros((50, 50), dtype=np.uint8)
    mask[10:30, 10:30] = 255
    assert water_fraction(img, mask) > 0.5


def test_spatial_fingerprint_parcel_relative():
    parcel = np.zeros((100, 100), np.uint8)
    parcel[10:90, 10:90] = 255
    pool_mask = np.zeros((100, 100), dtype=bool)
    pool_mask[20:40, 60:80] = True
    bld_mask = np.zeros((100, 100), dtype=bool)
    bld_mask[40:70, 30:70] = True
    drv_mask = np.zeros((100, 100), dtype=bool)
    drv_mask[70:90, 40:60] = True
    pool = ObjectMask(kind="pool", mask=pool_mask, status="CONFIRMED", geometry=contour_geometry(pool_mask))
    bld = ObjectMask(kind="building", mask=bld_mask, status="CONFIRMED", geometry=contour_geometry(bld_mask))
    drv = ObjectMask(
        kind="driveway",
        mask=drv_mask,
        status="PROBABLE",
        geometry=contour_geometry(drv_mask) | {"entry": {"x": 0.5, "y": 0.9}},
    )
    objs = ParcelObjects(stand_number="1", pool=pool, building=bld, driveway=drv)
    spatial = spatial_fingerprint(objs, parcel)
    assert spatial["house"]["present"]
    assert spatial["pool"]["centroid_parcel"] is not None
    rel = spatial["relationships"]["pool_house"]
    assert rel["distance_m"] > 0
    assert rel["direction"] in {"N", "NE", "E", "SE", "S", "SW", "W", "NW"}
    assert spatial["driveway"]["driveway_side"] in {"north", "south", "east", "west"}


def test_rejected_pool_is_absent_from_spatial_graph():
    parcel = np.full((40, 40), 255, np.uint8)
    mask = np.zeros((40, 40), dtype=bool)
    mask[5:15, 5:15] = True
    pool = ObjectMask(kind="pool", mask=mask, status="REJECTED", geometry=contour_geometry(mask))
    bld = ObjectMask(kind="building", mask=mask, status="CONFIRMED", geometry=contour_geometry(mask))
    objs = ParcelObjects(stand_number="570", pool=pool, building=bld)
    spatial = spatial_fingerprint(objs, parcel)
    assert spatial["pool"]["present"] is False
    assert spatial["pool"]["status"] == "REJECTED"
    assert spatial["relationships"]["pool_house"] is None


def test_objects_to_json_omits_masks():
    objs = ParcelObjects(
        stand_number="x",
        pool=ObjectMask(kind="pool", mask=np.zeros((4, 4), bool), status="UNKNOWN"),
        building=ObjectMask(kind="building", mask=np.zeros((4, 4), bool), status="UNKNOWN"),
        driveway=ObjectMask(kind="driveway", mask=np.zeros((4, 4), bool), status="UNKNOWN"),
    )
    payload = objects_to_json(objs)
    assert "mask" not in payload["pool"]
    assert payload["version"]
    assert payload["pool"]["status"] == "UNKNOWN"
