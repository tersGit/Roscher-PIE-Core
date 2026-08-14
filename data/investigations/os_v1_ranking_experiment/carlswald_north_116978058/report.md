# OS v1 ranking experiment — listing 116978058

Object Segmentation v1 (PR #4) is frozen and used unchanged. Production
`combined_score` / EvidenceFusion weights are unchanged. No AGS downloads
(native15 crops reused). Stands 370/408 were not retuned.

Question: does better object localisation improve **candidate discrimination**
for listing 116978058, or only segmentation accuracy?

Evaluation stand **365** is a visual match (faceted/octagonal pool, circular
jacuzzi, pavilion, power lines beyond the rear wall). GIS 970 m² vs listing
972 m² is corroboration only and was not a ranking input.

## Method

1. Blind baseline: existing ranking on all 330 unique native15 crops, frozen
   listing pool fingerprint, same listing photos as the native15 A/B run.
2. Experimental hybrid: replace blob pool / roof / driveway terms with
   high-confidence OS v1 features only (CONFIRMED/PROBABLE). REJECTED/UNKNOWN
   are skipped (`None`), not used as positive evidence, and do not apply
   `listing_has_pool_candidate_has_none × 0.25`.
3. Diagnostics (not production proposals):
   - **neutral fill**: missing OS object terms imputed at 0.5 so
     skip-and-renormalise cannot reward a failed extraction;
   - **pure OS**;
   - **among 95 high-confidence pools**.

CLIP aerial/exterior remain the baseline pass-2 shortlist (top 40 by blob
pool geometry). Stands outside that shortlist, including 365, have no CLIP
terms. That is a confound when reading hybrid ranks.

Runtime: **15.9 s**. AGS downloads: **0**. Candidates: **330**.

## Frozen baseline Top 20 (pre-segmentation)

Reproduced the native15 blob ranking. Top 1 = 611 (0.781). **LOW CONFIDENCE**
(gap 1–2 = 0.033, gap 1–10 = 0.099). Stand 365 = **#17** (0.666).

| rank | stand | score | blob pool | OS pool |
|---:|---:|---:|:---:|---|
| 1 | 611 | 0.781 | yes | REJECTED |
| 2 | 457 | 0.748 | yes | CONFIRMED |
| 3 | 585 | 0.726 | yes | PROBABLE |
| 4 | 587 | 0.706 | yes | REJECTED |
| 5 | 638 | 0.698 | yes | REJECTED |
| 6 | 538 | 0.694 | yes | UNKNOWN |
| 7 | 643 | 0.693 | yes | UNKNOWN |
| 8 | 491 | 0.691 | yes | CONFIRMED |
| 9 | 404 | 0.686 | yes | CONFIRMED |
| 10 | 358 | 0.682 | yes | REJECTED |
| 11 | 360 | 0.681 | yes | CONFIRMED |
| 12 | 690 | 0.680 | yes | CONFIRMED |
| 13 | 589 | 0.677 | yes | REJECTED |
| 14 | 418 | 0.676 | yes | UNKNOWN |
| 15 | 1/510 | 0.668 | yes | REJECTED |
| 16 | 452 | 0.667 | yes | REJECTED |
| 17 | **365** | 0.666 | yes | CONFIRMED |
| 18 | 353 | 0.666 | yes | REJECTED |
| 19 | 635 | 0.662 | yes | REJECTED |
| 20 | 361 | 0.662 | yes | UNKNOWN |

13 of 20 baseline “pools” are OS REJECTED/UNKNOWN. Localisation already
disagrees with the blob extractor on the current Top 20.

## Specified experiment (skip-None hybrid)

Stand 365: **#17 → #10** (0.781). Still LOW CONFIDENCE (gap 1–2 = 0.0035).

| rank | stand | score | OS pool | baseline | Δ |
|---:|---:|---:|---|---:|---:|
| 1 | 508 | 0.833 | REJECTED | 109 | +108 |
| 2 | 388 | 0.829 | REJECTED | 202 | +200 |
| 3 | 378 | 0.820 | REJECTED | 244 | +241 |
| 4 | 504 | 0.820 | REJECTED | 179 | +175 |
| 5 | 509 | 0.820 | REJECTED | 200 | +195 |
| 6 | 543 | 0.802 | UNKNOWN | 220 | +214 |
| 7 | 392 | 0.800 | UNKNOWN | 303 | +296 |
| 8 | 364 | 0.787 | UNKNOWN | 83 | +75 |
| 9 | 404 | 0.782 | CONFIRMED | 9 | 0 |
| 10 | **365** | 0.781 | CONFIRMED | 17 | +7 |

Top 5 entering: 508, 388, 378, 504, 509. Top 10 entering also includes
543, 392, 364, 365. Leaving: 611, 457, 585, 587, 638, 538, 643, 491, 358.

Stand **392** has every OS object UNKNOWN. Its hybrid score is gis + stand-size
renormalised to 0.80. That is not object evidence.

Skip-and-renormalise rewards missing pool terms: remaining building / driveway /
stand-size weights concentrate, so a REJECTED roof match outranks a CONFIRMED
pool. This ranking is not a candidate for EvidenceFusion.

## Neutral diagnostic (missing OS = 0.5)

Same OS features. Missing object terms stay in the mix at 0.5 — neither
positive evidence nor the 0.25 contradiction.

Stand 365: **#17 → #2** (0.781). Top 20 is entirely CONFIRMED/PROBABLE pools.
Blob-pool false positives 611/587/638/538/643/358 drop out of the Top 20.

| rank | stand | score | OS pool | baseline | Δ |
|---:|---:|---:|---|---:|---:|
| 1 | 404 | 0.782 | CONFIRMED | 9 | +8 |
| 2 | **365** | 0.781 | CONFIRMED | 17 | +15 |
| 3 | 348 | 0.765 | CONFIRMED | 153 | +150 |
| 4 | 623 | 0.754 | CONFIRMED | 31 | +27 |
| 5 | 582 | 0.754 | PROBABLE | 74 | +69 |
| 6 | 568 | 0.746 | CONFIRMED | 35 | +29 |
| 7 | 573 | 0.744 | PROBABLE | 232 | +225 |
| 8 | 528 | 0.742 | CONFIRMED | 47 | +39 |
| 9 | 667 | 0.729 | CONFIRMED | 64 | +55 |
| 10 | 354 | 0.725 | CONFIRMED | 108 | +98 |

Gap 404–365 = **0.0006**. Still LOW CONFIDENCE. 348 is a different property
(blob contradiction `pool_on_opposite_side_of_house`, not applied here).
420 (known kidney-pool distractor, not this listing) is **#11**.

Top 5 entering: 404, 365, 348, 623, 582. Leaving: 611, 457, 585, 587, 638.

## Among 95 high-confidence pools

Pure OS, restricted to CONFIRMED/PROBABLE pools. Stand 365 = **#4 / 95**.

1. 404 (irregular, exact shape match to the listing fingerprint)
2. 582
3. 348
4. **365** (OS shape `kidney_or_curved` → alias 0.75 vs listing `irregular`)

Localisation found the right pool. The fingerprint does not uniquely identify
it among other real pools.

## Which OS features moved 365

Listing fingerprint (frozen): present, `irregular`, aspect 1.934, compactness
0.158, pool-to-house dist 0.410. OS on 365: CONFIRMED 32.47 m²,
`kidney_or_curved`, aspect 1.771, pool-house dist 0.51.

| feature | 365 | 404 | 348 | 611 (baseline #1) |
|---|---:|---:|---:|---|
| pool_presence | 1.00 | 1.00 | 1.00 | skipped |
| pool_shape | 0.75 | **1.00** | **1.00** | skipped |
| pool_contour | 0.655 | 0.761 | 0.734 | skipped |
| pool_area | 0.863 | 0.843 | 0.830 | skipped |
| pool_house_dist | 0.986 | 0.986 | 0.529 | skipped |
| pool_house_position | 0.564 | 0.422 | 0.729 | skipped |
| building_footprint | 0.703 | 0.554 | 0.528 | 0.597 |
| driveway | 0.85 | 0.85 | 0.85 | 0.85 |

What helped 365: OS CONFIRMED recovered a pool the blob scorer under-weighted
(blob geom 0.589, so 365 missed the CLIP shortlist). Pool area and
pool-to-house distance are strong.

What failed to discriminate: listing `irregular` vs OS `kidney_or_curved` is
only a 0.75 alias, while 404’s true `irregular` scores 1.00. The listing
octagon+jacuzzi is not in the shape vocabulary. Driveway is a constant 0.85
presence bit. Building footprint compares listing-oblique roof fraction to
nadir relative area — too many stands score in the same band. Experimental
ranking does not keep blob contradictions, so 348 is free to enter the Top 3.

## Blob false positives removed from baseline Top 20

OS REJECTED/UNKNOWN in the frozen Top 20, with hybrid-neutral rank:

611 #1→93, 587 #4→242, 638 #5→163, 538 #6→227, 643 #7→165, 358 #10→178,
589 #13→253, 418 #14→244, 1/510 #15→275, 452 #16→166, 353 #18→213,
635 #19→152, 361 #20→126.

Those were blob-geometry false positives. Removing them is real. It is not
the same as identifying 365.

## Decision

**Do not integrate this skip-None hybrid into EvidenceFusion.**

The specified experiment moved 365 into the Top 10 by introducing obvious
false positives (no-pool stands promoted by renormalisation). That fails the
gate: a material jump *without* obvious FPs.

The 0.5-neutral diagnostic shows the other half of the picture: once missing
OS terms cannot rank, 365 jumps **17 → 2** and blob FPs leave the Top 20.
That is evidence the extractor is now good enough to *matter*. It is not
evidence the current comparison layer can finish the identification.

Next bottleneck is comparison/scoring, not imagery extraction:

1. How missing OS objects enter EvidenceFusion (skip-None is unsafe; 0.25
   contradiction is also unsafe when the extractor simply failed).
2. Shape vocabulary is too coarse for this listing (octagon + jacuzzi collapsed
   to `kidney_or_curved`, losing to unrelated `irregular` pools).
3. Listing-oblique vs nadir geometry (contour, roof fraction, pool-house
   vector) is still a weak comparator among true pools.
4. CLIP shortlist is still gated on blob pool geometry, so the correct stand
   never received CLIP terms in this run.

No production ranking weights were changed.
