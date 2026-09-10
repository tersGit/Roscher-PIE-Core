# Waterfall W2 final closure and evaluation-terminology correction

**Closure date:** 2026-09-10
**Applies to reveal commit:** `36a7e6aa3ccec0c02363991fa0e1f2dd6881ca02`
**Purpose:** Correct final evaluation terminology only. This addendum does not alter
the ground-truth recovery evidence, the official PIE W2 freeze, the Qwen evidence
freeze, or any ranking or result.

## Ground-truth status

**W2 STATUS = UNLABELLED — GROUND TRUTH UNAVAILABLE.**

The public-source recovery recorded in
[GROUND_TRUTH_REVEAL_REPORT.md](GROUND_TRUTH_REVEAL_REPORT.md) did not recover a
parcel-level ground truth. It is unknown whether the true property was in or out of
the frozen PIE Top 10, and it is unknown whether the true property was among the
Qwen-evaluated candidates.

## Frozen outputs and evaluation status

| Output | Frozen result | Evaluation status |
| --- | --- | --- |
| Official PIE W2 prediction | Stand 972, Ext 19, rank #1, score .7878 | Accuracy **UNLABELLED**; this result is neither HIT nor MISS. |
| Qwen32B diagnostic | Evaluated the frozen PIE Top 10; frozen #1 Stand 897, Ext 19, score .850 | Accuracy **UNLABELLED**. |

Qwen32B evaluated the frozen PIE Top-10, but ground truth is unavailable, so VLM
accuracy cannot be scored.

The official PIE W2 freeze remains unchanged. The Qwen evidence freeze remains
`2b4b65d`, and its external result SHA256 remains
`1c3bf26c647a99ab9b1353b62ff7510c27989f9b85058f29d16c35f96129a1d3`.

## Final verdict

BLIND PIPELINE EXECUTION = PASS
GROUND-TRUTH RECOVERY = INCONCLUSIVE
ACCURACY EVALUATION = UNLABELLED
