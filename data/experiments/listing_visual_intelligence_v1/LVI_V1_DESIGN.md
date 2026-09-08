# Listing Visual Intelligence v1 design

This is an experimental, pre-identification extraction stage. It consumes only
the two supplied Property24 listing pages, their ordinary listing text, and all
photo/video media exposed by those pages. It stops before GIS, candidate
matching, ranking, address recovery, or identity evidence.

## Architecture

`Property24 HTML -> media inventory -> deterministic multi-label frame analysis
-> observation table -> cross-frame relationship graph -> scene fingerprint`.

`scripts/lvi_v1.py` is reusable: listing IDs and URLs are inputs, scene labels
are non-exclusive, and every observation carries confidence plus provenance.
The current visual pass is intentionally conservative RGB/layout analysis. It
records unknowns instead of manufacturing roof ownership, geometry, solar, or
neighbour facts. A later vision model can replace the frame analyser without
changing the inventory, observation, relationship, or fingerprint contracts.

## Evidence boundaries

Listing text is stored separately from visual evidence. “Inverter”, “battery”,
or “backup power” never implies solar panels. Water colour is not used.
Visible structures are `TARGET_PROPERTY`, `NEIGHBOUR`, or
`UNKNOWN_STRUCTURE`; this pass defaults to the last value unless ownership is
defensible. Interior frames remain in the inventory and can be labelled
`INTERIOR_WITH_EXTERIOR_VIEW` by a future analyser.

## Blindness and procedural deviation

The extraction implementation contains no G9H references, human-review clues,
candidate data, GIS data, ranking outputs, or listing-specific visual rules.
Before extraction, the operator accidentally opened the locked file
`data/investigations/geolis_resolution_audit/phase_g9_2026-09-08/human_blind_review/PHASE_G9H_HUMAN_BLIND_REVIEW.md`
while locating the frozen source package. Its contents were not copied into
prompts, labels, code, extraction decisions, or generated outputs. The exact
access is recorded in `LVI_V1_FREEZE_MANIFEST.json`; the comparison is delayed
until after fingerprint freeze. Because the extractor is stateless and its
inputs/code are auditable, contamination of the extraction can be ruled out.
