#!/usr/bin/env python3
"""Build Estate Property Inventory v1 for Carlswald North (native15 + OS v1).

Experimental cached intelligence layer. Does not modify native15, OS v1,
FastSAM, Scoring v2, Hybrid Pool Geometry, viewpoint gates, or production
ranking. Colour is not used.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.gis.dataset_registry import CORRECT_CARLSWALD_NORTH, require_active_dataset
from backend.gis.estate_ags_matching.estate_property_inventory_v1 import (
    ALGORITHM_VERSION,
    DEFAULT_OS_DIR,
    SCHEMA_VERSION,
    SEGMENTATION_SOURCE_VERSION,
    EstateInventoryStore,
    load_inventory_records,
    scan_estate_inventory,
    status_counts,
)
from backend.gis.estate_ags_matching.listing_pool_gate_v1 import apply_listing_pool_gate
from backend.imagery.estate_tiles import cache_root_for, crop_dir_for

ESTATE_ID = CORRECT_CARLSWALD_NORTH
GIS_PATH = ROOT / "data" / "gis" / f"{ESTATE_ID}.json"
OUT = ROOT / "data" / "investigations" / "estate_property_inventory_v1" / "carlswald_north"
DIAGNOSTIC_STANDS = ("677", "612", "570", "420", "585", "408", "365", "491", "447", "370")
FROZEN_OS_RANKING = ROOT / "data/investigations/os_v1_ranking_experiment/carlswald_north_116978058/latest.json"


def _pct(part: int, whole: int) -> float:
    return 0.0 if whole == 0 else round(100.0 * part / whole, 2)


def _coverage(records: list[dict], crop_dir: Path, tile_cache: Path) -> dict:
    crops_present = 0
    os_present = 0
    tiles_present = 0
    tiles_missing = 0
    for record in records:
        if record.get("crop_hash"):
            crops_present += 1
        if record.get("segmentation_source") == SEGMENTATION_SOURCE_VERSION:
            os_present += 1
        tiles_present += sum(1 for _ in (record.get("tile_hashes") or {}))
        tiles_missing += len(record.get("tile_ids") or []) - len(record.get("tile_hashes") or {})
    tile_files = list(tile_cache.glob("tile_*_native15_*.jpg")) if tile_cache.is_dir() else []
    crop_files = list(crop_dir.glob("*_ags_aerial.jpg")) if crop_dir.is_dir() else []
    return {
        "unique_erven": len(records),
        "os_v1_fingerprints": os_present,
        "native15_crops_on_disk": len(crop_files),
        "native15_tiles_on_disk": len(tile_files),
        "records_with_crop_hash": crops_present,
        "tile_hash_hits": tiles_present,
        "tile_hash_misses": tiles_missing,
        "imagery_profile": "native15",
        "coverage_basis": "frozen object_segmentation_v1 native15 fingerprints"
        if os_present == len(records)
        else "partial",
    }


def _diagnostics(records: list[dict]) -> list[dict]:
    by_stand = {str(row.get("stand_number")): row for row in records}
    rows = []
    for stand in DIAGNOSTIC_STANDS:
        row = by_stand.get(stand)
        if not row:
            rows.append({"stand_number": stand, "missing": True})
            continue
        rows.append(
            {
                "stand_number": stand,
                "pool_status": row.get("pool_status"),
                "os_pool_status": row.get("os_pool_status"),
                "unknown_reason": row.get("unknown_reason"),
                "diagnostic_flags": row.get("diagnostic_flags"),
                "pool_area_m2": row.get("pool_area_m2"),
            }
        )
    return rows


def _gate_block(result) -> dict:
    payload = result.to_dict()
    payload.pop("survivor_parcel_ids", None)
    payload.pop("removed_parcel_ids", None)
    return payload


def _write_report(payload: dict) -> str:
    counts = payload["inventory_counts"]
    first = payload["first_scan"]
    reuse = payload["reuse_scan"]
    g_yes = payload["gate_listing_yes"]
    g_no = payload["gate_listing_no"]
    lines = [
        "# Estate Property Inventory v1 — Carlswald North",
        "",
        "Experimental cached intelligence layer on frozen native15 + Object Segmentation v1.",
        "Production ranking, Scoring v2 weights, Hybrid Pool Geometry, viewpoint gates,",
        "FastSAM configuration, and OS v1 behaviour are unchanged. Colour is not used.",
        "",
        "## A. Implementation summary",
        "",
        "One versioned JSONL inventory per estate, one record per erf. Pool status is",
        "`YES | NO | UNKNOWN` derived from frozen OS v1. REJECTED never becomes NO",
        "(protects dark-teal misses). Neighbour / parcel-bleed detections cannot be YES.",
        "Unchanged imagery + algorithm version reuses the stored row and does not invoke FastSAM.",
        "Listing Pool Gate v1 filters the candidate universe **before** detailed ranking.",
        "",
        "## B. Schema",
        "",
        f"- schema_version: `{payload['schema_version']}`",
        f"- algorithm_version: `{payload['algorithm_version']}`",
        "- format: deterministic JSONL (`current.jsonl`) + append-only `history.jsonl`",
        "- location: `data/estate_inventory/<estate_id>/`",
        "",
        "## C. Carlswald North inventory counts",
        "",
        f"- estate_id: `{payload['estate_id']}`",
        f"- parcel count (unique erven after GIS pass 1): **{counts['total']}**",
        f"- GIS pass-1 rows before property_id collapse: {payload['gis_pass1_rows']}",
        f"- imagery coverage: {payload['imagery_coverage']['coverage_basis']}; "
        f"OS v1 fingerprints {payload['imagery_coverage']['os_v1_fingerprints']}/{counts['total']}; "
        f"crops on disk {payload['imagery_coverage']['native15_crops_on_disk']}; "
        f"tiles on disk {payload['imagery_coverage']['native15_tiles_on_disk']}",
        f"- YES: **{counts['YES']}** ({counts['yes_pct']}%)",
        f"- NO: **{counts['NO']}** ({counts['no_pct']}%)",
        f"- UNKNOWN: **{counts['UNKNOWN']}** ({counts['unknown_pct']}%)",
        f"- first-scan runtime: **{first['runtime_s']} s**",
        f"- parcels reused vs newly processed (first scan): reused {first['parcels_reused']}, "
        f"rescanned/new {first['parcels_rescanned']}, FastSAM runs {first['fastsam_runs']}",
        "",
        "## D. Cache / reuse",
        "",
        f"- second scan runtime: **{reuse['runtime_s']} s**",
        f"- parcels reused: **{reuse['parcels_reused']}**",
        f"- parcels rescanned: **{reuse['parcels_rescanned']}**",
        f"- FastSAM runs: **{reuse['fastsam_runs']}**",
        f"- changed tiles: {len(reuse['changed_tiles'])}",
        f"- unchanged tiles: {len(reuse['unchanged_tiles'])}",
        "",
        "## E. Listing pool gate (before ranking)",
        "",
        "### Test 1 — listing has pool (YES)",
        "",
        f"- starting parcel count: {g_yes['starting_count']}",
        f"- parcels removed as confident NO: {g_yes['parcels_removed_confident_no']}",
        f"- YES survivors: {g_yes['yes_survivors']}",
        f"- UNKNOWN survivors: {g_yes['unknown_survivors']}",
        f"- total survivors: {g_yes['total_survivors']}",
        f"- search-space reduction: **{g_yes['pct_reduction']}%**",
        "",
        "### Test 2 — listing has no pool (NO)",
        "",
        f"- starting parcel count: {g_no['starting_count']}",
        f"- parcels removed as confident YES: {g_no['parcels_removed_confident_yes']}",
        f"- NO survivors: {g_no['no_survivors']}",
        f"- UNKNOWN survivors: {g_no['unknown_survivors']}",
        f"- total survivors: {g_no['total_survivors']}",
        f"- search-space reduction: **{g_no['pct_reduction']}%**",
        "",
        "UNKNOWN rows survive both gates. Listing UNKNOWN applies no pool filter.",
        "",
        "## F. Known diagnostic failures (not used to retune)",
        "",
    ]
    for row in payload["diagnostic_stands"]:
        lines.append(
            f"- Stand {row['stand_number']}: inventory={row.get('pool_status')} "
            f"os={row.get('os_pool_status')} reason={row.get('unknown_reason')} "
            f"flags={row.get('diagnostic_flags')}"
        )
    lines += [
        "",
        "Stand 370 (dark teal) stays UNKNOWN, not NO. Stands 408 and 612 are not YES",
        "(neighbour pools excluded by the OS v1 parcel mask; inventory additionally",
        "refuses YES on `partially_outside_parcel`).",
        "",
        "## G. Confirmations",
        "",
        f"- neighbour pools excluded from YES: {payload['confirmations']['neighbour_pools_not_yes']}",
        f"- UNKNOWN never hard-discarded: {payload['confirmations']['unknown_never_hard_discarded']}",
        f"- production ranking untouched: {payload['confirmations']['production_ranking_untouched']}",
        f"- frozen baseline_rank still {payload['confirmations']['frozen_baseline_rank']}",
        "",
        "No scoring weights were changed.",
        "",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    require_active_dataset(ESTATE_ID)
    dataset = json.loads(GIS_PATH.read_text(encoding="utf-8"))
    gis_pass1_rows = sum(
        1
        for item in dataset["parcels"]
        if item.get("land_type") == "Erven"
        and item.get("class") not in {"non_residential"}
        and (item.get("area_sqm") or 0) < 8000
        and item.get("geometry")
        and item.get("stand_number")
        and not str(item["stand_number"]).startswith("RE/")
    )
    store = EstateInventoryStore(ESTATE_ID)
    if store.current_path.is_file():
        store.current_path.unlink()
    if store.history_path.is_file():
        store.history_path.unlink()

    first_records, first_stats = scan_estate_inventory(
        estate_id=ESTATE_ID,
        dataset=dataset,
        store=store,
        os_dir=DEFAULT_OS_DIR,
        allow_fastsam=True,
    )
    reuse_records, reuse_stats = scan_estate_inventory(
        estate_id=ESTATE_ID,
        dataset=dataset,
        store=store,
        os_dir=DEFAULT_OS_DIR,
        allow_fastsam=True,
    )
    records = load_inventory_records(ESTATE_ID)
    counts = status_counts(records)
    total = len(records)
    crop_dir = crop_dir_for(ESTATE_ID, "native15")
    tile_cache = cache_root_for(ESTATE_ID, "native15")

    gate_yes = apply_listing_pool_gate(records, records, "YES")
    gate_no = apply_listing_pool_gate(records, records, "NO")
    gate_unk = apply_listing_pool_gate(records, records, "UNKNOWN")
    assert gate_unk.total_survivors == total
    assert gate_yes.unknown_survivors == counts["UNKNOWN"]
    assert gate_no.unknown_survivors == counts["UNKNOWN"]

    diagnostics = _diagnostics(records)
    by_stand = {row["stand_number"]: row for row in diagnostics}
    neighbour_ok = by_stand["408"]["pool_status"] != "YES" and by_stand["612"]["pool_status"] != "YES"
    dark_teal_ok = by_stand["370"]["pool_status"] == "UNKNOWN"
    frozen = json.loads(FROZEN_OS_RANKING.read_text(encoding="utf-8"))

    payload = {
        "schema_version": SCHEMA_VERSION,
        "algorithm_version": ALGORITHM_VERSION,
        "estate_id": ESTATE_ID,
        "gis_pass1_rows": gis_pass1_rows,
        "inventory_counts": {
            "total": total,
            "YES": counts["YES"],
            "NO": counts["NO"],
            "UNKNOWN": counts["UNKNOWN"],
            "yes_pct": _pct(counts["YES"], total),
            "no_pct": _pct(counts["NO"], total),
            "unknown_pct": _pct(counts["UNKNOWN"], total),
        },
        "imagery_coverage": _coverage(records, crop_dir, tile_cache),
        "first_scan": first_stats.to_dict(),
        "reuse_scan": reuse_stats.to_dict(),
        "gate_listing_yes": _gate_block(gate_yes),
        "gate_listing_no": _gate_block(gate_no),
        "gate_listing_unknown": _gate_block(gate_unk),
        "diagnostic_stands": diagnostics,
        "os_status_tally": dict(Counter(row.get("os_pool_status") for row in records)),
        "confirmations": {
            "neighbour_pools_not_yes": neighbour_ok,
            "unknown_never_hard_discarded": gate_yes.unknown_survivors == counts["UNKNOWN"]
            and gate_no.unknown_survivors == counts["UNKNOWN"],
            "dark_teal_370_unknown": dark_teal_ok,
            "production_ranking_untouched": frozen["production_ranking_modified"] is False,
            "frozen_baseline_rank": frozen["evaluation"]["baseline_rank"],
            "frozen_baseline_score": frozen["evaluation"]["baseline_score"],
            "fastsam_not_required_for_bootstrap": first_stats.fastsam_runs == 0,
        },
        "n_first_records": len(first_records),
        "n_reuse_records": len(reuse_records),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "latest.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report = _write_report(payload)
    (OUT / "report.md").write_text(report, encoding="utf-8")
    print(json.dumps({k: payload[k] for k in ("estate_id", "inventory_counts", "first_scan", "reuse_scan", "gate_listing_yes", "gate_listing_no", "confirmations")}, indent=2))
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
