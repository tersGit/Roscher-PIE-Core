#!/usr/bin/env python3
"""Diagnose OS v1 / FastSAM no_pool_candidate misses vs Stand 677.

Does not modify OS v1, FastSAM configuration, native15, ranking, or inventory.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.gis.estate_ags_matching.complete_estate_inventory import fastsam_importable
from backend.gis.estate_ags_matching.fastsam_miss_diagnostic import (
    ALL_STANDS,
    MISS_STANDS,
    OUT_DIR,
    REFERENCE_STAND,
    comparison_table,
    diagnose_stand,
    hypothesis_report,
    load_gis,
    recommended_experiment,
)


def _write_report(payload: dict) -> str:
    table = payload["comparison_table"]
    hyp = payload["hypothesis"]
    rec = payload["recommended_experiment"]
    lines = [
        "# FastSAM / OS v1 pool-miss diagnostic",
        "",
        "Read-only of frozen OS v1. FastSAM configuration, native15, Scoring v2,",
        "Hybrid Pool Geometry, ranking, and Listing Pool Gate semantics are unchanged.",
        "",
        f"Reference: Stand {REFERENCE_STAND}. Misses: {', '.join(MISS_STANDS)}.",
        "",
        "## F. Comparison vs Stand 677",
        "",
        "| Stand | Pool px size | FastSAM pool mask? | CLIP | Geometry | Parcel gate | Final OS result | Failure stage |",
        "| ----- | -----------: | ------------------ | ---: | -------- | ----------- | --------------- | ------------- |",
    ]
    for row in table:
        lines.append(
            f"| {row['stand']} | {row['pool_px_size']} | {row['fastsam_pool_mask']} | "
            f"{row['clip']} | {row['geometry']} | {row['parcel_gate']} | "
            f"{row['final_os_result']} | {row['failure_stage']} |"
        )
    lines += [
        "",
        "## H. Resolution / appearance hypotheses",
        "",
        json.dumps(hyp, indent=2),
        "",
        "## J. Why 677 is detected and these nine are not",
        "",
        payload.get("why_text") or "",
        "",
        "## K. Recommended next experiment (not implemented)",
        "",
        f"- id: `{rec['experiment_id']}`",
        f"- {rec['rationale']}",
        f"- success: {rec['success_criterion']}",
        f"- negative controls: {', '.join(rec['negative_controls'])}",
        "",
        "Do not implement K in this PR.",
        "",
        "## Panels",
        "",
    ]
    for row in payload.get("stands") or []:
        lines.append(f"- Stand {row['stand_number']}: `{row.get('panel_path')}` crop=`{row.get('crop_path')}`")
    return "\n".join(lines) + "\n"


def main() -> int:
    dataset = load_gis()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    clip_ok = fastsam_importable()
    fastsam_fn = None
    if clip_ok:
        from backend.vision.object_segmentation import fastsam_masks

        fastsam_fn = fastsam_masks
    rows = []
    for stand in ALL_STANDS:
        print(f"diagnosing {stand} fastsam={clip_ok}", flush=True)
        row = diagnose_stand(stand, dataset, OUT_DIR, fastsam_fn=fastsam_fn, clip_available=clip_ok)
        # drop bulky parcel geometry from JSON
        slim = dict(row)
        slim.pop("parcel", None)
        if slim.get("trace"):
            slim["trace"] = {
                k: slim["trace"][k]
                for k in (
                    "n_fastsam_masks",
                    "n_water_seeds",
                    "n_fastsam_at_pool",
                    "n_water_seeds_at_pool",
                    "failure_stage",
                    "final_select_pool",
                    "intersecting_visual_pool",
                    "traces",
                )
                if k in slim["trace"]
            }
        rows.append(slim)
        (OUT_DIR / f"{stand.replace('/', '_')}.json").write_text(
            json.dumps(slim, indent=2, default=str) + "\n", encoding="utf-8"
        )
    hyp = hypothesis_report(rows)
    rec = recommended_experiment(hyp)
    no_prop = hyp.get("fastsam_did_not_propose_n")
    why = (
        f"Stand 677 is OS CONFIRMED because FastSAM produced an in-parcel mask that CLIP scored as pool "
        f"(frozen CLIP 0.99, ~41x27 px). Of the nine documented misses, {no_prop} have no FastSAM mask "
        f"covering the visually identified pool, so OS v1 never saw a candidate (`no_pool_candidate`). "
        f"{hyp.get('fastsam_proposed_then_rejected_n')} had a proposal that downstream filters discarded. "
        f"Colour is not assumed to be the cause; this is measured proposal vs filter behaviour."
    )
    payload = {
        "production_ranking_modified": False,
        "os_v1_modified": False,
        "fastsam_config_modified": False,
        "native15_modified": False,
        "fastsam_available": clip_ok,
        "reference": REFERENCE_STAND,
        "misses": MISS_STANDS,
        "comparison_table": comparison_table(rows),
        "hypothesis": hyp,
        "recommended_experiment": rec,
        "why_text": why,
        "stands": [
            {k: row.get(k) for k in ("stand_number", "crop_path", "panel_path", "failure_stage", "crop_wh", "pool_px_size", "n_fastsam_at_pool")}
            for row in rows
        ],
        "panel_dir": str(OUT_DIR / "panels"),
    }
    (OUT_DIR / "latest.json").write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    report = _write_report(payload)
    (OUT_DIR / "report.md").write_text(report, encoding="utf-8")
    print(json.dumps(payload["comparison_table"], indent=2))
    print(json.dumps(hyp, indent=2))
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
