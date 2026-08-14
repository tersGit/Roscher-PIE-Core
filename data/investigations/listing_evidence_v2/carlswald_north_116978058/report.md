# Listing Evidence v2 — 116978058

Extraction quality gate **before** any 330-candidate rerank. Stand 365 is evaluation-only and was not an input to viewpoint classification, segmentation, channel assembly, or scoring.

Frozen and unmodified: production ranking, PR #6 Scoring v2 weights, Object Segmentation v1, native15 fingerprints, PR #7 artefacts and code.

**Quality gate: failed. No estate rerank was run.**

## A. Did viewpoint filtering work?

**Yes, on the failure modes that broke PR #7.**

| check | result |
|---|---|
| 051 classified interior | **Yes** (CLIP interior 0.993) |
| 051 spatial eligible | **False** |
| Other interiors contributing spatial | **none** |
| 025 classified pool close-up | **Yes** (CLIP said pool_overview 0.57; geometric override: single compact water, low grass, foreground centroid) |
| 025 nadir-scale eligible | **False** |
| Agent headshots 001/002 | **unusable_ambiguous** |
| Aerial / near-nadir frames | **none** in this listing |

Viewpoint counts (62 photos): interior 46, pool_overview 7, ground_level_exterior 5, unusable_ambiguous 2, pool_closeup 1, garden_only 1.

052 is a covered patio with no pool. CLIP ranked it ground-level vs interior; the low-grass + interior-second-score rule labelled it **interior**. It contributes no spatial evidence. That is the correct eligibility outcome even if “covered patio” is a finer label than the eight-class set.

049 (covered balcony, trees through a railing, no pool) is `ground_level_exterior` with **pool_detected=false** after size/edge filters removed a floor-tile scrap. It is not spatial-eligible.

## Explicit inspect

| image | viewpoint | pool | overview | spatial | scale | quality | n_comp |
|---|---|---|---:|---:|---:|---:|---:|
| 003 | pool_overview | False | False | False | False | 0.0 | 0 |
| 005 | pool_overview | False | False | False | False | 0.0 | 0 |
| 006 | pool_overview | True | False | False | False | 0.446 | 1 |
| 025 | pool_closeup | True | False | False | False | 0.935 | 1 |
| 051 | interior | False | False | False | False | 0.0 | 0 |
| 052 | interior | False | False | False | False | 0.0 | 0 |

003 and 005 are correctly *classified* as pool overviews. Extraction found only sub-threshold water slivers (garden leakage / dark reflections), so they record pool_detected=false after quality filters. That is conservative: a smeared PR #7-style blob is not promoted.

## B. Best usable listing frame(s)?

**The only high-quality water contour is 025** (jacuzzi close-up): compactness 0.572, circularity 0.845, solidity 0.986, 0 major indents, n_approx=6. It is excluded from overview, spatial, and nadir-scale channels by design.

Best *overview-eligible* frame: **009**, quality 0.462. The contour is a cyan reflection sliver inside the main pool (relative area 0.008, elongation 2.98, 3 major indents), not the pool coping. 006 has a similar internal sliver (rel 0.0066) and is not overview-eligible.

Selection method: **best_single_frame** (009). Consensus of independently good frames: empty. Cluster-sum recorded for comparison, not used: `[009]`.

No aerial-compatible evidence. No nadir-compatible pool/building area ratio.

## C. Did compound-pool detection work?

**Visually yes; in the extractor no.**

003, 005, 006, 008, 009 all show a large angular main pool and a separate smaller jacuzzi on a raised platform, separated by lawn. After quality filters the extractor never retained two components on an overview frame (`compound_pool.detected=false`).

025 detects the jacuzzi cleanly as a **single** component because the main pool is out of frame.

The gap is colour: overview pool water is dark and reflective (house/sky), so HSV cyan+dark seeds capture interior highlights rather than the coping polygon, and the jacuzzi on paving has little grass adjacency.

## D. Was the octagonal / straight-edged character materially better represented?

**Only on the close-up jacuzzi, not on the main pool overview.**

- 025: faceted/octagonal jacuzzi contour is clean. That is the secondary water body, and it is not an overview fingerprint.
- 009 (best overview): compactness 0.297 vs PR #7 smear 0.150 — higher, but still a reflection fragment (elongation 2.98, 3 indents). Not an octagon.
- 003/006: the octagonal coping is obvious in the photograph and is not the extracted contour.

Gate “substantially cleaner than PR #7 smear”: **False**.

## E. Did reliable pool-house geometry survive?

**No.** Spatial eligibility is technically true for 009 (pool fragment + roof centroid), but the pool centroid is a highlight inside a clipped foreground pool, so the vector is not a viewpoint-compatible planform relationship. 025 has the house in frame and is blocked as a close-up. 003/005/006, which *would* be the right spatial views, have no overview-eligible contour.

Scale/aerial channels are empty. This listing has no drone/nadir photo.

## Quality gate

| criterion | pass |
|---|---|
| 051 and interiors excluded from spatial | **True** |
| Close-ups excluded from nadir-compatible area ratio | **True** |
| Best pool overview substantially cleaner than PR #7 smear | **False** |
| More than one water component where main pool + adjacent jacuzzi are separable | **False** |
| Evidence source and viewpoint retained (not collapsed) | **True** |

**Passed: False**

## F. Frozen PR #6 scorer

Gate failed. **No 330-candidate rerank.** Scoring v2 weights were not changed. Stand 365 was not scored under this diagnostic.

An earlier unfiltered pass had treated a 049 balcony floor scrap as the best contour and would have produced a bogus estate ranking. Generic size, edge, grass-adjacency, and interior-second-score filters were applied so that scrap cannot enter shape/spatial channels. Those filters are not stand-specific and were not tuned to any candidate rank.

## What this means

Listing photographs **can** classify viewpoint well enough to kill PR #7’s 051-spatial and close-up-scale errors. They **cannot yet** produce a nadir-compatible, multi-component, octagonal-main-pool fingerprint from this listing’s dark reflective water and oblique garden views. Colour-blob extraction is the bottleneck, not fusion or Scoring v2 weights.

Next extraction work (still listing-side, still before scoring): coping-first / grass-boundary polygons, not HSV water fill.

## All frames

See `latest.json` `frames` for the full per-image record (image ID, viewpoint, pool yes/no, overview/spatial/scale eligible, contour quality, component count, dominant/secondary descriptors). Panels: `panels/` (inspect set plus strongest detected frames).
