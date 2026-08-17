#!/usr/bin/env python3
"""Blind ranking of Property24 116273255 against carlswald_north_corrected_002.

Phase 1 writes freeze.json before any stand/address lookup.
Phase 2 may inspect ground truth only after that file exists.

Does not modify Scoring v2, Hybrid v1, OS v1, FastSAM, native15, Pool Gate, or inventory.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.gis.estate_ags_matching.blind_116273255_complete_estate import (
    FREEZE_PATH,
    run_after_freeze,
    run_freeze,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze-only", action="store_true")
    parser.add_argument("--after-freeze", action="store_true")
    parser.add_argument("--skip-listing-pool-object", action="store_true")
    args = parser.parse_args()
    if args.after_freeze and not args.freeze_only:
        result = run_after_freeze()
        gt = result["ground_truth"]
        ev = result["evaluation"]
        print(f"ground_truth stand={gt.get('confirmed_stand')} confidence={gt.get('confidence')}")
        print(f"evaluation outcome={ev.get('outcome')} rank={ev.get('frozen_rank')} score={ev.get('frozen_score')}")
        return 0
    if not args.after_freeze:
        print("Phase 1 — acquire, gate, rank, freeze (no ground truth)")
        result = run_freeze(observe_objects=not args.skip_listing_pool_object)
        marker = result["marker"]
        print(f"  freeze={FREEZE_PATH}")
        print(f"  sha256={marker['sha256']}")
        print(f"  listing_pool={marker['listing_pool_status']} survivors={marker['final_survivor_count']}")
        print(f"  n_ranked={marker['n_candidates']} panels={len(marker.get('panels') or [])}")
        if args.freeze_only:
            return 0
    print("Phase 2 — ground truth after freeze file exists")
    result = run_after_freeze()
    gt = result["ground_truth"]
    ev = result["evaluation"]
    print(f"  stand={gt.get('confirmed_stand')} confidence={gt.get('confidence')}")
    print(f"  outcome={ev.get('outcome')} rank={ev.get('frozen_rank')} score={ev.get('frozen_score')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
