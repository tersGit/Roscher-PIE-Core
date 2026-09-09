# V4B prompt and generation comparison

All eight calls use the same pinned checkpoint, native Idefics3 implementation, CPU FP32,
one rendered image placeholder, one bound RGB image, greedy decoding, and the controls in
`controls/`. Exact prompts, rendered text, preprocessing shapes, generated token IDs,
EOS status, durations, and process RSS before/after are in
`raw_neutral_generation_results.json`.

| Prompt | Generation | Result |
|---|---|---|
| Free detail caption | `max_new_tokens=192`, `min_new_tokens=48`, repetition penalty 1.05 | Long multi-sentence output, capped at 192 tokens; partially recognizes colored geometric content but hallucinates shapes and measurements. |
| Structured visual inspection | `max_new_tokens=192` | Natural EOS on the geometric control after a multi-sentence description; names several visible colors/shapes but omits or misstates facts. |
| Spatial relations | `max_new_tokens=192` | Natural EOS; produces some relative language, but the geometric relations are not grounded and the layout only identifies house/pool left-right. |
| `FEATURE | VALUE | EVIDENCE` | `max_new_tokens=192` | Natural EOS after a single sentence and does not follow the requested delimiter schema. |

The V4B free-caption variation intentionally tests the only material generation controls absent
from v4: minimum output length and a light repetition penalty. It proves that 500-token v4
generation was not being cut by output extraction: the same decode path preserves long output
when the model generates it. It is **not** a configuration correction because the long output
does not meet factual acceptance.
