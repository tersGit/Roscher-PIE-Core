# Current-stack regression freeze — listing 116778622 on `carlswald_north_corrected_002`

**IMPROVED-STACK REGRESSION TEST.** Not a first-time blind. Previous PR #20 freeze is preserved at `data/investigations/blind_116778622_complete_estate/` and was **not** used as ranking input.

Accuracy test on Hybrid extraction + FastSAM adapter + Corner Gate v1 + Pool Object Validation v1 + **Pool Inventory NO/UNKNOWN safety v1.1.0**. Scoring v2 weights unchanged. Water colour is not used. PR #31 recommendations (omit-null pad, pool-scale, building-footprint scoring) are **not** implemented.

- **Freeze path:** `data/investigations/blind_116778622_current_stack/freeze.json`
- **Freeze commit:** `60b85359aa509b3664c096b7d752c993b496d7e0`
- **On-disk SHA256** (matches `freeze.sha256`, verified after write): `dce17f82162920ceeb6d39c2aa2b456a5bcdb16399ecfeb853e7892a0b694a29`
- **Official score:** `hybrid_v2`
- **Universe:** 400 unique erven
- **Inventory:** `estate_property_inventory_v1.1.0_pool_obs` (YES=118 NO=33 UNKNOWN=249)
- **Ground truth applied to ranking:** no
- **Ground-truth recovery in this test:** **not performed** (STOP after freeze)
- **PR #20 comparison in this test:** **not performed** (STOP after freeze)
- **Geometry-discrimination class:** **STRONG**
- **Do not treat Top 1 as truth.** Top 5 is for manual visual inspection.

## A. Blindness / regression isolation

Before freeze: no street / stand / erf-number / coordinate / archived-identity / agent-cross-listing / Private Property / GIS-parcel / unique-stand-size reverse lookup / prior advertisement / seller-social search. PR #20 ranking, shortlist, candidate identities, panels, and conclusions were not read as ranking inputs. Photos downloaded fresh. Historical PR #20 freeze tree left untouched at `data/investigations/blind_116778622_complete_estate`.

Prior-path inventory (excluded from ranking): `{'listing_id': '116778622', 'workspace_path_hits_excluded': [], 'frozen_hybrid_json_contains_listing': False, 'frozen_hybrid_json_used_as_ranking_input': False, 'hybrid_source': 'extract_frame_geometry_frozen_hybrid_v1_fresh', 'excluded_from_ranking_input': True}`.

## B. Acquisition

**Fresh.** 72/72 photos downloaded, 0 reused, **0 failed**. Video **YES** (1). Title / street / stand omitted from freeze.

| Field | Value |
| --- | --- |
| Property type | House |
| Erf size | 1226.0 m² |
| Floor size | 427.0 m² |
| Bedrooms | 5 |
| Listing photos | 72 (72 fresh, 0 failed) |
| Video | YES (count=1) |
| CLIP interior | 41 |
| CLIP exterior | 15 |
| CLIP driveway | 7 |
| CLIP garden/patio | 20 |
| CLIP aerial | 3 |
| CLIP `pool_garden` | 13 |
| Feature hits | swimming pool, covered patio, double garage, landscaped |

CLIP scene counts: `{'contextual': 7, 'pool_garden': 13, 'front_elevation': 1, 'aerial': 3, 'driveway_access': 7, 'interior': 41}`.

Useful pool frames: `['116778622-002', '116778622-005', '116778622-049', '116778622-050', '116778622-051', '116778622-060', '116778622-061', '116778622-062', '116778622-063', '116778622-064', '116778622-066', '116778622-067', '116778622-072']`.

Useful exterior: `['116778622-001', '116778622-003', '116778622-006', '116778622-008', '116778622-025', '116778622-037', '116778622-040', '116778622-045', '116778622-057', '116778622-058', '116778622-059', '116778622-065', '116778622-068', '116778622-069', '116778622-070']`.

Useful driveway: `['116778622-008', '116778622-025', '116778622-037', '116778622-040', '116778622-068', '116778622-069', '116778622-070']`.

Useful aerial: `['116778622-004', '116778622-007', '116778622-071']`.

## C. Pool Gate

Listing **POOL = YES**, determined from listing evidence **before** estate ranking.

Reason: `text_and_media_independently_support_private_pool`

| | Count |
| --- | ---: |
| Starting parcels | 400 |
| Inventory YES / NO / UNKNOWN | 118 / 33 / 249 |
| YES survivors | 118 |
| UNKNOWN survivors | 249 |
| Candidates removed (confident NO) | 33 |
| Candidates retained | **367** |
| Reduction | 8.25% |

## D. Corner Gate v1

Listing **CORNER = YES** (confidence=0.86, source=`aerial`, high_confidence=True).

Reason: `roads_visible_along_two_parcel_sides`. Frames: `['116778622-007', '116778622-045', '116778622-065']`.

Gate action: `high_confidence_listing_yes_drop_confident_parcel_no`.

Pool Gate survivors **367 → Corner Gate survivors 111** (removed confident parcel NO=256; YES/NO/UNKNOWN parcel survivors=63/0/48).

## E. Pool Object Validation v1 (listing)

Official fingerprint: **official_hybrid_fingerprint**.

Official pick: `116778622-005` source=`yoloe_sam2` viewpoint=`pool_overview`.

Selection reason: `principal_pool_identity then cross-frame agreement then geometry then viewpoint; cluster_size=6; incompatible contours are not averaged viewpoint=pool_overview source=yoloe_sam2 identity=0.913 quality=44.019`.

Pool-to-house spatial evidence: **not available** (Hybrid v1 omits viewpoint-incompatible pool–house terms).

Per-frame POV / adapter:

| media_id | viewpoint | extractor | scoring_ready | adapter | POV | POV conf | quality | aspect | principal |
| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | --- |
| 116778622-002 | pool_overview | YOLOE/SAM2 | True | ACCEPTED | CONFIRMED | 0.7506 | 43.9987 | 2.323 | True |
| 116778622-003 | ground_level_exterior | presence_only | False | NOT_SCORING_READY | UNKNOWN | None | 0.0 | None | False |
| 116778622-004 | elevated_exterior | presence_only | False | NOT_SCORING_READY | CONFIRMED | 0.6975 | 29.1497 | 2.798 | True |
| 116778622-005 | pool_overview | YOLOE/SAM2 | True | ACCEPTED | CONFIRMED | 0.9128 | 44.0194 | 1.79 | True |
| 116778622-006 | ground_level_exterior | presence_only | False | NOT_SCORING_READY | UNKNOWN | 0.4433 | 11.8934 | 10.0 | True |
| 116778622-007 | elevated_exterior | presence_only | False | NOT_SCORING_READY | CONFIRMED | 0.7673 | 27.2474 | 1.171 | False |
| 116778622-038 | garden_only | presence_only | False | NOT_SCORING_READY | UNKNOWN | None | 0.0 | None | False |
| 116778622-045 | elevated_exterior | presence_only | False | NOT_SCORING_READY | UNKNOWN | None | 0.0 | None | False |
| 116778622-049 | elevated_exterior | presence_only | False | NOT_SCORING_READY | CONFIRMED | 0.6975 | 24.8731 | 1.854 | False |
| 116778622-050 | pool_overview | YOLOE/SAM2 | True | ACCEPTED | CONFIRMED | 0.8416 | 44.8211 | 1.668 | True |
| 116778622-051 | elevated_exterior | YOLOE/SAM2 | True | ACCEPTED | UNKNOWN | 0.6147 | 51.9357 | 8.447 | True |
| 116778622-057 | ground_level_exterior | presence_only | False | NOT_SCORING_READY | UNKNOWN | None | 0.0 | None | False |
| 116778622-058 | garden_only | presence_only | False | NOT_SCORING_READY | CONFIRMED | 0.6032 | 2.4921 | 1.597 | False |
| 116778622-059 | garden_only | presence_only | False | NOT_SCORING_READY | UNKNOWN | 0.561 | -0.3745 | 1.712 | False |
| 116778622-060 | pool_overview | presence_only | False | NOT_SCORING_READY | UNKNOWN | 0.598 | 18.4637 | 1.976 | True |
| 116778622-061 | garden_only | presence_only | False | NOT_SCORING_READY | CONFIRMED | 0.6497 | 3.3005 | 2.074 | False |
| 116778622-062 | pool_overview | YOLOE/SAM2 | True | ACCEPTED | CONFIRMED | 0.7297 | 43.0147 | 2.221 | True |
| 116778622-063 | pool_overview | presence_only | False | NOT_SCORING_READY | UNKNOWN | 0.6399 | 20.4415 | 3.237 | True |
| 116778622-064 | pool_overview | YOLOE/SAM2 | True | ACCEPTED | CONFIRMED | 0.758 | 41.2974 | 3.02 | True |
| 116778622-065 | elevated_exterior | presence_only | False | NOT_SCORING_READY | UNKNOWN | 0.5979 | 24.5118 | 2.134 | False |
| 116778622-066 | pool_overview | presence_only | False | NOT_SCORING_READY | CONFIRMED | 0.8256 | 19.3049 | 1.444 | True |
| 116778622-067 | pool_overview | presence_only | False | NOT_SCORING_READY | CONFIRMED | 0.6146 | 15.8573 | 1.214 | True |
| 116778622-068 | ground_level_exterior | presence_only | False | NOT_SCORING_READY | CONFIRMED | 0.6154 | 10.2675 | 3.243 | False |
| 116778622-069 | ground_level_exterior | presence_only | False | NOT_SCORING_READY | UNKNOWN | None | 0.0 | None | False |
| 116778622-070 | ground_level_exterior | presence_only | False | NOT_SCORING_READY | UNKNOWN | None | 0.0 | None | False |
| 116778622-071 | elevated_exterior | presence_only | False | NOT_SCORING_READY | UNKNOWN | 0.4078 | 26.2823 | 1.212 | False |
| 116778622-072 | pool_overview | YOLOE/SAM2 | True | ACCEPTED | CONFIRMED | 0.8588 | 43.7734 | 2.098 | True |

## F. Pool Object Validation v1 (candidates, copies only)

OS JSON rewritten: **False**. Ranked=111.

CONFIRMED=31 UNKNOWN=77 REJECTED=3 missing=0.

## G. Scoring v2 freeze (unchanged weights)

Weights: pool_presence 0.14, shape_v2 0.36, spatial_v2 0.22, aerial 0.12, exterior 0.06, gis 0.03, stand_size 0.07.

Ranked survivors: **111**.

| #1 | #2 | #5 | #10 | #20 |
| --- | --- | --- | --- | --- |
| 0.7404 | 0.7276 | 0.7118 | 0.703 | 0.6798 |

Class: **STRONG** (SMALL_SUBSET).

### Top 20

| rank | stand | township | area_sqm | total | pool inv | OS/POV | corner | shape_v2 | spatial_v2 | pool_presence | aerial | exterior | gis | stand_size |
| ---: | --- | --- | ---: | ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 540 | SUMMERSET EXT.6 | 1102.0 | 0.7404 | YES | CONFIRMED | YES | 0.8161 | None | 0.14 | 0.0845 | 0.0427 | 0.015 | 0.0543 |
| 2 | 411 | SUMMERSET EXT.6 | 1294.0 | 0.7276 | UNKNOWN | CONFIRMED | UNKNOWN | 0.7519 | None | 0.14 | 0.0868 | 0.0437 | 0.015 | 0.0614 |
| 3 | 591 | SUMMERSET EXT.13 | 1083.0 | 0.7274 | YES | CONFIRMED | YES | 0.775 | None | 0.14 | 0.0878 | 0.0437 | 0.015 | 0.0519 |
| 4 | 897 | SUMMERSET EXT.3 | 1000.0 | 0.719 | YES | CONFIRMED | UNKNOWN | 0.7683 | None | 0.14 | 0.0907 | 0.0453 | 0.015 | 0.0413 |
| 5 | 871 | SUMMERSET EXT.3 | 1490.0 | 0.7118 | YES | CONFIRMED | YES | 0.7653 | None | 0.14 | 0.0894 | 0.0454 | 0.015 | 0.0365 |
| 6 | 640 | SUMMERSET EXT.13 | 1540.0 | 0.7078 | UNKNOWN | CONFIRMED | UNKNOWN | 0.7702 | None | 0.14 | 0.089 | 0.0463 | 0.015 | 0.0302 |
| 7 | 382 | SUMMERSET EXT.6 | 1251.0 | 0.706 | YES | CONFIRMED | YES | 0.6685 | None | 0.14 | 0.0877 | 0.0458 | 0.015 | 0.0668 |
| 8 | 898 | SUMMERSET EXT.3 | 1152.0 | 0.7054 | YES | CONFIRMED | YES | 0.6892 | None | 0.14 | 0.087 | 0.0446 | 0.015 | 0.0606 |
| 9 | 644 | SUMMERSET EXT.13 | 960.0 | 0.704 | YES | CONFIRMED | UNKNOWN | 0.7325 | None | 0.14 | 0.0916 | 0.0474 | 0.015 | 0.0362 |
| 10 | 1/373 | SUMMERSET EXT.6 | 500.0 | 0.703 | YES | CONFIRMED | UNKNOWN | 0.8285 | None | 0.14 | 0.0932 | 0.0466 | 0.015 | 0.0 |
| 11 | 673 | SUMMERSET EXT.13 | 990.0 | 0.7014 | UNKNOWN | CONFIRMED | UNKNOWN | 0.7277 | None | 0.14 | 0.0884 | 0.046 | 0.015 | 0.0401 |
| 12 | 629 | SUMMERSET EXT.13 | 1125.0 | 0.6939 | YES | CONFIRMED | UNKNOWN | 0.6746 | None | 0.14 | 0.0856 | 0.0432 | 0.015 | 0.0572 |
| 13 | 502 | SUMMERSET EXT.6 | 1032.0 | 0.6926 | YES | CONFIRMED | YES | 0.712 | None | 0.14 | 0.0834 | 0.0425 | 0.015 | 0.0454 |
| 14 | 672 | SUMMERSET EXT.13 | 975.0 | 0.6905 | YES | CONFIRMED | UNKNOWN | 0.7002 | None | 0.14 | 0.0893 | 0.046 | 0.015 | 0.0382 |
| 15 | 4/870 | SUMMERSET EXT.3 | 828.0 | 0.6894 | YES | CONFIRMED | UNKNOWN | 0.76 | None | 0.14 | 0.087 | 0.0443 | 0.015 | 0.0195 |
| 16 | 350 | SUMMERSET EXT.6 | 992.0 | 0.6883 | YES | CONFIRMED | YES | 0.7058 | None | 0.14 | 0.0852 | 0.0436 | 0.015 | 0.0403 |
| 17 | 572 | SUMMERSET EXT.13 | 1097.0 | 0.687 | YES | CONFIRMED | YES | 0.6572 | None | 0.14 | 0.0868 | 0.045 | 0.015 | 0.0536 |
| 18 | 545 | SUMMERSET EXT.6 | 918.0 | 0.6825 | YES | CONFIRMED | YES | 0.6959 | None | 0.14 | 0.09 | 0.0461 | 0.015 | 0.0309 |
| 19 | 1105 | SUMMERSET EXT.6 | 2191.0 | 0.6818 | UNKNOWN | CONFIRMED | UNKNOWN | 0.7786 | None | 0.14 | 0.0911 | 0.0455 | 0.015 | 0.0 |
| 20 | 523 | SUMMERSET EXT.6 | 1025.0 | 0.6798 | UNKNOWN | CONFIRMED | YES | 0.6605 | None | 0.14 | 0.0884 | 0.0441 | 0.015 | 0.0445 |

### Top 5 stands + panels

- **#1** stand `540` score=0.7404 shape_v2=0.8161 spatial_v2=None pool=YES corner=YES panel=`data/investigations/blind_116778622_current_stack/panels/top1_540.jpg`
- **#2** stand `411` score=0.7276 shape_v2=0.7519 spatial_v2=None pool=UNKNOWN corner=UNKNOWN panel=`data/investigations/blind_116778622_current_stack/panels/top2_411.jpg`
- **#3** stand `591` score=0.7274 shape_v2=0.775 spatial_v2=None pool=YES corner=YES panel=`data/investigations/blind_116778622_current_stack/panels/top3_591.jpg`
- **#4** stand `897` score=0.719 shape_v2=0.7683 spatial_v2=None pool=YES corner=UNKNOWN panel=`data/investigations/blind_116778622_current_stack/panels/top4_897.jpg`
- **#5** stand `871` score=0.7118 shape_v2=0.7653 spatial_v2=None pool=YES corner=YES panel=`data/investigations/blind_116778622_current_stack/panels/top5_871.jpg`

## H. STOP (freeze)

Freeze was committed as `60b85359aa509b3664c096b7d752c993b496d7e0` before evaluation. SHA256 was not rewritten.

Post-freeze evaluation (Top-5 read-out, PR #20 comparison, independent GT) is in `EVALUATION.md`. Decision vs PR #20: **INCONCLUSIVE**. Ground truth: **UNAVAILABLE**. Run class: **UNLABELLED REGRESSION TEST**. Production Scoring v2 was not modified.
