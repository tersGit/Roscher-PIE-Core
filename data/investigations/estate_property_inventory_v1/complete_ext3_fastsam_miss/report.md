# Complete Carlswald North (EXT.3+6+13) and FastSAM miss diagnostic

Dataset completion + diagnosis only. Frozen OS v1, FastSAM configuration,
native15, Scoring v2, Hybrid Pool Geometry, viewpoint gates, production
ranking, Listing Pool Gate semantics, and PR #15/#16 frozen datasets are
**unchanged**. Colour is not used in ranking. The recommended detector
experiment in **K is not implemented**.

GIS dataset: `carlswald_north_corrected_002`
Frozen 001 (330 unique erven): `carlswald_north_corrected_001` intact
  SHA256 GIS `1bab3126fdfa9d397857f67f2d0cb65ddc410fc5d82afaf1a823c63018f56608`
  SHA256 inventory `3bc02c09c293d011b8f2d866b2075e3e9863cc9af9db5c054faa0dc722aca861`

---

## A. Summerset EXT.3

| Item | Result |
| ---- | ------ |
| Source layer | CoJ Property MapServer **layer 8 `REGISTERED_STANDS`** |
| MapServer | `https://ags.joburg.org.za/server/rest/services/Property/MapServer` |
| Official name | **`SUMMERSET EXT.3`** (authoritative `TOWN_NAME_DESC`, not spatial proximity) |
| Township status | **PROCLAIMED** |
| Source parcel count | **78** Erven |
| Residential erven identified | **70** pass-1 unique (`residential` + `vacant` after filters) |
| Exclusions | **8**: 2 `RE/` remainder, 4 non-residential, 1 non-res+`RE/`, 1 non-res+area≥8000 m² |
| Duplicate handling | GIS pass 1 then unique `property_id` last-wins (same as frozen 001) |
| Final unique EXT.3 property count | **70** |
| GIS geometry coverage | 78/78 source parcels have rings; EXT.3 extent inside gated Carlswald North bbox |
| native15 imagery coverage | 8 intersecting 210 m / 1400 px tiles; all 70 pass-1 parcels intersect the grid |

EXT.2 remains absent from CoJ GIS. Membership is township-name, not proximity.

---

## B. Complete Carlswald North dataset (`002`)

| Extension | Source parcels | Included unique properties |
| --------- | -------------: | -------------------------: |
| EXT.3     | 78 | 70 |
| EXT.6     | 280 | 212 |
| EXT.13    | 136 | 118 |
| **TOTAL** | **494** | **400** |

Quality:
- Duplicate `property_id` after pass 1: **none**
- Cross-township stand numbers: **none**
- Missing geometry: **none**
- Axis-aligned bbox IoU ≥ 0.02 among neighbours: expected AABB overlap of adjacent erven, not duplicate parcels
- vs frozen 001: all **330** property_ids present, **0** geometry changes; 70 new stands are EXT.3 only

001 is kept as the PR #15/#16 universe. 002 is the complete intended estate.

Overview: `data/investigations/carlswald_north_complete/estate_overview_ext3_6_13.jpg`

---

## C. Inventory v1 on the complete estate

Classification semantics unchanged (YES / NO / UNKNOWN from frozen OS v1).

| Metric | Value |
| ------ | ----: |
| Total parcels | **400** |
| Reused from frozen 001 | **330** |
| Newly processed (EXT.3) | **70** |
| Rescanned | 70 |
| FastSAM runs | **70** (EXT.3 only) |
| Imagery tiles required / reused / downloaded | 8 / 0 / 8 |
| Crops written / reused / failed | 70 / 0 / 0 |
| Runtime | **95.5 s** |

Complete-estate inventory:

| Status | n | % |
| ------ | -: | -: |
| **YES** | **118** | **29.5%** |
| **NO** | **68** | **17.0%** |
| **UNKNOWN** | **214** | **53.5%** |

EXT.3-only split of the 70 new erven: YES 27 / NO 8 / UNKNOWN 35.

001 inventory bytes unchanged. EXT.6/13 geometry unchanged so no FastSAM rerun.

---

## D. Complete-estate Pool Gate baseline

Gate semantics unchanged. UNKNOWN always survives.

### Listing POOL = YES

| Item | Value |
| ---- | ----: |
| Starting parcels | 400 |
| Confident NO removed | 68 |
| YES survivors | 118 |
| UNKNOWN survivors | 214 |
| Final survivors | **332** |
| Percentage reduction | **17.0%** |

### Listing POOL = NO

| Item | Value |
| ---- | ----: |
| Starting parcels | 400 |
| Confident YES removed | 118 |
| NO survivors | 68 |
| UNKNOWN survivors | 214 |
| Final survivors | **282** |
| Percentage reduction | **29.5%** |

Compare frozen 001 gate: listing YES 330→270 (−18.18%); listing NO 330→239 (−27.58%).

---

## E–G. Pool miss diagnostic (frozen OS v1, no detector edits)

Nine documented `no_pool_candidate` false negatives vs Stand **677**.

Native15 crops were reconstructed from the **001** tile grid (same integer tile extract as OS v1). **All ten `crop_wh` match frozen OS JSON.** Re-running frozen `select_pool` reproduces `no_pool_candidate` on all nine misses and `CONFIRMED` on 677.

The table below is **pipeline behaviour**, not colour-as-cause. `Max CLIP` is the highest CLIP-pool score among **all** FastSAM + water-seed proposals that reached CLIP on that crop (not only a visual ROI).

| Stand | Crop px | FastSAM n | Water seeds | Reached CLIP | Max CLIP pool | Rival | Discard of that mask | Final OS | Failure stage |
| ----- | ------: | --------: | ----------: | -----------: | ------------: | ----: | -------------------- | -------- | ------------- |
| **677** | 605×402 | 71 | 3 | 11 | **0.992** | 0.007 | kept | CONFIRMED | FastSAM isolated pool; CLIP accepts |
| 339 | 286×311 | 32 | 0 | **0** | — | — | nothing ≥40 px in-parcel | UNKNOWN | **FastSAM proposal generation** |
| 408 | 318×569 | 38 | 1 | 4 | 0.105 | 0.373 | `clip_pool_lt_0.18` | UNKNOWN | FastSAM ran; CLIP sees roof/driveway |
| 1/437 | 251×378 | 27 | 0 | 1 | 0.006 | 0.603 | `clip_pool_lt_0.18` | UNKNOWN | FastSAM did not isolate pool |
| 1/520 | 537×316 | 45 | 1 | 3 | 0.040 | 0.596 | `clip_pool_lt_0.18` | UNKNOWN | FastSAM/water-seed ≠ CLIP-pool |
| 1/631 | 557×299 | 50 | 0 | 3 | 0.016 | 0.509 | `shadow_gate` | UNKNOWN | FastSAM did not isolate pool |
| 459 | 355×551 | 35 | 1 | 2 | 0.118 | 0.591 | `clip_pool_lt_0.18` | UNKNOWN | FastSAM/water-seed ≠ CLIP-pool |
| 462 | 581×303 | 62 | 0 | 7 | 0.191 | 0.274 | **`roof_gate`** | UNKNOWN | Best mask is roof-like |
| 543 | 427×612 | 84 | 2 | 13 | 0.176 | 0.626 | `clip_pool_lt_0.18` | UNKNOWN | Best mask is roof-like |
| 675 | 291×568 | 35 | 1 | 2 | 0.019 | 0.477 | `shadow_gate` | UNKNOWN | FastSAM/water-seed ≠ CLIP-pool |

Panels (raw crop, visual mark, FastSAM ∩ location, CLIP set, geometry survivors, final OS):

- `data/investigations/estate_property_inventory_v1/fastsam_miss/panels/<stand>_fastsam_miss_panel.jpg`
- Crops: `.../fastsam_miss/crops/<stand>_native15.jpg`
- Per-stand traces: `.../fastsam_miss/<stand>.json`

On 677, FastSAM mask 1 scores CLIP pool **0.988** (water 0.79, 27 m², parcel_frac 1.0) and the water-seed scores **0.992**. Frozen OS CLIP 0.99 is reproduced.

On the nine misses, FastSAM **does run** (27–84 masks). The masks that survive early area/parcel filters are classified by CLIP as **roof or shadow**, not pool. Water-seed priors exist on **5/9** (408, 1/520, 459, 543, 675) with HSV water fraction 0.94–0.99, but those seeds are **irregular** (fail `water_shape`) so they still need CLIP ≥ 0.18 and score **0.004–0.039**.

**339** is the clean proposal miss: 29/32 FastSAM masks are &lt; 40 px after parcel clip; **zero** reach CLIP; **zero** water seeds.

---

## H. Resolution / appearance hypotheses (measured)

Stand 677 pool ≈ **41 × 27 px** (6.18 × 3.99 m) at 0.15 m/px.

| Hypothesis | Supported? |
| ---------- | ---------- |
| Smaller pixel area than 677 | **Not the primary correlate.** Several misses have larger crops than 339; 543 crop is 427×612. 339 is smaller (286×311) and is the only total CLIP miss. |
| Narrower dimension | Possible for 339 (~8–17 px dark/light rectangle). Not measured as the driver for 408/543. |
| Irregular geometry | **Yes for water seeds** (compactness ~0.15–0.26 vs 677 0.75). They fail `water_shape`. |
| Pool touching patio/building | Common in this estate; 677 also sits in an L-nook and still scores 0.99. Not sufficient. |
| Shadow | Contributes on 1/631 and 675 (`shadow_gate` on the best CLIP mask). Not all nine. |
| Vegetation | One 408 FastSAM mask discarded `vegetation_not_water`. Not the majority. |
| Low local contrast | Not supported as a global correlate (auto gray-std gate did not flag the set). |
| FastSAM fragmentation | **Yes.** Most FastSAM masks are &lt;40 px after parcel clip (e.g. 339: 29/32; 543: 53/84). |
| Crop scale / context | 339/1/437/675 crops are smaller than 677. FastSAM `imgsz=512` resizes the whole crop; a ~17 px object is a weak proposal. |
| Colour as ranking cause | **Not used in ranking.** Colour is only a water-seed **proposal prior**. CLIP still has to accept the blob. On 677 it does (0.99); on miss water-seeds it does not (≤0.039). |

---

## J. Why PIE detects 677 and returns `no_pool_candidate` on these erven

677 is detected because **FastSAM (and the water-seed prior) isolate a compact in-parcel pool mask** that CLIP scores as a backyard pool at **0.99**, well above the 0.40 keep rule.

The nine misses reproduce `no_pool_candidate` on the **same native15 crops OS v1 used**. FastSAM is not “off”; it proposes dozens of regions. Those regions are not CLIP-pool objects. The bottleneck is therefore:

| Stage | Share of the nine |
| ----- | ----------------: |
| FastSAM never produces a CLIP-eligible in-parcel mask (**339**) | 1/9 |
| FastSAM/water-seed produce a mask, CLIP/geometry reject it as roof/shadow | **8/9** |
| CLIP pool on the *best* miss proposal | **max 0.191** (462, then `roof_gate`) vs **0.992** on 677 |

Primary attribution: **FastSAM proposal isolation at imgsz=512**, with CLIP and the irregularity gate as the immediate rejectors of whatever *did* get proposed. Parcel masking and 18 m crop padding are active but 677 uses the same path. Imagery is native CoJ 0.15 m/px (not Google/Bing). Combination, not a single colour bug.

---

## K. One next experiment (**do not implement here**)

**`fastsam_imgsz_proposal_ab`**

- Frozen baseline: OS v1, FastSAM-s, `imgsz=512`, `retina_masks=True`, CPU, native15.
- Single knob: FastSAM `imgsz` 512 vs 768 and/or 1024 on the **same** native15 crops.
- Do **not** change CLIP thresholds, geometry gates, parcel frac, water_seed HSV, native15, ranking, or gate semantics.
- Success: recover materially more of the nine known FNs without materially increasing false YES on **570** (shadow/object), neighbour-pool **1/335, 1/379, 395, 547**, and confirmed NO **1/355**.
- If imgsz does not isolate compact pool masks, the follow-up (separate experiment, not combined) is water-seed morphology / compactness recovery.

Stop. Do not implement K in this PR.
