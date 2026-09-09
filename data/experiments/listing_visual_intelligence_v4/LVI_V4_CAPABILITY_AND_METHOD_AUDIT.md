# LVI v4 caption-VLM capability and provenance gate

## Result: FAIL / STOP

No explicitly selected, locally usable caption-capable vision-language model was available to this run. LVI v4 therefore produced **no listing observations, media retrieval, frame selection, prompts, captions, normalization, scene relationships, fingerprints, panels, or blind observation freeze**. It did not substitute OWL-ViT, CLIP, generic scene labels, OCR, handcrafted visual rules, or another model.

## Required capability

The selected model must be supplied through `LVI_V4_VLM_MODEL_DIR`, point to a local Hugging Face-compatible model directory, include a vision configuration and a text configuration, declare a caption/generation architecture, and successfully pass image-to-text inference before any listing media is touched. This run was stopped before that inference stage because no selected directory was configured.

## Runtime provenance

| Field | Value |
|---|---|
| Python | 3.14.6 |
| Transformers | 5.14.1 |
| Torch | 2.13.0+cpu |
| Device | cpu |
| Deterministic settings | Not applicable: no VLM inference occurred |
| Input resize/crop | Not applicable: no VLM inference occurred |
| Prompt and output parsing | Not applicable: no VLM inference occurred |

## Available but rejected caches

The gate records every discovered cached model configuration in `LVI_V4_CAPABILITY_GATE.json`. CLIP is image/text similarity rather than caption generation; OWL-ViT is prompted object detection rather than a caption/relationship model. Neither is used, and their presence is not evidence that a caption VLM was available.

Standard Ollama/LM Studio model locations and loopback OpenAI-compatible endpoints are also recorded. This run found no configured selected VLM and no reachable local model-serving endpoint.

## Blindness and scope declaration

This gate did not read G9H substantive observations, identity/address/erf/stand, GIS, candidate sets, G9 Top5/Top20, rankings, ground truth, or any production/candidate/detector/Native15/PR27 code. It did not access Property24 listing media or video. A post-freeze G9H evaluation is prohibited because there is no v4 blind observation freeze to evaluate.
