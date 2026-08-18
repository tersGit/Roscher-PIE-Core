"""Proof panels and estate diagnostic artefacts for Corner Stand Detection v1.

Generic: no scoring-weight changes. Historical freeze files are not written.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from backend.gis.estate_ags_matching.corner_geometry_v1 import (
    LocalProjector,
    detect_intersections,
    extract_road_facing_edges,
    load_road_features,
    polygon_from_rings,
    project_roads,
    projector_for,
)
from backend.gis.estate_ags_matching.parcel_corner_v1 import ParcelCornerRecord

YES_FILL = (46, 180, 90, 110)
NO_FILL = (190, 55, 50, 95)
UNK_FILL = (140, 140, 140, 90)
YES_LINE = (40, 160, 80)
NO_LINE = (180, 50, 45)
UNK_LINE = (120, 120, 120)
ROAD_COLOR = (255, 210, 70)
EDGE_COLOR = (255, 120, 40)
IX_COLOR = (80, 220, 255)


def _font(size: int = 14) -> ImageFont.ImageFont:
    path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    return ImageFont.truetype(str(path), size) if path.is_file() else ImageFont.load_default()


def _world_bounds(parcels: Sequence[Mapping[str, Any]], pad: float = 0.0004) -> tuple[float, float, float, float]:
    xs: list[float] = []
    ys: list[float] = []
    for parcel in parcels:
        for ring in ((parcel.get("geometry") or {}).get("rings") or []):
            for x, y in ring:
                xs.append(float(x))
                ys.append(float(y))
    return min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad


def _to_px(lon: float, lat: float, bounds: tuple[float, float, float, float], width: int, height: int) -> tuple[int, int]:
    xmin, ymin, xmax, ymax = bounds
    x = int((lon - xmin) / max(xmax - xmin, 1e-9) * (width - 1))
    y = int((1.0 - (lat - ymin) / max(ymax - ymin, 1e-9)) * (height - 1))
    return x, y


def render_estate_layer(
    parcels: Sequence[Mapping[str, Any]],
    records: Sequence[ParcelCornerRecord],
    road_payload: Mapping[str, Any],
    dest: Path,
    *,
    width: int = 1800,
) -> Path:
    bounds = _world_bounds(parcels)
    xmin, ymin, xmax, ymax = bounds
    aspect = (ymax - ymin) / max(xmax - xmin, 1e-9)
    height = max(int(width * aspect), 400)
    image = Image.new("RGB", (width, height + 70), (18, 18, 20))
    overlay = Image.new("RGBA", (width, height), (18, 18, 20, 255))
    draw = ImageDraw.Draw(overlay, "RGBA")
    by_stand = {str(row.stand_number): row for row in records}
    for parcel in parcels:
        rec = by_stand.get(str(parcel.get("stand_number")))
        status = rec.classification if rec else "UNKNOWN"
        fill = {"YES": YES_FILL, "NO": NO_FILL}.get(status, UNK_FILL)
        line = {"YES": YES_LINE, "NO": NO_LINE}.get(status, UNK_LINE)
        for ring in ((parcel.get("geometry") or {}).get("rings") or []):
            pts = [_to_px(float(x), float(y), bounds, width, height) for x, y in ring]
            if len(pts) >= 3:
                draw.polygon(pts, fill=fill, outline=line + (255,))
    for feat in load_road_features(road_payload):
        for path in feat.get("paths") or []:
            pts = [_to_px(float(x), float(y), bounds, width, height) for x, y in path]
            if len(pts) >= 2:
                draw.line(pts, fill=ROAD_COLOR + (255,), width=2)
    base = Image.new("RGB", (width, height), (18, 18, 20))
    base.paste(overlay.convert("RGB"), (0, 0))
    canvas = Image.new("RGB", (width, height + 70), (18, 18, 20))
    canvas.paste(base, (0, 0))
    caption = ImageDraw.Draw(canvas)
    n_yes = sum(1 for row in records if row.classification == "YES")
    n_no = sum(1 for row in records if row.classification == "NO")
    n_unk = sum(1 for row in records if row.classification == "UNKNOWN")
    caption.text(
        (16, height + 12),
        f"Corner Stand Detection v1  GIS layer   YES={n_yes}  NO={n_no}  UNKNOWN={n_unk}   "
        "green=YES  red=NO  grey=UNKNOWN  yellow=road centreline",
        fill=(230, 230, 230),
        font=_font(16),
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(dest, quality=92)
    return dest


def _xy_bounds(coords: Sequence[tuple[float, float]], pad: float = 40.0) -> tuple[float, float, float, float]:
    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]
    return min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad


def _xy_to_px(x: float, y: float, bounds: tuple[float, float, float, float], w: int, h: int) -> tuple[int, int]:
    xmin, ymin, xmax, ymax = bounds
    px = int((x - xmin) / max(xmax - xmin, 1e-6) * (w - 1))
    py = int((1.0 - (y - ymin) / max(ymax - ymin, 1e-6)) * (h - 1))
    return px, py


def render_parcel_proof(
    parcel: Mapping[str, Any],
    record: ParcelCornerRecord,
    road_payload: Mapping[str, Any],
    dest: Path,
    *,
    projector: LocalProjector | None = None,
) -> Path:
    features = load_road_features(road_payload)
    projector = projector or projector_for([parcel], features)
    roads = project_roads(features, projector)
    poly = polygon_from_rings(((parcel.get("geometry") or {}).get("rings") or []), projector)
    if poly is None:
        raise ValueError("parcel has no polygon")
    nearby = [road for road in roads if road.geom.distance(poly) <= 90.0]
    if not nearby:
        nearby = roads
    intersections = [ix for ix in detect_intersections(roads) if poly.distance(ix.point) <= 90.0]
    coords = list(poly.exterior.coords)
    road_coords = [xy for road in nearby for path in road.paths for xy in path.coords]
    bounds = _xy_bounds(coords + road_coords, pad=35.0)
    w, h = 720, 640
    image = Image.new("RGB", (w, h + 110), (16, 16, 18))
    draw = ImageDraw.Draw(image)
    for road in nearby:
        for path in road.paths:
            pts = [_xy_to_px(x, y, bounds, w, h) for x, y in path.coords]
            if len(pts) >= 2:
                draw.line(pts, fill=ROAD_COLOR, width=3)
    pts = [_xy_to_px(x, y, bounds, w, h) for x, y in coords]
    fill = {"YES": (40, 120, 70), "NO": (120, 40, 40)}.get(record.classification, (90, 90, 90))
    draw.polygon(pts, outline=(240, 240, 240), fill=fill)
    edges = extract_road_facing_edges(poly, roads)
    for edge in edges:
        draw.line(
            [_xy_to_px(edge.x0, edge.y0, bounds, w, h), _xy_to_px(edge.x1, edge.y1, bounds, w, h)],
            fill=EDGE_COLOR,
            width=5,
        )
    for ix in intersections:
        px, py = _xy_to_px(ix.x, ix.y, bounds, w, h)
        if 0 <= px < w and 0 <= py < h:
            draw.ellipse([px - 5, py - 5, px + 5, py + 5], fill=IX_COLOR)
    font = _font(15)
    font_sm = _font(13)
    draw.rectangle([0, h, w, h + 110], fill=(12, 12, 14))
    names = ", ".join(record.distinct_road_names) or "none"
    lines = [
        f"PARCEL_CORNER={record.classification}  conf={record.confidence:.2f}  stand={record.stand_number}",
        f"sides={record.n_road_facing_sides}  roads={names}  angle={record.angle_between_sides_deg}  "
        f"ix={record.intersection_proximity_m}m ({record.nearest_intersection_kind})",
        f"reason={record.reason}",
        "white=parcel  yellow=road  orange=road-facing edge  cyan=intersection/bend",
    ]
    y = h + 8
    for i, line in enumerate(lines):
        draw.text((12, y), line, fill=(230, 230, 230), font=font if i == 0 else font_sm)
        y += 24 if i == 0 else 20
    dest.parent.mkdir(parents=True, exist_ok=True)
    image.save(dest, quality=92)
    return dest


def render_listing_proof(
    image_bytes: bytes,
    observation: Mapping[str, Any],
    dest: Path,
    *,
    listing_corner: str,
    confidence: float,
    reason: str,
) -> Path:
    """Listing-evidence panel. Does not overlay the true GIS parcel."""
    import cv2

    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    photo = Image.fromarray(rgb).convert("RGB")
    w, h = photo.size
    canvas = Image.new("RGB", (w, h + 120), (10, 10, 12))
    canvas.paste(photo, (0, 0))
    draw = ImageDraw.Draw(canvas)
    scores = observation.get("side_scores") or {}
    strong = list(observation.get("strong_sides") or [])
    pairs = [tuple(p) for p in (observation.get("adjacent_strong_pairs") or [])]
    if not pairs and len(strong) >= 2:
        pairs = [(strong[0], strong[1])]
    road_sides = set(pairs[0]) if pairs else set(strong[:2])
    labels = {
        "bottom": ((w // 2, h - 42), "apparent primary road"),
        "right": ((w - 28, h // 2), "apparent secondary road"),
        "left": ((28, h // 2), "apparent secondary road"),
        "top": ((w // 2, 24), "apparent primary road"),
    }
    side_labels = {
        "bottom": ((w // 2, h - 42), "apparent parcel side"),
        "right": ((w - 28, h // 2), "apparent parcel side"),
        "left": ((28, h // 2), "apparent parcel side"),
        "top": ((w // 2, 24), "apparent parcel side"),
    }
    for side in ("top", "bottom", "left", "right"):
        if side in road_sides:
            (x, y), text = labels[side]
            color = (255, 210, 80)
        elif side in strong:
            (x, y), text = side_labels[side]
            color = (180, 220, 255)
        else:
            continue
        draw.ellipse([x - 5, y - 5, x + 5, y + 5], fill=color)
        tx = 12 if x < w // 2 else max(12, x - 220)
        draw.text((tx, y + 10), text, fill=color, font=_font(16))
    if {"bottom", "right"} <= road_sides or {"bottom", "left"} <= road_sides:
        draw.arc([w - 150, h - 150, w - 10, h - 10] if "right" in road_sides else [10, h - 150, 150, h - 10],
                 start=0 if "right" in road_sides else 90,
                 end=90 if "right" in road_sides else 180,
                 fill=(255, 90, 90), width=4)
        draw.text((w - 230 if "right" in road_sides else 20, h - 78), "apparent corner", fill=(255, 130, 130), font=_font(16))
    draw.rectangle([0, h, w, h + 120], fill=(12, 12, 14))
    caption = [
        f"LISTING_CORNER={listing_corner}  confidence={confidence:.2f}  (listing evidence only; no GIS parcel)",
        f"frame={observation.get('media_id')}  strong_sides={sorted(strong)}  scores={scores}",
        f"reason={reason}",
        "Annotations mark roads visible in the listing photograph, not a known stand outline.",
    ]
    y = h + 8
    for line in caption:
        draw.text((12, y), line, fill=(230, 230, 230), font=_font(14))
        y += 26
    dest.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(dest, quality=92)
    return dest


def select_proof_parcels(
    parcels: Sequence[Mapping[str, Any]],
    records: Sequence[ParcelCornerRecord],
) -> dict[str, list[tuple[Mapping[str, Any], ParcelCornerRecord]]]:
    by_stand = {str(p.get("stand_number")): p for p in parcels}
    yes = [r for r in records if r.classification == "YES"]
    no = [r for r in records if r.classification == "NO"]
    unk = [r for r in records if r.classification == "UNKNOWN"]
    cul = [r for r in no if r.cul_de_sac_frontage]
    curved = [r for r in no if r.curved_single_road and not r.cul_de_sac_frontage]

    def _pack(rows: Sequence[ParcelCornerRecord], n: int, used: set[str]) -> list[tuple[Mapping[str, Any], ParcelCornerRecord]]:
        chosen = sorted(rows, key=lambda r: -float(r.confidence or 0))
        out = []
        for rec in chosen:
            stand = str(rec.stand_number)
            if stand in used:
                continue
            parcel = by_stand.get(stand)
            if parcel is None:
                continue
            used.add(stand)
            out.append((parcel, rec))
            if len(out) >= n:
                break
        return out

    used: set[str] = set()
    yes = _pack(yes, 12, used)
    no_single = _pack([r for r in no if r.reason == "single_road_frontage_not_corner"], 4, used)
    no_internal = _pack([r for r in no if r.reason == "no_meaningful_road_frontage"], 2, used)
    no_other = _pack(no, 6, used)
    cul = _pack(cul, 6, set())  # allow overlap with NO so cul-de-sac proofs exist even if also NO
    curved = _pack(curved, 6, set())
    unk_rows = _pack(unk, 6, set())
    return {
        "yes": yes,
        "no": no_single + no_internal + no_other,
        "unknown": unk_rows,
        "cul_de_sac": cul,
        "curved_road": curved,
    }
