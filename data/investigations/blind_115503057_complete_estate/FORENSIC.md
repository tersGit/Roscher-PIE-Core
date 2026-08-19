# PR #30 forensic — listing 115503057 post-freeze ground-truth recovery

PIE was not modified. Scores were not recomputed. Scoring v2 weights, Pool Gate, Corner Gate, and Pool Object Validation were not retuned. The official fingerprint was not replaced. The frozen ranking was not rewritten.

Machine-readable twin: `forensic.json`.
Identity: `ground_truth.json`.
Proof: `panels/forensic_listing_401_top5.jpg`.

## Freeze lock (untouched)

```
a6465002f681268391d4a87f3039532f47fd97e76d9a43217a8a45c841604ff6
```

On-disk `freeze.json` matches `freeze.sha256` and PR #30 freeze commit `5aa42ec266a0c515a75e9b7f4da623b0be84dc66`. Ranked Top 5 remains **868 / 624 / 648 / 545 / 401**.

Manual inspection was the recovery trigger only: 868/624/648/545 **RULED OUT**; 401 **INCONCLUSIVE / BASIC VISUAL MATCH**. Rank was not used as identity.

---

## A. Independent ground-truth recovery

**GROUND TRUTH = 401**

**MEDIUM CONFIDENCE: stand 401, SUMMERSET EXT.6, 6 Buffalo Thorn Drive, GIS 919.0 m².**

Published street and map pin are **withheld**. Identity is **not** inferred from the frozen ranking and is **not** assumed because 401 was the only surviving manual Top-5 possibility.

### Evidence (non-ranking)

| Source | What it says |
| --- | --- |
| Property24 `115503057` | Street withheld (“Contact agent”). Erf **897 m²**, floor 672 m², 5 bed / 5.5 bath, 2 garages, pool=yes. Agency LWP Properties / Kefilwe Double. Listed 30 January 2025. Copy: glass pivot door, downstairs guest suite, **koi pond**, covered patio. |
| Private Property `T4940696` | Same copy and sizes. Street withheld. URL has no street slug. Under offer at R7 500 000. |
| CoJ GIS 002 | Exact **897.0 m² is not unique**: three erven (539, 435, 1/867). Stand 401 is **919.0 m²** (22 m² / 2.5% off advertised). Size is corroboration only. |
| CoJ REGISTERED_STANDS | 401 = **6 BUFFALO THORN DRIVE**, SUMMERSET EXT.6, `property_id` 1490051. |
| 2023 CoJ AGS native15 of 401 | Dark-grey multi-plane roof (~430 m² footprint), elongated pool on the **north** side against the house/boundary, east driveway onto Buffalo Thorn, internal stand (one road). |
| South neighbour 400 | **8 Buffalo Thorn Drive**, terracotta/red-brown tiled roof with large solar arrays. Listing front frames 004/048 show a reddish-brown neighbour on the **left** when viewed from the street (looking west). Trees sit on the right / north-east, matching those frames. |
| Listing photos | Cubist charcoal house, beige cantilever over a double garage, rust-red accent, long rectangular side-yard lap pool with grey deck, internal courtyard and koi-pond water feature (frames 012/013, copy). |

Frozen Top 5 that were already manually false (868/624/648/545) were **not** used as truth.

### Exact 897 m² parcels — independently rejected

| Stand | Street | GIS | 2023 AGS / inventory | Frozen rank | Why not GT |
| --- | --- | ---: | --- | ---: | --- |
| **539** | 3 Buffalo Thorn Drive | 897.0 | Vacant grass lot / UNKNOWN | 135 | Cannot be a 672 m² house |
| **435** | 19 Huilboerboon Drive | 897.0 | Courtyard/C-shaped dark-grey roof; OS pool **REJECTED** (11.08 m²); ESRI imagery also shows **no swimming pool** | 123 | Best courtyard match, but the listing lap pool is not on this parcel; neighbour **434** holds the visible L-nook lap pool |
| **1/867** | 25 Coral Tree Drive | 897.0 | Light-grey roof + long solar array; inventory **NO** | *Pool Gate removed* | No confirmed pool |

435 is the serious alternative. It is not accepted: the listing’s principal outdoor object is a full swimming pool (submerged steps, cover roller, grey deck, frames 043/044/046), and that object is absent from 435 on both 2023 AGS and later ESRI World Imagery.

### Advertised 897 m² vs recovered GIS (validation only)

| | m² |
| --- | ---: |
| Listing advertised erf | **897** |
| GT stand 401 GIS | **919** |
| Delta | **+22 (2.5%)** |

This offset is within ordinary SG-diagram vs GIS rounding. It was **not** used to rerank or to pick 401. The three exact-897 parcels fail visually as above.

---

## B. Trace of stand 401 through the frozen pipeline

1. **Present in the 400-parcel universe?** **YES.** SUMMERSET EXT.6.

2. **AGS imagery valid?** **Valid 2023 CoJ aerial.** House, driveway, and north-side pool are visible.

3. **Was the actual pool detected?** **YES.** OS v1 `status=CONFIRMED`, 22.54 m², aspect 2.766, irregular, CLIP pool 0.98.

4. **Was the correct pool object selected?** **YES** — the in-parcel north-side pool, not a neighbour object.

5. **Survive Pool Gate?** **YES.** Inventory **YES**. Listing POOL=YES keeps YES and UNKNOWN. 400 → 367.

6. **Survive Corner Gate?** **YES.** Parcel corner **NO** (confidence 0.88, `single_road_frontage_not_corner`, Buffalo Thorn Drive only). Listing CORNER=UNKNOWN → gate retains all 367.

7. **Pool Object Validation?** **CONFIRMED.** Scoring-eligible.

8. **Scoring v2 components (frozen, not recomputed):**

   | Component | Weight | 401 received |
   | --- | ---: | ---: |
   | pool_presence | 0.14 | **0.14** (YES) |
   | shape_v2 | 0.36 | **0.2776** (shape 0.7712) |
   | spatial_v2 | 0.22 | **0.11** (null; hybrid omitted pool–house) |
   | aerial | 0.12 | **0.06** (null; no listing aerial → 0.5 pad) |
   | exterior | 0.06 | **0.0463** (CLIP 0.7724) |
   | gis | 0.03 | **0.015** (constant 0.5) |
   | stand_size | 0.07 | **0.0662** (919 vs 897) |
   | **total** | 1.00 | **0.7152** |

9. **Final frozen rank:** **5 of 367.**

---

## C. If Stand 401 is correct — what PIE matched, and why rank 5

**BLIND HIT — TOP 5 / RANK 5**

### What PIE matched correctly

- Listing POOL=YES and parcel inventory YES → 401 stayed in the 367.
- OS confirmed an elongated in-parcel pool; candidate POV CONFIRMED.
- Corner Gate did not drop an internal stand against listing CORNER=UNKNOWN.
- `shape_v2=0.7712` is a real geometric similarity to fingerprint 043, not a padded null.
- `stand_size` rewarded the near-897 GIS area.

### Why 401 only ranked fifth

The Top 5 scores occupy a **0.0113** band (0.7265–0.7152). Discrimination is almost entirely `shape_v2`.

401 `shape_v2=0.7712` vs 868 `0.8261` is a **0.0549** shape gap → **0.0198** on the 0.36 weight. That alone exceeds the 0.0113 total-score gap. 401 actually *wins* stand_size against 868 (958 m² is farther from 897) and is slightly better on exterior CLIP (0.7724 vs 0.7451). Shape of the wrong pools is what put 868/624/648/545 above it.

### Why 868 / 624 / 648 / 545 outranked it

All four are inventory YES, OS CONFIRMED elongated/irregular pools, `spatial_v2` null, aerial padded. They beat 401 on **oblique 043 shape_v2**, not on house identity.

| Stand | Rank / score | shape_v2 | Why it scored | Why it is not the house |
| --- | --- | ---: | --- | --- |
| **868** | #1 0.7265 | **0.8261** | Highest shape match to 043; irregular ~25 m² pool in a narrow backyard strip | Perimeter stand, curved/irregular pool, not the cubist charcoal house |
| **624** | #2 0.7200 | 0.7777 | Elongated 81 m² pool; GIS 886 m² is the *closest* Top-5 size to 897 | Different street / roof; pool far larger than the listing lap pool |
| **648** | #3 0.7184 | 0.7902 | Elongated 45 m² pool | Different massing; OS building only 138 m² |
| **545** | #4 0.7163 | 0.7685 | Elongated 39 m² pool; **highest exterior CLIP (0.8046)** | Same street (15 Buffalo Thorn, odd side), light/white roof, corner YES |

### Did missing `spatial_v2` materially suppress 401?

**No — not uniquely.** Hybrid v1 omitted pool–house terms (`pool_house_spatial_omitted_not_viewpoint_compatible`). Every ranked survivor, including 401 and the four outrankers, received the same **0.5 × 0.22 = 0.11** pad. Missing `spatial_v2` flattened the field; it did not single out 401. If spatial had been live, 401’s OS pool-to-house vector is **N / −90.4° / 12.69 m**, which is compatible with the listing side-yard pool, but that term was not in the frozen score.

Aerial CLIP was likewise padded at 0.5 for everyone (`no listing aerial`).

### Could any existing feature have distinguished 401 without adding new information?

**No existing Scoring v2 term would have promoted 401 to Top 1 without new information.**

- Exterior CLIP already existed and **preferred 545**.
- Stand size already existed and **preferred 624** (886 vs 897 closer than 919 vs 897).
- Corner is a gate, not a score; listing CORNER=UNKNOWN so 545’s parcel YES did not remove it and did not add points.
- Driveway orientation, roof courtyard, beige cantilever, and neighbour terracotta are **not** Scoring v2 features. Colour is unused.

The ranking loss is **oblique-fingerprint shape_v2** among many YES-pool parcels in a MODERATE-separation estate, with spatial and aerial both neutral.

---

## D. Listing fingerprint `115503057-043`

**PARTIAL.** Do not replace it.

Official pick: YOLOE/SAM2 `pool_overview`, POV **CONFIRMED** (identity 0.64).

| Question | Finding |
| --- | --- |
| Is it the principal swimming pool? | **YES.** Side-yard lap pool with submerged steps and cover roller. Distinct from the courtyard koi-pond water feature on 012/013. |
| Does the extracted geometry represent the visible pool? | **Approximately.** Hybrid `geometry_loss` = **PARTIALLY LOST** (spa/secondary not in dominant contour). Aspect 3.752, solidity 0.917, 1 major indent. Oblique, not nadir. |
| Viewpoint / spatial | **Oblique.** `pool_to_house_*` omitted. That is why every ranked candidate has `spatial_v2=null`. |
| Other pool frames | 044/046 show the same outdoor pool in the L of the house. 012/013 are courtyard water, not the official object. |

---

## E. Proof panel

`data/investigations/blind_115503057_complete_estate/panels/forensic_listing_401_top5.jpg`

Listing fingerprint 043 + contour / listing 043 raw / listing 004 front elevation; GT 401 parcel + OS pool/building/driveway; frozen Top 5 with the same overlays.

---

## F. Final classification

**BLIND HIT — TOP 5**

Blind rank: **5**.

**GROUND TRUTH = 401** (MEDIUM confidence).
