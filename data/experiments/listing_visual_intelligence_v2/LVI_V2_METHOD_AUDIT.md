# LVI v2 method audit

## Scope

This artifact captures the generic reusable visual observation workflow used to inspect the two still-blind Property24 listings: `117539389` and `117255083`.

## Exact component stack

- Model/components: deterministic RGB layout heuristics, retained LVI v1 photo inventory, provenance-aware frame registry, generic scene-class bundle, hand-written relationship graph, JSONL observation export, and CSV summaries.
- Purpose: inventory every still frame and video candidate in the listing corpus, classify broad scene labels, select the strongest stills for a generic observational pass, preserve confidence and provenance, and produce a frozen blind observation bundle before any G9H comparison.
- Resolution/crop: LVI v1 frame widths vary from 683px to 1623px, with heights from 500px to 1400px, and no per-frame crop or geometric normalization is assumed. The v2 pass keeps the original image evidence as the source-of-truth and does not perform model-specific cropping beyond generic metadata capture.
- Prompts/classes: the workflow uses generic scene classes only (`GARDEN`, `POOL`, `INTERIOR`, `ROOF_VISIBLE`, `HOUSE_EXTERIOR`, `AERIAL_VIEW`, `OTHER`), with no listing-specific prompts, no material colour seeds, no pool-water identity, no GIS prompts, and no G9H hints.
- Outputs: media inventory, video inventory, selected frames, frame-level observations, scene/ video relationships, feature evaluation, failure analysis, and freeze manifest.
- Current stack coverage: CLIP = no; scene classification = yes (generic labels only); segmentation = no; object detection = no; geometry = no; captioning = no; multimodal reasoning = no. This is intentionally a conservative visual documentation pipeline rather than a structured geometric/reasoning model.

## What the workflow can and cannot do

### Reliable

- inventory frame provenance and source URLs
- preserve blind listing media in a reusable corpus
- classify broad scene categories such as pool, garden, exterior, aerial, and interior
- preserve non-committal unknowns when evidence is weak
- maintain a frozen observation set before G9H comparison

### Not reliable

- roof pitch, roof colour, roof form, and material without direct geometric measurement
- pool geometry and pool-to-house relation beyond generic scene cues
- driveway, garage, road, and neighbour spatial relationships
- solar or backup-power attribution from text or generic visual matches
- detailed multi-view temporal reasoning when the video corpus is absent

## Video acceptance test

The workflow explicitly tests whether the retained corpus contains a materially new video stream that can be time-synchronized and represented through extracted keyframes. In this run, video availability is `NOT_RETAINED_IN_LVI_V1_CORPUS`, so the video acceptance test is `FAIL / NOT_VISIBLE`. Keyframe count is 0 and no motion continuity is available. This is recorded as an honest absence rather than a fabricated video interpretation.

## Interior-with-exterior evidence handling

Interior frames are retained and explicitly flagged as `INTERIOR` or `INTERIOR_WITH_EXTERIOR_VIEW` candidates. They are not discarded, but they are also not treated as ground-truth exterior geometry. The workflow requires a direct exterior view or a validated line-of-sight before assigning property geometry or neighbour relationship claims.

## Recommended next architecture

The next architecture should add a materially stronger still-image stack with: (1) CLIP or vision-language backbone for generic scene and object prompting, (2) segmentation model to isolate roof, pool, driveway, and boundary edges, (3) geometry pass for perspective-aware line estimation, (4) optional video keyframe extraction for original listing motion clips, and (5) a final multimodal reasoner that can compare multiple views while preserving `UNKNOWN` when no evidence is visible. This architecture should remain deliberately blind to rank, GIS, and identity data until after the observation freeze.
