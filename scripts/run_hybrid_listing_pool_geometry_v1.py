#!/usr/bin/env python3
"""Hybrid listing-side pool geometry v1 diagnostic.

Frozen: ranking, OS v1, Scoring v2, native15, viewpoint-gate rules, FastSAM
implementation, PR #12 benchmark outputs. No estate rerank. No colour geometry.
"""

from __future__ import annotations

import io
import json
import sys
import time
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.gis.estate_ags_matching.hybrid_listing_pool_geometry_v1 import (
    collect_yoloe,
    combine_listing_frames,
    extract_frame_geometry,
    frame_public,
)
from backend.gis.estate_ags_matching.listing_evidence_v2 import (
    clip_viewpoint_scores,
    observe_listing_frame,
)
from backend.gis.estate_ags_matching.pool_boundary_model_benchmark_v2 import (
    CACHE,
    SAM21_T,
    YOLOE_M,
    YOLOE_S,
    load_times,
    rss_mb,
)
from backend.gis.estate_ags_matching.pool_boundary_v1 import detect_segments, grayscale_edges
from backend.gis.estate_ags_matching.pool_geometry import _bgr_from_bytes

OUT = ROOT / "data/investigations/hybrid_listing_pool_geometry_v1"
PR12 = ROOT / "data/investigations/pool_boundary_model_benchmark_v2/latest.json"

LISTINGS = (
    {
        "listing_id": "116978058",
        "photos": ROOT / "data/investigations/carlswald_north_corrected/116978058/photos",
        "controls": ("001", "003", "005", "006", "008", "009", "023", "025", "033", "051"),
        "dark_overviews": ("003", "005", "006", "009", "033"),
    },
    {
        "listing_id": "116273255",
        "photos": ROOT / "data/investigations/property_test_116273255/photos",
        "controls": ("007", "008", "020", "029", "036", "037", "038"),
        "dark_overviews": (),
    },
)


def _font(size: int = 13):
    path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    return ImageFont.truetype(str(path), size) if path.is_file() else ImageFont.load_default()


def load_photos(listing_id: str, folder: Path) -> dict[str, bytes]:
    out = {}
    for path in sorted(folder.glob(f"{listing_id}-*.jpg")) + sorted(folder.glob(f"{listing_id}-*.jpeg")):
        out[path.stem] = path.read_bytes()
    return out


def draw_contour(draw, xy, size, color, width=3) -> None:
    w, h = size
    if not xy or len(xy) < 3:
        return
    pts = [(float(x) * (w - 1), float(y) * (h - 1)) for x, y in xy]
    draw.line(pts + [pts[0]], fill=color, width=width)


def caption(draw, text, w) -> None:
    font = _font(13)
    draw.rectangle([4, 4, min(w - 4, 8 + 7 * len(text)), 28], fill=(0, 0, 0))
    draw.text((8, 8), text, fill=(250, 250, 250), font=font)


def panel(body: bytes, frame, dest: Path) -> None:
    original = Image.open(io.BytesIO(body)).convert("RGB")
    overlay = original.copy()
    draw = ImageDraw.Draw(overlay)
    w, h = overlay.size
    color = {
        "yoloe_sam2": (0, 200, 255),
        "yoloe": (0, 220, 80),
        "fastsam_fallback": (255, 180, 40),
        "presence_only": (255, 90, 70),
        "no_usable_geometry": (160, 160, 160),
    }.get(frame.source, (255, 90, 70))
    draw_contour(draw, frame.contour_image, (w, h), color, 3)
    if frame.secondary and frame.secondary.get("contour_image"):
        draw_contour(draw, frame.secondary["contour_image"], (w, h), (220, 80, 255), 2)
    status = "READY" if frame.scoring_ready else frame.source
    label = (
        f"{frame.media_id[-3:]} {frame.viewpoint} {status} "
        f"src={frame.source} q={frame.yoloe_conf:.2f} n={frame.n_components} "
        f"{frame.source_reason}"
    )
    caption(ImageDraw.Draw(original), label, w)
    caption(draw, label, w)
    legend = "cyan=YOLOE+SAM2  green=YOLOE  orange=FastSAM-fallback  purple=secondary"
    draw.rectangle([4, h - 26, min(w - 4, 8 + 7 * len(legend)), h - 4], fill=(0, 0, 0))
    draw.text((8, h - 22), legend, fill=(230, 230, 230), font=_font(11))
    gap = 8
    out = Image.new("RGB", (w * 2 + gap, h), (12, 12, 12))
    out.paste(original, (0, 0))
    out.paste(overlay, (w + gap, 0))
    dest.parent.mkdir(parents=True, exist_ok=True)
    out.save(dest, quality=80)


def dark_overview_probe(listing_id: str, photos: dict[str, bytes], suffixes: tuple[str, ...]) -> list[dict]:
    """Generic recall probe only. No colour thresholds, no ranking feedback."""
    rows = []
    grid = (
        (640, 0.08, "swimming pool"),
        (640, 0.04, "swimming pool"),
        (1024, 0.08, "swimming pool"),
        (1024, 0.04, "swimming pool"),
        (640, 0.08, "outdoor swimming pool"),
        (640, 0.08, "residential swimming pool"),
        (800, 0.08, "swimming pool"),
    )
    for suffix in suffixes:
        media_id = f"{listing_id}-{suffix}"
        body = photos.get(media_id)
        if not body:
            continue
        bgr = _bgr_from_bytes(body)
        gray, _m, _c = grayscale_edges(bgr)
        segments = detect_segments(gray)
        for imgsz, conf, prompt in grid:
            for which in ("s", "m"):
                comps = collect_yoloe(
                    bgr, segments, which=which, prompt=[prompt], conf=conf, imgsz=imgsz
                )
                areas = [round(c.relative_area, 4) for c in comps]
                rows.append(
                    {
                        "media_id": media_id,
                        "model": f"yoloe-11{which}-seg",
                        "prompt": prompt,
                        "imgsz": imgsz,
                        "conf": conf,
                        "n": len(comps),
                        "max_area": max(areas) if areas else 0.0,
                        "confs": [round(c.confidence, 3) for c in comps],
                    }
                )
        print(f"  probe {media_id} done")
    return rows


def run_listing(spec: dict) -> dict:
    listing_id = spec["listing_id"]
    photos = load_photos(listing_id, spec["photos"])
    print(f"\n=== {listing_id} photos={len(photos)} ===")
    frozen = []
    frames = []
    for media_id, body in photos.items():
        image = Image.open(io.BytesIO(body)).convert("RGB")
        scores = clip_viewpoint_scores(image)
        frozen_frame = observe_listing_frame(media_id, body, clip_scores=scores)
        frozen.append(frozen_frame)
        suffix = media_id.split("-")[-1]
        interesting = frozen_frame.viewpoint in {
            "pool_overview",
            "elevated_exterior",
            "ground_level_exterior",
            "aerial_near_nadir",
            "pool_closeup",
        } or suffix in spec["controls"]
        if not interesting:
            continue
        frame = extract_frame_geometry(media_id, body, viewpoint=frozen_frame.viewpoint)
        frames.append(frame)
        print(
            f"  {media_id} vp={frame.viewpoint} src={frame.source} ready={frame.scoring_ready} "
            f"q={frame.yoloe_conf:.2f} n={frame.n_components} {frame.source_reason} {frame.runtime_s:.1f}s"
        )
        panel(body, frame, OUT / listing_id / "panels" / f"{media_id}.jpg")

    listing = combine_listing_frames(frames)
    probe = dark_overview_probe(listing_id, photos, spec["dark_overviews"]) if spec["dark_overviews"] else []
    return {
        "listing_id": listing_id,
        "n_photos": len(photos),
        "viewpoint_counts": dict(Counter(f.viewpoint for f in frozen)),
        "n_extracted": len(frames),
        "source_counts": dict(Counter(f.source for f in frames)),
        "listing": listing,
        "dark_overview_probe": probe,
        "frames": [frame_public(f) for f in frames],
        "control_suffixes": list(spec["controls"]),
    }


def ensure_mobileclip() -> None:
    src = CACHE / "mobileclip_blt.ts"
    cwd = ROOT / "mobileclip_blt.ts"
    repo = Path("/workspace/mobileclip_blt.ts")
    if not src.is_file() and repo.is_file():
        src.parent.mkdir(parents=True, exist_ok=True)
        repo.replace(src)
    if src.is_file() and not cwd.exists():
        cwd.symlink_to(src)


def main() -> int:
    ensure_mobileclip()
    missing = [p for p in (YOLOE_S, YOLOE_M, SAM21_T) if not p.is_file()]
    if missing:
        print("missing", missing)
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    rss0 = rss_mb()
    results = [run_listing(spec) for spec in LISTINGS]
    payload = {
        "experiment": "hybrid_listing_pool_geometry_v1",
        "production_ranking_modified": False,
        "os_v1_modified": False,
        "pbe_v1_modified": False,
        "pr12_modified": False,
        "fastsam_implementation_modified": False,
        "estate_reranked": False,
        "water_colour_used_as_boundary": False,
        "listing_specific_shape_rules": False,
        "load_times_s": load_times(),
        "rss_mb_max": round(rss_mb(), 1),
        "rss_mb_start": round(rss0, 1),
        "wall_s": round(time.perf_counter() - t0, 2),
        "listings": results,
        "pr12_reference": str(PR12),
    }
    (OUT / "latest.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print("\nLISTING GATES")
    for item in results:
        print(item["listing_id"], item["listing"], "sources", item["source_counts"])
    print("wall", payload["wall_s"], "rss", payload["rss_mb_max"])
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
