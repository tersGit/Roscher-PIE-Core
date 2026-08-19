"""Blind PIE ranking benchmark for Property24 listing 116273255 on GIS 002.

Uses the frozen ranking stack only: listing Pool Gate v1, Hybrid Pool Geometry v1,
Scoring v2 weights, OS v1 JSON, native15 crops, CLIP ViT-B-32. Does not modify
detectors, inventory classifications, or weights. Ground truth is applied only
after the freeze file exists.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import re
import time
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from backend.gis.carlswald_north_complete import COMPLETE_002_PATH
from backend.gis.dataset_registry import (
    COMPLETE_CARLSWALD_NORTH,
    FROZEN_CARLSWALD_NORTH_001,
)
from backend.gis.estate_ags_matching.ags_native15_raw_proof import (
    covering_tile,
    crop_parcel_from_tile,
    native15_tile_grid,
    parcel_bbox,
    render_proof_panel,
)
from backend.gis.estate_ags_matching.complete_estate_inventory import (
    COMPLETE_OS_DIR,
    crop_parcels,
    download_tiles_for_parcels,
    load_complete_dataset,
)
from backend.gis.estate_ags_matching.estate_property_inventory_v1 import (
    DEFAULT_OS_DIR,
    crop_path_for,
    load_inventory_records,
    os_json_path_for,
    pass1_parcels,
    safe_stand,
)
from backend.gis.estate_ags_matching.hybrid_geometry_ranking_test import (
    listing_evidence_from_hybrid_block,
    public_fingerprint,
    public_shape,
    rank_rows,
    score_one_candidate,
)
from backend.gis.estate_ags_matching.listing_pool_gate_v1 import apply_listing_pool_gate
from backend.gis.estate_ags_matching.os_scoring_v2 import V2_WEIGHTS_NO_BUILDING
from backend.gis.estate_ags_matching.pool_geometry import PoolGeometryFingerprint
from backend.gis.estate_ags_matching.listing_pool_object import (
    observation_public,
    observe_pool_object,
)
from backend.imagery.estate_tiles import crop_dir_for
from backend.parsers.property24 import USER_AGENT, download_images, parse_listing_html
from backend.vision.clip_encoder import classify_scene, load_clip, mean_top_similarity
from backend.vision.object_segmentation import parcel_mask_from_geometry

REPO_ROOT = Path(__file__).resolve().parents[3]
LISTING_ID = "116273255"
LISTING_URL = (
    "https://www.property24.com/for-sale/carlswald-north-estate/midrand/gauteng/12743/116273255"
)
DATASET_ID = COMPLETE_CARLSWALD_NORTH
HYBRID_JSON = REPO_ROOT / "data/investigations/hybrid_listing_pool_geometry_v1/latest.json"
OUT_DIR = REPO_ROOT / "data/investigations/blind_116273255_complete_estate"
PHOTOS_DIR = OUT_DIR / "photos"
FREEZE_PATH = OUT_DIR / "freeze.json"
ALL_CANDIDATES_PATH = OUT_DIR / "all_candidates.json"
PANELS_DIR = OUT_DIR / "panels"
PARCEL_CORNER_JSONL = (
    REPO_ROOT / "data/investigations/corner_stand_detection_v1/parcel_corner_records.jsonl"
)
GT_PATH = OUT_DIR / "ground_truth.json"
DETECTOR_PATH = OUT_DIR / "detector_true_erf.json"
REPORT_PATH = OUT_DIR / "REPORT.md"
FROZEN_001_GIS = REPO_ROOT / "data/gis" / f"{FROZEN_CARLSWALD_NORTH_001}.json"
FROZEN_001_INVENTORY = (
    REPO_ROOT / "data/estate_inventory" / FROZEN_CARLSWALD_NORTH_001 / "current.jsonl"
)
FROZEN_001_GIS_SHA256 = "1bab3126fdfa9d397857f67f2d0cb65ddc410fc5d82afaf1a823c63018f56608"
FROZEN_001_INVENTORY_SHA256 = "3bc02c09c293d011b8f2d866b2075e3e9863cc9af9db5c054faa0dc722aca861"

STAND_LEAK_RE = re.compile(
    r"(?i)\bstand\s*(?:no\.?|number|#)?\s*[:.]?\s*[0-9]+(?:/[0-9]+)?[A-Z]?\b"
)
ERF_LEAK_RE = re.compile(
    r"(?i)\berf\s*(?:no\.?|number|#)?\s*[:.]?\s*[0-9]+(?:/[0-9]+)?[A-Z]?\b"
)
STREET_RE = re.compile(
    r"(?i)\b\d{1,5}[A-Za-z]?\s+[A-Za-z][A-Za-z0-9'\-]*(?:\s+[A-Za-z][A-Za-z0-9'\-]*){0,4}"
    r"\s+(?:street|st\.?|road|rd\.?|drive|dr\.?|close|avenue|ave\.?|way|crescent|cres\.?)\b"
)
POOL_TEXT_RE = re.compile(
    r"(?i)\b(?:private\s+pool|l-?shaped\s+pool|swimming\s+pool|pool)\b"
)
NO_POOL_TEXT_RE = re.compile(
    r"(?i)\b(?:no\s+(?:private\s+|swimming\s+)?pool|without\s+(?:a\s+)?(?:swimming\s+)?pool|pool-?less)\b"
)
HYBRID_INTERESTING = frozenset(
    {
        "pool_overview",
        "elevated_exterior",
        "ground_level_exterior",
        "aerial_near_nadir",
        "pool_closeup",
        "garden_only",
    }
)
FEATURE_TERMS = (
    "private pool",
    "l-shaped pool",
    "l shaped pool",
    "swimming pool",
    "covered patio",
    "timber deck",
    "double garage",
    "paved driveway",
    "landscaped",
    "mature garden",
)
AERIAL_SCENES = frozenset({"aerial"})
EXTERIOR_SCENES = frozenset({"front_elevation", "rear_elevation", "contextual", "driveway_access"})
POOL_SCENES = frozenset({"pool_garden"})
DRIVEWAY_SCENES = frozenset({"driveway_access"})
GARDEN_SCENES = frozenset({"contextual", "pool_garden"})


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_dumps(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def redact_identity(text: str | None) -> str:
    if not text:
        return ""
    cleaned = STAND_LEAK_RE.sub("[STAND_REDACTED]", text)
    cleaned = ERF_LEAK_RE.sub("[ERF_REDACTED]", cleaned)
    cleaned = STREET_RE.sub("[STREET_REDACTED]", cleaned)
    cleaned = re.sub(r"(?is)<title>.*?</title>", "<title>[TITLE_REDACTED]</title>", cleaned)
    return cleaned


def _font(size: int = 14) -> ImageFont.ImageFont:
    path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    return ImageFont.truetype(str(path), size) if path.is_file() else ImageFont.load_default()


def load_gis_002(path: Path | None = None) -> dict[str, Any]:
    return load_complete_dataset(path or COMPLETE_002_PATH)


def load_inventory_002(root: Path | None = None) -> list[dict[str, Any]]:
    return load_inventory_records(DATASET_ID, root=root)


def load_hybrid_block(listing_id: str = LISTING_ID) -> dict[str, Any]:
    payload = json.loads(HYBRID_JSON.read_text(encoding="utf-8"))
    for block in payload["listings"]:
        if block["listing_id"] == listing_id:
            return block
    raise KeyError(listing_id)


def extract_hybrid_block(
    listing_id: str,
    photos: Mapping[str, bytes],
    *,
    dest: Path | None = None,
) -> dict[str, Any]:
    """Run frozen Hybrid Pool Geometry v1 on this listing. Does not retune Hybrid."""
    from backend.gis.estate_ags_matching.hybrid_listing_pool_geometry_v1 import (
        combine_listing_frames,
        extract_frame_geometry,
        frame_public,
    )
    from backend.gis.estate_ags_matching.listing_evidence_v2 import (
        clip_viewpoint_scores,
        observe_listing_frame,
    )
    from backend.gis.estate_ags_matching.pool_boundary_v1 import SKIP_VIEWS

    frozen = []
    frames = []
    for media_id, body in sorted(photos.items()):
        image = Image.open(io.BytesIO(body)).convert("RGB")
        scores = clip_viewpoint_scores(image)
        observed = observe_listing_frame(media_id, body, clip_scores=scores)
        frozen.append(observed)
        if observed.viewpoint in SKIP_VIEWS:
            continue
        if observed.viewpoint not in HYBRID_INTERESTING:
            continue
        frames.append(extract_frame_geometry(media_id, body, viewpoint=observed.viewpoint))
    listing = combine_listing_frames(frames)
    block = {
        "listing_id": listing_id,
        "n_photos": len(photos),
        "viewpoint_counts": dict(Counter(item.viewpoint for item in frozen)),
        "n_extracted": len(frames),
        "source_counts": dict(Counter(item.source for item in frames)),
        "listing": listing,
        "dark_overview_probe": [],
        "frames": [frame_public(item) for item in frames],
        "extracted_fresh_with_frozen_hybrid_v1": True,
        "hybrid_v1_modified": False,
        "listing_specific_control_suffixes": False,
        "_frame_objects": frames,
    }
    if dest is not None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        public = {key: val for key, val in block.items() if key != "_frame_objects"}
        dest.write_text(json.dumps(public, indent=2) + "\n", encoding="utf-8")
    return block


def scan_prior_listing_artifacts(listing_id: str) -> dict[str, Any]:
    """Path inventory only. Does not read prior ranking/GT payloads for this listing."""
    hits: list[str] = []
    current_token = f"blind_{listing_id}_complete_estate"
    roots = [REPO_ROOT / "data"]
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob(f"*{listing_id}*"):
            try:
                rel = str(path.relative_to(REPO_ROOT))
            except ValueError:
                continue
            if current_token in rel:
                continue
            hits.append(rel)
    hybrid_has = False
    if HYBRID_JSON.is_file():
        payload = json.loads(HYBRID_JSON.read_text(encoding="utf-8"))
        hybrid_has = any(str(block.get("listing_id")) == listing_id for block in payload.get("listings") or [])
    return {
        "listing_id": listing_id,
        "workspace_path_hits_excluded": hits,
        "frozen_hybrid_json_contains_listing": hybrid_has,
        "frozen_hybrid_json_used_as_ranking_input": False,
        "hybrid_source": "extract_frame_geometry_frozen_hybrid_v1_fresh",
        "excluded_from_ranking_input": True,
    }


def load_or_extract_hybrid_block(
    listing_id: str,
    photos: Mapping[str, bytes] | None = None,
    *,
    dest: Path | None = None,
    ignore_frozen_hybrid_json: bool = False,
) -> dict[str, Any]:
    if not ignore_frozen_hybrid_json:
        try:
            return load_hybrid_block(listing_id)
        except KeyError:
            pass
    if not photos:
        raise KeyError(listing_id)
    return extract_hybrid_block(listing_id, photos, dest=dest)


def load_os_payload(stand: str) -> dict[str, Any]:
    complete = os_json_path_for(stand, COMPLETE_OS_DIR)
    frozen = os_json_path_for(stand, DEFAULT_OS_DIR)
    if complete.is_file():
        return json.loads(complete.read_text(encoding="utf-8"))
    if frozen.is_file():
        return json.loads(frozen.read_text(encoding="utf-8"))
    return {}


def load_parcel_corner_records(path: Path | None = None) -> list[dict[str, Any]]:
    dest = Path(path) if path is not None else PARCEL_CORNER_JSONL
    if not dest.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in dest.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        rows.append(json.loads(text))
    return rows


def listing_text_for_gates(acquisition: Mapping[str, Any]) -> str:
    """In-memory listing title/description only. Not written to freeze.json."""
    listing = acquisition.get("listing")
    if listing is None:
        return ""
    parts = [getattr(listing, "title", None), getattr(listing, "description", None)]
    return " ".join(str(part) for part in parts if part)


def listing_corner_viewpoints(
    hybrid_block: Mapping[str, Any],
    photo_classes: Mapping[str, Any],
) -> dict[str, str]:
    views = {str(mid): str(scene) for mid, scene in (photo_classes.get("scenes") or {}).items()}
    for frame in hybrid_block.get("frames") or []:
        media_id = str(frame.get("media_id") or "")
        viewpoint = frame.get("viewpoint")
        if media_id and viewpoint:
            views[media_id] = str(viewpoint)
    return views


def overlay_os_payload_with_pov(
    payload: Mapping[str, Any],
    gis_geometry: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Re-evaluate a copy of frozen OS JSON. Does not write OS files."""
    from backend.gis.estate_ags_matching.pool_object_validation_v1 import validate_os_payload

    copy = deepcopy(dict(payload))
    validation = validate_os_payload(copy, gis_geometry=gis_geometry)
    pov = validation.to_dict() if hasattr(validation, "to_dict") else dict(validation)
    pool = dict(copy.get("pool") or {})
    frozen_status = pool.get("status")
    overlay_status = pov.get("final_status") or "UNKNOWN"
    pool["status"] = overlay_status
    copy["pool"] = pool
    signals = pov.get("signals") or {}
    if not isinstance(signals, Mapping):
        signals = {}
    summary = {
        "frozen_os_status": frozen_status,
        "pov_status": overlay_status,
        "object_role": pov.get("object_role"),
        "principal_pool_candidate": pov.get("principal_pool_candidate"),
        "reason_codes": list(pov.get("reason_codes") or []),
        "contour_retained": pov.get("contour_retained"),
        "parcel_containment": signals.get("parcel_containment"),
        "neighbour_risk": signals.get("neighbour_risk"),
        "yard_context": signals.get("yard_context"),
    }
    return copy, summary


def listing_pov_public(hybrid_block: Mapping[str, Any]) -> dict[str, Any]:
    frames = list(hybrid_block.get("frames") or [])
    listing_meta = hybrid_block.get("listing") or {}
    per_frame = []
    for frame in frames:
        pov = frame.get("pool_object_validation") or {}
        per_frame.append(
            {
                "media_id": frame.get("media_id"),
                "viewpoint": frame.get("viewpoint"),
                "source": frame.get("source"),
                "scoring_ready": frame.get("scoring_ready"),
                "principal_pool_candidate": frame.get("principal_pool_candidate"),
                "object_role": frame.get("object_role"),
                "pov_status": pov.get("final_status"),
                "pov_confidence": pov.get("final_pool_object_confidence"),
                "reason_codes": pov.get("reason_codes"),
            }
        )
    chosen_id = listing_meta.get("chosen_id")
    chosen = next((row for row in per_frame if row.get("media_id") == chosen_id), None)
    fingerprint = "NO_SHAPE_SIGNAL"
    if chosen_id and chosen is not None:
        fingerprint = "official_hybrid_fingerprint"
    return {
        "official_fingerprint": fingerprint,
        "official_pick_order": ["object_identity", "cross_frame_agreement", "geometry", "viewpoint"],
        "chosen_id": chosen_id,
        "chosen_source": listing_meta.get("chosen_source"),
        "chosen_viewpoint": listing_meta.get("chosen_viewpoint"),
        "chosen_reason": listing_meta.get("frame_selection_reason") or listing_meta.get("chosen_reason"),
        "chosen_pov": None if chosen is None else chosen,
        "n_principal_candidates": listing_meta.get("n_principal_candidates"),
        "per_frame": per_frame,
        "note": "Aerial does not win merely because it is aerial. Official pick is listing-side POV v1.",
    }


def listing_corner_public(evidence) -> dict[str, Any]:
    payload = evidence.to_dict() if hasattr(evidence, "to_dict") else dict(evidence)
    frames = []
    for row in payload.get("frames") or []:
        frames.append(
            {
                "media_id": row.get("media_id"),
                "viewpoint": row.get("viewpoint"),
                "visual_yes": row.get("visual_yes"),
                "visual_confidence": row.get("visual_confidence"),
                "reason": row.get("reason"),
                "strong_sides": row.get("strong_sides"),
                "two_heading_axes": row.get("two_heading_axes"),
            }
        )
    return {
        "listing_corner": payload.get("listing_corner") or payload.get("classification"),
        "confidence": payload.get("confidence"),
        "evidence_source": payload.get("evidence_source"),
        "frame_ids": payload.get("frame_ids"),
        "visual_reason": payload.get("visual_reason"),
        "high_confidence": payload.get("high_confidence"),
        "exceptional_non_corner": payload.get("exceptional_non_corner"),
        "positive_non_corner_evidence": payload.get("positive_non_corner_evidence"),
        "aerial_evidence": payload.get("aerial_evidence"),
        "video_evidence": payload.get("video_evidence"),
        "contradiction_flags": payload.get("contradiction_flags"),
        "n_text_evidence": len(payload.get("text_evidence") or []),
        "frames": frames,
        "note": "Listing media/text only. Street and stand identity are not inputs.",
    }


def corner_gate_public(result) -> dict[str, Any]:
    payload = result.to_dict()
    payload.pop("survivor_parcel_ids", None)
    payload.pop("removed_parcel_ids", None)
    payload.pop("unresolved_parcel_ids", None)
    payload["final_survivor_count"] = result.total_survivors
    payload["starting_candidates"] = result.starting_count
    payload["percentage_reduction"] = result.pct_reduction
    payload["gate_action"] = (
        "high_confidence_listing_yes_drop_confident_parcel_no"
        if result.listing_high_confidence and result.listing_corner == "YES"
        else "neutral_retain_pool_gate_survivors"
    )
    return payload


def candidate_pov_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    counts = Counter(str(row.get("candidate_pov_status") or "missing") for row in rows)
    return {
        "CONFIRMED": int(counts.get("CONFIRMED", 0)),
        "UNKNOWN": int(counts.get("UNKNOWN", 0)),
        "REJECTED": int(counts.get("REJECTED", 0)),
        "missing": int(counts.get("missing", 0)),
        "n_ranked": len(rows),
        "os_json_rewritten": False,
    }


def ranking_quality_report(
    rows: Sequence[Mapping[str, Any]],
    *,
    listing_shape_available: bool,
) -> dict[str, Any]:
    ordered = sorted(rows, key=lambda row: int(row.get("hybrid_v2_rank") or row.get("rank") or 0))
    sep = ranking_separation(ordered)
    shape = shape_discrimination(ordered)
    n_genuine_shape = sum(
        1 for row in ordered if row.get("hybrid_v2_shape_v2") is not None or row.get("shape_v2") is not None
    )
    n_shape_ge_80 = 0
    for row in ordered:
        raw = row.get("hybrid_v2_shape_v2")
        if raw is None:
            raw = row.get("shape_v2")
        if raw is not None and float(raw) >= 0.80:
            n_shape_ge_80 += 1
    top1 = ordered[0] if ordered else {}
    genuine, padding = _contrib_split(top1) if top1 else ([], [])
    genuine_sum = round(sum(float(item["contrib"]) for item in genuine), 4)
    padding_sum = round(sum(float(item["contrib"]) for item in padding), 4)
    total = genuine_sum + padding_sum
    evidence_pct = None if not total else round(100.0 * genuine_sum / total, 2)
    padding_pct = None if not total else round(100.0 * padding_sum / total, 2)
    if not listing_shape_available or n_genuine_shape == 0:
        quality_class = "NO_SHAPE_SIGNAL"
    else:
        quality_class = str(shape.get("discrimination_class") or "WEAK")
    return {
        "class": quality_class,
        "listing_shape_available": listing_shape_available,
        "n_genuine_shape": n_genuine_shape,
        "n_shape_v2_ge_0_80": n_shape_ge_80,
        "score_1": sep.get("top1_score"),
        "score_2": sep.get("top2_score"),
        "score_5": sep.get("top5_score"),
        "score_10": sep.get("top10_score"),
        "score_20": sep.get("top20_score"),
        "gap_1_2": sep.get("gap_1_2"),
        "gap_1_5": sep.get("gap_1_5"),
        "gap_1_10": sep.get("gap_1_10"),
        "gap_1_20": sep.get("gap_1_20"),
        "top1_evidence_pct": evidence_pct,
        "top1_padding_pct": padding_pct,
        "discrimination_mode": shape.get("discrimination_mode"),
        "note": "Reporting only. Does not change Scoring v2.",
    }


def parse_floor_size(html: str) -> float | None:
    redacted = redact_identity(html)
    patterns = (
        r"(?is)floor\s*size[^0-9]{0,80}([\d\s]+)\s*m",
        r"(?is)floorSize[^0-9]{0,40}([\d.]+)",
        r"(?is)\"floor_size\"[^0-9]{0,20}([\d.]+)",
    )
    for pattern in patterns:
        match = re.search(pattern, redacted)
        if match:
            return float(re.sub(r"\s+", "", match.group(1)))
    return None


def parse_bed_bath(html: str) -> dict[str, float | None]:
    redacted = redact_identity(html)
    beds = re.search(r"(?i)(\d+)\s*bedroom", redacted)
    baths = re.search(r"(?i)(\d+(?:\.\d+)?)\s*bathroom", redacted)
    return {
        "bedrooms": None if beds is None else int(beds.group(1)),
        "bathrooms": None if baths is None else float(baths.group(1)),
    }


def feature_hits(text: str) -> list[str]:
    lowered = redact_identity(text).lower()
    return [term for term in FEATURE_TERMS if term in lowered]


def acquire_listing(
    *,
    url: str = LISTING_URL,
    listing_id: str = LISTING_ID,
    photos_dir: Path = PHOTOS_DIR,
    html: str | None = None,
    force_fresh_photos: bool = False,
) -> dict[str, Any]:
    if html is None:
        import httpx

        with httpx.Client(timeout=40.0, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
            response = client.get(url)
            response.raise_for_status()
            raw_html = response.text
        listing = parse_listing_html(raw_html, url, listing_id)
    else:
        listing = parse_listing_html(html, url, listing_id)
        raw_html = html
    redacted = redact_identity(raw_html)
    photos_dir.mkdir(parents=True, exist_ok=True)
    if force_fresh_photos:
        for path in photos_dir.glob(f"{listing_id}-*.jpg"):
            path.unlink()
    existing_before = {
        path.name
        for path in photos_dir.glob(f"{listing_id}-*.jpg")
        if path.is_file() and path.stat().st_size > 2000
    }
    bodies = download_images(listing.image_urls, photos_dir, listing_id)
    reused = sum(1 for media_id in bodies if f"{media_id}.jpg" in existing_before)
    downloaded_fresh = len(bodies) - reused
    floor = parse_floor_size(raw_html)
    beds = parse_bed_bath(raw_html)
    hits = feature_hits(" ".join(filter(None, [listing.description, redacted])))
    return {
        "listing_id": listing_id,
        "listing_url": url,
        "property_type": listing.property_type,
        "estate": listing.estate,
        "erf_size_sqm": listing.stand_size_sqm,
        "floor_size_sqm": floor,
        "bedrooms": beds["bedrooms"],
        "bathrooms": beds["bathrooms"],
        "listing_photo_count": len(listing.image_urls),
        "photos_downloaded": len(bodies),
        "photos_downloaded_fresh": downloaded_fresh,
        "photos_reused_from_disk": reused,
        "photos_failed": max(0, len(listing.image_urls) - len(bodies)),
        "acquisition_fresh": reused == 0 and downloaded_fresh > 0,
        "force_fresh_photos": force_fresh_photos,
        "media_source": "fresh_download" if reused == 0 else "mixed_disk_reuse",
        "video_available": bool(listing.video_urls),
        "video_count": len(listing.video_urls),
        "feature_hits": hits,
        "pool_text_present": bool(POOL_TEXT_RE.search(redacted)) and not bool(NO_POOL_TEXT_RE.search(redacted)),
        "no_pool_text_present": bool(NO_POOL_TEXT_RE.search(redacted)),
        "identity_redacted": True,
        "title_omitted": True,
        "street_omitted": True,
        "stand_omitted": True,
        "photos": bodies,
        "listing": listing,
    }


def classify_listing_photos(photos: Mapping[str, bytes]) -> dict[str, Any]:
    scenes: dict[str, str] = {}
    for media_id, body in sorted(photos.items()):
        image = Image.open(io.BytesIO(body)).convert("RGB")
        scenes[media_id] = classify_scene(image)
    counts = dict(Counter(scenes.values()))
    return {
        "scenes": scenes,
        "scene_counts": counts,
        "exterior_photo_count": sum(1 for scene in scenes.values() if scene in EXTERIOR_SCENES),
        "pool_photo_count": sum(1 for scene in scenes.values() if scene in POOL_SCENES),
        "driveway_photo_count": sum(1 for scene in scenes.values() if scene in DRIVEWAY_SCENES),
        "garden_photo_count": sum(1 for scene in scenes.values() if scene in GARDEN_SCENES),
        "interior_photo_count": sum(1 for scene in scenes.values() if scene == "interior"),
        "useful_driveway_garage_views": [
            mid for mid, scene in scenes.items() if scene in DRIVEWAY_SCENES
        ],
        "useful_garden_patio_views": [
            mid for mid, scene in scenes.items() if scene in GARDEN_SCENES
        ],
        "useful_pool_views": [mid for mid, scene in scenes.items() if scene in POOL_SCENES],
        "useful_exterior_views": [mid for mid, scene in scenes.items() if scene in EXTERIOR_SCENES],
    }


def observe_pool_media(photos: Mapping[str, bytes], scenes: Mapping[str, str]) -> dict[str, Any]:
    observations = []
    preferred = [
        media_id
        for media_id, scene in sorted(scenes.items())
        if scene in {"pool_garden", "rear_elevation", "aerial", "front_elevation"}
    ]
    if not preferred:
        preferred = [media_id for media_id, scene in sorted(scenes.items()) if scene != "interior"]
    for media_id in preferred[:8]:
        body = photos.get(media_id)
        if not body:
            continue
        observations.append(observe_pool_object(media_id, body))
    detected = [obs for obs in observations if obs.pool_object_detected]
    l_hits = [
        obs
        for obs in detected
        if (obs.l_geometry or {}).get("consistent_with_l_planform")
        or (obs.l_geometry or {}).get("two_dominant_arms")
    ]
    return {
        "n_observed": len(observations),
        "n_pool_object_detected": len(detected),
        "detected_ids": [obs.media_id for obs in detected],
        "n_l_geometry": len(l_hits),
        "observations": [observation_public(obs) for obs in observations if obs.pool_object_detected],
    }


def classify_listing_pool_status(
    acquisition: Mapping[str, Any],
    hybrid_block: Mapping[str, Any],
    photo_classes: Mapping[str, Any],
    object_obs: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    evidence: list[str] = []
    text_yes = bool(acquisition.get("pool_text_present") or "private pool" in acquisition.get("feature_hits") or [])
    text_blob = " ".join(str(item) for item in (acquisition.get("feature_hits") or []))
    text_no = bool(NO_POOL_TEXT_RE.search(text_blob)) or bool(acquisition.get("no_pool_text_present"))
    if text_yes:
        evidence.append("listing_text_mentions_pool")
    if "l-shaped pool" in (acquisition.get("feature_hits") or []) or "l shaped pool" in (
        acquisition.get("feature_hits") or []
    ):
        evidence.append("listing_text_mentions_l_shaped_pool")
    hybrid_ready = int((hybrid_block.get("listing") or {}).get("n_scoring_ready") or 0)
    hybrid_pool_views = int((hybrid_block.get("viewpoint_counts") or {}).get("pool_overview") or 0)
    hybrid_pool_views += int((hybrid_block.get("viewpoint_counts") or {}).get("pool_closeup") or 0)
    if hybrid_ready >= 1:
        evidence.append(f"hybrid_v1_scoring_ready_frames={hybrid_ready}")
    if hybrid_pool_views >= 1:
        evidence.append(f"hybrid_v1_pool_viewpoints={hybrid_pool_views}")
    scene_pool = int(photo_classes.get("pool_photo_count") or 0)
    if scene_pool >= 1:
        evidence.append(f"clip_scene_pool_garden_photos={scene_pool}")
    object_n = 0 if object_obs is None else int(object_obs.get("n_pool_object_detected") or 0)
    if object_n >= 1:
        evidence.append(f"listing_pool_object_detected={object_n}")
    media_yes = hybrid_ready >= 1 or scene_pool >= 1 or object_n >= 1 or hybrid_pool_views >= 1
    if text_yes and media_yes:
        status = "YES"
        reason = "text_and_media_independently_support_private_pool"
    elif media_yes:
        status = "YES"
        reason = "listing_media_pool_detected_without_relying_on_ground_truth"
    elif text_yes:
        status = "YES"
        reason = "listing_text_pool_without_media_confirmation"
    elif text_no and not media_yes:
        status = "NO"
        reason = "listing_text_denies_pool_and_media_do_not_support_pool"
    else:
        status = "UNKNOWN"
        reason = "insufficient_listing_pool_evidence"
    return {
        "listing_pool_status": status,
        "reason": reason,
        "evidence": evidence,
        "text_yes": text_yes,
        "text_no": text_no,
        "media_yes": media_yes,
        "colour_used": False,
        "ground_truth_used": False,
    }


def listing_fingerprint(hybrid_block: Mapping[str, Any], photo_classes: Mapping[str, Any]) -> dict[str, Any]:
    evidence = listing_evidence_from_hybrid_block(dict(hybrid_block))
    chosen = evidence.get("chosen_frame") or {}
    geom = ((chosen.get("dominant") or {}).get("geometry") or {})
    relation = chosen.get("component_relation") or {}
    descriptors = chosen.get("descriptors") or {}
    qualitative = {
        "pool_geometry_priority": [
            "pool geometry",
            "pool-to-house relationship",
            "patio/deck relationship",
            "roof footprint/layout",
            "driveway orientation",
            "garage location/orientation",
            "garden/open-ground configuration",
            "exterior building massing",
        ],
        "hybrid_chosen_id": evidence.get("chosen_id"),
        "hybrid_chosen_source": evidence.get("chosen_source"),
        "hybrid_chosen_viewpoint": evidence.get("chosen_viewpoint"),
        "l_shape_or_bends": bool(int(geom.get("n_major_indents") or 0) >= 1 or descriptors.get("concavity")),
        "n_major_indents": geom.get("n_major_indents"),
        "aspect_ratio": geom.get("aspect_ratio"),
        "orientation_deg_oblique": geom.get("orientation_deg"),
        "compactness": geom.get("compactness"),
        "solidity": geom.get("solidity"),
        "component_count": relation.get("component_count") or descriptors.get("component_count"),
        "adjacent_second_arm": relation.get("adjacent"),
        "pool_to_house_vector": "omitted_not_viewpoint_compatible_in_frozen_hybrid_v1",
        "pool_distance_from_building": "omitted_not_viewpoint_compatible_in_frozen_hybrid_v1",
        "patio_deck_alignment": "hybrid_clip_deck_on_chosen_frame_not_used_as_colour_rank_signal",
        "roof_layout": "not_a_hybrid_v1_scoring_term",
        "driveway_orientation": "CLIP exterior/driveway scenes only; not a Scoring v2 spatial term",
        "colour_used_in_ranking": False,
        "photo_scene_counts": photo_classes.get("scene_counts"),
        "hybrid_viewpoint_counts": hybrid_block.get("viewpoint_counts"),
        "available": {
            "pool_geometry": bool(evidence.get("fingerprint") and evidence["fingerprint"].present),
            "pool_to_house_spatial": False,
            "listing_aerial": bool((photo_classes.get("scene_counts") or {}).get("aerial")),
            "listing_exterior": bool(photo_classes.get("exterior_photo_count")),
            "driveway_views": bool(photo_classes.get("driveway_photo_count")),
            "garden_views": bool(photo_classes.get("garden_photo_count")),
            "hybrid_scoring_ready": bool(evidence.get("scoring_ready_ids")),
        },
        "unavailable": [
            key
            for key, ok in {
                "pool_geometry": bool(evidence.get("fingerprint") and evidence["fingerprint"].present),
                "pool_to_house_spatial": False,
                "nadir_relative_area": False,
                "roof_footprint_as_scoring_term": False,
                "driveway_as_scoring_v2_spatial": False,
            }.items()
            if not ok
        ],
        "signal_classes": {
            "measured": [
                key
                for key, ok in {
                    "pool_geometry": bool(evidence.get("fingerprint") and evidence["fingerprint"].present),
                    "listing_exterior": bool(photo_classes.get("exterior_photo_count")),
                    "driveway_views": bool(photo_classes.get("driveway_photo_count")),
                    "garden_views": bool(photo_classes.get("garden_photo_count")),
                    "hybrid_scoring_ready": bool(evidence.get("scoring_ready_ids")),
                }.items()
                if ok
            ],
            "unavailable": [
                "pool_to_house_spatial",
                "nadir_relative_area",
                "roof_footprint_as_scoring_term",
                "driveway_as_scoring_v2_spatial",
            ]
            + (
                []
                if (photo_classes.get("scene_counts") or {}).get("aerial")
                else ["listing_aerial"]
            ),
            "neutral_default_in_ranking_not_fingerprint": [
                "spatial_v2=0.5_when_hybrid_omits_pool_house",
                "aerial=0.5_when_no_listing_aerial",
                "gis=0.5_constant",
            ],
        },
    }
    return {
        "hybrid_evidence": {
            **{
                key: val
                for key, val in evidence.items()
                if key not in {"fingerprint", "listing_shape", "chosen_frame", "ready_frames"}
            },
            "fingerprint": public_fingerprint(evidence["fingerprint"]),
            "listing_shape": public_shape(evidence["listing_shape"]),
        },
        "qualitative": qualitative,
        "fingerprint_obj": evidence["fingerprint"]
        or PoolGeometryFingerprint(present=False, unknown=True, notes=["no_scoring_ready_hybrid_frame"]),
        "listing_shape_obj": evidence["listing_shape"],
        "evidence_obj": evidence,
    }


WATCH_REPEAT_STANDS = ("605", "444", "573", "446", "401")
SIMILAR_SHAPE_V2 = 0.80
WEAK_SHAPE_V2 = 0.60


def _relative_limb_lengths(norm_xy: Sequence[Sequence[float]] | None) -> dict[str, Any] | None:
    if not norm_xy:
        return None
    pts = np.asarray(norm_xy, dtype=np.float64)
    if pts.ndim != 2 or len(pts) < 5:
        return None
    plus_x = float(max(pts[:, 0].max(), 0.0))
    minus_x = float(max(-pts[:, 0].min(), 0.0))
    plus_y = float(max(pts[:, 1].max(), 0.0))
    minus_y = float(max(-pts[:, 1].min(), 0.0))
    arms = {
        "plus_x": round(plus_x, 4),
        "minus_x": round(minus_x, 4),
        "plus_y": round(plus_y, 4),
        "minus_y": round(minus_y, 4),
    }
    ordered = sorted(arms.values(), reverse=True)
    longest = ordered[0] or 1e-6
    return {
        "extents": arms,
        "longest_to_second": round(ordered[0] / max(ordered[1], 1e-6), 3),
        "relative_to_longest": {key: round(val / longest, 3) for key, val in arms.items()},
    }


def _n_major_directional_changes(norm_xy: Sequence[Sequence[float]] | None, threshold_deg: float = 40.0) -> int:
    if not norm_xy:
        return 0
    pts = np.asarray(norm_xy, dtype=np.float64)
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


def _planform_characteristics(desc: Mapping[str, Any] | None, geom: Mapping[str, Any] | None) -> dict[str, Any]:
    desc = dict(desc or {})
    geom = dict(geom or {})
    n_indents = int(desc.get("n_major_indents") or geom.get("n_major_indents") or 0)
    solidity = float(desc.get("solidity") or geom.get("solidity") or 1.0)
    elongation = float(desc.get("elongation") or geom.get("aspect_ratio") or 1.0)
    circularity = float(desc.get("circularity") or 0.0)
    compactness = float(geom.get("compactness") or circularity)
    labels = []
    if n_indents >= 2 and solidity < 0.88:
        labels.append("T_or_multi_indent")
    if n_indents == 1 and solidity < 0.90 and elongation < 3.8:
        labels.append("L_or_indented")
    if elongation >= 2.2 and solidity >= 0.85:
        labels.append("elongated")
    if circularity >= 0.55 and solidity >= 0.90:
        labels.append("compact_rounded")
    if compactness >= 0.55 and solidity < 0.90 and n_indents == 0:
        labels.append("kidney_or_curved")
    if solidity < 0.86 or (n_indents >= 1 and circularity < 0.45):
        labels.append("freeform")
    if not labels:
        labels.append("simple")
    return {
        "labels": labels,
        "primary": labels[0],
        "l_shaped": "L_or_indented" in labels,
        "t_shaped": "T_or_multi_indent" in labels,
        "kidney": "kidney_or_curved" in labels,
        "freeform": "freeform" in labels,
        "elongated": "elongated" in labels,
    }


def distinctive_pool_fingerprint(fingerprint: Mapping[str, Any]) -> dict[str, Any]:
    """Reporting-only distinctive pool contour metrics. Not a ranking input change."""
    evidence = fingerprint.get("hybrid_evidence") or {}
    qualitative = fingerprint.get("qualitative") or {}
    listing_shape = fingerprint.get("listing_shape_obj") or {}
    chosen = (fingerprint.get("evidence_obj") or {}).get("chosen_frame") or {}
    geom = ((chosen.get("dominant") or {}).get("geometry") or {})
    fp = evidence.get("fingerprint") or {}
    norm_xy = list(listing_shape.get("norm_xy") or [])
    n_changes = _n_major_directional_changes(norm_xy)
    limbs = _relative_limb_lengths(norm_xy)
    planform = _planform_characteristics(listing_shape, geom)
    convexity = listing_shape.get("solidity")
    if convexity is None:
        convexity = geom.get("solidity") or fp.get("convexity")
    return {
        "present": bool(fp.get("present") and listing_shape),
        "shape_class": fp.get("shape_class") or "unknown",
        "aspect_ratio": listing_shape.get("elongation") or geom.get("aspect_ratio") or fp.get("aspect_ratio"),
        "hybrid_aspect_ratio": geom.get("aspect_ratio"),
        "major_bends_indents": listing_shape.get("n_major_indents"),
        "max_indent": listing_shape.get("max_indent"),
        "solidity": listing_shape.get("solidity"),
        "convexity": convexity,
        "concavity": listing_shape.get("n_major_indents"),
        "circularity": listing_shape.get("circularity"),
        "compactness": geom.get("compactness") or fp.get("compactness"),
        "orientation_deg_oblique_image": geom.get("orientation_deg"),
        "orientation_note": "hybrid_image_orientation_is_oblique_not_nadir_estate_bearing",
        "n_corners": listing_shape.get("n_corners"),
        "n_major_directional_changes": n_changes,
        "sharp_frac": listing_shape.get("sharp_frac"),
        "turn_std": listing_shape.get("turn_std"),
        "radial_cv": listing_shape.get("radial_cv"),
        "symmetry": listing_shape.get("symmetry"),
        "relative_limb_lengths": limbs,
        "l_t_kidney_freeform": planform,
        "normalized_contour": [[round(float(x), 4), round(float(y), 4)] for x, y in norm_xy],
        "normalized_contour_point_count": len(norm_xy),
        "pool_to_house_relationship": "not_genuinely_measurable_in_frozen_hybrid_v1",
        "chosen_id": qualitative.get("hybrid_chosen_id") or evidence.get("chosen_id"),
        "chosen_source": qualitative.get("hybrid_chosen_source") or evidence.get("chosen_source"),
        "chosen_viewpoint": qualitative.get("hybrid_chosen_viewpoint") or evidence.get("chosen_viewpoint"),
        "colour_used": False,
        "used_as_ranking_input_change": False,
        "metrics_source": "frozen_hybrid_v1_chosen_frame_plus_scoring_v2_contour_descriptors",
    }


def shape_discrimination(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Does shape_v2 isolate a small subset, or only re-cluster YES-pool stands?"""
    ordered = sorted(rows, key=lambda row: int(row.get("hybrid_v2_rank") or row.get("rank") or 0))[:20]
    scores = []
    for row in ordered:
        raw = row.get("hybrid_v2_shape_v2")
        if raw is None:
            raw = row.get("shape_v2")
        scores.append(None if raw is None else float(raw))
    measured = [val for val in scores if val is not None]
    top1_shape = scores[0] if scores else None
    top2_shape = scores[1] if len(scores) > 1 else None
    top5_measured = [val for val in scores[:5] if val is not None]
    similar = [
        {
            "rank": row.get("hybrid_v2_rank") or row.get("rank"),
            "stand_number": row.get("stand_number"),
            "shape_v2": score,
        }
        for row, score in zip(ordered, scores)
        if score is not None and score >= SIMILAR_SHAPE_V2
    ]
    weak_high = [
        {
            "rank": row.get("hybrid_v2_rank") or row.get("rank"),
            "stand_number": row.get("stand_number"),
            "shape_v2": score,
            "final_score": row.get("hybrid_v2") if "hybrid_v2" in row else row.get("score"),
        }
        for row, score in zip(ordered, scores)
        if int(row.get("hybrid_v2_rank") or row.get("rank") or 99) <= 10
        and (score is None or score < WEAK_SHAPE_V2)
    ]
    spread_top5 = None
    if len(top5_measured) >= 2:
        spread_top5 = round(max(top5_measured) - min(top5_measured), 4)
    gap_1_2 = None
    if top1_shape is not None and top2_shape is not None:
        gap_1_2 = round(top1_shape - top2_shape, 4)
    n_similar = len(similar)
    if not measured:
        mode = "NO_SHAPE_SIGNAL"
        dclass = "WEAK"
    elif n_similar <= 3 and (spread_top5 or 0) >= 0.04 and (gap_1_2 or 0) >= 0.02:
        mode = "SMALL_SUBSET"
        dclass = "STRONG"
    elif n_similar >= 8 or (spread_top5 is not None and spread_top5 < 0.03):
        mode = "BROAD_CLUSTER"
        dclass = "BROAD_CLUSTER"
    else:
        mode = "PARTIAL_SEPARATION"
        dclass = "MODERATE"
    if dclass != "BROAD_CLUSTER" and (gap_1_2 is None or gap_1_2 < 0.01) and (spread_top5 is None or spread_top5 < 0.02):
        dclass = "WEAK"
    per_candidate = []
    for row, score in zip(ordered, scores):
        per_candidate.append(
            {
                "rank": row.get("hybrid_v2_rank") or row.get("rank"),
                "stand_number": row.get("stand_number"),
                "shape_v2": None if score is None else round(score, 4),
                "final_score": row.get("hybrid_v2") if "hybrid_v2" in row else row.get("score"),
                "inventory_pool_status": row.get("inventory_pool_status"),
                "similar_geometry": bool(score is not None and score >= SIMILAR_SHAPE_V2),
                "weak_geometry": score is None or score < WEAK_SHAPE_V2,
            }
        )
    return {
        "listing_vs_top20_shape_v2": per_candidate,
        "top1_shape_v2": None if top1_shape is None else round(top1_shape, 4),
        "top2_shape_v2": None if top2_shape is None else round(top2_shape, 4),
        "top1_top2_shape_gap": gap_1_2,
        "top1_top5_shape_spread": spread_top5,
        "n_genuinely_similar_geometry": n_similar,
        "similar_stands": similar,
        "n_high_rank_despite_weak_geometry": len(weak_high),
        "high_rank_weak_geometry": weak_high,
        "discrimination_mode": mode,
        "discrimination_class": dclass,
        "similar_threshold": SIMILAR_SHAPE_V2,
        "weak_threshold": WEAK_SHAPE_V2,
        "note": "Reporting only. Thresholds do not change Scoring v2.",
    }


def _draw_normalized_contour(
    norm_xy: Sequence[Sequence[float]] | None,
    *,
    size: int = 280,
    outline: tuple[int, int, int] = (80, 220, 255),
    title: str = "",
) -> Image.Image:
    canvas = Image.new("RGB", (size, size), (16, 16, 16))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((8, 8, size - 9, size - 9), outline=(50, 50, 50))
    if title:
        draw.text((12, 10), title, fill=(220, 220, 220), font=_font(13))
    if not norm_xy or len(norm_xy) < 3:
        draw.text((20, size // 2), "no contour", fill=(160, 160, 160), font=_font(14))
        return canvas
    pts = np.asarray(norm_xy, dtype=np.float64)
    margin = 28
    usable = size - 2 * margin
    xy = (pts + 1.05) / 2.10 * usable + margin
    poly = [(int(x), int(y)) for x, y in xy]
    draw.polygon(poly, outline=outline)
    cx, cy = float(xy[:, 0].mean()), float(xy[:, 1].mean())
    draw.ellipse((cx - 3, cy - 3, cx + 3, cy + 3), fill=outline)
    return canvas


def _overlay_norm_contour_on_image(
    image: Image.Image,
    contour: Sequence[Sequence[float]] | None,
    *,
    outline: tuple[int, int, int] = (80, 220, 255),
) -> Image.Image:
    out = image.convert("RGB")
    if not contour or len(contour) < 3:
        return out
    draw = ImageDraw.Draw(out)
    width, height = out.size
    pts = []
    arr = np.asarray(contour, dtype=np.float64)
    if float(np.nanmax(np.abs(arr))) <= 1.5:
        pts = [(int(float(x) * (width - 1)), int(float(y) * (height - 1))) for x, y in arr]
    else:
        pts = [(int(x), int(y)) for x, y in arr]
    if len(pts) >= 3:
        draw.line(pts + [pts[0]], fill=outline, width=3)
    return out


def draw_listing_contour_proof(
    fingerprint: Mapping[str, Any],
    photos: Mapping[str, bytes],
    dest: Path,
) -> str | None:
    distinctive = fingerprint.get("distinctive") or distinctive_pool_fingerprint(fingerprint)
    chosen_id = distinctive.get("chosen_id")
    listing_shape = fingerprint.get("listing_shape_obj") or {}
    chosen = (fingerprint.get("evidence_obj") or {}).get("chosen_frame") or {}
    contour_image = (chosen.get("dominant") or {}).get("contour_image") or chosen.get("contour_image")
    photo = None
    if chosen_id and chosen_id in photos:
        photo = Image.open(io.BytesIO(photos[chosen_id])).convert("RGB")
        photo.thumbnail((480, 360))
        photo = _overlay_norm_contour_on_image(photo, contour_image)
    else:
        photo = Image.new("RGB", (480, 360), (24, 24, 24))
        ImageDraw.Draw(photo).text((20, 160), "chosen frame photo missing", fill=(180, 180, 180), font=_font(16))
    norm = _draw_normalized_contour(
        distinctive.get("normalized_contour") or listing_shape.get("norm_xy"),
        title="listing normalized contour",
    )
    gap = 12
    width = photo.size[0] + norm.size[0] + 36
    height = max(photo.size[1], norm.size[1]) + 48
    canvas = Image.new("RGB", (width, height), (10, 10, 10))
    draw = ImageDraw.Draw(canvas)
    draw.text((12, 8), "Listing pool contour proof (not used to rerank)", fill=(240, 240, 240), font=_font(16))
    canvas.paste(photo, (12, 36))
    canvas.paste(norm, (24 + photo.size[0], 36))
    dest.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(dest, quality=90)
    try:
        return str(dest.relative_to(REPO_ROOT))
    except ValueError:
        return str(dest)


def ensure_native15_crops(dataset: Mapping[str, Any], parcels: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    tiles = download_tiles_for_parcels(
        estate_id=DATASET_ID,
        extent=dataset["extent"],
        parcels=parcels,
        repo_root=REPO_ROOT,
    )
    crops = crop_parcels(
        estate_id=DATASET_ID,
        extent=dataset["extent"],
        parcels=parcels,
        repo_root=REPO_ROOT,
    )
    return {"tiles": tiles, "crops": crops}


def encode_images_batch(images: Sequence[Image.Image], batch: int = 16) -> list[np.ndarray]:
    model, preprocess, _, torch = load_clip()
    feats: list[np.ndarray] = []
    for index in range(0, len(images), batch):
        chunk = images[index : index + batch]
        tensor = torch.stack([preprocess(image.convert("RGB")) for image in chunk])
        with torch.no_grad():
            encoded = model.encode_image(tensor)
            encoded = encoded / encoded.norm(dim=-1, keepdim=True)
        feats.extend(encoded.cpu().numpy())
    return feats


def clip_listing_vectors(photos: Mapping[str, bytes], scenes: Mapping[str, str]) -> dict[str, list[np.ndarray]]:
    aerial: list[np.ndarray] = []
    exterior: list[np.ndarray] = []
    images = []
    roles = []
    for media_id, body in sorted(photos.items()):
        scene = scenes.get(media_id)
        if scene == "interior":
            continue
        images.append(Image.open(io.BytesIO(body)).convert("RGB"))
        roles.append(scene)
    if not images:
        return {"aerial": [], "exterior": []}
    encoded = encode_images_batch(images)
    for feat, scene in zip(encoded, roles):
        if scene in AERIAL_SCENES:
            aerial.append(feat)
        if scene in EXTERIOR_SCENES:
            exterior.append(feat)
    return {"aerial": aerial, "exterior": exterior}


def clip_candidate_similarities(
    parcels: Sequence[Mapping[str, Any]],
    listing_vecs: Mapping[str, list[np.ndarray]],
) -> dict[str, dict[str, float | None]]:
    crop_dir = crop_dir_for(DATASET_ID, "native15", repo_root=REPO_ROOT)
    images: list[Image.Image] = []
    stands: list[str] = []
    for parcel in parcels:
        stand = str(parcel["stand_number"])
        path = crop_dir / f"{safe_stand(stand)}_ags_aerial.jpg"
        if not path.is_file():
            continue
        images.append(Image.open(path).convert("RGB"))
        stands.append(stand)
    out = {str(parcel["stand_number"]): {"aerial": None, "exterior": None} for parcel in parcels}
    if not images:
        return out
    encoded = encode_images_batch(images)
    aerial_vecs = list(listing_vecs.get("aerial") or [])
    exterior_vecs = list(listing_vecs.get("exterior") or [])
    for stand, feat in zip(stands, encoded):
        cand = [feat]
        aerial = mean_top_similarity(aerial_vecs, cand) if aerial_vecs else None
        exterior = mean_top_similarity(exterior_vecs, cand) if exterior_vecs else None
        out[stand] = {
            "aerial": None if aerial is None else round(float(aerial), 4),
            "exterior": None if exterior is None else round(float(exterior), 4),
        }
    return out


def stand_size_support(listing_sqm: float | None, candidate_sqm: float | None) -> float:
    if not listing_sqm or not candidate_sqm or listing_sqm <= 0:
        return 0.0
    rel = abs(float(candidate_sqm) - float(listing_sqm)) / float(listing_sqm)
    return float(max(0.0, min(1.0, 1.0 - rel / 0.45)))


def rank_survivors(
    survivors: Sequence[Mapping[str, Any]],
    fingerprint,
    listing_shape,
    *,
    listing_erf_sqm: float | None,
    clip_sims: Mapping[str, Mapping[str, float | None]],
    apply_candidate_pov: bool = False,
    gis_geometry_by_stand: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    geom_lookup = dict(gis_geometry_by_stand or {})
    for parcel in survivors:
        stand = str(parcel["stand_number"])
        sims = clip_sims.get(stand) or {}
        size_score = stand_size_support(listing_erf_sqm, parcel.get("area_sqm"))
        os_payload = load_os_payload(stand)
        pov_summary = None
        if apply_candidate_pov:
            os_payload, pov_summary = overlay_os_payload_with_pov(
                os_payload,
                geom_lookup.get(stand) or parcel.get("geometry"),
            )
        scored = score_one_candidate(
            fingerprint,
            listing_shape,
            os_payload,
            aerial=sims.get("aerial"),
            exterior=sims.get("exterior"),
            stand_size=float(size_score or 0.0),
        )
        rows.append(
            {
                "stand_number": stand,
                "township": parcel.get("township"),
                "area_sqm": parcel.get("area_sqm"),
                "property_id": parcel.get("property_id"),
                "inventory_pool_status": parcel.get("inventory_pool_status"),
                "inventory_unknown_reason": parcel.get("inventory_unknown_reason"),
                "parcel_corner": parcel.get("parcel_corner"),
                "size_score": round(float(size_score), 4),
                "aerial_similarity": sims.get("aerial"),
                "exterior_similarity": sims.get("exterior"),
                "hybrid_v2": scored["score"],
                "hybrid_v2_contrib": scored["contrib"],
                "hybrid_v2_coverage": scored["coverage"],
                "hybrid_v2_shape_v2": scored["shape_v2"],
                "hybrid_v2_spatial_v2": scored["spatial_v2"],
                "hybrid_v2_shape_parts": scored["shape_parts"],
                "os_pool_status": scored["os_pool_status"],
                "os_building_status": scored["os_building_status"],
                "os_driveway_status": scored["os_driveway_status"],
                "os_high_conf_pool": scored["os_high_conf_pool"],
                "spatial_record": scored["spatial_record"],
                "pool_geometry_support": bool(scored["os_high_conf_pool"]),
                "candidate_pov_status": None if pov_summary is None else pov_summary.get("pov_status"),
                "frozen_os_pool_status": None if pov_summary is None else pov_summary.get("frozen_os_status"),
                "candidate_pov": pov_summary,
            }
        )
    rank_rows(rows, "hybrid_v2")
    return rows


def top_n(rows: Sequence[Mapping[str, Any]], n: int) -> list[dict[str, Any]]:
    ordered = sorted(rows, key=lambda row: int(row["hybrid_v2_rank"]))
    slim = []
    for row in ordered[:n]:
        contrib = row.get("hybrid_v2_contrib") or {}
        slim.append(
            {
                "rank": row["hybrid_v2_rank"],
                "stand_number": row["stand_number"],
                "property_id": row.get("property_id"),
                "township": row.get("township"),
                "area_sqm": row.get("area_sqm"),
                "score": row["hybrid_v2"],
                "inventory_pool_status": row.get("inventory_pool_status"),
                "os_pool_status": row.get("os_pool_status"),
                "os_building_status": row.get("os_building_status"),
                "os_driveway_status": row.get("os_driveway_status"),
                "os_high_conf_pool": row.get("os_high_conf_pool"),
                "pool_geometry_support": row.get("pool_geometry_support"),
                "parcel_corner": row.get("parcel_corner"),
                "candidate_pov_status": row.get("candidate_pov_status"),
                "frozen_os_pool_status": row.get("frozen_os_pool_status"),
                "shape_v2": row.get("hybrid_v2_shape_v2"),
                "spatial_v2": row.get("hybrid_v2_spatial_v2"),
                "coverage": row.get("hybrid_v2_coverage"),
                "aerial_similarity": row.get("aerial_similarity"),
                "exterior_similarity": row.get("exterior_similarity"),
                "size_score": row.get("size_score"),
                "evidence_contributors": contrib,
                "top_contributors": sorted(
                    ((key, val) for key, val in contrib.items()),
                    key=lambda item: -float(item[1]),
                )[:5],
                "spatial_record": row.get("spatial_record"),
                "neutral_components": _neutral_components(row),
            }
        )
    return slim


def _neutral_components(row: Mapping[str, Any]) -> list[str]:
    notes = []
    if row.get("aerial_similarity") is None:
        notes.append("aerial=0.5_neutral_missing_listing_aerial")
    if row.get("exterior_similarity") is None:
        notes.append("exterior=0.5_neutral_missing_listing_exterior")
    if row.get("hybrid_v2_spatial_v2") is None:
        notes.append("spatial_v2=0.5_neutral_hybrid_omits_pool_house")
    if row.get("hybrid_v2_shape_v2") is None:
        notes.append("shape_v2=0.5_neutral_no_listing_or_candidate_contour")
    if not row.get("os_high_conf_pool"):
        notes.append("pool_presence=0.5_neutral_no_high_conf_os_pool_or_listing_geometry")
    return notes


def _contrib_split(row: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    contrib = dict(row.get("hybrid_v2_contrib") or row.get("contrib") or {})
    weights = dict(V2_WEIGHTS_NO_BUILDING)
    genuine = []
    padding = []
    for key, weight in weights.items():
        value = contrib.get(key)
        if value is None:
            continue
        expected_neutral = 0.5 * weight
        if abs(float(value) - expected_neutral) <= 0.0015:
            padding.append({"term": key, "contrib": value, "weight": weight})
        else:
            genuine.append({"term": key, "contrib": value, "weight": weight})
    genuine.sort(key=lambda item: -float(item["contrib"]))
    return genuine, padding


def ranking_separation(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    ordered = sorted(rows, key=lambda row: int(row.get("hybrid_v2_rank") or row.get("rank") or 0))
    if len(ordered) < 2:
        return {"n": len(ordered)}

    def _score(row: Mapping[str, Any]) -> float:
        return float(row["hybrid_v2"] if "hybrid_v2" in row else row["score"])

    s1 = _score(ordered[0])
    s2 = _score(ordered[1])
    s5 = _score(ordered[min(4, len(ordered) - 1)])
    s10 = _score(ordered[min(9, len(ordered) - 1)])
    s20 = _score(ordered[min(19, len(ordered) - 1)])
    top1 = ordered[0]
    genuine, padding = _contrib_split(top1)
    padding_sum = round(sum(float(item["contrib"]) for item in padding), 4)
    genuine_sum = round(sum(float(item["contrib"]) for item in genuine), 4)
    top5 = []
    for row in ordered[:5]:
        g, p = _contrib_split(row)
        top5.append(
            {
                "rank": row.get("hybrid_v2_rank") or row.get("rank"),
                "stand_number": row.get("stand_number"),
                "score": _score(row),
                "genuine_drivers": g,
                "neutral_padding": p,
                "genuine_sum": round(sum(float(item["contrib"]) for item in g), 4),
                "neutral_sum": round(sum(float(item["contrib"]) for item in p), 4),
            }
        )
    return {
        "top1_score": s1,
        "top2_score": s2,
        "top5_score": s5,
        "top10_score": s10,
        "top20_score": s20,
        "top5_score_range": [s5, s1],
        "gap_1_2": round(s1 - s2, 4),
        "gap_1_5": round(s1 - s5, 4),
        "gap_1_10": round(s1 - s10, 4),
        "gap_1_20": round(s1 - s20, 4),
        "top1_stand": top1.get("stand_number"),
        "top1_genuine_drivers": genuine,
        "top1_neutral_padding": padding,
        "top1_genuine_sum": genuine_sum,
        "top1_neutral_padding_sum": padding_sum,
        "top1_padding_share_of_score": None if not s1 else round(padding_sum / s1, 4),
        "top1_neutral_notes": _neutral_components(top1),
        "top5_composition": top5,
        "weights": dict(V2_WEIGHTS_NO_BUILDING),
    }


def gate_public(result) -> dict[str, Any]:
    payload = result.to_dict()
    payload.pop("survivor_parcel_ids", None)
    payload.pop("removed_parcel_ids", None)
    payload["no_removed"] = payload.get("parcels_removed_confident_no")
    payload["yes_survivors"] = result.yes_survivors
    payload["unknown_survivors"] = result.unknown_survivors
    payload["final_survivor_count"] = result.total_survivors
    payload["percentage_reduction"] = result.pct_reduction
    payload["starting_candidates"] = result.starting_count
    return payload


def freeze_payload(
    *,
    acquisition: Mapping[str, Any],
    photo_classes: Mapping[str, Any],
    listing_pool: Mapping[str, Any],
    gate,
    fingerprint: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    crop_stats: Mapping[str, Any],
    listing_id: str = LISTING_ID,
    experiment: str | None = None,
    prior_artifacts: Mapping[str, Any] | None = None,
    distinctive_contour_v2: Mapping[str, Any] | None = None,
    listing_corner: Mapping[str, Any] | None = None,
    corner_gate=None,
    listing_pov: Mapping[str, Any] | None = None,
    candidate_pov: Mapping[str, Any] | None = None,
    ranking_quality: Mapping[str, Any] | None = None,
    apply_candidate_pov: bool = False,
) -> dict[str, Any]:
    acq = {
        key: val
        for key, val in acquisition.items()
        if key not in {"photos", "listing"}
    }
    acq.update(
        {
            "exterior_photo_count": photo_classes.get("exterior_photo_count"),
            "pool_photo_count": photo_classes.get("pool_photo_count"),
            "driveway_photo_count": photo_classes.get("driveway_photo_count"),
            "garden_photo_count": photo_classes.get("garden_photo_count"),
            "interior_photo_count": photo_classes.get("interior_photo_count"),
            "useful_driveway_garage_views": photo_classes.get("useful_driveway_garage_views"),
            "useful_garden_patio_views": photo_classes.get("useful_garden_patio_views"),
            "useful_pool_views": photo_classes.get("useful_pool_views"),
            "useful_exterior_views": photo_classes.get("useful_exterior_views"),
            "useful_aerial_views": [
                mid
                for mid, scene in (photo_classes.get("scenes") or {}).items()
                if scene in AERIAL_SCENES
            ],
            "scene_counts": photo_classes.get("scene_counts"),
        }
    )
    ranked = sorted(rows, key=lambda row: int(row["hybrid_v2_rank"]))
    distinctive = fingerprint.get("distinctive") or distinctive_pool_fingerprint(fingerprint)
    body = {
        "experiment": experiment or f"blind_{listing_id}_complete_estate",
        "dataset_id": DATASET_ID,
        "listing_id": listing_id,
        "rankings_frozen": True,
        "ground_truth_applied": False,
        "production_ranking_modified": False,
        "scoring_v2_weights_modified": False,
        "hybrid_v1_modified": False,
        "os_v1_modified": False,
        "fastsam_modified": False,
        "native15_modified": False,
        "pool_gate_semantics_modified": False,
        "inventory_classifications_modified": False,
        "colour_used_in_ranking": False,
        "stand_size_used_as_hard_filter": False,
        "clip_computed_on": (
            "corner_gate_survivors_with_native15_crops"
            if corner_gate is not None
            else "all_pool_gate_survivors_with_native15_crops"
        ),
        "official_score": "hybrid_v2",
        "acquisition": acq,
        "listing_pool_gate": listing_pool,
        "estate_pool_gate": gate_public(gate),
        "listing_corner": listing_corner,
        "estate_corner_gate": None if corner_gate is None else corner_gate_public(corner_gate),
        "listing_pool_object_validation": listing_pov,
        "candidate_pool_object_validation": candidate_pov,
        "listing_fingerprint": {
            "hybrid_evidence": fingerprint["hybrid_evidence"],
            "qualitative": fingerprint["qualitative"],
            "distinctive_pool": distinctive,
        },
        "pool_contour_metrics": distinctive,
        "crop_stats": crop_stats,
        "ranking": {
            "n_candidates": len(ranked),
            "separation": ranking_separation(ranked),
            "shape_discrimination": shape_discrimination(ranked),
            "quality": ranking_quality,
            "top20": top_n(ranked, 20),
            "top10": top_n(ranked, 10),
            "top5": top_n(ranked, 5),
            "top1": None if not ranked else top_n(ranked, 1)[0],
        },
        "ranking_configuration": {
            "official_score": "hybrid_v2",
            "scoring_v2_weights": dict(V2_WEIGHTS_NO_BUILDING),
            "os_keys": ["pool_presence", "shape_v2", "spatial_v2"],
            "hybrid_pool_geometry": "v1",
            "os_v1": "object_segmentation_v1",
            "fastsam_imgsz": 512,
            "native15": True,
            "clip": "ViT-B-32 openai",
            "pool_gate": "listing_pool_gate_v1",
            "corner_gate": None if corner_gate is None else "listing_corner_gate_v1",
            "pool_object_validation": "pool_object_validation_v1",
            "candidate_pov_overlay": bool(apply_candidate_pov),
            "scoring_v2_weights_modified": False,
            "inventory": "estate_property_inventory_v1",
            "dataset_id": DATASET_ID,
            "colour_used_in_ranking": False,
        },
        "frozen_001_untouched": {
            "gis_sha256_expected": FROZEN_001_GIS_SHA256,
            "inventory_sha256_expected": FROZEN_001_INVENTORY_SHA256,
            "gis_sha256": sha256_file(FROZEN_001_GIS) if FROZEN_001_GIS.is_file() else None,
            "inventory_sha256": sha256_file(FROZEN_001_INVENTORY) if FROZEN_001_INVENTORY.is_file() else None,
        },
        "prior_listing_artifacts": prior_artifacts or scan_prior_listing_artifacts(listing_id),
        "distinctive_contour_v2": None
        if distinctive_contour_v2 is None
        else {
            "used_in_ranking": False,
            "ranking_modified": False,
            "official_chosen_id": distinctive_contour_v2.get("official_chosen_id"),
            "n_useful_frames": distinctive_contour_v2.get("n_useful_frames"),
            "overall": distinctive_contour_v2.get("overall"),
            "panels": distinctive_contour_v2.get("panels"),
            "frames": [
                {
                    key: val
                    for key, val in row.items()
                    if key not in {"_draw"}
                }
                for row in (distinctive_contour_v2.get("frames") or [])
            ],
            "note": "Reporting/diagnostic only. Not a ranking input.",
        },
        "on_disk_sha256_recorded_in": "freeze.sha256",
    }
    return body


def write_freeze(
    payload: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    dest: Path = FREEZE_PATH,
    all_candidates: Path | None = None,
) -> str:
    dest.parent.mkdir(parents=True, exist_ok=True)
    body = {key: val for key, val in payload.items() if key != "sha256"}
    dest.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    digest = sha256_file(dest)
    recorded_path = dest.parent / "freeze.sha256"
    recorded_path.write_text(digest + "\n", encoding="utf-8")
    on_disk = sha256_file(dest)
    recorded = recorded_path.read_text(encoding="utf-8").strip()
    if on_disk != digest or recorded != on_disk:
        raise RuntimeError(
            f"freeze hash mismatch on_disk={on_disk} computed={digest} recorded={recorded}"
        )
    slim = []
    for row in sorted(rows, key=lambda item: int(item["hybrid_v2_rank"])):
        slim.append(
            {
                "rank": row["hybrid_v2_rank"],
                "stand_number": row["stand_number"],
                "property_id": row.get("property_id"),
                "township": row.get("township"),
                "area_sqm": row.get("area_sqm"),
                "score": row["hybrid_v2"],
                "inventory_pool_status": row.get("inventory_pool_status"),
                "os_pool_status": row.get("os_pool_status"),
                "os_high_conf_pool": row.get("os_high_conf_pool"),
                "parcel_corner": row.get("parcel_corner"),
                "candidate_pov_status": row.get("candidate_pov_status"),
                "frozen_os_pool_status": row.get("frozen_os_pool_status"),
                "shape_v2": row.get("hybrid_v2_shape_v2"),
                "spatial_v2": row.get("hybrid_v2_spatial_v2"),
                "coverage": row.get("hybrid_v2_coverage"),
                "aerial_similarity": row.get("aerial_similarity"),
                "exterior_similarity": row.get("exterior_similarity"),
                "contrib": row.get("hybrid_v2_contrib"),
            }
        )
    candidates_path = all_candidates or dest.with_name("all_candidates.json")
    candidates_path.write_text(
        json.dumps({"n": len(slim), "rows": slim}, indent=2) + "\n",
        encoding="utf-8",
    )
    (dest.parent / "freeze.sha256").write_text(digest + "\n", encoding="utf-8")
    if sha256_file(dest) != digest:
        raise RuntimeError("freeze.json changed after hash recording")
    return digest


def _listing_strip(photos: Mapping[str, bytes], media_ids: Sequence[str], fallback_scenes: Mapping[str, str], wanted: Sequence[str]) -> Image.Image:
    chosen: list[tuple[str, Image.Image]] = []
    for media_id in media_ids:
        if media_id in photos:
            chosen.append((media_id, Image.open(io.BytesIO(photos[media_id])).convert("RGB")))
        if len(chosen) >= 3:
            break
    if len(chosen) < 3:
        for media_id, scene in fallback_scenes.items():
            if scene in wanted and media_id in photos and all(media_id != item[0] for item in chosen):
                chosen.append((media_id, Image.open(io.BytesIO(photos[media_id])).convert("RGB")))
            if len(chosen) >= 3:
                break
    if not chosen:
        canvas = Image.new("RGB", (900, 240), (20, 20, 20))
        ImageDraw.Draw(canvas).text((20, 100), "no listing photos", fill=(200, 200, 200), font=_font(18))
        return canvas
    thumbs = []
    for media_id, image in chosen[:3]:
        image.thumbnail((420, 280))
        thumbs.append((media_id, image))
    gap = 8
    width = sum(img.size[0] for _, img in thumbs) + gap * (len(thumbs) + 1)
    height = max(img.size[1] for _, img in thumbs) + 28
    canvas = Image.new("RGB", (width, height), (16, 16, 16))
    draw = ImageDraw.Draw(canvas)
    x = gap
    for media_id, image in thumbs:
        draw.text((x, 4), media_id, fill=(220, 220, 220), font=_font(13))
        canvas.paste(image, (x, 22))
        x += image.size[0] + gap
    return canvas


def _pool_house_overlay(raw: Image.Image, seg: Mapping[str, Any], parcel: Mapping[str, Any]) -> Image.Image:
    image = raw.convert("RGBA")
    draw = ImageDraw.Draw(image, "RGBA")
    width, height = image.size
    mask = parcel_mask_from_geometry((width, height), parcel["geometry"])
    import cv2

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    bgr = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)
    cv2.drawContours(bgr, contours, -1, (0, 220, 255), 2)
    image = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)).convert("RGBA")
    draw = ImageDraw.Draw(image, "RGBA")

    def _pts(contour):
        return [(int(float(x) * (width - 1)), int(float(y) * (height - 1))) for x, y in (contour or [])]

    def _fill(contour, fill, outline):
        pts = _pts(contour)
        if len(pts) >= 3:
            draw.polygon(pts, fill=fill, outline=outline)

    pool = seg.get("pool") or {}
    building = seg.get("building") or {}
    driveway = seg.get("driveway") or {}
    _fill(driveway.get("contour"), (40, 180, 80, 70), (80, 220, 80))
    _fill(building.get("contour"), (220, 50, 50, 70), (255, 90, 90))
    _fill(pool.get("contour"), (40, 180, 255, 90), (80, 220, 255))
    pool_c = (pool.get("geometry") or {})
    bldg_c = (building.get("geometry") or {})
    if pool_c.get("centroid_x") is not None and bldg_c.get("centroid_x") is not None:
        p = (int(float(pool_c["centroid_x"]) * (width - 1)), int(float(pool_c["centroid_y"]) * (height - 1)))
        b = (int(float(bldg_c["centroid_x"]) * (width - 1)), int(float(bldg_c["centroid_y"]) * (height - 1)))
        draw.line([p, b], fill=(255, 220, 80, 255), width=3)
        draw.ellipse((p[0] - 4, p[1] - 4, p[0] + 4, p[1] + 4), fill=(80, 220, 255, 255))
        draw.ellipse((b[0] - 4, b[1] - 4, b[0] + 4, b[1] + 4), fill=(255, 90, 90, 255))
    return image.convert("RGB")


def draw_top5_panels(
    rows: Sequence[Mapping[str, Any]],
    photos: Mapping[str, bytes],
    photo_classes: Mapping[str, Any],
    dataset: Mapping[str, Any],
    dest: Path = PANELS_DIR,
    fingerprint: Mapping[str, Any] | None = None,
) -> list[str]:
    dest.mkdir(parents=True, exist_ok=True)
    by_stand = {str(item["stand_number"]): item for item in pass1_parcels(dataset)}
    scenes = photo_classes.get("scenes") or {}
    pool_ids = list(photo_classes.get("useful_pool_views") or [])
    ext_ids = list(photo_classes.get("useful_exterior_views") or [])
    drive_ids = list(photo_classes.get("useful_driveway_garage_views") or [])
    distinctive = {} if fingerprint is None else (fingerprint.get("distinctive") or distinctive_pool_fingerprint(fingerprint))
    listing_norm = distinctive.get("normalized_contour")
    chosen = {} if fingerprint is None else ((fingerprint.get("evidence_obj") or {}).get("chosen_frame") or {})
    listing_contour_image = (chosen.get("dominant") or {}).get("contour_image") or chosen.get("contour_image")
    chosen_id = distinctive.get("chosen_id")
    listing_photo = None
    if chosen_id and chosen_id in photos:
        listing_photo = Image.open(io.BytesIO(photos[chosen_id])).convert("RGB")
        listing_photo.thumbnail((360, 260))
        listing_photo = _overlay_norm_contour_on_image(listing_photo, listing_contour_image)
    written = []
    ordered = sorted(rows, key=lambda row: int(row["hybrid_v2_rank"]))[:5]
    for row in ordered:
        stand = str(row["stand_number"])
        parcel = by_stand[stand]
        crop_path = crop_path_for(DATASET_ID, stand, repo_root=REPO_ROOT)
        raw = Image.open(crop_path).convert("RGB") if crop_path.is_file() else Image.new("RGB", (400, 300), (30, 30, 30))
        seg = load_os_payload(stand)
        analysis = render_proof_panel(
            raw,
            parcel,
            seg,
            [
                f"frozen rank #{row['hybrid_v2_rank']} stand={stand} score={row['hybrid_v2']}",
                f"inventory={row.get('inventory_pool_status')} OS pool={row.get('os_pool_status')} "
                f"building={row.get('os_building_status')} driveway={row.get('os_driveway_status')}",
                f"shape_v2={row.get('hybrid_v2_shape_v2')} spatial_v2={row.get('hybrid_v2_spatial_v2')} "
                f"aerial={row.get('aerial_similarity')} exterior={row.get('exterior_similarity')}",
            ],
            [
                "Overlays are frozen OS v1 masks. Yellow line in the comparison panel is pool centroid to building centroid.",
                "Listing photos are CLIP scene-classified; they are not used to retune ranking.",
            ],
        )
        listing = _listing_strip(photos, pool_ids + ext_ids + drive_ids, scenes, ["pool_garden", "rear_elevation", "driveway_access", "front_elevation"])
        geometry = _pool_house_overlay(raw, seg, parcel)
        cand_desc = None
        pool = seg.get("pool") or {}
        if pool.get("contour"):
            from backend.gis.estate_ags_matching.os_scoring_v2 import contour_descriptors

            cand_desc = contour_descriptors(pool.get("contour") or (pool.get("geometry") or {}).get("contour_image"))
        listing_norm_img = _draw_normalized_contour(listing_norm, title="listing contour")
        cand_norm_img = _draw_normalized_contour(
            None if cand_desc is None else cand_desc.get("norm_xy"),
            outline=(255, 200, 80),
            title=f"candidate {stand} contour",
        )
        raw_thumb = raw.copy()
        raw_thumb.thumbnail((280, 220))
        gis_mask = geometry.copy()
        gis_mask.thumbnail((280, 220))
        shape_cell = Image.new("RGB", (280, 220), (18, 18, 18))
        sdraw = ImageDraw.Draw(shape_cell)
        sdraw.text((12, 16), f"shape_v2={row.get('hybrid_v2_shape_v2')}", fill=(240, 240, 240), font=_font(16))
        sdraw.text((12, 48), f"hybrid_v2={row.get('hybrid_v2')}", fill=(200, 200, 200), font=_font(14))
        sdraw.text((12, 76), f"inventory={row.get('inventory_pool_status')}", fill=(200, 200, 200), font=_font(14))
        sdraw.text((12, 104), f"OS pool={row.get('os_pool_status')}", fill=(200, 200, 200), font=_font(14))
        sdraw.text((12, 140), "Do not rerank from this panel.", fill=(160, 160, 160), font=_font(13))
        contour_row_imgs = [listing_photo or listing_norm_img, listing_norm_img, raw_thumb, gis_mask, cand_norm_img, shape_cell]
        labels = ["listing pool+contour", "listing normalized", "raw native15", "GIS+OS masks", "candidate normalized", "shape similarity"]
        gap = 12
        row_w = sum(img.size[0] for img in contour_row_imgs) + gap * (len(contour_row_imgs) + 1)
        row_h = max(img.size[1] for img in contour_row_imgs) + 28
        contour_row = Image.new("RGB", (row_w, row_h), (14, 14, 14))
        cdraw = ImageDraw.Draw(contour_row)
        x = gap
        for label, img in zip(labels, contour_row_imgs):
            cdraw.text((x, 2), label, fill=(210, 210, 210), font=_font(12))
            contour_row.paste(img, (x, 20))
            x += img.size[0] + gap
        width = max(listing.size[0], analysis.size[0], geometry.size[0], contour_row.size[0]) + 24
        height = listing.size[1] + contour_row.size[1] + analysis.size[1] + geometry.size[1] + 110
        canvas = Image.new("RGB", (width, height), (12, 12, 12))
        draw = ImageDraw.Draw(canvas)
        draw.text((12, 8), f"Top-{row['hybrid_v2_rank']} proof  {stand}  hybrid_v2={row['hybrid_v2']}", fill=(240, 240, 240), font=_font(18))
        y = 36
        canvas.paste(listing, (12, y))
        y += listing.size[1] + gap
        canvas.paste(contour_row, (12, y))
        y += contour_row.size[1] + gap
        canvas.paste(analysis, (12, y))
        y += analysis.size[1] + gap
        draw.text((12, y), "Pool-to-house / driveway / building overlay on raw native15", fill=(210, 210, 210), font=_font(14))
        y += 20
        canvas.paste(geometry, (12, y))
        path = dest / f"top{row['hybrid_v2_rank']}_{safe_stand(stand)}.jpg"
        canvas.convert("RGB").save(path, quality=90)
        written.append(str(path.relative_to(REPO_ROOT)))
    return written


def run_freeze(
    *,
    observe_objects: bool = True,
    listing_id: str = LISTING_ID,
    listing_url: str = LISTING_URL,
    out_dir: Path | None = None,
    write_panels: bool = True,
    force_fresh_photos: bool = False,
    ignore_frozen_hybrid_json: bool = False,
    apply_corner_gate: bool = False,
    apply_candidate_pov: bool = False,
) -> dict[str, Any]:
    started = time.time()
    dest = Path(out_dir) if out_dir is not None else REPO_ROOT / "data/investigations" / f"blind_{listing_id}_complete_estate"
    photos_dir = dest / "photos"
    freeze_path = dest / "freeze.json"
    dest.mkdir(parents=True, exist_ok=True)
    prior_artifacts = scan_prior_listing_artifacts(listing_id)
    dataset = load_gis_002()
    parcels = pass1_parcels(dataset)
    inventory = load_inventory_002()
    if len(parcels) != 400:
        raise RuntimeError(f"expected 400 unique erven, got {len(parcels)}")

    acquisition = acquire_listing(
        url=listing_url,
        listing_id=listing_id,
        photos_dir=photos_dir,
        force_fresh_photos=force_fresh_photos,
    )
    photos = acquisition["photos"]
    photo_classes = classify_listing_photos(photos)
    hybrid_block = load_or_extract_hybrid_block(
        listing_id,
        photos,
        dest=dest / "hybrid_block.json",
        ignore_frozen_hybrid_json=ignore_frozen_hybrid_json or bool(prior_artifacts.get("frozen_hybrid_json_contains_listing")),
    )
    frame_objects = list(hybrid_block.pop("_frame_objects", []) or [])
    object_obs = observe_pool_media(photos, photo_classes["scenes"]) if observe_objects else None
    listing_pool = classify_listing_pool_status(acquisition, hybrid_block, photo_classes, object_obs)
    if object_obs is not None:
        listing_pool["listing_pool_object"] = {
            "n_observed": object_obs["n_observed"],
            "n_pool_object_detected": object_obs["n_pool_object_detected"],
            "detected_ids": object_obs["detected_ids"],
            "n_l_geometry": object_obs["n_l_geometry"],
        }

    candidates = [
        {
            "stand_number": parcel["stand_number"],
            "township": parcel.get("township"),
            "area_sqm": parcel.get("area_sqm"),
            "property_id": parcel.get("property_id"),
            "parcel_id": parcel.get("property_id"),
        }
        for parcel in parcels
    ]
    gate = apply_listing_pool_gate(candidates, inventory, listing_pool["listing_pool_status"])
    ranking_candidates = list(gate.survivors)
    listing_corner_obs = None
    corner_gate = None
    if apply_corner_gate:
        from backend.gis.estate_ags_matching.listing_corner_evidence_v1 import observe_listing_corner
        from backend.gis.estate_ags_matching.listing_corner_gate_v1 import apply_listing_corner_gate

        listing_corner_obs = observe_listing_corner(
            text=listing_text_for_gates(acquisition),
            photos=photos,
            viewpoints=listing_corner_viewpoints(hybrid_block, photo_classes),
        )
        corner_gate = apply_listing_corner_gate(
            ranking_candidates,
            load_parcel_corner_records(),
            listing_corner_obs.classification,
            listing_evidence=listing_corner_obs,
        )
        ranking_candidates = list(corner_gate.survivors)
    crop_stats = ensure_native15_crops(dataset, parcels)
    fingerprint = listing_fingerprint(hybrid_block, photo_classes)
    fingerprint["distinctive"] = distinctive_pool_fingerprint(fingerprint)
    listing_vecs = clip_listing_vectors(photos, photo_classes["scenes"])
    clip_sims = clip_candidate_similarities(ranking_candidates, listing_vecs)
    gis_geometry_by_stand = (
        {str(parcel["stand_number"]): parcel.get("geometry") for parcel in parcels}
        if apply_candidate_pov
        else None
    )
    rows = rank_survivors(
        ranking_candidates,
        fingerprint["fingerprint_obj"],
        fingerprint["listing_shape_obj"],
        listing_erf_sqm=acquisition.get("erf_size_sqm"),
        clip_sims=clip_sims,
        apply_candidate_pov=apply_candidate_pov,
        gis_geometry_by_stand=gis_geometry_by_stand,
    )
    contour_proof = draw_listing_contour_proof(
        fingerprint,
        photos,
        dest=dest / "listing_pool_contour_proof.png",
    )
    if contour_proof:
        fingerprint["distinctive"]["contour_proof_path"] = contour_proof
    from backend.gis.estate_ags_matching.distinctive_contour_v2 import run_distinctive_contour_v2

    dcv2 = run_distinctive_contour_v2(
        photos,
        photo_classes,
        frame_objects,
        official_chosen_id=(fingerprint.get("qualitative") or {}).get("hybrid_chosen_id")
        or (fingerprint.get("hybrid_evidence") or {}).get("chosen_id"),
        dest=dest / "distinctive_contour_v2",
    )
    payload = freeze_payload(
        acquisition=acquisition,
        photo_classes=photo_classes,
        listing_pool=listing_pool,
        gate=gate,
        fingerprint=fingerprint,
        rows=rows,
        crop_stats=crop_stats,
        listing_id=listing_id,
        prior_artifacts=prior_artifacts,
        distinctive_contour_v2=dcv2,
        listing_corner=None if listing_corner_obs is None else listing_corner_public(listing_corner_obs),
        corner_gate=corner_gate,
        listing_pov=listing_pov_public(hybrid_block),
        candidate_pov=candidate_pov_counts(rows) if apply_candidate_pov else None,
        ranking_quality=ranking_quality_report(
            rows,
            listing_shape_available=bool(fingerprint.get("listing_shape_obj")),
        ),
        apply_candidate_pov=apply_candidate_pov,
    )
    marker_runtime = round(time.time() - started, 2)
    digest = write_freeze(payload, rows, dest=freeze_path)
    if sha256_file(freeze_path) != digest:
        raise RuntimeError("on-disk freeze.json hash does not match recorded SHA256")
    panels = []
    if write_panels:
        panels = draw_top5_panels(
            rows,
            photos,
            photo_classes,
            dataset,
            dest=dest / "panels",
            fingerprint=fingerprint,
        )
    marker = {
        "freeze_path": str(freeze_path.relative_to(REPO_ROOT)),
        "sha256": digest,
        "ground_truth_applied": False,
        "panels": panels,
        "n_candidates": len(rows),
        "listing_pool_status": listing_pool["listing_pool_status"],
        "final_survivor_count": len(rows),
        "pool_gate_survivors": gate.total_survivors,
        "corner_gate_survivors": None if corner_gate is None else corner_gate.total_survivors,
        "listing_corner": None
        if listing_corner_obs is None
        else listing_corner_obs.classification,
        "apply_corner_gate": apply_corner_gate,
        "apply_candidate_pov": apply_candidate_pov,
        "runtime_s_freeze": marker_runtime,
    }
    (dest / "rankings_frozen.json").write_text(json.dumps(marker, indent=2) + "\n", encoding="utf-8")
    return {"payload": payload, "rows": rows, "marker": marker, "photos": photos, "dataset": dataset, "out_dir": dest}


def extract_identity_from_html(html: str) -> dict[str, Any]:
    title = None
    match = re.search(r"<title>([^<]+)</title>", html, re.I)
    if match:
        title = re.sub(r"\s+", " ", match.group(1)).strip()
    stand_numbers = []
    for item in re.finditer(
        r"(?i)\bstand\s*(?:no\.?|number|#)?\s*[:.]?\s*([0-9]+(?:/[0-9]+)?[A-Z]?)\b",
        html,
    ):
        stand_numbers.append(item.group(1))
    street = None
    street_match = STREET_RE.search(html)
    if street_match:
        street = street_match.group(0)
    if title and street is None:
        street_match = STREET_RE.search(title)
        if street_match:
            street = street_match.group(0)
    withheld = bool(re.search(r"(?i)contact agent for street address", html))
    locality = None
    loc = re.search(r'"addressLocality"\s*:\s*"([^"]+)"', html)
    if loc:
        locality = loc.group(1)
    return {
        "title": title,
        "stand_mentions": stand_numbers,
        "street": street,
        "street_withheld_contact_agent": withheld,
        "address_locality": locality,
        "coordinates_present": bool(re.search(r'"(?:latitude|longitude)"\s*:', html)),
    }


def lookup_coj_street(street: str | None) -> list[dict[str, Any]]:
    if not street:
        return []
    from backend.gis.coj_property import CoJPropertyClient, OFFICIAL_SUMMERSET_EXT, REGISTERED_STANDS

    client = CoJPropertyClient(timeout_s=60.0)
    number_match = re.match(
        r"\s*(\d+[A-Za-z]?)\s+(.+?)\s+(?:street|st\.?|road|rd\.?|drive|dr\.?|close|avenue|ave\.?|way|crescent|cres\.?)\s*$",
        street,
        re.I,
    )
    where_parts = []
    if number_match:
        num = number_match.group(1).replace("'", "''")
        name = number_match.group(2).replace("'", "''")
        where_parts.append(f"STREET_NO='{num}' AND STREET_NAME LIKE '%{name}%'")
    safe = street.replace("'", "''")
    where_parts.append(f"STREET_ADDRESS LIKE '%{safe}%'")
    towns = "','".join(OFFICIAL_SUMMERSET_EXT[ext] for ext in (3, 6, 13))
    rows = []
    seen = set()
    for clause in where_parts:
        where = f"({clause}) AND TOWN_NAME_DESC IN ('{towns}')"
        try:
            features = client.query(
                REGISTERED_STANDS,
                where,
                fields="STAND_NO,TOWN_NAME_DESC,STREET_ADDRESS,STREET_NO,STREET_NAME,PROPERTY_ID,AREA_SQMT",
                return_geometry=False,
            )
        except Exception as exc:  # noqa: BLE001
            rows.append({"error": str(exc), "where": where})
            continue
        for feat in features:
            attrs = feat.get("attributes") or feat
            key = (attrs.get("PROPERTY_ID"), attrs.get("STAND_NO"))
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "stand_number": attrs.get("STAND_NO"),
                    "township": attrs.get("TOWN_NAME_DESC"),
                    "street_address": attrs.get("STREET_ADDRESS"),
                    "property_id": attrs.get("PROPERTY_ID"),
                    "area_sqm": attrs.get("AREA_SQMT"),
                }
            )
    return rows


def _norm_street(value: str | None) -> str:
    if not value:
        return ""
    text = value.lower()
    text = re.sub(r"[.,#]", " ", text)
    text = re.sub(r"\b(street|st|road|rd|drive|dr|close|avenue|ave|way|crescent|cres)\b", "", text)
    return re.sub(r"\s+", " ", text).strip()


def match_gis_street(dataset: Mapping[str, Any], street: str | None) -> list[dict[str, Any]]:
    needle = _norm_street(street)
    if not needle:
        return []
    hits = []
    for parcel in pass1_parcels(dataset):
        hay = _norm_street(str(parcel.get("street_address") or ""))
        if hay and (needle in hay or hay in needle):
            hits.append(
                {
                    "stand_number": parcel.get("stand_number"),
                    "township": parcel.get("township"),
                    "street_address": parcel.get("street_address"),
                    "property_id": parcel.get("property_id"),
                    "area_sqm": parcel.get("area_sqm"),
                    "source": "gis_002_street_address_after_freeze",
                }
            )
    return hits


def confirm_ground_truth(html: str, dataset: Mapping[str, Any], inventory: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    identity = extract_identity_from_html(html)
    gis_hits = match_gis_street(dataset, identity.get("street"))
    coj = lookup_coj_street(identity.get("street"))
    inv_by_stand = {str(row.get("stand_number")): row for row in inventory}
    unique_stands = []
    for row in gis_hits + coj:
        stand = str(row.get("stand_number") or "")
        if stand and stand not in unique_stands and "error" not in row:
            unique_stands.append(stand)
    confirmed = None
    confidence = "LOW"
    evidence = []
    if identity.get("stand_mentions"):
        evidence.append({"type": "listing_text_stand", "values": identity["stand_mentions"]})
    if identity.get("street"):
        evidence.append({"type": "listing_street", "value": identity["street"]})
    if gis_hits:
        evidence.append({"type": "gis_002_street_match_after_freeze", "rows": gis_hits})
    if unique_stands:
        evidence.append({"type": "coj_street_lookup", "stands": unique_stands, "rows": coj})
    listing_stands = list(dict.fromkeys(identity.get("stand_mentions") or []))
    if len(listing_stands) == 1 and listing_stands[0] in inv_by_stand:
        confirmed = listing_stands[0]
        confidence = "HIGH" if (not unique_stands or unique_stands == listing_stands) else "MEDIUM"
    elif len(unique_stands) == 1 and unique_stands[0] in inv_by_stand:
        confirmed = unique_stands[0]
        confidence = "HIGH" if identity.get("street") else "MEDIUM"
    elif listing_stands and unique_stands and set(listing_stands) & set(unique_stands):
        overlap = [stand for stand in listing_stands if stand in unique_stands]
        if len(overlap) == 1:
            confirmed = overlap[0]
            confidence = "HIGH"
    visual = None
    if confirmed:
        parcel_hits = [item for item in pass1_parcels(dataset) if str(item.get("stand_number")) == confirmed]
        inv = inv_by_stand.get(confirmed)
        visual = {
            "stand_in_complete_gis": bool(parcel_hits),
            "inventory_pool_status": None if inv is None else inv.get("pool_status"),
            "township": None if not parcel_hits else parcel_hits[-1].get("township"),
            "area_sqm": None if not parcel_hits else parcel_hits[-1].get("area_sqm"),
            "note": "Visual native15 comparison is recorded in detector diagnostic; rank was not used to choose this stand.",
        }
        evidence.append({"type": "gis_inventory_presence", "visual": visual})
    if confirmed is None:
        withheld = bool(identity.get("street_withheld_contact_agent")) and not identity.get("stand_mentions")
        confidence = "NOT DETERMINABLE" if withheld else "LOW"
        evidence.append(
            {
                "type": "public_listing_identity_withheld",
                "street_withheld_contact_agent": identity.get("street_withheld_contact_agent"),
                "coordinates_present": identity.get("coordinates_present"),
                "note": "Public Property24 page does not publish street or stand. Rank was not used as truth.",
            }
        )
    return {
        "confirmed_stand": confirmed,
        "confidence": confidence if confirmed else ("NOT DETERMINABLE" if confidence == "NOT DETERMINABLE" else "LOW"),
        "determinable": confirmed is not None,
        "identity": identity,
        "gis_street_matches": gis_hits,
        "coj_matches": coj,
        "evidence": evidence,
        "visual": visual,
        "inferred_from_pie_rank": False,
        "previous_001_hybrid_ranking_also_had_no_independent_gt": True,
    }


def detector_on_true_erf(stand: str, dataset: Mapping[str, Any], inventory: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    from backend.gis.estate_ags_matching.fastsam_miss_diagnostic import (
        MISS_STANDS,
        REFERENCE_STAND,
        localize_visual_pool,
        pool_pixel_size,
        trace_proposals,
    )
    from backend.vision.object_segmentation import (
        fastsam_masks,
        parcel_mask_from_geometry,
        select_pool,
    )
    import cv2

    inv = next((row for row in inventory if str(row.get("stand_number")) == str(stand)), None)
    parcel = next(item for item in pass1_parcels(dataset) if str(item.get("stand_number")) == str(stand))
    crop_path = crop_path_for(DATASET_ID, stand, repo_root=REPO_ROOT)
    os_payload = load_os_payload(stand)
    bgr = cv2.imread(str(crop_path)) if crop_path.is_file() else None
    if bgr is None:
        return {
            "stand_number": stand,
            "inventory_pool_status": None if inv is None else inv.get("pool_status"),
            "error": "missing_native15_crop",
        }
    height, width = bgr.shape[:2]
    parcel_mask = parcel_mask_from_geometry((width, height), parcel["geometry"])
    visual = localize_visual_pool(bgr, parcel_mask, os_payload, stand=stand)
    box = visual.get("bbox_xyxy")
    masks = list(fastsam_masks(bgr))
    trace = trace_proposals(bgr, masks, parcel_mask, box, clip_available=True)
    frozen_pool = os_payload.get("pool") or {}
    building_mask = None
    bldg_contour = (os_payload.get("building") or {}).get("contour") or []
    if bldg_contour:
        pts = np.array([[int(x * (width - 1)), int(y * (height - 1))] for x, y in bldg_contour], np.int32)
        building_mask = np.zeros((height, width), np.uint8)
        cv2.fillPoly(building_mask, [pts], 255)
        building_mask = building_mask > 0
    rerun = select_pool(bgr, masks, parcel_mask, building_mask)
    clip_scores = []
    for row in trace.get("traces") or []:
        clip = row.get("clip") or {}
        if clip.get("pool") is not None:
            clip_scores.append(float(clip["pool"]))
    max_clip = max(clip_scores) if clip_scores else None
    n_fastsam = len(masks)
    isolated = bool(
        frozen_pool.get("status") in {"CONFIRMED", "PROBABLE"}
        and (frozen_pool.get("geometry") or {}).get("present")
        and max_clip is not None
        and max_clip >= 0.40
    )
    geom = frozen_pool.get("geometry") or {}
    px = None
    if geom.get("present"):
        area = geom.get("area_px")
        aspect = float(geom.get("aspect_ratio") or 1.0)
        if area:
            width_px = math.sqrt(float(area) * max(aspect, 1e-6))
            height_px = float(area) / max(width_px, 1e-6)
            px = {
                "area_px": area,
                "approx_width_px": round(width_px, 1),
                "approx_height_px": round(height_px, 1),
                "bbox": pool_pixel_size(box),
            }
    resembles = "neither"
    if isolated and max_clip and max_clip >= 0.9:
        resembles = f"Stand {REFERENCE_STAND} (FastSAM isolates compact in-parcel pool; CLIP high)"
    elif not isolated:
        resembles = f"known miss cases {MISS_STANDS} (proposal/CLIP fail to confirm)"
    return {
        "stand_number": stand,
        "inventory_pool_status": None if inv is None else inv.get("pool_status"),
        "inventory_unknown_reason": None if inv is None else inv.get("unknown_reason"),
        "fastsam_isolates_pool": isolated,
        "fastsam_mask_count": n_fastsam,
        "maximum_pool_clip_score": None if max_clip is None else round(max_clip, 4),
        "pool_approximate_pixel_dimensions": px,
        "final_os_classification": frozen_pool.get("status"),
        "os_notes": frozen_pool.get("notes"),
        "select_pool_rerun_status": (rerun or {}).get("status") if isinstance(rerun, dict) else getattr(rerun, "status", None),
        "resembles": resembles,
        "detector_parameters_changed": False,
        "crop_wh": [width, height],
        "visual_pool": visual,
        "n_traces_presented_to_clip": sum(1 for row in (trace.get("traces") or []) if row.get("presented_to_clip")),
    }


def evaluate_true_property(freeze: Mapping[str, Any], gt: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    stand = gt.get("confirmed_stand")
    if not stand:
        return {
            "determinable": False,
            "outcome": None,
            "note": "Ground truth could not be established independently. Frozen ranking was not used as truth.",
        }
    by_stand = {str(row["stand_number"]): row for row in rows}
    row = by_stand.get(str(stand))
    gate = freeze.get("estate_pool_gate") or {}
    listing_status = (freeze.get("listing_pool_gate") or {}).get("listing_pool_status")
    survived = row is not None
    rank = None if row is None else row.get("hybrid_v2_rank")
    score = None if row is None else row.get("hybrid_v2")
    inv = None if row is None else row.get("inventory_pool_status")
    if row is None and listing_status == "YES":
        # Removed only if inventory NO.
        inv_note = "not_in_survivor_table"
    else:
        inv_note = inv
    band = "outside_top20"
    if rank == 1:
        band = "Top 1"
    elif rank is not None and rank <= 5:
        band = "Top 5"
    elif rank is not None and rank <= 10:
        band = "Top 10"
    elif rank is not None and rank <= 20:
        band = "Top 20"
    if not survived:
        outcome = "FAILURE"
    elif rank == 1:
        outcome = "STRONG IMPROVEMENT"
    elif rank is not None and rank <= 5:
        outcome = "IMPROVEMENT"
    elif rank is not None and rank <= 20:
        outcome = "MIXED"
    else:
        outcome = "NO IMPROVEMENT"
    contrib = {} if row is None else (row.get("hybrid_v2_contrib") or {})
    return {
        "true_stand": stand,
        "inventory_pool_status": inv_note,
        "pool_gate_survival": "YES" if survived else "NO",
        "frozen_rank": rank,
        "frozen_score": score,
        "top_band": band,
        "pool_geometry_rank_term": None if row is None else row.get("hybrid_v2_shape_v2"),
        "roof_layout_contribution": "not_in_frozen_scoring_v2_no_building_weights",
        "driveway_contribution": None if row is None else {
            "os_driveway_status": row.get("os_driveway_status"),
            "note": "driveway is not a Scoring v2 weight in V2_WEIGHTS_NO_BUILDING",
        },
        "aerial_clip_contribution": None if row is None else contrib.get("aerial"),
        "exterior_clip_contribution": None if row is None else contrib.get("exterior"),
        "shape_v2_contribution": None if row is None else contrib.get("shape_v2"),
        "spatial_v2_contribution": None if row is None else contrib.get("spatial_v2"),
        "pool_presence_contribution": None if row is None else contrib.get("pool_presence"),
        "outcome": outcome,
        "comparison_baseline": (
            "Previous 116273255 hybrid_v2 ranking was on carlswald_north_corrected_001 "
            "(330 erven, no inventory Pool Gate, no EXT.3). Compare frozen rank/band only after GT; "
            "do not retune."
        ),
    }


def write_report(
    freeze: Mapping[str, Any],
    gt: Mapping[str, Any] | None,
    evaluation: Mapping[str, Any] | None,
    detector: Mapping[str, Any] | None,
    panels: Sequence[str],
    dest: Path | None = None,
) -> None:
    acq = freeze.get("acquisition") or {}
    listing_pool = freeze.get("listing_pool_gate") or {}
    gate = freeze.get("estate_pool_gate") or {}
    ranking = freeze.get("ranking") or {}
    fp = ((freeze.get("listing_fingerprint") or {}).get("qualitative") or {})
    listing_id = freeze.get("listing_id") or LISTING_ID
    freeze_rel = (dest or REPORT_PATH).parent / "freeze.json"
    try:
        freeze_rel = freeze_rel.relative_to(REPO_ROOT)
    except ValueError:
        freeze_rel = freeze_rel
    lines = [
        f"# Blind PIE benchmark — listing {listing_id} on carlswald_north_corrected_002",
        "",
        "Detector parameters, Scoring v2 weights, Hybrid v1, OS v1, FastSAM, native15, and inventory labels were not changed.",
        "",
        "## A. Listing acquisition",
        json.dumps(acq, indent=2),
        "",
        "## B. Listing Pool Gate classification",
        json.dumps(listing_pool, indent=2),
        "",
        "## C. Pool Gate reduction",
        json.dumps(gate, indent=2),
        "",
        "## D. Listing visual fingerprint",
        json.dumps(fp, indent=2),
        "",
        "## E. Frozen Top 20",
        json.dumps(ranking.get("top20"), indent=2),
        "",
        "## F. Frozen artifact",
        f"- path: `{freeze_rel}`",
        f"- sha256: `{freeze.get('sha256')}`",
        "",
        "## G. Top-5 proof panels",
        *[f"- `{path}`" for path in panels],
        "",
        "## H. Ground truth",
        json.dumps(gt, indent=2) if gt else "Not yet applied.",
        "",
        "## I. True-property frozen rank",
        json.dumps(evaluation, indent=2) if evaluation else "Not yet applied.",
        "",
        "## J. Detector behaviour on true erf",
        json.dumps(detector, indent=2) if detector else "Not yet applied.",
        "",
        "## K. Conclusion",
    ]
    if evaluation and evaluation.get("outcome"):
        lines.append(
            f"{evaluation['outcome']}: true stand {evaluation.get('true_stand')} "
            f"inventory={evaluation.get('inventory_pool_status')} gate={evaluation.get('pool_gate_survival')} "
            f"rank={evaluation.get('frozen_rank')} score={evaluation.get('frozen_score')} band={evaluation.get('top_band')}."
        )
    else:
        lines.append("Ground truth was not independently confirmed; frozen ranking is preserved as a blind result.")
    path = dest or REPORT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def compare_repeat_candidates(
    current_top20: Sequence[Mapping[str, Any]],
    previous_freeze_path: Path,
) -> dict[str, Any]:
    if not previous_freeze_path.is_file():
        return {"previous_freeze_found": False}
    previous = json.loads(previous_freeze_path.read_text(encoding="utf-8"))
    prev_rows = (previous.get("ranking") or {}).get("top20") or []
    cur_ids = [str(row.get("stand_number")) for row in current_top20]
    prev_ids = [str(row.get("stand_number")) for row in prev_rows]

    def _family(stand: str) -> str:
        return str(stand).replace("RE/", "").replace("1/", "")

    overlap_top20 = [stand for stand in cur_ids if stand in prev_ids]
    overlap_top5 = [stand for stand in cur_ids[:5] if stand in prev_ids[:5]]
    watch = {
        "334_family": {
            "current_ranks": [i + 1 for i, stand in enumerate(cur_ids) if _family(stand) == "334"],
            "previous_ranks": [i + 1 for i, stand in enumerate(prev_ids) if _family(stand) == "334"],
        },
        "373_family": {
            "current_ranks": [i + 1 for i, stand in enumerate(cur_ids) if _family(stand) == "373"],
            "previous_ranks": [i + 1 for i, stand in enumerate(prev_ids) if _family(stand) == "373"],
        },
    }
    bias = bool(overlap_top5) or (len(overlap_top20) >= 8)
    return {
        "previous_freeze_found": True,
        "previous_listing_id": previous.get("listing_id"),
        "previous_path": str(previous_freeze_path.relative_to(REPO_ROOT)),
        "overlap_top5": overlap_top5,
        "overlap_top20": overlap_top20,
        "n_overlap_top20": len(overlap_top20),
        "watch_families": watch,
        "possible_candidate_ranking_bias": bias,
        "note": "Overlap across unrelated listings is a bias flag, not proof of a match.",
    }


BLIND_COMPLETE_ESTATE_FREEZES = [
    REPO_ROOT / "data/investigations/blind_116273255_complete_estate/freeze.json",
    REPO_ROOT / "data/investigations/blind_116223230_complete_estate/freeze.json",
    REPO_ROOT / "data/investigations/blind_116778622_complete_estate/freeze.json",
    REPO_ROOT / "data/investigations/blind_116978058_complete_estate/freeze.json",
]

WATCH_FALSE_POSITIVE_116978058 = ("351", "380", "468", "463", "461")


def compare_three_complete_estate_blinds(
    current_top20: Sequence[Mapping[str, Any]],
    current_listing_id: str,
) -> dict[str, Any]:
    current_ids = [str(row.get("stand_number")) for row in current_top20]
    sets_top5: dict[str, list[str]] = {current_listing_id: current_ids[:5]}
    sets_top20: dict[str, list[str]] = {current_listing_id: current_ids[:20]}
    pairwise = {}
    for path in BLIND_COMPLETE_ESTATE_FREEZES:
        if not path.is_file():
            continue
        previous = json.loads(path.read_text(encoding="utf-8"))
        lid = str(previous.get("listing_id") or "")
        if lid == current_listing_id:
            continue
        pairwise[lid] = compare_repeat_candidates(current_top20, path)
        prev_rows = (previous.get("ranking") or {}).get("top20") or []
        prev_ids = [str(row.get("stand_number")) for row in prev_rows]
        sets_top5[lid] = prev_ids[:5]
        sets_top20[lid] = prev_ids[:20]
    from collections import Counter

    top20_counts = Counter()
    top5_counts = Counter()
    for stands in sets_top20.values():
        top20_counts.update(stands)
    for stands in sets_top5.values():
        top5_counts.update(stands)
    repeated_top20 = {stand: count for stand, count in top20_counts.items() if count >= 2}
    repeated_top5 = {stand: count for stand, count in top5_counts.items() if count >= 2}
    all_top5 = [set(v) for v in sets_top5.values()]
    intersection_top5_all = sorted(set.intersection(*all_top5)) if len(all_top5) >= 3 else []
    watch = {
        "334_family": {
            lid: [i + 1 for i, stand in enumerate(ids) if str(stand).replace("RE/", "").replace("1/", "") == "334"]
            for lid, ids in sets_top20.items()
        },
        "373_family": {
            lid: [i + 1 for i, stand in enumerate(ids) if str(stand).replace("RE/", "").replace("1/", "") == "373"]
            for lid, ids in sets_top20.items()
        },
        "yes_pool_cluster": {
            stand: {
                lid: (ids.index(stand) + 1 if stand in ids else None)
                for lid, ids in sets_top20.items()
            }
            for stand in WATCH_REPEAT_STANDS
        },
        "false_positive_116978058_cluster": {
            stand: {
                lid: (ids.index(stand) + 1 if stand in ids else None)
                for lid, ids in sets_top20.items()
            }
            for stand in WATCH_FALSE_POSITIVE_116978058
        },
    }
    current_top5 = set(sets_top5.get(current_listing_id) or [])
    current_top20 = set(sets_top20.get(current_listing_id) or [])
    cluster_in_top5 = [stand for stand in WATCH_REPEAT_STANDS if stand in current_top5]
    cluster_in_top20 = [stand for stand in WATCH_REPEAT_STANDS if stand in current_top20]
    fp_cluster_top5 = [stand for stand in WATCH_FALSE_POSITIVE_116978058 if stand in current_top5]
    fp_cluster_top20 = [stand for stand in WATCH_FALSE_POSITIVE_116978058 if stand in current_top20]
    bias = bool(repeated_top5) or any(item.get("possible_candidate_ranking_bias") for item in pairwise.values())
    return {
        "listings": sorted(sets_top20.keys()),
        "pairwise": pairwise,
        "top5_by_listing": sets_top5,
        "top20_by_listing": {lid: ids[:20] for lid, ids in sets_top20.items()},
        "intersection_top5_all_three": intersection_top5_all,
        "repeated_top5_stands": repeated_top5,
        "repeated_top20_stands": repeated_top20,
        "watch_families": watch,
        "watch_repeat_cluster_in_current_top5": cluster_in_top5,
        "watch_repeat_cluster_in_current_top20": cluster_in_top20,
        "watch_116978058_false_positive_in_current_top5": fp_cluster_top5,
        "watch_116978058_false_positive_in_current_top20": fp_cluster_top20,
        "distinctive_shape_dropped_repeat_cluster": not bool(cluster_in_top5),
        "possible_candidate_ranking_bias": bias,
        "n_listings_compared": len(sets_top20),
        "listing_specific": not bool(intersection_top5_all),
        "note": "Listing-specificity is not proof of accuracy. Repeated high ranks across unrelated listings are a bias flag. The 116978058 Top-5 cluster was later visually rejected; recurrence is a bias flag only and was not used to rerank.",
    }


def run_after_freeze(
    *,
    listing_id: str = LISTING_ID,
    listing_url: str = LISTING_URL,
    out_dir: Path | None = None,
    compare_previous: Path | None = None,
) -> dict[str, Any]:
    dest = Path(out_dir) if out_dir is not None else REPO_ROOT / "data/investigations" / f"blind_{listing_id}_complete_estate"
    freeze_path = dest / "freeze.json"
    all_path = dest / "all_candidates.json"
    if not freeze_path.is_file():
        raise FileNotFoundError("freeze.json missing; refuse to look up ground truth")
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    rows = json.loads(all_path.read_text(encoding="utf-8"))["rows"]
    for row in rows:
        row["hybrid_v2"] = row.get("score")
        row["hybrid_v2_rank"] = row.get("rank")
        row["hybrid_v2_contrib"] = row.get("contrib")
        row["hybrid_v2_shape_v2"] = row.get("shape_v2")
        row["hybrid_v2_spatial_v2"] = row.get("spatial_v2")
    import httpx

    with httpx.Client(timeout=40.0, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
        html = client.get(listing_url).text
    dataset = load_gis_002()
    inventory = load_inventory_002()
    gt = confirm_ground_truth(html, dataset, inventory)
    (dest / "ground_truth.json").write_text(json.dumps(gt, indent=2) + "\n", encoding="utf-8")
    evaluation = evaluate_true_property(freeze, gt, rows)
    detector = None
    if gt.get("confirmed_stand"):
        detector = detector_on_true_erf(str(gt["confirmed_stand"]), dataset, inventory)
        (dest / "detector_true_erf.json").write_text(json.dumps(detector, indent=2) + "\n", encoding="utf-8")
    previous_path = compare_previous or (
        REPO_ROOT / "data/investigations/blind_116273255_complete_estate/freeze.json"
        if listing_id != "116273255"
        else None
    )
    comparison = None
    if previous_path is not None:
        comparison = compare_repeat_candidates((freeze.get("ranking") or {}).get("top20") or [], Path(previous_path))
    three_way = compare_three_complete_estate_blinds((freeze.get("ranking") or {}).get("top20") or [], listing_id)
    marker = json.loads((dest / "rankings_frozen.json").read_text(encoding="utf-8"))
    report_path = dest / "REPORT.md"
    handwritten = None
    if report_path.is_file() and report_path.read_text(encoding="utf-8").lstrip().startswith("# Blind PIE benchmark"):
        handwritten = report_path.read_text(encoding="utf-8")
    write_report(freeze, gt, evaluation, detector, marker.get("panels") or [], dest=dest / "REPORT.auto.md")
    if handwritten:
        report_path.write_text(handwritten, encoding="utf-8")
    elif not report_path.is_file():
        report_path.write_text((dest / "REPORT.auto.md").read_text(encoding="utf-8"), encoding="utf-8")
    (dest / "evaluation.json").write_text(
        json.dumps(
            {
                "ground_truth": gt,
                "evaluation": evaluation,
                "detector": detector,
                "comparison_vs_116273255": comparison,
                "comparison_three_blind_tests": three_way,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return {"ground_truth": gt, "evaluation": evaluation, "detector": detector, "comparison": comparison, "comparison_three": three_way}
