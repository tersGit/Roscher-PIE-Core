# Waterfall W2 Qwen32B Blind Result Evidence Freeze

**Freeze status:** IMMUTABLE  
**Scope:** Externally generated RunPod evidence only  
**Ground truth:** NOT_STARTED

## Run configuration

| Field | Recorded value |
|---|---|
| Model | Qwen2.5-VL-32B-Instruct Q4_K_M |
| `image_min_tokens` | 1024 |
| Temperature | 0 |
| Candidate count | 10 |
| Per-inference inputs | Five frozen listing views, candidate native15 crop, and parcel overlay |
| Ordering | Deterministic descending `overall_visual_compatibility`; official PIE rank used only as a tie-break |
| External result SHA256 | `1c3bf26c647a99ab9b1353b62ff7510c27989f9b85058f29d16c35f96129a1d3` |
| RunPod relative path | `waterfall_w2_rl5480_vlm/qwen32b_blind_results/W2_VLM_BLIND_TOP10.json` |
| Original external JSON | Awaiting archival; not locally available |

This freeze does not reconstruct or fabricate the unavailable original external JSON candidate responses.

## Complete VLM ranking

| VLM rank | Stand | Ext | Overall visual compatibility | Official PIE rank | PIE score |
|---:|---:|---:|---:|---:|---:|
| 1 | 897 | 19 | .850 | 9 | .7734 |
| 2 | 972 | 19 | .750 | 1 | .7878 |
| 3 | 906 | 19 | .750 | 4 | .7763 |
| 4 | 3269 | 105 | .750 | 5 | .7751 |
| 5 | 1002 | 19 | .750 | 6 | .7749 |
| 6 | 1169 | 19 | .750 | 8 | .7739 |
| 7 | 1081 | 19 | .750 | 10 | .7727 |
| 8 | 838 | 19 | .700 | 2 | .7829 |
| 9 | 1018 | 19 | .700 | 3 | .7771 |
| 10 | 3323 | 105 | .700 | 7 | .7739 |

## Diagnostic constraints

- VLM #1 is stand 897, ext 19; official PIE #1 is stand 972, ext 19.
- This is a VLM diagnostic only. The official W2 ranking is unchanged.
- Scores are compressed, including multiple .750 and .700 ties.
- No blending or production changes are permitted.
