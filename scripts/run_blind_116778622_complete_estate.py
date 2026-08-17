#!/usr/bin/env python3
"""Blind ranking of Property24 116778622 against carlswald_north_corrected_002.

Uses the exact frozen stack from PR #18 and PR #19.
Phase 1 writes freeze.json before any stand/address lookup.
Prior 116778622 artifacts are excluded from ranking input; Hybrid is extracted fresh.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.gis.estate_ags_matching.blind_116273255_complete_estate import (
    run_after_freeze,
    run_freeze,
    sha256_file,
)

LISTING_ID = "116778622"
LISTING_URL = (
    "https://www.property24.com/for-sale/carlswald-north-estate/midrand/gauteng/12743/116778622"
)
OUT_DIR = ROOT / "data/investigations/blind_116778622_complete_estate"


def _verify_freeze_hash() -> str:
    freeze_path = OUT_DIR / "freeze.json"
    recorded = (OUT_DIR / "freeze.sha256").read_text(encoding="utf-8").strip()
    on_disk = sha256_file(freeze_path)
    if on_disk != recorded:
        raise SystemExit(f"freeze hash mismatch on_disk={on_disk} recorded={recorded}")
    print(f"  verified on-disk sha256={on_disk}")
    return on_disk


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze-only", action="store_true")
    parser.add_argument("--after-freeze", action="store_true")
    parser.add_argument("--skip-listing-pool-object", action="store_true")
    parser.add_argument("--skip-panels", action="store_true")
    args = parser.parse_args()
    kwargs = dict(
        listing_id=LISTING_ID,
        listing_url=LISTING_URL,
        out_dir=OUT_DIR,
    )
    if args.after_freeze and not args.freeze_only:
        _verify_freeze_hash()
        result = run_after_freeze(**kwargs)
        gt = result["ground_truth"]
        ev = result["evaluation"]
        print(f"ground_truth stand={gt.get('confirmed_stand')} confidence={gt.get('confidence')}")
        print(f"evaluation outcome={ev.get('outcome')} rank={ev.get('frozen_rank')} score={ev.get('frozen_score')}")
        print(f"comparison_three={result.get('comparison_three')}")
        return 0
    if not args.after_freeze:
        print("Phase 1 — acquire, gate, rank, freeze (no ground truth)")
        result = run_freeze(
            observe_objects=not args.skip_listing_pool_object,
            write_panels=not args.skip_panels,
            force_fresh_photos=True,
            ignore_frozen_hybrid_json=True,
            **kwargs,
        )
        marker = result["marker"]
        print(f"  freeze={OUT_DIR / 'freeze.json'}")
        print(f"  sha256={marker['sha256']}")
        print(f"  listing_pool={marker['listing_pool_status']} survivors={marker['final_survivor_count']}")
        print(f"  n_ranked={marker['n_candidates']} panels={len(marker.get('panels') or [])}")
        _verify_freeze_hash()
        if args.freeze_only:
            return 0
    print("Phase 2 — ground truth after freeze file exists")
    _verify_freeze_hash()
    result = run_after_freeze(**kwargs)
    gt = result["ground_truth"]
    ev = result["evaluation"]
    print(f"  stand={gt.get('confirmed_stand')} confidence={gt.get('confidence')}")
    print(f"  outcome={ev.get('outcome')} rank={ev.get('frozen_rank')} score={ev.get('frozen_score')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
