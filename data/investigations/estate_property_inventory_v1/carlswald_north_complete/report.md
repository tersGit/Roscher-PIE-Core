# Complete Carlswald North inventory (EXT.3 + EXT.6 + EXT.13)

Dataset completion + diagnosis. Frozen OS v1 / FastSAM / native15 / Scoring v2 /
Hybrid Pool Geometry / viewpoint gates / production ranking / Listing Pool Gate
semantics are unchanged. Colour is not used in ranking.

Frozen 001 (`carlswald_north_corrected_001`) is intact for PR #15/#16.
Complete universe is `carlswald_north_corrected_002`.

## B. Complete GIS universe

| Extension | Source parcels | Included unique properties |
| --------- | -------------: | -------------------------: |
| EXT.3 | 78 | 70 |
| EXT.6 | 280 | 212 |
| EXT.13 | 136 | 118 |
| TOTAL | 494 | 400 |

## C. Inventory v1 (complete estate)

- total parcels: **400**
- reused from frozen 001: **330**
- newly processed: **70**
- rescanned: **70**
- FastSAM runs: **70**
- imagery tiles required/reused/downloaded: 8/0/8
- crops written/reused/failed: 70/0/0
- runtime: **95.453 s**
- FastSAM available: True

- YES: **118** (29.5%)
- NO: **68** (17.0%)
- UNKNOWN: **214** (53.5%)

## D. Complete-estate Pool Gate baseline

### Listing POOL = YES

- starting parcels: 400
- confident NO removed: 68
- YES survivors: 118
- UNKNOWN survivors: 214
- final survivors: 332
- percentage reduction: **17.0%**

### Listing POOL = NO

- starting parcels: 400
- confident YES removed: 118
- NO survivors: 68
- UNKNOWN survivors: 214
- final survivors: 282
- percentage reduction: **29.5%**

UNKNOWN always survives. Classification semantics unchanged from PR #15.

