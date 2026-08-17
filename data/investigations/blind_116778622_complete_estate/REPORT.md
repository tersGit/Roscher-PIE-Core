# Blind PIE benchmark — listing 116778622 on `carlswald_north_corrected_002`

Final Carlswald North listing test on the frozen complete-estate stack. No detector, weight, inventory, or Pool Gate changes. FastSAM 768/1024 was not run.

- **Freeze path:** `data/investigations/blind_116778622_complete_estate/freeze.json`
- **On-disk SHA256** (matches `freeze.sha256`): `3eb8f54dc03f804cff519b65d7f452444ff91e7c4133a9ec7b9b638a3337875f`
- **Official score:** Scoring v2 × Hybrid Pool Geometry v1 (`hybrid_v2`)
- **Universe:** 400 unique erven (Summerset EXT.3 + EXT.6 + EXT.13)
- **Ground truth applied to ranking:** no
- **Prior `116778622` artifacts used as ranking input:** none found in this repo; Hybrid extracted fresh; photos downloaded fresh
- **Outcome class:** **UNLABELLED — GROUND TRUTH UNAVAILABLE**

## A. Listing acquisition

Fresh Property24 fetch. Destination photo directory was empty; **71/72 images downloaded fresh**, 0 reused from disk, 1 failed. Video present (1). Identity redacted before ranking.

| Field | Value |
| --- | --- |
| Listing ID | 116778622 |
| Property type | House |
| Estate | Carlswald North Estate |
| Erf size | 1226 m² |
| Floor size | 427 m² |
| Bedrooms | 5 |
| Listing photo URLs | 72 (71 downloaded fresh) |
| Video | yes (1) |
| Exterior (CLIP) | 14 |
| Pool (`pool_garden`) | 13 |
| Driveway/garage | 6 |
| Garden/patio | 20 |
| Interior | 41 |
| Aerial CLIP scenes | **3** (first of the three blind tests with listing aerial) |

Feature hits from redacted text: swimming pool, covered patio, double garage, landscaped. Distinctive exterior structure noted only as listing evidence, not a scoring term: farm-style house, boma / pizza oven (from listing copy after freeze).

## B. Listing Pool Gate classification

**POOL = YES**

Independent evidence (before estate candidates; colour not used):

- listing text mentions a private swimming pool
- Hybrid v1: **7 scoring-ready** YOLOE+SAM2 frames; 10 pool viewpoints
- CLIP scene: 13 `pool_garden` photos
- listing pool object: 4/8 observed non-interior frames detected (`002`, `005`, `050`, `051`), all with L-geometry flags

Pool geometry **can** be extracted: official contour `116778622-051` (`yoloe_sam2`, `elevated_exterior`), aspect 7.756, 1 major indent. Reason: `text_and_media_independently_support_private_pool`.

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

## D. Fresh visual fingerprint

Official Hybrid v1 contour: **`116778622-051`**.

| Signal | Class |
| --- | --- |
| Pool geometry (oblique/elevated Hybrid v1) | **measured** |
| Listing exterior / driveway / garden photos | **measured** |
| Hybrid scoring-ready frames (7) | **measured** |
| Listing aerial CLIP (3 scenes) | **measured** (unlike PR #18/#19) |
| Pool–house spatial | **unavailable** (Hybrid v1 not nadir-compatible) |
| Roof footprint as Scoring v2 term | **unavailable** |
| Driveway as Scoring v2 spatial | **unavailable** |
| spatial_v2 | **neutral/default** (0.5) |
| gis | **neutral/default** (0.5) |
| Colour | not a ranking signal |

## E. Frozen Top 20

| Rank | Stand | Township | Area m² | Inventory | OS pool | Score |
| ---: | --- | --- | ---: | --- | --- | ---: |
| 1 | 605 | EXT.13 | 1101 | YES | CONFIRMED | 0.7087 |
| 2 | 444 | EXT.6 | 1044 | YES | CONFIRMED | 0.6941 |
| 3 | 572 | EXT.13 | 1097 | YES | PROBABLE | 0.6915 |
| 4 | 382 | EXT.6 | 1251 | YES | CONFIRMED | 0.6909 |
| 5 | 573 | EXT.13 | 911 | YES | PROBABLE | 0.6840 |
| 6 | 446 | EXT.6 | 993 | YES | PROBABLE | 0.6740 |
| 7 | 583 | EXT.13 | 917 | YES | CONFIRMED | 0.6738 |
| 8 | 568 | EXT.13 | 998 | YES | CONFIRMED | 0.6703 |
| 9 | 678 | EXT.13 | 1113 | YES | PROBABLE | 0.6703 |
| 10 | 567 | EXT.13 | 1106 | YES | CONFIRMED | 0.6636 |
| 11 | 401 | EXT.6 | 919 | YES | CONFIRMED | 0.6619 |
| 12 | 690 | EXT.13 | 1226 | YES | CONFIRMED | 0.6619 |
| 13 | 624 | EXT.13 | 886 | YES | CONFIRMED | 0.6603 |
| 14 | 868 | EXT.3 | 958 | YES | CONFIRMED | 0.6579 |
| 15 | 582 | EXT.13 | 1002 | YES | PROBABLE | 0.6572 |
| 16 | 604 | EXT.13 | 1226 | YES | CONFIRMED | 0.6572 |
| 17 | 470 | EXT.6 | 1111 | YES | CONFIRMED | 0.6546 |
| 18 | 688 | EXT.13 | 1511 | YES | CONFIRMED | 0.6545 |
| 19 | 482 | EXT.6 | 1007 | YES | CONFIRMED | 0.6534 |
| 20 | 428 | EXT.6 | 961 | YES | CONFIRMED | 0.6520 |

Top 1 contributors (605): shape_v2 0.2487, pool_presence 0.14, **aerial 0.0947** (not 0.5-neutral), stand_size 0.0541, exterior 0.0462.

## F. Ranking separation

| | Score |
| --- | ---: |
| #1 | 0.7087 |
| #2 | 0.6941 |
| #5 | 0.6840 |
| #10 | 0.6636 |
| #20 | 0.6520 |
| #1–#2 gap | **0.0146** |
| #1–#5 gap | **0.0247** |
| #1–#10 gap | 0.0451 |
| #1–#20 gap | 0.0567 |

**What actually separates Top 5:** shape_v2 first, then the shared pool-presence bonus, then **aerial CLIP** (this listing has aerial scenes), then stand-size and a small exterior term. Top 5 genuine sums are 0.5837 / 0.5691 / 0.5665 …; the #1–#2 gap is mostly aerial + stand-size, not spatial identity.

**Neutral/default on every Top-20 row:**

- spatial_v2 = 0.5 × 0.22 = **0.11**
- gis = 0.5 × 0.03 = **0.015**
- combined padding **0.125** (17.6% of Top 1)

Aerial is **not** padding on this listing (contrib 0.0947 vs 0.06 default). Pool-presence 0.14 is shared by all high-conf YES pools.

## G. Frozen artifact

Committed before ground-truth lookup. On-disk `sha256sum freeze.json` equals `freeze.sha256`. Frozen 001 GIS/inventory hashes unchanged.

## H. Top-5 proof panels

Generated after freeze. Ranking was not retuned.

| Rank | Stand | Panel |
| ---: | --- | --- |
| 1 | 605 | `panels/top1_605.jpg` |
| 2 | 444 | `panels/top2_444.jpg` |
| 3 | 572 | `panels/top3_572.jpg` |
| 4 | 382 | `panels/top4_382.jpg` |
| 5 | 573 | `panels/top5_573.jpg` |

Visual note only (not truth): listing pool photos show a curved/crescent pool; stand 605’s native15 crop also shows a curved in-parcel pool. That is visually plausible and **not** independent identity.

## I. Independent ground truth

**NOT DETERMINABLE. Confirmed stand: none.**

After freeze, identity was searched independently. Frozen Top 1 was not used as the starting assumption.

| Source | Street / stand |
| --- | --- |
| Property24 `116778622` | Contact agent for street address; no stand; no coordinates; agent Henk Humphries / RE/MAX Infoglobe |
| MG syndication | locality only; erf 1226 / floor 427 |
| RE/MAX Carlswald North search card | locality only; no street slug |
| Distinctive copy (farm-style masterpiece, boma with pizza oven, rain-water backup) | no published street |

**Rejected size-only hypotheses:** listing erf 1226 m² matches **two** GIS parcels (690 = 15 Karee Drive, rank 12; 604 = 3 Essenhout Close, rank 16). Seven parcels sit within ±5 m². Size is not identity.

## J. True-property diagnostics

Not run. No independently confirmed stand.

## K. Compare all three blind complete-estate tests

| | 116273255 PR #18 | 116223230 PR #19 | 116778622 this test |
| --- | --- | --- | --- |
| Listing erf | 500 m² | 1009 m² | 1226 m² |
| Listing aerial CLIP | none | none | **3 scenes** |
| Top 1 | 1/334 | 446 | 605 |
| #1–#2 gap | 0.0061 | 0.0029 | **0.0146** |
| Ground truth | not determinable | not determinable | not determinable |

**Top-5 overlap:** none with PR #18; **605, 444, 573** overlap with PR #19. No stand is in all three Top 5s.

**Top-20 overlap:** 2 stands with PR #18 (567, 688); **14/20** with PR #19.

**1/334 / 1/373:** PR #18 #1/#2; ranks 115/119 on PR #19; ranks **130 / 121** here. Those two stands are not a universal attractor.

**Candidate bias:** yes, between the two ~1000 m² YES-pool listings. Ranking is listing-specific versus the 500 m² listing, and listing-specificity is **not** proof of accuracy. The repeated cluster is inventory-YES high-conf pools with similar Hybrid shape scores.

This listing is **not** a genuine accuracy measurement of the 400-erf stack, because ground truth is unavailable.

## L. Final Carlswald conclusion

**UNLABELLED — GROUND TRUTH UNAVAILABLE**

### What the three blind tests collectively establish

1. The frozen stack runs end-to-end on complete-estate 002: listing Pool Gate YES, 400→332, Hybrid v2 ranking, freeze-before-GT.
2. Public Property24 identity is withheld on all three test listings, so **none of the three is an accuracy result**.
3. Ranking is partly listing-specific (500 m² vs ~1000 m² shortlists differ; 1/334 and 1/373 do not dominate every listing).
4. Ranking is also biased toward a recurring YES-pool cluster: PR #19 and this test share 14 of 20 Top-20 stands.
5. Spatial v2 and GIS are 0.5-neutral padding on every row. Aerial becomes a real term only when the listing has aerial photos (this test). Identification then still rests mainly on shape_v2 among many similar pools.
6. Unique or near-unique GIS erf size is not ground truth (508 on PR #19; 690 and 604 here).

**Recommended next experiment (do not implement here): obtain labelled examples** — listings that publish street or stand, or HOA/agent confirmation — and score this exact frozen 400-erf stack against known erven. FastSAM `imgsz` A/B is a later measured-bottleneck test; it cannot be scored until at least one labelled erf exists.
