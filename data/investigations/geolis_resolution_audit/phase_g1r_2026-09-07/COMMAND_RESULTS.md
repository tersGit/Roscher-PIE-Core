# G1R command record

## Provenance check

```text
HEAD before G1R evidence: d77d81c07f6b5ad784b8c07eba26f57e76b10377
freeze ancestor check (6c53661e15d1bda968318cbac7cc244ed7497789): exit 0
G1 evidence commit: d77d81c07f6b5ad784b8c07eba26f57e76b10377
```

## Searches performed

- Recursive filename and image metadata search under the four permitted roots.
- Exact original-cache filename search for all five `<stand>_ags_aerial.jpg` names.
- Repository object/history search for `data/visual_index`, `_imagery_cache_native15`, and all five original filenames.
- Git branch/HEAD/status and tracked/ignored-state probes for each established PIE checkout.

## Results

```text
Original cache directory: missing in current, main, PIE imagery-forensics, and imagery-pipeline-fixes worktrees.
Original five filenames: 0 matches.
Git object/history imagery-cache matches: 0.
```

The current worktree's `.gitignore` identifies `data/visual_index/` as ignored. The two partial input candidates and all applicable derived/unsuitable candidates are listed in `candidate_catalog.json`; their source files were left in place.
