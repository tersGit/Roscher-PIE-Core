# V4D stronger host and multimodal runtime qualification

V4D evaluates only neutral benchmark portability and host options. It does not begin LVI v5 and does not alter production, scoring, detector, or frozen evidence.

## Verdict

**Decision C — upgrade or use a local 24-32 GiB workstation, then run `ggml-org/Qwen2.5-VL-7B-Instruct-GGUF` through maintained llama.cpp (`llama-mtmd-cli` or `llama-server`) at Q4_K_M with its matching projector.** This is the lowest-install-complexity first stronger candidate that is documented in llama.cpp's maintained multimodal matrix and preserves local-only processing. The current 15.31 GiB Windows host is not sufficient for reliable repeated PIE-neutral inference: V4C had only 4.48 GiB available at capture and its 3B Transformers runs already took 119-367 seconds per prompt.

See [host options](host_options.md), [runtime compatibility](runtime_compatibility.md), [candidate shortlist](candidate_shortlist.md), and [portable reproduction](portable_benchmark/REPRODUCE.md).

## Scope and protocol record

V4C's intended protocol was neutral-only. A broad glob exposed forbidden listing-directory filenames; no media content was opened, read, inferred, or used. This deviation is recorded transparently here. In V4D, **no listing directory was enumerated or accessed.** All package inputs are copied only from individually inspected V4C neutral file paths, and the portable runner allows only four named control files.
