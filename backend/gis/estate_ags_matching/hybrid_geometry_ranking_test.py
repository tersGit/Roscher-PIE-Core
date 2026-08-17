"""Hybrid Pool Geometry v1 × frozen Scoring v2 ranking adapter.

Loads Hybrid listing evidence and scores native15 OS v1 candidates with frozen
Scoring v2 weights. Adapter eligibility follows Hybrid ``scoring_ready`` plus
existing contour integrity. Detector/source is provenance only and is not a
scoring feature.

Does not modify Hybrid extraction, Scoring v2 weights/formula, OS v1, native15,
viewpoint gates, FastSAM extraction, or production ranking.

Water colour is not a scoring feature. Oblique listing area is not treated as
nadir pool area. Missing viewpoint-incompatible terms stay Scoring v2 0.5-neutral.
"""

from __future__ import annotations

from typing import Any

from backend.gis.estate_ags_matching.os_scoring_v2 import (
    OS_KEYS_NO_BUILDING,
    V2_WEIGHTS_NO_BUILDING,
    candidate_spatial_record,
    contour_descriptors,
    score_v2,
    shape_v2_similarity,
    spatial_v2_similarity,
    v2_object_features,
)
from backend.gis.estate_ags_matching.os_v1_experimental_rank import is_high_conf
from backend.gis.estate_ags_matching.pool_geometry import PoolGeometryFingerprint

SCORING_SOURCES = frozenset({"yoloe", "yoloe_sam2", "fastsam_fallback"})
BLOCKED_SOURCES = frozenset({"presence_only", "no_usable_geometry"})


def scoring_ready_frames(frames: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Hybrid scoring-ready frames with a scorable contour.

    Detector identity is not an eligibility filter. ``presence_only`` and
    ``no_usable_geometry`` remain blocked. ``scoring_ready`` does not override
    missing or malformed geometry.
    """
    ready = []
    for frame in frames:
        if not frame.get("scoring_ready"):
            continue
        source = str(frame.get("source") or "")
        if source in BLOCKED_SOURCES or source not in SCORING_SOURCES:
            continue
        contour = _frame_contour(frame)
        if not _contour_passes_integrity(contour):
            continue
        ready.append(frame)
    return ready


def _contour_passes_integrity(contour: list[list[float]] | None) -> bool:
    """Existing Scoring v2 contour integrity. Does not change descriptor math."""
    if not contour or len(contour) < 5:
        return False
    try:
        desc = contour_descriptors(contour)
    except (TypeError, ValueError, ArithmeticError):
        return False
    return desc is not None


def _frame_contour(frame: dict[str, Any], *, secondary: bool = False) -> list[list[float]] | None:
    blob = frame.get("secondary") if secondary else frame.get("dominant")
    contour = None
    if isinstance(blob, dict):
        contour = blob.get("contour_image")
    if not contour:
        contour = frame.get("contour_image")
    if not contour or len(contour) < 5:
        return None
    return contour


def _generic_shape_class(geom: dict[str, Any]) -> str:
    compactness = float(geom.get("compactness") or 0.0)
    solidity = float(geom.get("solidity") or 0.0)
    aspect = float(geom.get("aspect_ratio") or 1.0)
    n_indents = int(geom.get("n_major_indents") or 0)
    if n_indents >= 1 and solidity < 0.95:
        return "irregular"
    if aspect >= 2.2 and solidity >= 0.68:
        return "elongated_rectangular"
    if solidity >= 0.78 and compactness >= 0.55 and aspect < 2.3:
        return "rectangular"
    if compactness < 0.42:
        return "irregular"
    if compactness >= 0.7 and solidity < 0.72:
        return "rounded"
    return "kidney_or_curved"


def fingerprint_from_hybrid_frame(
    frame: dict[str, Any],
    *,
    use_secondary: bool = False,
) -> PoolGeometryFingerprint:
    """Listing fingerprint from one Hybrid scoring-ready frame.

    Spatial pool–house terms are omitted: Hybrid v1 did not emit a
    viewpoint-compatible house relation, and oblique image centroids are not
    comparable to native15 nadir. relative_area is omitted for the same reason.
    """
    if not frame.get("scoring_ready") and not use_secondary:
        raise ValueError("frame is not scoring-ready")
    source = str(frame.get("source") or "")
    if source not in SCORING_SOURCES or source in BLOCKED_SOURCES:
        raise ValueError(f"source {source} cannot supply scoring geometry")
    blob = frame.get("secondary") if use_secondary else frame.get("dominant")
    if not isinstance(blob, dict):
        raise ValueError("requested component is missing")
    contour = _frame_contour(frame, secondary=use_secondary)
    if not _contour_passes_integrity(contour):
        raise ValueError("component contour failed existing integrity requirements")
    geom = blob.get("geometry") or {}
    cx, cy = (blob.get("centroid_xy") or [None, None])[:2]
    role = "secondary" if use_secondary else "dominant"
    notes = [
        "hybrid_pool_geometry_v1",
        f"source={source}",
        f"media={frame.get('media_id')}",
        f"role={role}",
        "oblique",
        "relative_area_omitted_not_nadir",
        "pool_house_spatial_omitted_not_viewpoint_compatible",
        "colour_not_used",
    ]
    return PoolGeometryFingerprint(
        present=True,
        unknown=False,
        shape_class=_generic_shape_class(geom),
        aspect_ratio=geom.get("aspect_ratio"),
        orientation_deg=None,
        compactness=geom.get("compactness"),
        rectangularity=geom.get("solidity"),
        convexity=geom.get("solidity"),
        curved_section_count=int(geom.get("n_major_indents") or 0),
        relative_area=None,
        centroid_x=None if cx is None else float(cx),
        centroid_y=None if cy is None else float(cy),
        house_centroid_x=None,
        house_centroid_y=None,
        pool_to_house_dx=None,
        pool_to_house_dy=None,
        pool_to_house_dist=None,
        pool_to_house_angle_deg=None,
        contour_normalized=[],
        contour_image=contour,
        evidence_media_id=str(frame.get("media_id") or ""),
        notes=notes,
    )


def listing_evidence_from_hybrid_block(block: dict[str, Any]) -> dict[str, Any]:
    """Build official listing evidence from a frozen Hybrid v1 listing block."""
    frames = list(block.get("frames") or [])
    ready = scoring_ready_frames(frames)
    listing_meta = block.get("listing") or {}
    chosen_id = listing_meta.get("chosen_id")
    chosen = next((frame for frame in ready if frame.get("media_id") == chosen_id), None)
    if chosen is None and ready:
        chosen = max(
            ready,
            key=lambda frame: (
                1 if frame.get("source") == "yoloe_sam2" else 0,
                float((frame.get("dominant") or {}).get("structural_support") or 0.0),
                float(frame.get("yoloe_conf") or 0.0),
            ),
        )
    excluded = []
    for frame in frames:
        source = str(frame.get("source") or "")
        if source in BLOCKED_SOURCES or not frame.get("scoring_ready"):
            excluded.append(
                {
                    "media_id": frame.get("media_id"),
                    "source": source,
                    "scoring_ready": bool(frame.get("scoring_ready")),
                    "reason": "presence_only_or_no_usable_geometry"
                    if source in BLOCKED_SOURCES
                    else "not_scoring_ready",
                }
            )
    fingerprint = None if chosen is None else fingerprint_from_hybrid_frame(chosen)
    listing_shape = None
    if fingerprint is not None:
        listing_shape = contour_descriptors(fingerprint.contour_image)
    secondary = None if chosen is None else chosen.get("secondary")
    return {
        "chosen_id": None if chosen is None else chosen.get("media_id"),
        "chosen_source": None if chosen is None else chosen.get("source"),
        "chosen_viewpoint": None if chosen is None else chosen.get("viewpoint"),
        "scoring_ready_ids": [frame.get("media_id") for frame in ready],
        "feature_sources": {
            "shape_from": None if chosen is None else chosen.get("media_id"),
            "spatial_from": None,
            "scale_from": None,
            "relative_area_used": False,
            "colour_used": False,
            "fastsam_used": bool(chosen is not None and chosen.get("source") == "fastsam_fallback"),
            "secondary_recorded": bool(secondary),
            "secondary_in_official_contour": False,
        },
        "excluded_frames": excluded,
        "fingerprint": fingerprint,
        "listing_shape": listing_shape,
        "chosen_frame": chosen,
        "ready_frames": ready,
        "oblique": True,
        "nadir_area_manufactured": False,
        "component_relation": None if chosen is None else chosen.get("component_relation"),
        "descriptors": None if chosen is None else chosen.get("descriptors"),
    }


def score_one_candidate(
    listing: PoolGeometryFingerprint,
    listing_shape: dict[str, Any] | None,
    seg: dict[str, Any],
    *,
    aerial: float | None,
    exterior: float | None,
    stand_size: float,
) -> dict[str, Any]:
    feats = v2_object_features(
        listing,
        seg,
        listing_shape=listing_shape,
        listing_has_driveway=False,
        listing_driveway_side=None,
        include_building_coarse=False,
    )
    cand_desc = None
    pool = seg.get("pool") or {}
    if is_high_conf(pool):
        cand_desc = contour_descriptors(pool.get("contour") or (pool.get("geometry") or {}).get("contour_image"))
    shape_score, shape_parts = shape_v2_similarity(listing_shape, cand_desc)
    spatial_score, spatial_parts = spatial_v2_similarity(listing, seg)
    score, contrib, coverage, factor = score_v2(
        feats,
        aerial=aerial,
        exterior=exterior,
        stand_size=stand_size,
        weights=V2_WEIGHTS_NO_BUILDING,
        os_keys=OS_KEYS_NO_BUILDING,
        missing="neutral",
    )
    return {
        "score": score,
        "contrib": contrib,
        "coverage": coverage,
        "factor": factor,
        "feats": feats,
        "shape_v2": shape_score,
        "spatial_v2": spatial_score,
        "shape_parts": {key: val for key, val in shape_parts.items() if key != "norm_xy"},
        "spatial_parts": spatial_parts,
        "spatial_record": candidate_spatial_record(seg),
        "cand_desc": None if cand_desc is None else {key: val for key, val in cand_desc.items() if key != "norm_xy"},
        "os_pool_status": pool.get("status"),
        "os_building_status": (seg.get("building") or {}).get("status"),
        "os_driveway_status": (seg.get("driveway") or {}).get("status"),
        "os_high_conf_pool": is_high_conf(pool),
    }


def rank_rows(rows: list[dict[str, Any]], score_key: str) -> list[dict[str, Any]]:
    ordered = sorted(rows, key=lambda row: (-float(row[score_key]), str(row["stand_number"])))
    for index, row in enumerate(ordered, start=1):
        row[f"{score_key}_rank"] = index
    return ordered


def public_fingerprint(fp: PoolGeometryFingerprint | None) -> dict[str, Any] | None:
    if fp is None:
        return None
    data = fp.model_dump()
    data.pop("contour_normalized", None)
    data.pop("contour_image", None)
    return data


def public_shape(desc: dict[str, Any] | None) -> dict[str, Any] | None:
    if not desc:
        return None
    return {key: val for key, val in desc.items() if key != "norm_xy"}
