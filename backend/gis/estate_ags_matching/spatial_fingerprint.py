"""Parcel-relative spatial fingerprint persistence (object_segmentation_v1).

This module stores the experimental object graph separately from frozen
CLIP / pool_geometry fingerprints so the experiment can be rolled back.
It does not feed ranking.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from backend.vision.object_segmentation import (
    SEGMENTATION_VERSION,
    objects_to_json,
    segment_parcel_bgr,
)

__all__ = [
    "SEGMENTATION_VERSION",
    "load_fingerprint",
    "save_fingerprint",
    "segment_and_save",
]


def save_fingerprint(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_fingerprint(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def segment_and_save(
    *,
    image_bgr: np.ndarray,
    parcel_geometry: dict,
    stand_number: str,
    out_path: Path,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    objects = segment_parcel_bgr(
        image_bgr, stand_number=str(stand_number), geometry=parcel_geometry
    )
    payload = objects_to_json(objects)
    if extra:
        payload["extra"] = extra
    save_fingerprint(out_path, payload)
    return payload
