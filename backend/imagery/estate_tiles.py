"""Estate AGS tile cache and parcel crops. One tile covers many parcels."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from pathlib import Path

from backend.imagery.ags_client import AGSAerialClient

WEB_MERCATOR_RADIUS = 6378137.0
DEFAULT_TILE_METRES = 280.0
DEFAULT_PIXELS = 1400
PADDING_METRES = 18.0


@dataclass
class TileStats:
    tiles_required: int = 0
    tiles_downloaded: int = 0
    tiles_reused: int = 0
    tiles_failed: int = 0
    tile_fetch_time_ms: float = 0.0


def _mercator(lat: float, lon: float) -> tuple[float, float]:
    x = WEB_MERCATOR_RADIUS * math.radians(lon)
    y = WEB_MERCATOR_RADIUS * math.log(math.tan(math.pi / 4.0 + math.radians(lat) / 2.0))
    return x, y


def _inv_mercator(x: float, y: float) -> tuple[float, float]:
    lon = math.degrees(x / WEB_MERCATOR_RADIUS)
    lat = math.degrees(2.0 * math.atan(math.exp(y / WEB_MERCATOR_RADIUS)) - math.pi / 2.0)
    return lat, lon


class EstateTileIndex:
    def __init__(self, cache_root: Path, extent: dict[str, float], year: int = 2023) -> None:
        self.cache_root = Path(cache_root)
        self.cache_root.mkdir(parents=True, exist_ok=True)
        self.extent = extent
        self.year = year
        self.client = AGSAerialClient(timeout_s=60.0)
        self.stats = TileStats()
        self.tiles: list[dict] = []

    def build(self, tile_metres: float = DEFAULT_TILE_METRES, pixels: int = DEFAULT_PIXELS) -> TileStats:
        started = time.perf_counter()
        xmin, ymin = _mercator(self.extent["min_latitude"], self.extent["min_longitude"])
        xmax, ymax = _mercator(self.extent["max_latitude"], self.extent["max_longitude"])
        pad = tile_metres * 0.15
        xmin -= pad
        ymin -= pad
        xmax += pad
        ymax += pad
        cols = max(1, int(math.ceil((xmax - xmin) / tile_metres)))
        rows = max(1, int(math.ceil((ymax - ymin) / tile_metres)))
        self.stats.tiles_required = cols * rows
        for row in range(rows):
            for col in range(cols):
                x0 = xmin + col * tile_metres
                y0 = ymin + row * tile_metres
                x1 = min(xmax, x0 + tile_metres)
                y1 = min(ymax, y0 + tile_metres)
                min_lat, min_lon = _inv_mercator(x0, y0)
                max_lat, max_lon = _inv_mercator(x1, y1)
                path = self.cache_root / f"tile_{self.year}_{row:02d}_{col:02d}.jpg"
                record = {
                    "row": row,
                    "col": col,
                    "path": path,
                    "min_lon": min_lon,
                    "min_lat": min_lat,
                    "max_lon": max_lon,
                    "max_lat": max_lat,
                }
                if path.is_file() and path.stat().st_size > 1000:
                    self.stats.tiles_reused += 1
                else:
                    try:
                        self.client.export_bbox_to_file(
                            path,
                            min_lon=min_lon,
                            min_lat=min_lat,
                            max_lon=max_lon,
                            max_lat=max_lat,
                            width=pixels,
                            height=pixels,
                            year=self.year,
                        )
                        self.stats.tiles_downloaded += 1
                    except Exception:
                        self.stats.tiles_failed += 1
                        continue
                self.tiles.append(record)
        self.stats.tile_fetch_time_ms = (time.perf_counter() - started) * 1000
        return self.stats

    def covering_tile(self, min_lon: float, min_lat: float, max_lon: float, max_lat: float) -> dict | None:
        cx = (min_lon + max_lon) / 2
        cy = (min_lat + max_lat) / 2
        for tile in self.tiles:
            if tile["min_lon"] <= cx <= tile["max_lon"] and tile["min_lat"] <= cy <= tile["max_lat"]:
                return tile
        return self.tiles[0] if self.tiles else None
