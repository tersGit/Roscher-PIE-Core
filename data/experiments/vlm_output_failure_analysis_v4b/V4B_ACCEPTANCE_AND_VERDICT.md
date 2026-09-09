# V4B acceptance and verdict

## Neutral-control acceptance

Pass requires meaningful multi-sentence, image-dependent descriptions with multiple verifiable
facts. The layout control must describe at least some of the road/front, road-to-driveway
connection, pool beside/behind house, and neighbour placement.

**Result: FAIL.** The free-caption variation is fluent and multi-sentence but hallucinates an
abstract geometric scene for the layout. The best layout spatial response says only that a
house is left of a pool. It omits the road/front, driveway connection, pool adjacency/behind
relationship, and neighbour placement. The non-JSON feature prompt produces a single generic
sentence instead of the requested schema. Therefore there is no corrected neutral smoke-test
success to record; `corrected_smoke_result` is **NOT APPLICABLE--no accepted configuration
correction exists**.

## Forensic conclusion

Frozen single-frame records include raw `" Green"`, `" Green."`, and `" White"` responses
after up to 500 permitted new tokens. Frozen multi-frame records include a natural short
`" Unknown_not_visible."` and a repeated `unknown_not_visible_relationships` string that
continues to the output cap. The records and SHA-256 references are preserved intact in
`frozen_raw_forensic_references.json`.

These outputs arise in generation, before JSON extraction: v4's decoder receives only the
generated suffix, and V4B's identical suffix-removal/decode path preserves both natural-EOS
and cap-limited long responses. Parsing then correctly refuses non-JSON text, explaining zero
normalized observations without causing it. The evidence does not support premature global
termination: some v4 rows run to the max-token cap, while other rows end naturally at EOS.

## Taxonomy decision: C MIXED

1. **Configuration/prompt contribution:** The retained large, restrictive classification JSON
   prompts cue the tiny model toward label/status continuations (`Green`, `White`,
   `UNKNOWN_NOT_VISIBLE`) instead of visual prose.
2. **Model capability failure:** A corrected native interface, increased cap, minimum-token
   control, and simpler prompts cannot meet the neutral factual/spatial acceptance gate.
   Responses contain hallucinated counts, shapes, dimensions, and incomplete relations.
3. **Not a post-processing failure:** Raw output, input-token removal, and parsing evidence
   rule out extraction as the root source.

## Recommendation

Do **not** start a blind LVI v5 from this diagnostic. Although the classification prompt should
not be reused unchanged, materially improved corrected neutral performance was not established.
Before any separate non-PIE model-selection evaluation, use a stronger CPU-feasible candidate:
`HuggingFaceTB/SmolVLM2-2.2B-Instruct` in a deliberately provisioned CPU quantized runtime.
Run the same neutral acceptance gate first; do not run property inputs as part of that evaluation.

## Prohibitions affirmed

V4B did not access or rerun listings `117539389` or `117255083`, other blind listing media,
G9H, identity/address/erf material, GIS, candidates/rankings, Native15 candidate imagery,
ground truth, or production code. It starts no LVI v5 and modifies no frozen v4 artifact.
