# Blind Carlswald North diagnostic — Property24 116273255

**Status:** ranks frozen. No scoring retune. Listing Evidence v2 not used. No stand number entered candidate generation or scoring.

| Constraint | Value |
|---|---|
| Listing | [116273255](https://www.property24.com/for-sale/carlswald-north-estate/midrand/gauteng/12743/116273255) |
| Estate | Carlswald North, 330 candidates |
| Crops | frozen native15 |
| OS | frozen Object Segmentation v1 JSON |
| Rankers | frozen production `combined_score`; PR #5 0.5-neutral; PR #6 Scoring v2 (`missing=neutral`, no building); PR #7 multi-image **unchanged** |
| Text “L-shaped pool” | recorded as listing evidence only — not a stand filter |
| Eval stand | unused |

Artefacts: `latest.json`, `listing_images.json`, `listing_text.json`, `listing_pool_fingerprint.json`, `all_candidates.json`, `pr7_observations.json`, `panels/listing/`, `panels/candidates/`. Listing JPEGs are gitignored under `photos/`.

Overlays for `019`, `037`, `038`, `043` were drawn **after** ranks froze (the runner capped listing overlays at 16 frames). Extraction used the same frozen `extract_pool_geometry`. Scores were not recomputed.

---

## A. Baseline Top 5

Frozen production / native15 `combined_score`. **LOW CONFIDENCE.** `#1` = **1/510** (0.7897). `#1–#2` margin = **0.0400**. `#1–#10` gap = **0.0844**.

| Rank | Stand | Score | OS pool | OS shape | Blob | Geom | Size | Area m² |
|---:|---|---:|---|---|---|---:|---:|---:|
| 1 | 1/510 | 0.7897 | REJECTED | elongated_rectangular | yes | 0.789 | 0.991 | 502 |
| 2 | 585 | 0.7497 | PROBABLE | kidney_or_curved | yes | 0.866 | 0.000 | 1213 |
| 3 | 635 | 0.7359 | REJECTED | irregular | yes | 0.834 | 0.000 | 1017 |
| 4 | 622 | 0.7308 | CONFIRMED | irregular | yes | 0.854 | 0.000 | 885 |
| 5 | 2/379 | 0.7287 | UNKNOWN | — | yes | 0.778 | 1.000 | 500 |

Major baseline drivers: blob `pool_geometry_similarity` against a smeared listing fingerprint, plus **stand-size ≈ 500 m²** on EXT.6 `1/xxx` / `2/379`. CLIP aerial is always null (no listing aerial). Exterior CLIP only on the geom shortlist of 40, so several high ranks have `exterior=null`.

Visual: **1/510 has no in-parcel pool.** The red blob sits on a patio/courtyard; a neighbour across the road has a rectangular pool. OS correctly REJECTED. Size match (502 vs 500) still made it `#1`.

---

## B. Scoring v2 Top 5

Frozen PR #6, `V2_WEIGHTS_NO_BUILDING`, `missing="neutral"`. **LOW CONFIDENCE.** `#1` = **1/334** (0.7372). `#1–#2` margin = **0.0184**. `#1–#10` gap = **0.1213**.

| Rank | Stand | Score | OS pool | OS shape | spatial_v2 | Size | Area m² | Top contribs |
|---:|---|---:|---|---|---:|---:|---:|---|
| 1 | 1/334 | 0.7372 | PROBABLE | kidney_or_curved | 0.990 | 0.911 | 520 | spatial_v2 0.218, shape_v2 0.211, presence 0.140, size 0.064 |
| 2 | 1/389 | 0.7188 | PROBABLE | irregular | 0.866 | 0.938 | 514 | shape_v2 0.218, spatial_v2 0.191, presence 0.140, size 0.066 |
| 3 | 1/450 | 0.7083 | PROBABLE | rectangular | 0.900 | 0.871 | 529 | shape_v2 0.204, spatial_v2 0.198, presence 0.140, size 0.061 |
| 4 | 365 | 0.6554 | CONFIRMED | kidney_or_curved | 0.790 | 0.000 | 970 | shape_v2 0.237, spatial_v2 0.174, presence 0.140 |
| 5 | 582 | 0.6505 | PROBABLE | irregular | 0.729 | 0.000 | 1002 | shape_v2 0.245, spatial_v2 0.160, presence 0.140 |

Aerial and missing OS terms are 0.5-filled (contrib aerial 0.060, exterior 0.030 when CLIP is absent). That is the same false-confidence path as 116978058, now with a **strong size term** because this listing is 500 m².

Visual: **1/334 does not contain an in-parcel pool.** The PROBABLE kidney mask sits on the **brown roof**. Neighbour pools are visible and unmasked. Rank is size + spatial_v2 0.99 against junk listing geometry.

---

## C. Best confidence achieved

**None of the four rankers leave LOW CONFIDENCE.**

| Ranker | #1 | Score | #1–#2 margin | #1–#10 gap | Confidence |
|---|---|---:|---:|---:|---|
| Baseline | 1/510 | 0.7897 | **0.0400** | 0.0844 | low |
| PR #5 0.5-neutral | 528 | 0.7342 | 0.0041 | 0.0435 | low |
| Scoring v2 | 1/334 | 0.7372 | 0.0184 | 0.1213 | low |
| PR #7 multi-image | 1/389 | 0.7476 | 0.0251 | 0.1253 | low |

Largest `#1–#2` is baseline 0.0400, which still fails the top-10 gap rule. Scoring v2 / PR #7 have larger top-10 gaps but `#1–#2` stays under 0.04. **Best confidence: low.** Do not treat any `#1` as a match.

---

## Phase 1 — Listing acquisition

| Field | Value |
|---|---|
| Title | 3 Bedroom House, Carlswald North Estate |
| Beds / baths | 3 / 2.5 |
| Advertised stand size | **500 m²** |
| Image URLs / acquired | 51 / **51** |
| Scene counts | interior 33, contextual 6, driveway_access 6, pool_garden 3, rear_elevation 2, front_elevation 1 |
| Exterior shortlist | **18** |
| Pool-related (frozen POOL_SCENES) | **11** |
| Aerial / elevated | **0** |
| Pool text | “The patio overlooks a sparkling **L-shaped pool with a cover and net**, and a timber deck…” |
| Used to select a stand | **false** |

---

## Phase 2 — Frozen listing evidence (not LEV2)

Consensus fingerprint (`consensus_from_10_pool_frames`):

- present, **shape = irregular**
- compactness **0.1303**, rectangularity 0.4904, convexity 0.6557, aspect 2.403
- pool–house dist 0.4349
- **Not L-shaped. Not rectilinear.** Same smear class as 116978058.

PR #7 fusion (unchanged): 16 `pool_present` frames; **shape_from `007`**; **spatial_from `002`**; fused still irregular, compactness 0.1863, aspect 1.463; scale median 0.4534 from close-up/oblique ratios. No frame is nadir-safe.

### Useful pool / exterior frames

Nadir-safe is **false for every listing image**.

| ID | Class | Pool | Contour | Shape | Spatial | Scale | Nadir-safe reason | In consensus | What the photo actually is |
|---|---|---|---:|---|---|---|---|---|---|
| 001 | contextual | no | — | unknown | no | no | no_pool_detected | yes | estate / context |
| 002 | contextual | **yes** | 0.048 | irregular | **yes** | no | smeared_low_compactness | yes | **agent headshot**; contour on black polo |
| 003 | contextual | yes | 0.157 | irregular | yes | no | smeared_low_compactness | yes | **front elevation**; contour on sky/canopy |
| 004 | front_elevation | no | — | unknown | no | no | no_pool_detected | no | front / driveway (correct class) |
| 005 | contextual | yes | 0.165 | irregular | yes | no | smeared_low_compactness | yes | front-of-house family; false water |
| 006 | contextual | yes | 0.089 | irregular | yes | no | smeared_low_compactness | yes | **front elevation** (misclassed contextual) |
| 007 | contextual | yes | 0.186 | irregular | yes | no | oblique_ground_or_garden_view | yes | **front elevation**; contour on grey wall/balcony. **PR7 shape source** |
| 008 | pool_garden | yes | 0.130 | irregular | yes | no | smeared_low_compactness | yes | **true L-pool**; contour climbs the pillar |
| 009 | driveway_access | yes | 0.098 | irregular | yes | no | smeared_low_compactness | no | driveway; false pool |
| 010 | driveway_access | yes | 0.255 | irregular | yes | no | scene_driveway_access_not_nadir | no | interior-looking / driveway; false pool. In PR7 scale set |
| 019 | rear_elevation | yes | 0.111 | irregular | yes | no | smeared_low_compactness | yes | **interior foyer** (misclassed rear); no pool |
| 037 | pool_garden | yes | 0.097 | irregular | yes | no | smeared_low_compactness | yes | **true L-pool with cover/net**; contour jagged, climbs pillar, eats planter |
| 038 | pool_garden | yes | 0.059 | irregular | yes | no | smeared_low_compactness | yes | **true L-pool**, open water; contour bleeds up the house wall |
| 043 | rear_elevation | yes | 0.150 | irregular | yes | no | smeared_low_compactness | yes | rear/garden family; smear |

All **6 driveway_access** frames have `pool_detected=true`. **30 of 33 interiors** have `pool_detected=true` (windows, rugs, dark furniture). Interiors are excluded from frozen consensus via `POOL_SCENES`, but they still enter **PR #7** `observe_listing_image` whenever `pool_present`.

The three genuine pool_garden frames (008, 037, 038) all detect a pool and all emit **irregular** with compactness 0.06–0.13. The L is visible to a person; the contour never follows the coping.

---

## Phase 3 — Blind 330-candidate ranking

### PR #5 0.5-neutral Top 5 (and Top 20 OS)

`#1` **528** 0.7342, margin **0.0041**.

| Rank | Stand | Score | OS pool | OS shape | Notes |
|---:|---|---:|---|---|---|
| 1 | 528 | 0.7342 | CONFIRMED | irregular | FP orange mask on patio/roof; **true rectangular pool in the same yard is unmasked** |
| 2 | 582 | 0.7301 | PROBABLE | irregular | lawn blob + neighbour-pool orange |
| 3 | 573 | 0.7291 | PROBABLE | irregular | blob_pool_present **false**; contradiction `listing_has_pool_candidate_has_none`; actual **narrow lap pool** poorly masked |
| 4 | 446 | 0.7108 | PROBABLE | irregular | |
| 5 | 1/384 | 0.7084 | PROBABLE | irregular | size 0.50; contradiction `pool_on_opposite_side_of_house` |

Top 20 OS: mostly CONFIRMED/PROBABLE **irregular** or kidney. Two kidney CONFIRMED (667, 352). Stand 365 (CONFIRMED kidney) is PR5 #16 — it is **not an input**; it merely scores against the smeared irregular listing fingerprint.

### PR #7 multi-image (unchanged) Top 5

`#1` **1/389** 0.7476, margin 0.0251.

| Rank | Stand | Score | OS pool | OS shape |
|---:|---|---:|---|---|
| 1 | 1/389 | 0.7476 | PROBABLE | irregular |
| 2 | 457 | 0.7225 | CONFIRMED | irregular |
| 3 | 1/334 | 0.6943 | PROBABLE | kidney_or_curved |
| 4 | 1/384 | 0.6782 | PROBABLE | irregular |
| 5 | 1/691 | 0.6444 | CONFIRMED | irregular |

Fusion used **junk sources**: shape = front-wall smear on 007; spatial = polo-shirt contour on agent portrait 002. That is why PR #7 does not recover the L-pool and still promotes ~500 m² EXT.6 stands plus 457 (also a 116978058 distractor).

### Baseline / Scoring v2 Top 20 OS (summary)

Baseline Top 20 is dominated by **blob geom + size**, with OS REJECTED/UNKNOWN on many high ranks (1/510, 635, 2/379, 656, 652, 514, 363). Scoring v2 Top 20 is dominated by **PROBABLE/CONFIRMED + size** on EXT.6 `1/xxx` stands (~500–530 m²) and a handful of larger CONFIRMED irregular/kidney/rectangular pools. No Top 20 OS label is `L-shaped` — the frozen OS vocabulary has no L class.

---

## Phase 4 — Shortlist inspection (ranks already frozen)

Inspected native15 OS panels for the union of each ranker’s Top 10, plus listing overlays.

### Does the candidate contain an in-parcel pool?

| Stand | Role | In-parcel pool? | OS vs photo | House / driveway | Neighbour / mask issues |
|---|---|---|---|---|---|
| 1/510 | baseline #1 | **No** | REJECTED patio blob | ordinary brown-roof house, not charcoal glass facade | neighbour rectangular pool across the road |
| 585 | baseline #2 | dark/covered backyard blob | PROBABLE kidney | not the listing facade | bright neighbour rectangle to the west |
| 635 | baseline #3 | **No** | REJECTED irregular backyard blob | — | neighbour rectangle unmasked |
| 622 | baseline #4 | dark backyard feature | CONFIRMED irregular smear | not distinctive | neighbour rectangle north |
| 2/379 | baseline #5 | **No clear water** | UNKNOWN blob | size-only | blob on patio/lawn |
| 1/334 | v2 #1 | **No** | PROBABLE kidney **on the roof** | brown tiles | two neighbour pools in crop |
| 1/389 | v2 #2 / PR7 #1 | elongated in-parcel pool | PROBABLE irregular; patio attached as second blob | dark roof, SUV on street — **not** the listing’s glass garage / cypress/palm front | neighbour rectangle east |
| 1/450 | v2 #3 | small backyard blob | PROBABLE rectangular | corner T-junction house | neighbour rectangle north, unmasked |
| 365 | v2 #4 | **yes, bright rectangle** | CONFIRMED kidney **offset onto deck**; actual rectangle missed | other-listing geometry | OS class/shape wrong |
| 528 | PR5 #1 | **yes, light rectangle in SW lawn** | CONFIRMED irregular is a **patio/roof FP**; true pool unmasked | brown gables | missed pool |
| 582 | PR5 #2 | rectangle in yard, poorly used | PROBABLE irregular on **lawn**; orange on **neighbour pool** | — | neighbour-pool contamination |
| 573 | PR5 #3 | **yes, long narrow lap pool** | PROBABLE irregular smear | — | blob extractor said absent |
| 457 | PR7 #2 | **yes, rectangle** | CONFIRMED **irregular** over a clearly rectangular pool | solar panels; not listing style | neighbour rectangles in crop |

**None of the Top 5 in baseline or Scoring v2 looks like this listing:** modern charcoal facade, double-volume glass, stone pillar, herringbone driveway, glass garage, L-pool wrapping a structural corner with timber deck.

Building-footprint and driveway evidence did not pull the distinctive frontage into the shortlist. OS driveway is UNKNOWN on several size-driven `#1`s.

---

## Phase 5 — Failure modes

### Seen again (same family as 116978058)

1. Listing water contour **smears** → generic **irregular**, compactness ~0.13.
2. Oblique listing vs nadir OS shape mismatch; **no nadir-safe listing frame**.
3. Baseline `#1` with **OS REJECTED** still wins via blob geom + another cue (here: size instead of CLIP).
4. Scoring v2 **0.5-fills** missing aerial/OS → compressed scores, low `#1–#2`.
5. PR #7 fusion picks a **high spatial_quality junk frame**.
6. Straight-edged water poorly represented by contour descriptors (457 rectangle → irregular; 573 lap pool → irregular).
7. Neighbour pools in native15 crops; some orange masks sit off-parcel (582).
8. False confidence from missing terms.

### New on 116273255 (not the 116978058 octagon/jacuzzi story)

1. **Agent portrait as pool evidence.** `002` is a headshot on neon green. Frozen classifier: `contextual`. Extractor: `pool=1` on the polo shirt. PR #7 **spatial_source = 002** (spatial_quality 0.95).
2. **Front-elevation glass / sky / wall as water.** `003` contour on sky/canopy; `007` contour on grey wall — and **007 is PR #7 shape_source**. Several “contextual” frames are actually the front of the house.
3. **Interior false pools at scale.** 30/33 interiors `pool_detected=true`. `019` is an interior foyer labelled `rear_elevation` and used in consensus.
4. **L-shape wrapping a house pillar.** The real pool is rectilinear L, inner corner occupied by a square column. Contours **climb the pillar** (008, 037, 038). Frozen extractor has **no L class**; even a clean L would likely dump to irregular. Pillar occlusion is extra.
5. **Cover and net.** 037 shows the advertised net; 008/038 are open water. Net + hard shadow on 037 add jagged boundaries. Cover/net is a new water-appearance mode vs the dark reflective octagon on 116978058.
6. **500 m² stand-size term is now material.** Listing 116978058 was ~972 m² so size was weak. Here size_score ≈ 0.9–1.0 on EXT.6 `1/510`, `1/334`, `1/389`, `1/450`, `2/379` and **promotes stands with no plausible pool**. That is a new ranking failure, not just a listing-extraction failure.
7. **OS roof-as-pool as Scoring v2 `#1`.** 1/334 kidney PROBABLE is the house roof. Combined with size + spatial_v2 0.99 this is a sharper OS-error × scorer interaction than 116978058.
8. **OS CONFIRMED on the wrong object while a real pool sits unmasked** (528). Presence/shape terms then reward the FP.
9. **No listing aerial at all**, so CLIP aerial never fires; v2 always 0.5-fills it.
10. **Driveway class does not imply no-pool.** All six driveway frames still emit pool contours, and several enter PR #7 scale.

---

## D. Does the listing extractor recognise the L-shaped pool?

**No.**

Text extraction correctly records `advertises_l_shaped_pool=true` and cover/net. That text is **not** applied to shape class (by design).

Vision: the three real pool_garden frames show an L to a person. Frozen `extract_pool_geometry` / consensus / PR #7 fusion all emit **irregular**. Compactness 0.06–0.19. No frame is nadir-safe. PR #7 does not even use a real pool photo for shape or spatial — it uses a wall smear and a headshot.

---

## E. Do the top candidates visually make sense?

**No.**

- Baseline `#1` 1/510: no pool; patio blob; size match.
- Scoring v2 `#1` 1/334: roof labelled kidney pool; size match.
- PR #5 `#1` 528: confirmed irregular is not the pool that is actually in the yard; that pool is a simple rectangle, not an L wrapping a pillar.
- PR #7 `#1` 1/389: has some in-parcel water, but elongated/irregular, ~514 m², and the house is not the listing’s charcoal glass frontage.

The shortlists are mixed false pools, neighbour contamination, and size-driven EXT.6 stands. They are not a coherent visual match to 116273255.

---

## F. New failure modes vs 116978058

See Phase 5 “New on 116273255”. Short list:

- Portrait / non-property photo → pool contour → PR7 spatial.
- Front facade / sky / wall → pool contour → consensus and PR7 shape.
- Interior misfiled as rear_elevation → consensus.
- L wrapping a pillar → contour climbs the wall.
- Pool net/cover on an otherwise clear L.
- 500 m² size term promoting no-pool EXT.6 stands.
- Roof-as-pool as Scoring v2 `#1`.
- CONFIRMED OS mask on patio while the real pool is unmasked.

This listing **reproduces** smear-to-irregular and missing-term false confidence, and **adds** scene-gating failures plus a live stand-size failure that 116978058 could not show.

---

## G. Recommended next technical change — if any

**Do not retune production, OS v1, PR #5, PR #6, or PR #7 from this result.** Do not try to force this listing to Top 1.

The bottleneck is still **listing evidence**, but it is not the same bottleneck as “recover octagon from dark water.”

Recommended next change, in order:

1. **Gate what may emit a pool contour at all** (listing-side, before any L-shape work):
   - drop person/portrait / agent-branding frames;
   - do not extract water from `front_elevation` / `driveway_access` unless a pool is actually in view;
   - keep interiors out of consensus **and** out of PR #7 fusion (LEV2 viewpoint gating was aimed at this; this listing shows it is not optional).
2. **Only then** recover rectilinear / L geometry from remaining true `pool_garden` frames: coping-first, do not climb vertical walls, optional compound-rectangle / L class. Running L-recovery on 007’s wall smear or 002’s shirt would be wasted.
3. After listing evidence is trustworthy, **revisit stand-size**: 5% support is enough to crown a 502 m² stand with no pool when geom is junk. That is a scoring-policy issue, but it should wait until the listing fingerprint is no longer a smear. Do not raise size weight.

Listing Evidence v2 remains the right vehicle for (1)–(2). This diagnostic is the reason to include **portrait rejection and front-elevation water rejection**, not only interior/close-up gating from 116978058.
