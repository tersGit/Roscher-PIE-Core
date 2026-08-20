#!/usr/bin/env python3
"""Rank-5 forensic + diagnostic counterfactuals for listing 115503057.

Read-only of freeze.json / freeze.sha256 / rankings / Scoring v2. Does not
rerank the official freeze, retune weights, replace the fingerprint, write
identity into freeze files, or modify production PIE.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.gis.estate_ags_matching.os_scoring_v2 import (  # noqa: E402
    V2_WEIGHTS_NO_BUILDING,
    contour_descriptors,
    shape_v2_similarity,
)

COMPLETE_002_PATH = ROOT / "data/gis/carlswald_north_corrected_002.json"
COMPLETE_OS_DIR = ROOT / "data/investigations/object_segmentation_v1/carlswald_north_complete/json"
DEFAULT_OS_DIR = ROOT / "data/investigations/object_segmentation_v1/carlswald_north/json"
INVENTORY_JSONL = ROOT / "data/estate_inventory/carlswald_north_corrected_002_pool_obs_v1_1_0/current.jsonl"

INV = ROOT / "data/investigations/blind_115503057_complete_estate"
FREEZE = INV / "freeze.json"
SHA = INV / "freeze.sha256"
RANKINGS = INV / "rankings_frozen.json"
CANDS = INV / "all_candidates.json"
PANELS = INV / "panels"
OUT_JSON = INV / "rank5_forensic.json"
OUT_MD = INV / "RANK5_FORENSIC.md"
PANEL_PATH = PANELS / "rank5_top5_forensic_proof.jpg"
LOCK_SHA = "a6465002f681268391d4a87f3039532f47fd97e76d9a43217a8a45c841604ff6"
LOCK_COMMIT = "5aa42ec266a0c515a75e9b7f4da623b0be84dc66"
LOCK_PR = 30
LOCK_BRANCH = "cursor/blind-115503057-complete-estate-dc1a"
GT_STAND = "401"
TOP5 = ["868", "624", "648", "545", "401"]
WEIGHTS = dict(V2_WEIGHTS_NO_BUILDING)
CORNER_JSONL = ROOT / "data/investigations/corner_stand_detection_v1/parcel_corner_records.jsonl"
LABELED_338 = ROOT / "data/investigations/blind_117262832_complete_estate/all_candidates.json"
LABELED_641_DIR = ROOT / "data/investigations/blind_117170887_complete_estate"


def _font(size: int = 14) -> ImageFont.ImageFont:
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ):
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def safe_stand(stand: str) -> str:
    return str(stand).replace("/", "_")


def pass1_parcels(dataset: Mapping[str, Any]) -> list[dict[str, Any]]:
    selected = []
    for item in dataset.get("parcels") or []:
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
        selected.append(item)
    unique: dict[int | str, dict[str, Any]] = {}
    for item in selected:
        unique[item.get("property_id") or item["stand_number"]] = item
    return [unique[key] for key in sorted(unique, key=lambda k: str(k))]


def load_os_payload(stand: str) -> dict[str, Any]:
    name = f"{safe_stand(stand)}.json"
    complete = COMPLETE_OS_DIR / name
    frozen = DEFAULT_OS_DIR / name
    if complete.is_file():
        return json.loads(complete.read_text(encoding="utf-8"))
    if frozen.is_file():
        return json.loads(frozen.read_text(encoding="utf-8"))
    return {}


def verify_freeze() -> dict[str, Any]:
    recorded = SHA.read_text(encoding="utf-8").strip()
    on_disk = hashlib.sha256(FREEZE.read_bytes()).hexdigest()
    if recorded != LOCK_SHA or on_disk != LOCK_SHA:
        raise SystemExit(f"freeze hash mismatch recorded={recorded} on_disk={on_disk}")
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    if freeze.get("ground_truth_applied") is not False:
        raise SystemExit("freeze ground_truth_applied must remain false")
    if freeze.get("scoring_v2_weights_modified") is not False:
        raise SystemExit("scoring weights flag changed")
    if freeze.get("colour_used_in_ranking") is not False:
        raise SystemExit("colour used in ranking")
    top5 = [str(row["stand_number"]) for row in freeze["ranking"]["top20"][:5]]
    if top5 != TOP5:
        raise SystemExit(f"frozen Top 5 changed: {top5}")
    rankings = json.loads(RANKINGS.read_text(encoding="utf-8"))
    if rankings.get("sha256") != LOCK_SHA:
        raise SystemExit("rankings_frozen.json sha256 does not match lock")
    return freeze


def _raw_from_row(row: Mapping[str, Any]) -> dict[str, float | None]:
    contrib = row["contrib"]
    pool_raw = None
    if row.get("os_high_conf_pool"):
        pool_raw = 1.0
    stand_w = WEIGHTS["stand_size"]
    size_raw = None
    if stand_w and contrib.get("stand_size") is not None:
        size_raw = float(contrib["stand_size"]) / stand_w
    return {
        "pool_presence": pool_raw,
        "shape_v2": None if row.get("shape_v2") is None else float(row["shape_v2"]),
        "spatial_v2": None if row.get("spatial_v2") is None else float(row["spatial_v2"]),
        "aerial": None if row.get("aerial_similarity") is None else float(row["aerial_similarity"]),
        "exterior": None if row.get("exterior_similarity") is None else float(row["exterior_similarity"]),
        "gis": 0.5,
        "stand_size": size_raw,
    }


def rescore(
    values: Mapping[str, float | None],
    *,
    weights: Mapping[str, float] | None = None,
    missing: str = "neutral",
    fill: float = 0.5,
    drop: set[str] | None = None,
) -> tuple[float, dict[str, float]]:
    used = dict(weights or WEIGHTS)
    for key in drop or ():
        used[key] = 0.0
    filled: dict[str, float] = {}
    active_w: dict[str, float] = {}
    for key, weight in used.items():
        if weight <= 0:
            continue
        val = values.get(key)
        if val is None:
            if missing == "omit":
                continue
            filled[key] = fill
        else:
            filled[key] = float(val)
        active_w[key] = weight
    total_w = sum(active_w[key] for key in filled)
    if total_w <= 0:
        return 0.0, {}
    contrib = {key: filled[key] * active_w[key] / total_w for key in filled}
    return round(float(sum(contrib.values())), 4), {k: round(v, 4) for k, v in contrib.items()}


def rank_of(stand: str, scored: list[tuple[str, float]]) -> int | None:
    ordered = sorted(scored, key=lambda item: (-item[1], item[0]))
    for index, (name, _score) in enumerate(ordered, start=1):
        if name == stand:
            return index
    return None


def _geom(obj: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict((obj or {}).get("geometry") or {})


def _clip(obj: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = obj or {}
    return dict(payload.get("clip") or payload.get("clip_scores") or payload.get("class_scores") or {})


def os_profile(stand: str, parcel: Mapping[str, Any] | None) -> dict[str, Any]:
    seg = load_os_payload(stand)
    pool = seg.get("pool") or {}
    building = seg.get("building") or {}
    driveway = seg.get("driveway") or {}
    rel = ((seg.get("spatial") or {}).get("relationships") or {})
    pool_house = rel.get("pool_house") or {}
    drive_house = rel.get("driveway_house") or {}
    pov = {
        "final_status": None,
        "confidence": None,
        "object_role": None,
        "reason_codes": None,
        "signals": None,
        "note": "POV copied from freeze row, not recomputed",
    }
    pool_g = _geom(pool)
    bldg_g = _geom(building)
    desc = None
    contour = pool.get("contour") or pool_g.get("contour_image")
    if contour:
        desc = contour_descriptors(contour)
        if desc is not None:
            desc = {k: v for k, v in desc.items() if k != "norm_xy"}
    return {
        "os_version": seg.get("version"),
        "pool": {
            "status": pool.get("status"),
            "notes": pool.get("notes"),
            "clip": {k: None if v is None else round(float(v), 4) for k, v in _clip(pool).items()},
            "area_m2": pool_g.get("area_m2"),
            "aspect_ratio": pool_g.get("aspect_ratio"),
            "orientation_deg": pool_g.get("orientation_deg"),
            "shape": pool_g.get("shape"),
            "rectangularity": pool_g.get("rectangularity"),
            "convexity": pool_g.get("convexity"),
            "compactness": pool_g.get("compactness"),
            "relative_area": pool_g.get("relative_area"),
            "centroid": [pool_g.get("centroid_x"), pool_g.get("centroid_y")],
            "contour_n": pool_g.get("contour_n") or (len(contour) if contour else None),
        },
        "building": {
            "status": building.get("status"),
            "clip_roof": (_clip(building) or {}).get("roof"),
            "area_m2": bldg_g.get("area_m2"),
            "aspect_ratio": bldg_g.get("aspect_ratio"),
            "orientation_deg": bldg_g.get("orientation_deg"),
            "shape": bldg_g.get("shape"),
            "rectangularity": bldg_g.get("rectangularity"),
            "compactness": bldg_g.get("compactness"),
            "centroid": [bldg_g.get("centroid_x"), bldg_g.get("centroid_y")],
        },
        "driveway": {
            "status": driveway.get("status"),
            "area_m2": _geom(driveway).get("area_m2"),
            "orientation_deg": _geom(driveway).get("orientation_deg"),
            "n_paved_components": _geom(driveway).get("n_paved_components"),
            "side": drive_house.get("driveway_side"),
        },
        "pool_house": {
            "direction": pool_house.get("direction"),
            "angle_deg": pool_house.get("angle_deg"),
            "distance_m": pool_house.get("distance_m"),
            "parcel_dist": pool_house.get("dist"),
        },
        "cand_shape_desc": desc,
        "pov": pov,
    }


def listing_shape_from_freeze(freeze: Mapping[str, Any]) -> dict[str, Any]:
    he = freeze["listing_fingerprint"]["hybrid_evidence"]
    stored = dict(he.get("listing_shape") or {})
    contour = (he.get("fingerprint") or {}).get("contour_normalized") or freeze["pool_contour_metrics"].get(
        "normalized_contour"
    )
    recomputed = contour_descriptors(contour) if contour else None
    if recomputed is None:
        return stored
    return recomputed


def convex_listing_shape(freeze: Mapping[str, Any]) -> dict[str, Any] | None:
    import cv2

    contour = freeze["pool_contour_metrics"].get("normalized_contour")
    xy = np.asarray(contour or [], dtype=np.float32)
    if xy.ndim != 2 or len(xy) < 5:
        return None
    hull = cv2.convexHull(xy.reshape(-1, 1, 2)).reshape(-1, 2)
    return contour_descriptors(hull)


def load_corners() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if not CORNER_JSONL.is_file():
        return out
    for row in load_jsonl(CORNER_JSONL):
        out[str(row.get("stand_number"))] = row
    return out


def inventory_index() -> dict[str, dict[str, Any]]:
    return {str(row.get("stand_number")): row for row in load_jsonl(INVENTORY_JSONL)}


def freeze_row_map(freeze: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row["stand_number"]): row for row in freeze["ranking"]["top20"]}


def labeled_338_effect(name: str, adjust) -> dict[str, Any]:
    payload = json.loads(LABELED_338.read_text(encoding="utf-8"))
    rows = list(payload["rows"])
    scored = []
    for row in rows:
        values = _raw_from_row(row)
        values = adjust(row, values)
        score, _contrib = rescore(values) if name != "omit_missing_pad" else rescore(values, missing="omit")
        if name == "remove_clip":
            score, _contrib = rescore(values, drop={"aerial", "exterior"})
        elif name == "remove_stand_size":
            score, _contrib = rescore(values, drop={"stand_size"})
        elif name == "missing_as_zero":
            score, _contrib = rescore(values, fill=0.0)
        scored.append((str(row["stand_number"]), score))
    frozen = next(int(row["rank"]) for row in rows if str(row["stand_number"]) == "338")
    diagnostic = rank_of("338", scored)
    return {
        "case": "117262832 / stand 338",
        "frozen_rank": frozen,
        "diagnostic_rank": diagnostic,
        "delta": None if diagnostic is None else diagnostic - frozen,
        "improves": diagnostic is not None and diagnostic < frozen,
        "damages": diagnostic is not None and diagnostic > frozen,
    }


def build_profiles(freeze: Mapping[str, Any]) -> dict[str, Any]:
    dataset = json.loads(COMPLETE_002_PATH.read_text(encoding="utf-8"))
    parcels = {str(item["stand_number"]): item for item in pass1_parcels(dataset)}
    corners = load_corners()
    inventory = inventory_index()
    listing_shape = listing_shape_from_freeze(freeze)
    listing_shape_pub = {k: v for k, v in listing_shape.items() if k != "norm_xy"}
    hull_shape = convex_listing_shape(freeze)
    hull_pub = None if hull_shape is None else {k: v for k, v in hull_shape.items() if k != "norm_xy"}
    rows = freeze_row_map(freeze)
    cands = {str(row["stand_number"]): row for row in json.loads(CANDS.read_text(encoding="utf-8"))["rows"]}
    listing_floor = freeze["acquisition"].get("floor_size_sqm")
    listing_erf = freeze["acquisition"].get("erf_size_sqm")

    profiles = []
    for stand in TOP5:
        row = rows[stand]
        parcel = parcels[stand]
        inv = inventory.get(stand) or {}
        corner = corners.get(stand) or {}
        os_info = os_profile(stand, parcel)
        cand_desc = None
        seg = load_os_payload(stand)
        pool = seg.get("pool") or {}
        contour = pool.get("contour") or (pool.get("geometry") or {}).get("contour_image")
        if contour:
            cand_desc = contour_descriptors(contour)
        shape_score, shape_parts = shape_v2_similarity(listing_shape, cand_desc)
        hull_score, hull_parts = (None, {})
        if hull_shape is not None:
            hull_score, hull_parts = shape_v2_similarity(hull_shape, cand_desc)
        spatial = row.get("spatial_record") or {}
        pool_m2 = os_info["pool"]["area_m2"]
        bldg_m2 = os_info["building"]["area_m2"]
        area_ratio = None
        if pool_m2 and bldg_m2 and bldg_m2 > 1:
            area_ratio = round(float(pool_m2) / float(bldg_m2), 4)
        floor_ratio = None
        if bldg_m2 and listing_floor:
            floor_ratio = round(float(bldg_m2) / float(listing_floor), 4)
        profiles.append(
            {
                "frozen_rank": row["rank"],
                "stand_number": stand,
                "is_ground_truth": stand == GT_STAND,
                "property_id": row.get("property_id") or parcel.get("property_id"),
                "township": row.get("township") or parcel.get("township"),
                "street_address": parcel.get("street_address"),
                "area_sqm": row.get("area_sqm"),
                "listing_erf_sqm": listing_erf,
                "listing_floor_sqm": listing_floor,
                "score": row["score"],
                "contrib": row["evidence_contributors"],
                "shape_v2": row["shape_v2"],
                "shape_v2_recomputed": shape_score,
                "shape_parts": {k: None if v is None else round(float(v), 4) for k, v in shape_parts.items()},
                "hull_shape_v2": hull_score,
                "hull_shape_parts": {k: None if v is None else round(float(v), 4) for k, v in hull_parts.items()},
                "spatial_v2": row["spatial_v2"],
                "coverage": row["coverage"],
                "aerial_similarity": row["aerial_similarity"],
                "exterior_similarity": row["exterior_similarity"],
                "size_score": row.get("size_score"),
                "neutral_components": row.get("neutral_components"),
                "inventory_pool_status": row["inventory_pool_status"],
                "inventory": {
                    "pool_status": inv.get("pool_status"),
                    "os_pool_status": inv.get("os_pool_status"),
                    "confidence": inv.get("pool_confidence"),
                    "unknown_reason": inv.get("unknown_reason"),
                    "diagnostic_flags": inv.get("diagnostic_flags"),
                    "pool_area_m2": inv.get("pool_area_m2"),
                    "observability": None
                    if not inv.get("pool_observability")
                    else {
                        "adequate_for_absence": inv["pool_observability"].get("adequate_for_absence"),
                        "canopy_occludes": inv["pool_observability"].get("canopy_occludes"),
                        "canopy_fraction": inv["pool_observability"].get("canopy_fraction"),
                        "visible_open_fraction": inv["pool_observability"].get("visible_open_fraction"),
                    },
                },
                "parcel_corner": row.get("parcel_corner"),
                "corner_record": {
                    "classification": corner.get("classification"),
                    "confidence": corner.get("confidence"),
                    "reason": corner.get("reason"),
                    "roads": corner.get("distinct_road_names"),
                    "n_road_facing_sides": corner.get("n_road_facing_sides"),
                    "intersection_proximity_m": corner.get("intersection_proximity_m"),
                },
                "candidate_pov_status": row.get("candidate_pov_status"),
                "frozen_os_pool_status": row.get("frozen_os_pool_status"),
                "os": os_info,
                "spatial_record": spatial,
                "pool_building_area_ratio": area_ratio,
                "building_to_listing_floor_ratio": floor_ratio,
                "all_candidates_row": cands.get(stand),
            }
        )
    return {
        "listing_shape": listing_shape_pub,
        "listing_hull_shape": hull_pub,
        "profiles": profiles,
        "parcels": parcels,
    }


def run_counterfactuals(freeze: Mapping[str, Any], bundle: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = json.loads(CANDS.read_text(encoding="utf-8"))["rows"]
    profiles = {str(item["stand_number"]): item for item in bundle["profiles"]}
    listing_shape = listing_shape_from_freeze(freeze)
    hull_shape = convex_listing_shape(freeze)

    os_cache: dict[str, dict[str, Any]] = {}

    def os_of(stand: str) -> dict[str, Any]:
        if stand not in os_cache:
            os_cache[stand] = load_os_payload(stand)
        return os_cache[stand]

    def base_values(row: Mapping[str, Any]) -> dict[str, float | None]:
        return _raw_from_row(row)

    experiments: list[tuple[str, str, Any]] = []

    def apply_all(name: str, title: str, scorer) -> dict[str, Any]:
        scored = []
        for row in rows:
            stand = str(row["stand_number"])
            score = scorer(row)
            scored.append((stand, score))
        frozen_rank = 5
        diagnostic = rank_of(GT_STAND, scored)
        top5 = [s for s, _ in sorted(scored, key=lambda item: (-item[1], item[0]))[:5]]
        labeled = []
        if LABELED_338.is_file():
            def _adj(row, values):
                return values

            if name in {"remove_clip", "remove_stand_size", "omit_missing_pad", "missing_as_zero"}:
                labeled.append(labeled_338_effect(name, _adj))
            else:
                labeled.append(
                    {
                        "case": "117262832 / stand 338",
                        "frozen_rank": 122,
                        "diagnostic_rank": None,
                        "note": "scoring-only CF not reapplied; 338 has no high-conf pool so pool-geometry CFs do not change its frozen 0.5847 unless missing-data treatment changes",
                        "improves": False,
                        "damages": False,
                    }
                )
        if LABELED_641_DIR.is_dir():
            labeled.append(
                {
                    "case": "117170887 / stand 641",
                    "frozen_rank": None,
                    "diagnostic_rank": None,
                    "note": "never ranked (inventory NO / Pool Gate). Scoring counterfactuals cannot move 641.",
                    "improves": False,
                    "damages": False,
                }
            )
        gt_score = next(score for stand, score in scored if stand == GT_STAND)
        return {
            "id": name,
            "title": title,
            "401_frozen_rank": frozen_rank,
            "401_diagnostic_rank": diagnostic,
            "401_diagnostic_score": gt_score,
            "improves_401": diagnostic is not None and diagnostic < frozen_rank,
            "damages_401": diagnostic is not None and diagnostic > frozen_rank,
            "diagnostic_top5": top5,
            "labeled_cases": labeled,
            "select_because_401_moves": False,
        }

    experiments.append(
        (
            "reproduce_frozen",
            "Reproduce freeze with stored components (sanity)",
            lambda row: rescore(base_values(row))[0],
        )
    )
    experiments.append(
        (
            "remove_clip",
            "Remove CLIP aerial+exterior contribution (renormalize remaining weights)",
            lambda row: rescore(base_values(row), drop={"aerial", "exterior"})[0],
        )
    )
    experiments.append(
        (
            "remove_stand_size",
            "Remove stand-size contribution (renormalize remaining weights)",
            lambda row: rescore(base_values(row), drop={"stand_size"})[0],
        )
    )
    experiments.append(
        (
            "omit_missing_pad",
            "Correct UNKNOWN treatment: omit null spatial/aerial instead of 0.5-pad, renormalize",
            lambda row: rescore(base_values(row), missing="omit")[0],
        )
    )
    experiments.append(
        (
            "missing_as_zero",
            "Treat missing spatial/aerial as 0 instead of 0.5 (does not distinguish equal-missing candidates)",
            lambda row: rescore(base_values(row), fill=0.0)[0],
        )
    )

    def stronger_validated(row):
        values = base_values(row)
        status = str(row.get("candidate_pov_status") or row.get("os_pool_status") or "")
        if status != "CONFIRMED":
            values["pool_presence"] = None
            values["shape_v2"] = None
        return rescore(values)[0]

    experiments.append(
        (
            "stronger_validated_pool",
            "Stronger validated-pool: only POV/OS CONFIRMED keep pool_presence+shape; else missing",
            stronger_validated,
        )
    )

    def pool_too_large(row):
        values = base_values(row)
        stand = str(row["stand_number"])
        pool_m2 = ((os_of(stand).get("pool") or {}).get("geometry") or {}).get("area_m2")
        if pool_m2 is not None and float(pool_m2) > 55.0 and values.get("shape_v2") is not None:
            values["shape_v2"] = float(values["shape_v2"]) * 0.35
        return rescore(values)[0]

    experiments.append(
        (
            "listing_lap_pool_upper_bound",
            "Listing-visual lap-pool upper bound: down-weight shape_v2 if candidate pool > 55 m²",
            pool_too_large,
        )
    )

    def building_floor(row):
        values = base_values(row)
        stand = str(row["stand_number"])
        bldg = ((os_of(stand).get("building") or {}).get("geometry") or {}).get("area_m2")
        floor = freeze["acquisition"].get("floor_size_sqm") or 0
        if bldg is not None and floor and float(bldg) < 0.30 * float(floor):
            extra = dict(values)
            extra["building_plausible"] = 0.15
            weights = dict(WEIGHTS)
            weights["building_plausible"] = 0.08
            return rescore(extra, weights=weights)[0]
        extra = dict(values)
        extra["building_plausible"] = 0.85
        weights = dict(WEIGHTS)
        weights["building_plausible"] = 0.08
        return rescore(extra, weights=weights)[0]

    experiments.append(
        (
            "building_vs_listing_floor",
            "Listing floor 672 m² / two-storey copy: penalise OS building footprint < 30% of floor",
            building_floor,
        )
    )

    def adjacent_pool(row):
        values = base_values(row)
        stand = str(row["stand_number"])
        edge = None
        if stand in profiles:
            edge = (profiles[stand].get("spatial_record") or {}).get("nearest_edge_norm")
        if edge is None:
            rec = ((os_of(stand).get("spatial") or {}).get("relationships") or {}).get("pool_house") or {}
            edge = rec.get("nearest_edge_norm")
        if edge is not None:
            # Listing frames 043/044/046 show the pool against the house/deck.
            adj = 1.0 if float(edge) <= 0.08 else max(0.0, 1.0 - (float(edge) - 0.08) / 0.40)
            values["spatial_v2"] = round(adj, 4)
        return rescore(values)[0]

    experiments.append(
        (
            "enforce_pool_house_adjacency",
            "Listing-photo adjacency prior: fill spatial_v2 from candidate nearest-edge (not GT 401 vector)",
            adjacent_pool,
        )
    )

    def hull_shape_cf(row):
        values = base_values(row)
        stand = str(row["stand_number"])
        if hull_shape is None:
            return rescore(values)[0]
        pool = os_of(stand).get("pool") or {}
        contour = pool.get("contour") or (pool.get("geometry") or {}).get("contour_image")
        desc = contour_descriptors(contour) if contour else None
        score, _parts = shape_v2_similarity(hull_shape, desc)
        values["shape_v2"] = score
        return rescore(values)[0]

    experiments.append(
        (
            "corrected_listing_contour_convex_hull",
            "Corrected listing pool object: replace PARTIALLY LOST indented contour with its convex hull",
            hull_shape_cf,
        )
    )

    def driveway_cf(row):
        values = base_values(row)
        stand = str(row["stand_number"])
        status = str((os_of(stand).get("driveway") or {}).get("status") or "UNKNOWN")
        drive = 0.9 if status in {"CONFIRMED", "PROBABLE"} else 0.45
        extra = dict(values)
        extra["driveway"] = drive
        weights = dict(WEIGHTS)
        weights["driveway"] = 0.05
        return rescore(extra, weights=weights)[0]

    experiments.append(
        (
            "enforce_driveway_context",
            "Listing double-garage/driveway views: small bonus for high-conf driveway, not a hard gate",
            driveway_cf,
        )
    )

    out = []
    for name, title, fn in experiments:
        result = apply_all(name, title, fn)
        out.append(result)
    # sanity: reproduce frozen rank 5 and score
    repro = next(item for item in out if item["id"] == "reproduce_frozen")
    if repro["401_diagnostic_rank"] != 5:
        raise SystemExit(f"sanity rescore moved 401 to {repro['401_diagnostic_rank']}")
    gt_frozen_score = freeze_row_map(freeze)[GT_STAND]["score"]
    if abs(repro["401_diagnostic_score"] - gt_frozen_score) > 0.0006:
        raise SystemExit(f"sanity score mismatch {repro['401_diagnostic_score']} vs {gt_frozen_score}")
    return out


def classify_components(profile: Mapping[str, Any]) -> dict[str, str]:
    stand = profile["stand_number"]
    out = {
        "pool_presence": "strong positive signal" if profile["inventory_pool_status"] == "YES" else "missing",
        "pool_object_validation": "strong positive signal"
        if profile["candidate_pov_status"] == "CONFIRMED"
        else "missing",
        "shape_v2": "useful supporting signal"
        if stand == GT_STAND
        else "misleading",
        "spatial_v2": "missing",
        "aerial": "missing",
        "exterior_clip": "useful supporting signal" if stand == GT_STAND else "neutral",
        "gis": "neutral",
        "stand_size": "useful supporting signal",
        "corner_gate": "neutral",
        "driveway": "useful supporting signal" if (profile.get("spatial_record") or {}).get("driveway_status") == "PROBABLE" else "missing",
        "building_footprint": "useful supporting signal"
        if (profile.get("os") or {}).get("building", {}).get("area_m2")
        and profile["os"]["building"]["area_m2"] > 300
        else "neutral",
        "pool_house_spatial_candidate_only": "useful supporting signal"
        if stand == GT_STAND
        else "neutral",
    }
    return out


def write_panel(freeze: Mapping[str, Any], bundle: Mapping[str, Any]) -> str:
    """Compose a Top-5 proof from freeze-time panels (native15 crops are gitignored)."""
    PANELS.mkdir(parents=True, exist_ok=True)
    rows = freeze_row_map(freeze)
    freeze_panels = {
        "868": PANELS / "top1_868.jpg",
        "624": PANELS / "top2_624.jpg",
        "648": PANELS / "top3_648.jpg",
        "545": PANELS / "top4_545.jpg",
        "401": PANELS / "top5_401.jpg",
    }
    cells = []
    cell_w = 420
    for stand in TOP5:
        row = rows[stand]
        src = freeze_panels[stand]
        if src.is_file():
            overlay = Image.open(src).convert("RGB")
            overlay.thumbnail((cell_w, 320))
        else:
            overlay = Image.new("RGB", (cell_w, 240), (30, 30, 30))
        mark = "GT" if stand == GT_STAND else "FP"
        contrib = row["evidence_contributors"]
        spatial = row.get("spatial_record") or {}
        title = f"#{row['rank']}  stand {stand}  {mark}  score={row['score']}"
        subtitle = (
            f"shape_v2={row['shape_v2']}  CLIP_ext={row['exterior_similarity']}  "
            f"size={row.get('size_score')}  pool {spatial.get('direction')} {spatial.get('distance_m')}m"
        )
        canvas = Image.new("RGB", (cell_w, overlay.size[1] + 92), (16, 16, 16))
        draw = ImageDraw.Draw(canvas)
        draw.text((8, 4), title, fill=(240, 240, 240), font=_font(14))
        draw.text((8, 22), subtitle[:88], fill=(180, 180, 180), font=_font(11))
        draw.text(
            (8, 40),
            f"contrib pool={contrib['pool_presence']} shape={contrib['shape_v2']} "
            f"spat={contrib['spatial_v2']} air={contrib['aerial']} "
            f"ext={contrib['exterior']} gis={contrib['gis']} sz={contrib['stand_size']}",
            fill=(160, 200, 160),
            font=_font(10),
        )
        draw.text(
            (8, 56),
            f"inv={row['inventory_pool_status']} POV={row.get('candidate_pov_status')} "
            f"corner={row.get('parcel_corner')} drv={spatial.get('driveway_status')} "
            f"yellow=parcel cyan=pool red=bldg green=drive yellow line=pool→house",
            fill=(160, 160, 200),
            font=_font(10),
        )
        canvas.paste(overlay, (max(0, (cell_w - overlay.size[0]) // 2), 74))
        cells.append(canvas)

    listing_cells = []
    for label, path in (
        ("fingerprint 043 + contour", INV / "listing_pool_contour_proof.png"),
        ("listing 043 official pick", INV / "distinctive_contour_v2/115503057-043.jpg"),
        ("listing 004 front/garage", INV / "distinctive_contour_v2/115503057-004.jpg"),
        ("listing 046 pool in L of house", INV / "distinctive_contour_v2/115503057-046.jpg"),
    ):
        if not path.is_file():
            continue
        img = Image.open(path).convert("RGB")
        img.thumbnail((320, 220))
        box = Image.new("RGB", (320, img.size[1] + 28), (16, 16, 16))
        draw = ImageDraw.Draw(box)
        draw.text((8, 6), label, fill=(230, 230, 230), font=_font(12))
        box.paste(img, ((320 - img.size[0]) // 2, 24))
        listing_cells.append(box)

    gap = 8
    header_h = 96
    listing_h = max((im.size[1] for im in listing_cells), default=0) + 32
    top_h = max(im.size[1] for im in cells)
    width = max(
        sum(im.size[0] for im in cells) + gap * (len(cells) + 1),
        sum(im.size[0] for im in listing_cells) + gap * (len(listing_cells) + 1),
        1600,
    )
    height = header_h + listing_h + top_h + 36
    canvas = Image.new("RGB", (width, height), (8, 8, 8))
    draw = ImageDraw.Draw(canvas)
    draw.text((12, 8), "115503057 Rank-5 forensic proof — freeze untouched", fill=(240, 240, 240), font=_font(18))
    draw.text(
        (12, 32),
        f"PR #{LOCK_PR}  freeze {LOCK_COMMIT[:12]}  SHA256 {LOCK_SHA[:16]}…  Top 5: 868 / 624 / 648 / 545 / 401",
        fill=(190, 190, 190),
        font=_font(13),
    )
    draw.text(
        (12, 52),
        "Freeze-time Top-5 panels (parcel / pool / building / driveway / pool-to-house vector) with freeze component scores. Not a rerank.",
        fill=(160, 160, 160),
        font=_font(12),
    )
    draw.text((12, 72), "Listing evidence (official 043 contour + freeze-time photos)", fill=(210, 210, 210), font=_font(13))
    x = gap
    y = header_h
    for img in listing_cells:
        canvas.paste(img, (x, y))
        x += img.size[0] + gap
    y = header_h + listing_h
    draw.text((12, y - 22), "Frozen Top 5 — 868/624/648/545 false; 401 independent GT / blind rank 5", fill=(210, 210, 210), font=_font(13))
    x = gap
    for img in cells:
        canvas.paste(img, (x, y))
        x += img.size[0] + gap
    canvas.save(PANEL_PATH, quality=90)
    return str(PANEL_PATH.relative_to(ROOT))


def _md_table(headers: list[str], rows: list[list[Any]]) -> str:
    line = "| " + " | ".join(headers) + " |"
    text_headers = {
        "stand",
        "street",
        "township",
        "inv",
        "pov",
        "corner",
        "component",
        "id",
        "title",
        "driveway status",
        "parcel corner",
    }
    aligns = ["---" if h.lower() in text_headers else "---:" for h in headers]
    sep = "| " + " | ".join(aligns) + " |"
    body = []
    for row in rows:
        body.append("| " + " | ".join("null" if v is None else str(v) for v in row) + " |")
    return "\n".join([line, sep, *body])


def write_report(freeze: Mapping[str, Any], bundle: Mapping[str, Any], counterfactuals: list[dict[str, Any]], panel_rel: str) -> None:
    profiles = bundle["profiles"]
    by_stand = {p["stand_number"]: p for p in profiles}
    gt = by_stand[GT_STAND]
    listing_fp = freeze["listing_fingerprint"]
    he = listing_fp["hybrid_evidence"]
    integrity = {
        "pr": LOCK_PR,
        "branch": LOCK_BRANCH,
        "freeze_commit": LOCK_COMMIT,
        "sha256": LOCK_SHA,
        "sha256_verified": True,
        "401_frozen_rank": 5,
        "frozen_top5": TOP5,
        "ranking_files_modified": False,
        "scoring_v2_weights": dict(WEIGHTS),
        "weights_modified": False,
        "colour_used": False,
        "ground_truth_applied_to_ranking": False,
    }
    payload = {
        "experiment": "blind_115503057_rank5_forensic",
        "not_a_rerank": True,
        "pie_modified": False,
        "production_scoring_modified": False,
        "freeze_integrity": integrity,
        "listing_fingerprint": {
            "media_id": he.get("chosen_id"),
            "source": he.get("chosen_source"),
            "viewpoint": he.get("chosen_viewpoint"),
            "geometry_loss": (he.get("descriptors") or {}).get("geometry_loss"),
            "shape_class": (he.get("fingerprint") or {}).get("shape_class"),
            "hybrid_aspect": (he.get("descriptors") or {}).get("aspect_ratio"),
            "listing_shape": bundle["listing_shape"],
            "pool_house_spatial": None,
            "oblique": True,
        },
        "profiles": profiles,
        "counterfactuals": counterfactuals,
        "panel": panel_rel,
    }
    # strip bulky all_candidates_row copies / parcel geometry from json profiles
    slim_profiles = []
    for item in profiles:
        copy = dict(item)
        copy.pop("all_candidates_row", None)
        slim_profiles.append(copy)
    payload["profiles"] = slim_profiles
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")

    fp_causes = []
    # rank 1 868
    fp_causes.append(
        {
            "stand": "868",
            "rank": 1,
            "prefer_401_because": (
                "Highest freeze-time shape_v2 (0.8261 vs 401 0.7712) against the official oblique 043 contour. "
                "The 0.0549 shape gap × 0.36 weight = +0.0198, larger than the 0.0113 total-score gap. "
                "868's n_indents part is 1.0 vs 401 0.5 (listing fingerprint has 1 major indent from PARTIALLY LOST spa/secondary). "
                "Pool presence, spatial pad, aerial pad, and GIS are identical. 868 loses stand_size and exterior CLIP to 401."
            ),
            "classes": [
                "pool geometry false positive",
                "segmentation error",
                "scoring-weight issue",
                "genuine visual similarity",
            ],
            "ab": "B primary (incorrect/misinterpreted listing contour: PARTIALLY LOST / freeform irregular official shape matches 868's curved backyard pool better than 401's rectilinear lap pool). A secondary: both are in-parcel elongated-ish YES pools, so shape_v2 is allowed to fire.",
        }
    )
    fp_causes.append(
        {
            "stand": "624",
            "rank": 2,
            "prefer_401_because": (
                "shape_v2 0.7777 vs 401 0.7712 and the closest Top-5 GIS size (886 vs advertised 897; size_score 0.9727 vs 0.9455). "
                "Exterior CLIP also slightly higher (0.7827 vs 0.7724). Candidate pool is 80.66 m² — scale-invariant shape_v2 does not penalise that."
            ),
            "classes": [
                "genuine visual similarity",
                "pool geometry false positive",
                "house/roof mismatch not sufficiently penalised",
                "scoring-weight issue",
            ],
            "ab": "A: elongated in-parcel pool and near-897 GIS size are correct evidence that happens to favour a wrong house. B: listing lap-pool scale is not in Scoring v2, so an 81 m² pool is treated as the same shape family as a ~23 m² lap pool.",
        }
    )
    fp_causes.append(
        {
            "stand": "648",
            "rank": 3,
            "prefer_401_because": (
                "shape_v2 0.7902 vs 401 0.7712. OS building footprint is only 138 m² against listing floor 672 m²; "
                "pool is 20.77 m from house (nearest_edge_norm 0.462) vs listing photos of a house-adjacent lap pool. "
                "spatial_v2 was padded 0.5 for everyone, so this mismatch did not cost 648."
            ),
            "classes": [
                "segmentation error",
                "pool-house spatial mismatch not sufficiently penalised",
                "house/roof mismatch not sufficiently penalised",
                "missing-data advantage",
            ],
            "ab": "B: undersized building mask and far pool-house geometry are incorrect/incomplete evidence that Scoring v2 could not use because listing spatial was omitted and building is not a v2 term. A: the elongated pool contour still legitimately scores on shape_v2.",
        }
    )
    fp_causes.append(
        {
            "stand": "545",
            "rank": 4,
            "prefer_401_because": (
                "Highest exterior CLIP in the Top 5 (0.8046 vs 401 0.7724) plus near-tie shape_v2 (0.7685 vs 0.7712) and near-identical stand_size (918 vs 919 m²). "
                "Parcel is a confirmed corner (Buffalo Thorn × Black Monkey Thorn); listing CORNER=UNKNOWN so Corner Gate was a no-op. Driveway OS=UNKNOWN."
            ),
            "classes": [
                "genuine visual similarity",
                "CLIP failure",
                "driveway/context mismatch",
                "parcel/context mismatch",
            ],
            "ab": "A: same-street elongated pool and 918 m² GIS are correct weak evidence. B: CLIP exterior prefers a light/white-roof corner house over the listing charcoal cubist front; driveway UNKNOWN is not penalised; corner mismatch is ungated because listing corner evidence was insufficient.",
        }
    )

    lines: list[str] = []
    a = lines.append
    a("# Rank-5 forensic — listing 115503057 / Stand 401")
    a("")
    a("Diagnostic only. Production PIE, Scoring v2 weights, freeze files, and hashes are unchanged. Ground truth is used solely for post-blind evaluation.")
    a("")
    a(f"Machine-readable twin: `rank5_forensic.json`. Proof panel: `{panel_rel}`.")
    a("")
    a("## A. Frozen-test integrity")
    a("")
    a("| Item | Value |")
    a("| --- | --- |")
    a(f"| PR | [#{LOCK_PR}](https://github.com/tersGit/Roscher-PIE-Core/pull/{LOCK_PR}) |")
    a(f"| Branch | `{LOCK_BRANCH}` |")
    a(f"| Freeze commit | `{LOCK_COMMIT}` |")
    a(f"| Freeze SHA256 | `{LOCK_SHA}` |")
    a("| SHA256 vs on-disk `freeze.json` | **MATCH** |")
    a("| SHA256 vs `rankings_frozen.json` | **MATCH** |")
    a("| Frozen rank of Stand 401 | **5 / 367** |")
    a("| Frozen Top 5 | **868 / 624 / 648 / 545 / 401** |")
    a("| Ranking / scoring files modified this task | **No** |")
    a("| Scoring v2 weights | pool_presence 0.14, shape_v2 0.36, spatial_v2 0.22, aerial 0.12, exterior 0.06, gis 0.03, stand_size 0.07 |")
    a("| Ground truth applied to ranking | false |")
    a("| Colour used | false |")
    a("")
    a("Post-freeze GT recovery lives in `FORENSIC.md` / `forensic.json` (commit `556f422`) and does not rewrite the freeze.")
    a("")
    a("## B. Frozen Top-5 table")
    a("")
    a(
        _md_table(
            ["rank", "stand", "street", "township", "GIS m²", "score", "shape_v2", "spatial_v2", "aerial", "exterior", "stand_size", "inv", "POV", "corner"],
            [
                [
                    p["frozen_rank"],
                    p["stand_number"] + (" **GT**" if p["is_ground_truth"] else ""),
                    p.get("street_address") or "",
                    p.get("township"),
                    p.get("area_sqm"),
                    p.get("score"),
                    p.get("shape_v2"),
                    p.get("spatial_v2"),
                    p.get("aerial_similarity"),
                    p.get("exterior_similarity"),
                    p.get("size_score"),
                    p.get("inventory_pool_status"),
                    p.get("candidate_pov_status"),
                    p.get("parcel_corner"),
                ]
                for p in profiles
            ],
        )
    )
    a("")
    a("Score band #1–#5: **0.7265–0.7152 (Δ 0.0113)**. Discrimination is almost entirely `shape_v2`.")
    a("")
    a("## C. Stand 401 evidence profile")
    a("")
    a("401 entered the 367 as inventory YES / POV CONFIRMED / Corner Gate retained (parcel NO, listing CORNER=UNKNOWN). Frozen score **0.7152**, rank **5**.")
    a("")
    a("| Component | Weight | Raw | Contrib | Freeze-time evidence | Class |")
    a("| --- | ---: | ---: | ---: | --- | --- |")
    a("| pool_presence | 0.14 | 1.0 | 0.14 | Inventory YES, OS CONFIRMED 22.54 m², CLIP pool 0.98 | strong positive signal |")
    a(f"| shape_v2 | 0.36 | 0.7712 | 0.2776 | Elongated in-parcel pool vs listing 043; parts below | useful supporting signal |")
    a("| spatial_v2 | 0.22 | null | 0.11 (pad) | Hybrid omitted pool–house (`not_viewpoint_compatible`). Candidate-only: N / −90.4° / 12.69 m / nearest_edge 0.0302 | missing |")
    a("| aerial | 0.12 | null | 0.06 (pad) | No listing aerial | missing |")
    a("| exterior | 0.06 | 0.7724 | 0.0463 | CLIP vs 12 exterior frames | useful supporting signal |")
    a("| gis | 0.03 | 0.5 | 0.015 | Constant | neutral |")
    a("| stand_size | 0.07 | 0.9455 | 0.0662 | GIS 919 vs advertised 897 | useful supporting signal |")
    a("")
    a("### Pool / house / driveway / parcel (freeze-time OS + GIS)")
    a("")
    a("- Pool: OS CONFIRMED, 22.54 m², aspect 2.766, irregular/elongated, north of house, in-parcel (correct object).")
    a("- POV: CONFIRMED (scoring-eligible). Viewpoint-gate: listing official pick is oblique `pool_overview` 043; candidate POV overlay did not change 401's CONFIRMED status.")
    a("- Building: CONFIRMED 429.66 m² dark multi-plane roof (compatible with listing floor 672 m² / two-storey copy).")
    a("- Driveway: PROBABLE, OS side `south` (image +y south); street is Buffalo Thorn to the east — candidate driveway sits on the street-front / SE of the house.")
    a("- Parcel: internal, one road (Buffalo Thorn), corner NO 0.88 `single_road_frontage_not_corner`.")
    a("- House–pool: adjacent north side-yard, axis_rel 0.8916 (nearly parallel). **Not scored** because listing spatial was omitted.")
    a("")
    a("### Listing fingerprint 043")
    a("")
    a("- Official Hybrid pick: YOLOE/SAM2, POV CONFIRMED 0.64, aspect 3.752 / descriptor elongation **2.4825**, solidity 0.9175, 1 major indent, shape_class **irregular**.")
    a("- Distinctive Contour v2: **PARTIALLY LOST** (`spa_or_secondary_not_in_dominant_contour`). **Not used in ranking.**")
    a("- Pool-to-house vector: omitted. Aerial: none. Colour: unused.")
    a("")
    a("shape_v2 parts vs listing 043 (recomputed from freeze-time contours; total 0.7712):")
    a("")
    parts = gt["shape_parts"]
    a("| elongation | chamfer | hu | solidity | n_indents | max_indent | n_corners | circularity | sharp_frac | radial_cv |")
    a("| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    a(
        "| "
        + " | ".join(
            str(parts.get(k))
            for k in (
                "elongation",
                "chamfer",
                "hu",
                "solidity",
                "n_indents",
                "max_indent",
                "n_corners",
                "circularity",
                "sharp_frac",
                "radial_cv",
            )
        )
        + " |"
    )
    a("")
    a("401 actually **wins chamfer (0.7435)** and elongation (0.957) vs 868. 868 wins because listing `n_indents=1` matches 868 perfectly (`n_indents` part 1.0 vs 401 0.5) and because 401's OS pool is itself `shape=irregular` with poor solidity match (0.668). The true AGS lap pool is elongated; OS over-irregularised 401 while 868 really is irregular.")
    a("")
    a("**Why Top 5 succeeded:** primarily (1) pool geometry close enough on an elongated+indented listing fingerprint, (2) pool presence / POV CONFIRMED keeping 401 inside the 367, and (6) GIS stand-size (removing it drops 401 to rank **11**). Not roof layout, not driveway, not aerial, not scored pool-house spatial.")
    a("")
    a("Primary Top-5 driver class: **pool geometry (useful but not unique) + stand-size supporting + shared 0.5 pads**. Not an accidental combination of only weak signals, and not a strong unique ID.")
    a("")
    a("## D. False-positive analysis for Rank 1–4")
    a("")
    for item in fp_causes:
        p = by_stand[item["stand"]]
        a(f"### Rank {item['rank']} — Stand {item['stand']} ({p.get('street_address')})")
        a("")
        a(item["prefer_401_because"])
        a("")
        a(f"- Classes: {', '.join(item['classes'])}")
        a(f"- **A vs B:** {item['ab']}")
        a("")
        os_p = p["os"]["pool"]
        os_b = p["os"]["building"]
        sp = p["spatial_record"]
        a(
            f"- Pool: {os_p['status']} {os_p['area_m2']} m² aspect {os_p['aspect_ratio']} shape={os_p['shape']} "
            f"CLIP pool={os_p['clip'].get('pool')}"
        )
        a(
            f"- Building: {os_b['status']} {os_b['area_m2']} m²  | driveway: {p['os']['driveway']['status']} "
            f"side={p['os']['driveway']['side']}"
        )
        a(
            f"- Pool–house: {sp.get('direction')} {sp.get('angle_deg')}°  {sp.get('distance_m')} m  "
            f"nearest_edge={sp.get('nearest_edge_norm')} area_ratio={p.get('pool_building_area_ratio')}"
        )
        a(
            f"- Corner: {p['parcel_corner']} ({(p.get('corner_record') or {}).get('reason')}, "
            f"roads={(p.get('corner_record') or {}).get('roads')})"
        )
        a("")
        a("shape_v2 parts:")
        a("")
        pp = p["shape_parts"]
        a("| elongation | chamfer | hu | solidity | n_indents | max_indent | n_corners | circularity | sharp_frac | radial_cv |")
        a("| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
        a(
            "| "
            + " | ".join(
                str(pp.get(k))
                for k in (
                    "elongation",
                    "chamfer",
                    "hu",
                    "solidity",
                    "n_indents",
                    "max_indent",
                    "n_corners",
                    "circularity",
                    "sharp_frac",
                    "radial_cv",
                )
            )
            + " |"
        )
        a("")

    a("## E. Component-level score comparison")
    a("")
    a(
        _md_table(
            ["component", "w", "868", "624", "648", "545", "401 GT"],
            [
                ["total", "1.00", *[by_stand[s]["score"] for s in TOP5]],
                ["shape_v2 raw", "0.36", *[by_stand[s]["shape_v2"] for s in TOP5]],
                ["shape_v2 contrib", "", *[by_stand[s]["contrib"]["shape_v2"] for s in TOP5]],
                ["pool_presence contrib", "0.14", *[by_stand[s]["contrib"]["pool_presence"] for s in TOP5]],
                ["spatial_v2 contrib (pad)", "0.22", *[by_stand[s]["contrib"]["spatial_v2"] for s in TOP5]],
                ["aerial contrib (pad)", "0.12", *[by_stand[s]["contrib"]["aerial"] for s in TOP5]],
                ["exterior raw CLIP", "0.06", *[by_stand[s]["exterior_similarity"] for s in TOP5]],
                ["exterior contrib", "", *[by_stand[s]["contrib"]["exterior"] for s in TOP5]],
                ["gis contrib", "0.03", *[by_stand[s]["contrib"]["gis"] for s in TOP5]],
                ["stand_size raw", "0.07", *[by_stand[s]["size_score"] for s in TOP5]],
                ["stand_size contrib", "", *[by_stand[s]["contrib"]["stand_size"] for s in TOP5]],
                ["OS pool m²", "", *[by_stand[s]["os"]["pool"]["area_m2"] for s in TOP5]],
                ["OS pool aspect", "", *[by_stand[s]["os"]["pool"]["aspect_ratio"] for s in TOP5]],
                ["OS building m²", "", *[by_stand[s]["os"]["building"]["area_m2"] for s in TOP5]],
                ["pool–house m", "", *[by_stand[s]["spatial_record"].get("distance_m") for s in TOP5]],
                ["nearest_edge_norm", "", *[by_stand[s]["spatial_record"].get("nearest_edge_norm") for s in TOP5]],
                ["pool/building area", "", *[by_stand[s].get("pool_building_area_ratio") for s in TOP5]],
                ["driveway status", "", *[by_stand[s]["os"]["driveway"]["status"] for s in TOP5]],
                ["parcel corner", "", *[by_stand[s]["parcel_corner"] for s in TOP5]],
            ],
        )
    )
    a("")
    a("Identical on all five: pool_presence 0.14, spatial pad 0.11, aerial pad 0.06, gis 0.015. Remaining movement is shape_v2 + small exterior/size deltas.")
    a("")
    a("## F. Counterfactual results")
    a("")
    a("Diagnostic rescoring of frozen `all_candidates.json` only. Official freeze ranks are not replaced. `401 frozen rank → diagnostic rank`.")
    a("")
    a("| id | 401 frozen → diagnostic | Top-5 | 338 (rank 122) | 641 (unranked) |")
    a("| --- | --- | --- | --- | --- |")
    for cf in counterfactuals:
        lab338 = next((x for x in cf["labeled_cases"] if "338" in x["case"]), {})
        lab641 = next((x for x in cf["labeled_cases"] if "641" in x["case"]), {})
        s338 = lab338.get("diagnostic_rank")
        if s338 is None:
            s338 = lab338.get("note", "n/a")
            if isinstance(s338, str) and len(s338) > 40:
                s338 = "n/a (no high-conf pool)"
        else:
            flag = "improves" if lab338.get("improves") else ("damages" if lab338.get("damages") else "same")
            s338 = f"{lab338['frozen_rank']} → {s338} ({flag})"
        a(
            f"| `{cf['id']}` | 5 → {cf['401_diagnostic_rank']} | "
            f"{' / '.join(cf['diagnostic_top5'])} | {s338} | never ranked |"
        )
    a("")
    a("Notes:")
    a("")
    a("- `reproduce_frozen` matches rank 5 / score 0.7152: stored components reconstruct the freeze.")
    a("- **Remove CLIP:** 401 stays 5; 545 leaves the Top 5 (CLIP was the term that preferred 545). 338 122→121 (tiny).")
    a("- **Remove stand_size: DAMAGES 401 5→11 and 338 122→182.** Stand-size is a useful supporting signal, not noise.")
    a("- **Omit 0.5-pad (correct UNKNOWN treatment): 401 stays 5; 338 122→8.** Largest labelled-case gain. Same Top 5 here because every YES-pool survivor has the same missing spatial/aerial.")
    a("- **Missing-as-zero: DAMAGES 338 122→124.** Omit-and-renormalise is not the same as filling 0.")
    a("- Stronger CONFIRMED-pool requirement does not separate this Top 5 (all five CONFIRMED).")
    a("- Listing-visual lap-pool upper bound (>55 m²) demotes 624 only; 401 5→4; **868 remains #1**.")
    a("- Building-vs-floor and pool-house adjacency each demote 648; 401 5→4; **868 remains #1**.")
    a("- Driveway context demotes 545 (OS UNKNOWN); 401 5→4; **868 remains #1**.")
    a("- **Convex-hull 'corrected listing contour' DAMAGES 401 5→39.** Do not ship this. 401's OS pool is itself irregular; hulling the listing fingerprint removes the indent that 401 partially shares.")
    a("- Stand 641 cannot move under scoring CFs (removed at Pool Gate).")
    a("")
    a("Do **not** adopt a CF merely because it moves 401. The only CF that both (a) repairs a previous labelled miss and (b) does not scramble this Top-5 hit is **omit-null missing-data treatment**.")
    a("")
    a("## G. Root-cause findings")
    a("")
    a("1. **401's Top-5 placement is real.** Inventory YES, correct in-parcel pool, POV CONFIRMED, elongated geometry, and near-897 GIS size put it in a 0.011-wide Top-5 band of 367 survivors. Removing stand_size drops it to rank 11, so this is not padding luck alone.")
    a("2. **401 is not #1 because `shape_v2` (weight 0.36) is the only live discriminator.** 868's irregular 24.7 m² pool matches listing `n_indents=1` (part 1.0 vs 401 0.5) and solidity (0.854 vs 401 0.668). 401 actually wins chamfer and elongation. The official 043 contour is PARTIALLY LOST / irregular, and 401's OS contour is also irregular — a double geometry error, not a missed house.")
    a("3. **Missing spatial_v2 and aerial did not uniquely suppress 401.** Every ranked survivor received the same 0.5 pads. Flattening is real; singling out 401 is not. Omitting those pads does not change this Top 5.")
    a("4. **False positives are mixed A/B.** 624 is correct elongated-pool + size evidence plus a missing scale penalty. 868 is listing-indent / OS-irregularity (B) with some genuine elongated-pool similarity (A). 648 is unused far pool-house geometry and an undersized 138 m² building. 545 is same-street CLIP preferring a white-roof corner house.")
    a("5. **No existing Scoring v2 term would have promoted 401 to #1 without new information.** Exterior CLIP prefers 545. Stand size prefers 624. Corner is a gate and listing CORNER=UNKNOWN. Naive listing-contour hull **hurts** 401 (5→39). Colour is unused.")
    a("6. **868 remaining #1 after every justified one-component CF is the honest result.** Rank 1 among many elongated YES-pool parcels, with listing spatial/aerial absent, is the MODERATE-separation operating point. The generalisable bugs are missing-data padding (338) and unused non-shape evidence (648/624), not '401 should have been #1 with a weight tweak'.")
    a("")
    a("## H. Maximum 3 recommended improvements")
    a("")
    a("Prefer fixing **bad evidence / missing-data policy before weights**. None of these is selected just because it lifts 401 — two of them only move 401 5→4, and the strongest labelled-case win **does not move 401 at all**.")
    a("")
    a("### 1. Omit null Scoring v2 components instead of 0.5-padding them")
    a("")
    a("- **Failure mode:** REJECTED/UNKNOWN pools still receive 0.5 × shape (0.18) and 0.5 × pool_presence (0.07). Confirmed-pool false positives then beat a true stand that has aerial+size but no accepted contour.")
    a("- **This test:** 401 frozen 5 → diagnostic 5 (Top 5 unchanged). Shared pads are identical on YES-pool survivors, so omitting them does not manufacture a 401 win.")
    a("- **Earlier blinds:** **Yes — this is the PR #25 / stand 338 mechanism.** 338 frozen rank 122 → diagnostic **8** under omit-null. Filling missing as 0 instead of omitting **damages** 338 (122→124). 641 still cannot score (inventory NO); that gate issue is PR #29, already in this freeze.")
    a("- **Expected benefit:** large for canopy-hidden / REJECTED-pool true stands that still have CLIP+size. Neutral for this YES-pool Top-5 hit.")
    a("- **Regression:** when listing spatial is omitted, remaining YES-pool races become even more shape-dominated (this test: Top 5 unchanged, still 868 #1). Do not combine with dropping stand_size.")
    a("- **Complexity:** low. **Layer:** scoring missing-data policy (`score_v2` `missing='omit'`), not weight retune, not candidate generation.")
    a("")
    a("### 2. One-sided listing-visual pool-scale check (not water colour, not a 401-fitted m²)")
    a("")
    a("- **Failure mode:** `shape_v2` is scale-invariant, so an 81 m² pool matches a listing lap pool.")
    a("- **This test:** 624 OS pool 80.66 m² / area_ratio 0.22 vs listing photos of a narrow side-yard lap pool. CF demotes 624; 401 5→4; 868 stays #1.")
    a("- **Earlier blinds:** large-pool FPs appear whenever shape dominates and listing nadir area is omitted (`relative_area_omitted_not_nadir` on this listing).")
    a("- **Expected benefit:** demote oversized backyard pools without GT or colour.")
    a("- **Regression:** genuine large listing pools. Use an upper bound from listing frames (elongated house-adjacent lap), not a target fitted to 22.54 m².")
    a("- **Complexity:** low–moderate. **Layer:** validation / optional scoring term. Do not retune the 0.36 shape weight to hide this.")
    a("")
    a("### 3. Use candidate building footprint vs listing floor, or listing-photo pool-house adjacency — not a convex-hulled fingerprint")
    a("")
    a("- **Failure mode:** Scoring v2 has no building term and listing spatial was omitted, so 648 (OS building 138 m² vs floor 672; pool 20.77 m / nearest_edge 0.462) outranks 401 on shape alone.")
    a("- **This test:** either CF demotes 648; 401 5→4; 868 stays #1.")
    a("- **Earlier blinds:** OS undersized buildings are a known inventory diagnostic (`undersized_building` / `MIN_BUILDING_AREA_M2_FOR_NO=180`). Pool-house spatial omitted on oblique fingerprints is the Hybrid v1 viewpoint rule that flattened every complete-estate freeze.")
    a("- **Expected benefit:** catch segmentation-too-small houses and far-yard pools when listing photos show a large house and a house-adjacent lap pool.")
    a("- **Regression:** single-storey vs two-storey floor/footprint; do not infer listing spatial from GT 401's OS vector. Convex-hull 'fix' of 043 is **rejected** (401 5→39).")
    a("- **Complexity:** moderate. **Layer:** validation / optional spatial fill from listing ground-level frames 044/046, not GT, not colour, not weight bump.")
    a("")
    a("Not recommended: retuning Scoring v2 weights; adding water colour; using Stand 401 as candidate-generation or fingerprint input; promoting CLIP (preferred 545); removing stand_size; convex-hulling the official contour.")
    a("")
    a("## I. GO / NO-GO for another blind test")
    a("")
    a("**GO for another freeze-only blind on the current stack. NO-GO for a scoring-changed or 401-targeted blind.**")
    a("")
    a("Reasons:")
    a("")
    a("- This is the first independently recovered **Top-5 hit**. That is a positive MODERATE-separation result, not a reason to retune on one GT.")
    a("- Rank 1–4 errors are **not** all 'genuinely similar houses', but they are also **not** all fixable by a weight change. 868 remains #1 after every justified one-component CF. Treating 868 as a bug to squash on this GT would overfit the listing indent.")
    a("- The one CF that strongly helps a previous labelled miss (338 122→8) **does not change this freeze Top 5**. It can be prototyped on a **separate freeze-only** listing after this next blind, not merged into production now.")
    a("- Inventory v1.1.0 / POV / Corner Gate / Scoring v2 weights should stay frozen as they were at `5aa42ec`.")
    a("")
    a("If the next listing again has only an oblique pool_overview fingerprint and no aerial, expect another shape-dominated Top 5, not a guaranteed Rank 1.")
    a("")

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    freeze = verify_freeze()
    bundle = build_profiles(freeze)
    counterfactuals = run_counterfactuals(freeze, bundle)
    panel_rel = write_panel(freeze, bundle)
    write_report(freeze, bundle, counterfactuals, panel_rel)
    print(f"freeze_sha256={LOCK_SHA}")
    print(f"401_frozen_rank=5 top5={TOP5}")
    print(f"wrote {OUT_JSON.relative_to(ROOT)}")
    print(f"wrote {OUT_MD.relative_to(ROOT)}")
    print(f"wrote {panel_rel}")
    for cf in counterfactuals:
        print(f"  {cf['id']}: 5 → {cf['401_diagnostic_rank']} top5={cf['diagnostic_top5']}")


if __name__ == "__main__":
    main()
