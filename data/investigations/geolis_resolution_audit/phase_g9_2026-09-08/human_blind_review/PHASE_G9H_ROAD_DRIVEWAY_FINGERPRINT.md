# Phase G9H road and driveway fingerprint

## First-class diagnostic fields

| Field | Meaning | G9 availability | Failure stage |
|---|---|---|---|
| `ROAD_CURVATURE_AT_FRONTAGE` | Straight, convex, concave, or compound road segment at frontage | Candidate road context retained; no bilateral extraction | A/B/C/D/E/G |
| `DRIVEWAY_ENTRY_POINT` | Position of driveway-road intersection along frontage | Listing driveway/garage scenes and candidate context retained; not structured | B/C/D/E/G |
| `DRIVEWAY_ENTRY_ANGLE` | Acute/orthogonal/obtuse entry angle to road tangent | Not extracted | B/C/D/E/G |
| `DRIVEWAY_CURVATURE` | Straight, single curve, S-curve, or compound approach | Not extracted | B/C/D/E/G |
| `GARAGE_ORIENTATION` | Garage facade/orientation relative to property and road | Scene class only; no geometric field | B/C/D/E/G |
| `GARAGE_TO_ROAD_VECTOR` | Direction and approximate distance from garage to frontage/entry | Not extracted | B/C/D/E/G |

## Blind finding

Road and driveway geometry produced obvious visual contradictions for some
of the ten inspected candidates, but G9 records driveway/garage only as
`PRESENT_UNCONFIRMED` scene evidence and candidate `road_context` as a
retained artifact. Neither side was transformed into the fields above, so
there was no spatial comparison or ranking penalty. This is not a claim
about the true property or an instruction to modify production.

The diagnostic unit should be the coupled frontage layout, not a generic
driveway-presence boolean: road curvature at the entry, entry location and
angle, driveway curve, and garage-to-road vector must agree in one
property-centred coordinate system. Unknown and occluded fields remain
unknown; no missing value may be treated as a match.
