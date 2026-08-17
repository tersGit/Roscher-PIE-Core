# Blind PIE benchmark — listing 116273255 on `carlswald_north_corrected_002`

Frozen stack only. No detector, weight, inventory, or Pool Gate changes.

- **Freeze path:** `data/investigations/blind_116273255_complete_estate/freeze.json`
- **SHA256:** `227a67c7100639300916d3a405da6030ff90b5d1dff54209c0160290c24ba500`
- **Official score:** Scoring v2 × Hybrid Pool Geometry v1 (`hybrid_v2`)
- **Universe:** 400 unique erven (Summerset EXT.3 + EXT.6 + EXT.13)
- **Ground truth applied to ranking:** no

## A. Listing acquisition

| Field | Value |
| --- | --- |
| Listing ID | 116273255 |
| Property type | House |
| Estate | Carlswald North Estate |
| Erf size | 500 m² |
| Floor size | 500 m² (Property24 overview; same figure as erf) |
| Bedrooms | 3 |
| Listing photos | 51 downloaded |
| Video | none |
| Exterior (CLIP scene) | 15 |
| Pool (CLIP `pool_garden`) | 3 |
| Driveway/garage views | 6 (`009`, `010`, `020`, `021`, `026`, `041`) |
| Garden/patio views | 9 |
| Interior | 33 |

Scene counts: interior 33, driveway_access 6, contextual 6, pool_garden 3, rear_elevation 2, front_elevation 1.

Redacted before freeze: title, street, stand. Feature hits from redacted text: L-shaped pool, swimming pool, covered patio, timber deck, double garage, paved driveway, landscaped.

## B. Listing Pool Gate classification

**POOL = YES**

Independent evidence (no ground truth):

- listing text: swimming pool + L-shaped pool
- Hybrid v1: 3 scoring-ready YOLOE+SAM2 frames (`008`, `037`, `038`); 4 pool viewpoints
- CLIP scene: 3 `pool_garden` photos
- listing pool object: 3/6 observed non-interior frames detected (`008`, `037`, `038`), including L-geometry flags

Reason: `text_and_media_independently_support_private_pool`. Colour was not used.

## C. Pool Gate reduction

Listing YES against frozen 002 inventory (classifications unchanged):

| | Count |
| --- | ---: |
| Starting candidates | 400 |
| NO removed | 68 |
| YES survivors | 118 |
| UNKNOWN survivors | 214 |
| Final survivors | **332** |
| Reduction | 17.0% |

UNKNOWN never dropped. Confident YES never dropped.

## D. Listing visual fingerprint

Official Hybrid v1 contour: **`116273255-038`** (`yoloe_sam2`, `pool_overview`).

| Descriptor | Value |
| --- | --- |
| Frozen shape class | `irregular` (n_major_indents=1 and solidity 0.918 < 0.95) |
| Aspect ratio | 2.263 |
| Orientation (oblique) | −85.6° |
| Compactness / solidity | 0.4723 / 0.918 |
| L / bends | yes (1 major indent; concavity) |
| Pool–house vector / distance | omitted — frozen Hybrid v1 is not viewpoint-compatible with nadir |
| Relative area | omitted — not nadir |
| Colour | not a ranking signal |
| Roof / driveway / garage | not Scoring v2 spatial terms; CLIP exterior used only as the 0.06 exterior weight |

Partner scoring-ready frames: `008` (elevated, aspect 3.717, adjacent second arm) and `037` (pool overview, aspect 2.369). Masks were not merged.

## E. Frozen Top 20

Ranked 332 Pool Gate survivors. CLIP aerial is missing for every candidate (listing has no aerial scene). Spatial v2 is 0.5-neutral (Hybrid omits pool–house). Shape v2 dominates.

| Rank | Stand | Township | Area m² | Inventory | OS pool | Score |
| ---: | --- | --- | ---: | --- | --- | ---: |
| 1 | 1/334 | EXT.6 | 520 | UNKNOWN | PROBABLE | 0.7234 |
| 2 | 1/373 | EXT.6 | 500 | YES | CONFIRMED | 0.7173 |
| 3 | 9/908 | EXT.3 | 509 | YES | CONFIRMED | 0.6892 |
| 4 | 1/691 | EXT.13 | 552 | YES | CONFIRMED | 0.6887 |
| 5 | 15/908 | EXT.3 | 575 | YES | CONFIRMED | 0.6835 |
| 6 | 8/870 | EXT.3 | 523 | YES | CONFIRMED | 0.6815 |
| 7 | 1/389 | EXT.6 | 514 | YES | PROBABLE | 0.6751 |
| 8 | 567 | EXT.13 | 1106 | YES | CONFIRMED | 0.6747 |
| 9 | 1/450 | EXT.6 | 529 | YES | PROBABLE | 0.6741 |
| 10 | 17/908 | EXT.3 | 575 | YES | CONFIRMED | 0.6716 |
| 11 | 1/343 | EXT.6 | 565 | YES | PROBABLE | 0.6703 |
| 12 | 1/417 | EXT.6 | 524 | YES | PROBABLE | 0.6695 |
| 13 | 1/449 | EXT.6 | 594 | YES | CONFIRMED | 0.6644 |
| 14 | 1/603 | EXT.13 | 600 | YES | CONFIRMED | 0.6621 |
| 15 | 540 | EXT.6 | 1102 | YES | CONFIRMED | 0.6604 |
| 16 | 1105 | EXT.6 | 2191 | UNKNOWN | PROBABLE | 0.6571 |
| 17 | 443 | EXT.6 | 960 | YES | CONFIRMED | 0.6538 |
| 18 | 649 | EXT.13 | 1109 | YES | CONFIRMED | 0.6514 |
| 19 | 1/342 | EXT.6 | 577 | YES | CONFIRMED | 0.6512 |
| 20 | 688 | EXT.13 | 1511 | YES | CONFIRMED | 0.6456 |

**Top 1 contributors (1/334):** shape_v2 0.2908, pool_presence 0.14, spatial_v2 0.11 (neutral), stand_size 0.0638, aerial 0.06 (neutral). Exterior CLIP 0.7305. High-conf OS pool yes. Inventory UNKNOWN (OS PROBABLE is not inventory YES).

#1–#2 gap = 0.0061 (LOW separation). All Top 20 have high-conf OS pools. Two inventory UNKNOWN rows (1/334, 1105) survived the listing-YES gate as required.

## F. Frozen artifact

- `data/investigations/blind_116273255_complete_estate/freeze.json`
- SHA256 `227a67c7100639300916d3a405da6030ff90b5d1dff54209c0160290c24ba500`
- `all_candidates.json` (332 rows)
- `rankings_frozen.json` (marker; `ground_truth_applied: false`)
- Frozen 001 GIS/inventory SHA256 unchanged

This file was committed before any street/stand lookup.

## G. Top-5 proof panels

| Rank | Stand | Panel |
| ---: | --- | --- |
| 1 | 1/334 | `panels/top1_1_334.jpg` |
| 2 | 1/373 | `panels/top2_1_373.jpg` |
| 3 | 9/908 | `panels/top3_9_908.jpg` |
| 4 | 1/691 | `panels/top4_1_691.jpg` |
| 5 | 15/908 | `panels/top5_15_908.jpg` |

Each panel: listing pool frames 008/037/038; raw native15 crop; GIS erf boundary; OS v1 pool (cyan) / building (red) / driveway (green); pool-centroid to building-centroid line. Ranking was not retuned after viewing.

Visual note only (not used to change ranks): listing L-pool wraps a house corner with deck/patio. Several Top-5 native15 pools are compact in-parcel water bodies; 1/334’s OS mask is a stiff/triangular PROBABLE pool, not a clear two-arm L.

## H. Ground truth

**Not independently determinable. Confidence: LOW. Confirmed stand: none.**

After freeze, the public Property24 page was inspected:

- title: `3 Bedroom House for sale in Carlswald North Estate - P24-116273255`
- `p24_address`: **Contact agent for street address**
- no stand number in HTML
- no latitude/longitude in the listing payload
- schema.org address is locality-only (`Carlswald North Estate`)
- CoJ street lookup not possible without a street
- GIS 002 `street_address` match not possible without a street
- Prior Hybrid ranking test on this listing also recorded **no independent GT**

Frozen Top 20 was **not** used as truth.

## I. True-property frozen rank

Cannot be reported. Outcome classes (STRONG IMPROVEMENT / IMPROVEMENT / MIXED / NO IMPROVEMENT / FAILURE) require a confirmed stand.

Stability vs the previous 330-erf 001 Hybrid v2 shortlist (also unlabelled): previous Top 5 was 1/334, 1/373, 1/691, 1/389, 1/450. This 400-erf Pool-Gated run keeps **1/334 #1** and **1/373 #2**, inserts EXT.3 **9/908** and **15/908** into the Top 5, and moves 1/691 to #4. That is a universe/gate change, not a measured accuracy gain.

## J. Detector behaviour on true erf

**Not run.** FastSAM / CLIP / OS diagnostic is defined only after an independently confirmed stand. Detector parameters were not changed.

## K. Conclusion

The frozen complete-estate stack ran blind: listing POOL YES, 400→332, Hybrid v2 Top 1 = **1/334** at 0.7234 with a 0.0061 gap. Public identity is withheld, so this freeze is an unlabelled ranking snapshot, not an accuracy result. Preserve it. Do not retune from this listing.
