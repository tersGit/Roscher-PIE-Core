# W4 Funnel v1 Retrieval Efficiency Forensic Audit

## Scope and provenance

This is a diagnostic-only audit of frozen Property24 `117571900`. It does not
change scores, ranks, thresholds, Funnel v1, the W1 universe, or production
code; it does not fetch imagery, attach identities, inspect historical
predictions, or establish ground truth. The recovered W1 native15 cache was
read-only. Exact source commits and SHA-256 values are in `provenance.json`.
The frozen input has 1,010 W1 parcels, listing area 1,251 m2, and a stated
pool, 28-panel installation, three garages, and greenbelt/dam adjacency.

The frozen result queued 896/1,010 parcels: all 428 T1 (within +/-10%) plus all
468 T2 (over +/-10% through +/-20%). T2 was added because 356/428 T1 parcels
were `UNKNOWN` for pool, triggering `high_unknown_pool_observability`.

## 1. Area distribution

`area_band_distribution.csv` and `area_histogram_100m2.csv` are raw,
reproducible distributions. Counts are inclusive at the stated boundaries.

| Area band around 1,251 m2 | Lower m2 | Upper m2 | Count | Universe % |
| --- | ---: | ---: | ---: | ---: |
| Exact | 1,251.000 | 1,251.000 | 3 | 0.297 |
| +/-2.5% | 1,219.725 | 1,282.275 | 93 | 9.208 |
| +/-5% | 1,188.450 | 1,313.550 | 270 | 26.733 |
| +/-7.5% | 1,157.175 | 1,344.825 | 323 | 31.980 |
| +/-10% | 1,125.900 | 1,376.100 | 428 | 42.376 |
| +/-12.5% | 1,094.625 | 1,407.375 | 648 | 64.158 |
| +/-15% | 1,063.350 | 1,438.650 | 696 | 68.911 |
| +/-20% | 1,000.800 | 1,501.200 | 896 | 88.713 |

The dense 1,000-1,500 m2 estate distribution explains why even a weak
size-priority band is broad. This evidence does **not** support a size hard
gate: all outer candidates remain recoverable and the audit reports work
ordering only.

## 2. Pool observability

Funnel v1 creates `OBSERVED_NO_POOL` only when `observable=true`,
`pool_detected=false`, and `clear_absence=true`. An unobservable crop is
`UNKNOWN`; a detection that is not parcel-bound is also `UNKNOWN`; and an
observable crop with no detector hit but no clear-absence claim remains
`UNKNOWN`. In frozen W4, `clear_absence` was always false, so T1 has 72
`OBSERVED_POOL`, zero `OBSERVED_NO_POOL`, and 356 `UNKNOWN`. The detector's
open-space condition was brightness coverage >=0.60 inside the parcel mask;
vegetation, roof shadow, dark water, obscured gardens, and crop framing can
prevent it. Non-detection is therefore insufficient to assert no pool.

Before crop inspection, the script selected 20 T1 `UNKNOWN` and 20 T1
`OBSERVED_POOL` samples by descending frozen score, ascending frozen rank, then
SHA-256 of a fixed candidate salt. Selection uses neither imagery nor identity.
`pool_blinded_sample_contact_sheet.jpg` is numbered without IDs; the selection
and review rows with crop hashes are retained in the two pool CSV files.

| T1 UNKNOWN visual outcome | Count | % of 20 |
| --- | ---: | ---: |
| A: genuinely not assessable | 1 | 5 |
| B: garden visible; no pool apparent | 7 | 35 |
| C: detector missed apparent pool | 8 | 40 |
| D: ambiguous | 4 | 20 |

This is a blinded, descriptive visual audit, not ground truth. Category B is
not `OBSERVED_NO_POOL`, and category C is not a performance estimate because
the finite, score-ordered sample is not random. The 40 `OBSERVED_POOL` and
`UNKNOWN` rows are retained so every review decision is auditable.

## 3. Solar diagnostic (T1/T2 only)

`solar_classes.csv` includes all T1/T2 rows (896 total): 896
`SOLAR_UNKNOWN`, 0 `SOLAR_OBSERVED_STRONG`, 0 `SOLAR_OBSERVED_SOME`, and 0
`SOLAR_NONE`. The source method computed parcel-bound dark-roof visibility
only; it deliberately made no panel detection or negative assertion because
native15's 0.15 m/px imagery, roof obliquity, shade, compression, and panel/
roof confounding do not validate a parcel-bound panel-count detector.

A typical panel's short dimension would span roughly seven native15 pixels, so
a 28-panel installation can be theoretically visible when unobscured. The
frozen listing aerial evidence says roof panels appear but exact count and
configuration are visually partial; without an identity attachment there is no
per-candidate test of the stated installation. Thus the required 28-panel
visibility test is **inconclusive**, and no candidate is promoted. `NONE` is
never treated as a contradiction: imagery can pre-date an installation.

The complete read-only audit took the measured duration in `provenance.json`
on 16 logical CPUs; its `timing_seconds` separates the boundary proxy from the
solar/driveway pass. These are CPU/OpenCV proxy timings, not model inference
costs. No vision model or trained solar detector was run.

## 4. Greenbelt/open-boundary diagnostic

`boundary_classes.csv` uses the W1 parcel mask and frozen crop only. It measures
vegetation in a 35-pixel exterior ring and a 19-pixel parcel boundary ring:
both high is `OPEN_BOUNDARY_LIKELY`, both low is `INTERNAL_RESIDENTIAL`, and
the remainder is `AMBIGUOUS`. It does not infer a dam, target identity, or
ownership. Counts:

| Area band | Candidates | Open likely | Internal residential | Ambiguous |
| --- | ---: | ---: | ---: | ---: |
| +/-2.5% | 93 | 0 | 91 | 2 |
| +/-5% | 270 | 0 | 266 | 4 |
| +/-7.5% | 323 | 0 | 317 | 6 |
| +/-10% | 428 | 0 | 420 | 8 |
| +/-20% | 896 | 0 | 886 | 10 |

This unvalidated proxy finds no positive open-boundary candidates. It is
structural context only and must not become a permanent filter without an
independent calibration set.

## 5. Driveway/garage cheap evidence

`driveway_garage_classes.csv` records 228 `BROAD_FRONTAGE`, 782 `UNKNOWN`,
and zero defensible `3+_GARAGE` or `1-2_GARAGE` labels across W1. Broad
frontage is only a parcel-bound bright, low-saturation hardscape fraction
>=0.24; it is not a garage count. Crop orientation and roof imagery cannot
reliably distinguish garage bays, so no overclaim is made.

## 6. Counterfactual workload calculations

`counterfactual_workloads.csv` provides every stage. The transparent retention
rule is uniform: a cheap stage may permanently remove only an observed,
explicitly incompatible class; it retains every `UNKNOWN` plus compatible or
positive classes. Pool retains `OBSERVED_POOL`/`UNKNOWN` and would remove only
`OBSERVED_NO_POOL`; solar retains all classes because solar `NONE` is
time-unsafe; boundary retains `OPEN_BOUNDARY_LIKELY`/`AMBIGUOUS` and removes
`INTERNAL_RESIDENTIAL`. These are diagnostic processing-order calculations,
not recall estimates or proposed permanent filters. The +/-10 fallback in B/E
is a priority expansion, not a filter.

| Strategy | Final expensive building/fine count | Reduction from 1,010 | Key stage result |
| --- | ---: | ---: | --- |
| A: +/-10 -> pool | 428 | 57.624% | 356 unknown pool survivors |
| B: +/-5 priority -> pool -> +/-10 fallback | 428 | 57.624% | 270 immediate; 225 pool-unknown; fallback restores 428 |
| C: +/-10 -> boundary -> pool | 8 | 99.208% | 8 boundary-ambiguous survivors |
| D: +/-10 -> pool -> solar -> boundary | 8 | 99.208% | solar preserves all; boundary leaves 8 |
| E: +/-5 -> pool -> boundary -> solar -> +/-10 fallback | 428 | 57.624% | 4 immediate after boundary; fallback restores 428 |

The 8-candidate boundary outcomes are an unvalidated proxy result and are
unsafe as a recommendation. The defensible work-order reduction is therefore
from the frozen 896 queue to an initial +/-5 priority queue of 270: **626
fewer immediate expensive candidates, a 69.866% reduction versus frozen
work**. Its recoverable +/-10 fallback is 428, still 468 fewer than frozen
(52.232%).

## 7. Expansion logic conceptual audit

The current rule expands T2 as soon as T1 pool unknown fraction reaches 0.5;
in W4 it was 83.178% (356/428), producing the 896 queue before other cheap
evidence can be considered. Because unknown is intentionally neutral and the
pool sample contains visually apparent misses and ambiguity, high unknown
alone expands too early as a **processing-order** decision. It is better to
defer T2 expansion until cheap building/roof observability, solar
observability when validated, and structural open-boundary evidence have been
exhausted. This is conceptual only: neither rule nor expansion behavior was
implemented or changed.

## 8. Ten verdict bullets

1. +/-10% is broad: 428 parcels (42.376%) are T1.
2. +/-5% improves immediate workload to 270 parcels (26.733%).
3. Zero exact matches are not grounds to reject area evidence: there are three.
4. Visible absence is not safe here: no frozen W4 candidate has
   `OBSERVED_NO_POOL`, and visual non-appearance remains non-negative.
5. Solar has no current safe filtering utility; the 28-panel observation is
   inconclusive at parcel level.
6. Boundary has possible future utility but its current proxy has no positive
   +/-10 candidate and is unvalidated.
7. Garage evidence has no reliable early filtering utility; only broad frontage
   is observable without claiming bay counts.
8. High pool unknown alone expands T2 too early for work ordering.
9. Best revised diagnostic order: +/-5 priority -> pool -> validated cheap
   structural/roof/solar evidence -> recoverable +/-10 fallback -> T2/T3.
10. Recommended safe reduction is 626 immediate candidates (69.866%) versus
    frozen 896, with a recoverable +/-10 queue of 428 (52.232% reduction).

**VERDICT: REVISE FUNNEL ORDER.** Observability semantics are correctly
conservative; the evidence does not justify revising them.
