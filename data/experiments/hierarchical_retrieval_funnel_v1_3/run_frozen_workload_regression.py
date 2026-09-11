#!/usr/bin/env python3
"""Read-only v1.3 workload regression over frozen W1 cadastral areas."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from backend.retrieval_funnel.hierarchical_v1_3 import (
    HighConfidenceStandSizeGate,
    ListingAreaAssessment,
    AreaConfidence,
    StandSizeCandidate,
)

GEOJSON = ROOT / "data/estates/waterfall_country_estate/waterfall_country_estate_w1.geojson"
OUT = Path(__file__).resolve().parent / "frozen_workload_regression.json"
W1_SHA256 = "6a375bf542bcff28c6a3ee862f9e0c3c9a5395d0497b4159027c40b75cf7be3a"
W1_COMMIT = "e86b156b3f8ac099cd386b9de2b3b2ba609c0635"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            value.update(block)
    return value.hexdigest()


def workload(listing: str, area_m2: float, candidates: list[StandSizeCandidate]) -> dict[str, object]:
    result = HighConfidenceStandSizeGate().select(
        ListingAreaAssessment(area_m2, AreaConfidence.HIGH_CONFIDENCE, "frozen_structured_listing_fact"),
        candidates,
    )
    if not result.gate_enabled:
        raise RuntimeError("Frozen structured listing fact must enable the gate.")
    deferred = len(result.excluded_from_ordinary_queue_ids)
    return {
        "listing": listing,
        "listing_area_m2": area_m2,
        "listing_area_confidence": result.listing_area_confidence.value,
        "plus_minus_10_lower_m2": result.lower_bound_m2,
        "plus_minus_10_upper_m2": result.upper_bound_m2,
        "priority_a_count": len(result.priority_a_ids),
        "priority_b_count": len(result.priority_b_ids),
        "normal_count": len(result.normal_candidate_ids),
        "deferred_exceptional_rescue_count": deferred,
        "deferred_percent_of_full_before_visual": round(deferred / len(candidates) * 100, 3),
        "claims": "No recall, identity, accuracy, scoring, or candidate visual-work claim.",
    }


def main() -> None:
    if digest(GEOJSON) != W1_SHA256:
        raise RuntimeError("Frozen W1 GeoJSON hash mismatch.")
    features = json.loads(GEOJSON.read_text(encoding="utf-8"))["features"]
    candidates = [
        StandSizeCandidate(
            str(feature["properties"]["pie_property_id"]),
            float(feature["properties"]["area_sqm"]),
        )
        for feature in features
    ]
    if len(candidates) != 1010:
        raise RuntimeError(f"Expected 1,010 frozen W1 parcels, found {len(candidates)}.")
    payload = {
        "schema_version": "HIERARCHICAL_RETRIEVAL_FUNNEL_V1_3_FROZEN_WORKLOAD_REGRESSION",
        "diagnostic_only": True,
        "source_access": "frozen_listing_facts_and_w1_cadastral_areas_only",
        "provenance": {
            "w1_universe_commit": W1_COMMIT,
            "w1_geojson": str(GEOJSON.relative_to(ROOT)).replace("\\", "/"),
            "w1_geojson_sha256": W1_SHA256,
            "candidate_count": len(candidates),
        },
        "workloads": [
            workload("W4 Property24 117571900", 1251.0, candidates),
            workload("W5 Property24 117413344", 1205.0, candidates),
        ],
    }
    expected = ((270, 428, 582), (272, 637, 373))
    actual = tuple(
        (
            item["priority_a_count"],
            item["normal_count"],
            item["deferred_exceptional_rescue_count"],
        )
        for item in payload["workloads"]
    )
    if actual != expected:
        raise RuntimeError(f"Frozen workload regression mismatch: {actual!r}.")
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
