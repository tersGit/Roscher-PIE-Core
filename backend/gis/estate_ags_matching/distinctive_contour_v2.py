"""Distinctive Contour v2 — listing-pool geometry diagnostic.

Reporting only. Compares listing image → raw segmentation mask → raw contour
→ simplified/regularised contour → official 64-point scoring contour.

Does not enter ranking. Does not modify Hybrid v1, Scoring v2, OS v1, native15,
FastSAM/SAM2, viewpoint gates, or Pool Gate.
"""

from __future__ import annotations

import io
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from backend.gis.estate_ags_matching.os_scoring_v2 import contour_descriptors
from backend.gis.estate_ags_matching.pool_geometry import NORMALIZED_POINTS, _resample_contour

REPO_ROOT = Path(__file__).resolve().parents[3]
USED_IN_RANKING = False
MAJOR_INDENT = 0.08
MINOR_INDENT = 0.04


def _cv2():
    import cv2

    return cv2


def _font(size: int = 13) -> ImageFont.ImageFont:
    path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    return ImageFont.truetype(str(path), size) if path.is_file() else ImageFont.load_default()


def mask_components(mask: np.ndarray) -> list[np.ndarray]:
    cv2 = _cv2()
    binary = (np.asarray(mask) > 0).astype(np.uint8) * 255
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    contours = [c for c in contours if cv2.contourArea(c) >= 40]
    contours.sort(key=lambda c: -float(cv2.contourArea(c)))
    return contours


def simplify_contour(contour: np.ndarray, eps_frac: float = 0.02) -> np.ndarray:
    cv2 = _cv2()
    peri = max(float(cv2.arcLength(contour, True)), 1.0)
    approx = cv2.approxPolyDP(contour, eps_frac * peri, True)
    if len(approx) < 5:
        return contour
    return approx


def _n_directional_changes(xy: Sequence[Sequence[float]], threshold_deg: float = 40.0) -> int:
    pts = np.asarray(xy, dtype=np.float64)
    if pts.ndim != 2 or len(pts) < 5:
        return 0
    prev = np.roll(pts, 1, axis=0)
    nxt = np.roll(pts, -1, axis=0)
    v1 = pts - prev
    v2 = nxt - pts
    ang1 = np.arctan2(v1[:, 1], v1[:, 0])
    ang2 = np.arctan2(v2[:, 1], v2[:, 0])
    turn = (ang2 - ang1 + math.pi) % (2.0 * math.pi) - math.pi
    return int(np.sum(np.abs(turn) > math.radians(threshold_deg)))


def _limb_extents(xy: Sequence[Sequence[float]] | None) -> dict[str, float] | None:
    if not xy:
        return None
    pts = np.asarray(xy, dtype=np.float64)
    if pts.ndim != 2 or len(pts) < 5:
        return None
    return {
        "plus_x": round(float(max(pts[:, 0].max(), 0.0)), 4),
        "minus_x": round(float(max(-pts[:, 0].min(), 0.0)), 4),
        "plus_y": round(float(max(pts[:, 1].max(), 0.0)), 4),
        "minus_y": round(float(max(-pts[:, 1].min(), 0.0)), 4),
    }


def stage_metrics(points: Sequence[Sequence[float]] | np.ndarray | None) -> dict[str, Any] | None:
    desc = contour_descriptors(points)
    if not desc:
        return None
    xy = desc.get("norm_xy") or []
    return {
        "n_points_in": 0 if points is None else int(len(np.asarray(points))),
        "n_major_indents": desc.get("n_major_indents"),
        "max_indent": desc.get("max_indent"),
        "solidity": desc.get("solidity"),
        "circularity": desc.get("circularity"),
        "elongation": desc.get("elongation"),
        "n_corners": desc.get("n_corners"),
        "sharp_frac": desc.get("sharp_frac"),
        "n_major_directional_changes": _n_directional_changes(xy),
        "limb_extents": _limb_extents(xy),
        "norm_xy": [[round(float(x), 4), round(float(y), 4)] for x, y in xy],
    }


def image_xy(contour: np.ndarray, width: int, height: int) -> list[list[float]]:
    pts = np.asarray(contour).reshape(-1, 2)
    return [
        [round(float(x) / max(width - 1, 1), 4), round(float(y) / max(height - 1, 1), 4)]
        for x, y in pts
    ]


def classify_stage_loss(
    raw: Mapping[str, Any] | None,
    simplified: Mapping[str, Any] | None,
    scoring: Mapping[str, Any] | None,
    *,
    n_mask_components: int,
    secondary_present: bool,
) -> dict[str, Any]:
    lost: list[str] = []
    notes: list[str] = []
    raw = dict(raw or {})
    scoring = dict(scoring or {})
    raw_ind = int(raw.get("n_major_indents") or 0)
    score_ind = int(scoring.get("n_major_indents") or 0)
    raw_max = float(raw.get("max_indent") or 0.0)
    score_max = float(scoring.get("max_indent") or 0.0)
    raw_sol = float(raw.get("solidity") or 1.0)
    score_sol = float(scoring.get("solidity") or 1.0)
    raw_dir = int(raw.get("n_major_directional_changes") or 0)
    score_dir = int(scoring.get("n_major_directional_changes") or 0)
    raw_el = float(raw.get("elongation") or 1.0)
    score_el = float(scoring.get("elongation") or 1.0)

    if raw_ind >= 1 and score_ind == 0:
        lost.append("major_indents")
    elif raw_ind > score_ind:
        lost.append("some_major_indents")
    if raw_max >= MINOR_INDENT and score_max < MINOR_INDENT:
        lost.append("concavities_kinks")
    if raw_sol <= 0.90 and score_sol >= 0.95:
        lost.append("freeform_collapsed_to_convex")
    if raw_dir >= 8 and score_dir <= max(3, raw_dir // 3):
        lost.append("directional_changes")
    if abs(raw_el - score_el) >= 0.8:
        lost.append("aspect_asymmetric_ends")
    if n_mask_components >= 2 or secondary_present:
        lost.append("spa_or_secondary_water_body_not_in_official_scoring_contour")
        notes.append("dominant-only scoring contour; secondary component preserved only in diagnostic")

    if not scoring:
        verdict = "COLLAPSED"
        lost.append("no_scoring_contour")
    elif not lost and abs(raw_sol - score_sol) <= 0.04 and raw_ind == score_ind:
        verdict = "GEOMETRY PRESERVED"
    elif (
        "major_indents" in lost
        and "freeform_collapsed_to_convex" in lost
        and score_ind == 0
        and score_sol >= 0.94
    ):
        verdict = "COLLAPSED"
    elif "major_indents" in lost and score_ind == 0 and raw_ind >= 2:
        verdict = "COLLAPSED"
    elif lost:
        verdict = "PARTIALLY LOST"
    else:
        verdict = "GEOMETRY PRESERVED"

    return {
        "verdict": verdict,
        "features_lost": lost,
        "notes": notes,
        "raw_vs_scoring": {
            "n_major_indents": [raw_ind, score_ind],
            "max_indent": [round(raw_max, 4), round(score_max, 4)],
            "solidity": [round(raw_sol, 4), round(score_sol, 4)],
            "n_major_directional_changes": [raw_dir, score_dir],
            "elongation": [round(raw_el, 4), round(score_el, 4)],
        },
    }


def analyze_mask_contour_pipeline(
    mask: np.ndarray | None,
    *,
    hybrid_contour_image: Sequence[Sequence[float]] | None = None,
    secondary_mask: np.ndarray | None = None,
) -> dict[str, Any]:
    if mask is None:
        return {
            "n_mask_components": 0,
            "verdict": "COLLAPSED",
            "features_lost": ["no_raw_mask"],
            "used_in_ranking": USED_IN_RANKING,
        }
    height, width = mask.shape[:2]
    comps = mask_components(mask)
    raw = None if not comps else comps[0]
    simplified = None if raw is None else simplify_contour(raw)
    resampled = None if raw is None else _resample_contour(raw, NORMALIZED_POINTS)
    raw_xy = None if raw is None else image_xy(raw, width, height)
    simple_xy = None if simplified is None else image_xy(simplified, width, height)
    resampled_xy = None if resampled is None else image_xy(resampled, width, height)
    scoring_src = hybrid_contour_image if hybrid_contour_image and len(hybrid_contour_image) >= 5 else resampled_xy
    raw_m = stage_metrics(raw_xy)
    simple_m = stage_metrics(simple_xy)
    resampled_m = stage_metrics(resampled_xy)
    scoring_m = stage_metrics(scoring_src)
    secondary_comps = mask_components(secondary_mask) if secondary_mask is not None else []
    extra_from_same_mask = comps[1:] if len(comps) > 1 else []
    loss = classify_stage_loss(
        raw_m,
        simple_m,
        scoring_m,
        n_mask_components=len(comps) + len(secondary_comps),
        secondary_present=bool(secondary_comps or extra_from_same_mask),
    )
    return {
        "image_wh": [int(width), int(height)],
        "n_mask_components": len(comps),
        "n_secondary_components": len(secondary_comps),
        "pool_spa_relationship": {
            "secondary_present": bool(secondary_comps or extra_from_same_mask),
            "same_mask_extra_blobs": len(extra_from_same_mask),
            "hybrid_secondary_mask": bool(secondary_comps),
            "merged_into_official_scoring_contour": False,
            "note": "Official scoring uses the dominant component only.",
        },
        "raw_contour": None if raw_m is None else {k: v for k, v in raw_m.items() if k != "norm_xy"} | {
            "n_raw_vertices": int(len(raw_xy or [])),
        },
        "simplified_contour": None if simple_m is None else {k: v for k, v in simple_m.items() if k != "norm_xy"} | {
            "n_simplified_vertices": int(len(simple_xy or [])),
        },
        "resampled_64": None if resampled_m is None else {k: v for k, v in resampled_m.items() if k != "norm_xy"},
        "official_scoring_contour": None if scoring_m is None else {
            **{k: v for k, v in scoring_m.items() if k != "norm_xy"},
            "normalized_contour": scoring_m.get("norm_xy"),
            "normalized_contour_point_count": len(scoring_m.get("norm_xy") or []),
        },
        "loss": loss,
        "verdict": loss["verdict"],
        "used_in_ranking": USED_IN_RANKING,
        "_draw": {
            "raw_xy": raw_xy,
            "simple_xy": simple_xy,
            "resampled_xy": resampled_xy,
            "scoring_xy": scoring_src,
            "scoring_norm": None if scoring_m is None else scoring_m.get("norm_xy"),
            "secondary_xy": [] if not secondary_comps else image_xy(secondary_comps[0], width, height),
            "extra_xy": [] if not extra_from_same_mask else image_xy(extra_from_same_mask[0], width, height),
        },
    }


def _overlay(image: Image.Image, contour_xy: Sequence[Sequence[float]] | None, color: tuple[int, int, int], width: int = 3) -> Image.Image:
    out = image.convert("RGB")
    if not contour_xy or len(contour_xy) < 3:
        return out
    draw = ImageDraw.Draw(out)
    w, h = out.size
    pts = [(int(float(x) * (w - 1)), int(float(y) * (h - 1))) for x, y in contour_xy]
    draw.line(pts + [pts[0]], fill=color, width=width)
    return out


def _mask_overlay(image: Image.Image, mask: np.ndarray | None, color: tuple[int, int, int] = (40, 180, 255)) -> Image.Image:
    out = image.convert("RGBA")
    if mask is None:
        return out.convert("RGB")
    resized = Image.fromarray((np.asarray(mask) > 0).astype(np.uint8) * 160).resize(out.size, Image.NEAREST)
    tint = Image.new("RGBA", out.size, color + (0,))
    alpha = resized
    tint.putalpha(alpha)
    return Image.alpha_composite(out, tint).convert("RGB")


def _norm_canvas(xy: Sequence[Sequence[float]] | None, title: str, color: tuple[int, int, int], size: int = 240) -> Image.Image:
    canvas = Image.new("RGB", (size, size), (16, 16, 16))
    draw = ImageDraw.Draw(canvas)
    draw.text((8, 6), title, fill=(220, 220, 220), font=_font(12))
    draw.rectangle((6, 22, size - 7, size - 7), outline=(50, 50, 50))
    if not xy or len(xy) < 3:
        draw.text((16, size // 2), "no contour", fill=(150, 150, 150), font=_font(13))
        return canvas
    pts = np.asarray(xy, dtype=np.float64)
    if float(np.nanmax(np.abs(pts))) <= 1.6:
        mapped = (pts + 1.05) / 2.10
    else:
        mapped = pts
        mapped = (mapped - mapped.min(axis=0)) / np.maximum(mapped.max(axis=0) - mapped.min(axis=0), 1e-6)
    margin = 28
    usable = size - 2 * margin
    xy_px = mapped * usable + margin
    poly = [(int(x), int(y)) for x, y in xy_px]
    draw.polygon(poly, outline=color)
    return canvas


def draw_frame_proof(
    media_id: str,
    photo: bytes,
    mask: np.ndarray | None,
    analysis: Mapping[str, Any],
    dest: Path,
) -> str:
    image = Image.open(io.BytesIO(photo)).convert("RGB")
    image.thumbnail((360, 260))
    draw = analysis.get("_draw") or {}
    orig = image.copy()
    masked = _mask_overlay(image, mask)
    raw_img = _overlay(image, draw.get("raw_xy"), (80, 220, 255))
    simple_img = _overlay(image, draw.get("simple_xy"), (255, 200, 80))
    score_img = _overlay(image, draw.get("scoring_xy"), (255, 90, 90))
    extra = draw.get("secondary_xy") or draw.get("extra_xy")
    if extra:
        score_img = _overlay(score_img, extra, (80, 255, 120), width=2)
        raw_img = _overlay(raw_img, extra, (80, 255, 120), width=2)
    cells = [
        (orig, "1 original"),
        (masked, "2 raw mask"),
        (raw_img, "3 raw contour"),
        (simple_img, "4 simplified"),
        (score_img, "5 official scoring overlay"),
        (_norm_canvas(draw.get("scoring_norm") or draw.get("scoring_xy"), "official 64-pt", (255, 90, 90)), "5b normalized"),
    ]
    gap = 8
    row_w = sum(img.size[0] for img, _ in cells) + gap * (len(cells) + 1)
    row_h = max(img.size[1] for img, _ in cells) + 44
    canvas = Image.new("RGB", (row_w, row_h + 36), (12, 12, 12))
    painter = ImageDraw.Draw(canvas)
    verdict = analysis.get("verdict") or ""
    painter.text((10, 6), f"Distinctive Contour v2  {media_id}  {verdict}  (not used in ranking)", fill=(240, 240, 240), font=_font(15))
    x = gap
    y = 32
    for img, label in cells:
        painter.text((x, y), label, fill=(200, 200, 200), font=_font(12))
        canvas.paste(img, (x, y + 16))
        x += img.size[0] + gap
    dest.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(dest, quality=90)
    try:
        return str(dest.relative_to(REPO_ROOT))
    except ValueError:
        return str(dest)


def _public_frame(analysis: Mapping[str, Any]) -> dict[str, Any]:
    return {key: val for key, val in analysis.items() if key != "_draw"}


def _overall_verdict(frames: Sequence[Mapping[str, Any]], official_id: str | None) -> dict[str, Any]:
    by_id = {str(row.get("media_id")): row for row in frames}
    official = by_id.get(str(official_id or ""))
    verdicts = [str(row.get("verdict") or "") for row in frames]
    official_verdict = None if official is None else official.get("verdict")
    reason = "see_per_frame"
    if not frames:
        overall = "COLLAPSED"
        reason = "no_useful_pool_frames"
    elif official_verdict == "COLLAPSED":
        overall = "COLLAPSED"
        reason = "official_scoring_contour_lost_raw_mask_structure"
    elif official_verdict == "PARTIALLY LOST":
        overall = "PARTIALLY LOST"
        reason = "official_scoring_contour_lost_some_distinctive_features"
    elif official_verdict == "GEOMETRY PRESERVED" and any(v == "COLLAPSED" for v in verdicts):
        overall = "PARTIALLY LOST"
        reason = "official_frame_preserved_but_other_pool_frames_collapsed_or_unused"
    elif official_verdict == "GEOMETRY PRESERVED":
        overall = "GEOMETRY PRESERVED"
        reason = "official_scoring_contour_retains_raw_mask_structure"
    elif "COLLAPSED" in verdicts and "GEOMETRY PRESERVED" not in verdicts:
        overall = "COLLAPSED"
        reason = "no_official_frame_and_extracted_contours_collapsed"
    elif "PARTIALLY LOST" in verdicts:
        overall = "PARTIALLY LOST"
        reason = "no_official_frame_partial_loss_on_extracted_contours"
    else:
        overall = verdicts[0] if verdicts else "COLLAPSED"
    return {
        "overall_verdict": overall,
        "official_frame_id": official_id,
        "official_frame_verdict": official_verdict,
        "reason": reason,
        "n_frames": len(frames),
        "verdict_counts": {
            "GEOMETRY PRESERVED": verdicts.count("GEOMETRY PRESERVED"),
            "PARTIALLY LOST": verdicts.count("PARTIALLY LOST"),
            "COLLAPSED": verdicts.count("COLLAPSED"),
        },
        "used_in_ranking": USED_IN_RANKING,
    }


def run_distinctive_contour_v2(
    photos: Mapping[str, bytes],
    photo_classes: Mapping[str, Any],
    hybrid_frames: Sequence[Any],
    *,
    official_chosen_id: str | None,
    dest: Path,
) -> dict[str, Any]:
    """Diagnostic only. hybrid_frames may be FrameGeometry objects with masks."""
    dest.mkdir(parents=True, exist_ok=True)
    scenes = dict(photo_classes.get("scenes") or {})
    pool_ids = list(photo_classes.get("useful_pool_views") or [])
    by_id = {}
    for frame in hybrid_frames or []:
        media_id = getattr(frame, "media_id", None) or (frame.get("media_id") if isinstance(frame, Mapping) else None)
        if media_id:
            by_id[str(media_id)] = frame
    wanted = []
    for media_id in pool_ids:
        if media_id not in wanted:
            wanted.append(media_id)
    for media_id, frame in by_id.items():
        viewpoint = getattr(frame, "viewpoint", None) or (frame.get("viewpoint") if isinstance(frame, Mapping) else None)
        present = getattr(frame, "pool_present", False) or (frame.get("pool_present") if isinstance(frame, Mapping) else False)
        if present and media_id not in wanted:
            wanted.append(media_id)
        if viewpoint in {"pool_overview", "pool_closeup", "elevated_exterior", "aerial_near_nadir"} and media_id not in wanted:
            wanted.append(media_id)
    if official_chosen_id and official_chosen_id not in wanted:
        wanted.insert(0, official_chosen_id)

    rows = []
    panels = []
    for media_id in wanted:
        body = photos.get(media_id)
        if not body:
            continue
        frame = by_id.get(media_id)
        mask = None if frame is None else getattr(frame, "mask", None)
        secondary = None
        hybrid_contour = None
        source = None
        viewpoint = scenes.get(media_id)
        scoring_ready = False
        if frame is not None:
            viewpoint = getattr(frame, "viewpoint", viewpoint)
            source = getattr(frame, "source", None) or (frame.get("source") if isinstance(frame, Mapping) else None)
            scoring_ready = bool(getattr(frame, "scoring_ready", False) or (frame.get("scoring_ready") if isinstance(frame, Mapping) else False))
            hybrid_contour = getattr(frame, "contour_image", None)
            if hybrid_contour is None and isinstance(frame, Mapping):
                hybrid_contour = frame.get("contour_image") or ((frame.get("dominant") or {}).get("contour_image"))
            dominant = getattr(frame, "dominant", None) if not isinstance(frame, Mapping) else frame.get("dominant")
            if hybrid_contour is None and isinstance(dominant, Mapping):
                hybrid_contour = dominant.get("contour_image")
            sec = getattr(frame, "secondary", None) if not isinstance(frame, Mapping) else frame.get("secondary")
            if isinstance(frame, Mapping):
                mask = None
        analysis = analyze_mask_contour_pipeline(
            mask,
            hybrid_contour_image=hybrid_contour,
            secondary_mask=None,
        )
        if mask is None and hybrid_contour:
            analysis["loss"]["notes"] = list(analysis.get("loss", {}).get("notes") or []) + [
                "raw_mask_unavailable_in_serialized_frame_used_hybrid_contour_only"
            ]
            if analysis.get("verdict") == "COLLAPSED" and hybrid_contour:
                scoring_m = stage_metrics(hybrid_contour)
                analysis["official_scoring_contour"] = None if scoring_m is None else {
                    **{k: v for k, v in scoring_m.items() if k != "norm_xy"},
                    "normalized_contour": scoring_m.get("norm_xy"),
                    "normalized_contour_point_count": len(scoring_m.get("norm_xy") or []),
                }
                analysis["_draw"] = {
                    "raw_xy": hybrid_contour,
                    "simple_xy": hybrid_contour,
                    "resampled_xy": hybrid_contour,
                    "scoring_xy": hybrid_contour,
                    "scoring_norm": None if scoring_m is None else scoring_m.get("norm_xy"),
                }
                analysis["verdict"] = "PARTIALLY LOST"
                analysis["loss"]["verdict"] = "PARTIALLY LOST"
                analysis["loss"]["features_lost"] = ["raw_mask_not_retained_for_this_frame"]
        panel = draw_frame_proof(media_id, body, mask, analysis, dest / f"{media_id}.jpg")
        panels.append(panel)
        public = _public_frame(analysis)
        public.update(
            {
                "media_id": media_id,
                "clip_scene": scenes.get(media_id),
                "hybrid_viewpoint": viewpoint,
                "hybrid_source": source,
                "scoring_ready": scoring_ready,
                "is_official_chosen_frame": media_id == official_chosen_id,
                "panel": panel,
            }
        )
        rows.append(public)

    overall = _overall_verdict(rows, official_chosen_id)
    payload = {
        "diagnostic": "distinctive_contour_v2",
        "used_in_ranking": USED_IN_RANKING,
        "ranking_modified": False,
        "official_chosen_id": official_chosen_id,
        "n_useful_frames": len(rows),
        "frames": rows,
        "overall": overall,
        "panels": panels,
        "note": "Diagnostic only. Official Hybrid v1 contour used for ranking was not replaced.",
    }
    (dest / "latest.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload
