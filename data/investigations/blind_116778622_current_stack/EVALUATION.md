# Evaluation — listing 116778622 current-stack regression vs PR #20

**Do not change the freeze.** SHA256 `dce17f82162920ceeb6d39c2aa2b456a5bcdb16399ecfeb853e7892a0b694a29` (commit `60b85359aa509b3664c096b7d752c993b496d7e0`) is unchanged by this document.

This is an **UNLABELLED REGRESSION TEST**. It is not a PIE accuracy success or failure.

## Freeze identity

| Field | Value |
| --- | --- |
| Listing | Property24 `116778622` |
| Dataset | `carlswald_north_corrected_002` (400 erven) |
| Inventory | `estate_property_inventory_v1.1.0_pool_obs` YES=118 / NO=33 / UNKNOWN=249 |
| Scoring v2 | unchanged (pool 0.14, shape_v2 0.36, spatial_v2 0.22, aerial 0.12, exterior 0.06, gis 0.03, stand_size 0.07) |
| Water colour | excluded |
| PR #31 scoring changes | not implemented |
| Ranked after gates | **111** (Pool Gate 400→367, Corner Gate 367→111) |
| Discrimination class | **STRONG** (`SMALL_SUBSET`) |
| Official fingerprint | `116778622-005` YOLOE/SAM2 `pool_overview` (FastSAM not used) |
| Historical PR #20 freeze | still `3eb8f54dc03f804cff519b65d7f452444ff91e7c4133a9ec7b9b638a3337875f` |

---

## Phase 1 — Listing acquisition

Independent fresh fetch. 72/72 photos, 0 failed. Video **YES** (YouTube `LmCgdfz0iXY`). Street withheld (`Contact agent for street address`). No stand, no coordinates.

| Signal | Result |
| --- | --- |
| Images | 72 |
| Video | YES (1) |
| CLIP exterior | 15 |
| CLIP pool_garden | 13 |
| CLIP aerial | 3 (`004`, `007`, `071`) |
| CLIP driveway | 7 |
| Advertised erf | **1226 m²** |
| Advertised floor | **427 m²** |
| Beds / baths | 5 / 5.5 |
| Price | R 4 550 000 |
| Agent | Henk Humphries / RE/MAX Infoglobe |
| Corner/internal/boundary | listing copy does not say “corner”; Corner Gate later called **YES** from aerial/elevated frames |
| Driveway/garage | double garage + brick driveway visible (`007`, `068`–`070`) |

Official fingerprint was **not** hand-picked. Pipeline chose `116778622-005` (YOLOE/SAM2 pool overview).

---

## Phase 2 — Pool validation (Hybrid + FastSAM adapter + POV)

| Field | Value |
| --- | --- |
| Selected frame | `116778622-005` |
| Extractor | YOLOE/SAM2 |
| Viewpoint | `pool_overview` |
| scoring_ready | True (adapter **ACCEPTED**; 7 scoring-ready frames) |
| POV | **CONFIRMED** (confidence 0.9128) |
| Hybrid aspect | 1.79 |
| Scoring elongation | 1.3186 |
| Compactness / solidity | 0.6376 / 0.9555 |
| Indents | 1 major (raw Hybrid reported 2; scoring contour kept 1) |
| Shape class | rectangular / compact_rounded (oblique photo; not a nadir planform) |
| Pool–house spatial | omitted (viewpoint-incompatible in Hybrid v1) |
| FastSAM used in official contour | **False** |
| Extraction ambiguity | Frame `051` is also scoring-ready YOLOE/SAM2 but **elevated_exterior**, aspect **8.447**, POV **UNKNOWN**. That was PR #20’s official pick. Current POV cluster (size 6) prefers `005`. The questionable elongated `051` contour was **preserved as a scoring-ready frame and not used as the official fingerprint**. |

Listing photos show a large freeform / indented pool hard against an L-house patio, terracotta roof, grey walls, white X-rail balcony, double garage. The official contour is a plausible water outline of that pool from a night overview, with one indent retained.

---

## Phase 3 — Estate universe

| Field | Value |
| --- | --- |
| Dataset ID | `carlswald_north_corrected_002` |
| Parcels | **400** |
| Inventory YES / NO / UNKNOWN | **118 / 33 / 249** |
| Entering Pool Gate | 400 |
| After Pool Gate | **367** (33 confident NO removed, 8.25%) |
| After Corner Gate | **111** (256 confident parcel-NO removed; YES/NO/UNKNOWN survivors 63/0/48) |
| native15 | 28/28 tiles downloaded, 400/400 crops written, 0 failed |
| CLIP computed on | corner-gate survivors with native15 crops |

No parcel was dropped because it ranked badly in PR #20. Exact-1226 m² stands **604** and **690** were dropped because Corner Gate classified them **NO** (cul-de-sac / single frontage), not because of the old ranking.

---

## Phase 5 — Frozen Top 20

`spatial_v2` is **None** on every row (0.5 pad → 0.11). GIS is the constant 0.5 pad → 0.015. CLIP aerial/exterior are live.

| rank | stand | township | m² | total | pool inv | POV/OS | corner | shape_v2 | spatial_v2 | aerial | CLIP ext | GIS | stand-size |
| ---: | --- | --- | ---: | ---: | --- | --- | --- | ---: | --- | ---: | ---: | ---: | ---: |
| 1 | 540 | EXT.6 | 1102 | 0.7404 | YES | CONFIRMED | YES | 0.8161 | pad 0.11 | 0.0845 | 0.0427 | 0.015 | 0.0543 |
| 2 | 411 | EXT.6 | 1294 | 0.7276 | UNKNOWN | CONFIRMED | UNKNOWN | 0.7519 | pad 0.11 | 0.0868 | 0.0437 | 0.015 | 0.0614 |
| 3 | 591 | EXT.13 | 1083 | 0.7274 | YES | CONFIRMED | YES | 0.7750 | pad 0.11 | 0.0878 | 0.0437 | 0.015 | 0.0519 |
| 4 | 897 | EXT.3 | 1000 | 0.7190 | YES | CONFIRMED | UNKNOWN | 0.7683 | pad 0.11 | 0.0907 | 0.0453 | 0.015 | 0.0413 |
| 5 | 871 | EXT.3 | 1490 | 0.7118 | YES | CONFIRMED | YES | 0.7653 | pad 0.11 | 0.0894 | 0.0454 | 0.015 | 0.0365 |
| 6 | 640 | EXT.13 | 1540 | 0.7078 | UNKNOWN | CONFIRMED | UNKNOWN | 0.7702 | pad | 0.0890 | 0.0463 | 0.015 | 0.0302 |
| 7 | 382 | EXT.6 | 1251 | 0.7060 | YES | CONFIRMED | YES | 0.6685 | pad | 0.0877 | 0.0458 | 0.015 | 0.0668 |
| 8 | 898 | EXT.3 | 1152 | 0.7054 | YES | CONFIRMED | YES | 0.6892 | pad | 0.0870 | 0.0446 | 0.015 | 0.0606 |
| 9 | 644 | EXT.13 | 960 | 0.7040 | YES | CONFIRMED | UNKNOWN | 0.7325 | pad | 0.0916 | 0.0474 | 0.015 | 0.0362 |
| 10 | 1/373 | EXT.6 | 500 | 0.7030 | YES | CONFIRMED | UNKNOWN | **0.8285** | pad | 0.0932 | 0.0466 | 0.015 | **0.000** |
| 11 | 673 | EXT.13 | 990 | 0.7014 | UNKNOWN | CONFIRMED | UNKNOWN | 0.7277 | pad | 0.0884 | 0.0460 | 0.015 | 0.0401 |
| 12 | 629 | EXT.13 | 1125 | 0.6939 | YES | CONFIRMED | UNKNOWN | 0.6746 | pad | 0.0856 | 0.0432 | 0.015 | 0.0572 |
| 13 | 502 | EXT.6 | 1032 | 0.6926 | YES | CONFIRMED | YES | 0.7120 | pad | 0.0834 | 0.0425 | 0.015 | 0.0454 |
| 14 | 672 | EXT.13 | 975 | 0.6905 | YES | CONFIRMED | UNKNOWN | 0.7002 | pad | 0.0893 | 0.0460 | 0.015 | 0.0382 |
| 15 | 4/870 | EXT.3 | 828 | 0.6894 | YES | CONFIRMED | UNKNOWN | 0.7600 | pad | 0.0870 | 0.0443 | 0.015 | 0.0195 |
| 16 | 350 | EXT.6 | 992 | 0.6883 | YES | CONFIRMED | YES | 0.7058 | pad | 0.0852 | 0.0436 | 0.015 | 0.0403 |
| 17 | 572 | EXT.13 | 1097 | 0.6870 | YES | CONFIRMED | YES | 0.6572 | pad | 0.0868 | 0.0450 | 0.015 | 0.0536 |
| 18 | 545 | EXT.6 | 918 | 0.6825 | YES | CONFIRMED | YES | 0.6959 | pad | 0.0900 | 0.0461 | 0.015 | 0.0309 |
| 19 | 1105 | EXT.6 | 2191 | 0.6818 | UNKNOWN | CONFIRMED | UNKNOWN | 0.7786 | pad | 0.0911 | 0.0455 | 0.015 | 0.000 |
| 20 | 523 | EXT.6 | 1025 | 0.6798 | UNKNOWN | CONFIRMED | YES | 0.6605 | pad | 0.0884 | 0.0441 | 0.015 | 0.0445 |

Gap #1–#2 = 0.0128. Live discriminator is almost entirely `shape_v2`.

### Top 5 explanations

**#1 Stand 540 — 1 Black Monkey Thorn Drive (EXT.6, 1102 m², CoJ `1555811`).** Highest shape_v2 (0.8161). Inventory YES, OS pool 14.31 m² CONFIRMED, parcel corner YES (Black Monkey Thorn × The Boulevard). Native15 building is a large multi-wing house; OS pool sits in an L-nook and is **small and relatively rectangular**. Listing photos show a **large freeform/indented pool** against the patio. Spatial unused (pad). Driveway PROBABLE (north). Do not treat as truth.

**#2 Stand 411 — 28 Baobab Close (EXT.6, 1294 m², CoJ `1566719`).** Closest GIS size among Top 5 (size_score 0.8767). Inventory **UNKNOWN**; frozen OS pool was **REJECTED**; ranking POV overlay is CONFIRMED. Parcel corner UNKNOWN (dual frontage, not confirmed). Native15 pool is a small backyard object. Promoted by size + shape + POV overlay, not by inventory YES.

**#3 Stand 591 — 7 Russet Bush Willow Close (EXT.13, 1083 m², CoJ `1721843`).** Inventory YES, OS pool 35.12 m² (largest of Top 5 — closer to a family pool). Corner YES (Hardekool View × Russet Bush Willow). Pool–house 9.8 m NE, unused in scoring. Visually a more credible pool scale than 540.

**#4 Stand 897 — 1 River Bush Willow Close (EXT.3, 1000 m², CoJ `1524592`).** Inventory YES, OS 23.42 m². Corner UNKNOWN. Highest aerial/exterior CLIP in Top 5 (0.7559 / 0.7555). Size 1000 vs 1226 is a mediocre stand-size contribution.

**#5 Stand 871 — 1 Coral Tree Drive (EXT.3, 1490 m², CoJ `1542074`).** Inventory YES, corner YES, OS 25.83 m². Pool–house **32.5 m** (dist/building 1.77) — listing pool is adjacent to the house. Spatial pad hides that contradiction. Stand-size is weak (1490 vs 1226).

---

## Phase 6 — Proof panels

Written at freeze time for manual inspection (not used to rerank):

- `panels/top1_540.jpg`
- `panels/top2_411.jpg`
- `panels/top3_591.jpg`
- `panels/top4_897.jpg`
- `panels/top5_871.jpg`
- `listing_pool_contour_proof.png` (official `005` contour)

Each panel shows listing photos, listing/candidate normalized contours, native15 crop, GIS boundary, OS building/pool/driveway masks, and a pool–house centroid vector. Spatial_v2 remains unused in the score.

---

## Phase 7 — PR #20 → current stack (after freeze)

Old freeze SHA `3eb8f54d…`. Old official contour **`116778622-051`** (YOLOE/SAM2, `elevated_exterior`, aspect **7.756**). Old ranked **332**. No Corner Gate, no candidate POV overlay, inventory NO=68.

### Top 20 movement

| Old # | Stand | New fate |
| ---: | --- | --- |
| 1 | 605 | **DROPPED** (corner NO, cul-de-sac Essenhout Close) |
| 2 | 444 | **DROPPED** (corner NO) |
| 3 | 572 | **#17** (corner YES) |
| 4 | 382 | **#7** (corner YES) |
| 5 | 573 | **DROPPED** (corner NO) |
| 12 / 16 | 690 / 604 | **DROPPED** (exact 1226 m² internals, corner NO) |

New Top 5 {540, 411, 591, 897, 871} **did not appear** in the old Top 20. Top-20 overlap is **2/20** (382, 572). Top-5 overlap is **empty**.

### Did concentration improve?

Mechanically yes: 332 → **111** ranked; quality class **STRONG / SMALL_SUBSET**; 31 genuine shapes; 2 with shape_v2 ≥ 0.80. The old PR #19/#20 recurring YES-pool cluster is largely gone (605/444/573 dropped).

### Were obvious visual false positives removed?

Old Top 1 **605** (5 Essenhout Close, cul-de-sac) is gone because Corner Gate listing=YES. That is an improvement **if** the listing is actually a corner. Listing evidence for two roads is **not airtight**: Corner Gate cites `007`/`045`/`065`; `045` is a balcony view over trees and `065` is a courtyard. `007` is an elevated front, not a nadir two-road proof. Confidence 0.86 is marked high-confidence.

New Top 1 **540** has a **~14 m² rectangular OS pool** vs a large freeform listing pool — a plausible remaining visual FP. Rank 10 **1/373** (500 m², highest shape_v2 0.8285) is a scale mismatch that stand-size (weight 0.07) did not kill.

### Component effects

| Stack piece | Effect on this listing |
| --- | --- |
| Hybrid | Still YOLOE/SAM2; 7 scoring-ready frames unchanged as a set vs PR #20 |
| FastSAM adapter | Official contour did **not** use FastSAM (`fastsam_used=False`) |
| POV (listing) | **Material.** Official pick moved `051` (aspect 8.4, POV UNKNOWN) → `005` (aspect 1.79, POV 0.91, cluster 6) |
| Corner Gate | **Material.** 367→111; deleted 16/20 of the old Top 20 as confident non-corners |
| Candidate POV | Overlay CONFIRMED=31 / UNKNOWN=77 / REJECTED=3 on 111 ranked. OS JSON not rewritten. **411** is inventory UNKNOWN + frozen OS REJECTED, yet ranks #2 as POV CONFIRMED |
| Null 0.5 pad | Every survivor gets spatial 0.11 + GIS 0.015. Does not uniquely promote one stand, but **hides** 871’s 32 m pool–house gap and all missing spatial identity |
| Inventory v1.1.0 | NO 68→33, Pool Gate survivors 332→367 **before** Corner Gate (more UNKNOWN kept) |

---

## Phase 8 — Independent ground truth (after freeze)

Searched without using rank as the identity hypothesis.

| Source | Street / stand |
| --- | --- |
| Property24 `116778622` | Contact agent; no stand; no coordinates |
| Schema.org / JSON-LD | locality Carlswald North Estate only |
| YouTube `LmCgdfz0iXY` | title only; no street |
| RE/MAX Infoglobe / Henk Humphries public cards | locality only |
| Private Property search on 1226 m² + copy | no street duplicate found |
| Distinctive copy (farm-style masterpiece, boma/pizza oven) | no published address |
| CoJ GIS exact 1226 m² | **two** parcels: 604 (3 Essenhout Close) and 690 (15 Karee Drive). Both are Corner=NO internals. Size is not identity |

**Confirmed stand: none.**

**Classification: UNAVAILABLE** (supporting evidence: withheld street, non-unique 1226 m², no syndicated street).

**Run class: UNLABELLED REGRESSION TEST.** Do not count as a PIE accuracy success or failure. Top 1 (540) is **not** declared ground truth.

---

## Final decision vs PR #20

# **INCONCLUSIVE**

The current stack is **more selective** (POV-fixed official pool object; Corner Gate 111-candidate universe; STRONG class; old cul-de-sac cluster mostly removed). That is architectural progress, not an accuracy result.

It is **not** a demonstrated improvement in identity: ground truth remains unavailable; new Top 1 still has a scale/shape visual conflict; Corner Gate listing-YES may be over-called from non-nadir frames; 0.5 spatial padding still equalises everyone.

**UNCHANGED** would understate the candidate-set rewrite (2/20 overlap). **REGRESSED** would require showing the new shortlist is worse against a known erf. **IMPROVED** would require labelled recovery.

Production Scoring v2 was not modified. PR #31 recommendations remain unimplemented.
