# Counterfactual classification

## Rule applied

The frozen target profile establishes a conjunction of a compact rectilinear
pool, near-building patio relation, limited manicured open space, contemporary
flat/parapet massing, and paved approach. This audit did not infer any
candidate identity from a crop.

A frozen `CONFLICT` is retained only where the corresponding candidate-bound
feature is directly visible and contradictory. Missing detection, no retained
blue component, occlusion, ambiguous tile content, low confidence, and
ground-level-only architecture reclassify to `UNKNOWN`.

## Deterministic blinded visual sample

Selection used the frozen full-universe order only: both `OBSERVED` rows, then
the first ten conflict rows, the centered ten conflict rows (positions 502--511
in the full ordering), and the final ten conflict rows. No selection used a
stand, address, identity, imagery content, prior prediction, or any other
ranking.

| Frozen detector class | Sampled | Directly visible candidate-bound conflict | Counterfactual unknown |
|---|---:|---:|---:|
| `OBSERVED` | 2 | 0 | 2 |
| High-score `CONFLICT` | 10 | 0 | 10 |
| Median-score `CONFLICT` | 10 | 0 | 10 |
| Low-score `CONFLICT` | 10 | 0 | 10 |
| **Total** | **32** | **0 (0.0%)** | **32 (100.0%)** |

The zero genuine-conflict count is not a claim that every candidate matches.
It is the only supportable result from a source that lacks a candidate binding.
The sample contains dense residential tiles, pools, roofs, hardscape, empty
land, tree cover, and sports-field context, but those observations cannot be
assigned to the scored row. Where a feature is hidden, absent from the
detector, or impossible to establish from nadir imagery, it is `NOT_VISIBLE`;
where it may be present but cannot be assigned, it is `AMBIGUOUS`.

## Full-universe implication

The frozen 1,008 `CONFLICT` labels cannot be interpreted as 1,008 observed
pool contradictions. The sampled counterfactual unknown rate is 100.0% and
the underlying implementation's unknown branch produced 0 rows despite
available non-detection and attribution limitations. The evidence supports a
modeling correction from residual detector `CONFLICT` to an explicit
non-assessable/unknown state; it does not establish a retrieval hit or produce
a candidate ranking.
