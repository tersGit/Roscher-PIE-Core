"""Estate AGS tile cache and parcel crops. One tile covers many parcels.

Acquisition standard
--------------------
CoJ AerialPhotography/2023 is native ~0.15 m/px. PIE caches estate tiles once,
then cuts local parcel crops. It does **not** issue one AGS request per parcel.

Profile choice (native15)
    210 m geographic tile × 1400 px = 0.15 m/px exactly.
    Preferred over 280 m @ 1867 px because:
    - required_pixels = 210 / 0.15 = 1400 (no oversize request, no extra resample)
    - same per-tile pixel budget / memory as the previous 1400 px JPEGs
    - square tiles stitch on a regular grid
    280 m @ 1867 px would keep the old geographic grid but request more pixels
    than needed per 0.15 m sample and inflate decode memory.

The previous 280 m / 1400 px cache (~0.20 m/px) is profile ``legacy_020``.
Those files are never overwritten and cannot be reused as native15.
"""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, field
from pathlib import Path

from backend.imagery.ags_client import AGSAerialClient

WEB_MERCATOR_RADIUS = 6378137.0
NATIVE_PIXEL_SIZE_M = 0.15
PADDING_METRES = 18.0
AGS_SERVICE_ID = "AerialPhotography/2023"
AGS_MAX_HEIGHT = 4100
AGS_MAX_WIDTH = 15000

# Kept as names so older call sites that imported them still resolve.
# New code should use CACHE_PROFILES["native15"] / cache_root_for().
DEFAULT_TILE_METRES = 210.0
DEFAULT_PIXELS = 1400


class CacheProfileMismatch(RuntimeError):
    """Raised when a cache directory belongs to a different resolution profile."""


@dataclass(frozen=True)
class CacheProfile:
    profile_id: str
    tile_metres: float
    metres_per_pixel: float
    cache_leaf: str
    crop_leaf: str
    description: str

    @property
    def pixels(self) -> int:
        return pixels_for_extent(self.tile_metres, self.tile_metres, self.metres_per_pixel)[0]


CACHE_PROFILES: dict[str, CacheProfile] = {
    "native15": CacheProfile(
        profile_id="native15",
        tile_metres=210.0,
        metres_per_pixel=NATIVE_PIXEL_SIZE_M,
        cache_leaf="ags_native15",
        crop_leaf="_imagery_cache_native15",
        description="Native CoJ 15 cm: 210 m tiles at 1400 px (0.15 m/px).",
    ),
    "legacy_020": CacheProfile(
        profile_id="legacy_020",
        tile_metres=280.0,
        metres_per_pixel=280.0 / 1400.0,
        cache_leaf="ags",
        crop_leaf="_imagery_cache",
        description="Legacy cache: 280 m tiles at 1400 px (~0.20 m/px). Do not use for native15.",
    ),
}

DEFAULT_PROFILE_ID = "native15"


def pixels_for_extent(
    width_m: float,
    height_m: float,
    metres_per_pixel: float = NATIVE_PIXEL_SIZE_M,
) -> tuple[int, int]:
    """Pixels required to sample an extent at metres_per_pixel, never above native 0.15.

    required_pixels = bbox_ground_width / 0.15, rounded to nearest integer and
    clamped to AGS advertised maxima. Refuses to request substantially more
    pixels than native (would only interpolate).
    """
    if metres_per_pixel < NATIVE_PIXEL_SIZE_M - 1e-9:
        metres_per_pixel = NATIVE_PIXEL_SIZE_M
    width = max(1, int(round(float(width_m) / metres_per_pixel)))
    height = max(1, int(round(float(height_m) / metres_per_pixel)))
    width = min(width, AGS_MAX_WIDTH)
    height = min(height, AGS_MAX_HEIGHT)
    return width, height


def cache_root_for(dataset_id: str, profile_id: str = DEFAULT_PROFILE_ID, *, repo_root: Path | None = None) -> Path:
    profile = CACHE_PROFILES[profile_id]
    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[2]
    return root / "data" / "cache" / profile.cache_leaf / dataset_id


def crop_dir_for(dataset_id: str, profile_id: str = DEFAULT_PROFILE_ID, *, repo_root: Path | None = None) -> Path:
    profile = CACHE_PROFILES[profile_id]
    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[2]
    return root / "data" / "visual_index" / dataset_id / profile.crop_leaf


def _mercator(lat: float, lon: float) -> tuple[float, float]:
    x = WEB_MERCATOR_RADIUS * math.radians(lon)
    y = WEB_MERCATOR_RADIUS * math.log(math.tan(math.pi / 4.0 + math.radians(lat) / 2.0))
    return x, y


def _inv_mercator(x: float, y: float) -> tuple[float, float]:
    lon = math.degrees(x / WEB_MERCATOR_RADIUS)
    lat = math.degrees(2.0 * math.atan(math.exp(y / WEB_MERCATOR_RADIUS)) - math.pi / 2.0)
    return lat, lon


@dataclass
class TileStats:
    tiles_required: int = 0
    tiles_downloaded: int = 0
    tiles_reused: int = 0
    tiles_failed: int = 0
    tile_fetch_time_ms: float = 0.0
    cache_size_bytes: int = 0
    metres_per_pixel: float = 0.0
    profile_id: str = ""
    tile_metres: float = 0.0
    pixels: int = 0
    failed_tiles: list[str] = field(default_factory=list)


class EstateTileIndex:
    def __init__(
        self,
        cache_root: Path,
        extent: dict[str, float],
        year: int = 2023,
        *,
        profile_id: str = DEFAULT_PROFILE_ID,
    ) -> None:
        self.profile = CACHE_PROFILES[profile_id]
        self.cache_root = Path(cache_root)
        self.cache_root.mkdir(parents=True, exist_ok=True)
        self.extent = extent
        self.year = year
        self.client = AGSAerialClient(timeout_s=60.0)
        self.stats = TileStats()
        self.tiles: list[dict] = []
        self._assert_cache_compatible()

    def _manifest_path(self) -> Path:
        return self.cache_root / "manifest.json"

    def _tile_stem(self, row: int, col: int) -> str:
        return f"tile_{self.year}_{self.profile.profile_id}_{row:02d}_{col:02d}"

    def _assert_cache_compatible(self) -> None:
        manifest_path = self._manifest_path()
        if manifest_path.is_file():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            found = manifest.get("profile")
            if found and found != self.profile.profile_id:
                raise CacheProfileMismatch(
                    f"Cache {self.cache_root} is profile {found!r}, requested {self.profile.profile_id!r}. "
                    "PIE will not reuse 0.20 m/px tiles as native 0.15 m/px."
                )
            return
        # Unversioned legacy files (tile_YYYY_RR_CC.jpg) live only in the old ags/ leaf.
        legacy = list(self.cache_root.glob("tile_????_??_??.jpg"))
        native_named = list(self.cache_root.glob("tile_*_native15_*.jpg"))
        if legacy and self.profile.profile_id != "legacy_020":
            raise CacheProfileMismatch(
                f"Unversioned legacy tiles in {self.cache_root} cannot be used as {self.profile.profile_id}."
            )
        if native_named and self.profile.profile_id != "native15":
            raise CacheProfileMismatch(
                f"native15 tiles in {self.cache_root} cannot be used as {self.profile.profile_id}."
            )

    def _write_manifest(self, rows: int, cols: int) -> None:
        payload = {
            "profile": self.profile.profile_id,
            "tile_metres": self.profile.tile_metres,
            "pixels": self.profile.pixels,
            "metres_per_pixel": self.profile.metres_per_pixel,
            "year": self.year,
            "ags_service": f"AerialPhotography/{self.year}",
            "native_pixel_size_m": NATIVE_PIXEL_SIZE_M,
            "interpolation": "RSP_BilinearInterpolation",
            "padding_metres": PADDING_METRES,
            "rows": rows,
            "cols": cols,
            "description": self.profile.description,
        }
        self._manifest_path().write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _write_tile_sidecar(self, path: Path, record: dict, width: int, height: int) -> None:
        side_x = record["xmax"] - record["xmin"]
        side_y = record["ymax"] - record["ymin"]
        sidecar = {
            "bbox": {
                "min_lon": record["min_lon"],
                "min_lat": record["min_lat"],
                "max_lon": record["max_lon"],
                "max_lat": record["max_lat"],
            },
            "bbox_3857": {
                "xmin": record["xmin"],
                "ymin": record["ymin"],
                "xmax": record["xmax"],
                "ymax": record["ymax"],
            },
            "width": width,
            "height": height,
            "effective_metres_per_pixel": {
                "x": side_x / max(width, 1),
                "y": side_y / max(height, 1),
            },
            "ags_service": f"AerialPhotography/{self.year}",
            "year": self.year,
            "profile": self.profile.profile_id,
        }
        path.with_suffix(".json").write_text(json.dumps(sidecar, indent=2), encoding="utf-8")

    def _tile_is_reusable(self, jpg_path: Path, expected_w: int, expected_h: int) -> bool:
        if not jpg_path.is_file() or jpg_path.stat().st_size <= 1000:
            return False
        sidecar = jpg_path.with_suffix(".json")
        if not sidecar.is_file():
            return False
        meta = json.loads(sidecar.read_text(encoding="utf-8"))
        if meta.get("profile") != self.profile.profile_id:
            return False
        if int(meta.get("width") or 0) != expected_w or int(meta.get("height") or 0) != expected_h:
            return False
        mpp = meta.get("effective_metres_per_pixel") or {}
        target = self.profile.metres_per_pixel
        for key in ("x", "y"):
            value = float(mpp.get(key) or 0)
            if abs(value - target) / target > 0.04:
                return False
        if meta.get("ags_service") != f"AerialPhotography/{self.year}":
            return False
        return True

    def build(self, tile_metres: float | None = None, pixels: int | None = None) -> TileStats:
        """Build the estate grid. ``tile_metres`` / ``pixels`` default from the profile.

        Explicit overrides are still clamped so we never request finer than 0.15 m/px.
        """
        started = time.perf_counter()
        profile = self.profile
        tile_metres = float(tile_metres if tile_metres is not None else profile.tile_metres)
        native_pixels = pixels_for_extent(tile_metres, tile_metres, NATIVE_PIXEL_SIZE_M)[0]
        if pixels is None:
            pixels = native_pixels
        else:
            pixels = min(int(pixels), native_pixels)
        width_px, height_px = pixels, pixels

        xmin, ymin = _mercator(self.extent["min_latitude"], self.extent["min_longitude"])
        xmax, ymax = _mercator(self.extent["max_latitude"], self.extent["max_longitude"])
        pad = tile_metres * 0.15
        xmin -= pad
        ymin -= pad
        xmax += pad
        ymax += pad
        cols = max(1, int(math.ceil((xmax - xmin) / tile_metres)))
        rows = max(1, int(math.ceil((ymax - ymin) / tile_metres)))
        self.stats = TileStats(
            tiles_required=cols * rows,
            metres_per_pixel=tile_metres / width_px,
            profile_id=profile.profile_id,
            tile_metres=tile_metres,
            pixels=width_px,
        )
        self.tiles = []
        for row in range(rows):
            for col in range(cols):
                x0 = xmin + col * tile_metres
                y0 = ymin + row * tile_metres
                x1 = x0 + tile_metres
                y1 = y0 + tile_metres
                min_lat, min_lon = _inv_mercator(x0, y0)
                max_lat, max_lon = _inv_mercator(x1, y1)
                stem = self._tile_stem(row, col)
                path = self.cache_root / f"{stem}.jpg"
                record = {
                    "row": row,
                    "col": col,
                    "path": path,
                    "min_lon": min_lon,
                    "min_lat": min_lat,
                    "max_lon": max_lon,
                    "max_lat": max_lat,
                    "xmin": x0,
                    "ymin": y0,
                    "xmax": x1,
                    "ymax": y1,
                    "width": width_px,
                    "height": height_px,
                    "metres_per_pixel": tile_metres / width_px,
                    "profile": profile.profile_id,
                    "ags_service": f"AerialPhotography/{self.year}",
                }
                if self._tile_is_reusable(path, width_px, height_px):
                    self.stats.tiles_reused += 1
                else:
                    try:
                        self.client.export_bbox_to_file(
                            path,
                            min_lon=min_lon,
                            min_lat=min_lat,
                            max_lon=max_lon,
                            max_lat=max_lat,
                            width=width_px,
                            height=height_px,
                            year=self.year,
                        )
                        self._write_tile_sidecar(path, record, width_px, height_px)
                        self.stats.tiles_downloaded += 1
                    except Exception as exc:  # noqa: BLE001
                        self.stats.tiles_failed += 1
                        self.stats.failed_tiles.append(f"{stem}: {exc}")
                        continue
                if path.is_file():
                    self.stats.cache_size_bytes += path.stat().st_size
                    sidecar = path.with_suffix(".json")
                    if sidecar.is_file():
                        self.stats.cache_size_bytes += sidecar.stat().st_size
                self.tiles.append(record)
        self._write_manifest(rows, cols)
        self.stats.tile_fetch_time_ms = (time.perf_counter() - started) * 1000
        return self.stats

    def covering_tile(self, min_lon: float, min_lat: float, max_lon: float, max_lat: float) -> dict | None:
        cx = (min_lon + max_lon) / 2
        cy = (min_lat + max_lat) / 2
        for tile in self.tiles:
            if tile["min_lon"] <= cx <= tile["max_lon"] and tile["min_lat"] <= cy <= tile["max_lat"]:
                return tile
        return self.tiles[0] if self.tiles else None
