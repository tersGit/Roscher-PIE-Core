# Maintained multimodal runtime compatibility

| Runtime | Verified image path | Qualification |
|---|---|---|
| llama.cpp | Upstream `libmtmd`; `llama-mtmd-cli`/`llama-server`; `-m model.gguf --mmproj projector.gguf`, or supported `-hf` collection | Maintained multimodal documentation explicitly lists Qwen2.5-VL 7B, Gemma 3 12B, and image support. A text-only GGUF is **not** vision-capable: use the matching mmproj/projector from the same model release. |
| Ollama | Vision-capable model plus chat `images` array (base64 on REST; paths/bytes in SDK) | Maintained Vision documentation confirms images alongside text. Verify the exact pulled tag is a vision model; a text-only Ollama model cannot infer from images. |
| Transformers | `AutoProcessor`/image-text-to-text model and chat template with image entries | Maintained Hugging Face guide documents multi-image messages. Best compatibility path for native Qwen/Gemma checkpoints; more Python/CUDA dependency surface than llama.cpp. |
| MLX | Apple Silicon only | Not applicable to this Windows x86-64 host; do not use for the first run. |
| vLLM/SGLang | Native multimodal checkpoints on compatible GPU | Maintained model ecosystems support these for throughput, but they add CUDA/container complexity and are not needed for the first portable benchmark. |

Sources: [llama.cpp multimodal documentation](https://github.com/ggml-org/llama.cpp/blob/master/docs/multimodal.md), [Ollama Vision documentation](https://docs.ollama.com/capabilities/vision), and [Transformers image-text-to-text documentation](https://huggingface.co/docs/transformers/main/en/tasks/image_text_to_text).
