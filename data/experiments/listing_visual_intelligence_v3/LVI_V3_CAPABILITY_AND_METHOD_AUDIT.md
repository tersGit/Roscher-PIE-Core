# LVI v3 capability and method audit

## Capability gate

| Capability | Result | Actual component / limit |
|---|---|---|
| Multimodal captioning / relationship reasoner | Unavailable | `transformers` is installed but no local captioning/VLM weights were found. |
| Semantic comparison | Available and usable | Cached `timm/vit_base_patch32_clip_224.openai` weights (605 MB); not used as a substitute captioner. |
| Object detection | Available and used | Cached `google/owlvit-base-patch32` weights (613 MB), local CPU inference, 224-pixel patch model, prompted zero-shot detections. |
| Segmentation | Unavailable | No SAM/segmentation package or weights. |
| Contour/geometry | Available and used, limited | OpenCV 5 Canny/external contours; edges only, no calibrated metric geometry or ownership inference. |
| Multi-image reasoning | Partly available | Evidence fusion is deterministic and only joins repeated direct appearances; no VLM relationship model is available. |
| Video/keyframing / temporal analysis | Partly available, unusable here | `yt_dlp` Python module and OpenCV are present; original source retrieval failed before a stream could be preserved. |

The environment is CPU-only (`torch` 2.13.0, CUDA false).  Generic deterministic RGB/layout classification was not used. OWL-ViT detections support frame review but the published fingerprint is limited to visually verified direct observations.

## Recovery-path finding

The normal `backend.parsers.property24.fetch_listing()` parser extracts only YouTube embeds. LVI v1 downloads stills to a temporary directory and deletes that cache; it records `video_count` but never downloads video. LVI v2 then hard-codes `NOT_RETAINED_IN_LVI_V1_CORPUS`. For `117255083`, the current normal parse returns `https://www.youtube.com/embed/bGvUiiWGuSE`; this proves v2's zero keyframes was a preservation failure, not source-video absence. At this run, `python -m yt_dlp --dump-single-json` returns YouTube's `This video is not available`, so original video, technical metadata, and keyframes cannot be preserved. This is an acquisition failure for the public embed, not an assertion of source-video absence.

No identity, address, erf, GIS, candidate, G9 Top5/Top20, ranking, scoring, Native15, pool detector, PR27, production, known ground truth, or G9H material was read by this extractor.
