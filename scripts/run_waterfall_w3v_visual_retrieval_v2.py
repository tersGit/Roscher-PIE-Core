#!/usr/bin/env python3
"""Run the preregistered, parcel-bound W3-V V2 visual retrieval."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "investigations" / "waterfall_w3v_visual_gt_recovery" / "v2"
PROFILE = ROOT / "data" / "investigations" / "waterfall_w3v_visual_gt_recovery" / "TARGET_GEOMETRY_PROFILE.md"
GEOJSON = ROOT / "data" / "estates" / "waterfall_country_estate" / "waterfall_country_estate_w1.geojson"
SOURCE = Path(
    r"C:\Users\ters\copilot-worktrees\Roscher-PIE-Core\tersgit-probable-winner"
    r"\data\visual_index\waterfall_country_estate_w1\_imagery_cache_native15"
)
PROFILE_SHA256 = "56aca3c5d9d680a1a69dd19680d885fe38793c45900133f762267332d16d04bc"
WEIGHTS = {
    "pool": 0.25,
    "building": 0.20,
    "pool_house_relation": 0.20,
    "driveway": 0.10,
    "open_space": 0.10,
    "parcel_geometry": 0.15,
}
COMPONENTS = tuple(WEIGHTS)
COMPAT_VALUES = {"MATCH": 1.0, "PARTIAL": 0.5, "CONFLICT": 0.0, "UNKNOWN": 0.0}


def clipped(value: float) -> float:
    return max(0.0, min(1.0, value))


def components(mask: np.ndarray, minimum: int) -> list[dict[str, float]]:
    count, labels, stats, centers = cv2.connectedComponentsWithStats(mask, 8)
    result: list[dict[str, float]] = []
    for index in range(1, count):
        area = int(stats[index, cv2.CC_STAT_AREA])
        if area < minimum:
            continue
        region = (labels == index).astype(np.uint8)
        contours, _ = cv2.findContours(region, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue
        contour = max(contours, key=cv2.contourArea)
        rect = cv2.minAreaRect(contour)
        width, height = rect[1]
        result.append({
            "area": float(area),
            "cx": float(centers[index][0]),
            "cy": float(centers[index][1]),
            "rectangularity": float(cv2.contourArea(contour) / max(width * height, 1.0)),
            "aspect": max(width, height) / max(min(width, height), 1.0),
        })
    return result


def parcel_mask(feature: dict, shape: tuple[int, int]) -> np.ndarray:
    """Reconstruct the frozen crop's parcel mask from its bbox plus 18 m padding."""
    height, width = shape
    ring = feature["geometry"]["rings"][0]
    lons = [point[0] for point in ring]
    lats = [point[1] for point in ring]
    pad = 18.0 / 111_320
    min_lon, max_lon = min(lons) - pad, max(lons) + pad
    min_lat, max_lat = min(lats) - pad, max(lats) + pad
    points = np.array([[
        round((lon - min_lon) / (max_lon - min_lon) * (width - 1)),
        round((max_lat - lat) / (max_lat - min_lat) * (height - 1)),
    ] for lon, lat in ring], dtype=np.int32)
    mask = np.zeros((height, width), dtype=np.uint8)
    cv2.fillPoly(mask, [points], 255)
    return mask


def binding(item: dict[str, float] | None, mask: np.ndarray) -> str:
    if item is None:
        return "UNBOUND"
    x, y = round(item["cx"]), round(item["cy"])
    x = min(max(x, 0), mask.shape[1] - 1)
    y = min(max(y, 0), mask.shape[0] - 1)
    if mask[y, x]:
        return "IN_PARCEL"
    dilated = cv2.dilate(mask, np.ones((9, 9), np.uint8))
    return "BOUNDARY_AMBIGUOUS" if dilated[y, x] else "OUTSIDE_PARCEL"


def evidence(visibility: str, bound: str, compat: str, confidence: float) -> tuple[str, str, str, float, float]:
    if visibility not in {"OBSERVED", "PARTIAL"} or bound not in {"IN_PARCEL", "BOUNDARY_AMBIGUOUS"}:
        compat = "UNKNOWN" if compat != "CONFLICT" else compat
    eligible = visibility in {"OBSERVED", "PARTIAL"} and bound in {"IN_PARCEL", "BOUNDARY_AMBIGUOUS"} and compat != "UNKNOWN"
    return visibility, bound, compat, round(confidence, 4), round(confidence * COMPAT_VALUES[compat] if eligible else 0.0, 6)


def inspect(feature: dict, crop: Path) -> dict[str, object]:
    image = cv2.imread(str(crop), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"Unreadable frozen crop: {crop}")
    height, width = image.shape[:2]
    mask = parcel_mask(feature, (height, width))
    inside = mask > 0
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    hue, saturation, value = cv2.split(hsv)
    shadow = float(np.mean(value[inside] < 50))
    green = (hue >= 35) & (hue <= 90) & (saturation >= 35) & (value >= 20)
    green_fraction = float(np.mean(green[inside]))
    image_confidence = clipped(0.92 - 0.65 * shadow)
    minimum = max(8, int(inside.sum() * 0.00008))

    blue = cv2.inRange(hsv, (78, 40, 35), (116, 255, 255))
    blue = cv2.morphologyEx(blue, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    blue_items = components(blue, minimum)
    pool_item = max(blue_items, key=lambda item: item["rectangularity"] * min(item["aspect"], 4.0), default=None)
    pool_bind = binding(pool_item, mask)
    pool_visible = "AMBIGUOUS"
    pool_compat = "UNKNOWN"
    pool_conf = image_confidence * 0.55
    if pool_item and pool_bind in {"IN_PARCEL", "BOUNDARY_AMBIGUOUS"}:
        pool_conf = image_confidence * clipped(pool_item["area"] / (inside.sum() * 0.0015))
        if pool_item["rectangularity"] >= 0.68 and pool_item["aspect"] >= 1.35:
            pool_visible, pool_compat = "OBSERVED", "MATCH"
        else:
            pool_visible, pool_compat = "PARTIAL", "PARTIAL"
    pool = evidence(pool_visible, pool_bind, pool_compat, pool_conf)

    roof = ((saturation < 115) & (value > 40) & (value < 220) & ~green).astype(np.uint8) * 255
    roof = cv2.morphologyEx(roof, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    roof_items = components(roof, minimum * 3)
    roof_item = max(roof_items, key=lambda item: item["area"], default=None)
    roof_bind = binding(roof_item, mask)
    roof_fraction = roof_item["area"] / inside.sum() if roof_item else 0.0
    if roof_item and roof_bind in {"IN_PARCEL", "BOUNDARY_AMBIGUOUS"} and roof_fraction >= 0.025:
        building = evidence("OBSERVED", roof_bind, "MATCH" if roof_item["rectangularity"] >= 0.55 else "PARTIAL", image_confidence * 0.8)
    elif roof_item and roof_bind in {"IN_PARCEL", "BOUNDARY_AMBIGUOUS"}:
        building = evidence("PARTIAL", roof_bind, "PARTIAL", image_confidence * 0.55)
    else:
        building = evidence("AMBIGUOUS", roof_bind, "UNKNOWN", image_confidence * 0.4)

    if pool_item and roof_item and pool[0] in {"OBSERVED", "PARTIAL"} and building[0] in {"OBSERVED", "PARTIAL"}:
        distance = math.hypot(pool_item["cx"] - roof_item["cx"], pool_item["cy"] - roof_item["cy"]) / math.hypot(width, height)
        relation_compat = "MATCH" if distance <= 0.33 else ("PARTIAL" if distance <= 0.48 else "CONFLICT")
        relation = evidence("OBSERVED", "IN_PARCEL", relation_compat, min(pool[3], building[3]) * 0.85)
    else:
        relation = evidence("AMBIGUOUS", "UNBOUND", "UNKNOWN", image_confidence * 0.35)

    hardscape = ((saturation < 70) & (value > 135) & ~green).astype(np.uint8) * 255
    hardscape_items = components(hardscape, minimum * 2)
    drive_item = max(hardscape_items, key=lambda item: item["area"], default=None)
    drive_bind = binding(drive_item, mask)
    if drive_item and drive_bind in {"IN_PARCEL", "BOUNDARY_AMBIGUOUS"}:
        driveway = evidence("PARTIAL", drive_bind, "PARTIAL", image_confidence * 0.6)
    else:
        driveway = evidence("AMBIGUOUS", drive_bind, "UNKNOWN", image_confidence * 0.35)

    visible_land = image_confidence >= 0.60 and roof_item is not None
    if visible_land:
        open_compat = "CONFLICT" if green_fraction > 0.62 else ("MATCH" if green_fraction < 0.43 else "PARTIAL")
        open_space = evidence("OBSERVED", "IN_PARCEL", open_compat, image_confidence * 0.70)
    else:
        open_space = evidence("AMBIGUOUS", "UNBOUND", "UNKNOWN", image_confidence * 0.35)

    if building[0] in {"OBSERVED", "PARTIAL"} and visible_land:
        parcel = evidence("OBSERVED", "IN_PARCEL", "MATCH" if roof_fraction >= 0.05 else "PARTIAL", image_confidence * 0.65)
    else:
        parcel = evidence("AMBIGUOUS", "UNBOUND", "UNKNOWN", image_confidence * 0.35)

    result: dict[str, object] = {
        "propertyid": str(feature["properties"]["pie_property_id"]),
        "crop_sha256": hashlib.sha256(crop.read_bytes()).hexdigest(),
    }
    for name, item in zip(COMPONENTS, (pool, building, relation, driveway, open_space, parcel)):
        result[f"{name}_visibility"], result[f"{name}_binding"], result[f"{name}_compat"], result[f"{name}_confidence"], raw = item
        result[f"{name}_score"] = round(WEIGHTS[name] * raw, 6)
    result["observed"] = sum(result[f"{name}_visibility"] in {"OBSERVED", "PARTIAL"} for name in COMPONENTS)
    result["unknown"] = sum(result[f"{name}_compat"] == "UNKNOWN" for name in COMPONENTS)
    result["conflict"] = sum(result[f"{name}_compat"] == "CONFLICT" for name in COMPONENTS)
    result["coverage"] = round(sum(WEIGHTS[name] * float(result[f"{name}_confidence"]) for name in COMPONENTS if result[f"{name}_compat"] != "UNKNOWN") / sum(WEIGHTS.values()), 6)
    compatibility = sum(float(result[f"{name}_score"]) for name in COMPONENTS)
    result["retrieval"] = round(compatibility * float(result["coverage"]), 6)
    return result


def main() -> int:
    if hashlib.sha256(PROFILE.read_bytes()).hexdigest() != PROFILE_SHA256:
        raise RuntimeError("Immutable target profile hash mismatch.")
    features = json.loads(GEOJSON.read_text(encoding="utf-8"))["features"]
    crops = {path.stem.split("_")[1]: path for path in SOURCE.glob("*_ags_aerial.jpg")}
    if len(features) != 1010 or len(crops) != 1010:
        raise RuntimeError(f"Expected 1010 parcels and crops, got {len(features)} and {len(crops)}.")
    rows = []
    for feature in features:
        property_id = str(feature["properties"]["pie_property_id"])
        if property_id not in crops:
            raise RuntimeError(f"Missing crop for property {property_id}.")
        rows.append(inspect(feature, crops[property_id]))
    rows.sort(key=lambda row: (-float(row["retrieval"]), str(row["propertyid"])))
    for index, row in enumerate(rows, 1):
        row["retrieval_rank"] = index
    fields = ["propertyid", "retrieval_rank", "retrieval", "coverage", "observed", "unknown", "conflict", "crop_sha256"]
    for name in COMPONENTS:
        fields.extend([f"{name}_visibility", f"{name}_binding", f"{name}_compat", f"{name}_confidence", f"{name}_score"])
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "V2_FULL_UNIVERSE_SCORES.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"rows={len(rows)} unknown_rows={sum(row['unknown'] > 0 for row in rows)} hard_conflicts={sum(row['conflict'] > 0 for row in rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
