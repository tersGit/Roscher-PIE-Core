# Phase G3: Freeze-compatible estate-scale A/B

## Verdict

**Estate validity: CLEAN.** Frozen candidate rows: 337; deduplicated runnable parcels: 330; valid pairs: 330. The direct paired protocol is identical to G2 except that it is applied estate-wide.

**Detection effect:** 46/330 (13.94%) change from `ABSENT` to `PRESENT` at
native15, while 2/330 (0.61%) change from `PRESENT` to `ABSENT`; 163/330
(49.39%) are `PRESENT` at both resolutions and 119/330 (36.06%) are
`ABSENT` at both. **Geometry effect:** among the 163 present-to-present
pairs, 64 are material, 99 minor, and zero stable under criteria fixed before
output inspection.

## Required answers

1. Universe: `PHASE_G3_UNIVERSE.csv` gives every frozen GIS row, filter, duplicate, and runnable reason.
2. Deduplication uses the historical safe-stand filename last-wins rule.
3. Each pair uses one identical 450 m EPSG:3857 extent at 2000 and 3000 pixels.
4. Service, JPEG, bilinear interpolation, CRS, crop and mask preprocessing are invariant; request hashes are in `request_source_manifest.csv`.
5. The exact frozen detector ran twice per valid image; repeat stability is in `PHASE_G3_DETECTOR_AB.csv`.
6. No detector score, semantic score, rejection reason, or candidate count is emitted by the frozen blob; null values are recorded rather than invented.
7. All nine PRESENT/ABSENT/UNKNOWN transitions are listed, including zero counts.
8. Materiality criteria were fixed before the run in `DETECTOR_FREEZE_MANIFEST_PRE.json`.
9. Stand 365 is classified by those fixed criteria in `PHASE_G3_GEOMETRY_CHANGES.csv`.
10. Source/overlay panels exist for all 48 state transitions and all 64 material geometry cases; review labels are neutral `AMBIGUOUS` without ground truth.
11. Material-case root cause is conservatively `other`: the paired frozen-detector contour changed, but the physical-object cause is not established without ground truth; no detector retuning occurred.
12. G2 controls 677, 420, and 408 remain in the estate output but are unweighted in interpretation.
13. No historical-byte equality is claimed for current live AGS.
14. Recommendation: retain this result as detector-only diagnostic evidence; do not rerank or alter frozen behavior without a separately authorized decision.
