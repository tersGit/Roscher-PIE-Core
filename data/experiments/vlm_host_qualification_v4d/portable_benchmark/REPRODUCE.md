# Portable neutral benchmark reproduction

This directory is self-contained and contains only four synthetic PNG controls, the unchanged V4C prompts/rubric, V4C raw outputs, and the V4D guard. It contains no listing-derived material.

## Preconditions

1. Copy this `portable_benchmark` directory as a unit to a local trusted host.
2. Install a maintained vision runtime and one explicitly vision-capable model. For the selected first run, use current llama.cpp with `ggml-org/Qwen2.5-VL-7B-Instruct-GGUF` and the matching mmproj that the release supplies. Do not substitute a text-only GGUF.
3. Keep model artifacts outside this package; record artifact URL, immutable revision/digest, quantization, llama.cpp version, OS, CPU/GPU, RAM/VRAM, context, image-resolution setting, and command.

## Validate the portable guard

From the repository root:

```powershell
python -m pytest -q data\experiments\vlm_host_qualification_v4d\tests\test_portable_benchmark_guard.py
python data\experiments\vlm_host_qualification_v4d\portable_benchmark\run_portable_benchmark.py
```

The command prints the only files it will permit. The package accepts no external image path, glob, recursive traversal, manifest indirection, symlink, or junction.

## Execute unchanged neutral prompts

For each control, submit exactly the listed prompt(s), retaining the image-to-prompt binding:

| Control | Prompts |
|---|---|
| `coloured_shapes.png` | `natural_caption`, `spatial_inspection`, `targeted_architecture` |
| `unlabelled_property_schematic.png` | `natural_caption`, `spatial_inspection`, `targeted_architecture` |
| `neutral_multiview_a.png` + `neutral_multiview_b.png` in that order | `spatial_inspection` only |

Use deterministic decoding (temperature zero / greedy) and V4C's 180 generated-token limit where the runtime supports it. Write a new result JSON beside the package, preserving every raw response, elapsed seconds, RSS/VRAM observation, model artifact identity, runtime version, device, and exact command. Score only against `neutral_controls_and_truth_rubric.json`; a pass requires all V4C E-L spatial relationships, no material hallucination, and materially better image-dependent spatial behavior than the 256M baseline.

`raw_outputs_smolvlm2_2b.json` and `raw_outputs_qwen25vl_3b.json` are retained only as V4C comparison evidence. Do not overwrite them.
