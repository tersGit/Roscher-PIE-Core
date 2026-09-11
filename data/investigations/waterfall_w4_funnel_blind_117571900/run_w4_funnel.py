#!/usr/bin/env python3
"""Run W4's blind, parcel-bound Funnel v1 retrieval before identity attachment."""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from backend.retrieval_funnel import (
    Candidate,
    EvidenceState,
    FunnelInput,
    PoolObservation,
    RetrievalFunnel,
)

OUT = Path(__file__).resolve().parent
GEOJSON = ROOT / "data" / "estates" / "waterfall_country_estate" / "waterfall_country_estate_w1.geojson"
W1_SHA256 = "6a375bf542bcff28c6a3ee862f9e0c3c9a5395d0497b4159027c40b75cf7be3a"
W1_COMMIT = "e86b156b3f8ac099cd386b9de2b3b2ba609c0635"
SOURCE = Path(
    r"C:\Users\ters\copilot-worktrees\Roscher-PIE-Core\tersgit-probable-winner"
    r"\data\visual_index\waterfall_country_estate_w1\_imagery_cache_native15"
)
STATES = ("pool_geometry", "building", "roof", "house_pool", "solar", "driveway_garage", "open_space", "neighbour_context")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            value.update(block)
    return value.hexdigest()


def parcel_mask(feature: dict, shape: tuple[int, int]) -> np.ndarray:
    height, width = shape
    ring = feature["geometry"]["rings"][0]
    lons = [point[0] for point in ring]
    lats = [point[1] for point in ring]
    pad = 18.0 / 111_320
    min_lon, max_lon = min(lons) - pad, max(lons) + pad
    min_lat, max_lat = min(lats) - pad, max(lats) + pad
    points = np.array(
        [
            [
                round((lon - min_lon) / (max_lon - min_lon) * (width - 1)),
                round((max_lat - lat) / (max_lat - min_lat) * (height - 1)),
            ]
            for lon, lat in ring
        ],
        dtype=np.int32,
    )
    result = np.zeros((height, width), dtype=np.uint8)
    cv2.fillPoly(result, [points], 255)
    return result


def components(mask: np.ndarray, minimum: int) -> list[dict[str, float]]:
    count, labels, stats, centers = cv2.connectedComponentsWithStats(mask, 8)
    found: list[dict[str, float]] = []
    for index in range(1, count):
        area = int(stats[index, cv2.CC_STAT_AREA])
        if area < minimum:
            continue
        region = (labels == index).astype(np.uint8)
        contours, _ = cv2.findContours(region, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue
        contour = max(contours, key=cv2.contourArea)
        width, height = cv2.minAreaRect(contour)[1]
        found.append(
            {
                "area": float(area),
                "cx": float(centers[index][0]),
                "cy": float(centers[index][1]),
                "rectangularity": float(cv2.contourArea(contour) / max(width * height, 1.0)),
                "aspect": max(width, height) / max(min(width, height), 1.0),
            }
        )
    return found


def bound(item: dict[str, float] | None, mask: np.ndarray) -> bool:
    if item is None:
        return False
    x = min(max(round(item["cx"]), 0), mask.shape[1] - 1)
    y = min(max(round(item["cy"]), 0), mask.shape[0] - 1)
    return bool(mask[y, x])


def inspect(feature: dict, crop: Path) -> Candidate:
    image = cv2.imread(str(crop), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"Unreadable W1 crop: {crop}")
    mask = parcel_mask(feature, image.shape[:2])
    inside = mask > 0
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    hue, saturation, value = cv2.split(hsv)
    minimum = max(8, int(inside.sum() * 0.00008))
    visibility = float(np.mean(value[inside] >= 50))

    blue = cv2.inRange(hsv, (78, 40, 35), (116, 255, 255))
    blue = cv2.morphologyEx(blue, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    pool_item = max(
        components(blue, minimum),
        key=lambda item: item["rectangularity"] * min(item["aspect"], 4.0),
        default=None,
    )
    pool_bound = bound(pool_item, mask)
    pool_detected = bool(
        pool_item
        and pool_bound
        and pool_item["rectangularity"] >= 0.55
        and pool_item["aspect"] >= 1.2
    )
    # A detector miss is deliberately not a claim that no pool exists.
    pool = PoolObservation(
        observable=visibility >= 0.60,
        pool_detected=pool_detected,
        parcel_bound=pool_detected,
        clear_absence=False,
        reason="parcel_bound_hsv_rectilinear_observation" if pool_detected else "no_clear_absence_claim",
    )

    green = (hue >= 35) & (hue <= 90) & (saturation >= 35) & (value >= 20)
    roof = ((saturation < 115) & (value > 40) & (value < 220) & ~green).astype(np.uint8) * 255
    roof = cv2.morphologyEx(roof, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    roof_item = max(components(roof, minimum * 3), key=lambda item: item["area"], default=None)
    roof_bound = bound(roof_item, mask)
    roof_fraction = roof_item["area"] / inside.sum() if roof_item else 0.0
    building = EvidenceState.MATCH if roof_bound and roof_fraction >= 0.025 else EvidenceState.UNKNOWN
    roof_state = EvidenceState.PARTIAL if building == EvidenceState.MATCH else EvidenceState.UNKNOWN
    relation = (
        EvidenceState.MATCH
        if pool_detected and building == EvidenceState.MATCH
        else EvidenceState.UNKNOWN
    )
    pool_geometry = (
        EvidenceState.MATCH
        if pool_detected and pool_item and pool_item["aspect"] >= 1.35
        else EvidenceState.PARTIAL
        if pool_detected
        else EvidenceState.UNKNOWN
    )
    hardscape = ((saturation < 70) & (value > 135) & ~green).astype(np.uint8) * 255
    driveway_item = max(components(hardscape, minimum * 2), key=lambda item: item["area"], default=None)
    driveway = EvidenceState.PARTIAL if bound(driveway_item, mask) else EvidenceState.UNKNOWN
    green_fraction = float(np.mean(green[inside]))
    open_space = EvidenceState.PARTIAL if visibility >= 0.60 and green_fraction >= 0.20 else EvidenceState.UNKNOWN

    return Candidate(
        candidate_id=str(feature["properties"]["pie_property_id"]),
        cadastral_area_m2=float(feature["properties"]["area_sqm"]),
        pool=pool,
        pool_geometry=pool_geometry,
        building=building,
        roof=roof_state,
        house_pool=relation,
        solar=EvidenceState.UNKNOWN,
        driveway_garage=driveway,
        open_space=open_space,
        neighbour_context=EvidenceState.UNKNOWN,
    )


def main() -> None:
    if digest(GEOJSON) != W1_SHA256:
        raise RuntimeError("W1 GeoJSON hash mismatch.")
    features = json.loads(GEOJSON.read_text(encoding="utf-8"))["features"]
    crops = {path.stem.split("_")[1]: path for path in SOURCE.glob("*_ags_aerial.jpg")}
    if len(features) != 1010 or len(crops) != 1010:
        raise RuntimeError(f"Expected exactly 1,010 W1 parcels and crops; got {len(features)} and {len(crops)}.")
    candidates = []
    for feature in features:
        candidate_id = str(feature["properties"]["pie_property_id"])
        if candidate_id not in crops:
            raise RuntimeError(f"Missing W1 crop for blind candidate {candidate_id}.")
        candidates.append(inspect(feature, crops[candidate_id]))

    funnel = RetrievalFunnel()
    result = funnel.retrieve(FunnelInput(1251.0, True, True), candidates)
    assessments = {item.candidate.candidate_id: item for item in result.assessments}
    order = list(result.expensive_queue) + list(funnel.recover_tier3(result))
    if len(order) != len(assessments) or len(set(order)) != len(order):
        raise RuntimeError("Funnel order did not retain every candidate exactly once.")
    rank = {candidate_id: index for index, candidate_id in enumerate(order, 1)}
    rows = []
    for candidate_id in order:
        item = assessments[candidate_id]
        evidence = item.candidate
        component_values = {name: getattr(evidence, name).value for name in STATES}
        rows.append(
            {
                "candidate_id": candidate_id,
                "final_rank": rank[candidate_id],
                "tier": item.tier.value,
                "cadastral_area_m2": item.candidate.cadastral_area_m2,
                "absolute_area_difference_m2": item.absolute_area_difference_m2,
                "percent_area_difference": item.percent_area_difference,
                "pool_state": item.pool_state.value,
                "pool_priority": item.pool_priority,
                "coverage": item.evidence_coverage,
                "final_score": item.final_compatibility,
                "stand_size_final_contribution": item.stand_size_final_contribution,
                "support_count": sum(value in {"MATCH", "PARTIAL"} for value in component_values.values()),
                "conflict_count": sum(value == "CONFLICT" for value in component_values.values()),
                "unknown_count": sum(value == "UNKNOWN" for value in component_values.values()),
                **component_values,
            }
        )
    fields = list(rows[0])
    with (OUT / "FULL_EXPERIMENTAL_SCORES.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    with (OUT / "BLIND_RANKING_ORDER.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["final_rank", "candidate_id", "tier", "final_score"])
        writer.writeheader()
        writer.writerows([{field: row[field] for field in writer.fieldnames} for row in rows])

    t1 = [item for item in result.assessments if item.tier.value == "T1"]
    counts = {
        "schema_version": "W4_FUNNEL_V1_STAGE_COUNTS",
        "funnel_implementation_commit": "0e92a524ce4f9f01b9c1573576376e4de8c747b7",
        "w1_universe_commit": W1_COMMIT,
        "w1_geojson_sha256": W1_SHA256,
        "input": {"listing_area_m2": 1251.0, "listing_area_reliable": True, "listing_has_pool": True},
        "stage_counts": result.stage_counts,
        "t1_pool_states": dict(sorted(Counter(item.pool_state.value for item in t1).items())),
        "expansion": {
            "tier2_expanded": bool(result.expansion_reasons),
            "triggers": list(result.expansion_reasons),
            "tier2_count_added": result.stage_counts["T2"] if result.expansion_reasons else 0,
            "tier3_recoverable_count": len(result.recoverable_tier3),
        },
        "progressive_component_order": list(STATES),
        "estimated_expensive_work_reduction": result.estimated_expensive_work_reduction,
        "identity_attachment": "NOT_PERFORMED_AT_BLIND_RANKING_FREEZE",
    }
    (OUT / "FUNNEL_STAGE_COUNTS.json").write_text(json.dumps(counts, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(counts, indent=2))


if __name__ == "__main__":
    main()
