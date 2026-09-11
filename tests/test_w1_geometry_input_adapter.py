import numpy as np

from backend.gis.estate_ags_matching.w1_geometry_input_adapter import (
    CropGeoreference, CROP_SIZE_PX, METRES_PER_PIXEL, pixel_to_world,
    rasterize_parcel, stored_centre_inside_polygon, validate_georeference, world_to_pixel,
)


def georef():
    return CropGeoreference("p", 19, "crop.jpg", 0, 0, -67.5, -67.5, 67.5, 67.5)


def test_world_pixel_transform_round_trip():
    point = pixel_to_world(georef(), 450, 450)
    assert point == (0.0, 0.0)
    assert world_to_pixel(georef(), *point) == (450.0, 450.0)
    assert CROP_SIZE_PX * METRES_PER_PIXEL == 135


def test_rasterization_clips_and_handles_holes():
    def ll(x, y):
        # At equator this simple conversion maps test metres to mercator metres.
        return [x / 111319.49079327357, y / 111319.49079327357]
    outer = [ll(-80, -80), ll(80, -80), ll(80, 80), ll(-80, 80), ll(-80, -80)]
    hole = [ll(-10, -10), ll(10, -10), ll(10, 10), ll(-10, 10), ll(-10, -10)]
    mask = rasterize_parcel({"rings": [outer, hole]}, georef())
    assert mask.shape == (900, 900)
    assert mask.any()
    assert not mask[450, 450]
    assert mask[50, 50]


def test_centroid_and_area_rasterization():
    def ll(x, y):
        return [x / 111319.49079327357, y / 111319.49079327357]
    ring = [ll(-15, -15), ll(15, -15), ll(15, 15), ll(-15, 15), ll(-15, -15)]
    mask = rasterize_parcel({"rings": [ring]}, georef())
    assert mask[450, 450]
    assert abs(mask.sum() * METRES_PER_PIXEL ** 2 - 900) < 20


def test_rasterization_marks_empty_polygon_outside_crop():
    ring = [[30, -26], [30.001, -26], [30.001, -25.999], [30, -25.999], [30, -26]]
    assert not rasterize_parcel({"rings": [ring]}, georef()).any()


def test_nonempty_mapped_polygon_is_valid_when_stored_centre_is_outside():
    def ll(x, y):
        return [x / 111319.49079327357, y / 111319.49079327357]
    ring = [ll(-60, -10), ll(-20, -10), ll(-20, 10), ll(-60, 10), ll(-60, -10)]
    mask = rasterize_parcel({"rings": [ring]}, georef())
    assert mask.any()
    assert not mask[450, 450]


def test_frozen_crop_georeference_is_required():
    validate_georeference(georef())


def test_stored_centre_uses_unrounded_polygon_containment():
    ring = [[-60, -10], [-20, -10], [-20, 10], [-60, 10], [-60, -10]]
    assert stored_centre_inside_polygon({"rings": [ring]}, -40, 0)
    assert not stored_centre_inside_polygon({"rings": [ring]}, 0, 0)
