# Blind PIE freeze — listing 117262832 on `carlswald_north_corrected_002`

First clean blind validation after **PR #23** (Hybrid extraction) + **PR #24** (adapter allows `scoring_ready=true` FastSAM into Scoring v2). Scoring v2, Pool Gate, OS v1, inventory labels, and ranking weights are unchanged. Distinctive Contour v2 is reporting-only.

- **Freeze path:** `data/investigations/blind_117262832_complete_estate/freeze.json`
- **On-disk SHA256** (matches `freeze.sha256`, verified after write): `32ecd4b526d4a299e143c869761664a9ed7a4b2d9ae65aba6ed300583a1dd10a`
- **Harness commit:** `5b15e39`
- **PR:** #25
- **Stack:** PR #23 extraction + PR #24 adapter; Scoring v2 frozen
- **Official score:** `hybrid_v2`
- **Universe:** 400 unique erven
- **Ground truth applied to ranking:** no
- **Ground-truth recovery in this test:** **not performed** (STOP after freeze)
- **Distinctive Contour v2 used in ranking:** no
- **Geometry-discrimination class (frozen classifier):** **STRONG** (`SMALL_SUBSET`)
- **Do not treat Top 1 as truth.** Top 5 is for manual visual inspection.

## A. Blindness

Before freeze: no street / stand / erf-number / coordinate / archived-identity / agent-cross-listing / Private Property / GIS-parcel / unique-stand-size reverse lookup / prior advertisement / seller-social search. Prior `117262832` artefacts: **none found** (`workspace_path_hits_excluded=[]`; frozen Hybrid JSON does not contain this listing). Photos downloaded fresh. Historical false-positive clusters from `116978058` / other blinds were **not** used to alter ranking. Historical freeze trees for `116978058`, `116889694`, `116778622`, `116273255`, `116223230` were not modified.

## B. Acquisition

**Fresh.** 38/39 photos downloaded, 0 reused, **1 failed**. Video **YES** (1). Title / street / stand omitted from freeze.

| Field | Value |
| --- | --- |
| Property type | House |
| Erf size | 869 m² |
| Floor size | 510 m² |
| Bedrooms | 4 |
| Listing photos | 39 (38 fresh, 1 failed) |
| Video | **YES** (count=1) |
| CLIP interior | 20 |
| CLIP exterior | 13 |
| CLIP driveway | 6 |
| CLIP garden/patio | 7 |
| CLIP aerial | **2** |
| CLIP `pool_garden` | **3** |
| Feature hits | swimming pool, covered patio, landscaped |

CLIP scene counts: `front_elevation` 2, `aerial` 2, `pool_garden` 3, `contextual` 4, `interior` 20, `driveway_access` 6, `rear_elevation` 1.

Useful pool frames (CLIP): `117262832-005`, `117262832-037`, `117262832-038`.

Useful garden/patio: `005`, `006`, `007`, `008`, `016`, `037`, `038`.

Useful driveway: `017`, `020`, `021`, `024`, `028`, `030`.

Aerial / near-nadir Hybrid viewpoints extracted: `003`, `039`.

Observational note (not a ranking change): `freeze_payload` still omits `useful_exterior_views` from the acquisition block; exterior count is 13.

## C. Pool Gate

Listing **POOL = YES**, determined from listing evidence **before** estate ranking.

Reason: `text_and_media_independently_support_private_pool`

Evidence: listing text; Hybrid scoring-ready frames = 4; Hybrid pool viewpoints = 4; CLIP `pool_garden` = 3; listing-pool-object 3/8 detected (`004`, `037`, `038`). Colour not used. Inventory labels unchanged.

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

## D. Hybrid geometry extraction (PR #23)

Official Hybrid pick: **`117262832-039`**, `fastsam_fallback`, `aerial_near_nadir`.

Selection reason: `best_valid_geometry viewpoint=aerial_near_nadir source=fastsam_fallback quality=64.066; aerial/near-nadir outranks oblique when both valid; incompatible contours are not averaged`.

`n_extracted=11`, `n_scoring_ready=4`, `n_overview_ready=4`. Frame agreement: **disagree** (aspect span 1.441, solidity span 0.297, indents `[1,1,2,1]`). Contours were **not averaged**.

### D.1 Useful / scoring-ready frames

| Frame | Viewpoint | Detector/source | CLIP pool | Status | `scoring_ready` | Reject / accept reason | Raw | Simplified | 64-pt | Aspect | Solidity | Major indents | Dir. changes | Shape class | Spa / secondary |
| --- | --- | --- | ---: | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 003 | aerial_near_nadir | FastSAM mask (SAM2 collapsed) | 0.456 | scoring-ready | **true** | FastSAM aerial after YOLOE miss / SAM2 indent collapse | yes (287) | yes | 64 | 1.160 | 0.939 | 1 | 4 | irregular | none |
| 005 | pool_overview | FastSAM+SAM2 box (presence) | 0.512 | presence_only | false | `fastsam_not_aerial_planform` | yes (1199) | yes | 64 | 6.986 | 0.893 | 1 | 4 | irregular | none |
| 037 | pool_overview | YOLOE/SAM2 box | 0.403 | scoring-ready | **true** | `yoloe_valid_sam2_box` | yes (2238) | yes | 64 | 2.600 | 0.650 | 1 | 4 | irregular | none |
| 038 | pool_overview | YOLOE/SAM2 box | 0.691 | scoring-ready | **true** | `yoloe_valid_sam2_box` | yes (3169) | yes | 64 | 2.601 | 0.677 | 2 | 7 | irregular | secondary present (9 extra blobs; diagnostic only) |
| 039 | aerial_near_nadir | FastSAM mask (SAM2 collapsed) | 0.514 | scoring-ready | **true** | FastSAM aerial after YOLOE miss / SAM2 indent collapse | yes (313) | yes | 64 | 2.418 | 0.946 | 1 | 5 | irregular | none |

Other extracted frames stayed presence-only (not useful pool planforms): `004` contamination, `006` vegetation, `007` bathtub/bathroom, `008`/`014`/`017` below min area.

### D.2 Official trace (`039`)

**source → detection → selected mask → raw contour → simplified contour → 64-point contour → scoring-ready**

1. **source:** listing photo `117262832-039`
2. **viewpoint:** `aerial_near_nadir`
3. **detection:** YOLOE primary + recall ladder → `no_valid_yoloe_pool`
4. **candidates:** FastSAM proposals; CLIP ranking kept a pool-dominant mask (`pool=0.514`, `deck=0.216`, vegetation ~0) and rejected turf/vegetation/contamination
5. **selected mask:** FastSAM; SAM2 box fill **rejected** (`sam2_collapsed_major_indents`); FastSAM mask kept
6. **raw contour:** yes, 313 points; GEOMETRY PRESERVED (raw indents 1 → scoring 1)
7. **simplified contour:** recorded `ok`
8. **64-point contour:** recorded `ok`, length 64
9. **scoring-ready:** **accepted** (`fastsam_mask_kept_after_sam2_collapse_scoring_ready` / source_reason `no_valid_yoloe_fastsam_selected`)

`037` / `038` traces: YOLOE detect → SAM2 box accepted → raw → simplify → 64-pt → scoring-ready. Aerial FastSAM still outranked these oblique overviews for the official pick.

## E. PR #24 adapter

Unchanged adapter rules. Observational result in `adapter_observational.json`:

| Frame | Source | `scoring_ready` | Adapter |
| --- | --- | --- | --- |
| 003 | FastSAM fallback | true | **ACCEPTED** |
| 037 | YOLOE/SAM2 | true | **ACCEPTED** |
| 038 | YOLOE/SAM2 | true | **ACCEPTED** |
| 039 | FastSAM fallback | true | **ACCEPTED** |
| 004–008, 014, 017 | presence_only | false | NOT_SCORING_READY |

Official Scoring v2 geometry source: **FastSAM fallback** (`fastsam_used=true`). Legitimate FastSAM `scoring_ready=true` contours reached the existing shape pipeline. No adapter rule was changed during this run.

## F. Official listing fingerprint

Not `NO_SHAPE_SIGNAL`.

| | Value |
| --- | --- |
| Selected frame | `117262832-039` |
| Source | FastSAM fallback |
| Viewpoint | aerial_near_nadir |
| Extraction-quality reason | aerial/near-nadir outranks oblique; quality 64.066 (highest) |
| Hybrid aspect | 2.418 |
| Scoring-v2 elongation (fingerprint) | 1.3655 |
| Hybrid solidity | 0.9463 |
| Scoring-v2 solidity | 0.9455 |
| Major indents | 1 |
| Directional changes | 5 |
| Shape class (Hybrid generic) | irregular |
| Distinctive planform labels | compact_rounded (not L / T / kidney / freeform / elongated) |
| Normalized contour length | 64 |
| Pool–house geometry | not measurable in Hybrid v1 |

The Hybrid min-area-rect aspect (2.418) and Scoring v2 elongation (1.3655) differ; both are recorded. Ranking uses Scoring v2 descriptors. Geometry was not manufactured.

## G. Frozen Top 20 (Scoring v2 unchanged)

Weights: pool presence `0.14`, shape `0.36`, spatial `0.22`, aerial `0.12`, exterior `0.06`, GIS `0.03`, stand size `0.07`. Neutral/default values unchanged.

| Rank | Stand | Extension | Total | Inventory | OS | Pool-pres. | `shape_v2` | Shape contrib | Spatial | Aerial | Exterior | GIS | Stand-size |
| ---: | --- | --- | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 654 | EXT.13 | 0.7725 | YES | CONFIRMED | 0.14 | 0.8744 | 0.3148 | 0.11 | 0.0958 | 0.0434 | 0.015 | 0.0535 |
| 2 | 467 | EXT.6 | 0.7479 | YES | CONFIRMED | 0.14 | 0.7776 | 0.2799 | 0.11 | 0.0925 | 0.0427 | 0.015 | 0.0679 |
| 3 | 405 | EXT.6 | 0.7393 | YES | CONFIRMED | 0.14 | 0.7623 | 0.2744 | 0.11 | 0.0922 | 0.0428 | 0.015 | 0.0648 |
| 4 | 644 | EXT.13 | 0.7388 | YES | PROBABLE | 0.14 | 0.7691 | 0.2769 | 0.11 | 0.0983 | 0.0449 | 0.015 | 0.0537 |
| 5 | 456 | EXT.6 | 0.7362 | YES | CONFIRMED | 0.14 | 0.7687 | 0.2767 | 0.11 | 0.0923 | 0.0418 | 0.015 | 0.0603 |
| 6 | 548 | EXT.6 | 0.7362 | YES | CONFIRMED | 0.14 | 0.8008 | 0.2883 | 0.11 | 0.0895 | 0.0419 | 0.015 | 0.0516 |
| 7 | 2/867 | EXT.3 | 0.7338 | YES | CONFIRMED | 0.14 | 0.7474 | 0.2691 | 0.11 | 0.0906 | 0.0416 | 0.015 | 0.0675 |
| 8 | 658 | EXT.13 | 0.7328 | UNKNOWN | CONFIRMED | 0.14 | 0.7420 | 0.2671 | 0.11 | 0.0935 | 0.0430 | 0.015 | 0.0641 |
| 9 | 896 | EXT.3 | 0.7328 | YES | CONFIRMED | 0.14 | 0.7529 | 0.2710 | 0.11 | 0.0923 | 0.0441 | 0.015 | 0.0603 |
| 10 | 4/870 | EXT.3 | 0.7327 | YES | CONFIRMED | 0.14 | 0.7413 | 0.2669 | 0.11 | 0.0950 | 0.0432 | 0.015 | 0.0627 |
| 11 | 443 | EXT.6 | 0.7317 | YES | CONFIRMED | 0.14 | 0.7570 | 0.2725 | 0.11 | 0.0964 | 0.0441 | 0.015 | 0.0537 |
| 12 | 649 | EXT.13 | 0.7278 | YES | CONFIRMED | 0.14 | 0.8366 | 0.3012 | 0.11 | 0.0922 | 0.0424 | 0.015 | 0.0270 |
| 13 | 487 | EXT.6 | 0.7265 | YES | CONFIRMED | 0.14 | 0.7230 | 0.2603 | 0.11 | 0.0941 | 0.0432 | 0.015 | 0.0639 |
| 14 | 359 | EXT.6 | 0.7263 | YES | CONFIRMED | 0.14 | 0.7516 | 0.2706 | 0.11 | 0.0887 | 0.0410 | 0.015 | 0.0610 |
| 15 | 347 | EXT.6 | 0.7240 | YES | CONFIRMED | 0.14 | 0.7551 | 0.2718 | 0.11 | 0.0890 | 0.0412 | 0.015 | 0.0569 |
| 16 | 903 | EXT.3 | 0.7219 | YES | CONFIRMED | 0.14 | 0.7249 | 0.2610 | 0.11 | 0.0932 | 0.0424 | 0.015 | 0.0603 |
| 17 | 899 | EXT.3 | 0.7217 | YES | CONFIRMED | 0.14 | 0.7188 | 0.2588 | 0.11 | 0.0941 | 0.0433 | 0.015 | 0.0605 |
| 18 | 535 | EXT.6 | 0.7212 | YES | CONFIRMED | 0.14 | 0.7456 | 0.2684 | 0.11 | 0.0971 | 0.0440 | 0.015 | 0.0467 |
| 19 | 500 | EXT.6 | 0.7190 | YES | CONFIRMED | 0.14 | 0.7462 | 0.2686 | 0.11 | 0.0951 | 0.0439 | 0.015 | 0.0464 |
| 20 | 873 | EXT.3 | 0.7190 | YES | CONFIRMED | 0.14 | 0.7572 | 0.2726 | 0.11 | 0.0977 | 0.0452 | 0.015 | 0.0385 |

Spatial is 0.11 on every row (`0.5 × 0.22` neutral; Hybrid omits pool–house). GIS is 0.015 (`0.5 × 0.03`).

## H. Ranking quality

| Metric | Value |
| --- | ---: |
| #1 | 0.7725 |
| #2 | 0.7479 |
| #5 | 0.7362 |
| #10 | 0.7327 |
| #20 | 0.7190 |
| #1–#2 gap | 0.0246 |
| #1–#5 gap | 0.0363 |
| #1–#10 gap | 0.0398 |
| #1–#20 gap | 0.0535 |
| Top-5 `shape_v2` spread | 0.1121 |
| Top-20 with `shape_v2 >= 0.80` | **3** (654, 548, 649) |
| Top-1 genuine evidence share | 0.6475 / 0.7725 = **83.8%** |
| Top-1 neutral/default padding | 0.1250 / 0.7725 = **16.2%** (spatial + GIS) |

**Class: STRONG** (frozen `shape_discrimination`: `SMALL_SUBSET`). Total-score gaps remain modest; do not infer identity from #1 separation.

## I. Shape discrimination

Official contour is **high-solidity, mildly indented, compact/irregular** — not a kidney/freeform signature, and not a long thin rectangle on Scoring v2 elongation (1.37).

- Frozen classifier: **tight distinctive shortlist** at `shape_v2 >= 0.80` (3 stands).
- Observational: ranks 2–5 sit in a **generic similar-pool band** (`shape_v2` 0.76–0.78). Shape isolated a small high-similarity set, but the frozen Top 5 still mixes that set with the generic band.
- Not a kidney/freeform cluster.
- Not `NO_SHAPE_SIGNAL`.

Do not infer correctness from score separation alone. Visual inspection of Top 5 is required. Top 1 is **not** assumed truth.

## J. Proof panels

| Panel | Path |
| --- | --- |
| top1 | `data/investigations/blind_117262832_complete_estate/panels/top1_654.jpg` |
| top2 | `data/investigations/blind_117262832_complete_estate/panels/top2_467.jpg` |
| top3 | `data/investigations/blind_117262832_complete_estate/panels/top3_405.jpg` |
| top4 | `data/investigations/blind_117262832_complete_estate/panels/top4_644.jpg` |
| top5 | `data/investigations/blind_117262832_complete_estate/panels/top5_456.jpg` |

Listing contour proof: `data/investigations/blind_117262832_complete_estate/listing_pool_contour_proof.png`

## K. Experiment answers (no ground truth)

1. **Did PR #23 extract usable real pool geometry on an unseen listing?** **YES.** Four scoring-ready frames; official aerial FastSAM contour with raw→64-pt preservation (1 indent kept). YOLOE/SAM2 also produced scoring-ready oblique overviews.
2. **Did PR #24 transport valid FastSAM geometry into Scoring v2?** **YES.** FastSAM `003` and `039` were adapter-**ACCEPTED**; official fingerprint is FastSAM `039`.
3. **Did unchanged shape ranking materially narrow the candidate field?** **Partially.** Pool Gate still leaves 332. Shape puts only 3 stands at `shape_v2 >= 0.80`, but Top-5 total scores occupy a 0.036 band.
4. **Does the frozen Top 5 visually contain the property?** **Not answered here.** STOP before ground-truth recovery. Inspect panels manually. Do not rerank after inspection.

## L. Recorded issues (no fix during this run)

- 1 listing photo failed to download.
- `freeze_payload` omits `useful_exterior_views` (pre-existing reporting gap).
- Hybrid `chosen_reason` / `source_reason` string `no_valid_yoloe_fastsam_selected` is the YOLOE-miss label even when FastSAM later succeeded.
- Hybrid aspect vs Scoring v2 elongation differ on the official contour; ranking uses Scoring v2.
- Historical `116273255` / `116223230` `freeze.json` vs `freeze.sha256` already disagreed before this run; those files were not rewritten.

## M. Freeze order

1. Wrote `freeze.json`
2. Computed SHA256
3. Wrote `freeze.sha256`
4. Verified on-disk file matches recorded hash: **yes** (`32ecd4b526d4a299e143c869761664a9ed7a4b2d9ae65aba6ed300583a1dd10a`)
5. Ground-truth lookup before this freeze commit: **none**
6. STOP. No after-freeze identity recovery in this test.
