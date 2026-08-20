# Rank-5 forensic — listing 115503057 / Stand 401

Diagnostic only. Production PIE, Scoring v2 weights, freeze files, and hashes are unchanged. Ground truth is used solely for post-blind evaluation.

Machine-readable twin: `rank5_forensic.json`. Proof panel: `data/investigations/blind_115503057_complete_estate/panels/rank5_top5_forensic_proof.jpg`.

## A. Frozen-test integrity

| Item | Value |
| --- | --- |
| PR | [#30](https://github.com/tersGit/Roscher-PIE-Core/pull/30) |
| Branch | `cursor/blind-115503057-complete-estate-dc1a` |
| Freeze commit | `5aa42ec266a0c515a75e9b7f4da623b0be84dc66` |
| Freeze SHA256 | `a6465002f681268391d4a87f3039532f47fd97e76d9a43217a8a45c841604ff6` |
| SHA256 vs on-disk `freeze.json` | **MATCH** |
| SHA256 vs `rankings_frozen.json` | **MATCH** |
| Frozen rank of Stand 401 | **5 / 367** |
| Frozen Top 5 | **868 / 624 / 648 / 545 / 401** |
| Ranking / scoring files modified this task | **No** |
| Scoring v2 weights | pool_presence 0.14, shape_v2 0.36, spatial_v2 0.22, aerial 0.12, exterior 0.06, gis 0.03, stand_size 0.07 |
| Ground truth applied to ranking | false |
| Colour used | false |

Post-freeze GT recovery lives in `FORENSIC.md` / `forensic.json` (commit `556f422`) and does not rewrite the freeze.

## B. Frozen Top-5 table

| rank | stand | street | township | GIS m² | score | shape_v2 | spatial_v2 | aerial | exterior | stand_size | inv | POV | corner |
| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |
| 1 | 868 | 21 CORAL TREE DRIVE | SUMMERSET EXT.3 | 958.0 | 0.7265 | 0.8261 | null | null | 0.7451 | 0.8489 | YES | CONFIRMED | UNKNOWN |
| 2 | 624 | 17 CAMELS FOOT DRIVE | SUMMERSET EXT.13 | 886.0 | 0.72 | 0.7777 | null | null | 0.7827 | 0.9727 | YES | CONFIRMED | NO |
| 3 | 648 | 4 KIAAT END | SUMMERSET EXT.13 | 920.0 | 0.7184 | 0.7902 | null | null | 0.715 | 0.943 | YES | CONFIRMED | NO |
| 4 | 545 | 15 BUFFALO THORN DRIVE | SUMMERSET EXT.6 | 918.0 | 0.7163 | 0.7685 | null | null | 0.8046 | 0.948 | YES | CONFIRMED | YES |
| 5 | 401 **GT** | 6 BUFFALO THORN DRIVE | SUMMERSET EXT.6 | 919.0 | 0.7152 | 0.7712 | null | null | 0.7724 | 0.9455 | YES | CONFIRMED | NO |

Score band #1–#5: **0.7265–0.7152 (Δ 0.0113)**. Discrimination is almost entirely `shape_v2`.

## C. Stand 401 evidence profile

401 entered the 367 as inventory YES / POV CONFIRMED / Corner Gate retained (parcel NO, listing CORNER=UNKNOWN). Frozen score **0.7152**, rank **5**.

| Component | Weight | Raw | Contrib | Freeze-time evidence | Class |
| --- | ---: | ---: | ---: | --- | --- |
| pool_presence | 0.14 | 1.0 | 0.14 | Inventory YES, OS CONFIRMED 22.54 m², CLIP pool 0.98 | strong positive signal |
| shape_v2 | 0.36 | 0.7712 | 0.2776 | Elongated in-parcel pool vs listing 043; parts below | useful supporting signal |
| spatial_v2 | 0.22 | null | 0.11 (pad) | Hybrid omitted pool–house (`not_viewpoint_compatible`). Candidate-only: N / −90.4° / 12.69 m / nearest_edge 0.0302 | missing |
| aerial | 0.12 | null | 0.06 (pad) | No listing aerial | missing |
| exterior | 0.06 | 0.7724 | 0.0463 | CLIP vs 12 exterior frames | useful supporting signal |
| gis | 0.03 | 0.5 | 0.015 | Constant | neutral |
| stand_size | 0.07 | 0.9455 | 0.0662 | GIS 919 vs advertised 897 | useful supporting signal |

### Pool / house / driveway / parcel (freeze-time OS + GIS)

- Pool: OS CONFIRMED, 22.54 m², aspect 2.766, irregular/elongated, north of house, in-parcel (correct object).
- POV: CONFIRMED (scoring-eligible). Viewpoint-gate: listing official pick is oblique `pool_overview` 043; candidate POV overlay did not change 401's CONFIRMED status.
- Building: CONFIRMED 429.66 m² dark multi-plane roof (compatible with listing floor 672 m² / two-storey copy).
- Driveway: PROBABLE, OS side `south` (image +y south); street is Buffalo Thorn to the east — candidate driveway sits on the street-front / SE of the house.
- Parcel: internal, one road (Buffalo Thorn), corner NO 0.88 `single_road_frontage_not_corner`.
- House–pool: adjacent north side-yard, axis_rel 0.8916 (nearly parallel). **Not scored** because listing spatial was omitted.

### Listing fingerprint 043

- Official Hybrid pick: YOLOE/SAM2, POV CONFIRMED 0.64, aspect 3.752 / descriptor elongation **2.4825**, solidity 0.9175, 1 major indent, shape_class **irregular**.
- Distinctive Contour v2: **PARTIALLY LOST** (`spa_or_secondary_not_in_dominant_contour`). **Not used in ranking.**
- Pool-to-house vector: omitted. Aerial: none. Colour: unused.

shape_v2 parts vs listing 043 (recomputed from freeze-time contours; total 0.7712):

| elongation | chamfer | hu | solidity | n_indents | max_indent | n_corners | circularity | sharp_frac | radial_cv |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.957 | 0.7435 | 0.5719 | 0.6684 | 0.5 | 0.9242 | 0.875 | 0.9693 | 0.5836 | 0.9367 |

401 actually **wins chamfer (0.7435)** and elongation (0.957) vs 868. 868 wins because listing `n_indents=1` matches 868 perfectly (`n_indents` part 1.0 vs 401 0.5) and because 401's OS pool is itself `shape=irregular` with poor solidity match (0.668). The true AGS lap pool is elongated; OS over-irregularised 401 while 868 really is irregular.

**Why Top 5 succeeded:** primarily (1) pool geometry close enough on an elongated+indented listing fingerprint, (2) pool presence / POV CONFIRMED keeping 401 inside the 367, and (6) GIS stand-size (removing it drops 401 to rank **11**). Not roof layout, not driveway, not aerial, not scored pool-house spatial.

Primary Top-5 driver class: **pool geometry (useful but not unique) + stand-size supporting + shared 0.5 pads**. Not an accidental combination of only weak signals, and not a strong unique ID.

## D. False-positive analysis for Rank 1–4

### Rank 1 — Stand 868 (21 CORAL TREE DRIVE)

Highest freeze-time shape_v2 (0.8261 vs 401 0.7712) against the official oblique 043 contour. The 0.0549 shape gap × 0.36 weight = +0.0198, larger than the 0.0113 total-score gap. 868's n_indents part is 1.0 vs 401 0.5 (listing fingerprint has 1 major indent from PARTIALLY LOST spa/secondary). Pool presence, spatial pad, aerial pad, and GIS are identical. 868 loses stand_size and exterior CLIP to 401.

- Classes: pool geometry false positive, segmentation error, scoring-weight issue, genuine visual similarity
- **A vs B:** B primary (incorrect/misinterpreted listing contour: PARTIALLY LOST / freeform irregular official shape matches 868's curved backyard pool better than 401's rectilinear lap pool). A secondary: both are in-parcel elongated-ish YES pools, so shape_v2 is allowed to fire.

- Pool: CONFIRMED 24.73 m² aspect 1.882 shape=irregular CLIP pool=0.9638
- Building: CONFIRMED 324.82 m²  | driveway: PROBABLE side=north
- Pool–house: NW -116.93°  10.16 m  nearest_edge=0.0599 area_ratio=0.0761
- Corner: UNKNOWN (dual_frontage_nearly_parallel_not_confirmed_corner, roads=['TAMBOTIE ROAD', 'CORAL TREE DRIVE'])

shape_v2 parts:

| elongation | chamfer | hu | solidity | n_indents | max_indent | n_corners | circularity | sharp_frac | radial_cv |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.9349 | 0.7137 | 0.6333 | 0.8538 | 1.0 | 0.9656 | 0.875 | 0.7682 | 0.7222 | 0.9 |

### Rank 2 — Stand 624 (17 CAMELS FOOT DRIVE)

shape_v2 0.7777 vs 401 0.7712 and the closest Top-5 GIS size (886 vs advertised 897; size_score 0.9727 vs 0.9455). Exterior CLIP also slightly higher (0.7827 vs 0.7724). Candidate pool is 80.66 m² — scale-invariant shape_v2 does not penalise that.

- Classes: genuine visual similarity, pool geometry false positive, house/roof mismatch not sufficiently penalised, scoring-weight issue
- **A vs B:** A: elongated in-parcel pool and near-897 GIS size are correct evidence that happens to favour a wrong house. B: listing lap-pool scale is not in Scoring v2, so an 81 m² pool is treated as the same shape family as a ~23 m² lap pool.

- Pool: CONFIRMED 80.66 m² aspect 2.866 shape=elongated_rectangular CLIP pool=0.9544
- Building: CONFIRMED 366.0 m²  | driveway: PROBABLE side=south
- Pool–house: N -82.18°  10.99 m  nearest_edge=0.0096 area_ratio=0.2204
- Corner: NO (single_road_frontage_not_corner, roads=['CAMELS FOOT DRIVE'])

shape_v2 parts:

| elongation | chamfer | hu | solidity | n_indents | max_indent | n_corners | circularity | sharp_frac | radial_cv |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.8608 | 0.7047 | 0.298 | 0.9556 | 1.0 | 0.9608 | 1.0 | 0.7035 | 0.9307 | 0.9035 |

### Rank 3 — Stand 648 (4 KIAAT END)

shape_v2 0.7902 vs 401 0.7712. OS building footprint is only 138 m² against listing floor 672 m²; pool is 20.77 m from house (nearest_edge_norm 0.462) vs listing photos of a house-adjacent lap pool. spatial_v2 was padded 0.5 for everyone, so this mismatch did not cost 648.

- Classes: segmentation error, pool-house spatial mismatch not sufficiently penalised, house/roof mismatch not sufficiently penalised, missing-data advantage
- **A vs B:** B: undersized building mask and far pool-house geometry are incorrect/incomplete evidence that Scoring v2 could not use because listing spatial was omitted and building is not a v2 term. A: the elongated pool contour still legitimately scores on shape_v2.

- Pool: CONFIRMED 44.8 m² aspect 2.635 shape=elongated_rectangular CLIP pool=0.9696
- Building: CONFIRMED 138.1 m²  | driveway: PROBABLE side=west
- Pool–house: W 162.95°  20.77 m  nearest_edge=0.462 area_ratio=0.3244
- Corner: NO (cul_de_sac_single_frontage_not_corner, roads=['KIAAT END'])

shape_v2 parts:

| elongation | chamfer | hu | solidity | n_indents | max_indent | n_corners | circularity | sharp_frac | radial_cv |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.9719 | 0.7199 | 0.2753 | 0.9869 | 1.0 | 0.791 | 1.0 | 0.7233 | 0.9307 | 0.8232 |

### Rank 4 — Stand 545 (15 BUFFALO THORN DRIVE)

Highest exterior CLIP in the Top 5 (0.8046 vs 401 0.7724) plus near-tie shape_v2 (0.7685 vs 0.7712) and near-identical stand_size (918 vs 919 m²). Parcel is a confirmed corner (Buffalo Thorn × Black Monkey Thorn); listing CORNER=UNKNOWN so Corner Gate was a no-op. Driveway OS=UNKNOWN.

- Classes: genuine visual similarity, CLIP failure, driveway/context mismatch, parcel/context mismatch
- **A vs B:** A: same-street elongated pool and 918 m² GIS are correct weak evidence. B: CLIP exterior prefers a light/white-roof corner house over the listing charcoal cubist front; driveway UNKNOWN is not penalised; corner mismatch is ungated because listing corner evidence was insufficient.

- Pool: CONFIRMED 38.81 m² aspect 2.34 shape=elongated_rectangular CLIP pool=0.9788
- Building: CONFIRMED 485.61 m²  | driveway: UNKNOWN side=None
- Pool–house: NW -127.76°  16.69 m  nearest_edge=0.0073 area_ratio=0.0799
- Corner: YES (two_distinct_road_facing_sides_at_intersection, roads=['BLACK MONKEY THORN DRIVE', 'BUFFALO THORN DRIVE'])

shape_v2 parts:

| elongation | chamfer | hu | solidity | n_indents | max_indent | n_corners | circularity | sharp_frac | radial_cv |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.932 | 0.7237 | 0.4168 | 0.9109 | 0.75 | 0.812 | 0.875 | 0.7615 | 0.9304 | 0.7303 |

## E. Component-level score comparison

| component | w | 868 | 624 | 648 | 545 | 401 GT |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| total | 1.00 | 0.7265 | 0.72 | 0.7184 | 0.7163 | 0.7152 |
| shape_v2 raw | 0.36 | 0.8261 | 0.7777 | 0.7902 | 0.7685 | 0.7712 |
| shape_v2 contrib |  | 0.2974 | 0.28 | 0.2845 | 0.2767 | 0.2776 |
| pool_presence contrib | 0.14 | 0.14 | 0.14 | 0.14 | 0.14 | 0.14 |
| spatial_v2 contrib (pad) | 0.22 | 0.11 | 0.11 | 0.11 | 0.11 | 0.11 |
| aerial contrib (pad) | 0.12 | 0.06 | 0.06 | 0.06 | 0.06 | 0.06 |
| exterior raw CLIP | 0.06 | 0.7451 | 0.7827 | 0.715 | 0.8046 | 0.7724 |
| exterior contrib |  | 0.0447 | 0.047 | 0.0429 | 0.0483 | 0.0463 |
| gis contrib | 0.03 | 0.015 | 0.015 | 0.015 | 0.015 | 0.015 |
| stand_size raw | 0.07 | 0.8489 | 0.9727 | 0.943 | 0.948 | 0.9455 |
| stand_size contrib |  | 0.0594 | 0.0681 | 0.066 | 0.0664 | 0.0662 |
| OS pool m² |  | 24.73 | 80.66 | 44.8 | 38.81 | 22.54 |
| OS pool aspect |  | 1.882 | 2.866 | 2.635 | 2.34 | 2.766 |
| OS building m² |  | 324.82 | 366.0 | 138.1 | 485.61 | 429.66 |
| pool–house m |  | 10.16 | 10.99 | 20.77 | 16.69 | 12.69 |
| nearest_edge_norm |  | 0.0599 | 0.0096 | 0.462 | 0.0073 | 0.0302 |
| pool/building area |  | 0.0761 | 0.2204 | 0.3244 | 0.0799 | 0.0525 |
| driveway status |  | PROBABLE | PROBABLE | PROBABLE | UNKNOWN | PROBABLE |
| parcel corner |  | UNKNOWN | NO | NO | YES | NO |

Identical on all five: pool_presence 0.14, spatial pad 0.11, aerial pad 0.06, gis 0.015. Remaining movement is shape_v2 + small exterior/size deltas.

## F. Counterfactual results

Diagnostic rescoring of frozen `all_candidates.json` only. Official freeze ranks are not replaced. `401 frozen rank → diagnostic rank`.

| id | 401 frozen → diagnostic | Top-5 | 338 (rank 122) | 641 (unranked) |
| --- | --- | --- | --- | --- |
| `reproduce_frozen` | 5 → 5 | 868 / 624 / 648 / 545 / 401 | n/a (no high-conf pool) | never ranked |
| `remove_clip` | 5 → 5 | 868 / 648 / 624 / 901 / 401 | 122 → 121 (improves) | never ranked |
| `remove_stand_size` | 5 → 11 | 444 / 868 / 572 / 482 / 568 | 122 → 182 (damages) | never ranked |
| `omit_missing_pad` | 5 → 5 | 868 / 624 / 648 / 545 / 401 | 122 → 8 (improves) | never ranked |
| `missing_as_zero` | 5 → 5 | 868 / 624 / 648 / 545 / 401 | 122 → 124 (damages) | never ranked |
| `stronger_validated_pool` | 5 → 5 | 868 / 624 / 648 / 545 / 401 | n/a (no high-conf pool) | never ranked |
| `listing_lap_pool_upper_bound` | 5 → 4 | 868 / 648 / 545 / 401 / 444 | n/a (no high-conf pool) | never ranked |
| `building_vs_listing_floor` | 5 → 4 | 868 / 624 / 545 / 401 / 444 | n/a (no high-conf pool) | never ranked |
| `enforce_pool_house_adjacency` | 5 → 4 | 868 / 624 / 545 / 401 / 444 | n/a (no high-conf pool) | never ranked |
| `corrected_listing_contour_convex_hull` | 5 → 39 | 665 / 648 / 461 / 545 / 351 | n/a (no high-conf pool) | never ranked |
| `enforce_driveway_context` | 5 → 4 | 868 / 624 / 648 / 401 / 444 | n/a (no high-conf pool) | never ranked |

Notes:

- `reproduce_frozen` matches rank 5 / score 0.7152: stored components reconstruct the freeze.
- **Remove CLIP:** 401 stays 5; 545 leaves the Top 5 (CLIP was the term that preferred 545). 338 122→121 (tiny).
- **Remove stand_size: DAMAGES 401 5→11 and 338 122→182.** Stand-size is a useful supporting signal, not noise.
- **Omit 0.5-pad (correct UNKNOWN treatment): 401 stays 5; 338 122→8.** Largest labelled-case gain. Same Top 5 here because every YES-pool survivor has the same missing spatial/aerial.
- **Missing-as-zero: DAMAGES 338 122→124.** Omit-and-renormalise is not the same as filling 0.
- Stronger CONFIRMED-pool requirement does not separate this Top 5 (all five CONFIRMED).
- Listing-visual lap-pool upper bound (>55 m²) demotes 624 only; 401 5→4; **868 remains #1**.
- Building-vs-floor and pool-house adjacency each demote 648; 401 5→4; **868 remains #1**.
- Driveway context demotes 545 (OS UNKNOWN); 401 5→4; **868 remains #1**.
- **Convex-hull 'corrected listing contour' DAMAGES 401 5→39.** Do not ship this. 401's OS pool is itself irregular; hulling the listing fingerprint removes the indent that 401 partially shares.
- Stand 641 cannot move under scoring CFs (removed at Pool Gate).

Do **not** adopt a CF merely because it moves 401. The only CF that both (a) repairs a previous labelled miss and (b) does not scramble this Top-5 hit is **omit-null missing-data treatment**.

## G. Root-cause findings

1. **401's Top-5 placement is real.** Inventory YES, correct in-parcel pool, POV CONFIRMED, elongated geometry, and near-897 GIS size put it in a 0.011-wide Top-5 band of 367 survivors. Removing stand_size drops it to rank 11, so this is not padding luck alone.
2. **401 is not #1 because `shape_v2` (weight 0.36) is the only live discriminator.** 868's irregular 24.7 m² pool matches listing `n_indents=1` (part 1.0 vs 401 0.5) and solidity (0.854 vs 401 0.668). 401 actually wins chamfer and elongation. The official 043 contour is PARTIALLY LOST / irregular, and 401's OS contour is also irregular — a double geometry error, not a missed house.
3. **Missing spatial_v2 and aerial did not uniquely suppress 401.** Every ranked survivor received the same 0.5 pads. Flattening is real; singling out 401 is not. Omitting those pads does not change this Top 5.
4. **False positives are mixed A/B.** 624 is correct elongated-pool + size evidence plus a missing scale penalty. 868 is listing-indent / OS-irregularity (B) with some genuine elongated-pool similarity (A). 648 is unused far pool-house geometry and an undersized 138 m² building. 545 is same-street CLIP preferring a white-roof corner house.
5. **No existing Scoring v2 term would have promoted 401 to #1 without new information.** Exterior CLIP prefers 545. Stand size prefers 624. Corner is a gate and listing CORNER=UNKNOWN. Naive listing-contour hull **hurts** 401 (5→39). Colour is unused.
6. **868 remaining #1 after every justified one-component CF is the honest result.** Rank 1 among many elongated YES-pool parcels, with listing spatial/aerial absent, is the MODERATE-separation operating point. The generalisable bugs are missing-data padding (338) and unused non-shape evidence (648/624), not '401 should have been #1 with a weight tweak'.

## H. Maximum 3 recommended improvements

Prefer fixing **bad evidence / missing-data policy before weights**. None of these is selected just because it lifts 401 — two of them only move 401 5→4, and the strongest labelled-case win **does not move 401 at all**.

### 1. Omit null Scoring v2 components instead of 0.5-padding them

- **Failure mode:** REJECTED/UNKNOWN pools still receive 0.5 × shape (0.18) and 0.5 × pool_presence (0.07). Confirmed-pool false positives then beat a true stand that has aerial+size but no accepted contour.
- **This test:** 401 frozen 5 → diagnostic 5 (Top 5 unchanged). Shared pads are identical on YES-pool survivors, so omitting them does not manufacture a 401 win.
- **Earlier blinds:** **Yes — this is the PR #25 / stand 338 mechanism.** 338 frozen rank 122 → diagnostic **8** under omit-null. Filling missing as 0 instead of omitting **damages** 338 (122→124). 641 still cannot score (inventory NO); that gate issue is PR #29, already in this freeze.
- **Expected benefit:** large for canopy-hidden / REJECTED-pool true stands that still have CLIP+size. Neutral for this YES-pool Top-5 hit.
- **Regression:** when listing spatial is omitted, remaining YES-pool races become even more shape-dominated (this test: Top 5 unchanged, still 868 #1). Do not combine with dropping stand_size.
- **Complexity:** low. **Layer:** scoring missing-data policy (`score_v2` `missing='omit'`), not weight retune, not candidate generation.

### 2. One-sided listing-visual pool-scale check (not water colour, not a 401-fitted m²)

- **Failure mode:** `shape_v2` is scale-invariant, so an 81 m² pool matches a listing lap pool.
- **This test:** 624 OS pool 80.66 m² / area_ratio 0.22 vs listing photos of a narrow side-yard lap pool. CF demotes 624; 401 5→4; 868 stays #1.
- **Earlier blinds:** large-pool FPs appear whenever shape dominates and listing nadir area is omitted (`relative_area_omitted_not_nadir` on this listing).
- **Expected benefit:** demote oversized backyard pools without GT or colour.
- **Regression:** genuine large listing pools. Use an upper bound from listing frames (elongated house-adjacent lap), not a target fitted to 22.54 m².
- **Complexity:** low–moderate. **Layer:** validation / optional scoring term. Do not retune the 0.36 shape weight to hide this.

### 3. Use candidate building footprint vs listing floor, or listing-photo pool-house adjacency — not a convex-hulled fingerprint

- **Failure mode:** Scoring v2 has no building term and listing spatial was omitted, so 648 (OS building 138 m² vs floor 672; pool 20.77 m / nearest_edge 0.462) outranks 401 on shape alone.
- **This test:** either CF demotes 648; 401 5→4; 868 stays #1.
- **Earlier blinds:** OS undersized buildings are a known inventory diagnostic (`undersized_building` / `MIN_BUILDING_AREA_M2_FOR_NO=180`). Pool-house spatial omitted on oblique fingerprints is the Hybrid v1 viewpoint rule that flattened every complete-estate freeze.
- **Expected benefit:** catch segmentation-too-small houses and far-yard pools when listing photos show a large house and a house-adjacent lap pool.
- **Regression:** single-storey vs two-storey floor/footprint; do not infer listing spatial from GT 401's OS vector. Convex-hull 'fix' of 043 is **rejected** (401 5→39).
- **Complexity:** moderate. **Layer:** validation / optional spatial fill from listing ground-level frames 044/046, not GT, not colour, not weight bump.

Not recommended: retuning Scoring v2 weights; adding water colour; using Stand 401 as candidate-generation or fingerprint input; promoting CLIP (preferred 545); removing stand_size; convex-hulling the official contour.

## I. GO / NO-GO for another blind test

**GO for another freeze-only blind on the current stack. NO-GO for a scoring-changed or 401-targeted blind.**

Reasons:

- This is the first independently recovered **Top-5 hit**. That is a positive MODERATE-separation result, not a reason to retune on one GT.
- Rank 1–4 errors are **not** all 'genuinely similar houses', but they are also **not** all fixable by a weight change. 868 remains #1 after every justified one-component CF. Treating 868 as a bug to squash on this GT would overfit the listing indent.
- The one CF that strongly helps a previous labelled miss (338 122→8) **does not change this freeze Top 5**. It can be prototyped on a **separate freeze-only** listing after this next blind, not merged into production now.
- Inventory v1.1.0 / POV / Corner Gate / Scoring v2 weights should stay frozen as they were at `5aa42ec`.

If the next listing again has only an oblique pool_overview fingerprint and no aerial, expect another shape-dominated Top 5, not a guaranteed Rank 1.

