# LVI v2 acceptance report

## Scope

The v2 workflow was executed on the still-blind Property24 listings `117539389` and `117255083`, using the retained LVI v1 media corpus and the generic observation protocol only. No stand, address, erf, GIS, G9 Top5/Top20, ranking, or candidate-matching logic was used.

## Frozen observation status

The observation bundle was frozen before any G9H comparison and remains unchanged. The frozen set contains generic, non-committal feature records for roof pitch/colour/material/geometry, pool geometry and pool-house relationship, driveway and garage geometry, road/frontage geometry, neighbour characteristics, solar vs backup power, and an explicit interior-with-exterior-evidence flag.

## G9H comparison

After the freeze, the locked blind-review record in `data/investigations/geolis_resolution_audit/phase_g9_2026-09-08/human_blind_review/PHASE_G9H_HUMAN_BLIND_REVIEW.md` and feature audit in `PHASE_G9H_VISUAL_FEATURE_AUDIT.csv` were checked. The summary confirms:

- all frozen Top-5 candidates were inspected blind, but no true stand was known
- most candidates were not visually close enough to justify their rankings
- raw listing media retained roof, pool/garden, and driveway/garage evidence, but not structured roof/neighbour/road fields
- the missing feature family was the neighbourhood layout: neighbouring-building fingerprint plus road/driveway/garage approach
- pool evidence was retained but insufficiently discriminative without relational context

## Acceptance result

FAIL / NOT_VISIBLE

This is a feature-extraction failure, not an identity or GIS result.

The v2 workflow is therefore considered a `FAIL` on the required property understanding task because the retained still-blind media did not permit a reliable, first-class extraction of:

- roof pitch
- roof colour
- roof material
- roof geometry
- pool geometry
- pool-to-house relation
- driveway geometry
- garage orientation
- road/frontage geometry
- neighbour characteristics and relative position

## Independently rediscovered vs missed G9H clues

### Independently rediscovered without G9H influence

- generic pool/garden scene retention from the still-blind listing corpus
- generic exterior and interior evidence retention
- multiple view provenance across still frames
- preserved indication that some interior frames may include exterior cues

### Missed or not structurally extracted

- the neighbour high-pitched green zinc/metal roof clue was not independently rediscovered in the generic v2 system and was not encoded as a structured neighbour feature
- roof colour/material/pitch remained unresolved
- pool contour and pool-house spatial relation remained unresolved
- driveway/road geometry and garage approach remained unresolved

### Failure reasons

1. Missing first-class representation: the retained media existed, but no dedicated roof/neighbour/road/garage fields existed in the frozen observation set.
2. Missing geometry: no direct perspective or contour extraction was performed on the retained frames.
3. Missing video: no complete original listing video was retained in the local corpus, so no temporal continuity or drone evidence was available.
4. No inference from candidate or parcel context: the workflow intentionally abstained from GIS, ranking, candidate matching, and score-based deduction.

## Video and interior impact

Video availability remained `NOT_RETAINED_IN_LVI_V1_CORPUS` for both listings. The workflow therefore issued a `FAIL / NOT_VISIBLE` result for video-driven geometric understanding and temporal continuity. Interior frames were preserved and flagged as `INTERIOR` or `INTERIOR_WITH_EXTERIOR_VIEW`, but they remained non-diagnostic without a validated exterior connection and direct geometric measurement.

## Capability conclusion

The current stack can inventory listing media, preserve provenance, and classify broad scene categories. It does not yet provide the detailed physical observation fidelity needed for a property-level exterior and neighbourhood fingerprint from Property24 stills alone. This is a valid diagnostic baseline, not a score or identity claim.

## Recommended next architecture

The next architecture should combine CLIP or a similar vision-language model for generic scene understanding with a segmentation/geometry pass that isolates roof, pool, boundaries, driveway, road, and neighbouring structure edges, then a multimodal reasoning stage that explicitly maintains `UNKNOWN` rather than forcing a claim. Video and drone input should be included only when the source footage is preserved and timestamped; otherwise the video acceptance test remains `NOT_VISIBLE`.
