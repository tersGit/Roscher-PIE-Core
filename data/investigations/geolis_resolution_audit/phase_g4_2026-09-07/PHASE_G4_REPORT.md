# Phase G4: Independent validation of changed detections

## Verdicts and decision

**Detection quality verdict: INCONCLUSIVE. Geometry quality verdict: INCONCLUSIVE. Decision: E — do not adopt.**

All 48 changed-detection cases and all 64 material geometry cases have blinded
first-pass panels. No independent physical pool/contour evidence was available
to resolve them without fabricating a visual conclusion, so every primary
transition is `UNRESOLVED` and every material geometry case is `AMBIGUOUS`.
Rates and confidence intervals are null because the independently resolved
denominator is zero.

## Required answers

1. G3 artifacts are frozen by SHA-256 in `FREEZE_VERIFICATION_PRE.json`.
2. All 46 additions and 2 removals are included in `PHASE_G4_TRANSITION_VALIDATION.csv`.
3. Every first-pass panel asks exactly: `Is there a swimming pool inside this parcel?`
4. First-pass panels expose only IMAGE A / IMAGE B and a parcel boundary.
5. Initial answers are exclusively permitted values and are `UNCERTAIN` where ungrounded.
6. No detector was rerun.
7. Evidence sources and independence are in `evidence_manifest.json`.
8. Blue colour is never treated as pool evidence.
9. Additions: 46 `UNRESOLVED`; no recovery/false-positive rates are computable.
10. Removals: 2 `UNRESOLVED`; no loss/removal rate is computable.
11. All 64 material geometry cases are in `PHASE_G4_GEOMETRY_VALIDATION.csv`.
12. All geometry judgments are `AMBIGUOUS`; root cause is conservatively `other`.
13. Explicit unweighted records for 408, 420, 677, and 365 are in `PHASE_G4_DECISION_METRICS.json`; 408 and 365 remain ambiguous material cases, while 420 and 677 are minor and therefore outside the material review set.
14. No claim equates current live AGS with August imagery.
15. Decision E is based only on the zero independently resolved cases; no detector behavior is adopted.
