#!/usr/bin/env python3
"""Run a rank-blind, high-recall W3-V geometry retrieval over frozen W1 crops."""

from __future__ import annotations

import argparse
import csv
import hashlib
import math
from pathlib import Path

import cv2
import numpy as np


METHOD_VERSION = "w3v-geometry-retrieval-v1"
PROFILE_SHA256 = "56aca3c5d9d680a1a69dd19680d885fe38793c45900133f762267332d16d04bc"


def clipped(value: float) -> float:
    return max(0.0, min(1.0, value))


def component_metrics(mask: np.ndarray) -> list[dict[str, float]]:
    count, _, stats, centroids = cv2.connectedComponentsWithStats(mask, 8)
    components: list[dict[str, float]] = []
    for index in range(1, count):
        area = float(stats[index, cv2.CC_STAT_AREA])
        if area < 80 or area > 55_000:
            continue
        x, y, width, height = (float(stats[index, field]) for field in (
            cv2.CC_STAT_LEFT, cv2.CC_STAT_TOP, cv2.CC_STAT_WIDTH, cv2.CC_STAT_HEIGHT
        ))
        component = (mask == index).astype(np.uint8)
        contours, _ = cv2.findContours(component, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue
        contour = max(contours, key=cv2.contourArea)
        contour_area = max(cv2.contourArea(contour), 1.0)
        rect = cv2.minAreaRect(contour)
        rect_w, rect_h = rect[1]
        rect_area = max(rect_w * rect_h, 1.0)
        aspect = max(rect_w, rect_h) / max(min(rect_w, rect_h), 1.0)
        components.append({
            "area": area,
            "fraction": area / mask.size,
            "rectangularity": clipped(contour_area / rect_area),
            "aspect": aspect,
            "cx": float(centroids[index][0]),
            "cy": float(centroids[index][1]),
            "width": width,
            "height": height,
        })
    return components


def normalized(values: np.ndarray) -> np.ndarray:
    minimum, maximum = float(values.min()), float(values.max())
    if maximum <= minimum:
        return np.full_like(values, 0.5, dtype=float)
    return (values - minimum) / (maximum - minimum)


def inspect(path: Path) -> dict[str, object]:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None or image.shape[:2] != (900, 900):
        raise RuntimeError(f"Invalid frozen W1 crop: {path}")
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)
    green = cv2.inRange(hsv, (35, 35, 20), (90, 255, 230))
    water = cv2.inRange(hsv, (78, 35, 35), (115, 255, 255))
    water = cv2.morphologyEx(water, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    waters = component_metrics(water)

    def water_score(item: dict[str, float]) -> float:
        size = math.exp(-abs(math.log(max(item["fraction"], 1e-6) / 0.0025)))
        aspect = math.exp(-abs(math.log(max(item["aspect"], 1e-3) / 2.5)))
        return 0.45 * size + 0.35 * item["rectangularity"] + 0.20 * aspect

    best_water = max(waters, key=water_score, default=None)
    pool_score = water_score(best_water) if best_water else 0.0
    blue_fraction = float(np.mean(water > 0))
    shadow_fraction = float(np.mean(v < 55))
    vegetation_fraction = float(np.mean(green > 0))
    visibility = clipped(0.60 * (1.0 - shadow_fraction) + 0.40 * (1.0 - vegetation_fraction))
    if best_water and pool_score >= 0.46:
        water_state = "OBSERVED"
    elif shadow_fraction > 0.24 or vegetation_fraction > 0.58:
        water_state = "UNKNOWN"
    else:
        water_state = "CONFLICT"

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 55, 145)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 55, minLineLength=35, maxLineGap=12)
    line_length = 0.0
    if lines is not None:
        for x1, y1, x2, y2 in lines.reshape(-1, 4):
            line_length += math.hypot(float(x2 - x1), float(y2 - y1))
    line_density = clipped(line_length / 180_000.0)
    roof = ((s < 115) & (v > 35) & (v < 215) & (green == 0)).astype(np.uint8) * 255
    roof = cv2.morphologyEx(roof, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    roofs = component_metrics(roof)
    dominant_roof = max(roofs, key=lambda item: item["area"], default=None)
    roof_fraction = dominant_roof["fraction"] if dominant_roof else 0.0
    massing = clipped(0.55 * clipped(roof_fraction / 0.10) + 0.25 * line_density + 0.20 * (dominant_roof["rectangularity"] if dominant_roof else 0.0))

    relation = 0.35
    if best_water and dominant_roof:
        distance = math.hypot(best_water["cx"] - dominant_roof["cx"], best_water["cy"] - dominant_roof["cy"]) / 900.0
        spacing = math.exp(-((distance - 0.17) / 0.15) ** 2)
        parallel = 1.0 - min(1.0, abs(best_water["aspect"] - 2.5) / 4.0)
        relation = clipped(0.75 * spacing + 0.25 * parallel)

    bright_hardscape = ((s < 75) & (v > 135) & (green == 0)).astype(np.uint8) * 255
    hardscape = float(np.mean(bright_hardscape > 0))
    open_space = clipped((1.0 - vegetation_fraction) * 0.65 + clipped(hardscape / 0.35) * 0.35)
    access = clipped(0.65 * clipped(hardscape / 0.38) + 0.35 * line_density)
    texture = clipped(0.65 * visibility + 0.35 * clipped(float(gray.std()) / 62.0))

    return {
        "crop_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "water_state": water_state,
        "water_component_count": len(waters),
        "water_fraction": round(best_water["fraction"] if best_water else 0.0, 8),
        "water_rectangularity": round(best_water["rectangularity"] if best_water else 0.0, 6),
        "water_aspect": round(best_water["aspect"] if best_water else 0.0, 6),
        "water_raw": pool_score,
        "building_raw": massing,
        "relation_raw": relation,
        "outdoor_raw": open_space,
        "access_raw": access,
        "texture_raw": texture,
        "visibility": visibility,
        "vegetation_fraction": vegetation_fraction,
        "shadow_fraction": shadow_fraction,
        "uncertainty": "HIGH_OCCLUSION" if vegetation_fraction > 0.58 else ("HIGH_SHADOW" if shadow_fraction > 0.24 else "NONE"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-crops", required=True, type=Path)
    parser.add_argument("--profile", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if hashlib.sha256(args.profile.read_bytes()).hexdigest() != PROFILE_SHA256:
        raise RuntimeError("Immutable target profile hash does not match the authorized value.")
    paths = sorted(args.source_crops.glob("*_ags_aerial.jpg"))
    if len(paths) != 1010:
        raise RuntimeError(f"Expected exactly 1010 frozen W1 crops, found {len(paths)}.")
    rows = [inspect(path) for path in paths]
    for field in ("water_raw", "building_raw", "relation_raw", "outdoor_raw", "access_raw", "texture_raw"):
        values = normalized(np.array([float(row[field]) for row in rows]))
        for row, value in zip(rows, values):
            row[field.replace("_raw", "_normalized")] = float(value)
    median_water = float(np.median([float(row["water_normalized"]) for row in rows]))
    for row in rows:
        water = median_water if row["water_state"] == "UNKNOWN" else float(row["water_normalized"])
        row["retrieval_score"] = (
            0.30 * water + 0.24 * float(row["building_normalized"]) +
            0.20 * float(row["relation_normalized"]) + 0.14 * float(row["outdoor_normalized"]) +
            0.07 * float(row["access_normalized"]) + 0.05 * float(row["texture_normalized"])
        )
    rows.sort(key=lambda row: (-float(row["retrieval_score"]), str(row["crop_sha256"])))
    for index, row in enumerate(rows, start=1):
        row["retrieval_rank"] = index
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fields = ["retrieval_rank", "crop_sha256", "water_state", "uncertainty", "water_component_count",
              "water_fraction", "water_rectangularity", "water_aspect", "water_raw", "water_normalized",
              "building_raw", "building_normalized", "relation_raw", "relation_normalized", "outdoor_raw",
              "outdoor_normalized", "access_raw", "access_normalized", "texture_raw", "texture_normalized",
              "visibility", "vegetation_fraction", "shadow_fraction", "retrieval_score"]
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    counts = {state: sum(row["water_state"] == state for row in rows) for state in ("OBSERVED", "CONFLICT", "UNKNOWN")}
    print(f"method={METHOD_VERSION} rows={len(rows)} states={counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
