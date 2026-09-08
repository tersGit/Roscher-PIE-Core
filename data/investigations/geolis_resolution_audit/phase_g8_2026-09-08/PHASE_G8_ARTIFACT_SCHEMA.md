# PHASE G8 artifact schema

Each parcel is stored as `parcels/<parcel_id>/manifest.json` plus `artifacts/`. Every named source artifact is copied and SHA-256 recorded:

| Required artifact | Purpose |
|---|---|
| `native15_raw_crop` | Original native15 crop |
| `parcel_mask` | GIS polygon raster |
| `candidate_mask_unclipped`, `candidate_mask_clipped` | Before/after parcel clipping |
| `building_mask`, `road_context` | Independent context evidence |
| `semantic_scores` | Raw semantic component outputs |
| `fastsam_object_candidates` | All object candidates, not only winner |
| `cross_frame_evidence` | Per-frame agreement/identity evidence |
| `contour_geometry` | Raw contours and derived geometry |
| `validator_component_scores` | Individual PR27 components |
| `pr27_decision_reasons` | Status and reason codes |
| `request_metadata` | Listing, request, profile, source, and timestamps |
| `imagery_hashes` | Source tile/crop content identifiers |

The manifest additionally holds all four result channels: `legacy_detector`, `current_detector`, `native15_raw`, and `native15_pr27_shadow`.
