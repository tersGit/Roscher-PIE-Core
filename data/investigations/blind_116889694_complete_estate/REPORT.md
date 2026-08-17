# Blind PIE benchmark — listing 116889694 on `carlswald_north_corrected_002`

Strict blind test of the frozen Hybrid / Pool Gate / Scoring v2 stack. Distinctive Contour v2 is reporting-only. No ranking, weight, Hybrid, OS, native15, FastSAM/SAM2, or Pool Gate changes. Colour not used in scoring.

- **Freeze path:** `data/investigations/blind_116889694_complete_estate/freeze.json`
- **On-disk SHA256** (matches `freeze.sha256`): `69b8ea31f1ecdb77311937b2e3db829ef14ecea33b8534d2730a5ed57d331465`
- **Freeze commit:** `f396e81`
- **PR:** #22
- **Official score:** `hybrid_v2`
- **Universe:** 400 unique erven
- **Ground truth applied to ranking:** no
- **Distinctive Contour v2 used in ranking:** no
- **Geometry-discrimination class:** **WEAK**
- **Identity:** **UNLABELLED — GROUND TRUTH UNAVAILABLE**

## A. Blindness

Before freeze: no street / stand / erf-number / coordinate / Property24-identity / archived-listing search. No unique-GIS-size reverse-ID. Prior `116889694` artefacts: **none found**. Photos downloaded fresh. Historical note that `116978058` Top 5 (351, 380, 468, 463, 461) were later visually rejected was **not** used to alter ranking.

## B. Acquisition

**Fresh.** 28/28 photos downloaded, 0 reused, 0 failed. No video. Title / street / stand omitted from freeze.

| Field | Value |
| --- | --- |
| Property type | House |
| Erf size | 920 m² |
| Floor size | 655 m² |
| Bedrooms | 5 |
| Listing photos | 28 (28 fresh) |
| Video | NO |
| CLIP interior | 17 |
| CLIP exterior | 10 |
| CLIP driveway | 2 |
| CLIP garden/patio (`contextual` + rear) | 4 contextual + 3 rear_elevation |
| CLIP aerial | **1** (`002`) |
| CLIP `pool_garden` | **0** |
| Feature hits | swimming pool, covered patio, landscaped |

Pool-relevant Hybrid viewpoints extracted: aerial_near_nadir 1, pool_overview 1, elevated_exterior 2. CLIP did not label any `pool_garden` frame.

## C. Pool Gate

Listing **POOL = YES** independently of estate candidates.

Reason: `text_and_media_independently_support_private_pool`

Evidence: listing text; Hybrid pool viewpoints = 1; listing-pool-object 1/5 detected (`002`) with L-geometry flag. Colour not used. Inventory labels unchanged.

| | Count |
| --- | ---: |
| Candidates before | 400 |
| YES | 118 |
| NO removed | 68 |
| UNKNOWN retained | 214 |
| Candidates after | **332** |
| Reduction | 17.0% |

## D. Existing Hybrid fingerprint

Official Hybrid v1: **no scoring-ready contour**.

| | Value |
| --- | --- |
| Chosen frame | **none** |
| Extraction method | YOLOE failed on all extracted frames |
| `n_scoring_ready` | **0** |
| Shape class | unknown |
| Aspect / solidity / indents | n/a |
| Directional changes / limbs | n/a |
| Normalized 64-pt scoring contour | **empty** |
| Pool–house | not measurable |

Per extracted frame (frozen Hybrid, not substituted):

| Frame | Viewpoint | Source | Scoring-ready | Note |
| --- | --- | --- | --- | --- |
| 002 | aerial_near_nadir | `presence_only` | no | FastSAM presence without valid boundary |
| 026 | elevated_exterior | `fastsam_fallback` | no | FastSAM box+SAM2; not an official scoring source |
| 027 | pool_overview | `no_usable_geometry` | no | no YOLOE, no FastSAM |
| 028 | elevated_exterior | `no_usable_geometry` | no | no YOLOE, no FastSAM |

The official ranking contour was **not** improved or replaced.

## E. Distinctive Contour v2 diagnostic

**Used in ranking: no.**

Run on all useful pool-relevant frames (CLIP pool views + Hybrid pool/aerial/elevated frames): `002`, `026`, `027`, `028`.

**Overall: COLLAPSED**

Reason: `no_official_frame_and_extracted_contours_collapsed`

| Frame | Verdict | What happened |
| --- | --- | --- |
| 002 (aerial; visible rectangular pool in the photo) | **COLLAPSED** | `presence_only` stored no usable mask; panels 1–5 have no overlay; 64-pt canvas is empty. Geometry is lost **at extraction**, before simplification. |
| 026 | **PARTIALLY LOST** | FastSAM fallback masked **artificial grass on a balcony**, not the swimming pool. Raw contour 2482 verts, 0 major indents, solidity 0.977; scoring 64-pt lost directional-change noise. Wrong object. |
| 027 | **COLLAPSED** | no mask / no contour |
| 028 | **COLLAPSED** | no mask / no contour |

Where information was lost:

1. Listing aerial `002` clearly shows a rectangular pool; YOLOE did not produce a valid pool component; FastSAM presence did not yield a scoring boundary or a retained mask.
2. FastSAM fallback on `026` attached to turf, not water — a false object, then regularisation smoothed its shadow jags.
3. Official Scoring v2 therefore received **no listing contour**. Pool+spa relationship could not be preserved because no dominant/secondary water pair entered the official path.

Proof panels: `data/investigations/blind_116889694_complete_estate/distinctive_contour_v2/`.

## F. Frozen Top 20

`shape_v2` is **None** on every row (neutral 0.5 × 0.36 = 0.18). `pool_presence` likewise neutral. Aerial is real (listing has CLIP aerial).

| Rank | Stand | Ext | Inv | OS pool | Score | shape_v2 | exterior | pool_pres. | stand_size | spatial | aerial | gis |
| ---: | --- | --- | --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 435 | EXT.6 | UNKNOWN | REJECTED | 0.5870 | None | 0.7445 | 0.07 | 0.0661 | 0.11 | 0.1012 | 0.015 |
| 2 | 626 | EXT.13 | UNKNOWN | REJECTED | 0.5837 | None | 0.7600 | 0.07 | 0.0697 | 0.11 | 0.0934 | 0.015 |
| 3 | 451 | EXT.6 | YES | CONFIRMED | 0.5833 | None | 0.6983 | 0.07 | 0.0693 | 0.11 | 0.0971 | 0.015 |
| 4 | 583 | EXT.13 | YES | CONFIRMED | 0.5829 | None | 0.7414 | 0.07 | 0.0695 | 0.11 | 0.0939 | 0.015 |
| 5 | 545 | EXT.6 | YES | CONFIRMED | 0.5825 | None | 0.7509 | 0.07 | 0.0697 | 0.11 | 0.0928 | 0.015 |
| 6 | 400 | EXT.6 | UNKNOWN | REJECTED | 0.5818 | None | 0.6946 | 0.07 | 0.0693 | 0.11 | 0.0958 | 0.015 |
| 7 | 590 | EXT.13 | UNKNOWN | REJECTED | 0.5817 | None | 0.7514 | 0.07 | 0.0683 | 0.11 | 0.0933 | 0.015 |
| 8 | 404 | EXT.6 | YES | CONFIRMED | 0.5816 | None | 0.7189 | 0.07 | 0.0668 | 0.11 | 0.0967 | 0.015 |
| 9 | 407 | EXT.6 | UNKNOWN | REJECTED | 0.5816 | None | 0.7502 | 0.07 | 0.0648 | 0.11 | 0.0969 | 0.015 |
| 10 | 345 | EXT.6 | UNKNOWN | REJECTED | 0.5812 | None | 0.7425 | 0.07 | 0.0700 | 0.11 | 0.0917 | 0.015 |
| 11–20 | 611, 607, 547, 636, 895, 360, 896, 584, **624**, 462 | | | | 0.5808–0.5778 | None | | 0.07 | | 0.11 | | 0.015 |

## G. Shape discrimination

**WEAK** (`NO_SHAPE_SIGNAL`).

- Top-5 shape spread: n/a (all `shape_v2` None)
- Top-20 with shape_v2 ≥ 0.80: **0**
- No listing contour to match. Ranking cannot discriminate pool geometry.

## H. Ranking separation

| | |
| --- | ---: |
| #1 | 0.5870 |
| #2 | 0.5837 |
| #5 | 0.5825 |
| #10 | 0.5812 |
| #20 | 0.5778 |
| #1–#2 | **0.0033** |
| #1–#5 | **0.0045** |
| #1–#10 | 0.0058 |
| #1–#20 | 0.0092 |

Top 1: **real evidence 0.212** (aerial 0.1012, stand_size 0.0661, exterior 0.0447) vs **neutral padding 0.375 (63.9%)** (shape_v2 0.18, spatial 0.11, pool_presence 0.07, gis 0.015). Near-total tie across Top 20.

## I. Freeze / SHA256

Committed **before** ground truth: `f396e81`.

On-disk SHA256 = recorded: `69b8ea31f1ecdb77311937b2e3db829ef14ecea33b8534d2730a5ed57d331465`

Frozen 001 unchanged:

- GIS `1bab3126fdfa9d397857f67f2d0cb65ddc410fc5d82afaf1a823c63018f56608`
- Inventory `3bc02c09c293d011b8f2d866b2075e3e9863cc9af9db5c054faa0dc722aca861`

## J. Top-5 proof panels

After freeze; **do not rerank**.

- `panels/top1_435.jpg`
- `panels/top2_626.jpg`
- `panels/top3_451.jpg`
- `panels/top4_583.jpg`
- `panels/top5_545.jpg`

Top 1 listing strip includes agent portrait / agency logo because CLIP ranked those as exterior-ish; listing pool contour cell is empty. Candidate 435 is inventory UNKNOWN / OS pool REJECTED. Historical `116978058` false-positive cluster 351/380/468/463/461 is **not** in this Top 5 or Top 20.

## K. Ground truth

Only after freeze.

- Property24 / Private Property `T5378240` / Lew Geffen Sotheby’s: **Contact agent for street address**; no stand; no coordinates; agent **Chris Stewart**
- Distinctive copy (38 solar panels, 12 batteries, 920 m², 655 m²) did not yield a street
- GIS 002: **920 m² is not unique** (stands 345, 397, 648, 438). 27 parcels within ±5 m². **Not used as truth.**
- Top 1 (435) **not used as truth.**

**UNLABELLED — GROUND TRUTH UNAVAILABLE** (`NOT DETERMINABLE`)

## L. Comparison with previous Carlswald tests

| Listing | Erf | Official contour | Top 5 | #1–#2 | #1–#5 | Class |
| --- | ---: | --- | --- | ---: | ---: | --- |
| 116273255 | 500 | yes | 1/334 family | 0.0061 | 0.0399 | mixed / unlabelled |
| 116223230 | 1009 | yes | 446, 573, 401, 444, 605 | 0.0029 | 0.0042 | broad ~1000 m² YES cluster |
| 116778622 | 1226 | yes | 605, 444, 572, 382, 573 | 0.0146 | 0.0247 | same cluster + aerial |
| 116978058 | 972 | elongated_rect, 0 indents | 351, 380, 468, 463, 461 | 0.0071 | 0.0109 | WEAK geometry; later visually rejected |
| **116889694** | **920** | **none** | **435, 626, 451, 583, 545** | **0.0033** | **0.0045** | **WEAK; aerial/size only** |

- Top-5 overlap with all previous: **none**
- Top-20 overlap: 583, 545, 624 vs prior YES-pool blinds
- Watch cluster 605/444/573/446/401: **not in Top 20** (401 is #24)
- `116978058` false-positive Top 5: **not in this Top 20**
- Recurring hanger-on: **624** (Top 20 on four of five blinds)

This listing did not reproduce the 351-cluster. Separation is the **worst** of the five because shape never fired.

## M. Conclusion

**WEAK** discrimination. Distinctive Contour v2: **COLLAPSED**.

The listing has a clearly visible rectangular pool on aerial frame `002`, but frozen Hybrid v1 produced **zero** scoring-ready contours, so Scoring v2 padded shape and pool-presence at 0.5 and ranked on aerial CLIP + stand size. FastSAM fallback on `026` traced turf, not water. Identity remains unlabelled. No ranking change was made.

**Next action only:** obtain labelled Carlswald listings that publish a street or stand, including at least one with a nadir/aerial pool frame, and score this exact frozen stack. Do not retune Hybrid from this unlabelled miss.
