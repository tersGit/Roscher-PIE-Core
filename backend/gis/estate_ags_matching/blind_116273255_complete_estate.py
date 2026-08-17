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
STREET_RE = re.compile(
    r"(?i)\b\d{1,5}[A-Za-z]?\s+[A-Za-z][A-Za-z0-9'\-]*(?:\s+[A-Za-z][A-Za-z0-9'\-]*){0,4}"
    r"\s+(?:street|st\.?|road|rd\.?|drive|dr\.?|close|avenue|ave\.?|way|crescent|cres\.?)\b"
)
POOL_TEXT_RE = re.compile(
    r"(?i)\b(?:private\s+pool|l-?shaped\s+pool|swimming\s+pool|pool)\b"
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


def load_os_payload(stand: str) -> dict[str, Any]:
    complete = os_json_path_for(stand, COMPLETE_OS_DIR)
    frozen = os_json_path_for(stand, DEFAULT_OS_DIR)
    if complete.is_file():
        return json.loads(complete.read_text(encoding="utf-8"))
    if frozen.is_file():
        return json.loads(frozen.read_text(encoding="utf-8"))
    return {}


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
    bodies = download_images(listing.image_urls, photos_dir, listing_id)
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
        "video_available": bool(listing.video_urls),
        "video_count": len(listing.video_urls),
        "feature_hits": hits,
        "pool_text_present": bool(POOL_TEXT_RE.search(redacted)),
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
    else:
        status = "UNKNOWN"
        reason = "insufficient_listing_pool_evidence"
    return {
        "listing_pool_status": status,
        "reason": reason,
        "evidence": evidence,
        "text_yes": text_yes,
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
        "fingerprint_obj": evidence["fingerprint"],
        "listing_shape_obj": evidence["listing_shape"],
        "evidence_obj": evidence,
    }


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
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for parcel in survivors:
        stand = str(parcel["stand_number"])
        sims = clip_sims.get(stand) or {}
        size_score = stand_size_support(listing_erf_sqm, parcel.get("area_sqm"))
        scored = score_one_candidate(
            fingerprint,
            listing_shape,
            load_os_payload(stand),
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
                "township": row.get("township"),
                "area_sqm": row.get("area_sqm"),
                "score": row["hybrid_v2"],
                "inventory_pool_status": row.get("inventory_pool_status"),
                "os_pool_status": row.get("os_pool_status"),
                "os_building_status": row.get("os_building_status"),
                "os_driveway_status": row.get("os_driveway_status"),
                "os_high_conf_pool": row.get("os_high_conf_pool"),
                "pool_geometry_support": row.get("pool_geometry_support"),
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
            }
        )
    return slim


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
            "scene_counts": photo_classes.get("scene_counts"),
        }
    )
    ranked = sorted(rows, key=lambda row: int(row["hybrid_v2_rank"]))
    body = {
        "experiment": "blind_116273255_complete_estate",
        "dataset_id": DATASET_ID,
        "listing_id": LISTING_ID,
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
        "clip_computed_on": "all_pool_gate_survivors_with_native15_crops",
        "official_score": "hybrid_v2",
        "acquisition": acq,
        "listing_pool_gate": listing_pool,
        "estate_pool_gate": gate_public(gate),
        "listing_fingerprint": {
            "hybrid_evidence": fingerprint["hybrid_evidence"],
            "qualitative": fingerprint["qualitative"],
        },
        "crop_stats": crop_stats,
        "ranking": {
            "n_candidates": len(ranked),
            "top20": top_n(ranked, 20),
            "top10": top_n(ranked, 10),
            "top5": top_n(ranked, 5),
            "top1": None if not ranked else top_n(ranked, 1)[0],
        },
        "frozen_001_untouched": {
            "gis_sha256_expected": FROZEN_001_GIS_SHA256,
            "inventory_sha256_expected": FROZEN_001_INVENTORY_SHA256,
            "gis_sha256": sha256_file(FROZEN_001_GIS) if FROZEN_001_GIS.is_file() else None,
            "inventory_sha256": sha256_file(FROZEN_001_INVENTORY) if FROZEN_001_INVENTORY.is_file() else None,
        },
    }
    digest = sha256_text(canonical_dumps(body))
    body["sha256"] = digest
    return body


def write_freeze(payload: Mapping[str, Any], rows: Sequence[Mapping[str, Any]], dest: Path = FREEZE_PATH) -> str:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    slim = []
    for row in sorted(rows, key=lambda item: int(item["hybrid_v2_rank"])):
        slim.append(
            {
                "rank": row["hybrid_v2_rank"],
                "stand_number": row["stand_number"],
                "township": row.get("township"),
                "area_sqm": row.get("area_sqm"),
                "score": row["hybrid_v2"],
                "inventory_pool_status": row.get("inventory_pool_status"),
                "os_pool_status": row.get("os_pool_status"),
                "os_high_conf_pool": row.get("os_high_conf_pool"),
                "shape_v2": row.get("hybrid_v2_shape_v2"),
                "spatial_v2": row.get("hybrid_v2_spatial_v2"),
                "coverage": row.get("hybrid_v2_coverage"),
                "aerial_similarity": row.get("aerial_similarity"),
                "exterior_similarity": row.get("exterior_similarity"),
                "contrib": row.get("hybrid_v2_contrib"),
            }
        )
    ALL_CANDIDATES_PATH.write_text(
        json.dumps({"n": len(slim), "rows": slim}, indent=2) + "\n",
        encoding="utf-8",
    )
    (dest.parent / "freeze.sha256").write_text(str(payload["sha256"]) + "\n", encoding="utf-8")
    return str(payload["sha256"])


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
) -> list[str]:
    dest.mkdir(parents=True, exist_ok=True)
    by_stand = {str(item["stand_number"]): item for item in pass1_parcels(dataset)}
    scenes = photo_classes.get("scenes") or {}
    pool_ids = list(photo_classes.get("useful_pool_views") or [])
    ext_ids = list(photo_classes.get("useful_exterior_views") or [])
    drive_ids = list(photo_classes.get("useful_driveway_garage_views") or [])
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
        gap = 12
        width = max(listing.size[0], analysis.size[0], geometry.size[0]) + 24
        height = listing.size[1] + analysis.size[1] + geometry.size[1] + 80
        canvas = Image.new("RGB", (width, height), (12, 12, 12))
        draw = ImageDraw.Draw(canvas)
        draw.text((12, 8), f"Top-{row['hybrid_v2_rank']} proof  {stand}  hybrid_v2={row['hybrid_v2']}", fill=(240, 240, 240), font=_font(18))
        y = 36
        canvas.paste(listing, (12, y))
        y += listing.size[1] + gap
        canvas.paste(analysis, (12, y))
        y += analysis.size[1] + gap
        draw.text((12, y), "Pool-to-house / driveway / building overlay on raw native15", fill=(210, 210, 210), font=_font(14))
        y += 20
        canvas.paste(geometry, (12, y))
        path = dest / f"top{row['hybrid_v2_rank']}_{safe_stand(stand)}.jpg"
        canvas.convert("RGB").save(path, quality=90)
        written.append(str(path.relative_to(REPO_ROOT)))
    return written


def run_freeze(*, observe_objects: bool = True) -> dict[str, Any]:
    started = time.time()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dataset = load_gis_002()
    parcels = pass1_parcels(dataset)
    inventory = load_inventory_002()
    if len(parcels) != 400:
        raise RuntimeError(f"expected 400 unique erven, got {len(parcels)}")

    acquisition = acquire_listing()
    photos = acquisition["photos"]
    photo_classes = classify_listing_photos(photos)
    hybrid_block = load_hybrid_block()
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
    crop_stats = ensure_native15_crops(dataset, parcels)
    fingerprint = listing_fingerprint(hybrid_block, photo_classes)
    listing_vecs = clip_listing_vectors(photos, photo_classes["scenes"])
    clip_sims = clip_candidate_similarities(gate.survivors, listing_vecs)
    rows = rank_survivors(
        gate.survivors,
        fingerprint["fingerprint_obj"],
        fingerprint["listing_shape_obj"],
        listing_erf_sqm=acquisition.get("erf_size_sqm"),
        clip_sims=clip_sims,
    )
    payload = freeze_payload(
        acquisition=acquisition,
        photo_classes=photo_classes,
        listing_pool=listing_pool,
        gate=gate,
        fingerprint=fingerprint,
        rows=rows,
        crop_stats=crop_stats,
    )
    marker_runtime = round(time.time() - started, 2)
    digest = write_freeze(payload, rows)
    panels = draw_top5_panels(rows, photos, photo_classes, dataset)
    marker = {
        "freeze_path": str(FREEZE_PATH.relative_to(REPO_ROOT)),
        "sha256": digest,
        "ground_truth_applied": False,
        "panels": panels,
        "n_candidates": len(rows),
        "listing_pool_status": listing_pool["listing_pool_status"],
        "final_survivor_count": gate.total_survivors,
        "runtime_s_freeze": marker_runtime,
    }
    (OUT_DIR / "rankings_frozen.json").write_text(json.dumps(marker, indent=2) + "\n", encoding="utf-8")
    return {"payload": payload, "rows": rows, "marker": marker, "photos": photos, "dataset": dataset}


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
        confidence = "LOW"
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
        "confidence": confidence if confirmed else "LOW",
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


def write_report(freeze: Mapping[str, Any], gt: Mapping[str, Any] | None, evaluation: Mapping[str, Any] | None, detector: Mapping[str, Any] | None, panels: Sequence[str]) -> None:
    acq = freeze.get("acquisition") or {}
    listing_pool = freeze.get("listing_pool_gate") or {}
    gate = freeze.get("estate_pool_gate") or {}
    ranking = freeze.get("ranking") or {}
    fp = ((freeze.get("listing_fingerprint") or {}).get("qualitative") or {})
    lines = [
        "# Blind PIE benchmark — listing 116273255 on carlswald_north_corrected_002",
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
        f"- path: `{FREEZE_PATH.relative_to(REPO_ROOT)}`",
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
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_after_freeze() -> dict[str, Any]:
    if not FREEZE_PATH.is_file():
        raise FileNotFoundError("freeze.json missing; refuse to look up ground truth")
    freeze = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    rows = json.loads(ALL_CANDIDATES_PATH.read_text(encoding="utf-8"))["rows"]
    # Rebuild hybrid_v2_rank key expected by evaluate
    for row in rows:
        row["hybrid_v2"] = row.get("score")
        row["hybrid_v2_rank"] = row.get("rank")
        row["hybrid_v2_contrib"] = row.get("contrib")
        row["hybrid_v2_shape_v2"] = row.get("shape_v2")
        row["hybrid_v2_spatial_v2"] = row.get("spatial_v2")
    import httpx

    with httpx.Client(timeout=40.0, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
        html = client.get(LISTING_URL).text
    dataset = load_gis_002()
    inventory = load_inventory_002()
    gt = confirm_ground_truth(html, dataset, inventory)
    GT_PATH.write_text(json.dumps(gt, indent=2) + "\n", encoding="utf-8")
    evaluation = evaluate_true_property(freeze, gt, rows)
    detector = None
    if gt.get("confirmed_stand"):
        detector = detector_on_true_erf(str(gt["confirmed_stand"]), dataset, inventory)
        DETECTOR_PATH.write_text(json.dumps(detector, indent=2) + "\n", encoding="utf-8")
    marker = json.loads((OUT_DIR / "rankings_frozen.json").read_text(encoding="utf-8"))
    handwritten = None
    if REPORT_PATH.is_file() and REPORT_PATH.read_text(encoding="utf-8").lstrip().startswith("# Blind PIE benchmark"):
        handwritten = REPORT_PATH.read_text(encoding="utf-8")
    write_report(freeze, gt, evaluation, detector, marker.get("panels") or [])
    (OUT_DIR / "REPORT.auto.md").write_text(REPORT_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    if handwritten:
        REPORT_PATH.write_text(handwritten, encoding="utf-8")
    (OUT_DIR / "evaluation.json").write_text(
        json.dumps({"ground_truth": gt, "evaluation": evaluation, "detector": detector}, indent=2) + "\n",
        encoding="utf-8",
    )
    return {"ground_truth": gt, "evaluation": evaluation, "detector": detector}
