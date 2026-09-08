# Phase G9H neighbour fingerprint

## First-class diagnostic fields

| Field | Meaning | G9 availability | Failure stage |
|---|---|---|---|
| `NEIGHBOUR_SIDE` | Adjacent side relative to the subject property | Raw visual context, not structured | B/C/D/E/G |
| `NEIGHBOUR_ROOF_COLOUR` | Dominant neighbour roof colour; supporting negative contradiction only | Human-observed, not structured | B/C/D/E/F/G |
| `NEIGHBOUR_ROOF_MATERIAL` | Visible roof material class | Human-observed, not structured | B/C/D/E/G |
| `NEIGHBOUR_ROOF_PITCH` | Low, medium, or high pitched roof class | Human-observed, not structured | B/C/D/E/G |
| `NEIGHBOUR_BUILDING_SHAPE` | Coarse adjacent-building footprint/roof silhouette | Raw context, not structured | B/C/D/E/G |
| `NEIGHBOUR_POOL` | Adjacent pool presence and coarse relation | Raw aerial context, not structured | B/C/D/E/G |
| `NEIGHBOUR_SOLAR` | Directly visible adjacent solar panels only | Not asserted in G9 | A/B/C/D/E/G |
| `NEIGHBOUR_RELATIVE_POSITION` | Direction and approximate offset from subject building/pool | Raw context, not structured | B/C/D/E/G |

## Blind finding

The distinctive neighbouring high-pitched green zinc/metal roof was visible
to the human reviewer and was not captured or used by G9. It is a
neighbourhood-level negative contradiction, not an identity clue. Its
absence is most directly a B/C/D/E/G failure: no bilateral field was
extracted, represented, or spatially compared, and retained evidence was
ignored. It therefore could not influence frozen scoring (F).

Colour is restricted to a supporting negative contradiction: it may rule
against an otherwise plausible candidate when coupled with roof
material/pitch/position, but must not independently select a candidate.
Water colour is excluded entirely.

## Diagnostic comparison contract

For a future authorized diagnostic pass, normalize every field to
`OBSERVED`, `NOT_OBSERVED`, or `UNKNOWN`, retain the source frame/crop and
confidence, and compare only like-for-like subject-neighbour relations.
Unknowns must not be inferred from an inverter, generic exterior scene, or
unverified imagery. This document defines no score, threshold, or rank
change.
