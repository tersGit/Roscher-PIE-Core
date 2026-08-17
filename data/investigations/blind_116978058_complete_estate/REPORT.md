# Blind PIE benchmark — listing 116978058 on `carlswald_north_corrected_002`

Distinctive pool-shape stress test on the frozen complete-estate stack. No detector, weight, inventory, or Pool Gate changes. FastSAM 768/1024 was not run.

- **Freeze path:** `data/investigations/blind_116978058_complete_estate/freeze.json`
- **On-disk SHA256** (matches `freeze.sha256`): `8cf975a7a14326c520dbfcdba48a73d24df6e3605de1632d6174abab72d97628`
- **Official score:** Scoring v2 × Hybrid Pool Geometry v1 (`hybrid_v2`)
- **Universe:** 400 unique erven (Summerset EXT.3 + EXT.6 + EXT.13)
- **Ground truth applied to ranking:** no
- **Prior `116978058` artifacts used as ranking input:** excluded (frozen Hybrid JSON block skipped; photos downloaded fresh)
- **Geometry-discrimination class:** **WEAK DISCRIMINATION**
- **Identity class:** **NOT DETERMINABLE**

## A. Preserve blindness

Before freeze, no street / stand / erf-number / coordinate / archived-identity search was run. Prior PIE paths for this listing were inventoried by path only and excluded from ranking input, including:

- `data/investigations/hybrid_listing_pool_geometry_v1/` (frozen JSON contains this listing; **not used**)
- `data/investigations/hybrid_geometry_ranking_test/116978058/`
- `data/investigations/os_scoring_v2/carlswald_north_116978058/`
- `data/investigations/os_v1_ranking_experiment/carlswald_north_116978058/`
- `data/investigations/carlswald_north_corrected/116978058/`
- pool-boundary and listing-evidence v2 artefacts

Hybrid geometry was extracted fresh with frozen Hybrid v1. Colour was not a ranking signal.

## B. Listing acquisition

**Fresh** Property24 fetch. Destination photo directory was empty; **59/59 images downloaded fresh**, 0 reused from disk, 0 failed. Video absent. Title / street / stand omitted from freeze.

| Field | Value |
| --- | --- |
| Listing ID | 116978058 |
| Property type | House |
| Estate | Carlswald North Estate |
| Erf size | 972 m² |
| Floor size | 449 m² |
| Bedrooms | 4 |
| Listing photo URLs | 59 (59 downloaded fresh) |
| Video | no |
| Exterior (CLIP) | 13 |
| Pool (`pool_garden`) | 5 (`003`, `005`, `018`, `019`, `026`) |
| Driveway/garage | 8 |
| Garden/patio | 8 |
| Interior | 41 |
| Aerial CLIP scenes | **0** |
| CLIP other | contextual 3, front_elevation 1, rear_elevation 1 |

Feature hits from redacted text: swimming pool, landscaped. Pool images exist from several backyard viewpoints (wide garden overviews plus closer patio/spa frames). No nadir/aerial listing photo.

## C. Pool Gate

Listing **POOL = YES** from listing evidence **before** viewing estate candidates (`text_and_media_independently_support_private_pool`).

Independent evidence (colour not used):

- listing text mentions a swimming pool
- Hybrid v1: **3 scoring-ready** frames; 5 pool viewpoints
- CLIP: 5 `pool_garden` photos
- listing-pool-object: 4/7 observed frames detected (`003`, `005`, `018`, `026`), all with L-geometry flags

Unchanged Pool Gate on frozen 002 inventory:

| | Count |
| --- | ---: |
| Starting candidates | 400 |
| NO removed | 68 |
| YES survivors | 118 |
| UNKNOWN survivors | 214 |
| Final survivors | **332** |
| Reduction | 17.0% |

Inventory labels were not altered.

## D. Distinctive pool fingerprint

Official Hybrid v1 contour used in ranking: **`116978058-026`** (`yoloe_sam2`, `pool_overview`).

The listing photos show a **non-rectangular backyard pool**: elongated planform, near-side kinks, a spa/jacuzzi adjacent, water-feature edge. That visual distinctiveness did **not** survive into the official Hybrid contour.

| Metric | Official ranking contour |
| --- | --- |
| Shape class | `elongated_rectangular` |
| Aspect (contour_descriptors elongation) | 2.432 |
| Hybrid aspect | 3.516 |
| Major bends / indents | **0** |
| Max indent | 0.0734 (below major-indent threshold) |
| Solidity / convexity | 0.9684 / 0.9684 |
| Circularity | 0.6263 |
| Compactness (hybrid geom) | 0.3862 |
| Orientation (oblique image, not nadir bearing) | −81.76° |
| n_corners | 5 |
| Major directional changes (>40°) | 7 |
| Relative limb lengths | long axis ≈ 1.00 / 0.95; short axis ≈ 0.47 / 0.35 |
| L / T / kidney / freeform (reporting labels) | elongated + compact_rounded; **not** L/T/kidney/freeform |
| Normalized contour | 64 PCA-aligned points in `freeze.json` |
| Pool-to-house relationship | not genuinely measurable in frozen Hybrid v1 |

Proof: `listing_pool_contour_proof.png` (listing photo + cyan overlay vs normalized contour). All three Hybrid scoring-ready frames (`005`, `026`, `059`) have **0 major indents** and solidity ≥ 0.957. Listing-pool-object L-flags were **not** the official ranking contour.

Colour not used. Spatial pool–house omitted.

## E. Frozen Top 20

Official `hybrid_v2` on 332 survivors. Frozen stack unchanged (OS v1, FastSAM `imgsz=512`, native15, CLIP thresholds, Hybrid v1, Scoring v2, stand-size weight, spatial/aerial/GIS defaults, Pool Gate, inventory labels).

| Rank | Stand | Ext | Inv | OS pool | Score | shape_v2 | aerial | exterior | stand_size contrib | Neutral/default |
| ---: | --- | --- | --- | --- | ---: | ---: | --- | ---: | ---: | --- |
| 1 | 351 | EXT.6 | YES | CONFIRMED | 0.7524 | 0.8701 | default 0.5 | 0.7516 | 0.0690 | spatial 0.11 + aerial 0.06 + gis 0.015 |
| 2 | 380 | EXT.6 | YES | CONFIRMED | 0.7453 | 0.8626 | default 0.5 | 0.7701 | 0.0636 | same |
| 3 | 468 | EXT.6 | YES | CONFIRMED | 0.7433 | 0.8488 | default 0.5 | 0.7503 | 0.0678 | same |
| 4 | 463 | EXT.6 | YES | CONFIRMED | 0.7430 | 0.8483 | default 0.5 | 0.7416 | 0.0681 | same |
| 5 | 461 | EXT.6 | YES | CONFIRMED | 0.7415 | 0.8415 | default 0.5 | 0.7386 | 0.0692 | same |
| 6 | 874 | EXT.3 | YES | CONFIRMED | 0.7396 | 0.8483 | default 0.5 | 0.7632 | 0.0634 | same |
| 7 | 428 | EXT.6 | YES | CONFIRMED | 0.7304 | 0.8125 | default 0.5 | 0.7449 | 0.0682 | same |
| 8 | 648 | EXT.13 | YES | CONFIRMED | 0.7303 | 0.8346 | default 0.5 | 0.7197 | 0.0617 | same |
| 9 | 365 | EXT.6 | YES | CONFIRMED | 0.7268 | 0.8008 | default 0.5 | 0.7302 | 0.0697 | same |
| 10 | 897 | EXT.3 | YES | CONFIRMED | 0.7267 | 0.8097 | default 0.5 | 0.7447 | 0.0655 | same |
| 11 | 666 | EXT.13 | YES | CONFIRMED | 0.7264 | 0.7949 | default 0.5 | 0.7567 | 0.0698 | same |
| 12 | 624 | EXT.13 | YES | CONFIRMED | 0.7241 | 0.8259 | default 0.5 | 0.7594 | 0.0562 | same |
| 13 | 899 | EXT.3 | YES | CONFIRMED | 0.7237 | 0.8087 | default 0.5 | 0.7590 | 0.0620 | same |
| 14 | 672 | EXT.13 | YES | CONFIRMED | 0.7207 | 0.7749 | default 0.5 | 0.7876 | 0.0695 | same |
| 15 | 901 | EXT.3 | YES | CONFIRMED | 0.7153 | 0.8028 | default 0.5 | 0.6765 | 0.0607 | same |
| 16 | 545 | EXT.6 | YES | CONFIRMED | 0.7145 | 0.7847 | default 0.5 | 0.7614 | 0.0614 | same |
| 17 | 665 | EXT.13 | YES | CONFIRMED | 0.7142 | 0.7927 | default 0.5 | 0.7579 | 0.0583 | same |
| 18 | 535 | EXT.6 | YES | CONFIRMED | 0.7111 | 0.7618 | default 0.5 | 0.7696 | 0.0657 | same |
| 19 | 873 | EXT.3 | YES | CONFIRMED | 0.7105 | 0.7796 | default 0.5 | 0.7757 | 0.0583 | same |
| 20 | 884 | EXT.3 | YES | CONFIRMED | 0.7101 | 0.8150 | default 0.5 | 0.7158 | 0.0487 | same |

Every Top-20 row is inventory YES / OS CONFIRMED. Aerial is default on every row (no listing aerial). spatial_v2 is default 0.5 on every row.

## F. Distinctive-shape discrimination

`shape_v2` vs listing official contour (Top 20):

| Rank | Stand | shape_v2 | Similar (≥0.80) |
| ---: | --- | ---: | --- |
| 1 | 351 | 0.8701 | yes |
| 2 | 380 | 0.8626 | yes |
| 3 | 468 | 0.8488 | yes |
| 4 | 463 | 0.8483 | yes |
| 5 | 461 | 0.8415 | yes |
| 6 | 874 | 0.8483 | yes |
| 7 | 428 | 0.8125 | yes |
| 8 | 648 | 0.8346 | yes |
| 9 | 365 | 0.8008 | yes |
| 10 | 897 | 0.8097 | yes |
| 11 | 666 | 0.7949 | no |
| 12 | 624 | 0.8259 | yes |
| 13 | 899 | 0.8087 | yes |
| 14 | 672 | 0.7749 | no |
| 15 | 901 | 0.8028 | yes |
| 16 | 545 | 0.7847 | no |
| 17 | 665 | 0.7927 | no |
| 18 | 535 | 0.7618 | no |
| 19 | 873 | 0.7796 | no |
| 20 | 884 | 0.8150 | yes |

- Top 1 vs Top 2 shape gap: **0.0075**
- Top 1–Top 5 shape spread: **0.0286**
- Genuinely similar geometry (shape_v2 ≥ 0.80): **14 / 20**
- High rank despite weak geometry (rank ≤ 10 and shape_v2 < 0.60): **0**

**Mode: BROAD_CLUSTER.** `shape_v2` is not isolating a small distinctive-planform subset. It is scoring a large set of elongated high-solidity OS pools as near-equivalent to the official Hybrid contour, which itself lost the listing’s kinks/spa/kidney character.

## G. Ranking separation

| | Score |
| --- | ---: |
| #1 | 0.7524 |
| #2 | 0.7453 |
| #5 | 0.7415 |
| #10 | 0.7267 |
| #20 | 0.7101 |
| #1–#2 gap | **0.0071** |
| #1–#5 gap | **0.0109** |
| #1–#10 gap | 0.0257 |
| #1–#20 gap | 0.0423 |

Top 1 composition:

- **Real discriminatory evidence (0.5673):** shape_v2 0.3132, pool_presence 0.1400, stand_size 0.0690, exterior 0.0451
- **Neutral/default padding (0.1850, 24.6% of score):** spatial_v2 0.1100, aerial 0.0600, gis 0.0150

Near-ties: Top 5 sits inside 0.011. Shape is the largest term, but it does not separate those five stands.

## H. Freeze

Deterministic `freeze.json` written before any identity search. On-disk SHA256 equals `freeze.sha256`:

`8cf975a7a14326c520dbfcdba48a73d24df6e3605de1632d6174abab72d97628`

Frozen 001 hashes untouched:

- GIS `1bab3126fdfa9d397857f67f2d0cb65ddc410fc5d82afaf1a823c63018f56608`
- Inventory `3bc02c09c293d011b8f2d866b2075e3e9863cc9af9db5c054faa0dc722aca861`

## I. Proof panels

Generated after freeze hash; ranking was not changed. Paths:

- `listing_pool_contour_proof.png`
- `panels/top1_351.jpg` … `top5_461.jpg`

Each Top-5 panel shows listing pool photo + contour, listing normalized contour, raw native15 crop, GIS boundary, OS pool/building/driveway masks, candidate normalized contour, and shape_v2.

Visual reading (not GT): listing waterline is an irregular elongated/kidney planform with spa. Candidate aerial pools in the Top 5 are also elongated backyard pools. The match is a **generic elongated-blob similarity**, not a unique kink/spa/limb signature. Do not rerank from panels.

## J. Ground truth

Only after freeze. Public sources:

- Property24 `116978058`: **Contact agent for street address**; no stand; no coordinates; 4 bed; erf 972 m²; floor 449 m²; marked Sold; agent **Julie Mcdonald** (MG also lists **Cameron Else**)
- Private Property `T5407938` and MG syndication: same copy; street still withheld
- Distinctive wording (solar-heated pool, pizza oven, cottage, jacuzzi) did not yield a street or stand

GIS 002: **exactly 972 m² = stand 548 only**. 14 parcels within ±5 m². **Do not declare 548 as truth from size. Do not declare 351 as truth because it ranked #1.**

**Classification: NOT DETERMINABLE.** Preserve as an unlabelled geometry-discrimination test.

## K. Compare with previous three blinds

| Listing | Erf m² | Top 5 | #1–#2 | #1–#5 | Aerial |
| --- | ---: | --- | ---: | ---: | --- |
| 116273255 | 500 | 1/334, 1/373, 9/908, 1/691, 15/908 | 0.0061 | 0.0399 | no |
| 116223230 | 1009 | **446, 573, 401, 444, 605** | 0.0029 | 0.0042 | no |
| 116778622 | 1226 | **605, 444, 572, 382, 573** | 0.0146 | 0.0247 | yes (3) |
| **116978058** | **972** | **351, 380, 468, 463, 461** | **0.0071** | **0.0109** | no |

- Top-5 overlap with each previous listing: **none**
- Top-20 overlap vs `116223230`: 461, 428, 624, 545 (4)
- Top-20 overlap vs `116778622`: 428, 624 (2)
- Top-20 overlap vs `116273255`: none
- Recurring 1000 m² YES-pool cluster in **this** Top 20: **none of 605, 444, 573, 446, 401**

Watch-stand ranks on this freeze (not used as truth):

| Stand | Rank | shape_v2 | GIS m² |
| --- | ---: | ---: | ---: |
| 444 | 36 | 0.7286 | 1044 |
| 446 | 64 | 0.6492 | 993 |
| 401 | 71 | 0.6379 | 919 |
| 605 | 81 | 0.6310 | 1101 |
| 573 | 93 | 0.5672 | 911 |

The ~1000 m² YES-pool Top-5 cluster **did fall away**. That is mostly **stand-size** (972 vs 1009/1226 listings) plus weaker shape vs this official elongated contour — not proof that distinctive kidney geometry was matched. A **new** ~970 m² YES/CONFIRMED elongated-pool cluster took its place. Score separation did **not** improve materially versus `116778622` (which had real aerial). Recurring Top-20 hangers-on: **428** and **624**.

## L. Conclusion

**WEAK DISCRIMINATION** of distinctive pool geometry.

The listing pool is visually unusual. Frozen Hybrid v1 reduced it to an elongated high-solidity rectangle with zero major indents, so Scoring v2 `shape_v2` produced another broad YES-pool cluster (14/20 similar; Top 1–2 shape gap 0.0075) instead of a small distinctive shortlist. Rank gaps remain near-ties. The previous 605/444/573/446 cluster leaving Top 5/20 is listing-specific relative to the ~1000–1226 m² blinds, but it is not convincing geometry isolation.

Identity remains **NOT DETERMINABLE**. No ranking or detector change was made.

**Next action only:** obtain labelled Carlswald listings that publish a street or stand, and score this exact frozen stack. Do not retune Hybrid / `shape_v2` from this unlabelled distinctive-pool test.
