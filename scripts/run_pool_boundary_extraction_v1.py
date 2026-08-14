#!/usr/bin/env python3
"""Pool Boundary Extraction v1 diagnostic for listings 116978058 and 116273255.

Frozen: production ranking, OS v1, Scoring v2, native15, PR #8 viewpoint gates,
PR #10 object-heatmap module. Does not rerank estate candidates.
"""

from __future__ import annotations

import io
import json
import sys
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.gis.estate_ags_matching.listing_evidence_v2 import (
    clip_viewpoint_scores,
    observe_listing_frame,
)
from backend.gis.estate_ags_matching.pool_boundary_v1 import (
    corroborate_axes,
    extract_frame_boundary,
    frame_public,
    listing_gate,
    reapply_corroboration,
)
from backend.gis.estate_ags_matching.pool_geometry import _bgr_from_bytes

OUT = ROOT / "data/investigations/pool_boundary_extraction_v1"
LISTINGS = (
    {
        "listing_id": "116978058",
        "photos": ROOT / "data/investigations/carlswald_north_corrected/116978058/photos",
        "controls": ("001", "002", "003", "005", "006", "009", "025", "051", "052"),
        "overviews_expected": ("003", "005", "006", "008", "009"),
    },
    {
        "listing_id": "116273255",
        "photos": ROOT / "data/investigations/property_test_116273255/photos",
        "controls": ("001", "002", "007", "008", "020", "029", "036", "037", "038"),
        "overviews_expected": ("008", "036", "037", "038"),
    },
)


def _font(size: int = 14):
    path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    return ImageFont.truetype(str(path), size) if path.is_file() else ImageFont.load_default()


def load_photos(listing_id: str, folder: Path) -> list[tuple[str, bytes]]:
    files = sorted(folder.glob(f"{listing_id}-*.jpg")) + sorted(folder.glob(f"{listing_id}-*.jpeg"))
    return [(p.stem, p.read_bytes()) for p in files]


def draw_overlay(body: bytes, frame, dest: Path) -> None:

    image = Image.open(io.BytesIO(body)).convert("RGB")
    draw = ImageDraw.Draw(image)
    w, h = image.size
    font = _font(13)
    if frame.best is not None:
        # rejected structural edges: wall-climb is already filtered; draw kept contour
        xy = (frame.best.descriptors or {}).get("contour_image") or []
        if len(xy) >= 3:
            pts = [(float(x) * (w - 1), float(y) * (h - 1)) for x, y in xy]
            color = (0, 220, 80) if frame.best.accepted else (255, 90, 70)
            draw.line(pts + [pts[0]], fill=color, width=3)
        # method contours in thinner overlays
        for prop in frame.proposals:
            if prop.method == (frame.best.method if frame.best else ""):
                continue
            cxy = (prop.descriptors or {}).get("contour_image") or []
            if len(cxy) >= 3:
                pts = [(float(x) * (w - 1), float(y) * (h - 1)) for x, y in cxy]
                draw.line(pts + [pts[0]], fill=(80, 160, 255), width=1)
    status = "ACCEPT" if frame.scoring_ready else "REJECT"
    reason = ""
    if frame.best is not None:
        reason = frame.best.reject_reason or "ok"
    label = (
        f"{frame.media_id[-3:]} {frame.viewpoint} {status} "
        f"method={None if frame.best is None else frame.best.method} "
        f"q={0 if frame.best is None else frame.best.confidence:.2f} "
        f"struct={0 if frame.best is None else frame.best.structural_support:.2f} "
        f"{reason}"
    )
    draw.rectangle([4, 4, min(w - 4, 8 + 7 * len(label)), 28], fill=(0, 0, 0))
    draw.text((8, 8), label, fill=(250, 250, 250), font=font)
    dest.parent.mkdir(parents=True, exist_ok=True)
    image.save(dest, quality=82)


def contact_sheet(photos: dict[str, bytes], frames, dest: Path, ids: tuple[str, ...]) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    by = {f.media_id.split("-")[-1]: f for f in frames}
    cols, tw, th = 3, 420, 300
    items = [sid for sid in ids if sid in by]
    rows = max(1, (len(items) + cols - 1) // cols)
    sheet = Image.new("RGB", (cols * tw, rows * th), (18, 18, 18))
    font = _font(15)
    for i, sid in enumerate(items):
        frame = by[sid]
        body = photos.get(frame.media_id)
        if not body:
            continue
        im = Image.open(io.BytesIO(body)).convert("RGB")
        im.thumbnail((tw, th - 36))
        cell = Image.new("RGB", (tw, th), (28, 28, 28))
        cell.paste(im, ((tw - im.size[0]) // 2, 36 + (th - 36 - im.size[1]) // 2))
        draw = ImageDraw.Draw(cell)
        st = "A" if frame.scoring_ready else "R"
        draw.text((8, 8), f"{sid} {frame.viewpoint} {st}", fill=(240, 240, 240), font=font)
        r, c = divmod(i, cols)
        sheet.paste(cell, (c * tw, r * th))
    sheet.save(dest, quality=85)


def run_listing(spec: dict) -> dict:
    listing_id = spec["listing_id"]
    photos = load_photos(listing_id, spec["photos"])
    photo_map = {mid: body for mid, body in photos}
    print(f"\n=== {listing_id} photos={len(photos)} ===")
    frozen = []
    boundaries = []
    for media_id, body in photos:
        image = Image.open(io.BytesIO(body)).convert("RGB")
        scores = clip_viewpoint_scores(image)
        frozen_frame = observe_listing_frame(media_id, body, clip_scores=scores)
        frozen.append(frozen_frame)
        suffix = media_id.split("-")[-1]
        interesting = (
            frozen_frame.viewpoint in {"pool_overview", "elevated_exterior", "ground_level_exterior", "aerial_near_nadir", "pool_closeup"}
            or suffix in spec["controls"]
        )
        if not interesting:
            # still record frozen viewpoint-only stub
            continue
        frame = extract_frame_boundary(
            media_id, body, viewpoint=frozen_frame.viewpoint, clip_scores=scores, corroborated=False
        )
        boundaries.append(frame)
        best = frame.best
        print(
            f"  {media_id} vp={frame.viewpoint} present={frame.pool_present} "
            f"ready={frame.scoring_ready} method={None if best is None else best.method} "
            f"struct={0 if best is None else best.structural_support:.2f} "
            f"reason={frame.gate_reasons[:2]}"
        )

    flags = corroborate_axes(boundaries)
    reapply_corroboration(boundaries, flags)
    gate = listing_gate(boundaries)

    out_dir = OUT / listing_id
    overlay_dir = out_dir / "panels"
    for frame in boundaries:
        body = photo_map.get(frame.media_id)
        if body:
            draw_overlay(body, frame, overlay_dir / f"{frame.media_id}.jpg")
    contact_sheet(photo_map, boundaries, out_dir / "contact_sheet.jpg", spec["controls"])

    method_wins = Counter(
        f.best.method for f in boundaries if f.best is not None and f.scoring_ready
    )
    return {
        "listing_id": listing_id,
        "n_photos": len(photos),
        "viewpoint_counts": dict(Counter(f.viewpoint for f in frozen)),
        "n_extracted": len(boundaries),
        "frozen_pool_true": sum(1 for f in frozen if f.pool_detected),
        "object_present": sum(1 for f in boundaries if f.pool_present),
        "scoring_ready": sum(1 for f in boundaries if f.scoring_ready),
        "gate": gate,
        "multiframe_flags": flags,
        "method_wins": dict(method_wins),
        "frames": [frame_public(f) for f in boundaries],
        "control_suffixes": list(spec["controls"]),
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    results = []
    for spec in LISTINGS:
        results.append(run_listing(spec))
    payload = {
        "experiment": "pool_boundary_extraction_v1",
        "production_ranking_modified": False,
        "os_v1_modified": False,
        "pr6_modified": False,
        "pr8_viewpoint_rules_modified": False,
        "pr10_modified": False,
        "estate_reranked": False,
        "water_colour_used_as_boundary": False,
        "listing_specific_shape_rules": False,
        "listings": results,
    }
    (OUT / "latest.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print("\nGATES")
    for item in results:
        print(item["listing_id"], item["gate"])
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
