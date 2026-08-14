"""Pool Boundary Extraction v1 — generic, no listing/stand hardcodes, no colour blobs."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from backend.gis.estate_ags_matching.pool_boundary_v1 import (
    coping_ring,
    local_ridge_snap,
    reject_wall_segments,
    score_and_gate,
)


def test_module_has_no_listing_hardcodes_or_colour_thresholds():
    text = Path("backend/gis/estate_ags_matching/pool_boundary_v1.py").read_text(encoding="utf-8")
    assert "116978058" not in text
    assert "116273255" not in text
    assert "365" not in text
    assert "inRange" not in text
    assert "COLOR_BGR2HSV" not in text
    assert "COLOR_RGB2HSV" not in text
    assert "cyan_frac" not in text
    assert "octagon" not in text.lower()
    assert "l-shaped" not in text.lower()
    assert "l_shaped" not in text.lower()


def test_object_mask_method_cannot_pass_gate():
    geom = {"relative_area": 0.18, "compactness": 0.55, "solidity": 0.88, "aspect_ratio": 1.6}
    clip = {"pool": 0.70, "wall": 0.05, "vegetation": 0.05, "furniture": 0.02, "bathtub": 0.0, "interior": 0.0}
    accepted, reason, *_ = score_and_gate(
        viewpoint="pool_overview",
        geom=geom,
        clip=clip,
        structural_support=0.70,
        edge_clip=0.02,
        climb=0.0,
        corroborated=True,
        method="fastsam_contour",
    )
    assert accepted is False
    assert reason == "object_mask_is_not_perimeter"


def test_corroboration_cannot_promote_weak_structure():
    geom = {"relative_area": 0.18, "compactness": 0.55, "solidity": 0.88, "aspect_ratio": 1.6}
    clip = {"pool": 0.55, "wall": 0.05, "vegetation": 0.05, "furniture": 0.02, "bathtub": 0.0, "interior": 0.0}
    accepted, reason, _conf, notes = score_and_gate(
        viewpoint="pool_overview",
        geom=geom,
        clip=clip,
        structural_support=0.40,
        edge_clip=0.02,
        climb=0.0,
        corroborated=True,
        method="local_ridge_snap",
    )
    assert accepted is False
    assert "needs_stronger_structure" in notes


def test_closed_polygon_without_structure_cannot_pass_gate():
    geom = {
        "relative_area": 0.18,
        "compactness": 0.55,
        "solidity": 0.88,
        "aspect_ratio": 1.6,
    }
    clip = {"pool": 0.55, "wall": 0.05, "vegetation": 0.05, "furniture": 0.02, "bathtub": 0.0, "interior": 0.0}
    accepted, reason, _conf, notes = score_and_gate(
        viewpoint="pool_overview",
        geom=geom,
        clip=clip,
        structural_support=0.10,
        edge_clip=0.02,
        climb=0.0,
        corroborated=False,
    )
    assert accepted is False
    assert "closed_polygon_without_structure" in notes or "weak_structural_edge_support" in notes


def test_bathtub_clip_cannot_pass_gate():
    geom = {"relative_area": 0.12}
    clip = {"pool": 0.20, "wall": 0.05, "vegetation": 0.02, "furniture": 0.02, "bathtub": 0.55, "interior": 0.1}
    accepted, reason, *_ = score_and_gate(
        viewpoint="pool_overview",
        geom=geom,
        clip=clip,
        structural_support=0.7,
        edge_clip=0.02,
        climb=0.0,
        corroborated=True,
    )
    assert accepted is False
    assert reason == "bathtub_or_bathroom"


def test_interior_viewpoint_blocked():
    accepted, reason, *_ = score_and_gate(
        viewpoint="interior",
        geom={"relative_area": 0.2},
        clip={"pool": 0.9, "wall": 0.0, "vegetation": 0.0, "furniture": 0.0, "bathtub": 0.0, "interior": 0.0},
        structural_support=0.9,
        edge_clip=0.0,
        climb=0.0,
        corroborated=True,
    )
    assert accepted is False
    assert reason == "blocked_viewpoint"


def test_closeup_cannot_be_overview_ready():
    accepted, reason, *_ = score_and_gate(
        viewpoint="pool_closeup",
        geom={"relative_area": 0.2},
        clip={"pool": 0.9, "wall": 0.0, "vegetation": 0.0, "furniture": 0.0, "bathtub": 0.0, "interior": 0.0},
        structural_support=0.9,
        edge_clip=0.0,
        climb=0.0,
        corroborated=True,
    )
    assert accepted is False
    assert reason == "closeup_not_overview"


def test_wall_segments_above_pool_object_are_dropped():
    mask = np.zeros((80, 80), dtype=bool)
    mask[40:70, 20:60] = True
    segs = np.array([[30, 5, 32, 38], [25, 50, 55, 50]], np.float32)
    keep, drop = reject_wall_segments(segs, mask)
    assert len(drop) == 1
    assert len(keep) == 1


def test_local_ridge_snap_is_stable_across_water_fill_colours():
    import cv2

    def _l(fill):
        image = Image.new("RGB", (240, 180), (40, 130, 50))
        draw = ImageDraw.Draw(image)
        draw.rectangle([20, 70, 220, 170], fill=(190, 180, 165))
        draw.polygon([(40, 90), (200, 90), (200, 125), (95, 125), (95, 160), (40, 160)], fill=fill)
        return np.array(image)[:, :, ::-1].copy()

    contours = []
    for fill in [(15, 15, 15), (40, 170, 200), (25, 80, 35)]:
        bgr = _l(fill)
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        mag = np.hypot(gx, gy)
        mask = np.zeros((180, 240), np.uint8)
        cv2.fillPoly(mask, [np.array([[40, 90], [200, 90], [200, 125], [95, 125], [95, 160], [40, 160]], np.int32)], 255)
        raw, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        snapped = local_ridge_snap(raw[0], mag, gx, gy, max_r=10)
        binm = np.zeros((180, 240), np.uint8)
        cv2.drawContours(binm, [snapped], -1, 255, -1)
        contours.append(binm > 0)
    base = contours[0]
    for other in contours[1:]:
        inter = float(np.logical_and(base, other).sum())
        union = float(np.logical_or(base, other).sum())
        assert inter / union >= 0.75


def test_coping_ring_is_outside_object_not_interior_fill():
    mask = np.zeros((60, 60), dtype=bool)
    mask[20:40, 20:40] = True
    ring = coping_ring(mask, inner=2, outer=8)
    assert ring[30, 30] == 0
    inner = (ring[22:38, 22:38] > 0).mean()
    band = (ring[16:44, 16:44] > 0).mean()
    assert inner < 0.35
    assert band > 0.15
