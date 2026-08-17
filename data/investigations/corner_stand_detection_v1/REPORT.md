# Corner Stand Detection v1

Separate contextual gate. Not a new blind test. Historical freeze for listing `117262832` is untouched (commit `4f24f3f`, SHA256 `32ecd4b526d4a299e143c869761664a9ed7a4b2d9ae65aba6ed300583a1dd10a`). Scoring v2 weights are unchanged.

Success is not “this listing moves up the ranking.” Success is independent listing-corner evidence, independent GIS corner classification, and safe removal of incompatible non-corner candidates without ground truth. UNKNOWN remains neutral.

## 1. GIS corner definition

A parcel is `PARCEL_CORNER = YES` only when it has **two meaningfully distinct road-facing sides** (heading separation ≥ 35°) associated with a **road intersection or a sharp same-road corner bend**.

Road-facing contact is sampled along each parcel edge. A sample counts only if it is:

* within 22 m of a road centreline,
* on the **outward** side of the parcel (winding-independent),
* heading-aligned with that road (≤ 32°).

Tiny vertex nicks and accidental buffer clips fail alignment and/or do not accumulate 8 m of frontage.

`NO` is a single meaningful frontage (including cul-de-sac and curved single-road frontage), no meaningful frontage when roads are clearly nearby, or two nearly collinear sides on one road without an intersection.

`UNKNOWN` when road data are missing, nearby topology is insufficient, a second frontage is only weakly present near an intersection, or two named roads are not clearly associated with an intersection.

Stand size is not used. Estate-boundary / open-land adjacency is not a second road.

### Curved roads / cul-de-sacs

A property on the outside or inside of a curved road is not a corner. A cul-de-sac frontage is not a corner. Consecutive road-facing edges that follow one road through a gentle heading change are clustered into a **single side**. Cul-de-sac bulbs (short consecutive facets) are not treated as intersections. Corner=YES requires two distinct sides plus an actual intersection or sharp corner bend.

## 2. Listing-side corner definition

`LISTING_CORNER` uses listing media and text only. Known stand identity is not an input.

* **YES:** explicit unambiguous phrases (`corner stand`, `corner property`, `corner erf`, `situated on the corner`, `dual road frontage`) and/or aerial/elevated frames with road-like evidence on two adjacent image borders.
* **NO:** only with **positive** non-corner evidence (explicit phrases such as `not a corner`, `mid-block`, `single road frontage`). One visible street in photographs is **not** NO.
* **UNKNOWN:** insufficient or contradictory evidence.

Visual YES is restricted to aerial / elevated / video viewpoints. Interiors and ground photos cannot produce listing YES by dark borders alone.

High-confidence listing YES is confidence ≥ 0.80. That is the primary v1 gate signal.

## 3. Files changed

| Path | Role |
| --- | --- |
| `backend/gis/estate_ags_matching/corner_geometry_v1.py` | Local projection, intersections, road-facing sides |
| `backend/gis/estate_ags_matching/parcel_corner_v1.py` | Parcel YES/NO/UNKNOWN classifier |
| `backend/gis/estate_ags_matching/listing_corner_evidence_v1.py` | Listing text + aerial visual evidence |
| `backend/gis/estate_ags_matching/listing_corner_gate_v1.py` | Corner Gate v1 after Pool Gate |
| `backend/gis/estate_ags_matching/corner_stand_diagnostics_v1.py` | Estate layer + GIS/listing proof panels |
| `scripts/run_corner_stand_detection_v1.py` | Estate run + retrospective diagnostic |
| `tests/test_corner_stand_detection_v1.py` | Synthetic GIS + listing + gate tests |
| `tests/test_hybrid_extraction_ranking_isolation.py` | Asserts `corner` is not a Scoring v2 weight |
| `data/gis/carlswald_north_roads_v1.json` | Cached CoJ Transportation layer 14 centrelines |
| `data/investigations/corner_stand_detection_v1/` | Counts, records, proofs, retrospective |

Algorithm modules contain no listing IDs, stand numbers, or the frozen false Top 5.

Pipeline: **listing acquisition → Pool Gate → Corner Gate → Hybrid / Scoring v2**. Pool Gate internals are unchanged. Historical `run_freeze` is not rewritten.

## 4. Tests

`tests/test_corner_stand_detection_v1.py`:

* clear 90° street corner → YES
* angled intersection → YES
* T-junction corner parcel → YES
* single-road internal parcel → NO
* curved single-road frontage → not YES
* cul-de-sac → not YES
* tiny road-buffer vertex contact → not YES
* irregular parcel bordering one road → not YES
* estate-boundary parcel with no second road → not YES
* missing road data → UNKNOWN
* listing text `corner stand` → YES
* aerial image with two-road evidence → YES
* listing with only one visible road → UNKNOWN, not NO
* Corner Gate: high listing YES removes parcel NO, keeps UNKNOWN
* listing UNKNOWN / weak listing NO are neutral
* Pool Gate then Corner Gate counts independently
* Scoring v2 weights frozen; `corner` is not a weight
* historical freeze SHA256 unchanged

## 5. Estate-wide YES / NO / UNKNOWN

From the original 400 Carlswald North complete (GIS 002) pass-1 parcels, CoJ GIS Road Centreline (43 features, 42 intersections):

| Class | Count |
| --- | ---: |
| YES | **64** |
| NO | **279** |
| UNKNOWN | **57** |

Layer: `data/investigations/corner_stand_detection_v1/proof_panels/estate_corner_layer.png`

## 6. Proof panels

Under `data/investigations/corner_stand_detection_v1/proof_panels/`:

* 12 YES parcels (boundary, roads, orange road-facing edges, cyan intersections, class + confidence)
* 12 NO parcels (single-road, internal, and cul-de-sac)
* 6 UNKNOWN
* 6 cul-de-sac
* 6 curved-road (single-road curve, not cul-de-sac type)
* estate-wide YES/NO/UNKNOWN layer
* listing-evidence panel (no true GIS parcel)

## 7. Listing `117262832` (retrospective, not a new blind)

Independently: **`LISTING_CORNER = YES`**, confidence **0.86**, high-confidence **true**.

| Field | Value |
| --- | --- |
| evidence source | aerial |
| frame | `117262832-003` (Hybrid viewpoint `aerial_near_nadir`) |
| aerial evidence | true |
| text evidence | none (no explicit corner phrase in fetched description) |
| visual reason | night aerial roads along front and side boundaries |
| identity used | no |

Frame `039` is also aerial but only one border scored as a road → not used as YES. Absence of a second road on that frame is not treated as NO.

Listing proof: `proof_panels/listing_corner_evidence.jpg` — listing photograph only, no GIS parcel overlay.

## 8. Pool Gate → Corner Gate

Listing pool status remains frozen **YES**. Listing corner YES is high-confidence, so Corner Gate removes confident parcel **NO**.

```
400 estate parcels
→ Pool Gate: 332
→ Corner Gate: 98
→ Scoring v2 ranking
```

332 − 98 = 234 confident non-corner parcels removed after Pool Gate. UNKNOWN parcel corners are retained and marked unresolved.

## 9. Frozen false Top 5 (GIS only; known-false status not used)

| Stand | PARCEL_CORNER | Would Corner Gate remove? |
| --- | --- | --- |
| 654 | NO (single frontage, Camels Foot Drive) | **yes** |
| 467 | NO (cul-de-sac, Baobab Close) | **yes** |
| 405 | NO (cul-de-sac, Baobab Close) | **yes** |
| 644 | UNKNOWN (two named roads, nearly parallel, weak intersection association) | **no** (retained) |
| 456 | NO (two sides, same close, no intersection/bend) | **yes** |

## 10. True property retained?

After-freeze identity (not used in classification): stand **338**.

GIS: **YES**, confidence 0.96, Soetdoring Close + Hardekool View, 86° sides, intersection association. **Retained** by Corner Gate.

Diagnostic passes this check. The algorithm was not tuned on 338.

## 11. False-positive / false-negative concerns

**Precision over recall is working as specified.**

* Listing visual is coarse on night aerials: dark neighbour strips can score as a third “road” border. Mitigation: only aerial/elevated viewpoints count; interiors cannot vote YES. Frame 003’s actual front road (bottom) scored 0.38 vs a 0.42 strip threshold, so the detector used top/left/right rather than bottom/right. Classification was still YES and is visually correct, but border scoring is not a surveyed kerb detector.
* Listing NO almost never fires in v1 (by design). A mid-block listing with only one street in photos stays UNKNOWN.
* GIS YES requires two distinct named/intersection-associated sides. Some dual-frontage but nearly parallel configurations stay UNKNOWN (including frozen Top-5 stand 644). That is a residual false-candidate leak, not a YES over-call.
* Missing or offset municipal centrelines → UNKNOWN, retained. Private estate roads absent from CoJ would also be UNKNOWN.
* Cul-de-sac bulbs and curved single frontages are classified NO, not YES.

## 12. Scoring v2 unchanged

Verified in code and tests:

* pool presence `0.14`
* shape `0.36`
* spatial `0.22`
* aerial `0.12`
* exterior `0.06`
* GIS `0.03`
* stand size `0.07`

Corner status is **not** a Scoring v2 weight. It is a separate gate.
