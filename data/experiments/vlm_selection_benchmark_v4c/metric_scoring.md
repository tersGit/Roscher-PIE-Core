# Metric scoring

## SmolVLM2-2.2B

| Control | Factual/spatial result | Hallucination / UNKNOWN | Classification |
|---|---|---|---|
| Coloured shapes | Recognized colours/shapes but called rectangle a square and omitted relations. | Appropriate UNKNOWN for absent architecture. | LIMITED |
| Property schematic | Caption reduced scene to house/tree; spatial prompt invented door and repeated circles to cap. Targeted prompt listed elements but no relations. | Material hallucination and no relationship reasoning. | FAIL |
| Multi-view | “The house is on the ground.” | Failed to distinguish views and did not use UNKNOWN. | FAIL |

## Qwen2.5-VL-3B

| Control | Factual/spatial result | Hallucination / UNKNOWN | Classification |
|---|---|---|---|
| Coloured shapes | Correctly identified all shapes and 2x2 layout. | Correctly stated absence of requested architectural elements. | PASS |
| Property schematic | Targeted output correctly found house/red roof, pool right, neighbour left, tree above, and boundary; it falsely denied visible road/driveway and described an extra roof. | No UNKNOWN where relationships were visually clear; material false negatives. | LIMITED |
| Multi-view | Collapsed two views into one and retained the pool despite its absence from the second. | Failed view-specific restraint/UNKNOWN. | FAIL |

Qwen is materially stronger than SmolVLM2 on single-image spatial recognition, but neither candidate meets the full E-L plus restraint threshold. Full raw outputs, timings, prompts, bindings, and per-call RSS are retained in `raw_outputs_*.json`.
