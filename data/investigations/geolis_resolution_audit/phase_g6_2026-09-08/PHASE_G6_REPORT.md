# PHASE G6 — NATIVE15 false-positive forensics

## Verdict

**Verdict D — multiple diagnostic experiments.** The 23 false positives and 21 true recoveries are measurable as a transition sample, but the committed evidence does not support one general hardening mechanism or adoption of native15. **Recommendation: G7 should be frozen to PR27 A/B only.** No detector change is recommended from this audit; any diagnostic experiments must remain outside the frozen detector work.

## Scope and preservation

The primary set is all 23 G5 `FALSE_POSITIVE` native15 additions; the control set is all 21 `TRUE_RECOVERY` additions. G5 reported 23/44 FP and 21/44 TP. The two unresolved/excluded additions and two removals are outside this resolved forensic set. The committed G4H first-pass panels (`phase_g4h_2026-09-07/first_pass_panels/case_*.jpg`) were inspected with their parcel/boundary and contour context. Existing object-segmentation JSON and G3 native15 results were compared. No imagery was fetched and no detector was rerun.

## Physical identity and causes

All 23 FPs are recorded as **UNKNOWN**, not because they are presumed water, roof, paving, shadow, vegetation, neighbour leakage, or another object, but because the committed panels and stored diagnostics do not independently establish physical identity. Water colour alone was never used. The allowed cause vocabulary is enforced in `PHASE_G6_FP_ROOT_CAUSES.csv`; `UNKNOWN` is the only defensible label for these records. Dominant cause is therefore **undetermined**, not a claimed visual mode. Boundary leakage, roof/building confusion, small/irregular recovery patterns, and segmentation/object versus semantic weakness cannot be separated for these 23 from committed values.

## Existing diagnostics

All 44 additions have native15 relative parcel area, compactness, convexity/solidity proxy, rectangularity, aspect ratio, normalized perimeter, contour point count, curvature/angle entropy, and distance to the extracted building centroid. TP/FP ranges overlap for every emitted geometry feature; medians are reported without threshold selection in `PHASE_G6_FEATURE_COMPARISON.csv`. Native15 area is small in both groups (TP median 0.0026; FP median 0.0025), so area does not distinguish them. Building-mask overlap, parcel-boundary distance/intersection, neighbour relationship, FastSAM/semantic score, CLIP pool score, competing-object scores, and candidate rank are missing for all 44. Missingness is reported, not imputed.

The strongest existing evidence is therefore the combination of parcel membership and contour geometry as a review aid, not a classifier. Geometry is not enough: true recoveries include irregular, elongated, rectangular, and kidney/curved objects, while FPs include the same families. The sample supports a mixed unobserved weakness (object identity / masking / semantic context), not attribution to one layer.

## PR27 diagnostic

PR27's historical design was reviewed but not enabled. Its required discriminators—unclipped-mask containment, independent building overlap, neighbour risk, semantic evidence, and cross-frame identity—are not emitted in this G5 native15 transition record. The stored legacy object status is shown only as an audit aid in `PHASE_G6_PR27_DIAGNOSTIC.csv`; it is not a valid replay. Determinable unchanged-PR27 counterfactuals: **0/23 FPs**, and **0/21 TPs wrongly rejected**, because required inputs are absent; all 44 remain unresolved under a strict evidence rule. Historical pools 401, 338, 408, 420, 677, and 365 remain regression controls, with the limitations documented in `PHASE_G6_HISTORICAL_REGRESSION.md`.

## Required answers

- Physical identity of 23 FPs: not established; all 23 are `UNKNOWN`.
- Dominant causes: no defensible dominant cause; unsupported labels are not substituted.
- Distinguishability: no reliable separation from committed diagnostics.
- Strongest features: parcel-context review plus geometry as descriptive evidence; no standalone geometry feature separates TP/FP.
- Boundary leakage and roof/building confusion: not measurable because boundary intersection and building-mask overlap are absent.
- Small/irregular pattern: both groups contain small, irregular, elongated, rectangular, and curved objects.
- Weakness layer: mixed/unknown; missing semantic and object-context diagnostics prevent attribution.
- PR27 performance and recovery preservation: no valid counterfactual; no rejection or preservation rate is claimed.
- Endangered historical pools: 338/408 are specifically sensitive to roof/boundary identity; 420/677 demonstrate that irregular and genuine pools must not be hard-rejected; 401/365 remain controls.
- One general hardening mechanism: **not supported**.

## Recommendation

G7 should be **frozen PR27 A/B only**. If a later phase is authorized, diagnostic-only work could obtain/emit independent building overlap and parcel-boundary intersection, object identity/semantic scores, and neighbour/context evidence, then evaluate those diagnostics against the same 23/21 cases and historical controls. Do not tune thresholds, optimize, grid-search, train, fetch imagery, adopt native15, or create stand-specific rules from this audit.

See the companion CSVs for row-complete features, missingness, root-cause labels, and PR27 diagnostic status. Existing panels are referenced rather than copied or altered.
