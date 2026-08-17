# Estate Property Inventory v1 — Carlswald North

Experimental cached intelligence layer on frozen native15 + Object Segmentation v1.
Production ranking, Scoring v2 weights, Hybrid Pool Geometry, viewpoint gates,
FastSAM configuration, and OS v1 behaviour are unchanged. Colour is not used.
No scoring was changed from these results.

## A. Implementation summary

A versioned per-estate JSONL inventory stores relatively static parcel attributes
so new listing investigations do not rescan the whole estate. v1 attribute:
**pool status** `YES | NO | UNKNOWN`.

- Reuses frozen OS v1 JSON (FastSAM is not invoked unless a native15 crop changed).
- YES = OS CONFIRMED/PROBABLE in-parcel pool, excluding `partially_outside_parcel`.
- NO = `no_pool_candidate` after adequate building segmentation only.
- UNKNOWN = everything else, including all OS REJECTED rows (dark-teal misses
  such as Stand 370 must not become NO).
- Imagery fingerprint = native15 profile + intersecting tile IDs/hashes + crop
  hash + parcel geometry hash. Unchanged imagery + algorithm version → reuse.
- History is append-only (`history.jsonl`); `current.jsonl` is the latest state.
- Listing Pool Gate v1 filters the candidate universe **before** detailed ranking.
  It is not wired into production ranking.

## B. Files changed

New only (frozen modules untouched):

- `backend/gis/estate_ags_matching/estate_property_inventory_v1.py`
- `backend/gis/estate_ags_matching/listing_pool_gate_v1.py`
- `scripts/run_estate_property_inventory_v1.py`
- `tests/test_estate_property_inventory_v1.py`
- `data/estate_inventory/carlswald_north_corrected_001/`
- `data/investigations/estate_property_inventory_v1/carlswald_north/`

## C. Schema

- schema_version: `estate_property_inventory_v1.1.0.0`
- algorithm_version: `estate_property_inventory_v1.1.0.0+object_segmentation_v1`
- format: deterministic sorted JSONL (`current.jsonl`) + append-only `history.jsonl` + `manifest.json`
- location: `data/estate_inventory/<estate_id>/`
- per-parcel fields: estate_id, parcel_id, stand_number, parcel_geometry_ref,
  imagery_profile, imagery_version, tile_ids/hashes, scan_timestamp, pool_status,
  pool_confidence, pool_count, pool_centroid, pool_area_m2, pool_bbox,
  normalized_pool_contour, geometry_fingerprint, segmentation_source,
  diagnostic_flags, unknown_reason, extensible_attributes (roof/driveway/solar/
  outbuildings/orientation reserved as null)

UNKNOWN is never written as NO.

## D. Carlswald North inventory counts

- estate_id: `carlswald_north_corrected_001`
- parcel count (unique erven after GIS pass 1): **330**
- GIS pass-1 rows before property_id collapse: 337
- imagery coverage: frozen OS v1 native15 fingerprints **330/330**; live crops on disk **0**; live tiles on disk **0**
- YES: **91** (27.58%)
- NO: **60** (18.18%)
- UNKNOWN: **179** (54.24%)
- first-scan runtime: **0.12 s**
- parcels reused vs newly processed (first scan): reused **0**, newly processed **330**, FastSAM runs **0**

## E. Cache / reuse statistics

- second scan runtime: **0.091 s**
- parcels reused: **330**
- parcels rescanned: **0**
- FastSAM runs: **0**
- changed tiles: **0**
- unchanged tiles: **35**

Unchanged imagery + algorithm version does not rerun FastSAM.

## F. Pool-gate reduction statistics

Gate runs before detailed estate ranking. Production ranking is not applied.

### Test 1 — listing has pool (YES)

- starting parcel count: 330
- parcels removed as confident NO: 60
- YES survivors: 91
- UNKNOWN survivors: 179
- total survivors: 270
- search-space reduction: **18.18%**

### Test 2 — listing has no pool (NO)

- starting parcel count: 330
- parcels removed as confident YES: 91
- NO survivors: 60
- UNKNOWN survivors: 179
- total survivors: 239
- search-space reduction: **27.58%**

Listing UNKNOWN applies no pool filter (330/330 survive). UNKNOWN rows survive both hard gates.

## G. Known limitations

- OS v1 recall is incomplete. REJECTED is treated as UNKNOWN, so many visually
  empty parcels (e.g. 447, 570, 612) are not confident NO. That is intentional.
- A dark pool that produces **no** OS candidate *and* has a well-segmented
  building could theoretically be NO. Stand 370 is REJECTED, so it stays UNKNOWN.
- 54% UNKNOWN caps listing-YES reduction at 18%. The gate is safe, not aggressive.
- Live native15 crops/tiles were absent here; bootstrap used frozen OS v1 JSON.
  When tiles change on disk, only intersecting parcels rescan.
- Gate is experimental and not wired into production ranking.
- Extensible attributes (roof, driveway, solar, outbuildings, orientation) are reserved, not computed.

## H. Test results

`python3 -m pytest tests/ -q` → **91 passed**.

Inventory tests cover: persistence, reload, unchanged-imagery reuse, changed-imagery
rescan, changed-tile intersecting rescan, YES/NO/UNKNOWN semantics, UNKNOWN survives
both gates, neighbour-outside-parcel is not YES, history retained after update,
frozen ranking artifacts/weights unchanged, no colour in this layer.

## I. Production ranking untouched

- `scripts/run_carlswald_north_corrected.py` is not imported by the gate and still
  uses frozen `pool_geom` 0.30 weights.
- Scoring v2 `V2_WEIGHTS_NO_BUILDING` unchanged (`pool_presence` 0.14, `shape_v2` 0.36).
- Frozen OS ranking artifact: `production_ranking_modified=false`, baseline_rank **17**,
  baseline_score **0.6659**.
- Object Segmentation v1, FastSAM, native15, Hybrid Pool Geometry, and viewpoint
  gates were not edited.

## Diagnostic stands (not used to retune)

- Stand 677: YES (OS CONFIRMED)
- Stand 612: UNKNOWN (OS REJECTED; neighbour kidney excluded — not YES)
- Stand 570: UNKNOWN (OS REJECTED)
- Stand 420: YES (OS CONFIRMED)
- Stand 585: YES (OS PROBABLE)
- Stand 408: UNKNOWN (no candidate + poor/fragmented building; neighbour pool not YES)
- Stand 365: YES (OS CONFIRMED)
- Stand 491: YES (OS CONFIRMED)
- Stand 447: UNKNOWN (OS REJECTED — not collapsed to NO)
- Stand 370: UNKNOWN (OS REJECTED dark-teal — not NO)

Neighbour-bleed OS rows `1/334`, `633`, `658`, `1105` are inventory UNKNOWN, not YES.
