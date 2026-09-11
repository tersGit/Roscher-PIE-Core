#!/usr/bin/env python3
"""Read-only v1.2 workload diagnostic over frozen W5 candidate output."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from backend.retrieval_funnel.hierarchical_v1_2 import (
    Compatibility,
    HierarchicalRetrievalFunnelV12,
    LaneCandidate,
    ObservableEvidence,
)

FROZEN_CSV = ROOT / (
    "data/investigations/waterfall_w5_funnel_v1_1_blind_117413344/"
    "FULL_EXPERIMENTAL_SCORES.csv"
)
OUT = Path(__file__).resolve().parent / "w5_frozen_diagnostic.json"


def legacy_observation(value: str) -> ObservableEvidence:
    """Preserve legacy status without inventing unavailable visual geometry."""
    if value == "CONFLICT":
        return ObservableEvidence(True, True, Compatibility.VISIBLE_CONFLICT)
    if value == "MATCH":
        return ObservableEvidence(True, True, Compatibility.MATCH)
    if value == "PARTIAL":
        return ObservableEvidence(True, True, Compatibility.PARTIAL)
    return ObservableEvidence()


def main() -> None:
    with FROZEN_CSV.open(newline="", encoding="utf-8") as handle:
        rows = [row for row in csv.DictReader(handle) if row["priority_band"] == "A"]
    if len(rows) != 272:
        raise RuntimeError(f"Expected frozen W5 A=272, found {len(rows)}.")
    candidates = [
        LaneCandidate(
            row["candidate_id"],
            "A",
            legacy_observation(row["pool_geometry"]) if row["pool_state"] == "OBSERVED_POOL"
            else ObservableEvidence(),
            legacy_observation(row["building"]),
        )
        for row in rows
    ]
    result = HierarchicalRetrievalFunnelV12().process_band("A", candidates)
    payload = {
        "schema_version": "HIERARCHICAL_RETRIEVAL_FUNNEL_V1_2_W5_FROZEN_DIAGNOSTIC",
        "diagnostic_only": True,
        "source": str(FROZEN_CSV.relative_to(ROOT)).replace("\\", "/"),
        "source_access": "frozen_candidate_output_only",
        "claims": "No recall, identity, accuracy, or blind reranking claim.",
        "area_band": "A",
        "candidate_count": len(candidates),
        "observed_pool_count": sum(row["pool_state"] == "OBSERVED_POOL" for row in rows),
        "pool_evidence_lane_count": sum(
            row["pool_state"] == "OBSERVED_POOL" and candidate.pool_geometry.strong
            for row, candidate in zip(rows, candidates)
        ),
        "pool_recovery_lane_count": sum(
            row["pool_state"] == "UNKNOWN" for row in rows
        ),
        "building_promotions": len(result.promotion_ids),
        "remaining_after_direct_conflicts": len(result.recovery_candidate_ids),
        "final_expensive_fine_count": len(result.expensive_candidate_ids),
        "would_stop_in_a": result.stopped,
        "expansion_triggers": [trigger.value for trigger in result.triggers],
        "workload": {
            "v1_1_immediate_expensive": 272,
            "v1_2_expensive": len(result.expensive_candidate_ids),
            "reduction_vs_v1_1_immediate": round(
                1 - len(result.expensive_candidate_ids) / 272, 4
            ),
        },
        "caveat": (
            "Frozen source has legacy compatibility labels but no reliable aspect, "
            "shape, orientation, relation, or strong building-footprint fields; "
            "legacy MATCH is retained as MATCH rather than upgraded to STRONG_MATCH."
        ),
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
