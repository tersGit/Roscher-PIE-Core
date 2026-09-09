# Candidate comparison

| Candidate | Revision / parameters | CPU deployment | Image and multi-image | CPU assessment | Outcome |
|---|---|---|---|---|---|
| HuggingFaceTB/SmolVLM2-2.2B-Instruct | `482adb537c021c86670beed01cd58990d01e72e4`; 2.2468B | Tested Transformers float32; GGUF Q4_K_M + projector is a future lower-RAM route | Yes / yes | Fits at 8-9 GiB RSS; 76-186 s per prompt | LIMITED |
| Qwen/Qwen2.5-VL-3B-Instruct | `66285546d2b821cf421d4f5eb2576359d3770cd3`; 3.7546B | Tested Transformers bfloat16; GGUF Q4_K_M + Q8 projector is a future lower-RAM route | Yes / yes | Fits at 7.6 GiB RSS; 119-367 s per prompt | LIMITED |
| openbmb/MiniCPM-V-4 | `6f69a8235885be89608f3a71ffd40695b379e1e7`; 4.1B | Not downloaded: custom-code runtime and expected 5-8 GiB quantized working set | Yes / yes/video | Strong prospective option, but not controlled-tested here | NOT TESTED |
| google/gemma-4-E4B-it | `ee0ef6023621cff504d758262d4e04895a5af4a2`; 4.5B effective | Not downloaded: Q4 plus projector is about 5.15 GB and 24 GiB RAM is prudent | Yes / yes/video frames | Not safely practical on this 15.3 GiB host | NOT TESTED |

Sources: [SmolVLM2 model card](https://huggingface.co/HuggingFaceTB/SmolVLM2-2.2B-Instruct), [Qwen2.5-VL model card](https://huggingface.co/Qwen/Qwen2.5-VL-3B-Instruct), [MiniCPM-V 4 model card](https://huggingface.co/openbmb/MiniCPM-V-4), [Gemma 4 model card](https://huggingface.co/google/gemma-4-E4B-it), and [llama.cpp multimodal documentation](https://github.com/ggml-org/llama.cpp/blob/master/docs/multimodal.md). Download-size/RAM values are deployment estimates, not measurements from this run.
