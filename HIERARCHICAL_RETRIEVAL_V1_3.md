# PIE Hierarchical Retrieval Funnel v1.3

## Scope and isolation

This experimental entry gate is isolated in
`backend/retrieval_funnel/hierarchical_v1_3.py`. It selects only the
cadastral candidate work universe. It does not change production scoring,
candidate visual work, pool logic, evidence/recovery lanes, geometry logic,
visual weights, detectors, or any v1/v1.1/v1.2 behavior. Frozen W4/W5 files
are not modified.

## Listing-area confidence classifier

The classifier is deterministic and conservative:

| Confidence | Rule |
| --- | --- |
| `HIGH_CONFIDENCE` | An explicit numeric `Erf Size` or `Land Size`; specific, unqualified structured metadata in `m2`; or the same specific exact figure repeated consistently at least twice. |
| `MEDIUM` | A rounded marketing figure, an unqualified marketing figure, or explicit conflicting figures. Conflicts never enable the gate. |
| `LOW` | An approximate or qualified figure, including `about` or `approximate`. |
| `UNKNOWN` | Missing, invalid, or inferred area. |

Any conflict, approximation, rounding, inferred value, non-positive value, or
missing value prevents hard gating. Only `HIGH_CONFIDENCE` enables it.

## High-confidence stand-size gate

For a high-confidence listing area, the inclusive ordinary universe is
`+/-10%`: Priority A is `<=5%`; Priority B is `>5%` through `<=10%`.
Candidates over 10% are excluded from the ordinary visual queue but remain
recorded in Exceptional Rescue. Rescue C is `>10%` through `<=15%`; Rescue D
is `>15%`.

Rescue C may activate only after ordinary processing fails with one or more of:
`NO_CREDIBLE_CANDIDATES`, `ALL_TOP_CANDIDATES_VISIBLE_CONFLICT`,
`LISTING_AREA_CONFIDENCE_DOWNGRADED`, `EVIDENCE_SUGGESTS_LISTING_AREA_ERROR`,
or `CADASTRAL_AREA_DATA_QUALITY_WARNING`. Rescue D may activate only when C
was activated and C then fails an eligible criterion. High unknown visual rate
is never a rescue trigger. Rescue activation, reason, and levels are
instrumented; no remainder is automatically processed.

When confidence is not high, the gate is disabled and every candidate remains
in the normal recoverable universe, preserving v1.2 entry behavior.

## Frozen workload regression

`data/experiments/hierarchical_retrieval_funnel_v1_3/frozen_workload_regression.json`
is a read-only calculation over the frozen W1 parcel GeoJSON and frozen
listing facts. It has no candidate scoring or visual work and makes no recall,
identity, or accuracy claim. It records the source commit and SHA-256
provenance alongside machine-readable counts.
