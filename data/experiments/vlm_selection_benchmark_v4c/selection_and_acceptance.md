# Selection and acceptance decision

**Decision: no model is recommended for a subsequent application phase.**

Qwen2.5-VL-3B is the stronger tested candidate: it correctly recovered five of seven principal property-schematic elements and their relationships in its targeted response, while SmolVLM2 did not. However, Qwen missed the clearly visible road-to-driveway-to-house connection and failed the two-image comparison. SmolVLM2 also hallucinated a door and repeated output until the token cap. These failures are disqualifying under the predefined neutral acceptance threshold.

Both checkpoints are content-pinned to exact Hugging Face revisions. `checkpoint_manifests.json` records SHA-256 hashes of every locally downloaded snapshot file. No unavailable runtime/model is represented as tested. The next infrastructure step is to provision a maintained quantized llama.cpp or Ollama-compatible runtime and repeat this exact neutral benchmark with MiniCPM-V 4 or Gemma 4 on a host with at least 24 GiB RAM; do not use application imagery until a neutral pass exists.

## Scope assurance

This directory was generated solely from four local synthetic PNG controls. The runner contains no input discovery and reads no repository media directories. No PIE, blind, property, identity, address, erf, GIS, candidate, ranking, native imagery, ground truth, production, scoring, detector, PR27, or frozen artifacts were accessed or modified.
