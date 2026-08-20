"""Pool Shape Family v1 — geometry-only diagnostic classifier.

No listing-id rules, no stand-number rules, no water colour, no Scoring v2
weight edits. Labels in this file are synthetic shapes, not properties.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from backend.gis.estate_ags_matching.os_scoring_v2 import V2_WEIGHTS_NO_BUILDING
from backend.gis.estate_ags_matching.pool_shape_family_v1 import (
    FAMILIES,
    compatibility,
    classify_contour,
    hard_reject,
    penalty_multiplier,
)


MODULE = Path("backend/gis/estate_ags_matching/pool_shape_family_v1.py")


def _rectangle(w: float = 1.0, h: float = 0.7, n: int = 40) -> np.ndarray:
    xs = np.linspace(-w, w, n // 4, endpoint=False)
    ys = np.linspace(-h, h, n // 4, endpoint=False)
    top = np.stack([xs, np.full_like(xs, -h)], axis=1)
    right = np.stack([np.full_like(ys, w), ys], axis=1)
    bot = np.stack([xs[::-1], np.full_like(xs, h)], axis=1)
    left = np.stack([np.full_like(ys, -w), ys[::-1]], axis=1)
    return np.vstack([top, right, bot, left])


def _circle(n: int = 64) -> np.ndarray:
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    return np.stack([np.cos(t), np.sin(t)], axis=1)


def _kidney(n: int = 80) -> np.ndarray:
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    x = np.cos(t) * (1.0 + 0.45 * np.sin(t))
    y = 0.55 * np.sin(t)
    return np.stack([x, y], axis=1)


def _l_shape() -> np.ndarray:
    """Densified L — multiple indents, not a rectangle."""
    verts = np.array(
        [[0.0, 0.0], [2.0, 0.0], [2.0, 0.55], [0.55, 0.55], [0.55, 2.0], [0.0, 2.0]],
        dtype=float,
    )
    pts = []
    for i in range(len(verts)):
        a = verts[i]
        b = verts[(i + 1) % len(verts)]
        for t in np.linspace(0, 1, 12, endpoint=False):
            pts.append(a * (1 - t) + b * t)
    return np.asarray(pts, dtype=float)


def test_module_has_no_listing_or_stand_hardcodes():
    text = MODULE.read_text(encoding="utf-8")
    assert "116778622" not in text
    assert "GT_STAND" not in text
    assert "water_colour" not in text.lower()
    assert "water color" not in text.lower()
    assert "V2_WEIGHTS_NO_BUILDING[" not in text


def test_production_weights_untouched():
    assert dict(V2_WEIGHTS_NO_BUILDING)["shape_v2"] == 0.36


def test_rectangle_is_rectangular():
    result = classify_contour(_rectangle())
    assert result["family"] == "RECTANGULAR"
    assert result["confidence"] >= 0.5


def test_lap_pool_is_lap_elongated():
    result = classify_contour(_rectangle(w=2.4, h=0.45))
    assert result["family"] == "LAP_ELONGATED"
    assert result["family"] in FAMILIES


def test_circle_is_round_oval():
    result = classify_contour(_circle())
    assert result["family"] == "ROUND_OVAL"


def test_kidney_is_not_rectangular():
    result = classify_contour(_kidney())
    assert result["family"] != "RECTANGULAR"
    assert result["family"] in {"FREEFORM", "KIDNEY_CURVED", "COMPOUND_IRREGULAR", "UNKNOWN"}


def test_l_shape_not_rectangular():
    result = classify_contour(_l_shape())
    assert result["family"] != "RECTANGULAR"
    assert result["family"] in {"COMPOUND_IRREGULAR", "FREEFORM", "KIDNEY_CURVED", "UNKNOWN"}


def test_freeform_vs_rectangular_incompatible():
    assert compatibility("FREEFORM", "RECTANGULAR") == "incompatible"
    assert hard_reject("incompatible") is True
    assert hard_reject("no_decision") is False
    assert penalty_multiplier("incompatible") == 0.20
    assert penalty_multiplier("partial") == 0.55
    assert compatibility("UNKNOWN", "RECTANGULAR") == "no_decision"
    assert hard_reject(compatibility("UNKNOWN", "RECTANGULAR")) is False
