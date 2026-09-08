# PHASE G8 — prospective native15 + PR27 blind shadow harness

## Scope

G8 is a forward-only, write-only evidence harness. It does not fetch imagery, select listings, invoke FastSAM, invoke a detector, rank production candidates, or call PR27. A future authorized runner supplies outputs that it has already produced for genuinely new listings; `prospective_native15_pr27_shadow.py` only freezes rankings and copies the resulting evidence into content-addressed parcel bundles.

## Isolation

The module has no imports from production ranking, detector, imagery, FastSAM, or PR27 code. It changes no default profile and never writes production inventory, ranking, cache, or listing output. `native15_pr27_shadow` is a separately named result beside `legacy_detector`, `current_detector`, and `native15_raw`; it cannot become a production decision by serialization accident.

## Execution sequence

1. Confirm an explicitly supplied listing is new and outside every G5/G6/G7 sample.
2. Freeze the candidate ranking with `freeze_candidate_rankings` before identity recovery.
3. Produce the frozen-profile evidence externally, then call `capture_parcel` once per processed parcel.
4. Freeze all parcel manifests and evaluate only those frozen outputs.

No G8 listing run is authorized by this commit.
