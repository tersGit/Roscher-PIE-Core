# Blind PIE freeze — listing 115503057 on `carlswald_north_corrected_002`

Accuracy test on Hybrid extraction + FastSAM adapter + Corner Gate v1 + Pool Object Validation v1 + **Pool Inventory NO/UNKNOWN safety v1.1.0**. Scoring v2 weights unchanged. Water colour is not used in matching or scoring.

- **Freeze path:** `data/investigations/blind_115503057_complete_estate/freeze.json`
- **Freeze commit:** `5aa42ec266a0c515a75e9b7f4da623b0be84dc66`
- **On-disk SHA256** (matches `freeze.sha256`, verified after write): `a6465002f681268391d4a87f3039532f47fd97e76d9a43217a8a45c841604ff6`
- **Official score:** `hybrid_v2`
- **Universe:** 400 unique erven
- **Inventory:** `estate_property_inventory_v1.1.0_pool_obs` (YES=118 NO=33 UNKNOWN=249)
- **Ground truth applied to ranking:** no
- **Ground-truth recovery in this test:** **not performed** (STOP after freeze)
- **Geometry-discrimination class:** **MODERATE**
- **Do not treat Top 1 as truth.** Top 5 is for manual visual inspection.

## A. Blindness

Before freeze: no street / stand / erf-number / coordinate / archived-identity / agent-cross-listing / Private Property / GIS-parcel / unique-stand-size reverse lookup / prior advertisement / seller-social search. Prior `115503057` artefacts: **none found**. Photos downloaded fresh. Historical freeze trees were not modified.

## B. Acquisition

**Fresh.** 34/49 photos downloaded, 0 reused, **15 failed**. Video **YES** (1). Title / street / stand omitted from freeze.

| Field | Value |
| --- | --- |
| Property type | House |
| Erf size | 897.0 m² |
| Floor size | 672.0 m² |
| Bedrooms | 5 |
| Listing photos | 49 (34 fresh, 15 failed) |
| Video | YES (count=1) |
| CLIP interior | 20 |
| CLIP exterior | 12 |
| CLIP driveway | 7 |
| CLIP garden/patio | 6 |
| CLIP aerial | 0 |
| CLIP `pool_garden` | 2 |
| Feature hits | covered patio |

CLIP scene counts: `{'contextual': 4, 'front_elevation': 1, 'driveway_access': 7, 'interior': 20, 'pool_garden': 2}`.

Useful pool frames: `['115503057-043', '115503057-044']`.

Useful exterior: `['115503057-001', '115503057-002', '115503057-003', '115503057-004', '115503057-012', '115503057-013', '115503057-017', '115503057-023', '115503057-038', '115503057-046', '115503057-048', '115503057-049']`.

Useful driveway: `['115503057-004', '115503057-017', '115503057-023', '115503057-038', '115503057-046', '115503057-048', '115503057-049']`.

Useful aerial: `[]`.

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

Listing **CORNER = UNKNOWN** (confidence=0.0, source=`none`, high_confidence=False).

Reason: `insufficient_listing_corner_evidence`. Frames: `[]`.

Gate action: `neutral_retain_pool_gate_survivors`.

Pool Gate survivors **367 → Corner Gate survivors 367** (removed confident parcel NO=0; YES/NO/UNKNOWN parcel survivors=63/256/48).

## E. Pool Object Validation v1 (listing)

Official fingerprint: **official_hybrid_fingerprint**.

Official pick: `115503057-043` source=`yoloe_sam2` viewpoint=`pool_overview`.

Selection reason: `principal_pool_identity then cross-frame agreement then geometry then viewpoint; cluster_size=1; incompatible contours are not averaged viewpoint=pool_overview source=yoloe_sam2 identity=0.64 quality=42.228`.

Pool-to-house spatial evidence: **not available** (Hybrid v1 omits viewpoint-incompatible pool–house terms).

Per-frame POV / adapter:

| media_id | viewpoint | extractor | scoring_ready | adapter | POV | POV conf | quality | aspect | principal |
| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | --- |
| 115503057-002 | elevated_exterior | presence_only | False | NOT_SCORING_READY | UNKNOWN | None | 0.0 | None | False |
| 115503057-003 | ground_level_exterior | presence_only | False | NOT_SCORING_READY | UNKNOWN | None | 0.0 | None | False |
| 115503057-004 | ground_level_exterior | presence_only | False | NOT_SCORING_READY | UNKNOWN | None | 0.0 | None | False |
| 115503057-005 | ground_level_exterior | presence_only | False | NOT_SCORING_READY | UNKNOWN | None | 0.0 | None | False |
| 115503057-008 | ground_level_exterior | presence_only | False | NOT_SCORING_READY | UNKNOWN | None | 0.0 | None | False |
| 115503057-012 | ground_level_exterior | presence_only | False | NOT_SCORING_READY | CONFIRMED | 0.7157 | 11.6561 | 2.335 | True |
| 115503057-013 | ground_level_exterior | presence_only | False | NOT_SCORING_READY | UNKNOWN | None | 0.0 | None | False |
| 115503057-017 | ground_level_exterior | presence_only | False | NOT_SCORING_READY | UNKNOWN | None | 0.0 | None | False |
| 115503057-043 | pool_overview | YOLOE/SAM2 | True | ACCEPTED | CONFIRMED | 0.64 | 42.2276 | 3.752 | True |
| 115503057-044 | pool_overview | presence_only | False | NOT_SCORING_READY | UNKNOWN | None | 0.0 | None | False |
| 115503057-046 | ground_level_exterior | presence_only | False | NOT_SCORING_READY | CONFIRMED | 0.6494 | 11.6507 | 6.621 | True |
| 115503057-048 | ground_level_exterior | presence_only | False | NOT_SCORING_READY | UNKNOWN | None | 0.0 | None | False |
| 115503057-049 | ground_level_exterior | presence_only | False | NOT_SCORING_READY | UNKNOWN | None | 0.0 | None | False |

## F. Pool Object Validation v1 (candidates, copies only)

OS JSON rewritten: **False**. Ranked=367.

CONFIRMED=121 UNKNOWN=235 REJECTED=11 missing=0.

## G. Scoring v2 freeze (unchanged weights)

Weights: pool_presence 0.14, shape_v2 0.36, spatial_v2 0.22, aerial 0.12, exterior 0.06, gis 0.03, stand_size 0.07.

Ranked survivors: **367**.

| #1 | #2 | #5 | #10 | #20 |
| --- | --- | --- | --- | --- |
| 0.7265 | 0.72 | 0.7152 | 0.7081 | 0.6894 |

Class: **MODERATE** (PARTIAL_SEPARATION).

### Top 20

| rank | stand | township | area_sqm | total | pool inv | OS/POV | corner | shape_v2 | spatial_v2 | pool_presence | aerial | exterior | gis | stand_size |
| ---: | --- | --- | ---: | ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 868 | SUMMERSET EXT.3 | 958.0 | 0.7265 | YES | CONFIRMED | UNKNOWN | 0.8261 | None | 0.14 | 0.06 | 0.0447 | 0.015 | 0.0594 |
| 2 | 624 | SUMMERSET EXT.13 | 886.0 | 0.72 | YES | CONFIRMED | NO | 0.7777 | None | 0.14 | 0.06 | 0.047 | 0.015 | 0.0681 |
| 3 | 648 | SUMMERSET EXT.13 | 920.0 | 0.7184 | YES | CONFIRMED | NO | 0.7902 | None | 0.14 | 0.06 | 0.0429 | 0.015 | 0.066 |
| 4 | 545 | SUMMERSET EXT.6 | 918.0 | 0.7163 | YES | CONFIRMED | YES | 0.7685 | None | 0.14 | 0.06 | 0.0483 | 0.015 | 0.0664 |
| 5 | 401 | SUMMERSET EXT.6 | 919.0 | 0.7152 | YES | CONFIRMED | NO | 0.7712 | None | 0.14 | 0.06 | 0.0463 | 0.015 | 0.0662 |
| 6 | 444 | SUMMERSET EXT.6 | 1044.0 | 0.7131 | YES | CONFIRMED | NO | 0.8231 | None | 0.14 | 0.06 | 0.0473 | 0.015 | 0.0445 |
| 7 | 482 | SUMMERSET EXT.6 | 1007.0 | 0.7131 | YES | CONFIRMED | NO | 0.8053 | None | 0.14 | 0.06 | 0.0472 | 0.015 | 0.0509 |
| 8 | 901 | SUMMERSET EXT.3 | 914.0 | 0.7124 | YES | CONFIRMED | NO | 0.7734 | None | 0.14 | 0.06 | 0.042 | 0.015 | 0.0671 |
| 9 | 583 | SUMMERSET EXT.13 | 917.0 | 0.7109 | YES | CONFIRMED | NO | 0.7541 | None | 0.14 | 0.06 | 0.0479 | 0.015 | 0.0665 |
| 10 | 461 | SUMMERSET EXT.6 | 967.0 | 0.7081 | YES | CONFIRMED | NO | 0.778 | None | 0.14 | 0.06 | 0.0451 | 0.015 | 0.0579 |
| 11 | 568 | SUMMERSET EXT.13 | 998.0 | 0.7055 | YES | CONFIRMED | UNKNOWN | 0.7817 | None | 0.14 | 0.06 | 0.0466 | 0.015 | 0.0525 |
| 12 | 428 | SUMMERSET EXT.6 | 961.0 | 0.7041 | YES | CONFIRMED | NO | 0.7561 | None | 0.14 | 0.06 | 0.048 | 0.015 | 0.0589 |
| 13 | 572 | SUMMERSET EXT.13 | 1097.0 | 0.7022 | YES | CONFIRMED | YES | 0.8209 | None | 0.14 | 0.06 | 0.0463 | 0.015 | 0.0353 |
| 14 | 352 | SUMMERSET EXT.6 | 886.0 | 0.7002 | YES | CONFIRMED | NO | 0.7319 | None | 0.14 | 0.06 | 0.0436 | 0.015 | 0.0681 |
| 15 | 446 | SUMMERSET EXT.6 | 993.0 | 0.7002 | YES | CONFIRMED | NO | 0.7654 | None | 0.14 | 0.06 | 0.0463 | 0.015 | 0.0534 |
| 16 | 423 | SUMMERSET EXT.6 | 950.0 | 0.6996 | YES | CONFIRMED | NO | 0.7396 | None | 0.14 | 0.06 | 0.0475 | 0.015 | 0.0608 |
| 17 | 468 | SUMMERSET EXT.6 | 986.0 | 0.6966 | YES | CONFIRMED | NO | 0.7539 | None | 0.14 | 0.06 | 0.0456 | 0.015 | 0.0546 |
| 18 | 351 | SUMMERSET EXT.6 | 978.0 | 0.6925 | YES | CONFIRMED | NO | 0.7339 | None | 0.14 | 0.06 | 0.0473 | 0.015 | 0.056 |
| 19 | 667 | SUMMERSET EXT.13 | 944.0 | 0.6903 | YES | CONFIRMED | NO | 0.7167 | None | 0.14 | 0.06 | 0.0454 | 0.015 | 0.0618 |
| 20 | 874 | SUMMERSET EXT.3 | 1013.0 | 0.6894 | YES | CONFIRMED | NO | 0.7445 | None | 0.14 | 0.06 | 0.0465 | 0.015 | 0.0499 |

### Top 5 stands + panels

- **#1** stand `868` score=0.7265 shape_v2=0.8261 spatial_v2=None pool=YES corner=UNKNOWN panel=`data/investigations/blind_115503057_complete_estate/panels/top1_868.jpg`
- **#2** stand `624` score=0.72 shape_v2=0.7777 spatial_v2=None pool=YES corner=NO panel=`data/investigations/blind_115503057_complete_estate/panels/top2_624.jpg`
- **#3** stand `648` score=0.7184 shape_v2=0.7902 spatial_v2=None pool=YES corner=NO panel=`data/investigations/blind_115503057_complete_estate/panels/top3_648.jpg`
- **#4** stand `545` score=0.7163 shape_v2=0.7685 spatial_v2=None pool=YES corner=YES panel=`data/investigations/blind_115503057_complete_estate/panels/top4_545.jpg`
- **#5** stand `401` score=0.7152 shape_v2=0.7712 spatial_v2=None pool=YES corner=NO panel=`data/investigations/blind_115503057_complete_estate/panels/top5_401.jpg`

## H. STOP

Freeze is committed. Manual Top-5 assessment comes next. Do not recover ground truth, rerank, or retune Scoring v2 from this report.
