# Phase G1: Legacy detector reproduction

## Verdict

**PARTIALLY REPRODUCED**

The requested freeze is reproduced exactly at `6c53661e15d1bda968318cbac7cc244ed7497789`, and the legacy detector, configuration, historical control expectations, GIS universe, scoring/ranking files, gates, inventory, and frozen result artifacts were identified and hash-recorded. The legacy detector was not invoked because its required historical native15 crop bytes are absent.

Phase G2 A/B is **not authorized**. G1 cannot certify output equivalence until the immutable historical crop cache is supplied as an existing asset.

## Scope and invariants

- No detector, model, configuration, threshold, segmentation, validation, scoring, ranking, gate, candidate-selection, listing, inventory, GIS, or frozen artifact was changed.
- No listing was reranked.
- No ground truth was opened or used.
- Evidence created by this phase is confined to `data/investigations/geolis_resolution_audit/phase_g1_2026-09-07/`.

## Historical detector and invocation

The intended legacy detector is `backend.gis.estate_ags_matching.pool_geometry.extract_pool_geometry`, a deterministic OpenCV HSV/blob detector. Its configuration is embedded in `pool_geometry.py`; it has no external model or weight. The documented historical control invocation is:

```python
extract_pool_geometry(crop_path.read_bytes(), parcel_mask=parcel_mask)
```

The intended source is the cached `native15` parcel crop at:

```text
data/visual_index/carlswald_north_corrected_001/_imagery_cache_native15/<stand>_ags_aerial.jpg
```

The required controls are `677`, `420`, `408`, `365`, and `491`. Their stored legacy outputs are preserved in the pre-existing Object Segmentation v1 JSON records as `old_extractor`; the complete machine-readable record is in `reproduction_comparison.json`.

## Reproduction result

All five historical crop paths are missing. `data/visual_index/` is gitignored, and neither its native15 crop cache nor the related cached model directory is available in this worktree. The correct action under the supplied protocol is to stop rather than regenerate crops from GIS/tile logic, fetch imagery, substitute an image, or use later/native15 Phase F work.

Consequently:

| Item | Result |
|---|---|
| Five-control unchanged-detector run | Not run: required historical bytes unavailable |
| Per-field comparison | Not possible; stored fields are retained without invented output |
| Contour, area, and geometry comparison | Not possible; those fields are not retained in the stored `old_extractor` baseline |
| Detector-only Carlswald inventory run | Not run: its historical crops are unavailable and the runner can recreate/acquire inputs |
| Exact matches/differences | Not assessable |
| Nondeterminism | Not assessable |
| Diagnostic panels | Not produced; no invocation occurred |

Stored legacy classifications for the five controls all have `old_pool_present=true`; their shape, aspect, rectangularity, compactness, centroid, and pool-to-house distance are recorded in `reproduction_comparison.json`. The stored baseline does not expose separate status, score/confidence, contour-point, area, or geometry fields, so none is inferred.

## Immutable record

`FREEZE_MANIFEST.json` contains the exact Git blob hashes for:

- legacy detector and embedded configuration;
- scoring and ranking;
- gates;
- inventory;
- GIS universe;
- relevant frozen result artifacts;
- historical runner and stored control/estate summaries.

`COMMAND_RESULTS.md` contains the freeze/ancestry proof, missing-input probe, runtime record, and executed test output.

## Constraint

The original report records a 330-crop native15 estate run and a 199/330 old-blob-positive count, but this worktree contains no live native15 crops or tiles. Those stored observations are evidence of the prior run, not a new G1 reproduction. Reproduction may resume only with the original immutable historical crop cache available locally; Phase G2 remains blocked pending that result.
