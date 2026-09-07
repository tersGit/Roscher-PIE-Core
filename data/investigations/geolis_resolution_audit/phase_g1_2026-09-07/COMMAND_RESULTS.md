# Captured G1 command results

## Freeze verification

```text
git status --short --branch
## tersgit-phase-g1-legacy-detector

git rev-parse HEAD
6c53661e15d1bda968318cbac7cc244ed7497789

git merge-base --is-ancestor 6c53661e15d1bda968318cbac7cc244ed7497789 HEAD
freeze-ancestor-exit=0
```

`HEAD` equals the requested freeze, and the worktree was clean before G1 evidence was added.

## Required-input probe

```text
MISSING data\visual_index\carlswald_north_corrected_001\_imagery_cache_native15\677_ags_aerial.jpg
MISSING data\visual_index\carlswald_north_corrected_001\_imagery_cache_native15\420_ags_aerial.jpg
MISSING data\visual_index\carlswald_north_corrected_001\_imagery_cache_native15\408_ags_aerial.jpg
MISSING data\visual_index\carlswald_north_corrected_001\_imagery_cache_native15\365_ags_aerial.jpg
MISSING data\visual_index\carlswald_north_corrected_001\_imagery_cache_native15\491_ags_aerial.jpg
.gitignore:219:data/visual_index/ data/visual_index/carlswald_north_corrected_001/_imagery_cache_native15
```

The historical detector has no external model or weight. Its required historical imagery bytes are unavailable. No asset was fetched, regenerated, substituted, or recreated.

## Executed test

```text
python -m pytest tests/test_object_segmentation.py -q
......                                                                   [100%]
6 passed in 0.51s
```

This unit test validates supporting segmentation utilities only; it is not evidence that the legacy detector was reproduced.

## Runtime record

```text
Python 3.14.6
cv2=5.0.0
numpy=2.5.1
pydantic=2.13.4
```

The original stored G1-adjacent report records Python 3.12. The historical imagery absence is the blocking condition; no output comparison is claimed across runtime versions.
