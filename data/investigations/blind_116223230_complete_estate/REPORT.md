# Blind PIE benchmark — listing 116223230 on `carlswald_north_corrected_002`

Frozen stack only. No detector, weight, inventory, or Pool Gate changes. FastSAM 768/1024 was not run.

- **Freeze path:** `data/investigations/blind_116223230_complete_estate/freeze.json`
- **Canonical freeze SHA256** (payload before the digest field; also in `freeze.sha256`): `be73a1615c5f87f678f9c4948c0d41b22d3f166aea3f10eb05b1ed6e98404126`
- **Official score:** Scoring v2 × Hybrid Pool Geometry v1 (`hybrid_v2`)
- **Universe:** 400 unique erven (Summerset EXT.3 + EXT.6 + EXT.13)
- **Ground truth applied to ranking:** no
- **Outcome class:** **UNLABELLED — GROUND TRUTH UNAVAILABLE**

## A. Listing acquisition

| Field | Value |
| --- | --- |
| Listing ID | 116223230 |
| URL | https://www.property24.com/for-sale/carlswald-north-estate/midrand/gauteng/12743/116223230 |
| Property type | House |
| Estate | Carlswald North Estate |
| Erf size | 1009 m² |
| Floor size | 820 m² |
| Bedrooms | 6 |
| Listing photo URLs | 65 (38 downloaded; some fetches failed) |
| Video | none |
| Exterior (CLIP scene) | 11 |
| Pool (CLIP `pool_garden`) | 5 |
| Driveway/garage views | 5 (`006`, `008`, `022`, `030`, `035`) |
| Garden/patio views | 9 |
| Interior | 22 |
| Other exterior structure | covered patio / braai; courtyard pool against a high stone wall (photos, not a scoring term) |

Scene counts: interior 22, pool_garden 5, driveway_access 5, contextual 4, front_elevation 1, rear_elevation 1.

Feature hits from redacted text: swimming pool, covered patio.

Redacted before ranking: title, street, stand, erf number, coordinates.

## B. Listing Pool Gate classification

**POOL = YES**

Independent evidence (classified before looking at estate candidates; colour not used):

- listing text mentions a private swimming pool
- Hybrid v1: 2 scoring-ready YOLOE+SAM2 frames; 5 pool viewpoints
- CLIP scene: 5 `pool_garden` photos
- listing pool object: 5/7 observed non-interior frames detected (`003`, `016`, `017`, `018`, `031`), including 4 L-geometry flags

Reason: `text_and_media_independently_support_private_pool`.

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

Official Hybrid v1 contour: **`116223230-017`** (`yoloe_sam2`, `pool_overview`).

| Descriptor | Value |
| --- | --- |
| L / bends | yes (n_major_indents=2) |
| Aspect ratio | 4.316 |
| Orientation (oblique) | −86.46° |
| Compactness / solidity | 0.2761 / 0.72 |
| Component count | 2 |
| Pool–house vector / distance | omitted — frozen Hybrid v1 is not viewpoint-compatible with nadir |
| Relative area | omitted — not nadir |
| Roof / driveway / garage as Scoring v2 spatial terms | unavailable |
| Colour | not a ranking signal |

**Available:** pool geometry (oblique Hybrid v1), listing exterior, driveway photos, garden/patio photos, Hybrid scoring-ready frames.

**Unavailable as scoring terms:** pool-to-house spatial, nadir relative area, roof footprint, driveway spatial, listing aerial.

Neutral CLIP scenes were not rewritten as positive identification evidence.

## E. Frozen Top 20

Ranked 332 Pool Gate survivors. CLIP aerial is missing for every candidate. Spatial v2 is 0.5-neutral (Hybrid omits pool–house). GIS is 0.5-neutral for every row (contrib 0.015). Shape v2 dominates among inventory-YES / high-conf OS pools.

| Rank | Stand | Township | Area m² | Inventory | OS pool | Score |
| ---: | --- | --- | ---: | --- | --- | ---: |
| 1 | 446 | EXT.6 | 993 | YES | PROBABLE | 0.7284 |
| 2 | 573 | EXT.13 | 911 | YES | PROBABLE | 0.7255 |
| 3 | 401 | EXT.6 | 919 | YES | CONFIRMED | 0.7248 |
| 4 | 444 | EXT.6 | 1044 | YES | CONFIRMED | 0.7247 |
| 5 | 605 | EXT.13 | 1101 | YES | CONFIRMED | 0.7242 |
| 6 | 583 | EXT.13 | 917 | YES | CONFIRMED | 0.7005 |
| 7 | 582 | EXT.13 | 1002 | YES | PROBABLE | 0.6988 |
| 8 | 868 | EXT.3 | 958 | YES | CONFIRMED | 0.6972 |
| 9 | 568 | EXT.13 | 998 | YES | CONFIRMED | 0.6969 |
| 10 | 428 | EXT.6 | 961 | YES | CONFIRMED | 0.6944 |
| 11 | 572 | EXT.13 | 1097 | YES | PROBABLE | 0.6943 |
| 12 | 482 | EXT.6 | 1007 | YES | CONFIRMED | 0.6923 |
| 13 | 678 | EXT.13 | 1113 | YES | PROBABLE | 0.6887 |
| 14 | 545 | EXT.6 | 918 | YES | CONFIRMED | 0.6842 |
| 15 | 624 | EXT.13 | 886 | YES | CONFIRMED | 0.6819 |
| 16 | 518 | EXT.6 | 1023 | YES | CONFIRMED | 0.6747 |
| 17 | 423 | EXT.6 | 950 | YES | CONFIRMED | 0.6746 |
| 18 | 623 | EXT.13 | 1001 | YES | CONFIRMED | 0.6745 |
| 19 | 420 | EXT.6 | 963 | YES | CONFIRMED | 0.6735 |
| 20 | 461 | EXT.6 | 967 | YES | CONFIRMED | 0.6714 |

All Top 20 are inventory YES with high-conf OS pools. Meaningful Top 1 contributors (stand 446): shape_v2 0.291, pool_presence 0.14, stand_size 0.0675, exterior CLIP 0.0448.

## F. Ranking separation

| | Score |
| --- | ---: |
| Top 1 | 0.7284 |
| Top 2 | 0.7255 |
| Top 5 range | 0.7242–0.7284 |
| #1–#2 gap | **0.0029** |
| #1–#5 gap | **0.0042** |

**Signals actually driving Top 1:** shape_v2 (elongated / indented Hybrid contour vs OS pool mask) plus the shared pool-presence bonus, a near-max stand-size term (993 vs listing 1009 m²), and a modest exterior CLIP term.

**Neutral / default padding on every Top-20 row:**

- spatial_v2 = 0.5 × 0.22 = **0.11** (Hybrid omits pool–house)
- aerial = 0.5 × 0.12 = **0.06** (no listing aerial)
- gis = 0.5 × 0.03 = **0.015**

Those three terms add 0.185 to every survivor with missing spatial/aerial and do not identify an erf. Pool-presence 0.14 is also shared by all high-conf YES pools, so it does not separate Top 1 from the rest of the YES cluster. Identification evidence in this freeze is almost entirely shape_v2, with a small stand-size and exterior remainder.

## G. Frozen artifact

- `data/investigations/blind_116223230_complete_estate/freeze.json`
- Canonical freeze SHA256 `be73a1615c5f87f678f9c4948c0d41b22d3f166aea3f10eb05b1ed6e98404126` (`freeze.sha256`; hash of canonical payload, not the pretty-printed file bytes)
- `all_candidates.json` (332 rows)
- `rankings_frozen.json` (marker; `ground_truth_applied: false`)
- `hybrid_block.json`
- Frozen 001 GIS/inventory SHA256 unchanged:
  - GIS `1bab3126fdfa9d397857f67f2d0cb65ddc410fc5d82afaf1a823c63018f56608`
  - Inventory `3bc02c09c293d011b8f2d866b2075e3e9863cc9af9db5c054faa0dc722aca861`

This file was committed before any street/stand lookup.

## H. Top-5 proof panels

Generated after freeze. Ranking was not retuned after viewing.

| Rank | Stand | Panel |
| ---: | --- | --- |
| 1 | 446 | `panels/top1_446.jpg` |
| 2 | 573 | `panels/top2_573.jpg` |
| 3 | 401 | `panels/top3_401.jpg` |
| 4 | 444 | `panels/top4_444.jpg` |
| 5 | 605 | `panels/top5_605.jpg` |

Each panel: listing exterior/pool frames; raw AGS native15 crop; GIS erf boundary; OS v1 pool (cyan) / building (red) / driveway (green); pool-centroid to building-centroid line.

Visual note only (not used as truth, not used to change ranks): listing photos show a courtyard-style pool against a high stone wall, viewed from a covered patio. Stand 446’s native15 crop shows an in-parcel water body south of a multi-gabled roof. That is visually plausible and **not** independent identity.

## I. Independent ground truth

**NOT DETERMINABLE. Confirmed stand: none.**

After freeze, identity was searched independently (Property24 metadata, syndicated/agent copies, distinctive copy, CoJ/GIS street fields). Frozen Top 1 was not treated as correct because it looked plausible.

| Source | Street / stand |
| --- | --- |
| Property24 `116223230` | Contact agent for street address; no stand; no coordinates |
| Private Property `T5167463` (same 6-bed / 6.5-bath / 1009 / 820 / fish pond / solar / wine room; Julie Mcdonald & Cameron Else) | Contact agent for street address |
| Mail & Guardian Property24 syndication | locality only |
| Platinum Residential freehold `2747059` (6-bed 820 m² sole mandate) | URL slug has no street |

**Rejected size-only hypothesis (not ground truth):** listing erf 1009 m² is the unique exact GIS area in dataset 002 = stand **508**, 6 Yellowood Close, EXT.6. Eighteen parcels sit within ±5 m² and five within ±1 m². No published listing, expired listing, or agent copy places this 6-bed / 820 m² house at that address (nearby Yellowood hits are unrelated, e.g. a 2-bed rental at 371/1 Yellowood Close). Stand 508 was therefore **not** declared as the property.

If 508 had been true, Pool Gate would have retained it (inventory UNKNOWN). Frozen rank of 508 is **#128** (score 0.5491; OS pool REJECTED; no shape_v2). That is a detector observation on a rejected hypothesis, not a labelled result.

## J. True-property frozen rank / detector diagnostic

Cannot be reported. Detector behaviour on a true erf is defined only after an independently confirmed stand. FastSAM / OS / CLIP diagnostics were not run on 446 or 508 as if they were truth. Detector parameters were not changed.

## K. Compare with listing 116273255 (PR #18)

PR #18 freeze SHA256 `227a67c7100639300916d3a405da6030ff90b5d1dff54209c0160290c24ba500`. Previous Top 5: **1/334, 1/373, 9/908, 1/691, 15/908**.

| Watch | PR #18 | This listing |
| --- | ---: | ---: |
| 1/334 | rank 1 | rank **115** (0.5687, inventory UNKNOWN, OS PROBABLE) |
| 1/373 | rank 2 | rank **119** (0.5591, inventory YES, OS CONFIRMED) |
| Top 5 overlap | — | **none** |
| Top 20 overlap | — | **none** |

The same two stands do **not** reappear near the top. Ranking is listing-specific relative to 116273255; this is **not** evidence of the 334/373 candidate-bias pattern on this run.

Caveat: specificity of the shortlist is not identification. This Top 5 is a tight cluster of inventory-YES pools with similar shape_v2 scores (#1–#5 gap 0.0042), padded by the same spatial/aerial/gis neutrals. A different listing can produce a different YES-pool cluster without proving that Top 1 is the listed house.

## L. Conclusion

**UNLABELLED — GROUND TRUTH UNAVAILABLE**

The frozen complete-estate stack ran blind: listing POOL YES, 400→332, Hybrid v2 Top 1 = **446** at 0.7284 with a 0.0029 gap. Public identity is withheld on every copy found. Unique GIS erf size is not identity. Preserve the freeze. Do not retune from this listing. Do not assign STRONG SUCCESS / SUCCESS / MIXED / FAILURE.

**Recommended next action (do not implement here):** run the next independent blind test on a Carlswald listing that **publishes street or stand**, using this exact frozen stack, so Top-20 specificity can be scored as accuracy rather than another unlabelled snapshot.
