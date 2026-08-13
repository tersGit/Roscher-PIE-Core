"""Property24 listing HTML parse for images, video, and metadata."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


@dataclass
class ListingData:
    listing_id: str
    listing_url: str
    title: str | None = None
    estate: str | None = None
    property_type: str | None = None
    stand_size_sqm: float | None = None
    stand_size_raw: str | None = None
    bedrooms: int | None = None
    bathrooms: float | None = None
    image_urls: list[str] = field(default_factory=list)
    video_urls: list[str] = field(default_factory=list)
    description: str | None = None


def _stand_size(text: str) -> tuple[float | None, str | None]:
    match = re.search(
        r"p24_info\">\s*([\d\s]+)\s*m(?:²|&sup2;|&#xB2;|2)",
        text,
        re.I,
    )
    if not match:
        match = re.search(
            r"([\d\s]+)\s*m(?:²|&sup2;|&#xB2;)\b",
            text,
            re.I,
        )
    if not match:
        return None, None
    raw = match.group(0)
    value = float(re.sub(r"\s+", "", match.group(1)))
    return value, raw


def _unique_image_urls(html: str) -> list[str]:
    ids: dict[str, str] = {}
    for match in re.finditer(r"https://images\.prop24\.com/(\d+)(/[^\"'\s>]*)?", html):
        image_id = match.group(1)
        suffix = match.group(2) or ""
        full = f"https://images.prop24.com/{image_id}"
        if image_id not in ids:
            ids[image_id] = full
        if not suffix:
            ids[image_id] = full
    return list(ids.values())


def parse_listing_html(html: str, url: str, listing_id: str) -> ListingData:
    unique = _unique_image_urls(html)

    videos = []
    for match in re.finditer(r"youtube(?:-nocookie)?\.com/embed/([A-Za-z0-9_-]{6,})", html, re.I):
        videos.append(f"https://www.youtube.com/embed/{match.group(1)}")
    videos = list(dict.fromkeys(videos))

    title = None
    m = re.search(r"<title>([^<]+)</title>", html, re.I)
    if m:
        title = re.sub(r"\s+", " ", m.group(1)).strip()

    property_type = "House" if title and "House" in title else None
    estate = None
    if "Carlswald North" in html:
        estate = "Carlswald North Estate"
    stand_size, stand_raw = _stand_size(html)
    description = None
    m = re.search(r'property="og:description"\s+content="([^"]+)"', html)
    if m:
        description = m.group(1)

    return ListingData(
        listing_id=listing_id,
        listing_url=url,
        title=title,
        estate=estate,
        property_type=property_type,
        stand_size_sqm=stand_size,
        stand_size_raw=stand_raw,
        image_urls=unique,
        video_urls=videos,
        description=description,
    )


def fetch_listing(url: str, listing_id: str) -> ListingData:
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            with httpx.Client(timeout=40.0, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
                response = client.get(url)
                if response.status_code >= 500:
                    last_error = httpx.HTTPStatusError(
                        f"HTTP {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                    time.sleep(1.5 * (attempt + 1))
                    continue
                response.raise_for_status()
                return parse_listing_html(response.text, url, listing_id)
        except httpx.HTTPError as exc:
            last_error = exc
    if last_error:
        raise last_error
    raise RuntimeError("listing fetch failed")


def download_images(urls: list[str], dest: Path, listing_id: str) -> dict[str, bytes]:
    dest.mkdir(parents=True, exist_ok=True)
    bodies: dict[str, bytes] = {}
    headers = {"User-Agent": USER_AGENT}
    with httpx.Client(timeout=40.0, follow_redirects=True, headers=headers) as client:
        for index, url in enumerate(urls, start=1):
            media_id = f"{listing_id}-{index:03d}"
            path = dest / f"{media_id}.jpg"
            if path.is_file() and path.stat().st_size > 2000:
                bodies[media_id] = path.read_bytes()
                continue
            try:
                response = client.get(url)
                if response.status_code == 200 and response.content:
                    path.write_bytes(response.content)
                    bodies[media_id] = response.content
            except httpx.HTTPError:
                continue
    return bodies
