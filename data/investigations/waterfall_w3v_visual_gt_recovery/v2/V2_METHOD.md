# Waterfall W3-V visual retrieval V2 method preregistration

## Scope and immutability

This is an independent retrieval-only pass. It uses exactly the 1,010 frozen W1
native15 aerial crops at
`C:\Users\ters\copilot-worktrees\Roscher-PIE-Core\tersgit-probable-winner\data\visual_index\waterfall_country_estate_w1\_imagery_cache_native15`.
The W1 cache manifest hash is
`b732dd96eddb3104cc69c7716d6e80498b39de08ec0b59b3f89f90aed99b377e`.

The target profile is read-only and must hash to
`56aca3c5d9d680a1a69dd19680d885fe38793c45900133f762267332d16d04bc`.
This pass uses W1 parcel geometry solely to determine whether a visible object
is inside the candidate parcel. It does not use stand numbers, addresses,
identity data, any historic rank, shortlist, production score, or imagery
outside the stated W1 cache. V1 and its forensic audit remain immutable.

## Fixed components and weights

| Component | Weight | Target cue |
|---|---:|---|
| `pool` | 0.25 | Compact rectilinear near-building pool-like geometry |
| `building` | 0.20 | Substantial contemporary rectilinear building mass |
| `pool_house_relation` | 0.20 | Near-building, broadly parallel pool/house relation |
| `driveway` | 0.10 | Paved approach/access within the parcel |
| `open_space` | 0.10 | Limited landscaped open space around the house |
| `parcel_geometry` | 0.15 | Visible parcel-compatible building/open-space arrangement |

Weights are fixed before the scan and sum to 1.00. No threshold, weight, or
ranking adjustment may be selected after observing the results.

## Observation, parcel binding, and compatibility

Every component receives all four independent fields:

1. `visibility`: `OBSERVED`, `PARTIAL`, `NOT_VISIBLE`, or `AMBIGUOUS`.
2. `binding`: `IN_PARCEL`, `BOUNDARY_AMBIGUOUS`, `OUTSIDE_PARCEL`, or
   `UNBOUND`.
3. `compat`: `MATCH`, `PARTIAL`, `CONFLICT`, or `UNKNOWN`.
4. `confidence`: a fixed confidence value in [0, 1] reflecting image and mask
   support, not likelihood of being the target.

An object can support a candidate only with `OBSERVED` or sufficient `PARTIAL`
visibility and `IN_PARCEL` or explicit, mask-supported
`BOUNDARY_AMBIGUOUS` binding. External objects are never candidate-owned.
Weak or missing detection is recorded as `NOT_VISIBLE` or `AMBIGUOUS`, never
as absence. `UNKNOWN` is required for non-visible, weak, unbound, or
cross-view-noncomparable evidence. `CONFLICT` requires directly visible,
parcel-bound geometry that contradicts a target cue; it is never inferred from
an `UNKNOWN` state.

Compatibility values are fixed as `MATCH = 1.0`, `PARTIAL = 0.5`,
`CONFLICT = 0.0`, and `UNKNOWN = 0.0`. Component score is
`weight * compat_value * confidence` only for score-eligible evidence.
Otherwise its component score is zero.

## Coverage and retrieval formula

For component *i*, score eligibility is 1 only when visibility is `OBSERVED`
or `PARTIAL`, binding is `IN_PARCEL` or `BOUNDARY_AMBIGUOUS`, and compatibility
is not `UNKNOWN`. Let *w_i* be its fixed weight, *q_i* its confidence, and
*c_i* its compatibility value.

`compatibility = sum(w_i * q_i * c_i) / sum(w_i)`

`coverage = sum(w_i * q_i * eligibility_i) / sum(w_i)`

`retrieval = compatibility * coverage`

Coverage is the observable weighted mass divided by all possible weighted mass.
The product makes unobservable evidence non-supportive without treating it as
contradictory. Ties are broken only by property ID in ascending lexical order.

## Output and stopping rules

One complete run must emit one row for each of the 1,010 W1 properties,
including all component fields and aggregate observed, unknown, conflict,
coverage, and retrieval values. The accompanying distribution report must
show component and candidate distributions plus sanity counts. If `UNKNOWN`
is absent, or more than 90% of candidates are hard conflicts, retrieval stops
for audit and no shortlist is made.

Only after the complete output is hash-frozen and sanity passes may the
independent top 30 be frozen. Manual review may then document visible support,
visible conflict, unknown evidence, and coverage, without naming a winner.
External confirmation is permitted only for a small independently retrieved
set, after its identity set is frozen; it is confirmation rather than
ground truth. If that condition is not reached, ground truth remains
unavailable and ranks remain unopened.
