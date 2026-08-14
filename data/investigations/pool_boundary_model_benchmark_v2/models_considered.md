# Models considered (CPU, no GPU assumed)

Environment at survey: 4 vCPU, 15 GiB RAM, torch 2.13.0+cpu, ultralytics 8.3.253, FastSAM-s already cached (23 MB). No `transformers`, `sam2`, `groundingdino`, or CUDA.

| model | package | size | CPU | expected CPU runtime | RAM | licence | install | verdict |
|---|---|---|---|---|---|---|---|---|
| FastSAM-s (frozen PR #11) | ultralytics FastSAM | 23 MB / 11.8M | yes | ~0.06–1 s/frame at imgsz 512 | low | AGPL-3.0 | already present | baseline, not replaced |
| FastSAM-x | ultralytics | ~138 MB | yes | similar family, a few s/frame | moderate | AGPL-3.0 | one weight file | same proposal style as FastSAM-s; not a new capability |
| YOLOE-11s-seg | ultralytics YOLOE | ~27 MB | yes | ~0.3–2 s/frame @640 after CLIP class embed | ~1–2 GB | AGPL-3.0 | one weight file | **primary candidate** — text-prompted instance segmentation, already in PIE stack |
| YOLOE-11m-seg | ultralytics YOLOE | ~50 MB | yes | ~1–4 s/frame @640 | ~2–3 GB | AGPL-3.0 | one weight file | quality step-up still PIE-practical; run if 11s misses the pool |
| YOLO-World v2 s | ultralytics YOLOWorld | ~25 MB | yes | detect-only; needs a segmenter | ~1–2 GB | AGPL-3.0 | one weight file | text boxes only; YOLOE already returns masks |
| SAM 2.1 tiny (`sam2.1_t.pt`) | ultralytics SAM | ~78 MB / 38.9M | yes | **~23 s/frame** (docs) | ~2–4 GB | Apache-2.0 weights; AGPL wrapper | one weight file | **boundary specialist** prompted by YOLOE boxes/points; listing-side only on few overview frames |
| SAM 2.1 small/base | ultralytics SAM | 46–162 MB | yes | 25–30+ s/frame | 3–6 GB | Apache-2.0 / AGPL | one weight file | slower, not justified before tiny is proven |
| MobileSAM | ultralytics | 41 MB | yes | ~24 s/frame (docs) | ~2 GB | Apache-2.0 | one weight file | similar CPU cost to SAM2-t, weaker masks |
| Grounding DINO + SAM2 | groundingdino + sam2/transformers | ~700 MB + SAM | theoretically CPU | tens of seconds–minutes/frame | 6–10 GB | Apache-2.0 | **new stack**, CUDA-oriented | rejected: install+runtime cost vs YOLOE |
| official `sam2` package | pip sam2 | same weights | CPU possible | similar to ultralytics SAM2 | 3–6 GB | Apache-2.0 | extra dep, CUDA-first | redundant with ultralytics 8.3.253 |
| SAM 3 | ultralytics SAM3 | **3.45 GB** / 474M | GPU-oriented | GPU ~3 s; CPU impractical | >8 GB weights | Meta gated HF weights | HF access + 3.5 GB | rejected for PIE CPU |
| YOLO11-seg (COCO) | ultralytics | 6–62 MB | yes | fast | low | AGPL-3.0 | one file | **no swimming-pool class** in COCO |
| colour/HSV blobs | OpenCV | n/a | yes | fast | tiny | BSD | already frozen | **prohibited** as geometry evidence |

## Selection for the actual benchmark

**YOLOE-11s-seg** as the practical open-vocabulary segmenter (text prompt `swimming pool`), with **YOLOE-11m-seg** as a same-family quality check, and **SAM 2.1 tiny** as a box/point-prompted boundary refiner on YOLOE detections.

Why not the largest model: SAM3 and Grounding DINO+SAM2 are not practical for CPU PIE. Why not FastSAM-x: same class of everything-proposals that already failed to separate deck/lawn.

Prompt strategies (all automatable, no manual clicks):

1. YOLOE text-only (`swimming pool`)
2. YOLOE multi-class text (`swimming pool`, `hot tub`, `wooden deck`, `lawn`)
3. YOLOE pool box → SAM2.1-t
4. YOLOE pool-mask centroid → SAM2.1-t positive point
