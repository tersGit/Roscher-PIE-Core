# Phase G3 command results

## Universe and collector

```text
candidate_rows=337 runnable_last_wins=330 duplicates=7
python data\investigations\geolis_resolution_audit\phase_g3_2026-09-07\run_phase_g3.py
completed 330/330 valid paired detector-only runs
```

The collector issued exactly two direct exports per deduplicated frozen
candidate: same 450 m EPSG:3857 bbox at 2000 x 2000 and 3000 x 3000. It
applied the identical historical padded-parcel crop and GIS mask procedure,
then executed the frozen detector twice per input.

## Post-run checks

```text
PRE_POST_AND_WORKTREE_FROZEN_BLOBS_MATCH
NO_PREEXISTING_SOURCE_CHANGES
python -m pytest tests\test_object_segmentation.py -q
6 passed
```

All full records are in `request_source_manifest.csv`, `results.json`,
`PHASE_G3_DETECTOR_AB.csv`, and the pre/post detector freeze manifests.
