"""City of Johannesburg AGS aerial imagery connector."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx

WEB_MERCATOR_RADIUS = 6378137.0


class AGSError(RuntimeError):
    """Raised when the CoJ AGS imagery service cannot satisfy a request."""


@dataclass(frozen=True)
class AGSImageRequest:
    latitude: float
    longitude: float
    radius_m: float = 100.0
    width: int = 1600
    height: int = 1600
    year: int = 2023
    image_format: str = "jpg"


class AGSAerialClient:
    BASE_URL = (
        "https://ags.joburg.org.za/server/rest/services/"
        "AerialPhotography/{year}/ImageServer"
    )

    def __init__(
        self,
        *,
        timeout_s: float = 40.0,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        self.timeout_s = timeout_s
        self._transport = transport

    @staticmethod
    def wgs84_to_web_mercator(latitude: float, longitude: float) -> tuple[float, float]:
        latitude = max(min(latitude, 85.05112878), -85.05112878)
        x = WEB_MERCATOR_RADIUS * math.radians(longitude)
        y = WEB_MERCATOR_RADIUS * math.log(math.tan(math.pi / 4.0 + math.radians(latitude) / 2.0))
        return x, y

    @staticmethod
    def web_mercator_to_wgs84(x: float, y: float) -> tuple[float, float]:
        longitude = math.degrees(x / WEB_MERCATOR_RADIUS)
        latitude = math.degrees(2.0 * math.atan(math.exp(y / WEB_MERCATOR_RADIUS)) - math.pi / 2.0)
        return latitude, longitude

    @classmethod
    def bbox_from_wgs84(
        cls, min_lon: float, min_lat: float, max_lon: float, max_lat: float
    ) -> tuple[float, float, float, float]:
        xmin, ymin = cls.wgs84_to_web_mercator(min_lat, min_lon)
        xmax, ymax = cls.wgs84_to_web_mercator(max_lat, max_lon)
        return xmin, ymin, xmax, ymax

    def export_bbox(
        self,
        *,
        min_lon: float,
        min_lat: float,
        max_lon: float,
        max_lat: float,
        width: int,
        height: int,
        year: int = 2023,
        image_format: str = "jpg",
    ) -> bytes:
        if width <= 0 or height <= 0:
            raise ValueError("width and height must be > 0")
        if height > 4100 or width > 15000:
            raise ValueError("requested image exceeds AGS advertised maxima")
        xmin, ymin, xmax, ymax = self.bbox_from_wgs84(min_lon, min_lat, max_lon, max_lat)
        url = f"{self.BASE_URL.format(year=year)}/exportImage"
        params = {
            "bbox": f"{xmin:.3f},{ymin:.3f},{xmax:.3f},{ymax:.3f}",
            "bboxSR": "3857",
            "imageSR": "3857",
            "size": f"{width},{height}",
            "format": image_format,
            "interpolation": "RSP_BilinearInterpolation",
            "returnSquarePixels": "false",
            "f": "image",
        }
        try:
            with httpx.Client(
                timeout=self.timeout_s,
                follow_redirects=True,
                transport=self._transport,
            ) as client:
                response = client.get(url, params=params)
        except httpx.HTTPError as exc:
            raise AGSError(f"AGS request failed: {exc}") from exc
        if response.status_code != 200:
            raise AGSError(f"AGS returned HTTP {response.status_code}: {response.text[:300]}")
        content_type = response.headers.get("content-type", "").lower()
        if not content_type.startswith("image/") or not response.content:
            raise AGSError(
                f"AGS did not return an image. content-type={content_type!r}; body={response.text[:300]!r}"
            )
        return response.content

    def export_bbox_to_file(self, destination: str | Path, **kwargs) -> Path:
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(self.export_bbox(**kwargs))
        return destination
