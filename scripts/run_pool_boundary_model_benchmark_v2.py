#!/usr/bin/env python3
"""Benchmark YOLOE + SAM2.1-t against frozen PR #11 pool boundaries.

Does not replace FastSAM, does not modify PBE v1, does not rerank the estate.
"""

from __future__ import annotations

import io
import json
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.gis.estate_ags_matching.pool_boundary_model_benchmark_v2 import (
    CACHE,
    SAM21_T,
    YOLOE_M,
    YOLOE_S,
    detect_segments,
    grayscale_edges,
    load_times,
    pick_best,
    public_mask,
    rss_mb,
    sam_from_box,
    sam_from_point,
    yoloe_text_multi,
    yoloe_text_pool,
)
from backend.gis.estate_ags_matching.pool_geometry import _bgr_from_bytes

OUT = ROOT / "data/investigations/pool_boundary_model_benchmark_v2"
PR11 = ROOT / "data/investigations/pool_boundary_extraction_v1/latest.json"

LISTINGS = (
    {
        "listing_id": "116978058",
        "photos": ROOT / "data/investigations/carlswald_north_corrected/116978058/photos",
        "frames": ("003", "005", "006", "008", "009", "023", "025", "033", "001", "051"),
        "sam_frames": ("003", "008", "009", "025"),
    },
    {
        "listing_id": "116273255",
        "photos": ROOT / "data/investigations/property_test_116273255/photos",
        "frames": ("007", "008", "020", "029", "036", "037", "038"),
        "sam_frames": ("008", "029", "036", "037", "038"),
    },
)


def _font(size: int = 14):
    path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    return ImageFont.truetype(str(path), size) if path.is_file() else ImageFont.load_default()


def load_pr11() -> dict:
    payload = json.loads(PR11.read_text(encoding="utf-8"))
    frames = {}
    for listing in payload["listings"]:
        for frame in listing["frames"]:
            frames[frame["media_id"]] = frame
    return frames


def photo_bytes(folder: Path, listing_id: str, suffix: str) -> bytes | None:
    for ext in (".jpg", ".jpeg"):
        path = folder / f"{listing_id}-{suffix}{ext}"
        if path.is_file():
            return path.read_bytes()
    return None


def draw_contour(draw: ImageDraw.ImageDraw, contour_xy, size, color, width=3) -> None:
    w, h = size
    if not contour_xy or len(contour_xy) < 3:
        return
    pts = [(float(x) * (w - 1), float(y) * (h - 1)) for x, y in contour_xy]
    draw.line(pts + [pts[0]], fill=color, width=width)


def caption(draw, text, w) -> None:
    font = _font(13)
    draw.rectangle([4, 4, min(w - 4, 8 + 7 * len(text)), 28], fill=(0, 0, 0))
    draw.text((8, 8), text, fill=(250, 250, 250), font=font)


def three_panel(body: bytes, pr11_frame: dict | None, best, dest: Path, media_id: str) -> None:
    original = Image.open(io.BytesIO(body)).convert("RGB")
    w, h = original.size
    left = original.copy()
    mid = original.copy()
    right = original.copy()
    d0, d1, d2 = ImageDraw.Draw(left), ImageDraw.Draw(mid), ImageDraw.Draw(right)
    caption(d0, f"{media_id[-3:]} original", w)
    pr_best = None if pr11_frame is None else pr11_frame.get("best")
    pr_xy = None if pr_best is None else pr_best.get("contour_image")
    pr_method = None if pr_best is None else pr_best.get("method")
    pr_ok = bool(pr11_frame and pr11_frame.get("scoring_ready"))
    draw_contour(d1, pr_xy, (w, h), (0, 220, 80) if pr_ok else (255, 90, 70), 3)
    caption(
        d1,
        f"PR11 {pr_method} {'ACCEPT' if pr_ok else 'REJECT'}",
        w,
    )
    if best is not None:
        draw_contour(d2, (best.geometry or {}).get("contour_image"), (w, h), (0, 180, 255), 3)
        caption(
            d2,
            f"{best.model} {best.strategy} q={best.confidence:.2f} struct={best.structural_support:.2f}",
            w,
        )
    else:
        caption(d2, "new model: no pool mask", w)
    gap = 8
    panel = Image.new("RGB", (w * 3 + gap * 2, h), (12, 12, 12))
    panel.paste(left, (0, 0))
    panel.paste(mid, (w + gap, 0))
    panel.paste(right, (2 * (w + gap), 0))
    dest.parent.mkdir(parents=True, exist_ok=True)
    panel.save(dest, quality=80)


def run_listing(spec: dict, pr11_frames: dict) -> dict:
    listing_id = spec["listing_id"]
    print(f"\n=== {listing_id} ===")
    frames_out = []
    for suffix in spec["frames"]:
        body = photo_bytes(spec["photos"], listing_id, suffix)
        media_id = f"{listing_id}-{suffix}"
        if body is None:
            print("  missing", media_id)
            continue
        bgr = _bgr_from_bytes(body)
        gray, _mag, _canny = grayscale_edges(bgr)
        segments = detect_segments(gray)
        pr11 = pr11_frames.get(media_id)
        t_frame = time.perf_counter()
        results = [
            yoloe_text_pool(bgr, "s", segments),
            yoloe_text_pool(bgr, "m", segments),
            yoloe_text_multi(bgr, "s", segments),
            yoloe_text_multi(bgr, "m", segments),
        ]
        seed = pick_best(results)
        if suffix in spec["sam_frames"] and seed is not None and seed.box is not None and SAM21_T.is_file():
            results.append(sam_from_box(bgr, seed.box, segments, seed.confidence))
            if seed.mask is not None:
                results.append(sam_from_point(bgr, seed.mask, seed.confidence, segments))
        best = pick_best(results)
        dt = time.perf_counter() - t_frame
        print(
            f"  {media_id} vp={None if pr11 is None else pr11.get('viewpoint')} "
            f"best={None if best is None else best.model+'/'+best.strategy} "
            f"q={0 if best is None else best.confidence:.2f} "
            f"area={None if best is None else (best.geometry or {}).get('relative_area')} "
            f"frame_s={dt:.1f}"
        )
        three_panel(body, pr11, best, OUT / listing_id / "panels" / f"{media_id}.jpg", media_id)
        frames_out.append(
            {
                "media_id": media_id,
                "viewpoint": None if pr11 is None else pr11.get("viewpoint"),
                "pr11_method": None if not pr11 or not pr11.get("best") else pr11["best"].get("method"),
                "pr11_scoring_ready": False if pr11 is None else bool(pr11.get("scoring_ready")),
                "pr11_reject": None if not pr11 or not pr11.get("best") else pr11["best"].get("reject_reason"),
                "best": public_mask(best),
                "strategies": [public_mask(r) for r in results],
                "frame_runtime_s": round(dt, 3),
            }
        )
    return {"listing_id": listing_id, "frames": frames_out}


def main() -> int:
    missing = [p for p in (YOLOE_S, YOLOE_M) if not p.is_file()]
    if missing:
        print("missing weights", missing, "in", CACHE)
        return 2
    # YOLOE text encoder looks for mobileclip_blt.ts in cwd.
    clip_src = CACHE / "mobileclip_blt.ts"
    clip_cwd = ROOT / "mobileclip_blt.ts"
    repo_clip = Path("/workspace/mobileclip_blt.ts")
    if not clip_src.is_file() and repo_clip.is_file():
        clip_src.parent.mkdir(parents=True, exist_ok=True)
        repo_clip.replace(clip_src)
    if clip_src.is_file() and not clip_cwd.exists():
        clip_cwd.symlink_to(clip_src)
    OUT.mkdir(parents=True, exist_ok=True)
    pr11 = load_pr11()
    t0 = time.perf_counter()
    rss0 = rss_mb()
    listings = [run_listing(spec, pr11) for spec in LISTINGS]
    payload = {
        "experiment": "pool_boundary_model_benchmark_v2",
        "production_ranking_modified": False,
        "os_v1_modified": False,
        "pbe_v1_modified": False,
        "estate_reranked": False,
        "water_colour_used_as_boundary": False,
        "listing_specific_shape_rules": False,
        "fastsam_replaced": False,
        "models": {
            "yoloe-11s-seg": str(YOLOE_S),
            "yoloe-11m-seg": str(YOLOE_M),
            "sam2.1_t": str(SAM21_T) if SAM21_T.is_file() else None,
        },
        "load_times_s": load_times(),
        "rss_mb_max": round(rss_mb(), 1),
        "rss_mb_start": round(rss0, 1),
        "wall_s": round(time.perf_counter() - t0, 2),
        "listings": listings,
    }
    (OUT / "latest.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print("\nload_times", load_times())
    print("rss_mb", rss_mb(), "wall_s", payload["wall_s"])
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
