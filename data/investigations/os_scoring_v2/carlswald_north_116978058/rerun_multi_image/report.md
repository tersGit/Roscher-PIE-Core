# Multi-listing-image Scoring v2 diagnostic — 116978058 / Carlswald North

**Listing:** 116978058 (Property24)  
**Candidates:** 330 Carlswald North native15 stands (PR #5 frozen set)  
**Evaluation-only visual match:** Stand 365. Not an input to candidate generation, fusion, or scoring.

**This diagnostic does not alter PR #6.** Code lives on `cursor/os-scoring-v2-multi-image-0357`. Frozen artefacts:

- PR #4 Object Segmentation v1
- PR #5 baseline experiment (`all_candidates.json` CLIP + stand_size)
- PR #6 Scoring v2 (`os_scoring_v2.py`, `latest.json`)
- native15 crops
- production ranking (`combined_score`)

## Frozen ranks reproduced (required gate)

`pr6_reproduce.json` recomputes Scoring v2 from the frozen listing fingerprint + OS v1 JSON + PR #5 CLIP/stand-size. It does **not** overwrite PR #6 files.

| ranking | Stand 365 rank | source |
|---|---:|---|
| Frozen baseline (`combined_score`) | **#17** | PR #5 `all_candidates.json` |
| PR #5 0.5-neutral | **#2** | PR #6 `latest.json` (and recompute) |
| PR #6 Scoring v2 (`v2_neutral_nobuilding`) | **#3** | PR #6 `latest.json` **and** recompute (`ok: true`) |

PR #6 Top 3 remains 583 / 428 / 365. Gap #1–#2 = 0.005.

## One new diagnostic

Use **all suitable exterior listing images**, not the single frozen oblique contour.

For each usable image: pool shape evidence, pool–house spatial where visible, pool/roof relative scale where both are framed, view quality, confidence. Fuse **before** comparing to frozen OS v1 fingerprints.

Fusion (generic, frozen before results):

- Skip CLIP `interior` scenes.
- Shape: cluster compatible views; pick the cluster with the highest **sum of shape quality**; take that cluster’s highest-quality contour. Do **not** average incompatible contours.
- Spatial: single highest `spatial_quality` view. Do **not** average angles.
- Scale: quality-weighted median of usable pool/roof pixel ratios; folded into the existing spatial mean as `area_ratio`.
- Scoring: same `V2_WEIGHTS_NO_BUILDING` + 0.5-neutral. REJECTED/UNKNOWN OS terms stay 0.5.

No Stand-365-specific rules. No weight tuning after seeing ranks. No production changes. No new pool semantic classes.

## Listing photos ingested

62 photos under `data/investigations/carlswald_north_corrected/116978058/photos/` (gitignored; not a ranking input beyond pixels).

CLIP scene counts: interior 44, pool_garden 8, driveway_access 6, contextual 2, front_elevation 1, rear_elevation 1.

Exterior observations: 18. Pool present: 16.

## What the fusion actually selected

| channel | source | why |
|---|---|---|
| **Shape** | `116978058-006` (pool_garden) | Compatible cluster 006+005+003+052 had the highest **sum** of shape quality. 006 is the best member of that cluster. |
| **Spatial** | `116978058-051` | Highest `spatial_quality` (0.882). CLIP labelled it `rear_elevation`. |
| **Scale** | median of 15 usable ratios | `pool_roof_pixel_ratio` = **0.755** |

**006** is a genuine garden/pool frame that *shows* the octagonal main pool, circular jacuzzi, and house. The colour-blob extractor still returns a **smeared contour** (compactness 0.150, 4 major indents, elongation 1.94). Fused listing shape descriptors are therefore still an irregular blob, not an octagon+jacuzzi.

The highest *single-frame* shape quality was **025** (0.727, compactness 0.562) — a **close-up of the circular jacuzzi**, not the main pool. It formed a singleton cluster and lost to the 006-family sum (1.72 vs 0.73). That is the fusion rule as coded; it was not changed after seeing ranks.

**051** is visually an **interior room / windows**. CLIP mislabelled it as rear elevation. Pool extraction on that frame is junk. Spatial fusion therefore used a bad view.

Scale 0.755 is a **close-up pool/roof pixel ratio**, not a nadir pool/building area ratio (OS v1 for 365 is ~0.14). Folding it into `area_ratio` systematically punishes stands whose true pool/building ratio is small.

## Multi-image Scoring v2 ranks

| stand | rank | score |
|---|---:|---:|
| **457** | **1** | **0.736** |
| 667 | 2 | 0.713 |
| 370 | 3 | 0.703 |
| 420 | 4 | 0.701 |
| 408 | 5 | 0.693 |
| 409 | 6 | 0.687 |
| 546 | 7 | 0.678 |
| 547 | 8 | 0.675 |
| **365** | **9** | **0.670** |
| 528 | 10 | 0.669 |

Gap #1–#2 = **0.023**. Gap #1–#10 = 0.067. **LOW CONFIDENCE — candidates insufficiently separated.**

365 vs #1: **−0.066**. 365 vs #10: **0.001** (near-tie with 528).

Coverage for 365 = 1.0 (OS ACCEPT + listing pool present). Contrib: pool_presence 0.14, shape_v2 0.224 (score 0.622), spatial_v2 0.132 (sector 0.65, dist 0.955, **area_ratio 0.191**), CLIP 0.5-fill, stand_size 0.070.

## Comparison

| ranking | Stand 365 |
|---|---:|
| Frozen baseline | **#17** |
| PR #5 0.5-neutral | **#2** |
| PR #6 Scoring v2 | **#3** |
| Multi-listing-image Scoring v2 | **#9** |

## Did 583 and 428 still beat 365?

**No.** 583 is **#46** (0.596). 428 is **#38** (0.604). Both drop because the fused listing shape is no longer the elongated frozen oblique contour they matched. That part of the PR #6 failure mode is gone.

It is replaced by a worse failure: 420 (kidney, previously demoted for real geometry) is back at **#4**. 457 wins in part because its OS pool/building ratio (~0.67) is closer to the inflated listing scale 0.755 than 365’s ~0.14.

## Did octagon + jacuzzi become more distinguishable?

**No, not in the fingerprint that scoring used.** Photo 006 *contains* that configuration, but extraction+fusion committed to a smeared garden blob (and ignored the jacuzzi close-up 025 as a minority cluster). OS v1 still does not emit a jacuzzi class. The listing side still has no second-pool / octagon descriptor that 365’s nadir mask can match.

## Is this genuinely stronger, or another near-tie?

**Weaker than PR #6, and still a near-tie.** Success required more than 365 becoming #1: a materially larger gap from competing genuine pools. 365 is **#9**, 0.001 above #10, and 0.066 behind a non-match (#1 457). Gap #1–#2 (0.023) is larger than PR #6’s 0.005 only because the leader is a different stand, not because 365 separated.

**Gate: does not pass.**

## What additional listing evidence changed the ranking

1. **006 cluster (shape)** — replaced the frozen oblique contour. 583/428 lose; 365 does not gain an octagon signature.
2. **051 (spatial)** — CLIP rear-elevation mislabel; garbage pool–house geometry.
3. **Scale median 0.755** — close-up ratios treated as nadir pool/building; 365 area_ratio 0.191 vs 457 0.669.

No weights were changed after seeing these ranks.

## Frozen / not done

- Production ranking, OS v1, native15 crops, PR #5, PR #6 Scoring v2: untouched.
- No 365-specific or listing-id rules.
- No new pool semantic classes.
- REJECTED/UNKNOWN stayed 0.5-neutral.
