# Pool inventory NO/UNKNOWN safety — listing 117170887

Versioned overlay `estate_property_inventory_v1.1.1.0`. Frozen PR #28 ranking and SHA256 are untouched.

**POOL GATE SAFETY FIX: PASS**

## Counts

- **A.** parcels before Pool Gate: **400**
- **B.** inventory before correction: YES=118 NO=68 UNKNOWN=214
- **B.** inventory after correction: YES=118 NO=33 UNKNOWN=249
- **C.** Pool Gate survivors: **367**
- **D.** Stand 641 survives Pool Gate: **True** (inventory `UNKNOWN`)
- **E.** Corner Gate 641: survives=True parcel_corner=`UNKNOWN` reason=`unresolved_parcel_corner`
- **F.** scoring eligible: **True**
- **G.** rank: **75** of 111 scored Corner Gate survivors
- **H.** unranked reason: `ranked — not unranked`

## Stand 641 score (if eligible)

- score=`0.535` shape_v2=`None` spatial_v2=`None` OS=`UNKNOWN` POV=`UNKNOWN`
- high-conf OS pool: `False`
- neutral/missing: `['shape_v2_null_no_candidate_contour', 'pool_presence_neutral_no_high_conf_os_pool', 'spatial_v2_null']`

## Next bottleneck

**ESTATE_POOL_EXTRACTION_MISSING_CONTOUR**

This run does not solve the missing-contour / canopy-hidden pool on Stand 641.

## Constraints honoured

- Scoring v2 weights unchanged
- listing fingerprint 117170887-077 unchanged
- Hybrid / FastSAM adapter / Corner Gate / POV / colour rules unmodified
- PR #28 `freeze.json` / `freeze.sha256` / frozen Top 5 untouched
