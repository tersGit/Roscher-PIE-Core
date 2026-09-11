# PIE Hierarchical Retrieval Funnel v1.2

## Status and isolation

This is a preregistered experimental work-order design, isolated in
`backend/retrieval_funnel/hierarchical_v1_2.py`. It does not alter Funnel v1,
v1.1, production scoring/ranking, area bands, detectors, W1 imagery, or frozen
W5 scores, ranks, and artifacts. It performs no identity, ground-truth, solar,
greenbelt, garage-count, pool-absence, or VLM work.

Area bands remain the v1.1 ordering bands. On entry to every band, candidates
are dynamically routed into an Evidence Lane or Recovery Lane. Both lanes
remain recoverable; neither is an elimination or identity decision.

## Deterministic lane rules

| Lane | Entry condition | Work |
| --- | --- | --- |
| Evidence | At least one observable, parcel-bound target discriminator is `STRONG_MATCH`. | Deep review, then expensive fine work. |
| Recovery | Important discriminator is `UNKNOWN` or insufficient, including ordinary `MATCH` or `PARTIAL`. | Cheap, high-coverage building/roof geometry pass; stored for later recovery. |

`OBSERVED_POOL` is not itself compatible. An observed pool enters Evidence only
when its parcel-bound geometry comparison is `STRONG_MATCH`. Pool comparison
uses existing observable rectangularity, aspect, size, orientation,
circular/oval form, adjacent feature, pool-house/patio relation, and parcel
position where available. The only allowed outputs are `STRONG_MATCH`,
`MATCH`, `PARTIAL`, `VISIBLE_CONFLICT`, and `UNKNOWN`. Missing source detail is
`UNKNOWN`, never conflict.

The recovery pass may promote a candidate only for a `STRONG_MATCH`
parcel-bound target-compatible building/roof geometry. An Evidence candidate is
demoted to Recovery only for a directly visible material building conflict.
Generic building existence and generic observability are not discriminators and
cannot provide strength. Unknown building evidence is neutral and recoverable.

## Generic evidence-strength and distinctiveness

For each candidate, the separate diagnostic metric records:

| Component | Rule |
| --- | --- |
| Observable discriminating components | Count parcel-bound `STRONG_MATCH` pool and building/roof components. |
| Compatibility | `STRONG_MATCH` contributes strength; `MATCH` and `PARTIAL` do not enter the Evidence Lane. |
| Distinctiveness | Sum preregistered distinctiveness components of strong observations. |
| Coverage | Recorded through the cheap recovery pass; it does not convert unknown to conflict. |
| Visible conflict | Count directly visible `VISIBLE_CONFLICT` observations. |

Distinctiveness is calculated only within the current area-band population and
does not use identity. A common rectangular pool is weak. A combination of
independent forms, a spa/rare adjacent relation, or a rare
pool-to-building/roof-footprint relation can contribute one or more
distinctiveness components. Exact component values must be recorded before
looking outside the current band. This policy is generic and not fitted to W5.

## Sequencing, expansion, and stopping

Within a band: (1) assess Evidence Lane deeply, (2) run Recovery Lane's cheap
building/roof pass, (3) promote/demote, then (4) perform expensive fine work
only on Evidence plus promotions. No next-band expansion occurs before both
steps complete. Recovery candidates remain stored after stopping and later
bands remain recoverable.

Only these preregistered triggers permit expansion:

* `NO_STRONG_EVIDENCE_LANE`
* `EVIDENCE_LANE_VISIBLE_CONFLICT`
* `INSUFFICIENT_DISTINCTIVE_SUPPORT`
* `RECOVERY_LANE_PROMOTIONS_INSUFFICIENT`

Unknown counts are explicitly forbidden as expansion triggers. The funnel may
stop when it has a credible 5--20 candidate Evidence Lane with meaningful
strong observations and no trigger. It need not name a unique winner; external
fine or Qwen review is optional and outside this implementation.

## Frozen W5 diagnostic protocol

`data/experiments/hierarchical_retrieval_funnel_v1_2/run_w5_frozen_diagnostic.py`
reads only W5's frozen `FULL_EXPERIMENTAL_SCORES.csv`. It is a counterfactual
workload diagnostic, not a rerank. The frozen CSV lacks pool aspect/shape,
orientation, relational geometry, and a strong building-footprint comparator.
Accordingly, its legacy `MATCH` values remain `MATCH`, not fabricated
`STRONG_MATCH` values. The resulting report explicitly records this caveat and
makes no recall, identity, or accuracy claim.
