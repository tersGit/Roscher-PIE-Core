# W3-V visual retrieval forensic classification logic

## Scope and immutable inputs

This audit reads only:

- `TARGET_GEOMETRY_PROFILE.md`, SHA256 `56aca3c5d9d680a1a69dd19680d885fe38793c45900133f762267332d16d04bc`;
- `FULL_UNIVERSE_SCORES.csv`, SHA256 `1de39d913051ad054a834cfa7ce0145c94f7cf138c845c1abb8e406f0e376827`;
- the recovered original frozen W1 native15 crop cache.

`SHORTLIST.csv` was not opened. Its recorded SHA256 was verified read-only as
`d3fb1697aa7f0a292996b040f73cbc39192caac40742e20fafa91a655d17253b`.
No retrieval, scoring, normalization, shortlist creation, threshold alteration,
reranking, external imagery, GIS, prior ranking, predicted stand, W3-S, W3-V
PIE/Qwen, or Top10 material was opened or used.

The input hashes were checked before and after this audit; the audit writes only
to this directory.

## Implemented state logic and reachability

The executable implementation is
`scripts/run_waterfall_w3v_visual_gt_recovery.py`.

`water_state` is the sole emitted categorical visual state:

| State | Exact condition | Observed reachability in frozen CSV |
|---|---|---:|
| `OBSERVED` | A retained HSV-water component exists and its fixed `water_score` is at least `0.46`. | 2 |
| `UNKNOWN` | Not observed, and `shadow_fraction > 0.24` or `vegetation_fraction > 0.58`. | 0 |
| `CONFLICT` | Every remaining case. | 1,008 |

The source's `water_score` is `0.45 * size + 0.35 * rectangularity + 0.20 *
aspect`, after fixed masks and component filters (area 80--55,000 pixels). The
water mask is HSV `(78,35,35)` through `(115,255,255)`, opened with a 3x3
kernel. Consequently, a pale, covered, shadowed, non-blue, small, or
otherwise undetected pool enters the same `CONFLICT` catch-all as a directly
contradictory visible feature.

`UNKNOWN` is mathematically reachable but empirically unreachable in this
freeze: maximum shadow is `0.215465`; maximum vegetation is `0.340490`. Both
are below their strict trigger thresholds. The emitted `uncertainty` field is
also `NONE` in all 1,010 rows.

## Other component outputs and missing mapping

The following are continuous diagnostics, not semantic assertions:

| Requested component | Frozen CSV output | Missing state/mapping |
|---|---|---|
| Pool / geometry | `water_*`, `water_state` | No pool absence proof; no candidate-pool association. |
| Visibility | `visibility`, vegetation and shadow fractions | No visibility class or threshold affects `CONFLICT`. |
| House | `building_*` | No house observed/partial/conflict/unknown state. |
| House-pool | `relation_*` | No feature pairing when water or roof is absent; normalized value is constant 0.5 in every row. |
| Open space | `outdoor_*` | No lawn/patio semantic state. |
| Driveway | `access_*` | No driveway continuity or driveway state is emitted. |
| Parcel | None | Parcel compactness/aspect described in method prose is not calculated or written. |
| Final | `retrieval_score` | No final observation or confidence state. |

The W1 crop is a 900x900 context tile. The permitted visual source has no
parcel overlay, target marker, feature boundary, or crop-to-scored-entity
mapping. In dense tiles it is therefore not possible to attribute a visible
pool, roof, driveway, lawn, or open ground to the CSV row rather than a
neighbour. This is the primary visual-audit observability limitation.

## Contribution and threshold consequences

Pool geometry has the largest fixed weight (0.30). `UNKNOWN` would receive the
universe median normalized water value, while `CONFLICT` receives its measured
water value. Since 992 rows have no retained water component and water's
normalized median is 0, the catch-all state supplies little or no pool
contribution to most rows. The remaining score is driven by broad building
massing (0.24), the constant relation term (0.20), outdoor layout (0.14),
access (0.07), and texture (0.05).

This is not a weak-pool gate that excludes rows: every conflict remains scored.
It is a weak-pool evidence model with an overbroad negative label. The
implementation does not test the target's required narrow near-building pool,
flat/parapet house, restricted lawn/patio, or driveway conjunction as
categorical evidence.

## Counterfactual audit rule

For visual reclassification:

- `VISIBLE_MATCH`: the candidate-bound feature is directly visible and supports
  the frozen target observation.
- `VISIBLE_CONFLICT`: the candidate-bound feature is directly visible and
  directly contradicts it.
- `NOT_VISIBLE`: the feature cannot be seen due to occlusion, resolution,
  absence of a detection, or an aerial/nadir-impossible target feature.
- `AMBIGUOUS`: a feature may be visible in the tile but cannot be attributed to
  the scored candidate, or its interpretation is equivocal.

Only `VISIBLE_CONFLICT` supports a genuine conflict. `NOT_VISIBLE` and
`AMBIGUOUS` must become `UNKNOWN` for counterfactual class counting. Ground
level architecture, full pool outline, patio treatment, roof expression under
obstruction, and all unbound dense-tile features are non-assessable rather
than negative evidence.
