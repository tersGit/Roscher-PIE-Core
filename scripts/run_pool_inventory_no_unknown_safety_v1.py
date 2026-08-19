#!/usr/bin/env python3
"""Build inventory v1.1.0 overlay and re-run listing 117170887 from corrected Pool Gate.

Does not rewrite frozen 001/002 inventory, PR #28 freeze, Scoring v2, Hybrid,
FastSAM, Corner Gate internals, POV, or colour rules.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.gis.estate_ags_matching.pool_inventory_no_unknown_safety_v1 import (
    INVESTIGATION_DIR,
    build_overlay_inventory,
    run_listing_from_corrected_gate,
    write_overlay,
    write_report,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--download-crops", action="store_true")
    parser.add_argument("--skip-listing-rerun", action="store_true")
    args = parser.parse_args()
    INVESTIGATION_DIR.mkdir(parents=True, exist_ok=True)
    records = build_overlay_inventory(download_crops=args.download_crops)
    overlay_path = write_overlay(records)
    (INVESTIGATION_DIR / "overlay_counts.json").write_text(
        json.dumps(
            {
                "overlay_path": str(overlay_path.relative_to(ROOT)),
                "n": len(records),
                "yes": sum(1 for row in records if row.get("pool_status") == "YES"),
                "no": sum(1 for row in records if row.get("pool_status") == "NO"),
                "unknown": sum(1 for row in records if row.get("pool_status") == "UNKNOWN"),
                "stand_641": next(row for row in records if str(row.get("stand_number")) == "641"),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"overlay={overlay_path} n={len(records)}")
    if args.skip_listing_rerun:
        return 0
    result = run_listing_from_corrected_gate(records)
    (INVESTIGATION_DIR / "listing_rerun.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    report = write_report(result)
    print(f"report={report}")
    print(f"POOL GATE SAFETY FIX: {'PASS' if result.get('pass') else 'FAIL'}")
    print(f"next_bottleneck={result.get('next_bottleneck')}")
    print(
        "A={A} B_before={B[before]} B_after={B[after]} C={C} D={D} E={E} F={F} G={G} H={H}".format(
            A=result.get("A_parcels_before_pool_gate"),
            B=result.get("B_inventory_counts"),
            C=result.get("C_pool_gate_survivor_count"),
            D=result.get("D_stand_641_survives_pool_gate"),
            E=result.get("E_corner_gate_641"),
            F=result.get("F_scoring_eligible"),
            G=result.get("G_rank"),
            H=result.get("H_unranked_reason"),
        )
    )
    return 0 if result.get("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
