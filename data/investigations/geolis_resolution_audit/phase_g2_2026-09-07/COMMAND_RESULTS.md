# Phase G2 command results

## Paired acquisition and detector execution

```text
python data\investigations\geolis_resolution_audit\phase_g2_2026-09-07\run_phase_g2.py
validity=CLEAN
```

The collector directly requested each control's identical EPSG:3857 450 m x
450 m extent from `AerialPhotography/2023/ImageServer` at 2000 x 2000
(0.225 m/px) and 3000 x 3000 (0.15 m/px). It cropped each direct response
to the identically computed padded parcel extent and passed the resulting
JPEG bytes plus identically rasterized GIS parcel mask to the frozen detector
twice. Request URLs, parameter maps, response SHA-256 values, dimensions,
GSD, detector inputs, and both result payloads are in `detector_results.json`.

## Validity and freeze checks

```text
pair_validity.json: clean=true for 677, 420, 408, 365, 491
FREEZE_BLOBS_UNCHANGED
FREEZE_DIFF_SCOPE_CHECK_COMPLETE
```

The source/detector blob set is recorded in `DETECTOR_FREEZE_MANIFEST.json`.
No path outside `data/investigations/geolis_resolution_audit/` differs from
the detector freeze `6c53661e15d1bda968318cbac7cc244ed7497789`.

## Estate shadow

Not run. The immutable historical record describes 337 GIS candidates and
330 unique crop filenames, not a 400-member universe. Generating a claimed
"all 400" shadow would require selecting or constructing a new universe,
which is prohibited. The two required shadow CSVs explicitly record this
unmeasured status.
