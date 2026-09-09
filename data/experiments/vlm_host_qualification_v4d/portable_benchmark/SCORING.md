# Scoring and raw-result schema

Score factual and spatial image dependence, not prose fluency. Ground truth is `neutral_controls_and_truth_rubric.json`, copied unchanged from V4C.

| Criterion group | Required result |
|---|---|
| Shapes A-D | Recognize the rectangle/circle/triangle/rectangle and their stated relations. |
| Schematic E-K | Recover road, road-to-driveway-to-house link, roof, pool, neighbour, tree, boundary, and the stated spatial relations. |
| Multi-view L | Keep first and second views distinct: pool only first, driveway only second, house/road shared. |
| Restraint M | Do not invent material features; use `UNKNOWN` where information is not visible. |

For every `(control, prompt)` write one raw JSON object with:

```json
{
  "control_id": "property_schematic",
  "prompt_id": "spatial_inspection",
  "image_paths": ["controls/unlabelled_property_schematic.png"],
  "raw_decoded_response": "unmodified model text",
  "inference_seconds": 0,
  "rss_before_bytes": 0,
  "rss_after_bytes": 0,
  "model": {"id": "exact model", "revision_or_digest": "immutable identity", "quantization": "exact format"},
  "runtime": {"name": "exact runtime", "version": "exact version", "device": "CPU/GPU", "command": "exact invocation"}
}
```

The acceptance threshold is intentionally unchanged: all E-L relationships must be correct, no material hallucination may appear, and image-dependent spatial behavior must materially exceed the V4C 256M baseline. Preserve results as a new file; never overwrite the two retained V4C raw-output files.
