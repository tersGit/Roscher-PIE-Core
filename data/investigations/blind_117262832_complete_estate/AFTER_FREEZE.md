# After-freeze forensic analysis — listing 117262832

Freeze is unchanged. SHA256 still `32ecd4b526d4a299e143c869761664a9ed7a4b2d9ae65aba6ed300583a1dd10a`. Ranking was not recomputed.

## 1. Ground-truth identity

**HIGH CONFIDENCE: stand 338, SUMMERSET EXT.6, 14 Soetdoring Close.**

Not CONFIRMED, because published street text names a different cadastral stand.

### Evidence

Independent public sources after freeze:

| Source | What it says |
| --- | --- |
| Property24 `117262832` title + schema `streetAddress` | `1 Carlswald North Estate, 1 Soetdoring` |
| Private Property `T5502075` | same address, same 4 bed / 3.5 bath / 869 m² / 510 m² / 28 May 2026 copy |
| Property24 map coordinates | **lat -25.967137, lon 28.098919** |
| CoJ REGISTERED_STANDS | that pin falls **uniquely inside stand 338** (14 SOETDORING CLOSE, 869 m²). 9.3 m from centroid. 163 m from stand 344. 328 m from estate centroid (not a suburb-drop pin). |
| Native15 visual | 338: dark gable + elongated rectangular backyard pool, internal close near The Boulevard. Compatible with listing night aerials. |
| Stand 344 (literal “1 Soetdoring Close”) | 1060 m², inventory **NO**, Pool-Gated out of the 332. Native15: older terracotta house, **no pool**, eastern perimeter road. Does **not** match listing photos. |

Listing erf 869 m² equals GIS 338. That is **corroboration only**. It was not used as the identity rule.

Frozen Top 5 (654, 467, 405, 644, 456) were **not** used as truth. All five were already visually false.

Published “1 Soetdoring” is treated as a copied portal address error (P24 and Private Property share it). The map pin and visual reject 344.

## 2. True stand in the frozen ranking

Stand **338** is in `all_candidates.json` (inventory UNKNOWN, so it survived Pool Gate). It is **not** in Top 20.

| Field | Frozen value |
| --- | --- |
| True stand | **338** |
| Extension | SUMMERSET EXT.6 |
| Frozen rank | **122 / 332** |
| Total score | **0.5847** |
| Inventory pool | UNKNOWN |
| OS status | **REJECTED** |
| `shape_v2` | **null** (contrib 0.18 = 0.5-neutral) |
| Shape contribution | 0.18 |
| Pool-presence contribution | 0.07 (0.5-neutral) |
| Spatial | 0.11 (0.5-neutral; Hybrid omits pool–house) |
| Aerial | 0.0953 (similarity 0.7943) |
| Exterior | 0.0444 (similarity 0.7396) |
| GIS | 0.015 (0.5-neutral) |
| Stand-size contribution | **0.07** (perfect; listing 869 = GIS 869) |

Genuine non-neutral terms only: aerial + exterior + stand-size (sum 0.2097). Shape and pool-presence contributed nothing above default.

## 3. True stand vs frozen Top 5

| Component | 338 | Top-5 mean | vs Top 5 |
| --- | ---: | ---: | --- |
| Pool presence | 0.07 | 0.14 | **HURT** |
| Shape (`shape_v2` contrib) | 0.18 | 0.2845 | **HURT** |
| Spatial | 0.11 | 0.11 | neutral padding both sides |
| Aerial | 0.0953 | 0.0942 | neither helped nor hurt |
| Exterior | 0.0444 | 0.0431 | neither helped nor hurt |
| GIS | 0.015 | 0.015 | neutral padding |
| Stand size | 0.07 | 0.060 | **HELP** |

Pool geometry / candidate extraction: **HURT**. OS REJECTED a visible rectangular pool (`clip.pool=0.019`, `clip.roof=0.498`, note `rejected_as_road_shadow_or_roof`). No `shape_v2` entered Scoring v2.

Listing contour quality: **HURT the match path**. Official Hybrid FastSAM frame `039` did **not** lock onto the listing’s own glowing rectangular pool. The ranking fingerprint is a smaller background / neighbour object (see `listing_pool_contour_proof.png`). Distinctive Contour v2 independently shows the large pool mask appearing then being discarded; that diagnostic is not a ranking input.

Neutral padding: spatial + GIS are identical defaults. They did not create the Top-5 miss. Missing shape (0.36 weight) did.

## 4. Candidate-side geometry audit (stand 338)

Frozen OS v1, not improved:

| Question | Finding |
| --- | --- |
| Pool present on native15? | **YES** — elongated rectangle, backyard, light deck |
| Correctly detected as pool? | **NO** — CLIP roof 0.50 vs pool 0.019 |
| Correctly segmented? | A rejected in-parcel blob exists (69-pt, 49.7 m², aspect 1.49, labelled kidney_or_curved) sitting on the dark water/shadow against the house. It was **not accepted** into scoring |
| Associated with parcel? | In-parcel, not neighbour-stolen |
| Correctly shaped? | Not used. Rejected object is incomplete / roof-confused relative to the clear rectangle |
| Distorted / incomplete | Incomplete; dark water scored as roof |
| Neighbour contamination | Not the failure mode |
| Inventory | UNKNOWN (`os_rejected_weak_evidence_not_absence`) — survived Pool Gate |
| Missed entirely for ranking | **YES** — `shape_v2` null, pool-presence 0.5-neutral |

Proof (frozen system, not improved):

`data/investigations/blind_117262832_complete_estate/true_stand_338_geometry_proof.png`

## 5. Why each false Top-5 candidate won

All five beat 338 for the same principal frozen reason: **they had an accepted OS pool contour and therefore a real `shape_v2`**, plus **pool-presence 0.14**. Stand 338 had neither.

| False stand | Rank / score | Principal reason it beat 338 |
| --- | --- | --- |
| 654 | 1 / 0.7725 | `shape_v2=0.8744` vs null; OS CONFIRMED. Aerial almost identical to 338. Stand-size slightly worse. Generic high-solidity match to the official (wrong-object) listing contour |
| 467 | 2 / 0.7479 | `shape_v2=0.7776` vs null; OS CONFIRMED. Stand-size almost equal (0.0679 vs 0.07) |
| 405 | 3 / 0.7393 | `shape_v2=0.7623` vs null; OS CONFIRMED |
| 644 | 4 / 0.7388 | `shape_v2=0.7691` vs null; OS PROBABLE; small aerial CLIP edge (0.0983 vs 0.0953) |
| 456 | 5 / 0.7362 | `shape_v2=0.7687` vs null; OS CONFIRMED |

Aerial CLIP and exterior CLIP did **not** separate 338 from this Top 5. Stand-size favoured 338 and still lost. Neutral padding is shared. The miss is not a stand-size distortion.

## 6. Estate-boundary observation (diagnostic only)

Confirmed from GIS, **not** implemented:

- 654 = 4 Camels Foot Drive, western edge (`lon_norm≈0.11`)
- 644 = 15 Galpini Drive, western edge (`lon_norm≈0.11`)
- 467 / 405 / 456 are internal closes (Baobab, Wild Olive)
- True stand 338 is an **internal** Soetdoring Close parcel near The Boulevard junction, not the eastern perimeter parcel (that is 344)

Listing night aerials look internal. Some false Top-5 stands are perimeter. **Do not add an estate-boundary feature.** This observation does not explain 338’s rank 122.

## 7. Diagnostic counterfactuals (frozen values only)

From `after_freeze_counterfactuals.json`. No rerank written into freeze artefacts.

| Diagnostic | 338 result |
| --- | --- |
| Shape-only rank | **124 / 332** (after the 122 survivors that have `shape_v2`) |
| Rank excluding stand-size contribution | **183** (score 0.5147) — stand-size was helping 338 |
| Rank excluding 0.5-neutral padding | **124** (genuine sum 0.2097) |
| Rank using only non-neutral evidence | **124** |

Removing stand-size makes the miss **worse**. The missing shape term is the frozen-score hole.

## 8. Root causes (ranked)

1. **B. CANDIDATE_GEOMETRY_FAILURE** — visible 338 rectangle rejected as roof; no `shape_v2` in Scoring v2; this is why 338 is rank 122.
2. **A. LISTING_GEOMETRY_FAILURE** — official FastSAM `039` contour is not the listing’s own rectangular pool; ranking compared a wrong/neighbour object to OS pools.
3. **C. SHAPE_SIMILARITY_FAILURE** — consequence of A+B: false Top 5 are a generic accepted-pool cluster against that fingerprint; 338 never entered the comparison.
4. **G. POOL_PRESENCE_FAILURE** — 0.07 vs 0.14, same OS reject.
5. **D. WEIGHTING_FAILURE** — secondary: shape weight 0.36 makes a null contour fatal. Weights were not wrong relative to a correct contour that never existed.
6. **I. INVENTORY/DATA_FAILURE** — minor: 338 is UNKNOWN not YES despite a visible pool. UNKNOWN still survived the gate. Not the rank-122 mechanism.
7. Not E/F: aerial and exterior did not hurt 338 vs Top 5.
8. Not H: stand-size **helped** 338.
9. Not J: identity is HIGH CONFIDENCE.

## 9. One recommended next action

**Do not implement it here. Do not add an estate-boundary feature.**

Repair **candidate-side OS rejection of dark in-parcel rectangular water that CLIP scores as roof**, so a visible pool on the true stand can supply `shape_v2`.

That is what happened to stand 338: native15 shows the pool; frozen OS still emitted `REJECTED` / `shape_v2=null` / rank 122.

A correct listing official contour (the glowing rectangle on `039`, not the neighbour object) is also required before 338 could *win* a shape shortlist. The blocker that kept the true stand at rank 122 is the candidate reject. Listing wrong-object is the parallel defect that manufactured the false Top 5.

The Top-5 miss is **not** noise around a reasonably ranked true stand.
