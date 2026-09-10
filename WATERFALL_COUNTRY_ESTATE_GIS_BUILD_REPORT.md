# Waterfall Country Estate GIS Build — W1

## A. Repository and provenance audit
No pre-existing Waterfall Country Estate or Jukskei View GIS, imagery cache, mapping, inventory, or listing-derived artifact was found. This build used CoJ Property MapServer layer 8 and the existing corrected native15 `EstateTileIndex` / `AGSAerialClient` infrastructure only. No listing source, target identity, ranking, matching, or production scoring code was used or changed.

## B. Authoritative scope and inventory
Membership is an exact `TOWN_NAME_DESC` query for only the six CoJ names below. `EXT`, `EXT.`, and `EXTENSION` are normalized in the output while the CoJ source value is retained. All layer-8 `LAND_TYPE_NAME=Erven` records are retained and classification concerns are flags, not deletions.

| Extension | CoJ source township | Erven |
|---:|---|---:|
| 19 | JUKSKEI VIEW EXT.19 | 358 |
| 38 | JUKSKEI VIEW EXT.38 | 69 |
| 39 | JUKSKEI VIEW EXT.39 | 209 |
| 40 | JUKSKEI VIEW EXT.40 | 197 |
| 43 | JUKSKEI VIEW EXT.43 | 52 |
| 105 | JUKSKEI VIEW EXT.105 | 125 |
| **Total** | **six exact extensions only** | **1010** |

## C. Scope QA
Duplicate extension-plus-stand groups: 0. Missing stands: 0; missing geometry: 0; invalid centroids: 0. Tiny-area flags: 3; large-area flags: 16; non-residential/common-property flags: 37. Flags are retained for review.

## D. Native15 source acquisition
Profile: `native15` (`210 m` tiles at `1400px`, target `0.15 m/px`). Legacy caches are not reused or overwritten. Status: **COMPLETE**.

## E. Parcel-centred crops
All requested parcel-centred crops are `[900, 900]` pixels at an actual effective GSD of `0.15 m/px`; crop status counts are preserved in the manifest.

## F. Visual inventory
No detector or scoring run was started. Pool/visual-inventory statuses were not inferred, changed, or used to eliminate parcels.

## G. Listing-independent QC
Deterministic random sample size: 12. Ready panels: 12. Panels retain parcel crop, centroid, stand, township/extension, and area context.

## H. Freeze
Machine-readable freeze: `data\estates\waterfall_country_estate\manifest.w1.json`. GIS feature collection: `data\estates\waterfall_country_estate\waterfall_country_estate_w1.geojson`. SHA256 is recorded in the manifest.

## I. Source identifiers
The GeoJSON retains PIE property ID, CoJ object ID, SG ID, stand, source and normalized township, area, geometry, centroid, and GIS street fields.

## J. Duplicate controls
Duplicate extension-plus-stand keys are explicitly flagged and retained, preserving unambiguous source identifiers for review.

## K. Address provenance
Street address, number, and name are copied only from CoJ layer 8 fields; no listing address data was consulted.

## L. Area and geometry coverage
The source-layer area and full CoJ polygon geometry are frozen per record; anomalies are flagged rather than removed.

## M. Cache provenance
The manifest records AGS service/year, cache profile/version, tile status, crop status, requested and effective GSD, and principal SHA256 values.

## N. Readiness conditions
Readiness requires exact scope, complete GIS geometry/centroids, complete native15 crop coverage, and every deterministic QC panel available.

## O. Final readiness
**READY** — requires complete native15 tile/crop coverage and all 12 QC panels. No listing testing began.
