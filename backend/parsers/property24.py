"""Property24 listing HTML parse for images, video, and metadata."""

from __future__ import annotations

import re
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
    match = re.search(r"([\d\s]+)\s*m[²2]", text, re.I)
    if not match:
        return None, None
    raw = match.group(0)
    value = float(re.sub(r"\s+", "", match.group(1)))
    return value, raw


def parse_listing_html(html: str, url: str, listing_id: str) -> ListingData:
    images: list[str] = []
    for match in re.finditer(r"https://images\.prop24\.com/[^\"'\s>]+", html):
        images.append(match.group(0).split("?")[0])
    # de-dupe preserving order
    seen = set()
    unique = []
    for item in images:
        if item not in seen and not item.endswith(".svg"):
            seen.add(item)
            unique.append(item)

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
    with httpx.Client(timeout=40.0, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
        response = client.get(url)
        response.raise_for_status()
        return parse_listing_html(response.text, url, listing_id)


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
