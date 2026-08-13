#!/usr/bin/env python3
"""Post-process AGS resolution experiment: extra pairs, identify, chips, report."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import cv2
import httpx
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from skimage.metrics import structural_similarity

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.imagery.ags_client import AGSAerialClient  # noqa: E402
from backend.imagery.estate_tiles import DEFAULT_PIXELS, DEFAULT_TILE_METRES  # noqa: E402
from scripts.investigate_ags_resolution import (  # noqa: E402
    INTERPOLATION,
    NATIVE_PIXEL_SIZE_M,
    OUT,
    SERVICE,
    YEAR,
    bgr_to_pil,
    geo_chip,
    image_metrics,
    letterbox,
    load_bgr,
    pair_comparisons,
    resize_to,
    save_chip_sheet,
    save_upsample_sheet,
    ssim_gray,
    tile_strategy,
    to_gray,
)

CHIP_WINDOWS = {
    "stand_34": {
        "roof": (0.32, 0.42, 0.78, 0.82),
        "pool": (0.38, 0.28, 0.62, 0.52),
        "driveway": (0.05, 0.42, 0.42, 0.82),
    },
    "stand_36": {
        "roof": (0.28, 0.30, 0.72, 0.72),
        "pool": (0.22, 0.38, 0.48, 0.62),
        "driveway": (0.45, 0.55, 0.85, 0.90),
    },
    "stand_677": {
        "roof": (0.28, 0.38, 0.72, 0.78),
        "pool": (0.36, 0.26, 0.60, 0.46),
        "driveway": (0.12, 0.40, 0.42, 0.68),
    },
}

VISUAL_SCORES = {
    # roof, pool, driveway  (0-4)
    "stand_34": {
        256: (1, 1, 1),
        400: (2, 2, 2),
        800: (3, 3, 3),
        1200: (4, 4, 4),
        1600: (4, 4, 4),
        2400: (4, 3, 3),
        3200: (3, 3, 3),
    },
    "stand_36": {
        256: (1, 1, 1),
        400: (2, 2, 2),
        800: (3, 3, 3),
        1200: (4, 4, 4),
        1600: (4, 4, 4),
        2400: (4, 3, 3),
        3200: (3, 3, 3),
    },
    "stand_677": {
        256: (1, 1, 1),
        400: (2, 2, 2),
        800: (4, 4, 3),
        1200: (4, 4, 3),
        1600: (4, 4, 3),
        2400: (4, 3, 3),
        3200: (3, 3, 3),
    },
}


def _font(size: int = 15):
    path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    return ImageFont.truetype(str(path), size) if path.is_file() else ImageFont.load_default()


def identify_3857(x: float, y: float) -> dict:
    params = {
        "geometry": json.dumps({"x": x, "y": y}),
        "geometryType": "esriGeometryPoint",
        "sr": "3857",
        "returnGeometry": "false",
        "returnCatalogItems": "true",
        "f": "json",
    }
    with httpx.Client(timeout=40.0, follow_redirects=True) as client:
        payload = client.get(f"{SERVICE}/identify", params=params).json()
    catalog = payload.get("catalogItems") or {}
    features = catalog.get("features") or []
    native = []
    overviews = []
    for feat in features:
        attrs = feat.get("attributes") or {}
        rec = {
            "Name": attrs.get("Name"),
            "LowPS": attrs.get("LowPS"),
            "HighPS": attrs.get("HighPS"),
            "MinPS": attrs.get("MinPS"),
            "MaxPS": attrs.get("MaxPS"),
        }
        name = str(attrs.get("Name") or "")
        if "15cm" in name:
            native.append(rec)
        else:
            overviews.append(rec)
    return {
        "pixel_value": payload.get("value"),
        "native_rasters": native,
        "overview_rasters": overviews,
    }


def uncapped_sift_count(gray: np.ndarray) -> int:
    sift = cv2.SIFT_create(nfeatures=0, contrastThreshold=0.04)
    kps = sift.detect(gray, None)
    return int(len(kps))


def extra_pairs(images: dict[int, np.ndarray]) -> dict:
    out = pair_comparisons(images)
    extra = [(256, 400), (400, 800), (800, 1200)]
    for lo, hi in extra:
        if lo not in images or hi not in images:
            continue
        key = f"{hi}_vs_upscaled_{lo}"
        if key in out:
            continue
        hi_down = resize_to(images[hi], lo, cv2.INTER_AREA)
        lo_up = resize_to(images[lo], hi, cv2.INTER_LINEAR)
        lo_up_c = resize_to(images[lo], hi, cv2.INTER_CUBIC)
        m_hi = image_metrics(images[hi])
        m_up = image_metrics(lo_up)
        out[key] = {
            "ssim_hi_vs_bilinear_up_lo": ssim_gray(images[hi], lo_up),
            "ssim_hi_vs_cubic_up_lo": ssim_gray(images[hi], lo_up_c),
            "ssim_lo_vs_downsampled_hi": ssim_gray(images[lo], hi_down),
            "laplacian_hi": m_hi["laplacian_variance"],
            "laplacian_upscaled_lo": m_up["laplacian_variance"],
            "hf_hi": m_hi["high_freq_energy_frac"],
            "hf_upscaled_lo": m_up["high_freq_energy_frac"],
            "sift_hi": uncapped_sift_count(to_gray(images[hi])),
            "sift_upscaled_lo": uncapped_sift_count(to_gray(lo_up)),
            "edge_density_hi": m_hi["edge_density"],
            "edge_density_upscaled_lo": m_up["edge_density"],
        }
    # replace capped sift on existing pairs
    for key, cmp_ in out.items():
        if "_vs_upscaled_" not in key:
            continue
        left, right = key.split("_vs_upscaled_")
        try:
            hi, lo = int(left), int(right)
        except ValueError:
            continue
        if hi in images and lo in images:
            lo_up = resize_to(images[lo], hi, cv2.INTER_LINEAR)
            cmp_["sift_hi_uncapped"] = uncapped_sift_count(to_gray(images[hi]))
            cmp_["sift_upscaled_lo_uncapped"] = uncapped_sift_count(to_gray(lo_up))
    return out


def crop_ags_to_padded_rect(ags: np.ndarray, square: dict, rect: dict) -> np.ndarray:
    rx0, ry0 = AGSAerialClient.wgs84_to_web_mercator(rect["min_lat"], rect["min_lon"])
    rx1, ry1 = AGSAerialClient.wgs84_to_web_mercator(rect["max_lat"], rect["max_lon"])
    side = square["side_m"]
    fx0 = (rx0 - square["xmin"]) / side
    fx1 = (rx1 - square["xmin"]) / side
    fy0 = (square["ymax"] - ry1) / side  # image y grows down
    fy1 = (square["ymax"] - ry0) / side
    return geo_chip(ags, fx0, fy0, fx1, fy1)


def compare_current_vs_ags(current: np.ndarray, ags_overlap: np.ndarray) -> dict:
    # compare at current crop size (what PIE actually holds) and at AGS overlap size
    h, w = current.shape[:2]
    ags_at_current = cv2.resize(ags_overlap, (w, h), interpolation=cv2.INTER_AREA)
    up_current = cv2.resize(current, (ags_overlap.shape[1], ags_overlap.shape[0]), interpolation=cv2.INTER_LINEAR)
    return {
        "current_size": [int(w), int(h)],
        "ags_overlap_size": [int(ags_overlap.shape[1]), int(ags_overlap.shape[0])],
        "ssim_current_vs_ags_downsampled_to_current": ssim_gray(current, ags_at_current),
        "ssim_ags_vs_current_upscaled": ssim_gray(ags_overlap, up_current),
        "laplacian_current": float(cv2.Laplacian(to_gray(current), cv2.CV_64F).var()),
        "laplacian_ags_at_current_size": float(cv2.Laplacian(to_gray(ags_at_current), cv2.CV_64F).var()),
        "laplacian_ags_native_overlap": float(cv2.Laplacian(to_gray(ags_overlap), cv2.CV_64F).var()),
        "sift_current": uncapped_sift_count(to_gray(current)),
        "sift_ags_downsampled_to_current": uncapped_sift_count(to_gray(ags_at_current)),
        "sift_ags_overlap": uncapped_sift_count(to_gray(ags_overlap)),
        "sift_current_upscaled": uncapped_sift_count(to_gray(up_current)),
    }


def gained_label(size: int, native_px: float, ssim_vs_prev: float | None) -> str:
    ratio = size / native_px
    if ratio < 0.70:
        return "below native — additional source detail still available"
    if ratio < 0.95:
        return "approaching native — most remaining source detail"
    if ratio <= 1.15:
        return "at native source resolution (~0.15 m/px)"
    if ssim_vs_prev is not None and ssim_vs_prev >= 0.96:
        return "UPSCALED — NO EXPECTED ADDITIONAL SOURCE DETAIL"
    return "beyond native (JPEG / resampling differences only)"


def fmt_pair(cmp_: dict) -> str:
    sift_hi = cmp_.get("sift_hi_uncapped", cmp_.get("sift_hi"))
    sift_up = cmp_.get("sift_upscaled_lo_uncapped", cmp_.get("sift_upscaled_lo"))
    return (
        f"SSIM(hi vs bilinear-up lo)={cmp_['ssim_hi_vs_bilinear_up_lo']:.4f}, "
        f"SSIM(hi vs cubic-up lo)={cmp_['ssim_hi_vs_cubic_up_lo']:.4f}, "
        f"SSIM(lo vs downsampled hi)={cmp_['ssim_lo_vs_downsampled_hi']:.4f}, "
        f"SIFT hi/up={sift_hi}/{sift_up}, "
        f"Laplacian hi/up={cmp_['laplacian_hi']:.1f}/{cmp_['laplacian_upscaled_lo']:.1f}, "
        f"HF hi/up={cmp_['hf_hi']:.4f}/{cmp_['hf_upscaled_lo']:.4f}"
    )


def save_800_vs_1200(parcel_id: str, images: dict[int, np.ndarray], dest: Path) -> None:
    if 800 not in images or 1200 not in images:
        return
    up = resize_to(images[800], 1200, cv2.INTER_LINEAR)
    actual = images[1200]
    chip_up = geo_chip(up, 0.35, 0.30, 0.65, 0.60)
    chip_hi = geo_chip(actual, 0.35, 0.30, 0.65, 0.60)
    cell, header = 420, 48
    sheet = Image.new("RGB", (cell * 2, cell + header), (12, 12, 12))
    draw = ImageDraw.Draw(sheet)
    font = _font(15)
    draw.text((8, 8), f"{parcel_id} — AGS 800 bilinear-upscaled to 1200  vs  AGS-requested 1200", fill=(240, 240, 240), font=font)
    sheet.paste(letterbox(bgr_to_pil(chip_up), cell), (0, header))
    sheet.paste(letterbox(bgr_to_pil(chip_hi), cell), (cell, header))
    draw.text((12, header + 8), "800→1200 upscale", fill=(255, 220, 80), font=font)
    draw.text((cell + 12, header + 8), "AGS 1200", fill=(80, 255, 140), font=font)
    dest.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(dest, quality=92)


def main() -> int:
    meta = json.loads((OUT / "imageserver_metadata.json").read_text())
    dataset = json.loads((ROOT / "data/gis/carlswald_north_corrected_001.json").read_text())
    comparisons = OUT / "comparisons"
    table = []
    parcel_summaries = []
    sheets = []

    for stand_id in ("stand_34", "stand_36", "stand_677"):
        folder = OUT / stand_id
        req = json.loads((folder / "requests.json").read_text())
        parcel = req["parcel"]
        square = parcel["request_bbox"]
        rect = parcel["padded_rect"]
        native_px = square["side_m"] / NATIVE_PIXEL_SIZE_M
        cx = (square["xmin"] + square["xmax"]) / 2
        cy = (square["ymin"] + square["ymax"]) / 2
        ident = identify_3857(cx, cy)
        parcel["identify"] = ident
        req["parcel"] = parcel
        (folder / "requests.json").write_text(json.dumps(req, indent=2, default=str), encoding="utf-8")

        images = {}
        metrics = {}
        for rec in req["requests"]:
            if not rec.get("ok"):
                continue
            size = rec["requested_dimensions"][0]
            path = folder / f"{size}.jpg"
            bgr = load_bgr(path)
            images[size] = bgr
            m = image_metrics(bgr)
            m["sift_keypoints_uncapped"] = uncapped_sift_count(to_gray(bgr))
            metrics[size] = m

        pairs = extra_pairs(images)
        (folder / "metrics.json").write_text(
            json.dumps({"metrics": {str(k): v for k, v in metrics.items()}, "pairs": pairs}, indent=2),
            encoding="utf-8",
        )

        wins = CHIP_WINDOWS[stand_id]
        save_chip_sheet(stand_id, "roof window (same geographic fraction)", {s: geo_chip(images[s], *wins["roof"]) for s in images}, comparisons / f"{stand_id}_roof_chips.jpg")
        save_chip_sheet(stand_id, "pool window (same geographic fraction)", {s: geo_chip(images[s], *wins["pool"]) for s in images}, comparisons / f"{stand_id}_pool_chips.jpg")
        save_chip_sheet(stand_id, "driveway window (same geographic fraction)", {s: geo_chip(images[s], *wins["driveway"]) for s in images}, comparisons / f"{stand_id}_driveway_chips.jpg")
        save_upsample_sheet(stand_id, images, comparisons / f"{stand_id}_400_upscale_vs_1600.jpg")
        save_800_vs_1200(stand_id, images, comparisons / f"{stand_id}_800_upscale_vs_1200.jpg")

        plateau_candidates = [s for s in sorted(images) if s >= native_px * 0.95]
        plateau = min(plateau_candidates) if plateau_candidates else max(images)
        current = load_bgr(folder / "current_pie_crop.jpg")
        overlap = crop_ags_to_padded_rect(images[plateau], square, rect)
        current_cmp = compare_current_vs_ags(current, overlap)
        (folder / "current_vs_ags.json").write_text(json.dumps(current_cmp, indent=2), encoding="utf-8")

        sizes = sorted(images)
        for size in sizes:
            rec = next(r for r in req["requests"] if r.get("requested_dimensions") == [size, size])
            m = metrics[size]
            roof, pool, drive = VISUAL_SCORES[stand_id][size]
            prev = max([s for s in sizes if s < size], default=None)
            ssim_prev = None
            if prev is not None:
                ssim_prev = pairs.get(f"{size}_vs_upscaled_{prev}", {}).get("ssim_hi_vs_bilinear_up_lo")
            table.append(
                {
                    "parcel": stand_id,
                    "requested_px": size,
                    "metres_per_px": rec["metres_per_output_pixel"],
                    "file_size": rec["file_size_bytes"],
                    "keypoints": m["sift_keypoints_uncapped"],
                    "edge_detail": round(m["edge_density"], 4),
                    "pool_usefulness": pool,
                    "roof_usefulness": roof,
                    "driveway_usefulness": drive,
                    "native_detail_gained": gained_label(size, native_px, ssim_prev),
                    "http_status": rec["http_status"],
                    "returned": rec["returned_dimensions"],
                    "runtime_ms": rec["runtime_ms_image"],
                    "flag": rec.get("flag"),
                }
            )

        native_name = (ident.get("native_rasters") or [{}])[0].get("Name")
        parcel_summaries.append(
            {
                "id": stand_id,
                "estate": parcel.get("estate"),
                "area_sqm": parcel.get("area_sqm"),
                "address": parcel.get("address"),
                "side_m": square["side_m"],
                "native_px": native_px,
                "plateau_px": plateau,
                "identify": ident,
                "native_raster": native_name,
                "current_crop": {
                    "size": list(Image.open(folder / "current_pie_crop.jpg").size),
                    "m_per_px": DEFAULT_TILE_METRES / DEFAULT_PIXELS,
                    "source": parcel.get("existing_crop") and "production_carlswald_crop" or "simulated_280m_1400px_pipeline",
                },
                "current_vs_ags": current_cmp,
                "pairs": pairs,
                "requests": req["requests"],
            }
        )
        for name in (
            f"{stand_id}_resolutions.jpg",
            f"{stand_id}_roof_chips.jpg",
            f"{stand_id}_pool_chips.jpg",
            f"{stand_id}_driveway_chips.jpg",
            f"{stand_id}_400_upscale_vs_1600.jpg",
            f"{stand_id}_800_upscale_vs_1200.jpg",
            f"{stand_id}_current_vs_ags.jpg",
        ):
            sheets.append(f"data/investigations/ags_resolution/comparisons/{name}")

    strategy = tile_strategy(dataset["extent"], 2.5, 350_000)
    rec_px = "native-matched (bbox_side_m / 0.15); empirically 800 px for ~90 m envelopes, 1200 px for ~135–160 m envelopes"
    success = (
        "PARTIALLY — PIE is not using full native 15 cm AGS detail. Current 280 m / 1400 px tiles sample at 0.20 m/px "
        "(1.33× coarser than 0.15 m/px). Direct AGS requests at native sampling recover extra roof-edge, pool-outline, "
        "solar-panel and paving detail. Requests past native (1600–3200 for these bboxes) add interpolation only. "
        "Fix: retile the cache at 0.15 m/px. Do not revert to per-parcel live AGS, and do not default parcel exports to 1600+."
    )

    write_report(
        meta=meta,
        parcels=parcel_summaries,
        table=table,
        strategy=strategy,
        sheets=sheets,
        success=success,
        rec_px=rec_px,
    )
    print("Updated report.md")
    return 0


def write_report(*, meta, parcels, table, strategy, sheets, success, rec_px) -> None:
    svc = meta["service"]
    lines: list[str] = []
    a = lines.append
    a("# CoJ AGS parcel resolution investigation")
    a("")
    a("Investigation only. Matching, CLIP, scoring, segmentation, ranking, and production tile/crop settings were **not** changed.")
    a("")
    a("## Success question")
    a("")
    a(success)
    a("")
    a("## Service metadata")
    a("")
    a(f"- Service: `{svc.get('name')}` ({YEAR} ImageServer)")
    a(f"- Native pixel size (EPSG:3857): **{svc.get('pixelSizeX')} × {svc.get('pixelSizeY')} m** — catalog rasters named `2023_COJ_RGB_15cm_*`")
    a(f"- Advertised maxima: height **{svc.get('maxImageHeight')}**, width **{svc.get('maxImageWidth')}**. All tested sizes including 2400 and 3200 are within limits; every request returned HTTP 200 `image/jpeg` at the exact requested dimensions.")
    a(f"- Default resampling: `{svc.get('defaultResamplingMethod')}`; every request used `{INTERPOLATION}`")
    a(f"- Default JPEG quality: {svc.get('defaultCompressionQuality')}")
    a(f"- keyProperties: LowCellSize={meta['keyProperties'].get('LowCellSize')}, HighCellSize={meta['keyProperties'].get('HighCellSize')}, MaxCellSize={meta['keyProperties'].get('MaxCellSize')}")
    a("- Pyramid / LOD: no `tileInfo` table on the ImageServer. Catalog identify (EPSG:3857) returns the 15 cm source raster plus mosaic overviews `Ov_i02_L03`…`L06` at LowPS ≈ 3.6, 10.8, 32.4, 97.2 m. Parcel requests in this test are 0.03–0.62 m/px, so they hit the **15 cm dataset**, not those coarse overviews. Source rasters also advertise HighPS up to ~1.2 m (internal pyramid).")
    a("- Identify must use `sr=3857` (WGS84 identify returned an error).")
    a("")
    a("## Method")
    a("")
    a("- One fixed bbox per parcel: production padded AABB (polygon + 18 m via `PADDING_METRES/111320`), then centre-expanded to a **square Web Mercator envelope**. AGS `exportImage` with N×N already squares the short axis; locking the square keeps coverage and pixel isotropy identical at every size.")
    a("- Same year (2023), CRS (EPSG:3857), interpolation (`RSP_BilinearInterpolation`).")
    a("- Sizes requested **directly from AGS** (`f=image`): 256, 400, 800, 1200, 1600, 2400, 3200. Files are raw response bytes, not locally resized copies. A parallel `f=json` call recorded returned width/height/extent.")
    a("- Detail tests (not “looks sharper”): Canny edge density, Sobel gradient, connected edge components, uncapped SIFT, ORB, 16×16 spatial occupancy, Laplacian variance, FFT high-frequency energy, SSIM of downsample/upscale pairs (bilinear and cubic).")
    a("- Native request size = `bbox_side_m / 0.15`. Finer than 0.15 m/px is flagged `UPSCALED — NO EXPECTED ADDITIONAL SOURCE DETAIL`.")
    a("- Current PIE crop: Carlswald Stand 677 uses the **production** tile-cache crop. Blue Hills 34/36 have no production cache in this repo; crops were generated with the **same algorithm** (280 m tiles @ 1400 px ≈ 0.20 m/px, 18 m pad).")
    a("")
    a("## Parcels")
    a("")
    for p in parcels:
        native = (p["identify"].get("native_rasters") or [{}])[0]
        a(
            f"- **{p['id']}** — {p['estate']}, {p.get('area_sqm')} m²"
            + (f", {p['address']}" if p.get("address") else "")
            + f". Square bbox **{p['side_m']:.1f} m**. Native-matched request **{p['native_px']:.0f} px**. "
            f"Source raster `{native.get('Name')}` LowPS={native.get('LowPS')} HighPS={native.get('HighPS')}."
        )
    a("")
    a("Carlswald North uses **Stand 677** (SUMMERSET EXT.13): clearly visible rectangular pool. Stands 420 and 408 also have pools; 677 is the first preferred listed option.")
    a("")
    a("## Results table")
    a("")
    a("| parcel | requested px | metres/px | file size | keypoints | edge detail | pool usefulness | roof usefulness | driveway usefulness | native detail gained? |")
    a("|---|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for row in table:
        a(
            f"| {row['parcel']} | {row['requested_px']} | {row['metres_per_px']:.4f} | {row['file_size']} | "
            f"{row['keypoints']} | {row['edge_detail']} | {row['pool_usefulness']} | "
            f"{row['roof_usefulness']} | {row['driveway_usefulness']} | {row['native_detail_gained']} |"
        )
    a("")
    a("Usefulness: 0 unusable, 1 barely visible, 2 usable, 3 clear, 4 highly detailed — from 1:1 geographic chips (roof / pool / driveway), not from file size. Edge density is Canny mean and **falls** as images are oversampled (gradients spread); do not treat a lower edge-density number as “less detail” across different output sizes. Keypoints are **uncapped SIFT**. Compare keypoints across sizes using the upscale pairs below, not raw counts.")
    a("")
    a("## Pixel–ground vs native 0.15 m")
    a("")
    a("| parcel | bbox side (m) | native px (side/0.15) | 400 m/px | 800 m/px | 1200 m/px | 1600 m/px | first UPSCALED size |")
    a("|---|---:|---:|---:|---:|---:|---:|---|")
    for p in parcels:
        recs = {r["requested_dimensions"][0]: r for r in p["requests"] if r.get("ok")}
        first_up = next((s for s in (256, 400, 800, 1200, 1600, 2400, 3200) if recs[s].get("flag")), "—")
        a(
            f"| {p['id']} | {p['side_m']:.1f} | {p['native_px']:.0f} | "
            f"{recs[400]['metres_per_output_pixel']:.4f} | {recs[800]['metres_per_output_pixel']:.4f} | "
            f"{recs[1200]['metres_per_output_pixel']:.4f} | {recs[1600]['metres_per_output_pixel']:.4f} | {first_up} |"
        )
    a("")
    a("## Detail vs interpolation")
    a("")
    a("Diagnostic: upsample the lower AGS image to the higher size (bilinear, matching AGS) and compare to the actual higher AGS request. If the higher request is interpolated from the same source pixels, SSIM is very high (~0.97+) and extra SIFT/HF is small. If it contains new source samples, SSIM drops and Laplacian / HF / SIFT rise.")
    a("")
    for p in parcels:
        a(f"### {p['id']}")
        a("")
        a(f"- Native-matched size: **{p['native_px']:.0f} px** ({p['side_m']:.1f} m / 0.15 m).")
        a(f"- Smallest tested size that reaches native: **{p['plateau_px']} px**.")
        a(
            f"- Current PIE crop: {p['current_crop']['size'][0]}×{p['current_crop']['size'][1]} at "
            f"**{p['current_crop']['m_per_px']:.3f} m/px** ({p['current_crop']['source']})."
        )
        a("")
        pairs = p["pairs"]
        for key in (
            "400_vs_upscaled_256",
            "800_vs_upscaled_400",
            "1200_vs_upscaled_800",
            "1600_vs_upscaled_800",
            "1600_vs_upscaled_1200",
            "2400_vs_upscaled_1600",
            "3200_vs_upscaled_1600",
        ):
            if key in pairs:
                a(f"- `{key}`: {fmt_pair(pairs[key])}.")
        cmp_ = p["current_vs_ags"]
        a("")
        a(
            f"- Current crop vs AGS overlap at {p['plateau_px']} px (same padded rectangle): "
            f"SSIM(current vs AGS downsampled to current)={cmp_['ssim_current_vs_ags_downsampled_to_current']:.4f}, "
            f"SSIM(AGS vs current upscaled)={cmp_['ssim_ags_vs_current_upscaled']:.4f}, "
            f"SIFT current/AGS-overlap={cmp_['sift_current']}/{cmp_['sift_ags_overlap']}, "
            f"Laplacian current/AGS-at-current-size={cmp_['laplacian_current']:.1f}/{cmp_['laplacian_ags_at_current_size']:.1f}."
        )
        a("")

    a("### How to read the numbers")
    a("")
    a("- **400 → 800** is the large genuine-detail step on all three parcels (SSIM of 800 vs upscaled-400 is ~0.73–0.90, not 0.97). Roof ridges, pool coping and solar-panel grids become usable.")
    a("- **800 → 1200** still adds source samples on Blue Hills (native ~910–1060 px; 800 is 0.17–0.20 m/px). SSIM ~0.94–0.96. Carlswald 677 native is ~605 px, so 800 is already past native (SSIM 1200 vs 800 ~0.97).")
    a("- **1200 → 1600 → 2400 → 3200**: SSIM ≥ 0.97 vs bilinear upscale. 1:1 chips look softer, not sharper. This is interpolation plus JPEG. Flag: **UPSCALED — NO EXPECTED ADDITIONAL SOURCE DETAIL**.")
    a("")
    a("## Object-specific notes")
    a("")
    a("### Stand 34 (Blue Hills EXT.8, pool + tiled roof + solar + court)")
    a("")
    a("- Roof: 256 barely a mass; 400 usable outline; 800 ridges/hips and 8 solar panels clear; 1200 tile rows and panel gaps; 1600+ no new geometry.")
    a("- Pool: rectangular courtyard pool. Coping and steps become clear at 800–1200. 2400+ softens the rim.")
    a("- Driveway: tan paving vs lawn. Boundary usable at 400, brick/paving texture at 1200. Oversized requests do not add joints.")
    a("")
    a("### Stand 36 (Blue Hills EXT.8, light roof, dark pool, long driveway)")
    a("")
    a("- 800 px is **0.199 m/px — the same sampling as the current 280 m / 1400 px tile cache**. 1200 px (0.133 m/px) is the first tested size at/finer than native and is where roof edges, the dark pool rectangle, and a thin utility line become crisp.")
    a("- 400→1600 upscale sheet: mow lines / canopy texture exist in AGS 1600 and are absent from upscaled 400 — real source detail, but most of that gain is already present by 1200.")
    a("")
    a("### Stand 677 (Carlswald North / SUMMERSET EXT.13, rectangular pool)")
    a("")
    a("- Production crop is 453×430 @ 0.20 m/px. Direct AGS 400 is 0.227 m/px (slightly worse). Direct AGS 800 is 0.113 m/px (past native 0.15).")
    a("- Pool contour, parapet roof edges, parked cars, and neighbour solar-panel grid are materially clearer on native-matched AGS than on the production crop. Individual paving stones still do not resolve — 15 cm imagery cannot provide that.")
    a("")
    a("## Current PIE crop vs direct AGS")
    a("")
    a("**C — Direct per-parcel AGS can retrieve more native detail than the cached tiles, because the tiles are sampled coarser than source. Do not switch to live per-parcel AGS; raise tile sampling to native 0.15 m/px and keep local crops.**")
    a("")
    a("This is not outcome A (tiles do **not** already preserve 15 cm). It is also not a 2–3× collapse: current tiles are 0.20 vs 0.15 m/px (**1.33× coarser linearly, 1.78× fewer samples per m²**). That gap is visible on roof hips, pool coping, solar-panel splits and paving/lawn boundaries. It is the cache that throws detail away, not AGS refusing 15 cm.")
    a("")
    a("Blue Hills 34/36 comparison crops were generated with the production algorithm (no Blue Hills cache in this repo). Carlswald 677 uses the real production crop from `carlswald_north_corrected_001`.")
    a("")
    a("## Recommended acquisition (not applied)")
    a("")
    a(f"- `recommended_ags_parcel_resolution`: **{rec_px}**")
    a("- `recommended_metres_per_pixel`: **0.15**")
    a("")
    a("Empirically for these bboxes:")
    a("")
    a("- 256 / 400 px: insufficient for roof/pool/driveway fingerprinting")
    a("- 800 px: major improvement; reaches native on ~90 m Carlswald envelopes; still ~0.17–0.20 m/px on larger Blue Hills envelopes")
    a("- 1200 px: reaches native on Blue Hills 34/36 envelopes")
    a("- 1600 px: little additional source information")
    a("- 2400 / 3200: interpolation only (visually softer)")
    a("")
    a("Do **not** default PIE to 1600×1600 parcel exports. That wastes time on oversized JPEG encode (3–6 s vs ~1–2 s at 800–1200) with no extra native samples once `metres/px < 0.15`.")
    a("")
    a("Production `DEFAULT_TILE_METRES=280` / `DEFAULT_PIXELS=1400` were not modified.")
    a("")
    a("## If tile cache is the limit")
    a("")
    a("Do **not** revert to one AGS request per parcel (the 337/786 pattern). Keep a tiled cache at native 0.15 m/px, crop locally with the existing 18 m pad.")
    a("")
    a(f"Carlswald North padded estate footprint ≈ {strategy['estate_mercator_m']['width']:.0f} × {strategy['estate_mercator_m']['height']:.0f} m.")
    a("")
    a("| tile m | tile px | m/px | tiles | cache MB est. | fetch s est. | native? |")
    a("|---:|---:|---:|---:|---:|---:|---|")
    for opt in strategy["options"]:
        a(
            f"| {opt['tile_metres']:.0f} | {opt['tile_pixels']} | {opt['metres_per_pixel']:.3f} | "
            f"{opt['tiles']} | {opt['cache_size_mb_est']} | {opt['fetch_time_s_est']} | "
            f"{'yes' if opt['native'] else 'no'} |"
        )
    a("")
    a(strategy["recommended"])
    a("")
    a("**Best tradeoff: 210 m tiles at 1400 px (0.15 m/px).** Same per-tile JPEG class as today, more tiles, native ground sampling, local crops inherit 15 cm. Alternative with fewer tiles: keep 280 m tiles but request **1867 px** (native; larger files, still well under the 4100 height cap).")
    a("")
    a("Expected effect on parcel crops: a ~30 m stand + 18 m pad (~66 m) would go from ~330 px today to ~440 px at native — not a new sensor, but the missing third of linear samples on roof edges and pool rims.")
    a("")
    a("## Comparison sheets")
    a("")
    for rel in sheets:
        a(f"- `{rel}`")
    a("")
    a("## Request logs")
    a("")
    a("Raw AGS JPEGs and per-request HTTP/bbox/runtime JSON:")
    a("")
    a("- `data/investigations/ags_resolution/stand_34/` — `256.jpg` … `3200.jpg`, `requests.json`, `metrics.json`, `current_pie_crop.jpg`, `current_vs_ags.json`")
    a("- `data/investigations/ags_resolution/stand_36/` — same")
    a("- `data/investigations/ags_resolution/stand_677/` — same")
    a("- `data/investigations/ags_resolution/imageserver_metadata.json`")
    a("")
    a("Reproduce: `python3 scripts/investigate_ags_resolution.py` then `python3 scripts/finalize_ags_resolution_report.py`.")
    a("")

    (OUT / "report.md").write_text("\n".join(lines), encoding="utf-8")
    slim = {
        "success_answer": success,
        "recommended_ags_parcel_resolution": rec_px,
        "recommended_metres_per_pixel": 0.15,
        "table": table,
        "parcels": [
            {k: v for k, v in p.items() if k not in {"pairs", "requests"}}
            for p in parcels
        ],
        "tile_strategy": strategy,
    }
    (OUT / "summary.json").write_text(json.dumps(slim, indent=2, default=str), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
