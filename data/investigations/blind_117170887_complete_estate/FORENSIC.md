# PR #28 forensic — listing 117170887 blind Top-5 FAIL 0/5

PIE was not modified. Scores were not recomputed. Scoring v2 weights, Pool Gate, Corner Gate, and Pool Object Validation were not retuned. The official fingerprint was not replaced.

Machine-readable twin: `forensic.json`.
Identity: `ground_truth.json`.
Proof: `panels/forensic_listing_641_top5.jpg`.

## Freeze lock (untouched)

```
96a66c8b240d8cab317d861d94582f1ba0bec84531c876fba4aaf090b4e82aa3
```

On-disk `freeze.json` matches `freeze.sha256` and the PR #28 lock. Freeze commit `6c53661`. Ranked Top 5 remains 545 / 868 / 568 / 572 / 897.

Manual inspection result used only as the failure trigger: **FAIL — 0/5**. Rank was not used as identity.

---

## A. Independent ground-truth recovery

**HIGH CONFIDENCE: stand 641, SUMMERSET EXT.13, 9 Galpini Drive, GIS 1024.0 m².**

Published street and map pin are **withheld**. Identity is **not** inferred from the frozen ranking.

### Evidence (non-ranking)

| Source | What it says |
| --- | --- |
| Property24 `117170887` | Street withheld (“Contact agent”). Erf **1 024 m²**, floor 431 m², 4 bed / 3 bath, pool=yes. Agent Schalk Visser / LuxLiv. Listed 29 April 2026. |
| Private Property `T5472094` | Same copy. Street withheld. No street slug in the URL. |
| LuxLiv `#2492408` | Same copy and sizes. Embedded map is `carlswald+north+estate+midrand` (estate centroid), not a parcel pin. |
| CoJ GIS 002 | Exact **1024.0 m² is unique** among 400 erven: stand **641** only. Next-nearest are 1023 m² (349, 518) and 1025 m² (459, 523). Size is the candidate key, **not** the sole identity rule. |
| CoJ REGISTERED_STANDS | 641 = **9 GALPINI DRIVE**, SUMMERSET EXT.13, `property_id` 1601616. |
| CoJ AGS 2023 native15 of 641 | Modern **flat/grey roof with skylights**, rooftop-terrace massing, backyard **buried under mature canopy**, dual frontage onto a paved street (Venus Avenue) and Galpini (dirt/gravel + open field south). |
| Listing photos / copy | Earthy-tan flat-roof house, **glass-roofed atrium**, **private rooftop garden**, pool nested in dense trees, double garage with balcony above. Copy also has a separate upstairs **jacuzzi**. |
| Neighbours on the same AGS frame | West: gabled grey roof + a **clear small rectangular pool**. East: terracotta tile roof + a **clear rectangular pool**. Both rejected: they do not match the listing house or the tree-hidden pool. |

Frozen Top 5 were already manually false and were **not** used as truth.

Exact 1024 m² is corroboration after the unique cadastral match plus visual. It is not a unique-size-only identity (within 1 m² there are five parcels; only 641 is exact **and** visually compatible).

### Gate / rank of the true stand

| Step | Result |
| --- | --- |
| Correct stand number | **641** |
| In 400-parcel universe | **YES** |
| Frozen rank out of 400 | **never ranked** (removed before Scoring v2) |
| Pool Gate | **REMOVED** — inventory **NO** |
| Rank after Pool Gate | **not in the 332** |
| Corner Gate | **never reached**. Parcel label **UNKNOWN** (would have been **kept**) |
| Rank after Corner Gate | n/a |
| Final frozen rank | **absent from the 98** |

641 does not appear in `freeze.json` or `all_candidates.json`. CLIP was computed only on Corner Gate survivors, so aerial/exterior similarities were never stored.

---

## B. Trace of stand 641 through the frozen pipeline

1. **Present in the 400-parcel universe?** **YES.** SUMMERSET EXT.13, reused from frozen 001 inventory.

2. **AGS imagery valid and current enough?** **Valid 2023 CoJ aerial.** The house, roads, and canopy are clear. The **pool is not visible**: the backyard is under mature tree crowns. Listing 2026 photos show that same tree-nested pool, so this is occlusion, not a missing 2023 house.

3. **Was the actual pool detected?** **NO.** Frozen OS v1: `status=UNKNOWN`, notes `no_pool_candidate`, no CLIP pool/roof scores, `spatial.pool.present=false`. Building **CONFIRMED** (383.7 m², irregular).

4. **Was the correct pool object selected?** **NO object existed to select.**

5. **Survive Pool Gate?** **NO.** Inventory maps `os_status=UNKNOWN` + `no_pool_candidate` + adequate building segmentation → **`pool_status=NO`** (`no_in_parcel_candidate_after_ok_os`, confidence 0.6). Listing POOL=YES therefore drops confident parcel NO. 400 → 332; 641 is one of the 68 removed.

6. **Survive Corner Gate?** **Never reached.** Parcel corner = **UNKNOWN** (confidence 0.4, `dual_frontage_nearly_parallel_not_confirmed_corner`, roads Venus Avenue + Galpini Drive). High-confidence listing YES keeps YES and UNKNOWN. **If 641 had reached Corner Gate, it would have been kept.** Native15 shows it is visually a corner (paved street + Galpini).

7. **Pool Object Validation?** **Never reached.** Candidate POV ran only on the 98 copies.

8. **Scoring v2 components?** **Never computed.** Diagnostic-only padding *if* it had been kept as UNKNOWN, using frozen weights, not written into the freeze:

   | Component | Weight | What 641 would have received |
   | --- | ---: | --- |
   | pool_presence | 0.14 | **0.07** (0.5-neutral; no YES) |
   | shape_v2 | 0.36 | **0.18** (null contour) |
   | spatial_v2 | 0.22 | **0.11** (listing hybrid omits pool–house; same padding as Top 5) |
   | aerial | 0.12 | not computed (gated out) |
   | exterior | 0.06 | not computed |
   | gis | 0.03 | **0.015** (constant 0.5) |
   | stand_size | 0.07 | **0.07** (perfect; 1024 = 1024) |

9. **Largest ranking loss?** **Pool Gate.** The true stand never entered Scoring v2. A later hole would still exist: `shape_v2` null because OS found no pool under the canopy. That second hole did not get the chance to matter.

---

## C. Listing fingerprint `117170887-077`

**PARTIAL.** Do not replace it.

The official pick is YOLOE/SAM2 `pool_overview`, POV **CONFIRMED** (identity 0.853), reason `principal_pool_identity then cross-frame agreement then geometry then viewpoint; cluster_size=2`.

| Question | Finding |
| --- | --- |
| Is it the principal swimming pool? | **YES.** Elevated overview of the outdoor elongated/shallow-chevron pool in the lawn, surrounded by trees. Distinct from the upstairs wood-clad **jacuzzi** on frames 053/054 (those were not chosen as official). |
| Does the extracted geometry represent the visible pool? | **Approximately.** `listing_pool_contour_proof.png` traces the water/coping. Hybrid v1 `geometry_loss` = **GEOMETRY PRESERVED**. Distinctive Contour v2 (not a ranking input) = **PARTIALLY LOST**: 64-pt simplification turns smooth curves into an angular polygon (aspect 2.923, solidity 0.835, 1 major indent). |
| Viewpoint / spatial | **Oblique.** `pool_to_house_*` omitted (`pool_house_spatial_omitted_not_viewpoint_compatible`). That is why every ranked candidate has `spatial_v2=null`. |
| Other pool frames | 071/073/074/076 show the **same outdoor pool**. 055 is truncated by a patio umbrella. 053/054 are the jacuzzi. 057/067/069 are non-pool (wall / grass). Official 077 is the right *object*, not the best nadir planform. |

Fingerprint is not WRONG (it is not the jacuzzi, not a neighbour object). It is not fully GOOD (oblique, curves simplified, no pool–house vector). **PARTIAL.**

---

## D. Top-5 false-positive analysis

All five beat an empty field: the true stand was already gone. They share one systematic feature.

**Shared cause: OS-confirmed elongated/irregular pool → high `shape_v2` against the oblique 077 fingerprint, plus pool-presence 0.14.**

`spatial_v2` is **null on all 98 survivors** (listing not nadir). Aerial CLIP 0.64–0.73 and exterior CLIP 0.71–0.78 are near-ties. Corner is **mixed** (YES / UNKNOWN / UNKNOWN / YES / UNKNOWN) and is not the shared cause. Driveway/garage did not separate them.

| Stand | Why it ranked highly | Geometry | Orientation | Pool–house | Roof / layout | Corner | Driveway | Aerial | Artefacts |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **545** #1 0.7681 | **shape_v2 0.8763** dominant | elongated_rectangular, aspect 2.34, 38.8 m² | NW vector in OS; listing vector unused | unused (`spatial_v2` null) | grey/white roof, not the listing tan flat roof | YES — helped survive the gate, not the score | UNKNOWN | 0.7263, non-discriminative | POV CONFIRMED on a real pool that is simply the wrong house |
| **868** #2 0.7608 | **shape_v2 0.8785** (highest) | irregular, aspect 1.88, 24.7 m² | pool west of house | unused | dark grey roof; major road along the north | UNKNOWN (same GIS dual-frontage class as 641) | PROBABLE | 0.6397, slightly *worse* than 545 | Generic elongated blob vs 077 |
| **568** #3 0.7523 | **shape_v2 0.8055** | irregular, aspect 1.71, 53.6 m² | pool east of house | unused | kidney-labelled building | UNKNOWN (weak second frontage / curve) | present in OS | 0.7125 | Same elongated-contour cluster |
| **572** #4 0.7427 | **shape_v2 0.8188** | kidney_or_curved, aspect **3.02**, 33.9 m² | elongated backyard pool | unused | smaller building PROBABLE | YES | unknown | 0.6632 | Frozen OS PROBABLE, POV still CONFIRMED; aspect closest to listing 2.92 |
| **897** #5 0.7353 | **shape_v2 0.7738** | rectangular, aspect 1.81, 23.4 m² | compact rectangle | unused | large irregular roof 645 m² | UNKNOWN | present | 0.6736 | Weakest shape of the five; still a confirmed pool vs a missing true stand |

None of the five is the listing property (manual). None matches 641’s flat-roof + canopy backyard. The model was matching **pool planform-ish blobs**, not house layout, driveway, or true corner context.

---

## E. Corner Gate audit

Listing: **CORNER = YES, confidence 0.86**, source=`aerial`, high-confidence, reason `roads_visible_along_two_parcel_sides`. Frames cited: `035`, `051`, `057`. Gate action: drop confident parcel NO. 332 → 98.

**Is the listing genuinely a corner?** From the recovered parcel, **YES.** Stand 641 has two named roads (Venus Avenue + Galpini Drive). Native15 shows paved street wrapping the north/east and Galpini along the south. PIE’s parcel classifier did **not** promote that to YES (`dual_frontage_nearly_parallel_not_confirmed_corner`, confidence 0.4 → UNKNOWN).

**Listing evidence quality is mixed.** Distinctive Contour v2 (not ranking) shows **051 = indoor staircase** and **057 = interior curved wall**, yet freeze listing-corner still marked 051 `visual_yes=true` (elevated_exterior, 0.78) and included 057 in `frame_ids`. CLIP scene `aerial=1` on 035 is the only plausible overhead; 051/057 are contaminated inputs. The **label happened to be correct** for 641; the cited frames are not all aerial.

**Did Corner Gate help, stay neutral, or kill the true stand?**

**NEUTRAL for 641 — it never got there.** Pool Gate had already removed it. Counterfactual: UNKNOWN would have been **kept**. Corner Gate did **not** accidentally eliminate the correct property.

Corner Gate **did** shape the false Top 5: 234 confident parcel-NO stands were dropped, so the ranked field is YES+UNKNOWN pool parcels. That concentrated generic elongated-pool matches. It did not create the 641 miss.

---

## F. Proof panel

`data/investigations/blind_117170887_complete_estate/panels/forensic_listing_641_top5.jpg`

Row 1: listing official 077 contour proof + Distinctive Contour v2 on 077 + other outdoor-pool frame 071.
Row 2: CoJ AGS 2023 of **641** raw and with GIS boundary (yellow). No OS pool contour exists to draw. Building is CONFIRMED in frozen OS JSON; pool is absent.
Row 3: frozen Top-5 proof panels at the same diagnostic scale (existing freeze panels; OS cyan pool / red building / yellow erf already burned in).

Supporting crops: `forensic_crops/641_ags_aerial.jpg`, `forensic_crops/641_ags_boundary.jpg`.

---

## G. Final diagnosis

### Primary: **ESTATE POOL DETECTION**

OS v1 emitted `no_pool_candidate` on a backyard that 2023 AGS cannot see through canopy. Inventory then treated that as confident **NO**. Pool Gate, with listing POOL=YES, **deleted the true stand** before Corner Gate or Scoring v2.

Contributing, not primary:

- **IMAGERY / GIS** — 2023 canopy occlusion is why FastSAM saw nothing. The house is current; the pool is hidden, not absent.
- **POOL GEOMETRY** — the oblique 077 fingerprint is PARTIAL and manufactured a generic elongated-pool Top 5 once 641 was gone. It did not remove 641.

Not the miss: Corner Gate (would have kept 641), pool–house spatial (null for everyone), Scoring v2 weights (never applied to 641), listing official object (right pool, not jacuzzi).

### Highest-value technical change (do not implement here)

**Do not map canopy-occluded FastSAM `no_pool_candidate` to inventory NO.** Keep **UNKNOWN** (or add an explicit occlusion / low-visibility flag) so Pool Gate cannot drop the true stand when listing POOL=YES.

A follow-on is still required: recover a scoring-ready in-parcel pool under tree cover, or 641 will survive the gate with `shape_v2=null` and still miss Top 5. The change that explains this 0/5 is the Pool Gate kill.

Stop. Frozen ranking and freeze hash are unchanged.
