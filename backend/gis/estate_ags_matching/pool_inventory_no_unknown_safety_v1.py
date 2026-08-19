"""Pool inventory NO/UNKNOWN safety overlay (v1.1.0).

Versioned experimental change. Does not rewrite frozen inventory 001/002,
PR #28 freeze/hash, Scoring v2, Hybrid, FastSAM, Corner Gate, POV, or colour.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

from backend.gis.carlswald_north_complete import COMPLETE_002_PATH
from backend.gis.dataset_registry import COMPLETE_CARLSWALD_NORTH
from backend.gis.estate_ags_matching.complete_estate_inventory import COMPLETE_OS_DIR
from backend.gis.estate_ags_matching.estate_property_inventory_v1 import (
    ALGORITHM_VERSION,
    INVENTORY_REVISION,
    SCHEMA_VERSION,
    classify_pool_from_os,
    os_json_path_for,
    parcel_bbox,
    pass1_parcels,
    safe_stand,
    status_counts,
)
from backend.gis.estate_ags_matching.listing_corner_gate_v1 import apply_listing_corner_gate
from backend.gis.estate_ags_matching.listing_pool_gate_v1 import apply_listing_pool_gate
from backend.gis.estate_ags_matching.pool_observability_v1 import (
    PoolObservability,
    observability_from_crop,
)
from backend.imagery.estate_tiles import PADDING_METRES

REPO_ROOT = Path(__file__).resolve().parents[3]
FROZEN_INVENTORY_002 = REPO_ROOT / "data" / "estate_inventory" / COMPLETE_CARLSWALD_NORTH / "current.jsonl"
OVERLAY_ESTATE_ID = f"{COMPLETE_CARLSWALD_NORTH}_pool_obs_v1_1_0"
OVERLAY_ROOT = REPO_ROOT / "data" / "estate_inventory" / OVERLAY_ESTATE_ID
INVESTIGATION_DIR = REPO_ROOT / "data" / "investigations" / "pool_inventory_no_unknown_safety_v1"
CROP_DIR = INVESTIGATION_DIR / "ags_crops"
BLIND_DIR = REPO_ROOT / "data" / "investigations" / "blind_117170887_complete_estate"
NATIVE15_M_PER_PX = 0.15


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def load_gis(path: Path | None = None) -> dict[str, Any]:
    return json.loads((path or COMPLETE_002_PATH).read_text(encoding="utf-8"))


def parcels_by_stand(dataset: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item["stand_number"]): item for item in pass1_parcels(dataset)}


def load_os(stand: str, os_dir: Path | None = None) -> dict[str, Any] | None:
    path = os_json_path_for(stand, os_dir or COMPLETE_OS_DIR)
    if not path.is_file():
        frozen = os_json_path_for(
            stand,
            REPO_ROOT / "data" / "investigations" / "object_segmentation_v1" / "carlswald_north" / "json",
        )
        if not frozen.is_file():
            return None
        path = frozen
    return json.loads(path.read_text(encoding="utf-8"))


def needs_observability(os_payload: Mapping[str, Any] | None) -> bool:
    if not os_payload:
        return False
    pool = os_payload.get("pool") or {}
    notes = [str(item) for item in (pool.get("notes") or [])]
    return str(pool.get("status")) == "UNKNOWN" and "no_pool_candidate" in notes


def export_parcel_crop(
    geometry: Mapping[str, Any],
    dest: Path,
    *,
    year: int = 2023,
) -> bool:
    """Live AGS padded parcel crop. Not native15 cache and not OS/FastSAM."""
    bbox = parcel_bbox(geometry)
    if bbox is None:
        return False
    min_lon, min_lat, max_lon, max_lat = bbox
    pad = PADDING_METRES / 111_320
    min_lon -= pad
    max_lon += pad
    min_lat -= pad
    max_lat += pad
    width_m = (max_lon - min_lon) * 111_320.0
    height_m = (max_lat - min_lat) * 111_320.0
    width = max(64, min(1600, int(round(width_m / NATIVE15_M_PER_PX))))
    height = max(64, min(1600, int(round(height_m / NATIVE15_M_PER_PX))))
    from backend.imagery.ags_client import AGSAerialClient, AGSError

    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        AGSAerialClient().export_bbox_to_file(
            dest,
            min_lon=min_lon,
            min_lat=min_lat,
            max_lon=max_lon,
            max_lat=max_lat,
            width=width,
            height=height,
            year=year,
        )
    except (AGSError, OSError, ValueError):
        return False
    return dest.is_file() and dest.stat().st_size > 500


def observability_for_stand(
    stand: str,
    parcel: Mapping[str, Any] | None,
    os_payload: Mapping[str, Any] | None,
    *,
    crop_dir: Path | None = None,
    download: bool = False,
) -> PoolObservability:
    dest = (crop_dir or CROP_DIR) / f"{safe_stand(stand)}_ags_aerial.jpg"
    if download and not dest.is_file() and parcel is not None:
        export_parcel_crop(parcel.get("geometry") or {}, dest)
    return observability_from_crop(
        dest if dest.is_file() else None,
        geometry=None if parcel is None else parcel.get("geometry"),
        os_payload=os_payload,
    )


def overlay_record(
    previous: Mapping[str, Any],
    classification,
    observability: PoolObservability | None = None,
) -> dict[str, Any]:
    record = dict(previous)
    record["schema_version"] = SCHEMA_VERSION
    record["algorithm_version"] = ALGORITHM_VERSION
    record["inventory_revision"] = INVENTORY_REVISION
    record["parent_algorithm_version"] = previous.get("algorithm_version")
    record["pool_status"] = classification.pool_status
    record["pool_confidence"] = classification.pool_confidence
    record["pool_count"] = classification.pool_count
    record["unknown_reason"] = classification.unknown_reason
    flags = list(classification.diagnostic_flags)
    for extra in previous.get("diagnostic_flags") or []:
        if extra in {"reused_from_frozen_001", "reused_os_v1_json"} and extra not in flags:
            flags.append(extra)
    record["diagnostic_flags"] = sorted(set(flags))
    if observability is not None:
        record["pool_observability"] = observability.to_dict()
    record["overlay"] = "pool_inventory_no_unknown_safety_v1"
    return record


def build_overlay_inventory(
    *,
    previous_path: Path | None = None,
    dataset: Mapping[str, Any] | None = None,
    os_dir: Path | None = None,
    crop_dir: Path | None = None,
    download_crops: bool = False,
) -> list[dict[str, Any]]:
    previous = load_jsonl(previous_path or FROZEN_INVENTORY_002)
    gis = dataset or load_gis()
    by_stand = parcels_by_stand(gis)
    dest_crops = crop_dir or CROP_DIR
    dest_crops.mkdir(parents=True, exist_ok=True)
    overlay: list[dict[str, Any]] = []
    for row in previous:
        stand = str(row.get("stand_number") or "")
        os_payload = load_os(stand, os_dir)
        obs = None
        if needs_observability(os_payload):
            obs = observability_for_stand(
                stand,
                by_stand.get(stand),
                os_payload,
                crop_dir=dest_crops,
                download=download_crops,
            )
        classification = classify_pool_from_os(os_payload, observability=obs)
        overlay.append(overlay_record(row, classification, obs))
    return overlay


def write_overlay(
    records: Sequence[Mapping[str, Any]],
    *,
    dest_dir: Path | None = None,
) -> Path:
    root = dest_dir or OVERLAY_ROOT
    root.mkdir(parents=True, exist_ok=True)
    path = root / "current.jsonl"
    lines = [json.dumps(dict(row), sort_keys=True, separators=(",", ":")) for row in records]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    counts = status_counts(records)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "algorithm_version": ALGORITHM_VERSION,
        "inventory_revision": INVENTORY_REVISION,
        "parent_inventory": str(FROZEN_INVENTORY_002.relative_to(REPO_ROOT)),
        "frozen_inventories_modified": False,
        "counts": counts,
        "parcel_count": len(records),
    }
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def clip_sims_from_freeze(all_candidates_path: Path | None = None) -> dict[str, dict[str, float | None]]:
    path = all_candidates_path or (BLIND_DIR / "all_candidates.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    sims: dict[str, dict[str, float | None]] = {}
    for row in payload.get("rows") or []:
        stand = str(row.get("stand_number") or "")
        if not stand:
            continue
        sims[stand] = {
            "aerial": row.get("aerial_similarity"),
            "exterior": row.get("exterior_similarity"),
        }
    return sims


def run_listing_from_corrected_gate(
    records: Sequence[Mapping[str, Any]],
    *,
    freeze_path: Path | None = None,
    hybrid_path: Path | None = None,
) -> dict[str, Any]:
    """Re-apply Pool Gate → Corner Gate → Scoring v2. Does not rewrite freeze.json."""
    from backend.gis.estate_ags_matching.blind_116273255_complete_estate import (
        load_gis_002,
        load_parcel_corner_records,
        overlay_os_payload_with_pov,
        rank_survivors,
        top_n,
    )
    from backend.gis.estate_ags_matching.hybrid_geometry_ranking_test import listing_evidence_from_hybrid_block
    from backend.gis.estate_ags_matching.os_scoring_v2 import V2_WEIGHTS_NO_BUILDING

    freeze = json.loads((freeze_path or (BLIND_DIR / "freeze.json")).read_text(encoding="utf-8"))
    hybrid = json.loads((hybrid_path or (BLIND_DIR / "hybrid_block.json")).read_text(encoding="utf-8"))
    evidence = listing_evidence_from_hybrid_block(hybrid)
    dataset = load_gis_002()
    parcels = pass1_parcels(dataset)
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
    listing_pool = (freeze.get("listing_pool_gate") or {}).get("listing_pool_status") or "YES"
    pool_gate = apply_listing_pool_gate(candidates, records, listing_pool)
    listing_corner = freeze.get("listing_corner") or {}
    corner_gate = apply_listing_corner_gate(
        pool_gate.survivors,
        load_parcel_corner_records(),
        listing_corner.get("listing_corner"),
        listing_confidence=float(listing_corner.get("confidence") or 0.0),
        listing_high_confidence=listing_corner.get("high_confidence"),
        listing_exceptional_non_corner=listing_corner.get("exceptional_non_corner"),
        positive_non_corner_evidence=bool(listing_corner.get("positive_non_corner_evidence")),
        listing_evidence=listing_corner,
    )
    gis_geometry = {str(parcel["stand_number"]): parcel.get("geometry") for parcel in parcels}
    clip_sims = clip_sims_from_freeze()
    rows = rank_survivors(
        corner_gate.survivors,
        evidence["fingerprint"],
        evidence["listing_shape"],
        listing_erf_sqm=(freeze.get("acquisition") or {}).get("erf_size_sqm"),
        clip_sims=clip_sims,
        apply_candidate_pov=True,
        gis_geometry_by_stand=gis_geometry,
    )
    row_641 = next((row for row in rows if str(row.get("stand_number")) == "641"), None)
    pool_641 = next((row for row in pool_gate.survivors if str(row.get("stand_number")) == "641"), None)
    corner_641 = next((row for row in corner_gate.survivors if str(row.get("stand_number")) == "641"), None)
    removed_corner_641 = next((row for row in corner_gate.removed if str(row.get("stand_number")) == "641"), None)
    before = status_counts(load_jsonl(FROZEN_INVENTORY_002))
    after = status_counts(records)
    ranking_eligible = row_641 is not None
    unranked_reason = None
    if pool_641 is None:
        unranked_reason = "removed_by_pool_gate"
    elif corner_641 is None:
        unranked_reason = "removed_by_corner_gate:" + str(
            (removed_corner_641 or {}).get("parcel_corner") or "NO"
        )
    elif not ranking_eligible:
        unranked_reason = "survived_gates_but_not_scored"
    elif not row_641.get("os_high_conf_pool"):
        # Still ranked, but record the contour bottleneck for the report.
        pass
    slim = top_n(rows, 20)
    rank_641 = None if row_641 is None else row_641.get("hybrid_v2_rank")
    return {
        "experiment": "pool_inventory_no_unknown_safety_v1",
        "listing_id": "117170887",
        "true_stand": "641",
        "freeze_modified": False,
        "scoring_v2_weights": dict(V2_WEIGHTS_NO_BUILDING),
        "official_fingerprint": "117170887-077",
        "A_parcels_before_pool_gate": pool_gate.starting_count,
        "B_inventory_counts": {
            "before": before,
            "after": after,
        },
        "C_pool_gate_survivor_count": pool_gate.total_survivors,
        "D_stand_641_survives_pool_gate": pool_641 is not None,
        "E_corner_gate_641": {
            "survives": corner_641 is not None,
            "parcel_corner": None
            if corner_641 is None and removed_corner_641 is None
            else (corner_641 or removed_corner_641 or {}).get("parcel_corner"),
            "reason": None
            if corner_641 is None
            else (
                corner_641.get("corner_gate_unresolved")
                or corner_641.get("parcel_corner_reason")
            ),
            "pool_gate_inventory_status": None if pool_641 is None else pool_641.get("inventory_pool_status"),
        },
        "F_scoring_eligible": ranking_eligible,
        "G_rank": rank_641,
        "H_unranked_reason": unranked_reason,
        "stand_641_score_row": None
        if row_641 is None
        else {
            "rank": row_641.get("hybrid_v2_rank"),
            "score": row_641.get("hybrid_v2"),
            "inventory_pool_status": row_641.get("inventory_pool_status"),
            "os_pool_status": row_641.get("os_pool_status"),
            "os_high_conf_pool": row_641.get("os_high_conf_pool"),
            "shape_v2": row_641.get("hybrid_v2_shape_v2"),
            "spatial_v2": row_641.get("hybrid_v2_spatial_v2"),
            "candidate_pov_status": row_641.get("candidate_pov_status"),
            "parcel_corner": row_641.get("parcel_corner"),
            "contrib": row_641.get("hybrid_v2_contrib"),
            "neutral_components": [
                name
                for name, ok in (
                    ("shape_v2_null_no_candidate_contour", row_641.get("hybrid_v2_shape_v2") is None),
                    ("pool_presence_neutral_no_high_conf_os_pool", not row_641.get("os_high_conf_pool")),
                    ("spatial_v2_null", row_641.get("hybrid_v2_spatial_v2") is None),
                )
                if ok
            ],
        },
        "pool_gate": {
            "listing_pool_status": listing_pool,
            "starting_count": pool_gate.starting_count,
            "yes_survivors": pool_gate.yes_survivors,
            "no_survivors": pool_gate.no_survivors,
            "unknown_survivors": pool_gate.unknown_survivors,
            "removed_confident_no": pool_gate.removed_confident_no,
            "total_survivors": pool_gate.total_survivors,
        },
        "corner_gate": {
            "listing_corner": listing_corner.get("listing_corner"),
            "starting_count": corner_gate.starting_count,
            "total_survivors": corner_gate.total_survivors,
            "removed_confident_no": corner_gate.removed_confident_no,
            "unknown_survivors": corner_gate.unknown_survivors,
        },
        "top20": slim,
        "n_ranked": len(rows),
        "next_bottleneck": _next_bottleneck(pool_641 is not None, ranking_eligible, row_641),
        "pass": bool(pool_641 is not None and (None if pool_641 is None else pool_641.get("inventory_pool_status")) == "UNKNOWN"),
    }


def _next_bottleneck(survived_pool: bool, scoring_eligible: bool, row_641: Mapping[str, Any] | None) -> str:
    if not survived_pool:
        return "POOL_GATE_STILL_REMOVES_641"
    if not scoring_eligible:
        return "CORNER_GATE_OR_SCORING_ELIGIBILITY"
    if row_641 is None:
        return "MISSING_SCORE_ROW"
    if not row_641.get("os_high_conf_pool") or row_641.get("hybrid_v2_shape_v2") is None:
        return "ESTATE_POOL_EXTRACTION_MISSING_CONTOUR"
    return "SCORING_V2_RANK_AFTER_GEOMETRY_PRESENT"


def write_report(result: Mapping[str, Any], dest: Path | None = None) -> Path:
    path = dest or (INVESTIGATION_DIR / "REPORT.md")
    path.parent.mkdir(parents=True, exist_ok=True)
    b = result.get("B_inventory_counts") or {}
    before = b.get("before") or {}
    after = b.get("after") or {}
    e = result.get("E_corner_gate_641") or {}
    row = result.get("stand_641_score_row") or {}
    verdict = "PASS" if result.get("pass") else "FAIL"
    lines = [
        "# Pool inventory NO/UNKNOWN safety — listing 117170887",
        "",
        "Versioned overlay `estate_property_inventory_v1.1.1.0`. Frozen PR #28 ranking and SHA256 are untouched.",
        "",
        f"**POOL GATE SAFETY FIX: {verdict}**",
        "",
        "## Counts",
        "",
        f"- **A.** parcels before Pool Gate: **{result.get('A_parcels_before_pool_gate')}**",
        f"- **B.** inventory before correction: YES={before.get('YES')} NO={before.get('NO')} UNKNOWN={before.get('UNKNOWN')}",
        f"- **B.** inventory after correction: YES={after.get('YES')} NO={after.get('NO')} UNKNOWN={after.get('UNKNOWN')}",
        f"- **C.** Pool Gate survivors: **{result.get('C_pool_gate_survivor_count')}**",
        f"- **D.** Stand 641 survives Pool Gate: **{result.get('D_stand_641_survives_pool_gate')}** (inventory `{e.get('pool_gate_inventory_status')}`)",
        f"- **E.** Corner Gate 641: survives={e.get('survives')} parcel_corner=`{e.get('parcel_corner')}` reason=`{e.get('reason')}`",
        f"- **F.** scoring eligible: **{result.get('F_scoring_eligible')}**",
        f"- **G.** rank: **{result.get('G_rank')}** of {result.get('n_ranked')} scored Corner Gate survivors",
        f"- **H.** unranked reason: `{result.get('H_unranked_reason') or 'ranked — not unranked'}`",
        "",
        "## Stand 641 score (if eligible)",
        "",
        f"- score=`{row.get('score')}` shape_v2=`{row.get('shape_v2')}` spatial_v2=`{row.get('spatial_v2')}` OS=`{row.get('os_pool_status')}` POV=`{row.get('candidate_pov_status')}`",
        f"- high-conf OS pool: `{row.get('os_high_conf_pool')}`",
        f"- neutral/missing: `{row.get('neutral_components')}`",
        "",
        "## Next bottleneck",
        "",
        f"**{result.get('next_bottleneck')}**",
        "",
        "This run does not solve the missing-contour / canopy-hidden pool on Stand 641.",
        "",
        "## Constraints honoured",
        "",
        "- Scoring v2 weights unchanged",
        "- listing fingerprint 117170887-077 unchanged",
        "- Hybrid / FastSAM adapter / Corner Gate / POV / colour rules unmodified",
        "- PR #28 `freeze.json` / `freeze.sha256` / frozen Top 5 untouched",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
