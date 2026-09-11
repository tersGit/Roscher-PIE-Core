# Waterfall W5 FastSAM Geometry v1 native15 diagnostic

## Result

**STOPPED before the A=272 production diagnostic.** W1 input validation and the normal-queue dry run pass: A is 272/272, B is 365/365, normal is 637/637, and rescue is scheduled for zero candidates. Property 2033377 remains invalid and excluded: its stored vertex mean is approximately 217.84 m outside its polygon, with zero polygon/crop intersection and an empty clipped mask.

The authorized external FastSAM-s model was found at the path and SHA256 recorded in `MODEL_MANIFEST.json`; its one-candidate model-only probe yielded 121 900x900 masks. No model was copied, downloaded, or updated. Recovered native15 crops were consumed read-only, with no refetch, recrop, or rebuild.

## Stop condition

The repository's frozen object selector required to label FastSAM masks as pool/building initializes OpenCLIP, which attempted unauthenticated Hugging Face Hub access. OpenCLIP is not an authorized external model and outbound access is prohibited. Continuing would therefore violate the diagnostic constraints. No A or B candidate received pool detection/binding/quality, building binding/quality, usable-relation, multiple-water, Geometry v1, or Funnel v1.2 lane result.

`FAILURE.json` records separate exact stop enums for A and B. There are no QC panels or overlays because no valid diagnostic output exists, and frozen W5 evidence, ranks, Geometry v1, Funnel v1.3, thresholds, bindings, and production code were not altered.

## Recommendation

Do not select a geometry-derived candidate or alter the frozen W5 ranking from this run. The next valid diagnostic requires an explicitly authorized, local-only pool/building mask-labeling method with all required weights already present and hashed.
