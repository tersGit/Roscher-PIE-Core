#!/usr/bin/env python3
"""Reproducible, read-only diagnostic audit of frozen Waterfall W4 Funnel v1."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import platform
import sys
import time
from collections import Counter
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
W4 = OUT.parent
GEOJSON = ROOT / "data" / "estates" / "waterfall_country_estate" / "waterfall_country_estate_w1.geojson"
SCORES = W4 / "FULL_EXPERIMENTAL_SCORES.csv"
COUNTS = W4 / "FUNNEL_STAGE_COUNTS.json"
LISTING_PROFILE = W4 / "LISTING_PROFILE.md"
CACHE = Path(
    r"C:\Users\ters\copilot-worktrees\Roscher-PIE-Core\tersgit-probable-winner"
    r"\data\visual_index\waterfall_country_estate_w1\_imagery_cache_native15"
)
EXPECTED_GEOJSON_SHA = "6a375bf542bcff28c6a3ee862f9e0c3c9a5395d0497b4159027c40b75cf7be3a"
EXPECTED_CACHE_MANIFEST_SHA = "b732dd96eddb3104cc69c7716d6e80498b39de08ec0b59b3f89f90aed99b377e"


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def pct(numerator: int, denominator: int) -> float:
    return round(100.0 * numerator / denominator, 3) if denominator else 0.0


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


def crop_index() -> dict[str, Path]:
    result = {}
    for path in CACHE.glob("*_ags_aerial.jpg"):
        result[path.stem.split("_")[1]] = path
    return result


def stable_samples(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Select before opening crops using only frozen score fields and an ID hash."""
    selected = []
    for state in ("UNKNOWN", "OBSERVED_POOL"):
        group = [r for r in rows if r["tier"] == "T1" and r["pool_state"] == state]
        ordered = sorted(
            group,
            key=lambda r: (
                -float(r["final_score"]),
                int(r["final_rank"]),
                hashlib.sha256(("W4-efficiency-v1|" + r["candidate_id"]).encode()).hexdigest(),
            ),
        )
        for ordinal, row in enumerate(ordered[:20], 1):
            selected.append(
                {
                    "sample_group": f"T1_{state}",
                    "sample_ordinal": ordinal,
                    "candidate_id": row["candidate_id"],
                    "final_rank": row["final_rank"],
                    "final_score": row["final_score"],
                    "selection_hash": hashlib.sha256(
                        ("W4-efficiency-v1|" + row["candidate_id"]).encode()
                    ).hexdigest(),
                }
            )
    return selected


def classify_boundaries(features: dict[str, dict], crops: dict[str, Path]) -> list[dict[str, object]]:
    rows = []
    for candidate_id, feature in features.items():
        image = cv2.imread(str(crops[candidate_id]), cv2.IMREAD_COLOR)
        mask = parcel_mask(feature, image.shape[:2])
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        hue, sat, val = cv2.split(hsv)
        green = ((hue >= 35) & (hue <= 90) & (sat >= 35) & (val >= 20)).astype(np.uint8)
        outer = cv2.dilate(mask, np.ones((35, 35), np.uint8)) > 0
        ring = outer & ~(mask > 0)
        # A long open exterior edge must be vegetation-dominant. This is a structural
        # cue only, not a claim of water, greenbelt ownership, or target identity.
        exterior_green = float(green[ring].mean()) if ring.any() else 0.0
        boundary = cv2.morphologyEx(mask, cv2.MORPH_GRADIENT, np.ones((19, 19), np.uint8)) > 0
        boundary_green = float(green[boundary].mean()) if boundary.any() else 0.0
        if exterior_green >= 0.72 and boundary_green >= 0.62:
            label = "OPEN_BOUNDARY_LIKELY"
        elif exterior_green <= 0.32 and boundary_green <= 0.32:
            label = "INTERNAL_RESIDENTIAL"
        else:
            label = "AMBIGUOUS"
        rows.append(
            {
                "candidate_id": candidate_id,
                "open_boundary_class": label,
                "outside_green_fraction": round(exterior_green, 5),
                "boundary_green_fraction": round(boundary_green, 5),
            }
        )
    return rows


def classify_solar_and_driveway(features: dict[str, dict], crops: dict[str, Path]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    solar_rows, garage_rows = [], []
    for candidate_id, feature in features.items():
        image = cv2.imread(str(crops[candidate_id]), cv2.IMREAD_COLOR)
        mask = parcel_mask(feature, image.shape[:2]) > 0
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        hue, sat, val = cv2.split(hsv)
        green = (hue >= 35) & (hue <= 90) & (sat >= 35) & (val >= 20)
        # Native15 resolves a typical panel's short dimension to about seven pixels,
        # but roof orientation, shade, and compression preclude a reliable panel-count
        # detector here. No candidate is promoted from this proxy.
        dark_roof = mask & ~green & (sat < 115) & (val > 35) & (val < 150)
        roof_visible_fraction = float(dark_roof.sum() / max(mask.sum(), 1))
        solar_rows.append(
            {
                "candidate_id": candidate_id,
                "solar_class": "SOLAR_UNKNOWN",
                "roof_visible_fraction": round(roof_visible_fraction, 5),
                "method_note": "No validated parcel-bound panel detector; no positive or negative solar assertion.",
            }
        )
        hardscape = mask & ~green & (sat < 70) & (val > 135)
        hardscape_fraction = float(hardscape.sum() / max(mask.sum(), 1))
        # A crop does not provide defensible road orientation or bay separations.
        # Only unusually broad paved frontage is exposed as a non-garage-specific cue.
        garage_class = "BROAD_FRONTAGE" if hardscape_fraction >= 0.24 else "UNKNOWN"
        garage_rows.append(
            {
                "candidate_id": candidate_id,
                "driveway_garage_class": garage_class,
                "hardscape_fraction": round(hardscape_fraction, 5),
                "method_note": "No 3+ garage claim: roof imagery cannot reliably separate garage bays.",
            }
        )
    return solar_rows, garage_rows


def write_csv(name: str, rows: list[dict[str, object]]) -> None:
    with (OUT / name).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else [])
        writer.writeheader()
        writer.writerows(rows)


def retained(current: list[str], feature: dict[str, str], positives: set[str], negative: set[str]) -> tuple[list[str], int]:
    next_ids = [candidate_id for candidate_id in current if feature[candidate_id] not in negative]
    unknowns = sum(feature[candidate_id] not in positives | negative for candidate_id in current)
    return next_ids, unknowns


def strategy_rows(rows: list[dict[str, str]], boundary: dict[str, str], solar: dict[str, str], garage: dict[str, str]) -> list[dict[str, object]]:
    all_ids = [r["candidate_id"] for r in rows]
    area5 = [r["candidate_id"] for r in rows if float(r["percent_area_difference"]) <= 0.05]
    area10 = [r["candidate_id"] for r in rows if float(r["percent_area_difference"]) <= 0.10]
    pool = {r["candidate_id"]: r["pool_state"] for r in rows}
    definitions = {
        "A": [("area_10", area10), ("pool", None)],
        "B": [("area_5_priority", area5), ("pool", None), ("area_10_fallback", area10)],
        "C": [("area_10", area10), ("open_boundary", None), ("pool", None)],
        "D": [("area_10", area10), ("pool", None), ("solar", None), ("open_boundary", None)],
        "E": [("area_5_priority", area5), ("pool", None), ("open_boundary", None), ("solar", None), ("area_10_fallback", area10)],
    }
    output = []
    for strategy, stages in definitions.items():
        current: list[str] = []
        for index, (stage, ids) in enumerate(stages, 1):
            if stage.startswith("area"):
                if stage == "area_10" or stage == "area_5_priority":
                    current = list(ids)
                else:
                    current = list(dict.fromkeys(current + ids))
                unknown_survival = 0
            elif stage == "pool":
                current, unknown_survival = retained(current, pool, {"OBSERVED_POOL"}, {"OBSERVED_NO_POOL"})
            elif stage == "open_boundary":
                current, unknown_survival = retained(current, boundary, {"OPEN_BOUNDARY_LIKELY"}, {"INTERNAL_RESIDENTIAL"})
            elif stage == "solar":
                # NONE is intentionally retained: image vintage may pre-date installation.
                current, unknown_survival = retained(current, solar, {"SOLAR_OBSERVED_STRONG", "SOLAR_OBSERVED_SOME"}, set())
            else:
                raise ValueError(stage)
            output.append(
                {
                    "strategy": strategy,
                    "stage_number": index,
                    "stage": stage,
                    "retained_count": len(current),
                    "unknown_survival_at_stage": unknown_survival,
                    "expensive_building_fine_count": len(current),
                    "reduction_from_universe_pct": pct(len(all_ids) - len(current), len(all_ids)),
                }
            )
    return output


def main() -> None:
    started = time.perf_counter()
    if sha256(GEOJSON) != EXPECTED_GEOJSON_SHA:
        raise RuntimeError("Frozen W1 GeoJSON hash mismatch.")
    cache_manifest = CACHE.parents[2] / "cache" / "ags_native15" / "waterfall_country_estate_w1" / "manifest.json"
    if not CACHE.is_dir() or sha256(cache_manifest) != EXPECTED_CACHE_MANIFEST_SHA:
        raise RuntimeError("Recovered native15 cache is unavailable or does not match its frozen manifest.")
    features = {
        str(feature["properties"]["pie_property_id"]): feature
        for feature in json.loads(GEOJSON.read_text(encoding="utf-8"))["features"]
    }
    crops = crop_index()
    if len(features) != 1010 or len(crops) != 1010 or set(features) != set(crops):
        raise RuntimeError("Expected exactly 1,010 matching frozen parcels and read-only crops.")
    with SCORES.open(encoding="utf-8", newline="") as handle:
        scores = list(csv.DictReader(handle))
    if len(scores) != 1010:
        raise RuntimeError("Frozen score row count is not 1,010.")
    samples = stable_samples(scores)
    write_csv("pool_blinded_sample_selection.csv", samples)
    # The numbered panels preserve the pre-image selection order; candidate IDs are
    # omitted from the panel so the visual label can be applied without identity cues.
    panels = []
    for sample in samples:
        image = cv2.imread(str(crops[sample["candidate_id"]]), cv2.IMREAD_COLOR)
        image = cv2.resize(image, (225, 225), interpolation=cv2.INTER_AREA)
        cv2.putText(
            image,
            f'{sample["sample_group"]} #{sample["sample_ordinal"]:02d}',
            (5, 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
        panels.append(image)
    contact = np.full((5 * 225, 8 * 225, 3), 255, dtype=np.uint8)
    for index, image in enumerate(panels):
        y, x = divmod(index, 8)
        contact[y * 225 : (y + 1) * 225, x * 225 : (x + 1) * 225] = image
    cv2.imwrite(str(OUT / "pool_blinded_sample_contact_sheet.jpg"), contact)

    feature_started = time.perf_counter()
    boundary_rows = classify_boundaries(features, crops)
    boundary_seconds = time.perf_counter() - feature_started
    feature_started = time.perf_counter()
    solar_rows, garage_rows = classify_solar_and_driveway(features, crops)
    solar_garage_seconds = time.perf_counter() - feature_started
    write_csv("boundary_classes.csv", boundary_rows)
    write_csv("solar_classes.csv", solar_rows)
    write_csv("driveway_garage_classes.csv", garage_rows)
    boundary = {r["candidate_id"]: r["open_boundary_class"] for r in boundary_rows}
    solar = {r["candidate_id"]: r["solar_class"] for r in solar_rows}
    garage = {r["candidate_id"]: r["driveway_garage_class"] for r in garage_rows}
    workload = strategy_rows(scores, boundary, solar, garage)
    write_csv("counterfactual_workloads.csv", workload)

    area_rows = []
    for tolerance in (0, 2.5, 5, 7.5, 10, 12.5, 15, 20):
        lower, upper = 1251 * (1 - tolerance / 100), 1251 * (1 + tolerance / 100)
        count = sum(lower <= float(r["cadastral_area_m2"]) <= upper for r in scores)
        area_rows.append({"band": "exact" if tolerance == 0 else f"+/-{tolerance:g}%", "lower_m2": lower, "upper_m2": upper, "count": count, "pct_universe": pct(count, len(scores))})
    write_csv("area_band_distribution.csv", area_rows)
    histogram = Counter(int(float(r["cadastral_area_m2"]) // 100 * 100) for r in scores)
    write_csv("area_histogram_100m2.csv", [{"lower_m2": key, "upper_m2": key + 99.999, "count": histogram[key], "pct_universe": pct(histogram[key], len(scores))} for key in sorted(histogram)])

    selection_map = {r["candidate_id"]: r for r in samples}
    # Manual classifications are a deliberately conservative visual audit of the original
    # native15 crops. They are keyed by reproducibly selected blind parcel IDs only.
    visual_labels = {
        "2033239": "D_AMBIGUOUS",
        "2033192": "B_GARDEN_VISIBLE_NO_POOL_APPARENT",
        "2033129": "B_GARDEN_VISIBLE_NO_POOL_APPARENT",
        "2033307": "C_DETECTOR_MISSED_APPARENT_POOL",
        "2033122": "A_GENUINELY_NOT_ASSESSABLE",
        "2033379": "C_DETECTOR_MISSED_APPARENT_POOL",
        "2033385": "B_GARDEN_VISIBLE_NO_POOL_APPARENT",
        "2033155": "B_GARDEN_VISIBLE_NO_POOL_APPARENT",
        "2033157": "D_AMBIGUOUS",
        "2033159": "C_DETECTOR_MISSED_APPARENT_POOL",
        "2032873": "C_DETECTOR_MISSED_APPARENT_POOL",
        "2032875": "C_DETECTOR_MISSED_APPARENT_POOL",
        "2033367": "C_DETECTOR_MISSED_APPARENT_POOL",
        "2033376": "D_AMBIGUOUS",
        "2033034": "B_GARDEN_VISIBLE_NO_POOL_APPARENT",
        "2033018": "C_DETECTOR_MISSED_APPARENT_POOL",
        "2033020": "C_DETECTOR_MISSED_APPARENT_POOL",
        "2033023": "B_GARDEN_VISIBLE_NO_POOL_APPARENT",
        "2033024": "B_GARDEN_VISIBLE_NO_POOL_APPARENT",
        "2032942": "D_AMBIGUOUS",
    }
    review_rows = []
    for candidate_id, sample in selection_map.items():
        label = visual_labels.get(candidate_id, "CONTROL_NOT_CLASSIFIED")
        review_rows.append({**sample, "visual_pool_review": label, "crop_sha256": sha256(crops[candidate_id])})
    write_csv("pool_blinded_visual_review.csv", review_rows)

    counts = json.loads(COUNTS.read_text(encoding="utf-8"))
    provenance = {
        "schema_version": "W4_FUNNEL_V1_RETRIEVAL_EFFICIENCY_AUDIT",
        "frozen_listing_commit": "299607debe45b9c0dcb2f2c4e5db14321e79de5a",
        "frozen_prediction_commit": "878547e958d4185223d74e46b72c70f8efa8f23e",
        "frozen_final_evaluation_commit": "756b261",
        "source_hashes": {
            "w1_geojson_sha256": sha256(GEOJSON),
            "w1_native15_manifest_sha256": sha256(cache_manifest),
            "frozen_scores_sha256": sha256(SCORES),
            "frozen_stage_counts_sha256": sha256(COUNTS),
            "frozen_listing_profile_sha256": sha256(LISTING_PROFILE),
        },
        "source_access": "Recovered W1 native15 cache read-only; no imagery fetched; no identity lookup or ground-truth work.",
        "frozen_baseline": counts,
        "sample_selection": "Within each T1 pool state, sort descending frozen final_score, ascending frozen final_rank, then SHA-256('W4-efficiency-v1|' + candidate_id); select first 20 before opening crops.",
        "runtime_seconds": round(time.perf_counter() - started, 3),
        "timing_seconds": {
            "boundary_proxy": round(boundary_seconds, 3),
            "solar_and_driveway_proxy": round(solar_garage_seconds, 3),
        },
        "environment": {"python": sys.version, "opencv": cv2.__version__, "platform": platform.platform(), "cpu_count": os.cpu_count()},
    }
    (OUT / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    (OUT / "validation.json").write_text(json.dumps({"parcel_count": len(features), "crop_count": len(crops), "score_count": len(scores), "sample_count": len(samples), "all_totals_valid": True}, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
