# Scoring v2 — listing 116978058

Experimental comparison only. Production `combined_score`, Object Segmentation
v1, native15 crops, and the PR #5 frozen baseline were not modified. No
listing-id or stand-number rules.

Question: can better comparison/scoring move the visual match **stand 365**
into a meaningfully separated Top 1–5?

## Frozen inputs

- Listing pool fingerprint (consensus contour, already major-axis normalised)
- OS v1 JSON for 330 unique native15 parcels
- PR #5 `all_candidates.json` for baseline ranks, CLIP, and stand size
- AGS downloads: **0**

Driveway is omitted: the frozen listing fingerprint has no driveway side,
entry, or approach. Building is either removed or presence-only (never listing
oblique roof fraction vs nadir footprint).

Missing OS terms are **0.5-neutral** (no skip-and-renormalise). A coverage
factor `0.5 + 0.5 × coverage` is A/B’d on top of that.

## Stand 365 rank under every variant

| variant | 365 rank | 365 score | #1 (score) | gap #1–#2 | 365 vs nearest high-conf pool | REJECTED/UNKNOWN in Top 20 | blob FPs removed from baseline Top 20 |
|---|---:|---:|---|---:|---:|---:|---:|
| Frozen baseline | **17** | 0.666 | 611 (0.781) | 0.033 | −0.082 (457) | 13 | — |
| PR #5 0.5-neutral | **2** | 0.781 | 404 (0.782) | 0.0006 | −0.0006 (404) | 0 | 13 |
| v2 0.5-neutral, building off | **3** | 0.757 | 583 (0.764) | 0.0051 | −0.0066 (583) | 0 | 13 |
| v2 coverage, building off | **3** | 0.757 | 583 (0.764) | 0.0051 | −0.0066 (583) | 0 | 13 |
| v2 0.5-neutral, building presence | **3** | 0.748 | 583 (0.754) | 0.0050 | −0.0059 (583) | 0 | 13 |
| v2 coverage, building presence | **3** | 0.748 | 583 (0.754) | 0.0050 | −0.0059 (583) | 0 | 13 |
| Ablation: no shape_v2 | **2** | 0.675 | 451 (0.676) | 0.0015 | −0.0015 (451) | 0 | 13 |
| Ablation: no spatial_v2 | **22** | 0.688 | 545 (0.723) | 0.0105 | −0.035 (545) | 0 | 13 |

Every variant is **LOW CONFIDENCE** (gap 1–2 < 0.04).

## Top 20 — v2 0.5-neutral, building off (primary)

All CONFIRMED/PROBABLE. Coverage = 1.0 for every row.

| rank | stand | score | OS pool | shape_v2 | spatial_v2 | baseline | PR5 0.5 |
|---:|---:|---:|---|---:|---:|---:|---:|
| 1 | 583 | 0.764 | CONFIRMED | 0.809 | 0.757 | 26 | 32 |
| 2 | 428 | 0.759 | CONFIRMED | 0.801 | 0.716 | 147 | 42 |
| 3 | **365** | 0.757 | CONFIRMED | 0.730 | 0.818 | 17 | 2 |
| 4 | 568 | 0.734 | CONFIRMED | 0.794 | 0.626 | 35 | 6 |
| 5 | 451 | 0.733 | CONFIRMED | 0.658 | 0.859 | 88 | 38 |
| 6 | 667 | 0.729 | CONFIRMED | 0.788 | 0.613 | 64 | 9 |
| 7 | 528 | 0.728 | CONFIRMED | 0.732 | 0.821 | 47 | 8 |
| 8 | 573 | 0.726 | PROBABLE | 0.693 | 0.779 | 232 | 7 |
| 9 | 423 | 0.726 | CONFIRMED | 0.807 | 0.562 | 82 | 25 |
| 10 | 468 | 0.723 | CONFIRMED | 0.762 | 0.617 | 284 | 49 |
| 11 | 444 | 0.720 | CONFIRMED | 0.784 | 0.537 | 43 | 19 |
| 12 | 1/450 | 0.718 | PROBABLE | 0.750 | 0.925 | 97 | 62 |
| 13 | 446 | 0.717 | PROBABLE | 0.785 | 0.560 | 181 | 16 |
| 14 | 621 | 0.709 | CONFIRMED | 0.613 | 0.792 | 224 | 24 |
| 15 | 623 | 0.709 | CONFIRMED | 0.705 | 0.592 | 31 | 4 |
| 16 | 582 | 0.708 | PROBABLE | 0.646 | 0.754 | 74 | 5 |
| 17 | 545 | 0.708 | CONFIRMED | 0.850 | 0.432 | 175 | 67 |
| 18 | 352 | 0.702 | CONFIRMED | 0.808 | 0.501 | 168 | 17 |
| 19 | 463 | 0.699 | CONFIRMED | 0.703 | 0.604 | 44 | 21 |
| 20 | 1/334 | 0.699 | PROBABLE | 0.673 | 0.962 | 46 | 47 |

Coverage vs 0.5-neutral: **identical Top 20** among these high-conf pools
(all coverage 1.0). Coverage only further buries REJECTED stands already
outside the Top 20 (611 score 0.542 → 0.271).

Building presence-only: same 365 rank, slightly lower scores. Presence is
almost constant across residential stands, so it does not discriminate.
**Removing the building term is the better of the two.**

## Known distractors (genuine geometry, not missing-data)

| stand | PR5 0.5 rank | v2 rank | why |
|---|---:|---:|---|
| 404 | 1 | **29** | Compact irregular (elongation 1.02 vs listing 2.42). Coarse label `irregular` had been an exact match. |
| 348 | 3 | **64** | Deep indentations, short centroid dist 0.22 vs listing 0.41. |
| 420 | 11 | **39** | Kidney/NW of house; opposite-ish sector. |
| 611 | 93 | **99** | OS REJECTED; stays out. |

That movement is real visual discrimination.

## Why 365 is #3, not #1

Listing frozen contour (oblique consensus) is elongated (2.42) with two
indentations — the jacuzzi reads as a side lobe. OS on 365 is a simplified
nadir polygon: elongation 2.08, **zero major indents**, kidney_or_curved.
The jacuzzi is not in the OS contour.

583 and 428 are elongated_rectangular nadir pools (elongation 3.17 / 2.67,
two indents). They match the *listing photo contour* better than 365 does
(`shape_v2` 0.809 / 0.801 vs 0.730). They sit east of the house; listing
bearing is SE in the photo, so 8-sector gives the same adjacent credit
(0.65) as 365’s true south.

365 still wins **spatial** (centroid dist 0.404 vs listing 0.410). It loses
**shape_v2**. Net: 0.757 vs 583 0.764.

This is not skip-and-renormalise. It is a remaining comparison error:
oblique listing contour ≠ nadir octagon+jacuzzi mask.

Per-feature contributions, v2 0.5-neutral building-off:

| | 583 | 428 | 365 |
|---|---:|---:|---:|
| pool_presence | 0.140 | 0.140 | 0.140 |
| shape_v2 | **0.291** | 0.288 | 0.263 |
| spatial_v2 | 0.167 | 0.158 | **0.180** |
| aerial (0.5 fill) | 0.060 | 0.060 | 0.060 |
| exterior (0.5 fill) | 0.030 | 0.030 | 0.030 |
| gis | 0.015 | 0.015 | 0.015 |
| stand_size | 0.061 | 0.068 | 0.070 |

Ablations: drop spatial → 365 **#22**. Drop shape → 365 **#2** but 404 returns
to #5. Spatial is what keeps 365 in the Top 5; shape_v2 is what removes 404.

Terms that could not be compared on this listing (no listing house contour /
metres / orientation) and were left unscored: nearest pool–building edge,
dist / √building, relative long axes, pool/building area ratio.

## Gate

| criterion | result |
|---|---|
| 365 in Top 5 | **Yes** (#3) |
| REJECTED/UNKNOWN do not dominate | **Yes** (0 in Top 20) |
| Movement from genuine pool/house geometry | **Partial** (404/348/420 demoted for the right reasons; 583/428 win by matching the distorted listing contour) |
| No listing- or stand-specific rules | **Yes** |
| Meaningful separation | **No** (gap 1–2 = 0.005; 365 is 0.007 behind 583) |

**Does not pass.** 365 is in the Top 5 with LOW CONFIDENCE. It is not
identified. Do not treat #3 as solved, and do not wire Scoring v2 into
production EvidenceFusion.

## A–E

**A.** Best 365 rank: **#2** (PR #5 0.5-neutral, and the no-shape ablation).
Best full Scoring v2 rank: **#3**.

**B.** Best #1–#2 margin among v2 variants: **0.005**. 365 vs nearest rival:
**−0.007** (behind 583). Still LOW CONFIDENCE.

**C.** Largest genuine improvement vs the blob baseline: **shape_v2
elongation / indent / chamfer**, which moved 404 from PR5 #1 to #29 and 348
from #3 to #64. The term that keeps 365 itself in the Top 5 is **spatial_v2
(8-sector + centroid distance)**. Dropping spatial sends 365 to #22.

**D.** Neutral missing-data treatment remains **necessary**. Coverage did not
beat 0.5-neutral on this listing’s Top 20 (every survivor already has full
OS coverage). Skip-and-renormalise was already shown unsafe in PR #5.

**E.** Not strong enough to integrate. Strong enough to **test Scoring v2 on
additional known-ground-truth listings**, because the remaining errors are
now real similar pools plus listing-oblique vs nadir contour mismatch, not
blob false positives.

Panels: `data/investigations/os_scoring_v2/carlswald_north_116978058/panels/`.
