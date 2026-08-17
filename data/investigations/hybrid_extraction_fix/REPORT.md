# Hybrid extraction fix — before/after report

Extraction only. Frozen blind rankings of `116978058` and `116889694` were **not** rerun.
Ranking weights, Scoring v2, Pool Gate, OS v1, native15, GIS inventory, and stand-size/aerial/spatial contributions are unchanged.

Proof panels: `data/investigations/hybrid_extraction_fix/{listing}/*_before_after.jpg`
Machine record: `data/investigations/hybrid_extraction_fix/latest.json`

## 1. Root cause

### `116978058`
Official contour `116978058-026` was `yoloe_sam2`. SAM2 **box** refinement convexified an irregular YOLOE mask (kinked pool + attached spa) into a high-solidity elongated rectangle (aspect 3.516, solidity 0.958, **0 major indents**). Distinctive geometry was lost at **mask refinement**, not at ranking.

### `116889694`
Pool Gate correctly said YES. Hybrid `n_scoring_ready = 0`.
- `002` aerial: FastSAM established presence, then SAM2/area gates discarded the mask (`presence_only`, `comp=None`). Aerial pools are often <1.5% of the frame (`OVERVIEW_MIN_AREA` 0.015).
- `026` elevated balcony: FastSAM ranked a **deck/turf** blob (`clip.deck` 0.62 > `clip.pool` 0.22) because ranking was `pool - 0.5*vegetation` and ignored deck.
- `027`/`028`: no YOLOE hit; FastSAM proposals were CLIP-rejected (turf/interior). These frames do not contain a usable pool planform.

## 2. Exact extraction changes

All in `hybrid_listing_pool_geometry_v1.py`. No ranking modules edited.

1. **Trace** every stage with a precise reason (`candidate below minimum area`, `wrong-object rejection`, `CLIP semantic rejection`, `viewpoint gate rejection`, `sam2_collapsed_major_indents`, …).
2. **Presence retention**: FastSAM/YOLOE masks that fail scoring-ready still keep mask, box, raw contour, detector, CLIP scores, eligibility reason. Not auto scoring-ready.
3. **FastSAM multi-candidate**: score all proposals with CLIP pool vs vegetation/deck/furniture; reject deck-dominant turf. Deck is extraction-only (CLIP object prompt includes coping; YOLOE does not reject on deck).
4. **FastSAM scoring-ready only for aerial/near-nadir**. Elevated/oblique FastSAM stays presence-only so balcony turf cannot become a planform.
5. **Aerial min area 0.002** (dominant overview remains 0.015).
6. **SAM2**: box + interior point prompts; reject refinements that collapse indents/solidity; keep YOLOE mask if SAM2 convexifies.
7. **Contour path**: `CHAIN_APPROX_NONE` → conservative simplify → 64-point resample. No convex hull of spa+pool. Secondary/spa stored as diagnostic metadata only.
8. **Frame selection**: independent per-frame extract; near-nadir outranks oblique; **extraction quality** (structure + CLIP + viewpoint) outranks source rank so an irregular YOLOE mask beats a convex SAM2 fill. Contours are never averaged.

## 3. Files changed

- `backend/gis/estate_ags_matching/hybrid_listing_pool_geometry_v1.py`
- `tests/test_hybrid_listing_pool_geometry_v1.py`
- `tests/test_hybrid_extraction_ranking_isolation.py`
- `scripts/run_hybrid_extraction_fix_proof.py`
- `data/investigations/hybrid_extraction_fix/` (panels + `latest.json` + this report)

Unchanged: `os_scoring_v2.py`, `listing_pool_gate_v1.py`, `object_segmentation.py`, `hybrid_geometry_ranking_test.py` (YOLOE-only scoring sources), GIS/inventory bytes.

## 4. Tests added

- Aerial small-pool area gate
- FastSAM deck/turf rejection vs YOLOE coping
- FastSAM scoring-ready is aerial-only
- L-shape indent survives 64-point normalize
- Kidney not collapsed (vs rectangle)
- Spa blob not hull-merged
- SAM2 convex fill rejected
- Presence evidence retains mask fields without scoring-ready
- Combine prefers valid aerial over oblique
- Ranking isolation: V2 weights, score formula, Pool Gate, GIS/inventory SHA, OS stands 677/612/408/420/570/370, no listing/GT hardcodes

## 5. Regression results

| Control | Result |
|---|---|
| Stand 677 | OS `CONFIRMED` pool unchanged |
| Stand 612 | Neighbour kidney still `REJECTED` / not YES |
| Stand 408 | Neighbour outside parcel still `UNKNOWN` / `no_pool_candidate` |
| Stand 420 | Kidney/irregular still `CONFIRMED`, convexity 0.64 |
| Stand 570 | Road/shadow still `REJECTED` |
| Stand 370 | Dark-teal still `REJECTED` → inventory UNKNOWN (not solved here) |
| Scoring v2 weights | Frozen `0.14/0.36/0.22/0.12/0.06/0.03/0.07` |
| Ranking adapter | FastSAM still cannot enter Scoring v2 |

## 6. Before/after proof

Layout: **SOURCE → OLD MASK → OLD CONTOUR → NEW MASK → NEW RAW CONTOUR → NEW 64-POINT CONTOUR**

### `116978058` (chosen `026`)

| | Before | After |
|---|---|---|
| scoring-ready | 3 frames; chosen `026` `yoloe_sam2` | 2 frames; chosen `026` `yoloe` |
| detector | YOLOE box → SAM2 (convex fill) | YOLOE-11s-seg; SAM2 rejected (`sam2_collapsed_major_indents`) |
| aspect | 3.516 | 3.995 |
| solidity | 0.958 | 0.777 |
| major indents | 0 | **2** |
| max indent | 0.073 | 0.526 |
| CLIP pool | 0.938 | 0.922 |
| geometry quality | (none) | 44.09 |
| frame selection | SAM2 IoU accepted | highest extraction quality among valid overviews; SAM2 convex fill discarded |
| spa | not recorded | `spa_present=true` (diagnostic only) |

`005` remains scoring-ready but is a more convex SAM2-points contour (solidity 1.0, 0 indents) and is **not** chosen.

### `116889694` (chosen `002`)

| | Before | After |
|---|---|---|
| scoring-ready | **0** | **1** (`002` aerial) |
| selected frame | none | `002` `aerial_near_nadir` FastSAM mask (SAM2 collapsed, original mask kept) |
| detector | presence_only / turf FastSAM | `fastsam_mask_kept_after_sam2_collapse` |
| aspect / solidity / indents | none | 3.579 / 0.851 / 1 |
| CLIP pool | none | 0.813 (deck 0.171) |
| `026` turf | `fastsam_fallback` scoring-ready false but dominant turf | **presence_only**, `viewpoint gate rejection: fastsam_not_aerial_planform` |
| `027`/`028` | `no_usable_geometry` | presence-only with CLIP reject reasons; no scoring contour |

## 7. `116978058`: **YES**

The new official contour keeps two major indents and solidity 0.777 instead of a 0-indent 0.96 rectangle. SAM2 box fill is the stage that previously destroyed the kinked planform; it is now rejected.

Remaining: an attached spa can still sit in the dominant outline when YOLOE emits one connected mask. It is recorded as spa metadata and is not a ranking weight.

## 8. `116889694`: **YES**

Hybrid now emits a scoring-ready contour of the **actual aerial pool** on `002`. Balcony turf on `026` is not scoring-ready. `027`/`028` correctly stay non-ready (no usable pool planform in those frames).

## 9. Ranking/scoring unchanged

- `V2_WEIGHTS_NO_BUILDING` identical
- `score_v2(..., missing="neutral")` identical
- Pool Gate behaviour identical
- GIS SHA `1bab3126…` and inventory SHA `3bc02c09…` identical
- OS v1 `select_pool` / stand JSON statuses identical
- Hybrid ranking adapter still accepts only `yoloe` / `yoloe_sam2` (`fastsam_fallback` blocked)
- No listing IDs, frame numbers, Carlswald geometry, or ground truth in the Hybrid module
- **No new ranking of `116978058` or `116889694`**

## 10. Remaining extraction weaknesses

- **Ranking adapter still ignores FastSAM scoring-ready geometry.** `116889694-002` is extraction-ready but would not enter Scoring v2 until a later, explicit ranking-adapter change.
- CLIP can still assign a high pool score to bright terrace turf; the aerial-only FastSAM scoring-ready gate is what stops `026`, not CLIP alone.
- `027`/`028` have no legitimate pool planform; Hybrid returns UNKNOWN geometry rather than inventing a contour.
- Attached spa vs main pool is not always split when the detector emits one blob.
- Scoring v2’s 0.08 indent threshold is unchanged, so mild kinks can still report `n_major_indents=0` even when the 64-point outline is visually non-rectangular.
- Stand 370 dark-teal remains a known OS-side miss (not a Hybrid listing-photo path).
