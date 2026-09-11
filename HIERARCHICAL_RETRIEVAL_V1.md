# PIE Hierarchical Candidate Retrieval Funnel V1

## Status and scope

This is an experimental, standalone retrieval-ordering module at
`backend/retrieval_funnel/`. It is not wired into frozen artifacts, production
Scoring v2, ranking, or detectors. It establishes the order in which candidates
may receive progressively expensive visual processing; it does not identify a
stand, assert ground truth, or dominate final compatibility.

## Area tiering

When the listing land size is reliable and a positive cadastral area is
available, the module retains the listing area, cadastral area, absolute
difference, percent difference, and tier for every candidate:

| Tier | Inclusive difference |
| --- | --- |
| T1 | <=10% |
| T2 | >10% and <=20% |
| T3 | >20% |

Missing or unreliable listing area starts the complete universe in `NORMAL`;
there is no area gate. T1 is processed first. T2 automatically joins the
expensive queue for insufficient T1 support, high pool-observation unknowns,
no T1 pool-compatible observation, or low evidence coverage. T3 is always
retained by the documented `recover_tier3()` expansion path.

## Observation and compatibility

Pool observation has exactly three states:

| State | Meaning |
| --- | --- |
| `OBSERVED_POOL` | Pool is visible and bound to the candidate parcel. |
| `OBSERVED_NO_POOL` | Parcel is clearly observable and has no pool. |
| `UNKNOWN` | Vegetation, shadow, inadequate/ambiguous imagery, weak detection, binding uncertainty, or no visibility. |

A detector miss is `UNKNOWN`, never `OBSERVED_NO_POOL`. A detected neighbour
pool without parcel binding is also `UNKNOWN`. Listing pool yes gives a
positive retrieval priority to `OBSERVED_POOL` and deprioritizes observed
absence; listing pool no reverses that treatment; listing pool unknown gates
nothing. Unknown is retained in every case.

Pool is followed by independent building, roof, and house-pool evidence, then
solar, driveway/garage, open-space, and neighbour context. Each uses
`MATCH`, `PARTIAL`, `CONFLICT`, or `UNKNOWN`. Unknown is neutral, never a
conflict. Geometry is only eligible when observed and parcel-bound; unavailable
geometry is not a mismatch.

## Separation and instrumentation

Retrieval priority is separate from final compatibility. Stand size contributes
at most `0.05` to the experimental final compatibility (and `0.0` for T3 or
normal-area candidates), while observed visual evidence remains the primary
term. `FunnelResult` exposes stage counts, fallback reasons, evidence coverage,
expensive queue size, and estimated reduction in expensive work. `VLMReranker`
is an optional interface and is intentionally not implemented or invoked.

Expected empirical recording for every run: universe/T1/T2/T3 counts, each
fallback reason, pool-state distribution, expensive queue count, elapsed
runtime by stage supplied by the caller, and reduction against processing the
full universe.
