# Blind PIE freeze — listing 117170887 on `carlswald_north_corrected_002`

Accuracy test on **PR #23** (Hybrid extraction) + **PR #24** (adapter) + **PR #26** (Corner Gate v1) + **PR #27** (Pool Object Validation v1). Scoring v2 weights, Pool Gate internals, OS v1 JSON on disk, native15, and inventory labels are unchanged.

- **Freeze path:** `data/investigations/blind_117170887_complete_estate/freeze.json`
- **On-disk SHA256** (matches `freeze.sha256`, verified after write): `96a66c8b240d8cab317d861d94582f1ba0bec84531c876fba4aaf090b4e82aa3`
- **Harness commit:** `fa3b49f`
- **Freeze commit:** `6c53661`
- **PR:** #28
- **Stack:** PR #23 extraction + PR #24 adapter + PR #26 Corner Gate + PR #27 POV; Scoring v2 frozen
- **Official score:** `hybrid_v2`
- **Universe:** 400 unique erven
- **Ground truth applied to ranking:** no
- **Ground-truth recovery in this test:** **not performed** (STOP after freeze)
- **Geometry-discrimination class:** **MODERATE**
- **Do not treat Top 1 as truth.** Top 5 is for manual visual inspection.

## A. Blindness

Before freeze: no street / stand / erf-number / coordinate / archived-identity / agent-cross-listing / Private Property / GIS-parcel / unique-stand-size reverse lookup / prior advertisement / seller-social search. Prior `117170887` artefacts: **none found**. Photos downloaded fresh. Historical freeze trees were not modified.

## B. Acquisition

**Fresh.** 76/77 photos downloaded, 0 reused, **1 failed**. Video **NO** (0). Title / street / stand omitted from freeze.

| Field | Value |
| --- | --- |
| Property type | House |
| Erf size | 1024.0 m² |
| Floor size | 431.0 m² |
| Bedrooms | 4 |
| Listing photos | 77 (76 fresh, 1 failed) |
| Video | NO (count=0) |
| CLIP interior | 36 |
| CLIP exterior | 27 |
| CLIP driveway | 7 |
| CLIP garden/patio | 21 |
| CLIP aerial | 1 |
| CLIP `pool_garden` | 12 |
| Feature hits | swimming pool, covered patio |

CLIP scene counts: `{'contextual': 9, 'driveway_access': 7, 'front_elevation': 1, 'interior': 36, 'rear_elevation': 10, 'aerial': 1, 'pool_garden': 12}`.

Useful pool frames: `['117170887-047', '117170887-053', '117170887-054', '117170887-055', '117170887-063', '117170887-071', '117170887-072', '117170887-073', '117170887-074', '117170887-075', '117170887-076', '117170887-077']`.

Useful exterior: `['117170887-001', '117170887-003', '117170887-004', '117170887-005', '117170887-006', '117170887-007', '117170887-009', '117170887-010', '117170887-013', '117170887-021', '117170887-023', '117170887-024', '117170887-031', '117170887-033', '117170887-034', '117170887-036', '117170887-039', '117170887-049', '117170887-051', '117170887-057', '117170887-059', '117170887-064', '117170887-065', '117170887-067', '117170887-068', '117170887-069', '117170887-070']`.

Useful driveway: `['117170887-003', '117170887-005', '117170887-009', '117170887-021', '117170887-031', '117170887-034', '117170887-036']`.

Useful aerial: `['117170887-035']`.

## C. Pool Gate

Listing **POOL = YES**, determined from listing evidence **before** estate ranking.

Reason: `text_and_media_independently_support_private_pool`

Estate inventory (unchanged):

| | Count |
| --- | ---: |
| Starting parcels | 400 |
| YES | 118 |
| NO | 68 |
| UNKNOWN | 214 |
| Candidates removed (confident NO) | 68 |
| Candidates retained | **332** |
| Reduction | 17.0% |

## D. Corner Gate v1

Listing **CORNER = YES** (confidence=0.86, source=`aerial`, high_confidence=True).

Reason: `roads_visible_along_two_parcel_sides`. Frames: `['117170887-035', '117170887-051', '117170887-057']`.

Gate action: `high_confidence_listing_yes_drop_confident_parcel_no`.

Pool Gate survivors **332 → Corner Gate survivors 98** (removed confident parcel NO=234; YES/NO/UNKNOWN parcel survivors=56/0/42).

## E. Pool Object Validation v1 (listing)

Official fingerprint: **official_hybrid_fingerprint**.

Official pick: `117170887-077` source=`yoloe_sam2` viewpoint=`pool_overview`.

Selection reason: `principal_pool_identity then cross-frame agreement then geometry then viewpoint; cluster_size=2; incompatible contours are not averaged viewpoint=pool_overview source=yoloe_sam2 identity=0.853 quality=44.061`.

Per-frame POV:

| media_id | viewpoint | source | scoring_ready | POV | role | principal |
| --- | --- | --- | --- | --- | --- | --- |
| 117170887-003 | ground_level_exterior | presence_only | False | UNKNOWN | unknown | False |
| 117170887-004 | ground_level_exterior | presence_only | False | UNKNOWN | unknown | False |
| 117170887-005 | ground_level_exterior | presence_only | False | UNKNOWN | principal_pool | False |
| 117170887-006 | garden_only | presence_only | False | UNKNOWN | unknown | False |
| 117170887-007 | ground_level_exterior | presence_only | False | UNKNOWN | principal_pool | False |
| 117170887-047 | elevated_exterior | presence_only | False | UNKNOWN | unknown | False |
| 117170887-048 | ground_level_exterior | presence_only | False | UNKNOWN | principal_pool | True |
| 117170887-049 | ground_level_exterior | presence_only | False | UNKNOWN | unknown | False |
| 117170887-051 | elevated_exterior | presence_only | False | UNKNOWN | unknown | False |
| 117170887-053 | pool_overview | presence_only | False | UNKNOWN | principal_pool | True |
| 117170887-054 | pool_overview | yoloe_sam2 | False | REJECTED | unknown | False |
| 117170887-055 | pool_overview | yoloe_sam2 | True | CONFIRMED | principal_pool | True |
| 117170887-057 | elevated_exterior | presence_only | False | UNKNOWN | principal_pool | True |
| 117170887-063 | pool_overview | presence_only | False | CONFIRMED | principal_pool | True |
| 117170887-067 | elevated_exterior | presence_only | False | CONFIRMED | principal_pool | True |
| 117170887-068 | garden_only | presence_only | False | UNKNOWN | unknown | False |
| 117170887-069 | ground_level_exterior | presence_only | False | CONFIRMED | principal_pool | True |
| 117170887-070 | pool_overview | presence_only | False | UNKNOWN | principal_pool | False |
| 117170887-071 | pool_overview | yoloe | True | CONFIRMED | principal_pool | True |
| 117170887-072 | pool_overview | yoloe | True | CONFIRMED | principal_pool | True |
| 117170887-073 | pool_overview | yoloe_sam2 | True | CONFIRMED | principal_pool | True |
| 117170887-074 | pool_overview | yoloe_sam2 | True | CONFIRMED | principal_pool | True |
| 117170887-075 | pool_overview | presence_only | False | UNKNOWN | unknown | False |
| 117170887-076 | pool_overview | yoloe_sam2 | True | CONFIRMED | principal_pool | True |
| 117170887-077 | pool_overview | yoloe_sam2 | True | CONFIRMED | principal_pool | True |

## F. Pool Object Validation v1 (candidates, copies only)

OS JSON rewritten: **False**. Ranked=98.

CONFIRMED=31 UNKNOWN=64 REJECTED=3 missing=0.

## G. Scoring v2 freeze (unchanged weights)

Weights: pool_presence 0.14, shape_v2 0.36, spatial_v2 0.22, aerial 0.12, exterior 0.06, gis 0.03, stand_size 0.07.

Ranked survivors: **98**.

| #1 | #2 | #5 | #10 | #20 |
| --- | --- | --- | --- | --- |
| 0.7681 | 0.7608 | 0.7353 | 0.7025 | 0.6698 |

Gaps: 1–2=0.0073, 1–5=0.0328, 1–10=0.0656, 1–20=0.0983.

Genuine shape rows=31; shape_v2≥0.80=7; Top1 evidence=83.73% padding=16.27%.

Class: **MODERATE** (PARTIAL_SEPARATION).

### Top 20

| rank | stand | township | area_sqm | total | pool inv | OS/POV | corner | shape_v2 | spatial_v2 | pool_presence | aerial | exterior | gis | stand_size |
| ---: | --- | --- | ---: | ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 545 | SUMMERSET EXT.6 | 918.0 | 0.7681 | YES | CONFIRMED | YES | 0.8763 | None | 0.14 | 0.0872 | 0.0466 | 0.015 | 0.0539 |
| 2 | 868 | SUMMERSET EXT.3 | 958.0 | 0.7608 | YES | CONFIRMED | UNKNOWN | 0.8785 | None | 0.14 | 0.0768 | 0.0428 | 0.015 | 0.06 |
| 3 | 568 | SUMMERSET EXT.13 | 998.0 | 0.7523 | YES | CONFIRMED | UNKNOWN | 0.8055 | None | 0.14 | 0.0855 | 0.0458 | 0.015 | 0.0661 |
| 4 | 572 | SUMMERSET EXT.13 | 1097.0 | 0.7427 | YES | CONFIRMED | YES | 0.8188 | None | 0.14 | 0.0796 | 0.0444 | 0.015 | 0.0589 |
| 5 | 897 | SUMMERSET EXT.3 | 1000.0 | 0.7353 | YES | CONFIRMED | UNKNOWN | 0.7738 | None | 0.14 | 0.0808 | 0.0445 | 0.015 | 0.0664 |
| 6 | 672 | SUMMERSET EXT.13 | 975.0 | 0.7313 | YES | CONFIRMED | UNKNOWN | 0.7689 | None | 0.14 | 0.0816 | 0.0454 | 0.015 | 0.0626 |
| 7 | 523 | SUMMERSET EXT.6 | 1025.0 | 0.7234 | UNKNOWN | CONFIRMED | YES | 0.7306 | None | 0.14 | 0.0813 | 0.0442 | 0.015 | 0.0698 |
| 8 | 629 | SUMMERSET EXT.13 | 1125.0 | 0.719 | YES | CONFIRMED | UNKNOWN | 0.7589 | None | 0.14 | 0.0825 | 0.0437 | 0.015 | 0.0547 |
| 9 | 665 | SUMMERSET EXT.13 | 899.0 | 0.7047 | YES | CONFIRMED | UNKNOWN | 0.7206 | None | 0.14 | 0.0834 | 0.0458 | 0.015 | 0.051 |
| 10 | 540 | SUMMERSET EXT.6 | 1102.0 | 0.7025 | YES | CONFIRMED | YES | 0.7111 | None | 0.14 | 0.0802 | 0.0431 | 0.015 | 0.0582 |
| 11 | 350 | SUMMERSET EXT.6 | 992.0 | 0.701 | YES | CONFIRMED | YES | 0.6766 | None | 0.14 | 0.0834 | 0.0438 | 0.015 | 0.0651 |
| 12 | 673 | SUMMERSET EXT.13 | 990.0 | 0.6959 | UNKNOWN | CONFIRMED | UNKNOWN | 0.6523 | None | 0.14 | 0.0847 | 0.0465 | 0.015 | 0.0648 |
| 13 | 382 | SUMMERSET EXT.6 | 1251.0 | 0.6891 | YES | CONFIRMED | YES | 0.7174 | None | 0.14 | 0.0847 | 0.0456 | 0.015 | 0.0355 |
| 14 | 1/417 | SUMMERSET EXT.6 | 524.0 | 0.6859 | YES | CONFIRMED | YES | 0.8219 | None | 0.14 | 0.0811 | 0.0439 | 0.015 | 0.0 |
| 15 | 1/603 | SUMMERSET EXT.13 | 600.0 | 0.6849 | YES | CONFIRMED | UNKNOWN | 0.804 | None | 0.14 | 0.0801 | 0.0447 | 0.015 | 0.0056 |
| 16 | 1/449 | SUMMERSET EXT.6 | 594.0 | 0.6839 | YES | CONFIRMED | UNKNOWN | 0.8209 | None | 0.14 | 0.0753 | 0.0434 | 0.015 | 0.0047 |
| 17 | 591 | SUMMERSET EXT.13 | 1083.0 | 0.6781 | YES | CONFIRMED | YES | 0.6163 | None | 0.14 | 0.0853 | 0.0449 | 0.015 | 0.061 |
| 18 | 1/450 | SUMMERSET EXT.6 | 529.0 | 0.6767 | YES | CONFIRMED | YES | 0.7996 | None | 0.14 | 0.0787 | 0.0452 | 0.015 | 0.0 |
| 19 | 1105 | SUMMERSET EXT.6 | 2191.0 | 0.6713 | UNKNOWN | CONFIRMED | UNKNOWN | 0.7711 | None | 0.14 | 0.0828 | 0.0459 | 0.015 | 0.0 |
| 20 | 644 | SUMMERSET EXT.13 | 960.0 | 0.6698 | YES | CONFIRMED | UNKNOWN | 0.5944 | None | 0.14 | 0.0836 | 0.047 | 0.015 | 0.0603 |

### Top 5 stands + panels

- **#1** stand `545` score=0.7681 shape_v2=0.8763 POV=CONFIRMED corner=YES panel=`data/investigations/blind_117170887_complete_estate/panels/top1_545.jpg`
- **#2** stand `868` score=0.7608 shape_v2=0.8785 POV=CONFIRMED corner=UNKNOWN panel=`data/investigations/blind_117170887_complete_estate/panels/top2_868.jpg`
- **#3** stand `568` score=0.7523 shape_v2=0.8055 POV=CONFIRMED corner=UNKNOWN panel=`data/investigations/blind_117170887_complete_estate/panels/top3_568.jpg`
- **#4** stand `572` score=0.7427 shape_v2=0.8188 POV=CONFIRMED corner=YES panel=`data/investigations/blind_117170887_complete_estate/panels/top4_572.jpg`
- **#5** stand `897` score=0.7353 shape_v2=0.7738 POV=CONFIRMED corner=UNKNOWN panel=`data/investigations/blind_117170887_complete_estate/panels/top5_897.jpg`

## H. STOP

Freeze is committed. Manual Top-5 assessment comes next. Do not recover ground truth, rerank, or retune Scoring v2 from this report.
