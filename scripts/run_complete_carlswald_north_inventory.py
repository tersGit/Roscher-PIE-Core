#!/usr/bin/env python3
"""Populate Estate Property Inventory v1 for complete Carlswald North (EXT.3+6+13).

Reuses frozen 001 EXT.6/EXT.13 inventory rows. Processes only newly introduced
EXT.3 parcels. Does not modify OS v1, FastSAM config, native15, ranking, or
classification semantics.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.gis.dataset_registry import COMPLETE_CARLSWALD_NORTH, FROZEN_CARLSWALD_NORTH_001, require_active_dataset
from backend.gis.estate_ags_matching.complete_estate_inventory import (
    INVESTIGATION_OUT,
    build_complete_inventory,
    gate_baselines,
    load_complete_dataset,
)
from backend.gis.estate_ags_matching.estate_property_inventory_v1 import load_inventory_records, status_counts
from backend.gis.estate_ags_matching.listing_pool_gate_v1 import apply_listing_pool_gate


def _pct(part: int, whole: int) -> float:
    return 0.0 if whole == 0 else round(100.0 * part / whole, 2)


def _write_report(payload: dict) -> str:
    counts = payload["inventory_counts"]
    scan = payload["scan"]
    g_yes = payload["gate_listing_yes"]
    g_no = payload["gate_listing_no"]
    table = payload["extension_table"]
    lines = [
        "# Complete Carlswald North inventory (EXT.3 + EXT.6 + EXT.13)",
        "",
        "Dataset completion + diagnosis. Frozen OS v1 / FastSAM / native15 / Scoring v2 /",
        "Hybrid Pool Geometry / viewpoint gates / production ranking / Listing Pool Gate",
        "semantics are unchanged. Colour is not used in ranking.",
        "",
        f"Frozen 001 (`{FROZEN_CARLSWALD_NORTH_001}`) is intact for PR #15/#16.",
        f"Complete universe is `{COMPLETE_CARLSWALD_NORTH}`.",
        "",
        "## B. Complete GIS universe",
        "",
        "| Extension | Source parcels | Included unique properties |",
        "| --------- | -------------: | -------------------------: |",
    ]
    for row in table:
        lines.append(
            f"| {row['extension']} | {row['source_parcels']} | {row['included_unique_properties']} |"
        )
    lines += [
        "",
        "## C. Inventory v1 (complete estate)",
        "",
        f"- total parcels: **{scan['parcels_total']}**",
        f"- reused from frozen 001: **{scan['parcels_reused']}**",
        f"- newly processed: **{scan['newly_processed']}**",
        f"- rescanned: **{scan['rescanned']}**",
        f"- FastSAM runs: **{scan['fastsam_runs']}**",
        f"- imagery tiles required/reused/downloaded: "
        f"{scan['tile_stats'].get('tiles_required')}/"
        f"{scan['tile_stats'].get('tiles_reused')}/"
        f"{scan['tile_stats'].get('tiles_downloaded')}",
        f"- crops written/reused/failed: "
        f"{scan['crop_stats'].get('crops_written')}/"
        f"{scan['crop_stats'].get('crops_reused')}/"
        f"{scan['crop_stats'].get('crops_failed')}",
        f"- runtime: **{scan['runtime_s']} s**",
        f"- FastSAM available: {scan['fastsam_available']}",
        "",
        f"- YES: **{counts['YES']}** ({counts['yes_pct']}%)",
        f"- NO: **{counts['NO']}** ({counts['no_pct']}%)",
        f"- UNKNOWN: **{counts['UNKNOWN']}** ({counts['unknown_pct']}%)",
        "",
        "## D. Complete-estate Pool Gate baseline",
        "",
        "### Listing POOL = YES",
        "",
        f"- starting parcels: {g_yes['starting_count']}",
        f"- confident NO removed: {g_yes['parcels_removed_confident_no']}",
        f"- YES survivors: {g_yes['yes_survivors']}",
        f"- UNKNOWN survivors: {g_yes['unknown_survivors']}",
        f"- final survivors: {g_yes['total_survivors']}",
        f"- percentage reduction: **{g_yes['pct_reduction']}%**",
        "",
        "### Listing POOL = NO",
        "",
        f"- starting parcels: {g_no['starting_count']}",
        f"- confident YES removed: {g_no['parcels_removed_confident_yes']}",
        f"- NO survivors: {g_no['no_survivors']}",
        f"- UNKNOWN survivors: {g_no['unknown_survivors']}",
        f"- final survivors: {g_no['total_survivors']}",
        f"- percentage reduction: **{g_no['pct_reduction']}%**",
        "",
        "UNKNOWN always survives. Classification semantics unchanged from PR #15.",
        "",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    require_active_dataset(COMPLETE_CARLSWALD_NORTH)
    require_active_dataset(FROZEN_CARLSWALD_NORTH_001)
    dataset = load_complete_dataset()
    records_map, scan = build_complete_inventory(dataset=dataset, allow_fastsam=True, download_new_tiles=True)
    records = load_inventory_records(COMPLETE_CARLSWALD_NORTH)
    counts = status_counts(records)
    total = len(records)
    gates = gate_baselines(records)
    unk_gate = apply_listing_pool_gate(records, records, "UNKNOWN")
    assert unk_gate.total_survivors == total
    from backend.gis.carlswald_north_complete import freeze_summary_table

    payload = {
        "estate_id": COMPLETE_CARLSWALD_NORTH,
        "frozen_001": FROZEN_CARLSWALD_NORTH_001,
        "inventory_counts": {
            "total": total,
            "YES": counts["YES"],
            "NO": counts["NO"],
            "UNKNOWN": counts["UNKNOWN"],
            "yes_pct": _pct(counts["YES"], total),
            "no_pct": _pct(counts["NO"], total),
            "unknown_pct": _pct(counts["UNKNOWN"], total),
        },
        "scan": scan,
        "gate_listing_yes": gates["listing_yes"],
        "gate_listing_no": gates["listing_no"],
        "gate_listing_unknown": gates["listing_unknown"],
        "extension_table": freeze_summary_table(dataset),
        "os_status_tally": dict(Counter(row.get("os_pool_status") for row in records)),
        "n_written": len(records_map),
        "production_ranking_modified": False,
        "classification_semantics_unchanged": True,
        "frozen_001_inventory_untouched": True,
    }
    INVESTIGATION_OUT.mkdir(parents=True, exist_ok=True)
    (INVESTIGATION_OUT / "latest.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    report = _write_report(payload)
    (INVESTIGATION_OUT / "report.md").write_text(report, encoding="utf-8")
    print(json.dumps({k: payload[k] for k in ("estate_id", "inventory_counts", "scan", "gate_listing_yes", "gate_listing_no")}, indent=2))
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
