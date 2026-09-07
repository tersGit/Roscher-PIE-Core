# Phase G2: Controlled same-source resolution A/B

## Validity and detector-effect verdict

**Validity: CLEAN. Detector effect: geometry-sensitive, not status-changing on these five controls.**

Each valid pair uses a direct response from the same CoJ
`AerialPhotography/2023/ImageServer` with exactly the same EPSG:3857 450 m
square request extent, CRS, JPEG format, `RSP_BilinearInterpolation`,
`returnSquarePixels=false`, local padded-parcel crop algorithm, GIS mask
algorithm, and frozen-detector preprocessing. The only acquisition variable
is request size: legacy-sim 2000 px (`0.225 m/px`) versus native15 3000 px
(`0.15 m/px`). ImageServer's published pixel size is 0.15 m and it
dynamically resamples requested output.

Both runs of every unchanged detector input are identical. All five controls
remain `PRESENT`, with 64-point contours. Four retain an `irregular`
classification with small centroid/relative-area movement. Stand 365 changes
from `kidney_or_curved`, centroid `(0.6421, 0.3634)`, relative area `0.0027`
at 0.225 m/px to `irregular`, centroid `(0.4464, 0.5225)`, relative area
`0.0049` at 0.15 m/px. This is a material geometry-selection change, not an
improvement claim.

## Measured results

`PHASE_G2_CONTROL_AB.csv` is the concise result matrix. `detector_results.json`
contains every request URL and parameter map (no secrets), bbox, response
hash/size, decoded dimensions, GSD, detector input hash, crop record, and
complete two-run detector outputs. `pair_validity.json` documents no
contamination for every pair. `raw/` contains the unmodified ImageServer
responses and `derived/` contains unenhanced detector inputs, overlays, and
same-extent comparison panels.

No true 100% known-pool crop is provided: the frozen historical controls
preserve no manually verified pool polygon or bounding box, and detector
output was not used to invent one.

## G1R references

Recovered 677 and 408 imagery is reference-only. It did not feed either
primary pair. `reference_comparison.json` records those source hashes and
shows that their dimensions differ from both live detector crops, so each
comparison is **inconclusive**, not forced equal.

## Estate shadow

Not run. Although all five controls are clean and stable, the frozen
historical record contains 337 GIS candidates and 330 unique crops, whereas
the requested shadow scope is 400. There is no immutable 400-member universe
to run without selecting/constructing one. `PHASE_G2_ESTATE_SHADOW_AB.csv`
and `PHASE_G2_TRANSITIONS.csv` contain explicit `NOT_RUN` records rather than
fabricated transition data. No ranking occurred.

## Required answers

1. The detector freeze manifest records the detector, embedded thresholds, geometry, validation, scoring, ranking, gates, inventory, GIS, and frozen-result blobs.
2. The controls are exactly 677, 420, 408, 365, and 491.
3. A/B inputs are direct paired exports from the same 2023 CoJ ImageServer.
4. Pair validity is CLEAN: all declared invariant fields match and only size/GSD differs.
5. Every A/B detector input ran twice unchanged; all ten results are deterministic.
6. Raw source responses, direct detector inputs, overlays, and unenhanced panels are retained under this phase only.
7. G1R 677/408 references are isolated from primary pairs and inconclusive because crop realizations differ.
8. This does not reproduce historical bytes or claim equality with historical output.
9. No estate shadow was measured because an immutable all-400 universe is unavailable.
10. No transition matrix was measured; the CSV explicitly says why.
11. No listing was reranked.
12. No detector, model, configuration, threshold, scoring, ranking, shape logic, gate, candidate-selection, listing, or inventory source changed.
13. Before/after Git blob checks prove the frozen source surface is unchanged.
14. Recommendation: treat resolution as a material contour-selection variable, retain the exact same-source paired protocol, and do not promote it to estate-wide selection/ranking without an explicitly frozen estate universe and separately authorized detector-only shadow run.
