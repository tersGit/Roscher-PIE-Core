# PIE Hierarchical Retrieval Funnel v1.1

## Status and scope

This is an experimental revision to retrieval **order only**, implemented in
`backend/retrieval_funnel/hierarchical_v1_1.py`. It is separate from Funnel v1
and is not wired to production Scoring v2, production ranking, detectors, VLM
logic, frozen W1/W4 evidence, or prior scores and ranks. It performs no
identity, ground-truth, or imagery work.

The safe evidence sequence for every processed priority is: area priority,
pool observability/presence, pool geometry only for an observed parcel-bound
pool, building/roof, house-pool relationship only when observed, existing safe
secondary evidence, then coverage/compatibility assessment. Pool semantics are
unchanged: `OBSERVED_POOL`, `OBSERVED_NO_POOL`, and `UNKNOWN` retain their v1
meanings. A detector non-detection remains `UNKNOWN` unless the existing
explicit clear-absence process establishes absence. Unknown candidates survive.

## Priority groups

For a reliable positive listing area and positive cadastral area:

| Priority | Difference from listing area | Processing role |
| --- | --- | --- |
| A | <=5% | Immediate safe-evidence work |
| B | >5% and <=10% | First recoverable expansion |
| C | >10% and <=20% | Second recoverable expansion |
| D | >20% | Final recoverable expansion |

Missing or unreliable area assigns every candidate `NORMAL`; the full universe
is processed and remains recoverable, following v1. Area controls work order
only. It does not determine identity, final compatibility, or permanent
elimination.

## Pre-registered expansion assessment

After A, then after combined A+B, then after combined A+B+C when reached, the
same deterministic assessment runs. Expansion is required when one or more of
these evidence-only triggers is true:

| Trigger | Exact threshold |
| --- | --- |
| `NO_ADEQUATE_CANDIDATES` | No candidate has compatibility >=0.60. |
| `LOW_TOP_CANDIDATE_COVERAGE` | Highest-compatible serious candidate has coverage <0.35. |
| `NON_UNIQUE_TOP_SET` | More than 3 serious candidates are within 0.05 compatibility of the top serious candidate. |
| `MATERIAL_VISIBLE_CONFLICTS` | The top serious candidate has more than 0 visible conflicts. |
| `INSUFFICIENT_COMBINED_SUPPORT` | Top serious candidate has fewer than 3 observable supporting components, or the mean of its compatibility, coverage, and normalized supporting-component count (count/8, capped at 1) is <0.60. |

“Serious” means compatibility >=0.60. A sufficient result may be a Top-N
serious candidate set; a unique winner is not required. `HIGH_POOL_UNKNOWN_RATE`
is deliberately not a trigger and cannot itself cause expansion.

Every expansion record is machine-readable and contains `expanded`, `from`,
`to`, and triggers. A processed-ID ledger prevents reprocessing A when B/C/D
is added. D is reached only after earlier insufficiency and is recoverable even
when not processed.

## Instrumentation

Each actually processed priority records its candidate count, observed-pool
count, unknown-pool count, observable-building count, average coverage, and
serious-candidate count. The result separately records
`IMMEDIATE_EXPENSIVE_WORKLOAD` (A only) and `TOTAL_EXPENSIVE_WORKLOAD`
(all priorities reached), so deferred work cannot be reported as immediate
work.

The frozen W4 counterfactual fixture and validation are under
`data/experiments/hierarchical_retrieval_funnel_v1_1/`. They report workload
only, with no recall, ranking, accuracy, or identity claim.
