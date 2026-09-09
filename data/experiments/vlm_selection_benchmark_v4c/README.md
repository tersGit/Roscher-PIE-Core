# V4C stronger VLM selection benchmark

Reproduce with:

```powershell
python scripts\run_vlm_selection_benchmark_v4c.py --model smolvlm2_2b --overwrite
python scripts\run_vlm_selection_benchmark_v4c.py --model qwen25vl_3b --overwrite
python scripts\emit_vlm_selection_evidence_v4c.py
python -m pytest -q tests\test_vlm_selection_benchmark_v4c_schema.py
```

The benchmark creates only unlabelled synthetic controls, runs natural captions before targeted prompts, retains raw results, and records CPU/RSS/timing. It is deliberately separate from production and frozen work.
