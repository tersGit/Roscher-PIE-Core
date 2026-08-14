#!/usr/bin/env python3
"""Colour-independent listing pool-object diagnostic for Property24 116273255.

Based on frozen PR #8 viewpoint gates. Does not modify production ranking,
OS v1, Scoring v2, native15 crops, listing_evidence_v2 viewpoint rules, or
PR #8 extraction. Water colour is not used as matching evidence.

No stand number is an input to candidate generation, extraction, or scoring.
Rerank only if a genuinely usable pool boundary is obtained.
"""

from __future__ import annotations

import io
import json
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.gis.dataset_registry import CORRECT_CARLSWALD_NORTH
from backend.gis.estate_ags_matching.final_candidates import assess_separation
from backend.gis.estate_ags_matching.listing_evidence_v2 import (
    assemble_channels,
    clip_viewpoint_scores,
    frame_public,
    observe_listing_frame,
)
from backend.gis.estate_ags_matching.listing_pool_object import (
    observation_public,
    observe_pool_object,
    quality_gate,
    scoring_fingerprint,
)
from backend.gis.estate_ags_matching.os_scoring_v2 import (
    OS_KEYS_NO_BUILDING,
    V2_WEIGHTS_NO_BUILDING,
    contour_descriptors,
    score_v2,
    v2_object_features,
)
from backend.gis.estate_ags_matching.pool_geometry import (
    extract_pool_geometry,
    pool_geometry_similarity,
)
from backend.imagery.estate_tiles import crop_dir_for
from backend.parsers.property24 import download_images, fetch_listing
from backend.vision.clip_encoder import encode_image, mean_top_similarity
from scripts.run_carlswald_north_corrected import combined_score, parcel_mask, stand_size_support

LISTING_ID = "116273255"
LISTING_URL = "https://www.property24.com/for-sale/carlswald-north-estate/midrand/gauteng/12743/116273255"
GIS_PATH = ROOT / "data/gis" / f"{CORRECT_CARLSWALD_NORTH}.json"
CROP_DIR = crop_dir_for(CORRECT_CARLSWALD_NORTH, "native15")
SEG_DIR = ROOT / "data/investigations/object_segmentation_v1/carlswald_north/json"
OUT = ROOT / "data/investigations/property_test_116273255"
PHOTOS = OUT / "photos"


def _safe(stand: str) -> str:
    return str(stand).replace("/", "_")


def _font(size: int = 14):
    path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    return ImageFont.truetype(str(path), size) if path.is_file() else ImageFont.load_default()


def _load_seg(stand: str) -> dict:
    path = SEG_DIR / f"{_safe(stand)}.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_parcels_last_wins() -> list[dict]:
    gis = json.loads(GIS_PATH.read_text(encoding="utf-8"))
    by_safe: dict[str, dict] = {}
    for item in gis["parcels"]:
        if item.get("land_type") != "Erven":
            continue
        if item.get("class") in {"non_residential"}:
            continue
        if (item.get("area_sqm") or 0) >= 8000:
            continue
        if not item.get("geometry") or not item.get("stand_number"):
            continue
        if str(item["stand_number"]).startswith("RE/"):
            continue
        by_safe[_safe(item["stand_number"])] = item
    return list(by_safe.values())


def acquire_photos() -> tuple[list[tuple[str, bytes]], object]:
    listing = fetch_listing(LISTING_URL, LISTING_ID)
    PHOTOS.mkdir(parents=True, exist_ok=True)
    existing = {p.name: p for p in PHOTOS.glob(f"{LISTING_ID}-*.jpg")}
    if len(existing) >= len(listing.image_urls):
        photos = []
        for path in sorted(PHOTOS.glob(f"{LISTING_ID}-*.jpg")):
            photos.append((path.stem, path.read_bytes()))
        return photos, listing
    bodies = download_images(listing.image_urls)
    photos = []
    for index, body in enumerate(bodies, start=1):
        media_id = f"{LISTING_ID}-{index:03d}"
        (PHOTOS / f"{media_id}.jpg").write_bytes(body)
        photos.append((media_id, body))
    return photos, listing


def contact_sheet(photos: dict[str, bytes], frames, dest: Path) -> list[str]:
    dest.parent.mkdir(parents=True, exist_ok=True)
    useful = [
        f
        for f in frames
        if f.viewpoint in {
            "pool_overview",
            "pool_closeup",
            "ground_level_exterior",
            "elevated_exterior",
            "aerial_near_nadir",
        }
    ]
    if not useful:
        useful = [f for f in frames if f.viewpoint not in {"interior", "unusable_ambiguous"}][:12]
    cols = 4
    thumb_w, thumb_h = 420, 280
    rows = int(np.ceil(len(useful) / cols)) or 1
    sheet = Image.new("RGB", (cols * thumb_w, rows * thumb_h), (20, 20, 20))
    font = _font(16)
    ids = []
    for i, frame in enumerate(useful):
        body = photos.get(frame.media_id)
        if not body:
            continue
        ids.append(frame.media_id)
        im = Image.open(io.BytesIO(body)).convert("RGB")
        im.thumbnail((thumb_w, thumb_h - 28))
        cell = Image.new("RGB", (thumb_w, thumb_h), (30, 30, 30))
        ox = (thumb_w - im.size[0]) // 2
        oy = 28 + (thumb_h - 28 - im.size[1]) // 2
        cell.paste(im, (ox, oy))
        draw = ImageDraw.Draw(cell)
        label = f"{frame.media_id[-3:]} {frame.viewpoint}"
        draw.text((8, 6), label, fill=(240, 240, 240), font=font)
        r, c = divmod(i, cols)
        sheet.paste(cell, (c * thumb_w, r * thumb_h))
    sheet.save(dest, quality=85)
    return ids


def draw_object_panels(photos: dict[str, bytes], frozen, objects, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    font = _font(14)
    by_frozen = {f.media_id: f for f in frozen}
    chosen = []
    seen = set()
    for obs in objects:
        if obs.viewpoint in {"pool_overview", "pool_closeup", "ground_level_exterior", "elevated_exterior"}:
            chosen.append(obs)
            seen.add(obs.media_id)
    for obs in sorted(objects, key=lambda o: (-o.contour_quality, o.media_id)):
        if obs.media_id in seen:
            continue
        if obs.pool_object_detected or obs.viewpoint not in {"interior"}:
            chosen.append(obs)
            seen.add(obs.media_id)
        if len(chosen) >= 18:
            break
    for obs in chosen[:18]:
        body = photos.get(obs.media_id)
        if not body:
            continue
        image = Image.open(io.BytesIO(body)).convert("RGB")
        draw = ImageDraw.Draw(image)
        w, h = image.size
        frozen_frame = by_frozen.get(obs.media_id)
        if frozen_frame is not None:
            for comp in (frozen_frame.components or [])[:3]:
                xy = comp.get("contour_image") or []
                if len(xy) >= 3:
                    pts = [(float(x) * (w - 1), float(y) * (h - 1)) for x, y in xy]
                    draw.line(pts + [pts[0]], fill=(255, 80, 80), width=2)
        xy = obs.contour_image or []
        if len(xy) >= 3:
            pts = [(float(x) * (w - 1), float(y) * (h - 1)) for x, y in xy]
            draw.line(pts + [pts[0]], fill=(0, 220, 90), width=3)
        label = (
            f"{obs.media_id[-3:]} {obs.viewpoint} obj={int(obs.pool_object_detected)} "
            f"{obs.geometry_class} n={obs.component_count} q={obs.contour_quality:.2f} "
            f"sh={int(obs.shape_eligible)} sp={int(obs.spatial_eligible)}"
        )
        draw.rectangle([4, 4, min(w - 4, 8 + 7 * len(label)), 28], fill=(0, 0, 0))
        draw.text((8, 8), label, fill=(250, 250, 250), font=font)
        image.save(dest / f"{obs.media_id}.jpg", quality=80)


def compact_rank_row(row: dict, score_key: str, rank_key: str) -> dict:
    contrib = row.get("contrib") or {}
    top = sorted(contrib.items(), key=lambda item: -abs(float(item[1] or 0)))[:6]
    return {
        "rank": row.get(rank_key),
        "stand_number": row["stand_number"],
        "township": row.get("township"),
        "area_sqm": row.get("area_sqm"),
        "score": row.get(score_key),
        "os_pool_status": row.get("os_pool_status"),
        "os_pool_shape": row.get("os_pool_shape"),
        "contrib_top": top,
        "size_score": row.get("size_score"),
        "shape_v2": row.get("shape_v2"),
        "spatial_v2": row.get("spatial_v2"),
        "blob_pool_present": row.get("blob_pool_present"),
    }


def maybe_rerank(listing_fp, listing_stand_sqm: float | None) -> dict | None:
    if listing_fp is None:
        return None
    from backend.gis.estate_ags_matching.os_v1_experimental_rank import is_high_conf

    parcels = load_parcels_last_wins()
    listing_shape = contour_descriptors(listing_fp.contour_normalized or listing_fp.contour_image)
    listing_has_driveway = True
    rows = []
    bytes_by = {}
    for parcel in parcels:
        stand = str(parcel["stand_number"])
        crop_path = CROP_DIR / f"{_safe(stand)}_ags_aerial.jpg"
        if not crop_path.is_file():
            continue
        body = crop_path.read_bytes()
        bytes_by[stand] = body
        image = Image.open(io.BytesIO(body)).convert("RGB")
        mask = parcel_mask(image.size, parcel["geometry"], None)
        cand_pool = extract_pool_geometry(body, media_id=f"cand-{stand}", parcel_mask=mask)
        compared = pool_geometry_similarity(listing_fp, cand_pool)
        size_score = stand_size_support(listing_stand_sqm, parcel.get("area_sqm"))
        seg = _load_seg(stand)
        pool = seg.get("pool") or {}
        geom = pool.get("geometry") or {}
        rows.append(
            {
                "stand_number": stand,
                "township": parcel.get("township"),
                "area_sqm": parcel.get("area_sqm"),
                "size_score": size_score,
                "blob_pool_present": cand_pool.present,
                "pool_geometry_similarity": compared.get("pool_geometry_similarity"),
                "pool_house_similarity": compared.get("pool_house_similarity"),
                "contradiction": compared.get("contradiction"),
                "os_pool_status": pool.get("status"),
                "os_pool_shape": geom.get("shape"),
                "os_high_conf_pool": is_high_conf(pool),
            }
        )
    pool_ranked = sorted(
        rows,
        key=lambda row: (-(row["pool_geometry_similarity"] or -1), str(row["stand_number"])),
    )
    short_ids = {row["stand_number"] for row in pool_ranked[:40]}
    listing_vec = encode_image(
        Image.open(io.BytesIO(next(iter(bytes_by.values())))).convert("RGB")
    )
    # Exterior CLIP vs candidates uses listing exterior vectors computed by caller if needed.
    # Here aerial listing is absent; leave aerial/exterior None unless shortlisted later.
    for row in rows:
        row["aerial_similarity"] = None
        row["exterior_similarity"] = None
        row["baseline_score"] = combined_score(
            pool_geom=row["pool_geometry_similarity"],
            pool_house=row["pool_house_similarity"],
            structural=None,
            aerial=None,
            video=None,
            exterior=None,
            driveway=None,
            gis=0.5,
            stand_size=row["size_score"],
            contradiction=row["contradiction"],
        )
        feats = v2_object_features(
            listing_fp,
            _load_seg(row["stand_number"]),
            listing_shape=listing_shape,
            listing_has_driveway=listing_has_driveway,
            listing_driveway_side=None,
            include_building_coarse=False,
        )
        score, contrib, cov, _fac = score_v2(
            feats,
            aerial=None,
            exterior=None,
            stand_size=row["size_score"],
            weights=V2_WEIGHTS_NO_BUILDING,
            os_keys=OS_KEYS_NO_BUILDING,
            missing="neutral",
        )
        row["pr6_score"] = score
        row["contrib"] = contrib
        row["coverage"] = cov
        row["shape_v2"] = feats.get("shape_v2")
        row["spatial_v2"] = feats.get("spatial_v2")
    del listing_vec, short_ids  # CLIP exterior skipped: no listing aerial; keep ranking colour-free
    for key, rank_key in (("baseline_score", "baseline_rank"), ("pr6_score", "pr6_rank")):
        ordered = sorted(rows, key=lambda row: (-float(row[key] or 0.0), str(row["stand_number"])))
        for index, row in enumerate(ordered, start=1):
            row[rank_key] = index
    def _block(score_key, rank_key, name):
        ordered = sorted(rows, key=lambda row: (-float(row[score_key] or 0.0), str(row["stand_number"])))
        scores = [float(row[score_key] or 0.0) for row in ordered]
        conf = assess_separation(scores)
        return {
            "name": name,
            "n": len(ordered),
            "top1": {"stand": ordered[0]["stand_number"], "score": ordered[0][score_key]},
            "top2": {"stand": ordered[1]["stand_number"], "score": ordered[1][score_key]},
            "margin_1_2": round(float(ordered[0][score_key] or 0) - float(ordered[1][score_key] or 0), 4),
            "confidence": conf,
            "top5": [compact_rank_row(row, score_key, rank_key) for row in ordered[:5]],
            "top20": [compact_rank_row(row, score_key, rank_key) for row in ordered[:20]],
        }
    return {
        "baseline": _block("baseline_score", "baseline_rank", "frozen_production_combined_score"),
        "scoring_v2": _block("pr6_score", "pr6_rank", "pr6_scoring_v2_unchanged"),
        "n_candidates": len(rows),
        "weights": "V2_WEIGHTS_NO_BUILDING unchanged",
        "colour_used_in_score": False,
    }


def l_consistency(objects) -> dict:
    usable = [o for o in objects if o.shape_eligible and o.l_geometry]
    if len(usable) < 2:
        return {
            "n_comparable": len(usable),
            "stable_across_views": False,
            "reason": "fewer_than_two_shape_eligible_frames",
            "ids": [o.media_id for o in usable],
        }
    flags = [o.l_geometry.get("consistent_with_l_planform") for o in usable]
    arms = [o.l_geometry.get("two_dominant_arms") for o in usable]
    return {
        "n_comparable": len(usable),
        "stable_across_views": sum(1 for v in flags if v) >= 2 or sum(1 for v in arms if v) >= 2,
        "consistent_with_l_ids": [o.media_id for o in usable if o.l_geometry.get("consistent_with_l_planform")],
        "two_arm_ids": [o.media_id for o in usable if o.l_geometry.get("two_dominant_arms")],
        "ids": [o.media_id for o in usable],
    }


def write_report(payload: dict, dest: Path) -> None:
    acq = payload["acquisition"]
    gate = payload["quality_gate"]
    vp = payload["viewpoint_counts"]
    lines = [
        "# 116273255 — colour-independent pool object diagnostic (frozen PR #8 gates)",
        "",
        "Frozen and unmodified: production ranking, OS v1, Scoring v2 weights, native15 crops,",
        "PR #8 viewpoint-gating rules. Water colour is not a matching feature.",
        "No stand number entered extraction or scoring.",
        "",
        "## Phase 1 — Acquisition / viewpoint",
        "",
        f"- Total images: **{acq['images_acquired']}**",
        f"- pool_overview: **{vp.get('pool_overview', 0)}**",
        f"- pool_closeup: **{vp.get('pool_closeup', 0)}**",
        f"- ground_level_exterior: **{vp.get('ground_level_exterior', 0)}**",
        f"- elevated_exterior: **{vp.get('elevated_exterior', 0)}**",
        f"- aerial_near_nadir: **{vp.get('aerial_near_nadir', 0)}**",
        f"- interiors rejected: **{vp.get('interior', 0)}**",
        f"- unusable_ambiguous: **{vp.get('unusable_ambiguous', 0)}**",
        f"- garden_only: **{vp.get('garden_only', 0)}**",
        f"- Contact sheet: `{payload.get('contact_sheet')}`",
        "",
        "## A. Viewpoint filtering",
        "",
        f"- Interiors: {vp.get('interior', 0)}; spatial-eligible interiors: {payload['viewpoint_audit']['interior_spatial_ids'] or 'none'}",
        f"- Headshots/unusable: {payload['viewpoint_audit']['unusable_ids'] or 'none'}",
        f"- Close-ups contributing nadir scale: {payload['viewpoint_audit']['closeup_scale_ids'] or 'none'}",
        "",
        "## Object vs frozen colour-blob extraction",
        "",
        "| id | viewpoint | frozen pool | object pool | geometry class | full boundary | n_comp | q | shape | spatial | scale |",
        "|---|---|---|---|---|---|---:|---:|---|---|---|",
    ]
    for row in payload["frame_table"]:
        lines.append(
            f"| {row['media_id'][-3:]} | {row['viewpoint']} | {row['frozen_pool']} | {row['object_pool']} | "
            f"{row['geometry_class']} | {row['full_boundary']} | {row['component_count']} | {row['contour_quality']} | "
            f"{row['shape_eligible']} | {row['spatial_eligible']} | {row['scale_eligible']} |"
        )
    lcons = payload["l_consistency"]
    lines += [
        "",
        "## L-shape geometry (physical, not CLIP phrase)",
        "",
        f"- Comparable shape-eligible frames: {lcons.get('n_comparable')}",
        f"- Stable across views: **{lcons.get('stable_across_views')}**",
        f"- consistent_with_l_planform ids: {lcons.get('consistent_with_l_ids')}",
        f"- two-arm ids: {lcons.get('two_arm_ids')}",
        "",
        "## Quality gate",
        "",
        f"**Passed: {gate['passed']}** — {gate['reason']}",
        f"- usable ids: {gate.get('usable_ids')}",
        f"- chosen: {gate.get('chosen_id')} class={gate.get('chosen_class')} q={gate.get('chosen_quality')}",
        "",
        "## Ranking",
        "",
    ]
    rerank = payload.get("rerank")
    if rerank is None:
        lines.append("Gate failed. No 330-candidate rerank. Scoring v2 weights were not touched.")
    else:
        b, v = rerank["baseline"], rerank["scoring_v2"]
        lines.append(f"Baseline #1 {b['top1']} margin={b['margin_1_2']} conf={b['confidence']['level']}")
        lines.append(f"Scoring v2 #1 {v['top1']} margin={v['margin_1_2']} conf={v['confidence']['level']}")
        lines.append("Baseline Top 5: " + ", ".join(f"{r['stand_number']} {r['score']}" for r in b["top5"]))
        lines.append("Scoring v2 Top 5: " + ", ".join(f"{r['stand_number']} {r['score']}" for r in v["top5"]))
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    started = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    photos, listing = acquire_photos()
    photo_map = {mid: body for mid, body in photos}
    print(f"photos={len(photos)} stand_size={listing.stand_size_sqm}")

    frozen = []
    objects = []
    for media_id, body in photos:
        image = Image.open(io.BytesIO(body)).convert("RGB")
        scores = clip_viewpoint_scores(image)
        frozen_frame = observe_listing_frame(media_id, body, clip_scores=scores)
        frozen.append(frozen_frame)
        obj = observe_pool_object(
            media_id,
            body,
            clip_scores=scores,
            viewpoint=frozen_frame.viewpoint,
        )
        objects.append(obj)
        print(
            f"  {media_id} vp={frozen_frame.viewpoint} frozen_pool={frozen_frame.pool_detected} "
            f"obj={obj.pool_object_detected} class={obj.geometry_class} q={obj.contour_quality:.3f} "
            f"sh={obj.shape_eligible} sp={obj.spatial_eligible}"
        )

    channels = assemble_channels(frozen)
    gate = quality_gate(objects)
    listing_fp = scoring_fingerprint(objects, gate)
    print("gate", gate["passed"], gate["reason"], "chosen", gate.get("chosen_id"))

    contact_ids = contact_sheet(photo_map, frozen, OUT / "panels" / "contact_sheet.jpg")
    draw_object_panels(photo_map, frozen, objects, OUT / "panels" / "object")

    frame_table = []
    for frozen_frame, obj in zip(frozen, objects):
        if frozen_frame.viewpoint in {"interior"} and not frozen_frame.pool_detected and not obj.pool_object_detected:
            continue
        if frozen_frame.viewpoint not in {
            "pool_overview",
            "pool_closeup",
            "ground_level_exterior",
            "elevated_exterior",
            "aerial_near_nadir",
            "unusable_ambiguous",
            "garden_only",
        } and not frozen_frame.pool_detected and not obj.pool_object_detected:
            continue
        frame_table.append(
            {
                "media_id": obj.media_id,
                "viewpoint": obj.viewpoint,
                "frozen_pool": frozen_frame.pool_detected,
                "object_pool": obj.pool_object_detected,
                "geometry_class": obj.geometry_class,
                "full_boundary": obj.full_boundary_recovered,
                "partial_object": obj.partial_object,
                "component_count": obj.component_count,
                "contour_quality": obj.contour_quality,
                "edge_clip": obj.edge_clip,
                "shape_eligible": obj.shape_eligible,
                "spatial_eligible": obj.spatial_eligible,
                "scale_eligible": obj.scale_eligible,
                "frozen_quality": frozen_frame.contour_quality,
                "frozen_n": frozen_frame.n_components,
                "l_geometry": obj.l_geometry,
            }
        )

    rerank = None
    if gate["passed"]:
        print("Phase 5 — gate passed, frozen Scoring v2 on 330 candidates")
        rerank = maybe_rerank(listing_fp, listing.stand_size_sqm)
    else:
        print("Phase 5 — gate failed, no rerank")

    payload = {
        "listing_id": LISTING_ID,
        "based_on": "frozen_pr8_listing_evidence_v2",
        "production_ranking_modified": False,
        "os_v1_modified": False,
        "pr6_modified": False,
        "pr8_viewpoint_rules_modified": False,
        "water_colour_used_as_evidence": False,
        "stand_used_in_extraction_or_scoring": False,
        "listing_specific_rules": False,
        "l_shape_special_case_in_scoring": False,
        "acquisition": {
            "image_urls": len(listing.image_urls),
            "images_acquired": len(photos),
            "stand_size_sqm": listing.stand_size_sqm,
            "bedrooms": listing.bedrooms,
            "bathrooms": listing.bathrooms,
        },
        "viewpoint_counts": dict(Counter(f.viewpoint for f in frozen)),
        "viewpoint_audit": {
            "interior_spatial_ids": [f.media_id for f in frozen if f.viewpoint == "interior" and f.spatial_eligible],
            "unusable_ids": [f.media_id for f in frozen if f.viewpoint == "unusable_ambiguous"],
            "closeup_scale_ids": [f.media_id for f in objects if f.viewpoint == "pool_closeup" and f.scale_eligible],
            "interiors_rejected": sum(1 for f in frozen if f.viewpoint == "interior"),
        },
        "frozen_lev2_channels": {
            "shape_eligible": channels["shape"]["eligible"],
            "shape_ids": channels["shape"]["source_ids"],
            "spatial_eligible": channels["spatial"]["eligible"],
            "spatial_ids": channels["spatial"]["source_ids"],
            "scale_eligible": channels["scale"]["eligible"],
            "aerial_eligible": channels["aerial"]["eligible"],
        },
        "frozen_frames": [frame_public(f) for f in frozen],
        "object_frames": [observation_public(o) for o in objects],
        "frame_table": frame_table,
        "l_consistency": l_consistency(objects),
        "quality_gate": gate,
        "contact_sheet": "panels/contact_sheet.jpg",
        "contact_sheet_ids": contact_ids,
        "rerank": rerank,
        "elapsed_s": round(time.time() - started, 1),
    }
    (OUT / "listing_pool_object_latest.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    write_report(payload, OUT / "listing_pool_object_report.md")
    print("wrote", OUT, "elapsed", time.time() - started)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
