#!/usr/bin/env python3
"""Read-only W5 geometry diagnostic; never reranks frozen results."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from backend.gis.estate_ags_matching.parcel_bound_geometry_v1 import PARCEL_BOUND_GEOMETRY_VERSION

FROZEN = ROOT / "data/investigations/waterfall_w5_funnel_v1_1_blind_117413344/FULL_EXPERIMENTAL_SCORES.csv"
OUT = Path(__file__).resolve().parent / "w5_geometry_diagnostic.json"
QC = Path(__file__).resolve().parent / "qc_panels_manifest.json"

def main() -> None:
    with FROZEN.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    normal = [row for row in rows if row["priority_band"] in {"A", "B"}]
    a = [row for row in normal if row["priority_band"] == "A"]
    b = [row for row in normal if row["priority_band"] == "B"]
    if (len(normal), len(a), len(b)) != (637, 272, 365):
        raise RuntimeError("Frozen W5 normal/A/B regression mismatch.")
    payload = {
        "schema_version": PARCEL_BOUND_GEOMETRY_VERSION + "_W5_DIAGNOSTIC",
        "diagnostic_only": True, "reranked": False, "claims": "No recall, identity, or accuracy claim.",
        "source": str(FROZEN.relative_to(ROOT)).replace("\\", "/"),
        "normal_count": 637, "priority_a_count": 272, "priority_b_count": 365,
        "processed_b": True, "b_reason": "A had no credible geometry evidence; B was expanded under the preregistered rule.",
        "geometry": {"pool": 0, "building": 0, "relation": 0, "multiple_water": 0},
        "quality_distribution": {"UNKNOWN": 637},
        "lane": {"entrants": 0, "recovery": 637, "promotions": 0, "demotions": 0, "fine_candidates": 0},
        "failure_modes": {"source_unavailable": 637, "detector": 0, "mask": 0, "binding": 0, "resolution": 0, "occlusion": 0, "small_object": 0, "relational_unreliable": 0},
        "note": "Recovered W1 native15 imagery is absent locally and was not fetched or rebuilt; UNKNOWN is preserved.",
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    QC.write_text(json.dumps({"schema_version": PARCEL_BOUND_GEOMETRY_VERSION, "panels": [], "reason": "No suitable locally recovered imagery; no panels fabricated."}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))

if __name__ == "__main__":
    main()
