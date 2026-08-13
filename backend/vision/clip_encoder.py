"""OpenCLIP helpers for listing vs AGS comparison."""

from __future__ import annotations

from functools import lru_cache

import numpy as np
from PIL import Image

SCENE_LABELS = [
    "aerial drone photo of a house and garden from above",
    "swimming pool and house garden backyard",
    "front elevation of a suburban house",
    "rear elevation of a suburban house",
    "driveway and garage of a house",
    "interior living room kitchen bathroom",
    "contextual garden lawn and house exterior",
]
SCENE_KEYS = [
    "aerial",
    "pool_garden",
    "front_elevation",
    "rear_elevation",
    "driveway_access",
    "interior",
    "contextual",
]


@lru_cache(maxsize=1)
def load_clip():
    import open_clip
    import torch

    model, _, preprocess = open_clip.create_model_and_transforms("ViT-B-32", pretrained="openai")
    tokenizer = open_clip.get_tokenizer("ViT-B-32")
    model.eval()
    return model, preprocess, tokenizer, torch


def encode_image(image: Image.Image) -> np.ndarray:
    model, preprocess, _, torch = load_clip()
    tensor = preprocess(image.convert("RGB")).unsqueeze(0)
    with torch.no_grad():
        feat = model.encode_image(tensor)
        feat = feat / feat.norm(dim=-1, keepdim=True)
    return feat.cpu().numpy()[0]


def classify_scene(image: Image.Image) -> str:
    model, preprocess, tokenizer, torch = load_clip()
    image_t = preprocess(image.convert("RGB")).unsqueeze(0)
    text = tokenizer(SCENE_LABELS)
    with torch.no_grad():
        image_f = model.encode_image(image_t)
        text_f = model.encode_text(text)
        image_f = image_f / image_f.norm(dim=-1, keepdim=True)
        text_f = text_f / text_f.norm(dim=-1, keepdim=True)
        scores = (100.0 * image_f @ text_f.T).softmax(dim=-1)[0]
    index = int(scores.argmax().item())
    return SCENE_KEYS[index]


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / max(np.linalg.norm(a) * np.linalg.norm(b), 1e-9))


def mean_top_similarity(listing: list[np.ndarray], candidate: list[np.ndarray], top_k: int = 3) -> float | None:
    if not listing or not candidate:
        return None
    scores = []
    for item in listing:
        scores.append(max(cosine(item, other) for other in candidate))
    scores.sort(reverse=True)
    return float(sum(scores[:top_k]) / max(len(scores[:top_k]), 1))
