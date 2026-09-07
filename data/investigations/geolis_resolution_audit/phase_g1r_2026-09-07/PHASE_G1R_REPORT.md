# Phase G1R: Historical imagery recovery

## Verdict

**PARTIAL**

No complete five-control set of exact or high-confidence legacy detector input imagery was recovered. The historical detector reproduction is therefore **not authorized and was not executed**.

## Recovery result

The expected original cache directory is absent from every permitted PIE checkout:

```text
data/visual_index/carlswald_north_corrected_001/_imagery_cache_native15/
```

No original cache filename (`677_ags_aerial.jpg`, `420_ags_aerial.jpg`, `408_ags_aerial.jpg`, `365_ags_aerial.jpg`, or `491_ags_aerial.jpg`) was found. The path is gitignored, and a local Git object/history search found no tracked historical cache object.

Two tracked, provenance-supported partial candidates remain in place:

| Stand | Classification | Reason |
|---|---|---|
| 677 | High-confidence historical cache | `677_ags_native15_raw_crop.jpg` is a 605 x 402 native15 integer tile extract and is byte-identical to the tracked `677_native15.jpg` diagnostic crop. |
| 408 | High-confidence historical cache | `408_native15.jpg` is a 318 x 569 crop whose diagnostic metadata records `crop_matches_os_v1_wh=true` and the native15 tile identity. |

The original absent-cache bytes cannot be hash-compared, so neither partial candidate is claimed as an exact historical cache. Controls 420, 365, and 491 have no suitable detector input candidate.

Tracked A/B images for all five controls are 1076 x 616 composite comparison panels and cannot be used as detector input. Later Phase E images are 2000 x 2000 live AGS estate tiles, not the historical parcel crops; they are recorded as unsuitable and were not substituted.

## Scope preservation

- No imagery was fetched, regenerated, copied, moved, or overwritten.
- No detector/config/model was changed or invoked.
- No Phase F work was used.
- No ranking, inventory, frozen artifact, or candidate selection was changed.
- No G1 reproduction was rerun.

## Provenance

The current evidence lineage is `6c53661e15d1bda968318cbac7cc244ed7497789` (detector freeze) plus `d77d81c07f6b5ad784b8c07eba26f57e76b10377` (G1 evidence). The current checkout is at the G1 evidence commit before this G1R evidence is added.

Permitted locations searched:

1. `C:\Users\ters\copilot-worktrees\Roscher-PIE-Core\tersgit-fluffy-waffle`
2. `C:\Users\ters\Roscher-PIE-Core`
3. `C:\Users\ters\copilot-worktrees\Roscher-PIE-Core`, including the established PIE worktrees `tersgit-crispy-train` and `tersgit-fluffy-bassoon`
4. `C:\Users\ters\.copilot\workspaces`

The full machine-readable candidate paths, file sizes, SHA-256 values, decoded formats/dimensions, timestamps, known duplication, classifications, and provenance are in `candidate_catalog.json`.

## Next condition

Only a locally supplied complete set of all five original or otherwise high-confidence historical detector input crops can authorize the unchanged G1 reproduction. This recovery phase stops here.
