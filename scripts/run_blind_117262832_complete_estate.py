#!/usr/bin/env python3
"""Blind ranking of Property24 117262832 against carlswald_north_corrected_002.

First clean blind of PR #23 Hybrid extraction + PR #24 adapter eligibility,
with unchanged Scoring v2. Distinctive Contour v2 is reporting/diagnostic only.

This script is freeze-only. It does not look up street, stand, coordinates,
archives, or any other ground-truth identity.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.gis.estate_ags_matching.blind_116273255_complete_estate import (
    run_freeze,
    sha256_file,
)
from backend.gis.estate_ags_matching.hybrid_geometry_ranking_test import (
    listing_evidence_from_hybrid_block,
    scoring_ready_frames,
)

LISTING_ID = "117262832"
LISTING_URL = (
    "https://www.property24.com/for-sale/carlswald-north-estate/midrand/gauteng/12743/117262832"
)
OUT_DIR = ROOT / "data/investigations/blind_117262832_complete_estate"

SOURCE_LABEL = {
    "yoloe": "YOLOE",
    "yoloe_sam2": "YOLOE/SAM2",
    "fastsam_fallback": "FastSAM fallback",
}


def _verify_freeze_hash() -> str:
    freeze_path = OUT_DIR / "freeze.json"
    recorded = (OUT_DIR / "freeze.sha256").read_text(encoding="utf-8").strip()
    on_disk = sha256_file(freeze_path)
    if on_disk != recorded:
        raise SystemExit(f"freeze hash mismatch on_disk={on_disk} recorded={recorded}")
    print(f"  verified on-disk sha256={on_disk}")
    return on_disk


def _adapter_observational_report(hybrid_path: Path) -> dict:
    """Observe PR #24 adapter decisions. Does not change eligibility rules."""
    if not hybrid_path.is_file():
        return {"hybrid_block_missing": True}
    block = json.loads(hybrid_path.read_text(encoding="utf-8"))
    frames = list(block.get("frames") or [])
    accepted = scoring_ready_frames(frames)
    accepted_ids = {str(frame.get("media_id")) for frame in accepted}
    rows = []
    for frame in frames:
        media_id = frame.get("media_id")
        source = str(frame.get("source") or "")
        scoring_ready = bool(frame.get("scoring_ready"))
        if scoring_ready and str(media_id) in accepted_ids:
            decision = "ACCEPTED"
        elif scoring_ready:
            decision = "REJECTED"
        else:
            decision = "NOT_SCORING_READY"
        rows.append(
            {
                "media_id": media_id,
                "source": source,
                "source_label": SOURCE_LABEL.get(source, source),
                "scoring_ready": scoring_ready,
                "adapter": decision,
            }
        )
    evidence = listing_evidence_from_hybrid_block(block)
    return {
        "frames": rows,
        "scoring_ready_ids": evidence.get("scoring_ready_ids"),
        "chosen_id": evidence.get("chosen_id"),
        "chosen_source": evidence.get("chosen_source"),
        "fastsam_used": bool((evidence.get("feature_sources") or {}).get("fastsam_used")),
        "n_scoring_ready_accepted": len(accepted),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze-only", action="store_true", default=True)
    parser.add_argument("--skip-listing-pool-object", action="store_true")
    parser.add_argument("--skip-panels", action="store_true")
    args = parser.parse_args()
    print("Phase 1 — acquire, gate, rank, freeze (no ground truth)")
    print("STOP after freeze. Ground-truth recovery is not part of this run.")
    result = run_freeze(
        listing_id=LISTING_ID,
        listing_url=LISTING_URL,
        out_dir=OUT_DIR,
        observe_objects=not args.skip_listing_pool_object,
        write_panels=not args.skip_panels,
        force_fresh_photos=True,
        ignore_frozen_hybrid_json=True,
    )
    marker = result["marker"]
    print(f"  freeze={OUT_DIR / 'freeze.json'}")
    print(f"  sha256={marker['sha256']}")
    print(f"  listing_pool={marker['listing_pool_status']} survivors={marker['final_survivor_count']}")
    print(f"  n_ranked={marker['n_candidates']} panels={len(marker.get('panels') or [])}")
    _verify_freeze_hash()
    adapter = _adapter_observational_report(OUT_DIR / "hybrid_block.json")
    (OUT_DIR / "adapter_observational.json").write_text(
        json.dumps(adapter, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        "  adapter_accepted="
        f"{adapter.get('n_scoring_ready_accepted')} chosen={adapter.get('chosen_id')} "
        f"source={adapter.get('chosen_source')} fastsam_used={adapter.get('fastsam_used')}"
    )
    print("Freeze complete. Do not look up ground truth from this script.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
