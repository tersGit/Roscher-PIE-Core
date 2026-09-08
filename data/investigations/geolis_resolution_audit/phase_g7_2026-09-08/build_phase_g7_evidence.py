#!/usr/bin/env python3
"""Build Phase G7 frozen PR27 A/B evidence without changing prior artifacts."""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from backend.gis.estate_ags_matching.pool_object_validation_v1 import validate_os_payload

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
G5 = ROOT / "data/investigations/geolis_resolution_audit/phase_g5_2026-09-08"
G6 = ROOT / "data/investigations/geolis_resolution_audit/phase_g6_2026-09-08"
OS = ROOT / "data/investigations/object_segmentation_v1/carlswald_north/json"
GIS = ROOT / "data/gis/carlswald_north_corrected_001.json"
G5_COMMIT = "bd46a6fda2b8879dd7b0f5247665551ebd33eaf3"
G6_COMMIT = "313ef89b89077902aed6526bdc65da4a06c2f9c8"
G3_COMMIT = "bc434935a6316acf0c333b15d0a8b0787cfb33fd"
G4H_COMMIT = "5dd93d99405806211bcf2e2c6cc9af2feefb6fa5"
DETECTOR_COMMIT = "6c53661e15d1bda968318cbac7cc244ed7497789"
PR27 = "9e5e727fa28749e90b95730084ec97cb98dfbddf"
PR27_DATE = "2026-08-18T08:55:03Z"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def is_ancestor(ancestor: str, descendant: str) -> bool:
    return subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=ROOT,
        check=False,
    ).returncode == 0


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def gis_map() -> dict[str, dict]:
    data = json.loads(GIS.read_text(encoding="utf-8"))
    return {str(p["stand_number"]): p for p in data["parcels"]}


def write_csv(path: Path, fieldnames: list[str], records: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    joined = rows(G5 / "PHASE_G5_JOINED_RESULTS.csv")
    resolved = [r for r in joined if r["outcome"] in {"TRUE_RECOVERY", "FALSE_POSITIVE"}]
    assert len(resolved) == 44
    excluded = [
        r
        for r in joined
        if r["transition"] == "ABSENT->PRESENT" and r["outcome"] in {"UNRESOLVED", "EXCLUDED"}
    ]
    assert {r["outcome"] for r in excluded} == {"UNRESOLVED", "EXCLUDED"}

    ab = []
    for r in resolved:
        ab.append(
            {
                "stand": r["stand"],
                "case": r["case"],
                "human_ground_truth": "POOL" if r["outcome"] == "TRUE_RECOVERY" else "NO_POOL",
                "native15_detector_result": r["native15_classification"],
                "native15_geometry": r["native15_geometry"],
                "pr27_validation_result": "NOT_RUNNABLE",
                "pr27_reason": (
                    "Required native15 PR27 inputs are absent: unclipped mask, independent "
                    "building/road masks, semantic scores, and cross-frame identity."
                ),
                "pr27_component_outputs": "",
                "diagnostic_panel": "",
                "evidence_source": "G5 joined result; strict no-counterfactual rule",
            }
        )
    write_csv(
        OUT / "PHASE_G7_PR27_AB.csv",
        [
            "stand",
            "case",
            "human_ground_truth",
            "native15_detector_result",
            "native15_geometry",
            "pr27_validation_result",
            "pr27_reason",
            "pr27_component_outputs",
            "diagnostic_panel",
            "evidence_source",
        ],
        ab,
    )

    controls = ["401", "338", "408", "420", "677", "365"]
    historical = []
    gm = gis_map()
    for stand in controls:
        path = OS / f"{stand}.json"
        if not path.is_file() or stand not in gm:
            historical.append(
                {
                    "stand": stand,
                    "historical_label": "KNOWN_POOL",
                    "runnable": "NO",
                    "pr27_result": "NOT_RUNNABLE",
                    "pr27_reason": "Missing stored OS JSON or GIS geometry",
                    "pr27_component_outputs": "",
                }
            )
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        val = validate_os_payload(payload, gis_geometry=gm[stand].get("geometry"))
        historical.append(
            {
                "stand": stand,
                "historical_label": "KNOWN_POOL",
                "runnable": "YES",
                "pr27_result": val.final_status,
                "pr27_reason": ";".join(val.reason_codes),
                "pr27_component_outputs": json.dumps(val.to_dict(), sort_keys=True),
            }
        )
    write_csv(
        OUT / "PHASE_G7_HISTORICAL_REGRESSION.csv",
        ["stand", "historical_label", "runnable", "pr27_result", "pr27_reason", "pr27_component_outputs"],
        historical,
    )

    metrics = {
        "phase": "G7",
        "scope": "44 resolved native15 additions only; transition-case metrics, not estate-wide",
        "counts": {
            "resolved_cases": 44,
            "true_recovery": 21,
            "false_positive": 23,
            "unresolved_separate": 1,
            "excluded_separate": 1,
            "pr27_runnable_transition_cases": 0,
            "pr27_not_runnable_transition_cases": 44,
            "historical_controls": len(historical),
            "historical_controls_runnable": sum(r["runnable"] == "YES" for r in historical),
            "historical_controls_retained": sum(r["pr27_result"] in {"CONFIRMED", "UNKNOWN"} for r in historical),
            "historical_controls_rejected": sum(r["pr27_result"] == "REJECTED" for r in historical),
            "historical_controls_not_runnable": sum(r["runnable"] != "YES" for r in historical),
        },
        "transition_metrics": {
            "before_precision": 21 / 44,
            "after_precision": None,
            "fp_rejected": None,
            "fp_retained": None,
            "tp_retained": None,
            "tp_wrongly_rejected": None,
            "fp_rejection_rate": None,
            "tp_retention_rate": None,
            "post_validation_precision": None,
            "absolute_fp_reduction": None,
            "percentage_fp_reduction": None,
            "true_pool_cost": None,
            "precision_improvement": None,
            "interpretation": "N/A: no valid native15 PR27 counterfactual is runnable from frozen inputs.",
        },
        "separate_cases": {
            "unresolved": [{"stand": r["stand"], "case": r["case"]} for r in excluded if r["outcome"] == "UNRESOLVED"],
            "excluded": [{"stand": r["stand"], "case": r["case"]} for r in excluded if r["outcome"] == "EXCLUDED"],
        },
        "verdict": "E",
        "recommendation": "4",
    }
    (OUT / "PHASE_G7_METRICS.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")

    source_paths = [
        G5 / "PHASE_G5_HUMAN_LOCKED.csv",
        G5 / "PHASE_G5_JOINED_RESULTS.csv",
        G5 / "PHASE_G5_METRICS.json",
        G6 / "PHASE_G6_REPORT.md",
        G6 / "PHASE_G6_PROVENANCE.json",
        G6 / "PHASE_G6_FP_ROOT_CAUSES.csv",
        G6 / "PHASE_G6_TP_FP_FEATURES.csv",
        G6 / "PHASE_G6_FEATURE_COMPARISON.csv",
        G6 / "PHASE_G6_PR27_DIAGNOSTIC.csv",
        G6 / "PHASE_G6_HISTORICAL_REGRESSION.md",
        G6 / "PHASE_G6_FREEZE_VERIFICATION.md",
        ROOT / "data/investigations/geolis_resolution_audit/phase_g3_2026-09-07/DETECTOR_FREEZE_MANIFEST_POST.json",
        ROOT / "backend/gis/estate_ags_matching/pool_object_validation_v1.py",
    ]
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "authoritative_commits": {
            "g5": G5_COMMIT,
            "g6": G6_COMMIT,
            "g4h": G4H_COMMIT,
            "g3": G3_COMMIT,
            "detector_freeze": DETECTOR_COMMIT,
            "pr27": PR27,
        },
        "pr27": {
            "url": "https://github.com/tersGit/Roscher-PIE-Core/pull/27",
            "source_ref": "cursor/pool-object-validation-v1-b313",
            "source_commit": PR27,
            "source_commit_date": PR27_DATE,
            "predates_g5_commit": is_ancestor(PR27, G5_COMMIT),
            "historical_source_hashes": {
                p: git("rev-parse", f"{PR27}:{p}") for p in [
                    "backend/gis/estate_ags_matching/pool_object_validation_v1.py",
                    "scripts/run_pool_object_validation_v1.py",
                ]
            },
        },
        "artifact_sha256": {str(p.relative_to(ROOT)): sha(p) for p in source_paths},
        "method": "Unchanged PR27 validate_os_payload applied only to stored labelled OS controls; no detector rerun, imagery fetch, threshold tuning, or prior-artifact mutation.",
    }
    (OUT / "PHASE_G7_PROVENANCE.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    report = f"""# PHASE G7 — Frozen Pool Object Validation v1 A/B

## Verdict

**Verdict E — no valid native15 PR27 A/B can be claimed from the frozen transition inputs.**

**Recommendation 4 — retain the frozen evidence and do not design or apply a fix in G7.**

## Scope and method

This is a transition-case audit, not an estate-wide metric. It uses exactly 44 resolved native15 additions: 21 `TRUE_RECOVERY` and 23 `FALSE_POSITIVE`. The one unresolved and one excluded addition are listed separately and are not scored. PR27 is the exact historical implementation from commit `{PR27}` (`{PR27_DATE}`), before G5 ground truth. The source and artifact hashes are in `PHASE_G7_PROVENANCE.json`.

The native15 transition rows do not contain PR27's required unclipped mask, independent building/road masks, semantic scores, or cross-frame identity. Therefore every transition row is recorded as `NOT_RUNNABLE`; no PR27 retain/reject result is fabricated. The unchanged validator is applied to labelled historical controls 401, 338, 408, 420, 677, and 365 using their stored OS JSON and GIS geometry.

## Transition-case results

Before validation precision is **21/44 = 0.4772727**, as frozen by G5. After-validation precision, FP rejection/retention, TP retention/rejection, FP reduction, true-pool cost, and precision improvement are **N/A** because 0/44 native15 cases are runnable under the strict evidence rule. These are not estate-wide metrics.

No FP is claimed as PR27-retained and no true recovery is claimed as PR27-rejected; consequently no transition diagnostic panel is applicable. Existing evidence is referenced only; prior evidence is unchanged.

## Historical controls

`PHASE_G7_HISTORICAL_REGRESSION.csv` records retained, rejected, not-runnable, reason codes, and the complete available PR27 component output for each control. These controls are regression evidence, not current live ground truth and are not combined with the 44-case transition metrics.

## Required preservation answers

- PR27 exact source: `{PR27}` on `cursor/pool-object-validation-v1-b313`; PR #27 is open and predates G5.
- Detector/configuration/thresholds/scoring/ranking/Shape v2/imagery/inventory/prior evidence: not modified.
- Imagery fetch, detector rerun, training, tuning, parameter search, and stand-specific exceptions: not performed.
- A/B conclusion: the frozen native15 transition sample cannot establish PR27 performance without the missing PR27 inputs.
"""
    (OUT / "PHASE_G7_REPORT.md").write_text(report, encoding="utf-8")
    (OUT / "PHASE_G7_FAILURES.csv").write_text(
        "failure_class,count,scope,reason\n"
        "transition_not_runnable,44,native15_additions,missing_pr27_inputs\n"
        "unresolved_separate,1,g5_additions,excluded_from_scoring\n"
        "excluded_separate,1,g5_additions,excluded_from_scoring\n",
        encoding="utf-8",
    )
    (OUT / "PHASE_G7_FREEZE_VERIFICATION.md").write_text(
        "# PHASE G7 freeze verification\n\n"
        "Authoritative commit and source/artifact hashes are recorded in `PHASE_G7_PROVENANCE.json`. "
        "Prior G3/G4H/G5/G6 evidence is read-only input. No imagery was fetched and no detector, "
        "configuration, threshold, scoring, ranking, Shape v2, imagery, inventory, or prior evidence was modified.\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
