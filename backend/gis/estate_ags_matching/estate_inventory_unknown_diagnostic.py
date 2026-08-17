"""Estate Property Inventory v1 UNKNOWN diagnostic — read-only.

Does not modify inventory current.jsonl, OS v1, FastSAM, Scoring v2,
Hybrid Pool Geometry, native15, ranking, or the listing pool gate.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

from backend.gis.estate_ags_matching.estate_property_inventory_v1 import (
    DEFAULT_INVENTORY_ROOT,
    DEFAULT_OS_DIR,
    pass1_parcels,
    safe_stand,
)
from backend.gis.estate_ags_matching.listing_pool_gate_v1 import apply_listing_pool_gate
from backend.gis.dataset_registry import CORRECT_CARLSWALD_NORTH

REPO_ROOT = Path(__file__).resolve().parents[3]
GIS_PATH = REPO_ROOT / "data" / "gis" / f"{CORRECT_CARLSWALD_NORTH}.json"
OS_DIR = DEFAULT_OS_DIR

CLIP_KEYS = ("pool", "roof", "shadow", "road", "driveway", "lawn")

# Primary UNKNOWN reasons derived from frozen OS v1 evidence.
PRIMARY_REASONS = (
    "os_rejected",
    "pool_candidate_confidence_insufficient",
    "partially_outside_parcel",
    "no_candidate_poor_building",
    "other",
)

REPORT_REASON = {
    "os_rejected": "os_rejected",
    "pool_candidate_confidence_insufficient": "weak_ambiguous_pool_candidate",
    "partially_outside_parcel": "partially_outside_parcel",
    "no_candidate_poor_building": "good_imagery_no_pool_candidate",
    "other": "other",
}

VISUAL_REVIEW_PATH = (
    REPO_ROOT
    / "data"
    / "investigations"
    / "estate_property_inventory_v1"
    / "unknown_diagnostic"
    / "safe_no_visual_review.json"
)

MIN_CROP_PX_FOR_677_POOL = 200
NO_CREDIBLE_POOL_LABELS = frozenset({"no_in_parcel_pool", "vacant_no_pool", "construction_no_pool"})
CREDIBLE_POOL_LABELS = frozenset({"missed_in_parcel_pool", "dark_possible_in_parcel_pool"})


_VISUAL_REVIEW_CACHE: dict[str, Any] | None = None


def load_safe_no_visual_review(path: Path | None = None) -> dict[str, Any]:
    global _VISUAL_REVIEW_CACHE
    review_path = path or VISUAL_REVIEW_PATH
    if path is None and _VISUAL_REVIEW_CACHE is not None:
        return _VISUAL_REVIEW_CACHE
    if not review_path.is_file():
        payload = {"labels": {}, "notes": {}}
    else:
        payload = json.loads(review_path.read_text(encoding="utf-8"))
    if path is None:
        _VISUAL_REVIEW_CACHE = payload
    return payload


def load_gis(path: Path | None = None) -> dict[str, Any]:
    return json.loads((path or GIS_PATH).read_text(encoding="utf-8"))


def load_inventory_rows(estate_id: str = CORRECT_CARLSWALD_NORTH, root: Path | None = None) -> list[dict[str, Any]]:
    path = (root or DEFAULT_INVENTORY_ROOT) / estate_id / "current.jsonl"
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def load_os(stand_number: str, os_dir: Path | None = None) -> dict[str, Any] | None:
    path = (os_dir or OS_DIR) / f"{safe_stand(stand_number)}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def coverage_report(dataset: Mapping[str, Any], inventory_rows: Sequence[Mapping[str, Any]], os_dir: Path | None = None) -> dict[str, Any]:
    parcels = list(dataset.get("parcels") or [])
    pass1 = pass1_parcels(dataset)
    excluded = []
    for item in parcels:
        reasons = []
        if item.get("land_type") != "Erven":
            reasons.append(f"land_type={item.get('land_type')}")
        if item.get("class") in {"non_residential"}:
            reasons.append("non_residential")
        if (item.get("area_sqm") or 0) >= 8000:
            reasons.append("area_sqm>=8000")
        if not item.get("geometry"):
            reasons.append("missing_geometry")
        if not item.get("stand_number"):
            reasons.append("missing_stand_number")
        if str(item.get("stand_number") or "").startswith("RE/"):
            reasons.append("township_remainder_RE")
        if reasons:
            excluded.append(
                {
                    "stand_number": item.get("stand_number"),
                    "property_id": item.get("property_id"),
                    "township": item.get("township"),
                    "class": item.get("class"),
                    "area_sqm": item.get("area_sqm"),
                    "reasons": reasons,
                }
            )
    os_dir = os_dir or OS_DIR
    os_hits = 0
    for row in pass1:
        if (os_dir / f"{safe_stand(row['stand_number'])}.json").is_file():
            os_hits += 1
    raw_pass1 = []
    for item in parcels:
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
        raw_pass1.append(item)
    by_pid: dict[str, int] = {}
    for item in raw_pass1:
        key = str(item.get("property_id") or item["stand_number"])
        by_pid[key] = by_pid.get(key, 0) + 1
    duplicate_extra = sum(n - 1 for n in by_pid.values() if n > 1)
    requested = [r.get("official_name") or r.get("requested") for r in dataset.get("township_reports") or []]
    return {
        "dataset_id": dataset.get("dataset_id"),
        "source_parcel_count": len(parcels),
        "unique_stand_numbers_source": len({p.get("stand_number") for p in parcels}),
        "unique_property_ids_source": len({p.get("property_id") for p in parcels}),
        "townships_in_dataset": list(dataset.get("townships") or []),
        "requested_townships": requested,
        "excluded_wrong_estate_townships": list(dataset.get("excluded_townships") or []),
        "summerset_ext_2": dataset.get("summerset_ext_2"),
        "search_extent": dataset.get("extent"),
        "gated_community_extent": dataset.get("gated_carlswald_north_estate_extent"),
        "class_counts_source": dict(Counter(p.get("class") for p in parcels)),
        "pass1_rows_before_dedup": len(raw_pass1),
        "unique_erven_after_property_id_dedup": len(pass1),
        "duplicate_gis_rows_removed": duplicate_extra,
        "excluded_from_pass1": len(excluded),
        "excluded_reason_counts": {
            " | ".join(key): val for key, val in Counter(tuple(row["reasons"]) for row in excluded).items()
        },
        "inventory_rows": len(inventory_rows),
        "os_v1_fingerprints_for_pass1": os_hits,
        "native15_fingerprint_coverage": os_hits == len(pass1),
        "why_330": (
            "GIS pass 1 keeps Erven that are not non-residential, not RE/ remainders, "
            "and under 8000 m² (337 rows). Seven duplicate GIS records share a property_id "
            "in SUMMERSET EXT.6, leaving 330 unique erven. OS v1 and the inventory use that "
            "unique set. There are no cross-township stand collisions."
        ),
    }


def _clip(pool: Mapping[str, Any]) -> dict[str, float]:
    raw = pool.get("clip") or {}
    return {key: float(raw.get(key) or 0.0) for key in CLIP_KEYS}


def _rival(clip: Mapping[str, float]) -> tuple[str, float]:
    rival = max((key for key in CLIP_KEYS if key != "pool"), key=lambda key: clip[key])
    return rival, clip[rival]


def diagnose_unknown_os(os_payload: Mapping[str, Any] | None, inventory_row: Mapping[str, Any]) -> dict[str, Any]:
    """Read-only diagnostic labels. Does not change inventory pool_status."""
    flags = list(inventory_row.get("diagnostic_flags") or [])
    pool = {} if os_payload is None else (os_payload.get("pool") or {})
    building = {} if os_payload is None else (os_payload.get("building") or {})
    spatial = {} if os_payload is None else (os_payload.get("spatial") or {})
    notes = [str(item) for item in (pool.get("notes") or [])]
    os_status = pool.get("status")
    geom = pool.get("geometry") or {}
    clip = _clip(pool)
    rival, rival_score = _rival(clip) if any(clip.values()) else ("none", 0.0)
    gap = clip["pool"] - rival_score
    building_area = float((building.get("geometry") or {}).get("area_m2") or 0.0)
    masses = int(spatial.get("n_building_masses") or 0)
    crop_wh = None if os_payload is None else os_payload.get("crop_wh")
    good_imagery = bool(crop_wh and min(crop_wh) >= 200)

    primary = "other"
    rejected_subtype = None
    if "partially_outside_parcel" in notes:
        primary = "partially_outside_parcel"
    elif os_status == "REJECTED":
        primary = "os_rejected"
        if clip["pool"] >= 0.18 and gap >= -0.08:
            rejected_subtype = "low_confidence_genuine_looking"
            primary = "pool_candidate_confidence_insufficient"
        elif rival == "shadow":
            rejected_subtype = "shadow"
        elif rival == "roof":
            rejected_subtype = "roof_object"
        elif rival == "road":
            rejected_subtype = "road_or_neighbour_context"
        elif rival == "lawn":
            rejected_subtype = "vegetation"
        elif rival == "driveway":
            rejected_subtype = "driveway_paving"
        else:
            rejected_subtype = "unclear"
        if "low_pool_evidence" in notes and rejected_subtype not in {
            "low_confidence_genuine_looking"
        }:
            rejected_subtype = f"low_evidence_{rejected_subtype}"
    elif os_status in {"UNKNOWN", None} and "no_pool_candidate" in notes:
        primary = "no_candidate_poor_building"

    extra = []
    if "partially_outside_parcel" in notes:
        extra.append("neighbour_contamination_risk")
        extra.append("neighbour_pool")
    if os_status == "REJECTED" and clip["pool"] < 0.08 and geom.get("present"):
        extra.append("dark_or_low_contrast_risk")
    if not good_imagery:
        extra.append("imagery_quality_or_coverage_issue")
        extra.append("poor_imagery_coverage")
    if masses >= 3:
        extra.append("poor_incomplete_building_mask")
        extra.append("inadequate_building_segmentation")
    if building_area and building_area < 180:
        extra.append("undersized_building_mask")
        extra.append("inadequate_building_segmentation")
    if building.get("status") not in {"CONFIRMED", "PROBABLE"}:
        extra.append("building_status_weak")
        extra.append("inadequate_building_segmentation")
    if rejected_subtype and any(key in str(rejected_subtype) for key in ("shadow", "roof", "vegetation", "driveway")):
        extra.append("shadow_vegetation_object_confusion")
    parcel_present = bool((spatial.get("parcel") or {}).get("present", True))
    if not parcel_present:
        extra.append("inadequate_parcel_mask")

    visual_label = (load_safe_no_visual_review().get("labels") or {}).get(str(inventory_row.get("stand_number")))
    if visual_label:
        extra.append(f"visual_{visual_label}")

    sufficient_for_677 = bool(good_imagery and crop_wh and min(crop_wh) >= MIN_CROP_PX_FOR_677_POOL)
    os_has_candidate = "no_pool_candidate" not in notes
    return {
        "stand_number": inventory_row.get("stand_number"),
        "parcel_id": inventory_row.get("parcel_id"),
        "inventory_pool_status": inventory_row.get("pool_status"),
        "inventory_unknown_reason": inventory_row.get("unknown_reason"),
        "os_pool_status": os_status,
        "os_notes": notes,
        "primary_reason": primary,
        "report_reason": REPORT_REASON.get(primary, primary),
        "rejected_subtype": rejected_subtype,
        "diagnostic_flags": sorted(set(flags + extra)),
        "clip_pool": round(clip["pool"], 4),
        "clip_rival": rival,
        "clip_rival_score": round(rival_score, 4),
        "clip_gap": round(gap, 4),
        "pool_area_m2": geom.get("area_m2"),
        "pool_shape": geom.get("shape"),
        "building_status": building.get("status"),
        "building_area_m2": None if not building_area else round(building_area, 2),
        "n_building_masses": masses,
        "crop_wh": crop_wh,
        "good_full_parcel_imagery": good_imagery,
        "erf_bbox_adequately_visible": good_imagery,
        "imagery_sufficient_for_677_scale_pool": sufficient_for_677,
        "os_credible_in_parcel_candidate": os_has_candidate,
        "roof_segmentation_required_to_see_pool": False,
        "no_in_parcel_pool_candidate": "no_pool_candidate" in notes,
        "unknown_solely_because_building_inadequate": primary == "no_candidate_poor_building",
        "visual_safe_no_label": visual_label,
        "parcel_mask_present": parcel_present,
    }


def analyse_unknowns(
    inventory_rows: Sequence[Mapping[str, Any]],
    os_dir: Path | None = None,
) -> dict[str, Any]:
    unknown = [row for row in inventory_rows if row.get("pool_status") == "UNKNOWN"]
    diagnosed = []
    for row in unknown:
        os_payload = load_os(str(row.get("stand_number")), os_dir)
        diagnosed.append(diagnose_unknown_os(os_payload, row))
    n = max(len(diagnosed), 1)
    primary_counts = Counter(item["primary_reason"] for item in diagnosed)
    subtype_counts = Counter(item["rejected_subtype"] for item in diagnosed if item["rejected_subtype"])
    no_candidate = [item for item in diagnosed if item["no_in_parcel_pool_candidate"]]
    building_only = [item for item in diagnosed if item["unknown_solely_because_building_inadequate"]]
    good_imagery = [item for item in diagnosed if item["good_full_parcel_imagery"]]
    rejected = [item for item in diagnosed if item["os_pool_status"] == "REJECTED"]
    report_counts = Counter(item["report_reason"] for item in diagnosed)
    visual_counts = Counter(
        item.get("visual_safe_no_label") or "not_in_no_candidate_set" for item in building_only
    )
    visual_no_credible = [
        item
        for item in building_only
        if item.get("visual_safe_no_label") in NO_CREDIBLE_POOL_LABELS
    ]
    visual_missed = [
        item for item in building_only if item.get("visual_safe_no_label") in CREDIBLE_POOL_LABELS
    ]
    visual_ambiguous = [
        item
        for item in building_only
        if item.get("visual_safe_no_label") == "occlusion_cannot_certify"
    ]
    return {
        "unknown_n": len(diagnosed),
        "primary_reason_counts": dict(primary_counts),
        "primary_reason_pct": {key: round(100.0 * val / n, 2) for key, val in primary_counts.items()},
        "report_reason_counts": dict(report_counts),
        "report_reason_pct": {key: round(100.0 * val / n, 2) for key, val in report_counts.items()},
        "rejected_subtype_counts": dict(subtype_counts),
        "good_full_parcel_imagery_n": len(good_imagery),
        "imagery_sufficient_for_677_scale_pool_n": sum(
            1 for item in diagnosed if item.get("imagery_sufficient_for_677_scale_pool")
        ),
        "poor_imagery_coverage_n": sum(
            1 for item in diagnosed if "poor_imagery_coverage" in item["diagnostic_flags"]
        ),
        "inadequate_parcel_mask_n": sum(
            1 for item in diagnosed if "inadequate_parcel_mask" in item["diagnostic_flags"]
        ),
        "no_in_parcel_candidate_n": len(no_candidate),
        "unknown_solely_building_inadequate_n": len(building_only),
        "rejected_n": len(rejected),
        "safe_no": {
            "good_full_parcel_imagery_n": len(good_imagery),
            "good_imagery_and_os_zero_candidate_n": len(building_only),
            "visual_no_credible_in_parcel_pool_n": len(visual_no_credible),
            "visual_missed_or_dark_pool_n": len(visual_missed),
            "visual_occlusion_cannot_certify_n": len(visual_ambiguous),
            "visual_label_counts": dict(visual_counts),
            "missed_pool_stands": [item["stand_number"] for item in visual_missed],
            "potential_visual_no_stands": [item["stand_number"] for item in visual_no_credible],
            "occlusion_stands": [item["stand_number"] for item in visual_ambiguous],
            "roof_fail_prevents_seeing_a_pool": False,
            "automated_safe_no_from_the_43": 0,
            "potential_visual_no_not_safe_for_hard_gate": len(visual_no_credible),
        },
        "rows": diagnosed,
    }


def conservative_v11_simulation(inventory_rows: Sequence[Mapping[str, Any]], unknown_analysis: Mapping[str, Any]) -> dict[str, Any]:
    """Hard-filter simulation only. Does not write inventory.

    Conservative v1.1 keeps all current YES, keeps all REJECTED as UNKNOWN,
    and only considers promoting no-candidate / poor-building rows to NO
    as an *upper bound* that still has dark-miss residual risk.
    """
    current = Counter(row.get("pool_status") for row in inventory_rows)
    building_only = unknown_analysis["unknown_solely_building_inadequate_n"]
    # Safe hard-filter v1.1: no extra YES; NO stays 60 unless reviewers accept
    # no-candidate-without-building as absence. Report both bounds.
    safe = {"YES": current["YES"], "NO": current["NO"], "UNKNOWN": current["UNKNOWN"]}
    upper_no = {
        "YES": current["YES"],
        "NO": current["NO"] + building_only,
        "UNKNOWN": current["UNKNOWN"] - building_only,
    }
    visual_no_n = int(unknown_analysis.get("safe_no", {}).get("visual_no_credible_in_parcel_pool_n") or 0)
    visual_stands = set(unknown_analysis.get("safe_no", {}).get("potential_visual_no_stands") or [])
    visual_upper = {
        "YES": current["YES"],
        "NO": current["NO"] + visual_no_n,
        "UNKNOWN": current["UNKNOWN"] - visual_no_n,
    }
    total = max(sum(current.values()), 1)

    def pack(counts: Mapping[str, int], label: str) -> dict[str, Any]:
        classified = counts["YES"] + counts["NO"]
        rows = []
        for row in inventory_rows:
            status = row.get("pool_status")
            if (
                label == "upper_no"
                and status == "UNKNOWN"
                and "no_candidate_with_poor_segmentation" in {row.get("unknown_reason")}
            ):
                status = "NO"
            if label == "visual_upper" and status == "UNKNOWN" and str(row.get("stand_number")) in visual_stands:
                status = "NO"
            rows.append({**dict(row), "sim_pool_status": status})
        gate_yes = apply_listing_pool_gate(
            [{"parcel_id": r.get("parcel_id"), "stand_number": r.get("stand_number"), "pool_status": r["sim_pool_status"]} for r in rows],
            [{"parcel_id": r.get("parcel_id"), "stand_number": r.get("stand_number"), "pool_status": r["sim_pool_status"]} for r in rows],
            "YES",
        )
        gate_no = apply_listing_pool_gate(
            [{"parcel_id": r.get("parcel_id"), "stand_number": r.get("stand_number"), "pool_status": r["sim_pool_status"]} for r in rows],
            [{"parcel_id": r.get("parcel_id"), "stand_number": r.get("stand_number"), "pool_status": r["sim_pool_status"]} for r in rows],
            "NO",
        )
        return {
            "counts": dict(counts),
            "classified_n": classified,
            "classified_pct": round(100.0 * classified / total, 2),
            "gate_listing_yes": _gate_brief(gate_yes),
            "gate_listing_no": _gate_brief(gate_no),
        }

    return {
        "current_v1": pack(safe, "safe"),
        "conservative_v1_1_no_rule_change": pack(safe, "safe"),
        "upper_bound_if_building_gate_dropped_for_no": pack(upper_no, "upper_no"),
        "unsafe_visual_empty_as_no": pack(visual_upper, "visual_upper"),
        "pr15_listing_yes_survivors": 270,
        "pr15_listing_no_survivors": 239,
    }


def _gate_brief(result) -> dict[str, Any]:
    return {
        "starting_count": result.starting_count,
        "removed_confident_no": result.removed_confident_no,
        "removed_confident_yes": result.removed_confident_yes,
        "yes_survivors": result.yes_survivors,
        "no_survivors": result.no_survivors,
        "unknown_survivors": result.unknown_survivors,
        "total_survivors": result.total_survivors,
        "pct_reduction": result.pct_reduction,
    }


STRATIFIED_EIGHT = (
    ("677", "confirmed_pool_reference", "likely YES"),
    ("392", "likely_safe_no_good_imagery", "likely NO — vacant erf; remain UNKNOWN for hard gate"),
    ("2/379", "unknown_only_poor_building", "likely NO visually — remain UNKNOWN; same OS signature as 339"),
    ("411", "genuine_ambiguous_candidate", "remain UNKNOWN — low-confidence backyard rectangle"),
    ("370", "dark_teal_potential_pool", "likely YES visually — remain UNKNOWN; OS REJECTED a roof blob"),
    ("1/335", "neighbour_pool_correctly_excluded", "likely NO visually — neighbour pools outside GIS line"),
    ("570", "shadow_object_false_candidate", "likely NO visually — remain UNKNOWN; REJECTED ≠ absence"),
    ("406", "observability_failure", "remain UNKNOWN — canopy could hide a 677-scale pool"),
)

KNOWN_DIAGNOSTIC_STANDS = ("370", "447", "570", "612", "408")


def select_panel_stands(unknown_analysis: Mapping[str, Any], inventory_rows: Sequence[Mapping[str, Any]]) -> list[str]:
    """Deterministic stratified sample. Not used to retune inventory."""
    by_reason: dict[str, list[str]] = {}
    for row in unknown_analysis["rows"]:
        by_reason.setdefault(row["primary_reason"], []).append(str(row["stand_number"]))
        if row.get("rejected_subtype"):
            by_reason.setdefault(f"rej_{row['rejected_subtype']}", []).append(str(row["stand_number"]))
    yes = sorted(str(r["stand_number"]) for r in inventory_rows if r.get("pool_status") == "YES")
    no = sorted(str(r["stand_number"]) for r in inventory_rows if r.get("pool_status") == "NO")
    sample = list(KNOWN_DIAGNOSTIC_STANDS)
    sample += [s for s in ("677", "420") if s in yes][:2]
    sample += no[:2]
    for key in (
        "partially_outside_parcel",
        "no_candidate_poor_building",
        "pool_candidate_confidence_insufficient",
        "rej_roof_object",
        "rej_shadow",
        "rej_road_or_neighbour_context",
        "rej_low_confidence_genuine_looking",
    ):
        for stand in sorted(by_reason.get(key, []), key=lambda s: (len(s), s)):
            if stand not in sample:
                sample.append(stand)
            if sum(1 for item in sample if item in by_reason.get(key, [])) >= 2 and key != "partially_outside_parcel":
                break
    # keep unique order
    seen = set()
    ordered = []
    for stand in sample:
        if stand not in seen:
            seen.add(stand)
            ordered.append(stand)
    return ordered[:20]
