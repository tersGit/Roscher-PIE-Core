"""Hybrid extraction-fix proof panels. Extraction only — no ranking.

Compares archived Hybrid contours against a fresh extract_frame_geometry pass.
Does not call Scoring v2, Pool Gate, OS v1, or estate ranking.
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.gis.estate_ags_matching.hybrid_listing_pool_geometry_v1 import (
    combine_listing_frames,
    extract_frame_geometry,
    frame_public,
)

OUT = ROOT / "data/investigations/hybrid_extraction_fix"
CASES = (
    {
        "listing_id": "116978058",
        "photos": ROOT / "data/investigations/blind_116978058_complete_estate/photos",
        "old_block": ROOT / "data/investigations/blind_116978058_complete_estate/hybrid_block.json",
        "frames": ("003", "005", "016", "026"),
    },
    {
        "listing_id": "116889694",
        "photos": ROOT / "data/investigations/blind_116889694_complete_estate/photos",
        "old_block": ROOT / "data/investigations/blind_116889694_complete_estate/hybrid_block.json",
        "frames": ("002", "026", "027", "028"),
    },
)


def _font(size: int = 13):
    path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    return ImageFont.truetype(str(path), size) if path.is_file() else ImageFont.load_default()


def _overlay_contour(image: Image.Image, xy, color, width=3) -> Image.Image:
    out = image.convert("RGB")
    if not xy or len(xy) < 3:
        return out
    draw = ImageDraw.Draw(out)
    w, h = out.size
    pts = [(int(float(x) * (w - 1)), int(float(y) * (h - 1))) for x, y in xy]
    draw.line(pts + [pts[0]], fill=color, width=width)
    return out


def _fill_contour(image: Image.Image, xy, color=(40, 180, 255)) -> Image.Image:
    out = image.convert("RGBA")
    if not xy or len(xy) < 3:
        return out.convert("RGB")
    overlay = Image.new("RGBA", out.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    w, h = out.size
    pts = [(int(float(x) * (w - 1)), int(float(y) * (h - 1))) for x, y in xy]
    draw.polygon(pts, fill=color + (90,))
    draw.line(pts + [pts[0]], fill=color + (255,), width=2)
    return Image.alpha_composite(out, overlay).convert("RGB")


def _mask_overlay(image: Image.Image, mask: np.ndarray | None) -> Image.Image:
    out = image.convert("RGBA")
    if mask is None:
        return out.convert("RGB")
    resized = Image.fromarray((np.asarray(mask) > 0).astype(np.uint8) * 150).resize(out.size, Image.NEAREST)
    tint = Image.new("RGBA", out.size, (40, 180, 255, 0))
    tint.putalpha(resized)
    return Image.alpha_composite(out, tint).convert("RGB")


def _cell(img: Image.Image, title: str) -> Image.Image:
    img = img.copy()
    img.thumbnail((320, 240))
    canvas = Image.new("RGB", (img.size[0], img.size[1] + 22), (16, 16, 16))
    ImageDraw.Draw(canvas).text((4, 3), title, fill=(230, 230, 230), font=_font(12))
    canvas.paste(img, (0, 22))
    return canvas


def _metrics(frame: dict | None) -> dict:
    if not frame:
        return {}
    geom = ((frame.get("dominant") or {}).get("geometry") or {})
    clip = ((frame.get("dominant") or {}).get("clip") or {})
    desc = frame.get("descriptors") or {}
    return {
        "scoring_ready": frame.get("scoring_ready"),
        "source": frame.get("source"),
        "viewpoint": frame.get("viewpoint"),
        "source_reason": frame.get("source_reason"),
        "detector": (frame.get("dominant") or {}).get("detector") or (frame.get("dominant") or {}).get("model"),
        "aspect_ratio": geom.get("aspect_ratio") or desc.get("aspect_ratio"),
        "solidity": geom.get("solidity") or desc.get("solidity"),
        "major_indents": geom.get("n_major_indents") if geom.get("n_major_indents") is not None else desc.get("n_major_indents"),
        "max_indent": geom.get("max_indent"),
        "compactness": geom.get("compactness"),
        "n_approx": geom.get("n_approx"),
        "semantic_confidence": clip.get("pool"),
        "clip_deck": clip.get("deck"),
        "clip_vegetation": clip.get("vegetation"),
        "geometry_quality": frame.get("geometry_quality"),
        "geometry_loss": (frame.get("geometry_loss") or {}).get("verdict"),
        "presence_retained": bool(frame.get("presence_evidence")),
        "spa_present": bool((frame.get("spa_relationship") or {}).get("secondary_present")),
        "reject_trace": [
            row for row in (frame.get("extraction_trace") or []) if row.get("status") == "rejected"
        ],
    }


def draw_proof(photo: bytes, old_frame: dict | None, new_frame, dest: Path) -> None:
    src = Image.open(io.BytesIO(photo)).convert("RGB")
    src.thumbnail((320, 240))
    old_xy = None if old_frame is None else (old_frame.get("contour_image") or ((old_frame.get("dominant") or {}).get("contour_image")))
    new_dom = None if new_frame is None else (new_frame.dominant or {})
    cells = [
        _cell(src, "1 SOURCE"),
        _cell(_fill_contour(src, old_xy), "2 OLD MASK (contour fill)"),
        _cell(_overlay_contour(src, old_xy, (255, 90, 90)), "3 OLD CONTOUR"),
        _cell(_mask_overlay(src, None if new_frame is None else new_frame.mask), "4 NEW MASK"),
        _cell(
            _overlay_contour(src, None if new_dom is None else new_dom.get("raw_contour_image"), (80, 220, 255)),
            "5 NEW RAW CONTOUR",
        ),
        _cell(
            _overlay_contour(src, None if new_frame is None else new_frame.contour_image, (255, 200, 80)),
            "6 NEW 64-POINT CONTOUR",
        ),
    ]
    gap = 8
    row_w = sum(c.size[0] for c in cells) + gap * (len(cells) + 1)
    row_h = max(c.size[1] for c in cells) + 56
    canvas = Image.new("RGB", (row_w, row_h), (10, 10, 10))
    draw = ImageDraw.Draw(canvas)
    mid = getattr(new_frame, "media_id", "")
    ready = None if new_frame is None else new_frame.scoring_ready
    src_name = None if new_frame is None else new_frame.source
    draw.text(
        (10, 8),
        f"{mid}  new_source={src_name}  scoring_ready={ready}  (extraction only, not ranked)",
        fill=(240, 240, 240),
        font=_font(15),
    )
    x = gap
    for cell in cells:
        canvas.paste(cell, (x, 36))
        x += cell.size[0] + gap
    dest.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(dest, quality=90)


def run_case(case: dict) -> dict:
    listing_id = case["listing_id"]
    old = json.loads(Path(case["old_block"]).read_text(encoding="utf-8"))
    old_frames = {str(f.get("media_id")): f for f in old.get("frames") or []}
    photos = {}
    for suffix in case["frames"]:
        media_id = f"{listing_id}-{suffix}"
        path = Path(case["photos"]) / f"{media_id}.jpg"
        if path.is_file():
            photos[media_id] = path.read_bytes()
    extracted = []
    per_frame = []
    out_dir = OUT / listing_id
    out_dir.mkdir(parents=True, exist_ok=True)
    for media_id, body in photos.items():
        old_f = old_frames.get(media_id)
        vp = None if old_f is None else old_f.get("viewpoint")
        frame = extract_frame_geometry(media_id, body, viewpoint=vp)
        extracted.append(frame)
        draw_proof(body, old_f, frame, out_dir / f"{media_id}_before_after.jpg")
        pub = frame_public(frame)
        per_frame.append(
            {
                "media_id": media_id,
                "before": _metrics(old_f),
                "after": _metrics(pub),
                "extraction_trace": pub.get("extraction_trace"),
                "presence_evidence": pub.get("presence_evidence"),
                "spa_relationship": pub.get("spa_relationship"),
                "geometry_loss": pub.get("geometry_loss"),
                "scoring_ready_reason": pub.get("scoring_ready_reason"),
            }
        )
    listing = combine_listing_frames(extracted)
    old_listing = old.get("listing") or {}
    return {
        "listing_id": listing_id,
        "old_listing": {
            "n_scoring_ready": old_listing.get("n_scoring_ready"),
            "chosen_id": old_listing.get("chosen_id"),
            "chosen_source": old_listing.get("chosen_source"),
            "chosen_reason": old_listing.get("chosen_reason"),
        },
        "new_listing": listing,
        "frames": per_frame,
        "ranking_ran": False,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report = {
        "experiment": "hybrid_extraction_fix",
        "ranking_ran": False,
        "note": "Extraction only. Frozen blind rankings for these listings were not rerun.",
        "cases": [],
    }
    for case in CASES:
        report["cases"].append(run_case(case))
    (OUT / "latest.json").write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({c["listing_id"]: c["new_listing"] for c in report["cases"]}, indent=2))


if __name__ == "__main__":
    main()
