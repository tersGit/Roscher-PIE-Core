#!/usr/bin/env python3
"""Post-freeze forensic proof panel for listing 115503057.

Read-only of freeze.json / freeze.sha256 / rankings. Does not rerank,
retune weights, replace the official fingerprint, or write identity into
the freeze.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.gis.carlswald_north_complete import COMPLETE_002_PATH
from backend.gis.estate_ags_matching.blind_116273255_complete_estate import (  # noqa: E402
    DATASET_ID,
    REPO_ROOT,
    _font,
    _pool_house_overlay,
    load_os_payload,
)
from backend.gis.estate_ags_matching.estate_property_inventory_v1 import (  # noqa: E402
    crop_path_for,
    pass1_parcels,
)

INV = ROOT / "data/investigations/blind_115503057_complete_estate"
FREEZE = INV / "freeze.json"
SHA = INV / "freeze.sha256"
PHOTOS = INV / "photos"
PANELS = INV / "panels"
LOCK_SHA = "a6465002f681268391d4a87f3039532f47fd97e76d9a43217a8a45c841604ff6"
LOCK_COMMIT = "5aa42ec266a0c515a75e9b7f4da623b0be84dc66"
GT_STAND = "401"
TOP5 = ["868", "624", "648", "545", "401"]


def _verify_freeze() -> dict:
    recorded = SHA.read_text(encoding="utf-8").strip()
    on_disk = hashlib.sha256(FREEZE.read_bytes()).hexdigest()
    if recorded != LOCK_SHA or on_disk != LOCK_SHA:
        raise SystemExit(f"freeze hash mismatch recorded={recorded} on_disk={on_disk}")
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    if freeze.get("ground_truth_applied") is not False:
        raise SystemExit("freeze ground_truth_applied must remain false")
    top5 = [str(row["stand_number"]) for row in freeze["ranking"]["top20"][:5]]
    if top5 != TOP5:
        raise SystemExit(f"frozen Top 5 changed: {top5}")
    return freeze


def _thumb(path: Path, size: tuple[int, int]) -> Image.Image:
    image = Image.open(path).convert("RGB")
    image.thumbnail(size)
    return image


def _cell(image: Image.Image, title: str, subtitle: str, width: int = 340) -> Image.Image:
    image = image.copy()
    image.thumbnail((width, 260))
    canvas = Image.new("RGB", (width, image.size[1] + 48), (18, 18, 18))
    draw = ImageDraw.Draw(canvas)
    draw.text((8, 4), title, fill=(240, 240, 240), font=_font(14))
    draw.text((8, 22), subtitle[:64], fill=(180, 180, 180), font=_font(12))
    x = max(0, (width - image.size[0]) // 2)
    canvas.paste(image, (x, 42))
    return canvas


def _parcel_cell(stand: str, parcel: dict, title: str, subtitle: str) -> Image.Image:
    crop_path = crop_path_for(DATASET_ID, stand, repo_root=REPO_ROOT)
    raw = Image.open(crop_path).convert("RGB") if crop_path.is_file() else Image.new("RGB", (400, 300), (30, 30, 30))
    overlay = _pool_house_overlay(raw, load_os_payload(stand), parcel)
    return _cell(overlay, title, subtitle)


def main() -> None:
    freeze = _verify_freeze()
    dataset = json.loads(COMPLETE_002_PATH.read_text(encoding="utf-8"))
    by_stand = {str(item["stand_number"]): item for item in pass1_parcels(dataset)}
    rows = {str(row["stand_number"]): row for row in freeze["ranking"]["top20"]}

    listing_043 = PHOTOS / "115503057-043.jpg"
    listing_004 = PHOTOS / "115503057-004.jpg"
    listing_proof = INV / "listing_pool_contour_proof.png"

    listing_cells = []
    if listing_proof.is_file():
        listing_cells.append(_cell(_thumb(listing_proof, (340, 240)), "fingerprint 043 + contour", "YOLOE/SAM2 pool_overview POV CONFIRMED"))
    elif listing_043.is_file():
        listing_cells.append(_cell(_thumb(listing_043, (340, 240)), "fingerprint 043", "official hybrid pick"))
    if listing_043.is_file() and listing_proof.is_file():
        listing_cells.append(_cell(_thumb(listing_043, (340, 240)), "listing 043 raw", "lap pool / grey house / side yard"))
    if listing_004.is_file():
        listing_cells.append(_cell(_thumb(listing_004, (340, 240)), "listing 004 front", "double garage / beige cantilever"))

    gt = by_stand[GT_STAND]
    gt_row = rows[GT_STAND]
    gt_cell = _parcel_cell(
        GT_STAND,
        gt,
        f"GT stand {GT_STAND}  6 Buffalo Thorn Dr",
        f"GIS {gt.get('area_sqm')} m2  frozen rank #{gt_row['rank']}  score={gt_row['score']}",
    )

    top_cells = []
    for stand in TOP5:
        row = rows[stand]
        parcel = by_stand[stand]
        mark = "GT" if stand == GT_STAND else "ruled out"
        top_cells.append(
            _parcel_cell(
                stand,
                parcel,
                f"#{row['rank']}  stand {stand}  {mark}",
                f"shape_v2={row['shape_v2']}  score={row['score']}  inv={row['inventory_pool_status']}",
            )
        )

    gap = 10
    rows_imgs = [
        ("Listing 115503057 — fingerprint 043 / front elevation (not used to rerank)", listing_cells),
        ("Ground truth stand 401 — parcel boundary + OS pool (cyan) + building (red) + driveway (green)", [gt_cell]),
        ("Frozen Top 5 — 868 / 624 / 648 / 545 ruled out; 401 independent GT / blind rank 5", top_cells),
    ]
    row_canvases = []
    max_w = 0
    for heading, cells in rows_imgs:
        width = sum(img.size[0] for img in cells) + gap * (len(cells) + 1)
        height = max(img.size[1] for img in cells) + 36
        canvas = Image.new("RGB", (width, height), (10, 10, 10))
        draw = ImageDraw.Draw(canvas)
        draw.text((gap, 6), heading, fill=(220, 220, 220), font=_font(15))
        x = gap
        for img in cells:
            canvas.paste(img, (x, 30))
            x += img.size[0] + gap
        row_canvases.append(canvas)
        max_w = max(max_w, canvas.size[0])

    header_h = 72
    total_h = header_h + sum(img.size[1] for img in row_canvases) + gap * (len(row_canvases) + 1)
    board = Image.new("RGB", (max_w + 16, total_h), (8, 8, 8))
    draw = ImageDraw.Draw(board)
    draw.text((16, 10), "115503057 forensic  |  listing fingerprint 043  /  GT 401  /  frozen Top 5", fill=(250, 250, 250), font=_font(20))
    draw.text(
        (16, 36),
        f"Freeze {LOCK_COMMIT}  SHA256 {LOCK_SHA}  not a rerank  spatial_v2 omitted on all survivors",
        fill=(170, 170, 170),
        font=_font(13),
    )
    y = header_h
    for img in row_canvases:
        board.paste(img, (8, y))
        y += img.size[1] + gap

    PANELS.mkdir(parents=True, exist_ok=True)
    dest = PANELS / "forensic_listing_401_top5.jpg"
    board.convert("RGB").save(dest, quality=90)
    print(f"wrote {dest.relative_to(ROOT)}  {dest.stat().st_size} bytes")
    print("freeze hash untouched")


if __name__ == "__main__":
    main()
