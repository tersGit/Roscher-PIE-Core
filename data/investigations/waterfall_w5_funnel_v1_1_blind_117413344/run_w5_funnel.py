#!/usr/bin/env python3
"""Run W5's frozen v1.1 funnel without identity or ground-truth access."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from backend.retrieval_funnel import FunnelInput, HierarchicalRetrievalFunnelV11
from data.investigations.waterfall_w4_funnel_blind_117571900.run_w4_funnel import (
    STATES,
    digest,
    inspect,
)

OUT = Path(__file__).resolve().parent
GEOJSON = ROOT / "data" / "estates" / "waterfall_country_estate" / "waterfall_country_estate_w1.geojson"
W1_SHA256 = "6a375bf542bcff28c6a3ee862f9e0c3c9a5395d0497b4159027c40b75cf7be3a"
W1_COMMIT = "e86b156b3f8ac099cd386b9de2b3b2ba609c0635"
FUNNEL_COMMIT = "2f92687"
SOURCE = Path(
    r"C:\Users\ters\copilot-worktrees\Roscher-PIE-Core\tersgit-probable-winner"
    r"\data\visual_index\waterfall_country_estate_w1\_imagery_cache_native15"
)
LISTING_AREA_M2 = 1205.0


def serialise_assessment(assessment: object) -> dict[str, object]:
    candidate = assessment.candidate
    values = {name: getattr(candidate, name).value for name in STATES}
    return {
        "candidate_id": candidate.candidate_id,
        "priority_band": None,
        "processed": False,
        "cadastral_area_m2": candidate.cadastral_area_m2,
        "absolute_area_difference_m2": assessment.absolute_area_difference_m2,
        "percent_area_difference": assessment.percent_area_difference,
        "pool_state": assessment.pool_state.value,
        "pool_priority": assessment.pool_priority,
        "coverage": assessment.evidence_coverage,
        "final_score": assessment.final_compatibility,
        "stand_size_final_contribution": assessment.stand_size_final_contribution,
        "support_count": sum(value in {"MATCH", "PARTIAL"} for value in values.values()),
        "conflict_count": sum(value == "CONFLICT" for value in values.values()),
        "unknown_count": sum(value == "UNKNOWN" for value in values.values()),
        **values,
    }


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    if digest(GEOJSON) != W1_SHA256:
        raise RuntimeError("Frozen W1 GeoJSON hash mismatch.")
    features = json.loads(GEOJSON.read_text(encoding="utf-8"))["features"]
    crops = {path.stem.split("_")[1]: path for path in SOURCE.glob("*_ags_aerial.jpg")}
    if len(features) != 1010 or len(crops) != 1010:
        raise RuntimeError(f"Expected 1,010 frozen W1 parcels and crops; got {len(features)} and {len(crops)}.")

    candidates = []
    for feature in features:
        candidate_id = str(feature["properties"]["pie_property_id"])
        crop = crops.get(candidate_id)
        if crop is None:
            raise RuntimeError(f"Missing frozen native15 crop for anonymous candidate {candidate_id}.")
        candidates.append(inspect(feature, crop))

    request = FunnelInput(LISTING_AREA_M2, True, True)
    funnel = HierarchicalRetrievalFunnelV11()
    result = funnel.retrieve(request, candidates)
    processed = set(result.processed_candidate_ids)
    priority = {
        item.candidate.candidate_id: funnel.priority_for(request, item.candidate).value
        for item in result.assessments
    }
    rows = []
    for assessment in result.assessments:
        row = serialise_assessment(assessment)
        row["priority_band"] = priority[row["candidate_id"]]
        row["processed"] = row["candidate_id"] in processed
        rows.append(row)
    rows.sort(
        key=lambda row: (
            not row["processed"],
            -float(row["final_score"]),
            -float(row["coverage"]),
            str(row["candidate_id"]),
        )
    )
    for rank, row in enumerate(rows, 1):
        row["final_rank"] = rank
    ordered_fields = ["final_rank"] + [field for field in rows[0] if field != "final_rank"]
    rows = [{field: row[field] for field in ordered_fields} for row in rows]
    write_csv(OUT / "FULL_EXPERIMENTAL_SCORES.csv", rows)

    band_rows = [
        {
            "band": band,
            "definition": definition,
            "candidate_count": result.priority_counts[band],
        }
        for band, definition in (
            ("A", "<=5%"),
            ("B", ">5% to <=10%"),
            ("C", ">10% to <=20%"),
            ("D", ">20%"),
        )
    ]
    (OUT / "FUNNEL_BANDS.json").write_text(
        json.dumps(
            {
                "schema_version": "HIERARCHICAL_RETRIEVAL_FUNNEL_V1_1_BANDS",
                "listing_area_m2": LISTING_AREA_M2,
                "listing_area_reliable": True,
                "bands": band_rows,
                "normal_count": result.priority_counts["NORMAL"],
                "universe_count": result.priority_counts["universe"],
                "recoverability": "All 1,010 candidates remain recoverable; bands order work only.",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    histories = []
    for instrumentation, sufficiency, expansion in zip(
        result.stage_instrumentation, result.sufficiency_assessments, result.expansions
    ):
        histories.append(
            {
                "after_priority": instrumentation.priority.value,
                "processed_total": sum(
                    stage.candidate_count
                    for stage in result.stage_instrumentation[
                        : len(histories) + 1
                    ]
                ),
                "serious_candidate_count": len(sufficiency.serious_candidate_ids),
                "top_candidate_id": sufficiency.top_candidate_id,
                "top_candidate_coverage": sufficiency.top_candidate_coverage,
                "top_candidate_support_count": sufficiency.top_candidate_support_count,
                "top_candidate_visible_conflicts": sufficiency.top_candidate_visible_conflicts,
                "combined_support": sufficiency.combined_support,
                "non_unique_top_set_size": sufficiency.non_unique_top_set_size,
                "triggers": [trigger.value for trigger in sufficiency.triggers],
                "expanded": expansion.expanded,
                "from": expansion.from_priority.value,
                "to": expansion.to_priority.value if expansion.to_priority else None,
            }
        )
    (OUT / "EXPANSION_HISTORY.json").write_text(
        json.dumps(
            {
                "schema_version": "HIERARCHICAL_RETRIEVAL_FUNNEL_V1_1_EXPANSION_HISTORY",
                "high_unknown_pool_rate_is_expansion_trigger": False,
                "history": histories,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (OUT / "FUNNEL_STAGE_COUNTS.json").write_text(
        json.dumps(
            {
                "schema_version": "HIERARCHICAL_RETRIEVAL_FUNNEL_V1_1_STAGE_COUNTS",
                "funnel_implementation_commit": FUNNEL_COMMIT,
                "w1_universe_commit": W1_COMMIT,
                "w1_geojson_sha256": W1_SHA256,
                "input": {
                    "listing_area_m2": LISTING_AREA_M2,
                    "listing_area_reliable": True,
                    "listing_has_pool": True,
                },
                "priority_counts": result.priority_counts,
                "stage_instrumentation": [
                    {
                        "priority": stage.priority.value,
                        "candidate_count": stage.candidate_count,
                        "pool_observed_count": stage.pool_observed_count,
                        "pool_unknown_count": stage.pool_unknown_count,
                        "building_observable_count": stage.building_observable_count,
                        "average_coverage": stage.average_coverage,
                        "serious_candidate_count": stage.serious_candidate_count,
                    }
                    for stage in result.stage_instrumentation
                ],
                "immediate_expensive_workload": result.immediate_expensive_workload,
                "total_expensive_workload": result.total_expensive_workload,
                "immediate_work_reduction_vs_1010": round(
                    1 - result.immediate_expensive_workload / 1010, 4
                ),
                "total_work_reduction_vs_1010": round(
                    1 - result.total_expensive_workload / 1010, 4
                ),
                "recoverable_unprocessed_count": len(result.recoverable_candidate_ids),
                "identity_attachment": "NOT_PERFORMED_AT_BLIND_RANKING_FREEZE",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    processed_rows = [row for row in rows if row["processed"]]
    write_csv(OUT / "BLIND_TOP30.csv", processed_rows[:30])
    write_csv(OUT / "BLIND_TOP10.csv", processed_rows[:10])
    panels = OUT / "proof_panels"
    for row in processed_rows[:30]:
        candidate_id = str(row["candidate_id"])
        shutil.copyfile(crops[candidate_id], panels / f"rank_{int(row['final_rank']):02d}.jpg")
    print(
        json.dumps(
            {
                "priority_counts": result.priority_counts,
                "processed": len(processed_rows),
                "immediate": result.immediate_expensive_workload,
                "expansions": histories,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
