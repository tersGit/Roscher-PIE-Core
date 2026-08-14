#!/usr/bin/env python3
"""Hybrid Pool Geometry v1 × frozen Scoring v2 ranking experiment.

Does not modify Hybrid v1, Scoring v2 weights, OS v1, native15, viewpoint gates,
FastSAM, or production combined_score. No extraction or weight retuning.

Ground-truth stand numbers are applied only after ranking files are written.
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
from backend.gis.estate_ags_matching.hybrid_geometry_ranking_test import (
    fingerprint_from_hybrid_frame,
    listing_evidence_from_hybrid_block,
    public_fingerprint,
    public_shape,
    rank_rows,
    score_one_candidate,
)
from backend.gis.estate_ags_matching.os_scoring_v2 import (
    contour_descriptors,
    listing_shape_descriptors,
)
from backend.gis.estate_ags_matching.os_v1_experimental_rank import (
    experimental_hybrid_neutral_score,
    is_high_conf,
    os_object_features,
)
from backend.gis.estate_ags_matching.pool_geometry import (
    PoolGeometryFingerprint,
    consensus_pool_fingerprint,
    extract_pool_geometry,
    pool_geometry_similarity,
)
from backend.imagery.estate_tiles import crop_dir_for
from backend.vision.clip_encoder import classify_scene, encode_image, mean_top_similarity
from scripts.run_carlswald_north_corrected import combined_score, parcel_mask, stand_size_support

HYBRID_JSON = ROOT / "data/investigations/hybrid_listing_pool_geometry_v1/latest.json"
PR5_ALL = ROOT / "data/investigations/os_v1_ranking_experiment/carlswald_north_116978058/all_candidates.json"
PR6_LATEST = ROOT / "data/investigations/os_scoring_v2/carlswald_north_116978058/latest.json"
PR6_ALL = ROOT / "data/investigations/os_scoring_v2/carlswald_north_116978058/all_candidates.json"
PR7_LATEST = ROOT / "data/investigations/os_scoring_v2/carlswald_north_116978058/rerun_multi_image/latest.json"
FROZEN_LISTING_116978058 = ROOT / "data/investigations/carlswald_north_corrected/116978058/listing_pool_fingerprint.json"
PHOTOS_116273255 = ROOT / "data/investigations/property_test_116273255/photos"
GIS_PATH = ROOT / "data/gis" / f"{CORRECT_CARLSWALD_NORTH}.json"
SEG_DIR = ROOT / "data/investigations/object_segmentation_v1/carlswald_north/json"
CROP_DIR = crop_dir_for(CORRECT_CARLSWALD_NORTH, "native15")
OUT = ROOT / "data/investigations/hybrid_geometry_ranking_test"
BLOB_FP_STATUSES = frozenset({"REJECTED", "UNKNOWN"})
LISTINGS = (
    {"id": "116978058", "stand_sqm": 972.0},
    {"id": "116273255", "stand_sqm": 500.0},
)


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


def load_hybrid_block(listing_id: str) -> dict:
    payload = json.loads(HYBRID_JSON.read_text(encoding="utf-8"))
    for block in payload["listings"]:
        if block["listing_id"] == listing_id:
            return block
    raise KeyError(listing_id)


def variant_payload(rows: list[dict], score_key: str, note: str) -> dict:
    ordered = rank_rows(rows, score_key)
    scores = [float(row[score_key]) for row in ordered]
    top1, top2 = ordered[0], ordered[1]
    top20 = []
    for row in ordered[:20]:
        top20.append(
            {
                "rank": row[f"{score_key}_rank"],
                "stand_number": row["stand_number"],
                "township": row.get("township"),
                "area_sqm": row.get("area_sqm"),
                "score": row[score_key],
                "os_pool_status": row.get("os_pool_status"),
                "os_building_status": row.get("os_building_status"),
                "os_driveway_status": row.get("os_driveway_status"),
                "os_high_conf_pool": row.get("os_high_conf_pool"),
                "blob_pool_present": row.get("blob_pool_present"),
                "coverage": row.get(f"{score_key}_coverage", row.get("coverage")),
                "contrib": row.get(f"{score_key}_contrib"),
                "shape_v2": row.get(f"{score_key}_shape_v2", row.get("shape_v2")),
                "spatial_v2": row.get(f"{score_key}_spatial_v2", row.get("spatial_v2")),
                "shape_parts": row.get(f"{score_key}_shape_parts"),
                "baseline_rank": row.get("baseline_rank"),
                "pr5_neutral_rank": row.get("pr5_neutral_rank"),
                "pr6_previous_rank": row.get("pr6_previous_rank"),
                "aerial_similarity": row.get("aerial_similarity"),
                "exterior_similarity": row.get("exterior_similarity"),
            }
        )
    return {
        "note": note,
        "n": len(ordered),
        "top1": {"stand": top1["stand_number"], "score": top1[score_key]},
        "top2": {"stand": top2["stand_number"], "score": top2[score_key]},
        "margin_1_2": round(float(top1[score_key]) - float(top2[score_key]), 4),
        "confidence": assess_separation(scores),
        "top5": top20[:5],
        "top20": top20,
        "os_status_top20": dict(Counter(row["os_pool_status"] for row in ordered[:20])),
        "n_rejected_or_unknown_top20": sum(
            1 for row in ordered[:20] if row.get("os_pool_status") in BLOB_FP_STATUSES
        ),
        "n_high_conf_pool_top20": sum(1 for row in ordered[:20] if row.get("os_high_conf_pool")),
        "evidence_coverage_top5": [row.get("coverage") for row in top20[:5]],
    }


def attach_v2(rows: list[dict], listing: PoolGeometryFingerprint, listing_shape, score_key: str) -> None:
    for row in rows:
        scored = score_one_candidate(
            listing,
            listing_shape,
            _load_seg(row["stand_number"]),
            aerial=row.get("aerial_similarity"),
            exterior=row.get("exterior_similarity"),
            stand_size=float(row.get("size_score") or 0.0),
        )
        row[score_key] = scored["score"]
        row[f"{score_key}_contrib"] = scored["contrib"]
        row[f"{score_key}_coverage"] = scored["coverage"]
        row[f"{score_key}_shape_v2"] = scored["shape_v2"]
        row[f"{score_key}_spatial_v2"] = scored["spatial_v2"]
        row[f"{score_key}_shape_parts"] = scored["shape_parts"]
        row[f"{score_key}_feats"] = scored["feats"]
        row["os_pool_status"] = scored["os_pool_status"]
        row["os_building_status"] = scored["os_building_status"]
        row["os_driveway_status"] = scored["os_driveway_status"]
        row["os_high_conf_pool"] = scored["os_high_conf_pool"]


def slim_rows(rows: list[dict], score_keys: list[str]) -> list[dict]:
    ordered = sorted(rows, key=lambda row: int(row.get("baseline_rank") or 10**9))
    slim = []
    for row in ordered:
        item = {
            "stand_number": row["stand_number"],
            "township": row.get("township"),
            "area_sqm": row.get("area_sqm"),
            "baseline_rank": row.get("baseline_rank"),
            "baseline_score": row.get("baseline_score"),
            "pr5_neutral_rank": row.get("pr5_neutral_rank"),
            "pr5_neutral_score": row.get("pr5_neutral_score"),
            "os_pool_status": row.get("os_pool_status"),
            "os_high_conf_pool": row.get("os_high_conf_pool"),
            "blob_pool_present": row.get("blob_pool_present"),
            "aerial_similarity": row.get("aerial_similarity"),
            "exterior_similarity": row.get("exterior_similarity"),
            "size_score": row.get("size_score"),
        }
        for key in score_keys:
            item[key] = row.get(key)
            item[f"{key}_rank"] = row.get(f"{key}_rank")
            item[f"{key}_shape_v2"] = row.get(f"{key}_shape_v2")
            item[f"{key}_spatial_v2"] = row.get(f"{key}_spatial_v2")
            item[f"{key}_coverage"] = row.get(f"{key}_coverage")
        slim.append(item)
    return slim


def rank_116978058() -> dict:
    hybrid_block = load_hybrid_block("116978058")
    evidence = listing_evidence_from_hybrid_block(hybrid_block)
    previous = PoolGeometryFingerprint.model_validate(json.loads(FROZEN_LISTING_116978058.read_text(encoding="utf-8")))
    previous_shape = listing_shape_descriptors(previous) if previous.present else None
    pr5 = json.loads(PR5_ALL.read_text(encoding="utf-8"))
    rows = []
    for item in pr5["rows"]:
        rows.append(
            {
                **item,
                "size_score": stand_size_support(972.0, item.get("area_sqm")),
                "pr5_neutral_score": item.get("hybrid_neutral_score"),
                "pr5_neutral_rank": item.get("hybrid_neutral_rank"),
            }
        )
    attach_v2(rows, previous, previous_shape, "pr6_previous")
    attach_v2(rows, evidence["fingerprint"], evidence["listing_shape"], "hybrid_v2")
    if evidence["chosen_frame"] and evidence["chosen_frame"].get("secondary"):
        spa_fp = fingerprint_from_hybrid_frame(evidence["chosen_frame"], use_secondary=True)
        spa_shape = contour_descriptors(spa_fp.contour_image)
        attach_v2(rows, spa_fp, spa_shape, "diagnostic_secondary")
    else:
        for row in rows:
            row["diagnostic_secondary"] = None

    rank_rows(rows, "pr6_previous")
    rank_rows(rows, "hybrid_v2")
    if rows[0].get("diagnostic_secondary") is not None:
        rank_rows(rows, "diagnostic_secondary")

    payload = {
        "listing_id": "116978058",
        "rankings_frozen": True,
        "ground_truth_applied": False,
        "production_ranking_modified": False,
        "hybrid_v1_modified": False,
        "scoring_v2_weights_modified": False,
        "colour_used_in_hybrid_score": False,
        "n_candidates": len(rows),
        "listing_evidence": {
            **{k: v for k, v in evidence.items() if k not in {"fingerprint", "listing_shape", "chosen_frame", "ready_frames"}},
            "fingerprint": public_fingerprint(evidence["fingerprint"]),
            "listing_shape": public_shape(evidence["listing_shape"]),
            "previous_fingerprint_media": previous.evidence_media_id,
        },
        "variants": {
            "baseline": _frozen_variant_from_pr5(rows, "baseline_score", "baseline_rank", "Frozen production/native15 combined_score (PR #5 file)"),
            "pr5_neutral": _frozen_variant_from_pr5(rows, "pr5_neutral_score", "pr5_neutral_rank", "Frozen PR #5 0.5-neutral diagnostic"),
            "pr6_previous": variant_payload(
                rows,
                "pr6_previous",
                "Frozen Scoring v2 weights + previous colour-blob listing fingerprint",
            ),
            "hybrid_v2": variant_payload(
                rows,
                "hybrid_v2",
                "Frozen Scoring v2 weights + Hybrid Pool Geometry v1 scoring-ready frames only",
            ),
        },
        "frozen_sources": {
            "pr5": str(PR5_ALL.relative_to(ROOT)),
            "pr6": str(PR6_LATEST.relative_to(ROOT)),
            "pr7": str(PR7_LATEST.relative_to(ROOT)) if PR7_LATEST.is_file() else None,
        },
        "diagnostic_secondary": None
        if rows[0].get("diagnostic_secondary") is None
        else variant_payload(rows, "diagnostic_secondary", "Diagnostic only: secondary component used as listing contour"),
    }
    return {"payload": payload, "rows": rows, "evidence": evidence}


def _frozen_variant_from_pr5(rows: list[dict], score_key: str, rank_key: str, note: str) -> dict:
    ordered = sorted(rows, key=lambda row: (int(row[rank_key]), str(row["stand_number"])))
    scores = [float(row[score_key]) for row in ordered]
    top20 = []
    for row in ordered[:20]:
        top20.append(
            {
                "rank": row[rank_key],
                "stand_number": row["stand_number"],
                "township": row.get("township"),
                "area_sqm": row.get("area_sqm"),
                "score": row[score_key],
                "os_pool_status": row.get("os_pool_status"),
                "os_high_conf_pool": row.get("os_high_conf_pool"),
                "blob_pool_present": row.get("blob_pool_present"),
            }
        )
    return {
        "note": note,
        "n": len(ordered),
        "top1": {"stand": ordered[0]["stand_number"], "score": ordered[0][score_key]},
        "top2": {"stand": ordered[1]["stand_number"], "score": ordered[1][score_key]},
        "margin_1_2": round(float(ordered[0][score_key]) - float(ordered[1][score_key]), 4),
        "confidence": assess_separation(scores),
        "top5": top20[:5],
        "top20": top20,
        "os_status_top20": dict(Counter(row.get("os_pool_status") for row in ordered[:20])),
        "n_rejected_or_unknown_top20": sum(
            1 for row in ordered[:20] if row.get("os_pool_status") in BLOB_FP_STATUSES
        ),
        "n_high_conf_pool_top20": sum(1 for row in ordered[:20] if row.get("os_high_conf_pool")),
    }


def rank_116273255() -> dict:
    hybrid_block = load_hybrid_block("116273255")
    evidence = listing_evidence_from_hybrid_block(hybrid_block)
    photos = {path.stem: path.read_bytes() for path in sorted(PHOTOS_116273255.glob("116273255-*.jpg"))}
    previous_items = []
    scenes = {}
    listing_vecs = {}
    for media_id, body in photos.items():
        image = Image.open(io.BytesIO(body)).convert("RGB")
        scene = classify_scene(image)
        scenes[media_id] = scene
        if scene == "interior":
            continue
        previous_items.append(extract_pool_geometry(body, media_id=media_id))
        listing_vecs[media_id] = encode_image(image)
    previous = consensus_pool_fingerprint(previous_items) if previous_items else PoolGeometryFingerprint(present=False)
    previous_shape = listing_shape_descriptors(previous) if previous.present else None
    aerial_vecs = [listing_vecs[mid] for mid, scene in scenes.items() if scene == "aerial" and mid in listing_vecs]
    exterior_vecs = [
        listing_vecs[mid]
        for mid, scene in scenes.items()
        if scene in {"front_elevation", "rear_elevation", "contextual", "driveway_access"} and mid in listing_vecs
    ]

    parcels = load_parcels_last_wins()
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
        compared = pool_geometry_similarity(previous, cand_pool)
        size_score = stand_size_support(500.0, parcel.get("area_sqm"))
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
            }
        )
    pool_ranked = sorted(
        rows,
        key=lambda row: (-(row["pool_geometry_similarity"] or -1), str(row["stand_number"])),
    )
    short_ids = {row["stand_number"] for row in pool_ranked[:40]}
    for row in rows:
        stand = row["stand_number"]
        aerial = exterior = None
        if stand in short_ids:
            image = Image.open(io.BytesIO(bytes_by[stand])).convert("RGB")
            cand_vecs = [encode_image(image)]
            aerial = mean_top_similarity(aerial_vecs, cand_vecs) if aerial_vecs else None
            exterior = mean_top_similarity(exterior_vecs, cand_vecs) if exterior_vecs else None
        row["aerial_similarity"] = None if aerial is None else round(float(aerial), 4)
        row["exterior_similarity"] = None if exterior is None else round(float(exterior), 4)
        row["video_similarity"] = None
        row["baseline_score"] = combined_score(
            pool_geom=row["pool_geometry_similarity"],
            pool_house=row["pool_house_similarity"],
            structural=None,
            aerial=row["aerial_similarity"],
            video=None,
            exterior=row["exterior_similarity"],
            driveway=None,
            gis=0.5,
            stand_size=row["size_score"],
            contradiction=row["contradiction"],
        )
        seg = _load_seg(stand)
        feats = os_object_features(
            previous,
            seg,
            listing_roof_area_frac=None,
            listing_roof_orientation_deg=None,
            listing_roof_aspect=None,
            listing_has_driveway=any(scene == "driveway_access" for scene in scenes.values()),
        )
        hybrid_n, _contrib = experimental_hybrid_neutral_score(
            feats,
            aerial=row["aerial_similarity"],
            video=None,
            exterior=row["exterior_similarity"],
            stand_size=row["size_score"],
        )
        row["pr5_neutral_score"] = hybrid_n
        row["os_features"] = feats

    rank_rows(rows, "baseline_score")
    for row in rows:
        row["baseline_rank"] = row["baseline_score_rank"]
    rank_rows(rows, "pr5_neutral_score")
    for row in rows:
        row["pr5_neutral_rank"] = row["pr5_neutral_score_rank"]

    attach_v2(rows, previous, previous_shape, "pr6_previous")
    attach_v2(rows, evidence["fingerprint"], evidence["listing_shape"], "hybrid_v2")
    rank_rows(rows, "pr6_previous")
    rank_rows(rows, "hybrid_v2")

    alt_variants = {}
    for frame in evidence["ready_frames"]:
        mid = str(frame.get("media_id") or "")
        suffix = mid.split("-")[-1]
        if suffix not in {"008", "037", "038"}:
            continue
        fp = fingerprint_from_hybrid_frame(frame)
        shape = contour_descriptors(fp.contour_image)
        key = f"diagnostic_frame_{suffix}"
        attach_v2(rows, fp, shape, key)
        rank_rows(rows, key)
        alt_variants[key] = variant_payload(
            rows,
            key,
            f"Diagnostic only: scoring-ready frame {mid} as the sole listing contour",
        )

    payload = {
        "listing_id": "116273255",
        "rankings_frozen": True,
        "ground_truth_applied": False,
        "production_ranking_modified": False,
        "hybrid_v1_modified": False,
        "scoring_v2_weights_modified": False,
        "colour_used_in_hybrid_score": False,
        "n_candidates": len(rows),
        "scene_counts": dict(Counter(scenes.values())),
        "previous_listing_note": "Colour-blob extract_pool_geometry consensus on non-interior listing photos (frozen previous method). Not Hybrid.",
        "listing_evidence": {
            **{k: v for k, v in evidence.items() if k not in {"fingerprint", "listing_shape", "chosen_frame", "ready_frames"}},
            "fingerprint": public_fingerprint(evidence["fingerprint"]),
            "listing_shape": public_shape(evidence["listing_shape"]),
            "previous_fingerprint": public_fingerprint(previous),
            "previous_shape": public_shape(previous_shape),
        },
        "variants": {
            "baseline": variant_payload(rows, "baseline_score", "Production combined_score on native15 blob geometry + CLIP (frozen method)"),
            "pr5_neutral": variant_payload(rows, "pr5_neutral_score", "PR #5 0.5-neutral OS terms using previous listing fingerprint"),
            "pr6_previous": variant_payload(rows, "pr6_previous", "Frozen Scoring v2 + previous colour-blob listing fingerprint"),
            "hybrid_v2": variant_payload(rows, "hybrid_v2", "Frozen Scoring v2 + Hybrid Pool Geometry v1 scoring-ready frames only"),
        },
        "diagnostic_frames": alt_variants,
    }
    return {"payload": payload, "rows": rows, "evidence": evidence}


def write_ranking_files(listing_id: str, result: dict) -> Path:
    dest = OUT / listing_id
    dest.mkdir(parents=True, exist_ok=True)
    payload = result["payload"]
    (dest / "rankings.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    score_keys = ["pr6_previous", "hybrid_v2"]
    if listing_id == "116273255":
        score_keys = ["baseline_score", "pr5_neutral_score", "pr6_previous", "hybrid_v2"]
        score_keys += [key for key in result["rows"][0] if key.startswith("diagnostic_frame_")]
    elif result["rows"] and result["rows"][0].get("diagnostic_secondary") is not None:
        score_keys.append("diagnostic_secondary")
    (dest / "all_candidates.json").write_text(
        json.dumps({"n": len(result["rows"]), "rows": slim_rows(result["rows"], score_keys)}, indent=2),
        encoding="utf-8",
    )
    return dest


def evaluate_after_freeze() -> dict:
    """Ground truth may be used only here, after ranking files exist."""
    known = {
        "116978058": {
            "stand": "365",
            "basis": "Independent visual match of listing rear pool vs native15, frozen since PR #5. Not used in ranking.",
        }
    }
    evals = {}
    for item in LISTINGS:
        listing_id = item["id"]
        path = OUT / listing_id / "rankings.json"
        all_path = OUT / listing_id / "all_candidates.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        all_rows = json.loads(all_path.read_text(encoding="utf-8"))["rows"]
        gt = known.get(listing_id)
        listing_eval = {"ground_truth_known": bool(gt), "ground_truth": gt}
        if gt:
            stand = gt["stand"]
            by_stand = {row["stand_number"]: row for row in all_rows}
            row = by_stand.get(stand)
            variant_eval = {}
            rankings = json.loads(path.read_text(encoding="utf-8"))
            for name, variant in rankings["variants"].items():
                ordered_ids = [item["stand_number"] for item in variant["top20"]]
                # rank among all candidates
                if name == "baseline":
                    rank = None if row is None else row.get("baseline_rank")
                    score = None if row is None else row.get("baseline_score")
                elif name == "pr5_neutral":
                    rank = None if row is None else row.get("pr5_neutral_rank")
                    score = None if row is None else row.get("pr5_neutral_score")
                elif name == "pr6_previous":
                    rank = None if row is None else row.get("pr6_previous_rank")
                    score = None if row is None else row.get("pr6_previous")
                else:
                    rank = None if row is None else row.get("hybrid_v2_rank")
                    score = None if row is None else row.get("hybrid_v2")
                top1_score = variant["top1"]["score"]
                variant_eval[name] = {
                    "rank": rank,
                    "score": score,
                    "top1_stand": variant["top1"]["stand"],
                    "top1_score": top1_score,
                    "diff_from_top1": None if score is None else round(float(score) - float(top1_score), 4),
                    "in_top20": stand in ordered_ids,
                    "confidence": variant["confidence"],
                    "margin_1_2": variant["margin_1_2"],
                }
            listing_eval["variants"] = variant_eval
            if row is not None:
                listing_eval["hybrid_shape_v2"] = row.get("hybrid_v2_shape_v2")
                listing_eval["hybrid_spatial_v2"] = row.get("hybrid_v2_spatial_v2")
                listing_eval["pr6_shape_v2"] = row.get("pr6_previous_shape_v2")
                listing_eval["pr6_spatial_v2"] = row.get("pr6_previous_spatial_v2")
                if PR7_LATEST.is_file():
                    pr7 = json.loads(PR7_LATEST.read_text(encoding="utf-8"))
                    listing_eval["pr7_multi_image_rank"] = (pr7.get("comparison") or {}).get("multi_image_365_rank")
                    listing_eval["pr7_multi_image_score"] = (pr7.get("comparison") or {}).get("multi_image_365_score")
                rivals = []
                for other in sorted(all_rows, key=lambda item: int(item.get("hybrid_v2_rank") or 10**9)):
                    if other["stand_number"] == stand:
                        continue
                    if other.get("os_high_conf_pool"):
                        rivals.append(
                            {
                                "stand_number": other["stand_number"],
                                "hybrid_rank": other.get("hybrid_v2_rank"),
                                "hybrid_score": other.get("hybrid_v2"),
                                "shape_v2": other.get("hybrid_v2_shape_v2"),
                                "spatial_v2": other.get("hybrid_v2_spatial_v2"),
                                "os_pool_status": other.get("os_pool_status"),
                            }
                        )
                    if len(rivals) >= 5:
                        break
                listing_eval["nearest_highconf_competitors"] = rivals
            diag = payload.get("diagnostic_secondary")
            if diag and row is not None:
                listing_eval["diagnostic_secondary_rank"] = row.get("diagnostic_secondary_rank")
                listing_eval["diagnostic_secondary_score"] = row.get("diagnostic_secondary")
        else:
            listing_eval["note"] = (
                "No independent ground-truth stand is available. Shortlist quality only; "
                "definitive rank accuracy cannot be measured."
            )
            listing_eval["hybrid_top5"] = payload["variants"]["hybrid_v2"]["top5"]
            listing_eval["hybrid_confidence"] = payload["variants"]["hybrid_v2"]["confidence"]
            listing_eval["baseline_top5"] = payload["variants"]["baseline"]["top5"]
            listing_eval["os_status_hybrid_top20"] = payload["variants"]["hybrid_v2"]["os_status_top20"]
            listing_eval["diagnostic_frames"] = {
                key: {
                    "top1": val["top1"],
                    "margin_1_2": val["margin_1_2"],
                    "confidence": val["confidence"],
                    "top5": val["top5"],
                }
                for key, val in (payload.get("diagnostic_frames") or {}).items()
            }
        payload["evaluation"] = listing_eval
        payload["ground_truth_applied"] = True
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        evals[listing_id] = listing_eval
    return evals


def draw_panels(listing_id: str, evidence: dict, rows: list[dict]) -> None:
    dest = OUT / listing_id / "panels"
    dest.mkdir(parents=True, exist_ok=True)
    listing_shape = evidence.get("listing_shape")
    listing_xy = None if listing_shape is None else np.asarray(listing_shape.get("norm_xy") or [], dtype=np.float64)
    hybrid_ordered = sorted(rows, key=lambda row: int(row.get("hybrid_v2_rank") or 10**9))
    items = [("listing Hybrid", listing_xy if listing_xy is not None and len(listing_xy) else None, (220, 220, 230))]
    colors = [(255, 196, 64), (80, 180, 255), (255, 110, 110), (160, 220, 120), (200, 160, 255)]

    for i, row in enumerate(hybrid_ordered[:5]):
        seg = _load_seg(row["stand_number"])
        desc = None
        pool = seg.get("pool") or {}
        if is_high_conf(pool):
            desc = contour_descriptors(pool.get("contour"))
        xy = None if desc is None else np.asarray(desc["norm_xy"], dtype=np.float64)
        items.append((f"{row['stand_number']} {row.get('os_pool_status')}", xy, colors[i % len(colors)]))
    w, h = 1100, 280
    canvas = Image.new("RGB", (w, h), (18, 18, 22))
    draw = ImageDraw.Draw(canvas)
    font = _font(13)
    n = max(len(items), 1)
    cell_w = w // n
    for i, (label, xy, color) in enumerate(items):
        x0 = i * cell_w
        box = [x0 + 8, 28, x0 + cell_w - 8, h - 12]
        draw.rectangle(box, outline=(60, 60, 70), width=1)
        draw.text((x0 + 12, 6), str(label)[:28], fill=(230, 230, 230), font=font)
        if xy is None or len(xy) < 3:
            draw.text((x0 + 16, h // 2), "no contour", fill=(160, 80, 80), font=font)
            continue
        cx, cy = (box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0
        scale = 0.42 * min(box[2] - box[0], box[3] - box[1])
        pix = [(int(cx + p[0] * scale), int(cy + p[1] * scale)) for p in xy]
        if listing_xy is not None and len(listing_xy) >= 3:
            lpix = [(int(cx + p[0] * scale), int(cy + p[1] * scale)) for p in listing_xy]
            draw.line(lpix + [lpix[0]], fill=(90, 90, 110), width=2)
        draw.line(pix + [pix[0]], fill=color, width=2)
    canvas.save(dest / "shape_contours.png")

    for row in hybrid_ordered[:8]:
        stand = row["stand_number"]
        crop_path = CROP_DIR / f"{_safe(stand)}_ags_aerial.jpg"
        if not crop_path.is_file():
            continue
        image = Image.open(crop_path).convert("RGBA")
        draw = ImageDraw.Draw(image, "RGBA")
        w, h = image.size
        seg = _load_seg(stand)

        def _poly(contour, fill, outline):
            if not contour:
                return
            pts = [(int(p[0] * (w - 1)), int(p[1] * (h - 1))) for p in contour]
            if len(pts) >= 3:
                draw.polygon(pts, fill=fill, outline=outline)

        pool = seg.get("pool") or {}
        building = seg.get("building") or {}
        if is_high_conf(building):
            _poly(building.get("contour"), (40, 80, 255, 60), (80, 140, 255))
        if is_high_conf(pool):
            _poly(pool.get("contour"), (255, 180, 40, 90), (255, 220, 80))
        ImageDraw.Draw(image).text(
            (8, 8),
            f"{stand} pool={row.get('os_pool_status')} shape={row.get('hybrid_v2_shape_v2')} #{row.get('hybrid_v2_rank')}",
            fill=(255, 255, 255),
            font=_font(16),
        )
        image.convert("RGB").save(dest / f"crop_{_safe(stand)}.jpg")


def main() -> int:
    started = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    print("Phase 1 — rank both listings with no ground truth")
    r1 = rank_116978058()
    d1 = write_ranking_files("116978058", r1)
    print(f"  wrote {d1 / 'rankings.json'} n={r1['payload']['n_candidates']}")
    r2 = rank_116273255()
    d2 = write_ranking_files("116273255", r2)
    print(f"  wrote {d2 / 'rankings.json'} n={r2['payload']['n_candidates']}")
    freeze_marker = {
        "rankings_frozen_at_unix": time.time(),
        "files": [
            str((d1 / "rankings.json").relative_to(ROOT)),
            str((d1 / "all_candidates.json").relative_to(ROOT)),
            str((d2 / "rankings.json").relative_to(ROOT)),
            str((d2 / "all_candidates.json").relative_to(ROOT)),
        ],
        "ground_truth_applied": False,
    }
    (OUT / "rankings_frozen.json").write_text(json.dumps(freeze_marker, indent=2), encoding="utf-8")
    print("Phase 2 — apply ground truth for evaluation only")
    evals = evaluate_after_freeze()
    draw_panels("116978058", r1["evidence"], r1["rows"])
    draw_panels("116273255", r2["evidence"], r2["rows"])
    summary = {
        "experiment": "hybrid_geometry_ranking_test",
        "production_ranking_modified": False,
        "hybrid_v1_modified": False,
        "scoring_v2_weights_modified": False,
        "os_v1_modified": False,
        "native15_modified": False,
        "colour_used_in_hybrid_score": False,
        "n_candidates": 330,
        "runtime_s": round(time.time() - started, 2),
        "listing_116978058": evals.get("116978058"),
        "listing_116273255": evals.get("116273255"),
        "variants_116978058": {name: _compact_variant(val) for name, val in r1["payload"]["variants"].items()},
        "variants_116273255": {name: _compact_variant(val) for name, val in r2["payload"]["variants"].items()},
    }
    (OUT / "latest.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"runtime_s={summary['runtime_s']}")
    print(f"wrote {OUT / 'latest.json'}")
    return 0


def _compact_variant(variant: dict) -> dict:
    return {
        "top1": variant["top1"],
        "top2": variant["top2"],
        "margin_1_2": variant["margin_1_2"],
        "confidence": variant["confidence"],
        "top5": [{"rank": r["rank"], "stand": r["stand_number"], "score": r["score"], "os": r.get("os_pool_status")} for r in variant["top5"]],
        "n_rejected_or_unknown_top20": variant.get("n_rejected_or_unknown_top20"),
    }


if __name__ == "__main__":
    raise SystemExit(main())
