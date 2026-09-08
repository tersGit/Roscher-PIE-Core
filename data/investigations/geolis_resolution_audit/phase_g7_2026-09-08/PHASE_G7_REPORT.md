# PHASE G7 — Frozen Pool Object Validation v1 A/B

## Verdict

**Verdict E — no valid native15 PR27 A/B can be claimed from the frozen transition inputs.**

**Recommendation 4 — retain the frozen evidence and do not design or apply a fix in G7.**

## Scope and method

This is a transition-case audit, not an estate-wide metric. It uses exactly 44 resolved native15 additions: 21 `TRUE_RECOVERY` and 23 `FALSE_POSITIVE`. The one unresolved and one excluded addition are listed separately and are not scored. PR27 is the exact historical implementation from commit `9e5e727fa28749e90b95730084ec97cb98dfbddf` (`2026-08-18T08:55:03Z`), before G5 ground truth. The source and artifact hashes are in `PHASE_G7_PROVENANCE.json`.

The native15 transition rows do not contain PR27's required unclipped mask, independent building/road masks, semantic scores, or cross-frame identity. Therefore every transition row is recorded as `NOT_RUNNABLE`; no PR27 retain/reject result is fabricated. The unchanged validator is applied to labelled historical controls 401, 338, 408, 420, 677, and 365 using their stored OS JSON and GIS geometry.

## Transition-case results

Before validation precision is **21/44 = 0.4772727**, as frozen by G5. After-validation precision, FP rejection/retention, TP retention/rejection, FP reduction, true-pool cost, and precision improvement are **N/A** because 0/44 native15 cases are runnable under the strict evidence rule. These are not estate-wide metrics.

No FP is claimed as PR27-retained and no true recovery is claimed as PR27-rejected; consequently no transition diagnostic panel is applicable. Existing evidence is referenced only; prior evidence is unchanged.

## Historical controls

`PHASE_G7_HISTORICAL_REGRESSION.csv` records retained, rejected, not-runnable, reason codes, and the complete available PR27 component output for each control. These controls are regression evidence, not current live ground truth and are not combined with the 44-case transition metrics.

## Required preservation answers

- PR27 exact source: `9e5e727fa28749e90b95730084ec97cb98dfbddf` on `cursor/pool-object-validation-v1-b313`; PR #27 is open and predates G5.
- Detector/configuration/thresholds/scoring/ranking/Shape v2/imagery/inventory/prior evidence: not modified.
- Imagery fetch, detector rerun, training, tuning, parameter search, and stand-specific exceptions: not performed.
- A/B conclusion: the frozen native15 transition sample cannot establish PR27 performance without the missing PR27 inputs.
