#!/usr/bin/env python3
"""Blind Carlswald North diagnostic for Property24 listing 116273255.

Uses frozen production ranking, PR #5 0.5-neutral, PR #6 Scoring v2, and
unchanged PR #7 multi-image fusion. Does not implement Listing Evidence v2.
No stand number is an input to candidate generation or scoring. No retune
before seeing ranks.
"""

from __future__ import annotations

import html as html_lib
import io
import json
import re
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
from backend.gis.estate_ags_matching.aerial_geometric import (
    extract_structural_layout,
    structural_layout_similarity,
)
from backend.gis.estate_ags_matching.final_candidates import (
    FINAL_CANDIDATE_LIMIT,
    INTERNAL_PASS2_SHORTLIST,
    assess_separation,
    freeze_final_candidates,
)
from backend.gis.estate_ags_matching.os_scoring_v2 import (
    OS_KEYS_NO_BUILDING,
    V2_WEIGHTS_NO_BUILDING,
    contour_descriptors,
    listing_shape_descriptors,
    score_v2,
    v2_object_features,
)
from backend.gis.estate_ags_matching.os_scoring_v2_multi_image import (
    fuse_listing_observations,
    observation_public,
    observe_listing_image,
    spatial_v2_with_scale,
)
from backend.gis.estate_ags_matching.os_v1_experimental_rank import (
    experimental_hybrid_neutral_score,
    is_high_conf,
    os_object_features,
)
from backend.gis.estate_ags_matching.pool_geometry import (
    consensus_pool_fingerprint,
    extract_pool_geometry,
    pool_geometry_similarity,
)
from backend.imagery.estate_tiles import crop_dir_for
from backend.parsers.property24 import download_images, fetch_listing
from backend.vision.clip_encoder import classify_scene, encode_image, mean_top_similarity
from scripts.run_carlswald_north_corrected import combined_score, parcel_mask, stand_size_support

LISTING_ID = "116273255"
LISTING_URL = "https://www.property24.com/for-sale/carlswald-north-estate/midrand/gauteng/12743/116273255"
GIS_PATH = ROOT / "data/gis" / f"{CORRECT_CARLSWALD_NORTH}.json"
CROP_DIR = crop_dir_for(CORRECT_CARLSWALD_NORTH, "native15")
SEG_DIR = ROOT / "data/investigations/object_segmentation_v1/carlswald_north/json"
OUT = ROOT / "data/investigations/property_test_116273255"
POOL_SCENES = frozenset({"pool_garden", "aerial", "rear_elevation", "contextual"})
IDENT_SCENES = frozenset(
    {"aerial", "pool_garden", "front_elevation", "rear_elevation", "driveway_access", "contextual"}
)


def _safe(stand: str) -> str:
    return str(stand).replace("/", "_")


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


def _font(size: int = 14):
    path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    return ImageFont.truetype(str(path), size) if path.is_file() else ImageFont.load_default()


def _load_seg(stand: str) -> dict:
    path = SEG_DIR / f"{_safe(stand)}.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _clean(text: str) -> str:
    text = html_lib.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def extra_listing_text(url: str) -> dict:
    import httpx
    from backend.parsers.property24 import USER_AGENT

    html = httpx.get(url, headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=40).text
    desc_m = re.search(r"p24_description[^>]*>(.*?)</div>", html, re.I | re.S)
    description = _clean(desc_m.group(1)) if desc_m else None
    # Full page text: og:description is truncated; pool wording lives in later paragraphs.
    page_text = _clean(html)
    pool_mentions = []
    source = description or page_text
    for sent in re.split(r"(?<=[.!?])\s+", page_text):
        if re.search(r"\bpool\b|jacuzzi|spa|L[- ]shaped", sent, re.I) and len(sent) < 400:
            if "sparkling" in sent.lower() or "l-shaped" in sent.lower() or "swimming pool" in sent.lower():
                pool_mentions.append(sent)
    pool_mentions = list(dict.fromkeys(pool_mentions))[:8]
    l_shaped = bool(re.search(r"\bL[- ]shaped\b", page_text, re.I))
    cover_net = bool(re.search(r"L[- ]shaped pool with a cover and net|pool with a cover and net", page_text, re.I))
    bedrooms = None
    m = re.search(r"(\d+)\s*Bedroom House", html, re.I)
    if m:
        bedrooms = int(m.group(1))
    bathrooms = None
    m = re.search(r"two-and-a-half-bathroom|2\.5\s*bath", html, re.I)
    if m:
        bathrooms = 2.5
    else:
        m = re.search(r"(\d+(?:\.\d+)?)\s*Bathroom", html, re.I)
        if m:
            bathrooms = float(m.group(1))
    return {
        "description": description,
        "pool_mentions": pool_mentions,
        "advertises_l_shaped_pool": l_shaped,
        "advertises_pool_cover_or_net": cover_net,
        "bedrooms": bedrooms,
        "bathrooms": bathrooms,
        "used_to_select_stand": False,
        "note": "Textual pool shape is recorded as listing evidence only. It is not a candidate filter.",
    }


def nadir_safe_flag(scene: str, fp) -> dict:
    if scene == "interior":
        return {"safe": False, "reason": "interior"}
    if scene == "aerial":
        return {"safe": True, "reason": "aerial_near_nadir"}
    if not fp.present:
        return {"safe": False, "reason": "no_pool_detected"}
    rel = float(fp.relative_area or 0.0)
    compact = float(fp.compactness or 0.0)
    if rel > 0.28:
        return {"safe": False, "reason": "excessive_frame_coverage_closeup"}
    if compact < 0.18:
        return {"safe": False, "reason": "smeared_low_compactness"}
    if scene in {"pool_garden", "contextual", "rear_elevation"}:
        return {"safe": False, "reason": "oblique_ground_or_garden_view"}
    return {"safe": False, "reason": f"scene_{scene}_not_nadir"}


def _rank(rows: list[dict], key: str, rank_key: str) -> list[dict]:
    ordered = sorted(rows, key=lambda row: (-float(row[key] or 0.0), str(row["stand_number"])))
    for index, row in enumerate(ordered, start=1):
        row[rank_key] = index
    return ordered


def _os_pool_brief(seg: dict) -> dict:
    pool = seg.get("pool") or {}
    geom = pool.get("geometry") or {}
    building = seg.get("building") or {}
    driveway = seg.get("driveway") or {}
    rel = ((seg.get("spatial") or {}).get("relationships") or {}).get("pool_house") or {}
    return {
        "os_pool_status": pool.get("status"),
        "os_pool_present": bool(geom.get("present")),
        "os_high_conf_pool": is_high_conf(pool),
        "os_pool_shape": geom.get("shape"),
        "os_pool_aspect": geom.get("aspect_ratio"),
        "os_pool_compactness": geom.get("compactness"),
        "os_pool_rectangularity": geom.get("rectangularity"),
        "os_pool_area_m2": geom.get("area_m2"),
        "os_building_status": building.get("status"),
        "os_driveway_status": driveway.get("status"),
        "os_pool_house_dir": rel.get("direction"),
        "os_pool_house_dist": rel.get("dist"),
    }


def compact_row(row: dict, score_key: str, rank_key: str) -> dict:
    contrib = row.get("contrib") or {}
    top_contrib = sorted(contrib.items(), key=lambda item: -abs(float(item[1] or 0)))[:6]
    return {
        "rank": row.get(rank_key),
        "stand_number": row["stand_number"],
        "township": row.get("township"),
        "area_sqm": row.get("area_sqm"),
        "score": row.get(score_key),
        "os_pool_status": row.get("os_pool_status"),
        "os_pool_shape": row.get("os_pool_shape"),
        "os_high_conf_pool": row.get("os_high_conf_pool"),
        "os_building_status": row.get("os_building_status"),
        "os_driveway_status": row.get("os_driveway_status"),
        "blob_pool_present": row.get("blob_pool_present"),
        "pool_geometry_similarity": row.get("pool_geometry_similarity"),
        "shape_v2": row.get("shape_v2"),
        "spatial_v2": row.get("spatial_v2"),
        "aerial_similarity": row.get("aerial_similarity"),
        "exterior_similarity": row.get("exterior_similarity"),
        "size_score": row.get("size_score"),
        "coverage": row.get("coverage"),
        "contrib_top": top_contrib,
        "contradiction": row.get("contradiction"),
    }


def ranking_block(rows: list[dict], score_key: str, rank_key: str, name: str) -> dict:
    ordered = sorted(rows, key=lambda row: (-float(row[score_key] or 0.0), str(row["stand_number"])))
    scores = [float(row[score_key] or 0.0) for row in ordered]
    conf = assess_separation(scores)
    top1, top2 = ordered[0], ordered[1]
    return {
        "name": name,
        "n": len(ordered),
        "top1": {"stand": top1["stand_number"], "score": top1[score_key]},
        "top2": {"stand": top2["stand_number"], "score": top2[score_key]},
        "margin_1_2": round(float(top1[score_key] or 0) - float(top2[score_key] or 0), 4),
        "confidence": conf,
        "top5": [compact_row(row, score_key, rank_key) for row in ordered[:5]],
        "top20": [compact_row(row, score_key, rank_key) for row in ordered[:20]],
    }


def _draw_listing_overlays(bodies: dict[str, bytes], frames: list[dict], dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    font = _font(14)
    useful = [item for item in frames if item["scene"] in IDENT_SCENES or item["pool_detected"]]
    useful = useful[:16]
    for item in useful:
        body = bodies.get(item["media_id"])
        if not body:
            continue
        image = Image.open(io.BytesIO(body)).convert("RGB")
        draw = ImageDraw.Draw(image)
        w, h = image.size
        xy = item.get("contour_image") or []
        if len(xy) >= 3:
            pts = [(float(x) * (w - 1), float(y) * (h - 1)) for x, y in xy]
            draw.line(pts + [pts[0]], fill=(0, 220, 90), width=3)
        label = (
            f"{item['media_id'][-3:]} {item['scene']} pool={int(item['pool_detected'])} "
            f"shape={item.get('shape_class')} c={item.get('compactness')} "
            f"nadir_safe={int(item['nadir_safe']['safe'])}"
        )
        draw.rectangle([4, 4, min(w - 4, 10 + 7 * len(label)), 28], fill=(0, 0, 0))
        draw.text((8, 8), label, fill=(250, 250, 250), font=font)
        image.save(dest / f"{item['media_id']}.jpg", quality=82)


def _draw_candidate_panel(stand: str, seg: dict, title: str, dest: Path) -> None:
    crop_path = CROP_DIR / f"{_safe(stand)}_ags_aerial.jpg"
    if not crop_path.is_file():
        return
    image = Image.open(crop_path).convert("RGBA")
    draw = ImageDraw.Draw(image, "RGBA")
    w, h = image.size

    def _poly(contour, fill, outline):
        if not contour:
            return
        pts = [(int(p[0] * (w - 1)), int(p[1] * (h - 1))) for p in contour]
        if len(pts) >= 3:
            draw.polygon(pts, fill=fill, outline=outline)

    pool = seg.get("pool") or {}
    building = seg.get("building") or {}
    driveway = seg.get("driveway") or {}
    if is_high_conf(driveway):
        _poly(driveway.get("contour"), (180, 180, 180, 50), (200, 200, 200))
    if is_high_conf(building):
        _poly(building.get("contour"), (40, 80, 255, 60), (80, 140, 255))
    if is_high_conf(pool):
        _poly(pool.get("contour"), (255, 180, 40, 90), (255, 220, 80))
    elif pool.get("contour"):
        _poly(pool.get("contour"), (255, 80, 80, 40), (255, 80, 80))
    ImageDraw.Draw(image).text((8, 8), title, fill=(255, 255, 255), font=_font(16))
    dest.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(dest, quality=88)


def main() -> int:
    started = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "panels").mkdir(exist_ok=True)
    print("Phase 1 — listing acquisition")
    listing = fetch_listing(LISTING_URL, LISTING_ID)
    text = extra_listing_text(LISTING_URL)
    listing.bedrooms = listing.bedrooms or text.get("bedrooms")
    listing.bathrooms = listing.bathrooms or text.get("bathrooms")
    (OUT / "listing_meta.json").write_text(json.dumps(listing.__dict__, indent=2), encoding="utf-8")
    (OUT / "listing_text.json").write_text(json.dumps(text, indent=2), encoding="utf-8")
    print(f"  title={listing.title}")
    print(f"  stand_size={listing.stand_size_sqm} beds={listing.bedrooms} baths={listing.bathrooms}")
    print(f"  image_urls={len(listing.image_urls)} l_shaped={text['advertises_l_shaped_pool']}")
    bodies = download_images(listing.image_urls, OUT / "photos", LISTING_ID)
    print(f"  images_acquired={len(bodies)}")

    print("Phase 2 — frozen listing evidence (not Listing Evidence v2)")
    frames = []
    retained = []
    scenes = {}
    for media_id, body in bodies.items():
        try:
            image = Image.open(io.BytesIO(body)).convert("RGB")
        except Exception:
            continue
        if min(image.size) < 80:
            continue
        scene = classify_scene(image)
        scenes[media_id] = scene
        fp = extract_pool_geometry(body, media_id=media_id)
        desc = None
        if fp.present:
            desc = contour_descriptors(fp.contour_normalized or fp.contour_image)
        safe = nadir_safe_flag(scene, fp)
        rec = {
            "media_id": media_id,
            "scene": scene,
            "image_class": scene,
            "pool_detected": fp.present,
            "shape_class": fp.shape_class,
            "compactness": fp.compactness,
            "convexity": fp.convexity,
            "rectangularity": fp.rectangularity,
            "aspect_ratio": fp.aspect_ratio,
            "relative_area": fp.relative_area,
            "curved_section_count": fp.curved_section_count,
            "house_visible": fp.house_centroid_x is not None,
            "pool_to_house_dist": fp.pool_to_house_dist,
            "pool_to_house_angle_deg": fp.pool_to_house_angle_deg,
            "pool_to_house_dx": fp.pool_to_house_dx,
            "pool_to_house_dy": fp.pool_to_house_dy,
            "contour_quality": None if not fp.present else round(float(fp.compactness or 0.0), 4),
            "predicted_shape": fp.shape_class,
            "n_corners": None if desc is None else desc.get("n_corners"),
            "n_major_indents": None if desc is None else desc.get("n_major_indents"),
            "elongation": None if desc is None else desc.get("elongation"),
            "circularity": None if desc is None else desc.get("circularity"),
            "solidity": None if desc is None else desc.get("solidity"),
            "spatial_evidence": fp.pool_to_house_dist is not None and fp.house_centroid_x is not None,
            "scale_evidence": bool(fp.present and fp.relative_area and 0.01 <= fp.relative_area <= 0.20 and scene == "aerial"),
            "nadir_safe": safe,
            "used_in_frozen_consensus": scene in POOL_SCENES and scene != "interior",
            "contour_image": fp.contour_image,
        }
        frames.append(rec)
        if scene in IDENT_SCENES:
            retained.append(media_id)
    print(f"  scenes={dict(Counter(scenes.values()))} exterior={len(retained)}")
    pool_ids = [item["media_id"] for item in frames if item["used_in_frozen_consensus"]]
    if not pool_ids:
        pool_ids = retained[:]
    pool_fps = [extract_pool_geometry(bodies[mid], media_id=mid) for mid in pool_ids if mid in bodies]
    listing_pool = consensus_pool_fingerprint(pool_fps)
    listing_shape = listing_shape_descriptors(listing_pool)
    (OUT / "listing_pool_fingerprint.json").write_text(
        json.dumps(listing_pool.model_dump(mode="json"), indent=2), encoding="utf-8"
    )
    public_frames = [{k: v for k, v in item.items() if k != "contour_image"} for item in frames]
    (OUT / "listing_images.json").write_text(json.dumps(public_frames, indent=2), encoding="utf-8")
    print(
        f"  consensus present={listing_pool.present} shape={listing_pool.shape_class} "
        f"aspect={listing_pool.aspect_ratio} compact={listing_pool.compactness}"
    )
    _draw_listing_overlays(bodies, frames, OUT / "panels" / "listing")

    print("PR #7 multi-image fusion (unchanged module)")
    pr7_obs = []
    for item in frames:
        if item["scene"] == "interior":
            continue
        pr7_obs.append(observe_listing_image(item["media_id"], bodies[item["media_id"]], item["scene"]))
    pr7_fused = fuse_listing_observations(pr7_obs)
    pr7_listing = pr7_fused.get("fused_fingerprint")
    pr7_shape = pr7_fused.get("fused_shape_descriptors")
    print(
        f"  pr7 pool_frames={pr7_fused.get('n_pool_present')} shape_from={pr7_fused.get('shape_source')} "
        f"spatial_from={pr7_fused.get('spatial_source')}"
    )

    print("Phase 3 — blind 330-candidate ranking")
    parcels = load_parcels_last_wins()
    listing_layout = None
    aerial_ids = [mid for mid in retained if scenes.get(mid) == "aerial"]
    layout_ids = aerial_ids or [mid for mid in retained if scenes.get(mid) in {"pool_garden", "rear_elevation", "contextual"}][:6]
    if layout_ids:
        listing_layout = extract_structural_layout(bodies[layout_ids[0]])
    listing_vecs = {mid: encode_image(Image.open(io.BytesIO(bodies[mid])).convert("RGB")) for mid in retained}
    aerial_vecs = [listing_vecs[mid] for mid in aerial_ids if mid in listing_vecs]
    exterior_vecs = [
        listing_vecs[mid]
        for mid in retained
        if scenes.get(mid) in {"front_elevation", "rear_elevation", "contextual", "driveway_access"}
    ]
    listing_has_driveway = any(scenes.get(mid) == "driveway_access" for mid in retained)

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
        compared = pool_geometry_similarity(listing_pool, cand_pool)
        cand_layout = extract_structural_layout(body)
        structural = structural_layout_similarity(listing_layout, cand_layout) if listing_layout else None
        size_score = stand_size_support(listing.stand_size_sqm, parcel.get("area_sqm"))
        seg = _load_seg(stand)
        os_brief = _os_pool_brief(seg)
        rows.append(
            {
                "stand_number": stand,
                "township": parcel.get("township"),
                "area_sqm": parcel.get("area_sqm"),
                "pool_geometry_similarity": compared.get("pool_geometry_similarity"),
                "pool_house_similarity": compared.get("pool_house_similarity"),
                "structural_layout_similarity": structural,
                "driveway_similarity": structural,
                "size_score": size_score,
                "contradiction": compared.get("contradiction"),
                "blob_pool_present": cand_pool.present,
                **os_brief,
            }
        )
    print(f"  candidates={len(rows)}")

    pool_ranked = sorted(
        rows,
        key=lambda row: (
            -(row["pool_geometry_similarity"] or -1),
            -(row["pool_house_similarity"] or -1),
            str(row["stand_number"]),
        ),
    )
    short_ids = {row["stand_number"] for row in pool_ranked[:INTERNAL_PASS2_SHORTLIST]}
    for row in rows:
        aerial = exterior = video = None
        if row["stand_number"] in short_ids:
            image = Image.open(io.BytesIO(bytes_by[row["stand_number"]])).convert("RGB")
            cand_vecs = [encode_image(image)]
            aerial = mean_top_similarity(aerial_vecs, cand_vecs)
            exterior = mean_top_similarity(exterior_vecs, cand_vecs)
        row["aerial_similarity"] = None if aerial is None else round(aerial, 4)
        row["exterior_similarity"] = None if exterior is None else round(exterior, 4)
        row["video_similarity"] = None if video is None else round(video, 4)
        row["baseline_score"] = combined_score(
            pool_geom=row["pool_geometry_similarity"],
            pool_house=row["pool_house_similarity"],
            structural=row["structural_layout_similarity"],
            aerial=row["aerial_similarity"],
            video=row["video_similarity"],
            exterior=row["exterior_similarity"],
            driveway=row["driveway_similarity"],
            gis=0.5,
            stand_size=row["size_score"],
            contradiction=row["contradiction"],
        )
        seg = _load_seg(row["stand_number"])
        feats = os_object_features(
            listing_pool,
            seg,
            listing_roof_area_frac=None if listing_layout is None else listing_layout.roof_area_frac,
            listing_roof_orientation_deg=None if listing_layout is None else listing_layout.roof_orientation_deg,
            listing_roof_aspect=None if listing_layout is None else listing_layout.roof_aspect,
            listing_has_driveway=listing_has_driveway,
        )
        hybrid_n, hybrid_n_c = experimental_hybrid_neutral_score(
            feats,
            aerial=row["aerial_similarity"],
            video=row["video_similarity"],
            exterior=row["exterior_similarity"],
            stand_size=row["size_score"],
        )
        row["pr5_neutral_score"] = hybrid_n
        row["pr5_contrib"] = hybrid_n_c
        v2_feats = v2_object_features(
            listing_pool,
            seg,
            listing_shape=listing_shape,
            listing_has_driveway=listing_has_driveway,
            listing_driveway_side=None,
            include_building_coarse=False,
        )
        v2_score, v2_contrib, v2_cov, _fac = score_v2(
            v2_feats,
            aerial=row["aerial_similarity"],
            exterior=row["exterior_similarity"],
            stand_size=row["size_score"],
            weights=V2_WEIGHTS_NO_BUILDING,
            os_keys=OS_KEYS_NO_BUILDING,
            missing="neutral",
        )
        row["pr6_score"] = v2_score
        row["pr6_contrib"] = v2_contrib
        row["coverage"] = v2_cov
        row["shape_v2"] = v2_feats.get("shape_v2")
        row["spatial_v2"] = v2_feats.get("spatial_v2")
        if pr7_listing is not None and pr7_shape is not None:
            pr7_feats = v2_object_features(
                pr7_listing,
                seg,
                listing_shape=pr7_shape,
                listing_has_driveway=listing_has_driveway,
                listing_driveway_side=None,
                include_building_coarse=False,
            )
            spatial_score, _parts = spatial_v2_with_scale(pr7_listing, pr7_fused.get("fused_pool_roof_ratio"), seg)
            pr7_feats["spatial_v2"] = spatial_score
            pr7_score, pr7_contrib, pr7_cov, _f = score_v2(
                pr7_feats,
                aerial=row["aerial_similarity"],
                exterior=row["exterior_similarity"],
                stand_size=row["size_score"],
                weights=V2_WEIGHTS_NO_BUILDING,
                os_keys=OS_KEYS_NO_BUILDING,
                missing="neutral",
            )
            row["pr7_score"] = pr7_score
            row["pr7_contrib"] = pr7_contrib
            row["pr7_coverage"] = pr7_cov
            row["pr7_shape_v2"] = pr7_feats.get("shape_v2")
            row["pr7_spatial_v2"] = pr7_feats.get("spatial_v2")

    _rank(rows, "baseline_score", "baseline_rank")
    _rank(rows, "pr5_neutral_score", "pr5_neutral_rank")
    _rank(rows, "pr6_score", "pr6_rank")
    if any("pr7_score" in row for row in rows):
        _rank(rows, "pr7_score", "pr7_rank")

    baseline = ranking_block(rows, "baseline_score", "baseline_rank", "frozen_production_native15")
    pr5 = ranking_block(rows, "pr5_neutral_score", "pr5_neutral_rank", "pr5_0.5_neutral")
    pr6 = ranking_block(rows, "pr6_score", "pr6_rank", "pr6_scoring_v2")
    pr7 = None
    if any("pr7_score" in row for row in rows):
        pr7 = ranking_block(rows, "pr7_score", "pr7_rank", "pr7_multi_image_unchanged")

    for name, block in (("baseline", baseline), ("pr5", pr5), ("pr6", pr6), ("pr7", pr7)):
        if not block:
            continue
        print(
            f"  {name} #1={block['top1']['stand']} score={block['top1']['score']} "
            f"margin={block['margin_1_2']} conf={block['confidence']['level']}"
        )

    print("Phase 4 — freeze ranks, then write Top 10+ panels")
    inspect_stands = []
    for block in (baseline, pr5, pr6, pr7):
        if not block:
            continue
        inspect_stands.extend(item["stand_number"] for item in block["top20"][:10])
    inspect_stands = list(dict.fromkeys(inspect_stands))
    by = {row["stand_number"]: row for row in rows}
    for stand in inspect_stands:
        row = by[stand]
        seg = _load_seg(stand)
        title = (
            f"{stand} base#{row['baseline_rank']} n#{row['pr5_neutral_rank']} "
            f"v2#{row['pr6_rank']} pool={row.get('os_pool_status')} {row.get('os_pool_shape')}"
        )
        _draw_candidate_panel(stand, seg, title, OUT / "panels" / "candidates" / f"stand_{_safe(stand)}.jpg")

    payload = {
        "listing_id": LISTING_ID,
        "blind": True,
        "eval_stand_used_in_scoring": False,
        "production_ranking_modified": False,
        "os_v1_modified": False,
        "pr5_modified": False,
        "pr6_modified": False,
        "pr7_modified": False,
        "listing_evidence_v2_used": False,
        "retuned_before_results": False,
        "n_candidates": len(rows),
        "clip_shortlist_n": INTERNAL_PASS2_SHORTLIST,
        "listing_acquisition": {
            "image_urls": len(listing.image_urls),
            "images_acquired": len(bodies),
            "scene_counts": dict(Counter(scenes.values())),
            "exterior_shortlist": len(retained),
            "pool_related_images": sum(1 for item in frames if item["scene"] in POOL_SCENES),
            "aerial_elevated_images": sum(1 for item in frames if item["scene"] == "aerial"),
            "stand_size_sqm": listing.stand_size_sqm,
            "bedrooms": listing.bedrooms,
            "bathrooms": listing.bathrooms,
            "advertises_l_shaped_pool": text["advertises_l_shaped_pool"],
            "advertises_pool_cover_or_net": text["advertises_pool_cover_or_net"],
        },
        "listing_consensus": {
            "present": listing_pool.present,
            "shape_class": listing_pool.shape_class,
            "aspect_ratio": listing_pool.aspect_ratio,
            "compactness": listing_pool.compactness,
            "rectangularity": listing_pool.rectangularity,
            "convexity": listing_pool.convexity,
            "pool_to_house_dist": listing_pool.pool_to_house_dist,
            "notes": listing_pool.notes,
        },
        "pr7_fusion": {
            "shape_source": pr7_fused.get("shape_source"),
            "spatial_source": pr7_fused.get("spatial_source"),
            "scale_sources": pr7_fused.get("scale_sources"),
            "shape_cluster": pr7_fused.get("shape_cluster"),
            "fused_pool_roof_ratio": pr7_fused.get("fused_pool_roof_ratio"),
            "n_pool_present": pr7_fused.get("n_pool_present"),
            "fused_shape_class": None if pr7_listing is None else pr7_listing.shape_class,
            "fused_compactness": None if pr7_listing is None else pr7_listing.compactness,
            "fused_aspect": None if pr7_listing is None else pr7_listing.aspect_ratio,
        },
        "rankings": {"baseline": baseline, "pr5_neutral": pr5, "pr6_scoring_v2": pr6, "pr7_multi_image": pr7},
        "inspect_stands": inspect_stands,
        "elapsed_s": round(time.time() - started, 1),
    }
    (OUT / "latest.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    slim_rows = []
    keep = {
        "stand_number", "township", "area_sqm", "baseline_score", "baseline_rank",
        "pr5_neutral_score", "pr5_neutral_rank", "pr6_score", "pr6_rank", "pr7_score", "pr7_rank",
        "os_pool_status", "os_pool_shape", "os_high_conf_pool", "os_building_status", "os_driveway_status",
        "blob_pool_present", "pool_geometry_similarity", "shape_v2", "spatial_v2",
        "aerial_similarity", "exterior_similarity", "size_score", "coverage", "contradiction",
        "pr5_contrib", "pr6_contrib", "pr7_contrib",
    }
    for row in rows:
        slim_rows.append({k: row[k] for k in keep if k in row})
    (OUT / "all_candidates.json").write_text(json.dumps({"rows": slim_rows}, indent=2), encoding="utf-8")
    (OUT / "pr7_observations.json").write_text(
        json.dumps([observation_public(item) for item in pr7_obs], indent=2, default=str),
        encoding="utf-8",
    )
    print(f"wrote {OUT} elapsed={time.time()-started:.1f}s")
    print("Ranks frozen. Inspect panels next; do not rescore.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
