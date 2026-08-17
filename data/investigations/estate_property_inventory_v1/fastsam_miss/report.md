# FastSAM / OS v1 pool-miss diagnostic

Read-only of frozen OS v1. FastSAM configuration, native15, Scoring v2,
Hybrid Pool Geometry, ranking, and Listing Pool Gate semantics are unchanged.

Full A–K write-up: `data/investigations/estate_property_inventory_v1/complete_ext3_fastsam_miss/report.md`

Reference: Stand 677. Misses: 339, 408, 1/437, 1/520, 1/631, 459, 462, 543, 675.

All ten reconstructed native15 `crop_wh` match frozen OS JSON. Re-running
`select_pool` reproduces CONFIRMED on 677 and `no_pool_candidate` on all nine.

## Max CLIP among all proposals (measured)

| Stand | Crop | FastSAM n | Seeds | Max CLIP pool | Rival | Final |
| ----- | ---: | --------: | ----: | ------------: | ----: | ----- |
| 677 | 605×402 | 71 | 3 | **0.992** | 0.007 | CONFIRMED |
| 339 | 286×311 | 32 | 0 | — (nothing reached CLIP) | — | UNKNOWN |
| 408 | 318×569 | 38 | 1 | 0.105 | 0.373 | UNKNOWN |
| 1/437 | 251×378 | 27 | 0 | 0.006 | 0.603 | UNKNOWN |
| 1/520 | 537×316 | 45 | 1 | 0.040 | 0.596 | UNKNOWN |
| 1/631 | 557×299 | 50 | 0 | 0.016 | 0.509 | UNKNOWN |
| 459 | 355×551 | 35 | 1 | 0.118 | 0.591 | UNKNOWN |
| 462 | 581×303 | 62 | 0 | 0.191 | 0.274 | UNKNOWN (`roof_gate`) |
| 543 | 427×612 | 84 | 2 | 0.176 | 0.626 | UNKNOWN |
| 675 | 291×568 | 35 | 1 | 0.019 | 0.477 | UNKNOWN |

## K. Recommended next experiment (not implemented)

`fastsam_imgsz_proposal_ab`: FastSAM `imgsz` 512 vs 768/1024 on the same native15
crops. CLIP/geometry/parcel frozen. Success: recover the nine FNs without
raising false YES on 570, neighbour-pool 1/335 1/379 395 547, confirmed NO 1/355.

## Panels

- `panels/<stand>_fastsam_miss_panel.jpg`
- `crops/<stand>_native15.jpg`
