# Pool Object Validation v1

Extraction / object-identity only. Historical freezes, OS v1 JSON, Scoring v2, Pool Gate, Corner Gate, GIS inventory, and ranking weights were not modified.

Machine-readable twin: `results.json`.
Panels: `panels/`.

## 1. Root cause addressed

**Candidate Stand 338.** Frozen OS v1 already stored a 69-point in-parcel contour (~49.7 m²). `select_pool` then applied a keep-stage CLIP veto (`pool >= 0.40`) and rewrote the note to `rejected_as_road_shadow_or_roof` because CLIP roof was 0.498. Scoring v2 therefore never saw the object (`shape_v2` null, pool-presence 0.5-neutral).

**Listing `117262832`.** FastSAM on aerial `039` kept a tiny top-border blob (`rel_area` 0.0027, centroid y ≈ 0.058). `combine_listing_frames` ranked aerial viewpoint above object identity, so that speck became the official fingerprint even though courtyard overviews `037`/`038` (aspect ~2.60, large interior objects) agreed with each other.

## 2. Validation architecture

New module `backend/gis/estate_ags_matching/pool_object_validation_v1.py`.

- Candidate path: `select_pool` proposes blobs, then `validate_candidate_pool_object` sets `CONFIRMED` / `REJECTED` / `UNKNOWN`. CLIP is evidence, not a keep-stage oracle.
- Listing path: every frame is annotated (`scoring_ready` still means usable geometry only). `select_principal_listing_pool` / `combine_listing_frames` pick the official contour from `principal_pool_candidate` clusters.
- Priority: **object identity → cross-frame agreement → geometry quality → viewpoint**. Aerial never wins merely because it is aerial when the segmented object is wrong.
- Material conflict → **UNKNOWN**.

Frozen OS JSON is re-evaluated diagnostically via `validate_os_payload` and is **not rewritten**.

## 3. True-parcel containment

OS native15 crops include ~18 m padding. `true_parcel_mask_from_geometry` rasterizes the **GIS ring** into padded-crop coordinates. Crop-filling masks (`parcel.mean() >= 0.80`) are treated as missing parcel, not in-parcel proof.

Live `select_pool` validates the **unclipped** FastSAM mask against that polygon so a neighbour kidney in the pad cannot become valid by clipping a 40% sliver. Frozen JSON only stores already-clipped contours; 612/408 protection on frozen artefacts is “not CONFIRMED”, while the live path uses unclipped containment.

## 4. Candidate signals

`semantic_pool_confidence`, `water_confidence`, `roof_confidence`, `road_shadow_confidence`, `parcel_containment`, `parcel_edge_risk`, `building_overlap`, `road_overlap`, `geometry_plausibility`, `area_plausibility`, `yard_context`, `neighbour_risk`, `final_pool_object_confidence`, `final_status`, `reason_codes`. Raw contour retained on UNKNOWN/REJECTED.

Roof CLIP is a strong reject only when it **agrees** with building overlap. High roof CLIP + negligible building overlap + strong parcel/geometry = conflict (UNKNOWN), which is the 338 vs 570 distinction.

## 5. Listing principal-pool selection

`principal_pool_candidate` is separate from `scoring_ready`. Tiny aerial border specks are not principal. Large overview pools cropped at the bottom/side of the frame are allowed. Spa/secondary water is diagnostic metadata only.

## 6. Cross-frame consistency

Candidates are clustered by aspect / solidity / indents / relative size. Incompatible contours are not averaged. The official pick is the strongest validated member of the best-supported principal-pool cluster. Viewpoint is last.

## 7. Files changed

- `backend/gis/estate_ags_matching/pool_object_validation_v1.py` (new)
- `backend/vision/object_segmentation.py` (`select_pool` + validation record)
- `backend/gis/estate_ags_matching/hybrid_listing_pool_geometry_v1.py` (per-frame validation + combine)
- `tests/test_pool_object_validation_v1.py` (new)
- `tests/test_hybrid_extraction_ranking_isolation.py` (isolation asserts)
- `scripts/run_pool_object_validation_v1.py` (new diagnostic runner)
- `data/investigations/pool_object_validation_v1/` (diagnostic only)

## 8. Tests

`tests/test_pool_object_validation_v1.py` plus existing Hybrid / isolation / OS / Corner Gate tests: **75 passed**.

Covers: weak CLIP + good parcel/yard; roof CLIP ± building overlap; road/shadow; neighbour in pad; boundary crossing; irregular kidney; dark/low-semantic → UNKNOWN; tiny aerial border vs large overview crop; two agreeing overviews vs aerial speck; spa vs principal; missing parcel; freeze hashes; frozen OS JSON bytes; ranking weights/gates.

## 9. Stand 338 OLD → NEW

| | |
| --- | --- |
| **OLD** | **REJECTED** (`rejected_as_road_shadow_or_roof`, CLIP pool 0.019 / roof 0.498) |
| **NEW** | **UNKNOWN** (`semantic_conflict_geometry_and_parcel_support`) |

Independent support: true-parcel containment, area ~49.7 m², compactness 0.631 / convexity 0.923 / rectangularity 0.622. CLIP roof is **not** treated as a veto because independent building overlap is not confirmed on the frozen artefact (roof extractor can swallow a previously rejected blob). Conflict → UNKNOWN, not forced CONFIRMED.

**Supported by multiple independent signals rather than a listing-specific exception?** **YES**

## 10. Candidate regressions (diagnostic re-eval of frozen JSON)

| Stand | Frozen OS | New v1 | Protection |
| --- | --- | --- | --- |
| 338 | REJECTED | **UNKNOWN** | no CLIP-only veto |
| 677 | CONFIRMED | **CONFIRMED** | genuine pool kept |
| 612 | REJECTED | **UNKNOWN** | neighbour not CONFIRMED |
| 408 | UNKNOWN | **UNKNOWN** | no in-parcel candidate |
| 420 | CONFIRMED | **CONFIRMED** | irregular/kidney preserved |
| 570 | REJECTED | **REJECTED** | road/shadow |
| 370 | REJECTED | **UNKNOWN** | dark-teal, not forced |

**Did 570 remain rejected and 612/408 remain protected from neighbour contamination?** **YES**

## 11. `116978058`

Official contour remains **`116978058-026`** (irregular/kinked YOLOE/SAM2, aspect ≥ 3). Not replaced by a cleaner generic rectangle.

## 12. `116889694`

Still **zero scoring-ready** frames. FastSAM `026` balcony turf (`deck` 0.62 > pool) stays **REJECTED** `turf_or_deck`. Aerial `002` is not forced.

## 13. `117262832` OLD official → NEW official

| | |
| --- | --- |
| **OLD** | FastSAM `117262832-039` tiny top-border speck |
| **NEW** | YOLOE/SAM2 **`117262832-038`** courtyard pool (aspect 2.601, CLIP pool 0.691, large interior object) |

`003` right-edge speck and `039` top-border speck are not principal-pool candidates. `037`/`038` form the agreeing courtyard cluster.

**Does the official scoring contour now correspond to the actual principal pool?** **YES**

This is a future-run extraction change. The frozen PR #25 ranking still uses `039`.

## 14. Proof-panel paths

- `data/investigations/pool_object_validation_v1/panels/candidate_338.jpg`
- `data/investigations/pool_object_validation_v1/panels/candidate_612.jpg`
- `data/investigations/pool_object_validation_v1/panels/candidate_408.jpg`
- `data/investigations/pool_object_validation_v1/panels/candidate_570.jpg`
- `data/investigations/pool_object_validation_v1/panels/candidate_420.jpg`
- `data/investigations/pool_object_validation_v1/panels/listing_117262832_frames.jpg`
- `data/investigations/pool_object_validation_v1/panels/listing_117262832_old_vs_new.jpg`

Native15 JPEGs were not present in this environment; candidate panels render GIS true-parcel + OS contours (building/driveway overlays). Listing panels render stored Hybrid contours.

## 15. Ranking isolation

Unchanged: pool_presence **0.14**, shape **0.36**, spatial **0.22**, aerial **0.12**, exterior **0.06**, GIS **0.03**, stand size **0.07**. Shape similarity formula, Pool Gate, Corner Gate, GIS inventory SHA, `SEGMENTATION_VERSION = object_segmentation_v1` unchanged. `select_pool` no longer contains `CLIP pool >= 0.40` as a keep-stage veto.

## 16. Historical freeze hashes (unchanged)

| Listing | freeze.sha256 |
| --- | --- |
| 117262832 | `32ecd4b526d4a299e143c869761664a9ed7a4b2d9ae65aba6ed300583a1dd10a` |
| 116978058 | `8cf975a7a14326c520dbfcdba48a73d24df6e3605de1632d6174abab72d97628` |
| 116889694 | `69b8ea31f1ecdb77311937b2e3db829ef14ecea33b8534d2730a5ed57d331465` |
| 116778622 | `3eb8f54dc03f804cff519b65d7f452444ff91e7c4133a9ec7b9b638a3337875f` |
| 116273255 | `227a67c7100639300916d3a405da6030ff90b5d1dff54209c0160290c24ba500` |
| 116223230 | `be73a1615c5f87f678f9c4948c0d41b22d3f166aea3f10eb05b1ed6e98404126` |

## 17. Remaining known weaknesses

- Frozen OS contours are already `_in_parcel` clipped, so 612’s neighbour identity cannot be recovered from JSON alone; the live unclipped-mask path is the real neighbour gate.
- Independent roof overlap is unavailable on frozen REJECTED pools because building extraction may have swallowed the blob; 338 therefore stays UNKNOWN rather than CONFIRMED.
- Native15 crops were not in this environment, so water-texture confirmation for 338 was not computed from pixels.
- 370 dark-teal remains UNKNOWN (acceptable).
- 116889694 aerial `002` still has no scoring-ready contour; this PR does not invent one.
- Inventory mapping of OS REJECTED vs UNKNOWN is unchanged; UNKNOWN still does not enter `shape_v2`.

## Pass / fail

**PASS** on the stated criteria: 338 is not CLIP-only REJECTED; 570 stays REJECTED; 612/408 are not CONFIRMED; 420 stays CONFIRMED; `117262832` official pick is the courtyard cluster; `116978058` geometry is preserved; turf does not return; ranking/freezes are untouched.

No further blind listing will be run from this PR.
