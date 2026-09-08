# LVI v1 post-freeze human comparison

This comparison was written only after fingerprint-freeze commit `fb2ddc0`.
The two `SCENE_FINGERPRINT.json` files and all pre-comparison outputs are
unchanged.

## Independent discoveries

LVI independently retained all 93 ordinary Property24 photo frames with
per-frame hashes and provenance. It produced non-exclusive generic scene cues
for house/exterior, roof-visible, pool, garden, and interior frames, and it
kept interior frames in scope rather than discarding them. It also recorded
listing-text pool evidence separately from visual cues and created a
multi-frame corroboration edge for repeated pool cues. These are useful
architecture-level discoveries, but not a reliable physical fingerprint.

Against the locked G9H record, the extractor's only materially overlapping
physical clue was pool presence and the existence of exterior house/roof views.
It did not independently recover the more discriminative human observations.

## Missed human-observed clues

- Roof appearance/colour and pitch were not extracted as structured values.
- Pool contour/geometry and pool-to-house relation were not established.
- Driveway/garage approach and road/frontage geometry were not extracted.
- Distinctive neighbouring-building characteristics were not assigned to a
  neighbour entity.
- Interior frames with exterior views were retained but not fused into a
  defensible exterior observation.

The missed items are reported as extraction gaps, not added retrospectively to
the fingerprints. No candidate, stand, address, GIS, ranking, or identity
evidence is introduced here.

## Result

The frozen LVI v1 baseline answers the question **not yet**: complete
multi-view inventory and provenance are achievable, but the current generic
visual pass does not understand enough physical scene structure for a human to
eliminate incompatible aerial candidates. The next step is a generic
structure-aware visual analyser (roof/pool/driveway/road/neighbour relations)
that consumes the existing frame inventory and preserves the same blind,
contradiction-ready schema; it must be evaluated as a new experiment, not
retrofitted into these frozen fingerprints.

## Procedural note

Before extraction, the operator accidentally opened the locked G9H human-review
file while locating frozen sources. The freeze manifest records the exact path,
attests that its contents were not used as prompts, labels, code, extraction
decisions, or outputs, and records the restart before extraction. This document
is the first substantive comparison with that locked review.
