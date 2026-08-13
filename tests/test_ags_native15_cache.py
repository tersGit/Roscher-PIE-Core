"""Native 0.15 m/px AGS cache profile: pixel cap and isolation from 0.20 tiles."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.imagery.estate_tiles import (
    CACHE_PROFILES,
    CacheProfileMismatch,
    EstateTileIndex,
    NATIVE_PIXEL_SIZE_M,
    cache_root_for,
    crop_dir_for,
    pixels_for_extent,
)


def test_native15_is_exactly_fifteen_cm():
    profile = CACHE_PROFILES["native15"]
    assert profile.tile_metres == 210.0
    assert profile.pixels == 1400
    assert abs(profile.tile_metres / profile.pixels - 0.15) < 1e-9
    assert profile.metres_per_pixel == NATIVE_PIXEL_SIZE_M


def test_legacy_profile_is_point_two_and_isolated():
    legacy = CACHE_PROFILES["legacy_020"]
    assert abs(legacy.tile_metres / 1400 - 0.20) < 1e-9
    assert legacy.cache_leaf == "ags"
    assert CACHE_PROFILES["native15"].cache_leaf == "ags_native15"
    assert cache_root_for("carlswald_north_corrected_001", "native15") != cache_root_for(
        "carlswald_north_corrected_001", "legacy_020"
    )
    assert crop_dir_for("ds", "native15") != crop_dir_for("ds", "legacy_020")


def test_required_pixels_formula():
    assert pixels_for_extent(210, 210, 0.15) == (1400, 1400)
    assert pixels_for_extent(90.8, 90.8, 0.15) == (605, 605)
    # must not request finer than native 0.15 (2400/3200-style oversize)
    w, h = pixels_for_extent(210, 210, 0.05)
    assert (w, h) == (1400, 1400)


def test_refuses_legacy_cache_as_native15(tmp_path: Path):
    (tmp_path / "tile_2023_00_00.jpg").write_bytes(b"x" * 2000)
    with pytest.raises(CacheProfileMismatch, match="legacy"):
        EstateTileIndex(tmp_path, _extent(), profile_id="native15")


def test_refuses_manifest_mismatch(tmp_path: Path):
    (tmp_path / "manifest.json").write_text(json.dumps({"profile": "legacy_020"}), encoding="utf-8")
    with pytest.raises(CacheProfileMismatch, match="will not reuse"):
        EstateTileIndex(tmp_path, _extent(), profile_id="native15")


def test_native15_does_not_reuse_wrong_sidecar(tmp_path: Path):
    index = EstateTileIndex(tmp_path, _extent(), profile_id="native15")
    jpg = tmp_path / "tile_2023_native15_00_00.jpg"
    jpg.write_bytes(b"x" * 2000)
    sidecar = {
        "profile": "legacy_020",
        "width": 1400,
        "height": 1400,
        "effective_metres_per_pixel": {"x": 0.20, "y": 0.20},
        "ags_service": "AerialPhotography/2023",
    }
    jpg.with_suffix(".json").write_text(json.dumps(sidecar), encoding="utf-8")
    assert index._tile_is_reusable(jpg, 1400, 1400) is False


def test_native15_reuses_matching_sidecar(tmp_path: Path):
    index = EstateTileIndex(tmp_path, _extent(), profile_id="native15")
    jpg = tmp_path / "tile_2023_native15_00_00.jpg"
    jpg.write_bytes(b"x" * 2000)
    sidecar = {
        "profile": "native15",
        "width": 1400,
        "height": 1400,
        "effective_metres_per_pixel": {"x": 0.15, "y": 0.15},
        "ags_service": "AerialPhotography/2023",
    }
    jpg.with_suffix(".json").write_text(json.dumps(sidecar), encoding="utf-8")
    assert index._tile_is_reusable(jpg, 1400, 1400) is True


def _extent() -> dict[str, float]:
    return {
        "min_longitude": 28.09,
        "max_longitude": 28.10,
        "min_latitude": -25.97,
        "max_latitude": -25.96,
    }
