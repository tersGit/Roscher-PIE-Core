#!/usr/bin/env python3
"""G3 estate-scale paired direct-resolution diagnostic for the frozen detector."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "data/investigations/geolis_resolution_audit/phase_g2_2026-09-07"))
from run_phase_g2 import (  # noqa: E402
    EXTENT_M, PAIRS, SERVICE, crop_and_mask, detector_result, export_url, fetch,
    inspect, mercator, overlay, panel,
)

FREEZE = "6c53661e15d1bda968318cbac7cc244ed7497789"
CRITERIA = {
    "centroid_displacement_gt": 0.15,
    "relative_area_ratio_outside": [0.67, 1.5],
    "aspect_ratio_relative_change_gt": 0.33,
    "orientation_delta_deg_gt": 30.0,
    "geometry_family_change": True,
}
FREEZE_FILES = (
    "backend/gis/estate_ags_matching/pool_geometry.py",
    "backend/gis/estate_ags_matching/aerial_geometric.py",
    "backend/gis/estate_ags_matching/pool_object_validation_v1.py",
    "backend/gis/estate_ags_matching/os_scoring_v2.py",
    "backend/gis/estate_ags_matching/os_scoring_v2_multi_image.py",
    "backend/gis/estate_ags_matching/final_candidates.py",
    "backend/gis/estate_ags_matching/listing_pool_gate_v1.py",
    "backend/gis/estate_ags_matching/listing_corner_gate_v1.py",
    "backend/gis/estate_ags_matching/estate_property_inventory_v1.py",
    "backend/gis/dataset_registry.py",
    "data/gis/carlswald_north_corrected_001.json",
    "data/gis/registry.json",
    "data/investigations/object_segmentation_v1/carlswald_north/diagnostic_summary.json",
    "data/investigations/object_segmentation_v1/carlswald_north/estate_summary.json",
)


def blob(path: str) -> str:
    return subprocess.check_output(["git", "ls-tree", "HEAD", "--", path], cwd=ROOT, text=True).split()[2]


def state(result: dict) -> str:
    return result["status"]


def angle_delta(a: float | None, b: float | None) -> float | None:
    if a is None or b is None:
        return None
    delta = abs(a - b) % 180.0
    return min(delta, 180.0 - delta)


def geometry_change(a: dict, b: dict) -> dict:
    reasons, displacement, area_ratio, aspect_change = [], None, None, None
    if not (a["present"] and b["present"]):
        return {"classification": "NOT_APPLICABLE", "reasons": reasons}
    if None not in (a["centroid_x"], a["centroid_y"], b["centroid_x"], b["centroid_y"]):
        displacement = math.hypot(a["centroid_x"] - b["centroid_x"], a["centroid_y"] - b["centroid_y"])
        if displacement > CRITERIA["centroid_displacement_gt"]:
            reasons.append("centroid_displacement")
    if a["relative_area"] and b["relative_area"]:
        area_ratio = b["relative_area"] / a["relative_area"]
        if area_ratio < 0.67 or area_ratio > 1.5:
            reasons.append("relative_area_ratio")
    if a["aspect_ratio"] and b["aspect_ratio"]:
        aspect_change = abs(b["aspect_ratio"] - a["aspect_ratio"]) / a["aspect_ratio"]
        if aspect_change > CRITERIA["aspect_ratio_relative_change_gt"]:
            reasons.append("aspect_ratio_change")
    orientation = angle_delta(a["orientation_deg"], b["orientation_deg"])
    if orientation is not None and orientation > CRITERIA["orientation_delta_deg_gt"]:
        reasons.append("orientation_delta")
    if a["shape_class"] != b["shape_class"]:
        reasons.append("geometry_family_change")
    if reasons:
        classification = "MATERIAL"
    elif any(value not in (None, 0.0) for value in (displacement, area_ratio and abs(area_ratio - 1), aspect_change, orientation)):
        classification = "MINOR"
    else:
        classification = "STABLE"
    return {
        "classification": classification, "reasons": reasons, "centroid_displacement": displacement,
        "relative_area_ratio": area_ratio, "aspect_ratio_relative_change": aspect_change,
        "orientation_delta_deg": orientation, "legacy_family": a["shape_class"], "native_family": b["shape_class"],
    }


def write_csv(name: str, header: list[str], rows: list[list]) -> None:
    with (OUT / name).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def main() -> None:
    if any(path.name != Path(__file__).name for path in OUT.iterdir()):
        raise RuntimeError(f"refusing to overwrite {OUT}")
    inputs, panels = OUT / "inputs", OUT / "panels"
    inputs.mkdir(); panels.mkdir()
    gis = json.loads((ROOT / "data/gis/carlswald_north_corrected_001.json").read_text(encoding="utf-8"))
    eligible = []
    universe_rows = []
    for index, item in enumerate(gis["parcels"]):
        reason = ""
        if item.get("land_type") != "Erven": reason = "excluded_non_erven"
        elif item.get("class") == "non_residential": reason = "excluded_non_residential"
        elif (item.get("area_sqm") or 0) >= 8000: reason = "excluded_large_remainder"
        elif not item.get("geometry") or not item.get("stand_number"): reason = "excluded_missing_geometry_or_stand"
        elif str(item["stand_number"]).startswith("RE/"): reason = "excluded_remainder_stand"
        else: eligible.append((index, item))
        universe_rows.append([index, item.get("stand_number"), item.get("property_id"), "data/gis/carlswald_north_corrected_001.json", json.dumps(item.get("geometry", {}).get("rings", [])[:1]), "PENDING" if not reason else "EXCLUDED", reason])
    last_for_stand = {str(item["stand_number"]).replace("/", "_"): index for index, item in eligible}
    runnable = []
    for row, (index, item) in enumerate(eligible):
        safe = str(item["stand_number"]).replace("/", "_")
        universe_index = next(i for i, values in enumerate(universe_rows) if values[0] == index)
        if last_for_stand[safe] != index:
            universe_rows[universe_index][5:7] = ["EXCLUDED", "duplicate_safe_stand_last_wins"]
        else:
            universe_rows[universe_index][5:7] = ["RUNNABLE", "historical_candidate_rule"]
            runnable.append(item)
    write_csv("PHASE_G3_UNIVERSE.csv", ["gis_row", "stand", "property_id", "geometry_source", "geometry_rings", "status", "reason"], universe_rows)
    pre = {"freeze_commit": FREEZE, "head_before": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "criteria_recorded_before_output_inspection": CRITERIA, "blobs": {path: blob(path) for path in FREEZE_FILES}}
    (OUT / "DETECTOR_FREEZE_MANIFEST_PRE.json").write_text(json.dumps(pre, indent=2), encoding="utf-8")
    records, detector_rows, geometry_rows, review_rows, manifest_rows = [], [], [], [], []
    for number, item in enumerate(runnable, 1):
        stand, prop, geometry = str(item["stand_number"]), item["property_id"], item["geometry"]
        ring = geometry["rings"][0]
        lon = sum(point[0] for point in ring[:-1]) / (len(ring) - 1)
        lat = sum(point[1] for point in ring[:-1]) / (len(ring) - 1)
        x, y = mercator(lon, lat); bbox = (x - EXTENT_M / 2, y - EXTENT_M / 2, x + EXTENT_M / 2, y + EXTENT_M / 2)
        paired = {}
        for profile, pixels in PAIRS:
            url, params = export_url(bbox, pixels)
            try:
                raw = fetch(url); decoded = inspect(raw)
                crop, mask, crop_meta = crop_and_mask(raw, geometry, bbox)
                result = detector_result(crop, mask)
                input_path = inputs / f"{number:03d}_{stand.replace('/', '_')}_{profile}.jpg"
                input_path.write_bytes(crop)
                paired[profile] = {"ok": True, "url": url, "parameters": params, "response_sha256": hashlib.sha256(raw).hexdigest(), "response_bytes": len(raw), **decoded, "gsd": EXTENT_M / decoded["decoded_size_px"][0], "input_path": str(input_path.relative_to(OUT)), "input_sha256": hashlib.sha256(crop).hexdigest(), "crop": crop_meta, "result": result}
            except Exception as exc:
                paired[profile] = {"ok": False, "error": str(exc)}
        valid = all(paired[p]["ok"] for p, _ in PAIRS)
        if valid:
            a, b = paired["legacy_0225"], paired["native15"]
            valid = a["parameters"] | {"size": "DIFFERENT"} == b["parameters"] | {"size": "DIFFERENT"} and a["crop"]["crop_bbox_epsg_3857"] == b["crop"]["crop_bbox_epsg_3857"] and a["decoded_size_px"] == [2000, 2000] and b["decoded_size_px"] == [3000, 3000] and a["result"]["stable"] and b["result"]["stable"]
        change = geometry_change(paired["legacy_0225"]["result"]["run_1"], paired["native15"]["result"]["run_1"]) if valid else {"classification": "INVALID_PAIR", "reasons": ["pair_validation_failed"]}
        if valid and (state(paired["legacy_0225"]["result"]) != state(paired["native15"]["result"]) or change["classification"] == "MATERIAL"):
            left = (OUT / paired["legacy_0225"]["input_path"]).read_bytes(); right = (OUT / paired["native15"]["input_path"]).read_bytes()
            stem = f"{number:03d}_{stand.replace('/', '_')}"
            overlay(left, paired["legacy_0225"]["result"], f"{stand} legacy_0225", panels / f"{stem}_legacy_overlay.jpg")
            overlay(right, paired["native15"]["result"], f"{stand} native15", panels / f"{stem}_native_overlay.jpg")
            panel(left, right, "LEGACY 0.225", "NATIVE15 0.15", panels / f"{stem}_AB.jpg")
            review_rows.append([stand, prop, change["classification"], "AMBIGUOUS", "Automated paired source/overlay panel emitted; no ground-truth or detector-output tuning used.", ";".join(change["reasons"]), "panels/" + stem + "_AB.jpg"])
        for profile, rec in paired.items():
            if rec["ok"]:
                fp = rec["result"]["run_1"]
                detector_rows.append([stand, prop, profile, valid, rec["result"]["status"], fp["present"], fp["unknown"], rec["result"]["contour_point_count"], fp["relative_area"], fp["centroid_x"], fp["centroid_y"], fp["aspect_ratio"], fp["orientation_deg"], fp["shape_class"], rec["result"]["detector_score_or_confidence"], rec["result"]["semantic_score"], rec["result"]["rejection_reason"], rec["result"]["stable"]])
                manifest_rows.append([stand, prop, profile, rec["url"], json.dumps(rec["parameters"], sort_keys=True), json.dumps(bbox), rec["response_sha256"], rec["response_bytes"], rec["decoded_size_px"][0], rec["decoded_size_px"][1], rec["gsd"], rec["input_sha256"], rec["input_path"]])
        geometry_rows.append([stand, prop, valid, change["classification"], ";".join(change["reasons"]), change.get("centroid_displacement"), change.get("relative_area_ratio"), change.get("aspect_ratio_relative_change"), change.get("orientation_delta_deg"), change.get("legacy_family"), change.get("native_family")])
        records.append({"stand": stand, "property_id": prop, "valid": valid, "pair": paired, "geometry": change})
        print(f"[{number}/{len(runnable)}] {stand} valid={valid} geometry={change['classification']}", flush=True)
    write_csv("PHASE_G3_DETECTOR_AB.csv", ["stand", "property_id", "profile", "pair_valid", "status", "present", "unknown", "contour_points", "relative_area", "centroid_x", "centroid_y", "aspect_ratio", "orientation_deg", "family", "detector_confidence", "semantic_score", "rejection_reason", "repeat_stable"], detector_rows)
    write_csv("PHASE_G3_GEOMETRY_CHANGES.csv", ["stand", "property_id", "pair_valid", "classification", "material_reasons", "centroid_displacement", "relative_area_ratio", "aspect_relative_change", "orientation_delta_deg", "legacy_family", "native_family"], geometry_rows)
    write_csv("PHASE_G3_MANUAL_REVIEW.csv", ["stand", "property_id", "geometry_classification", "manual_label", "visual_reason", "observed_root_cause", "panel"], review_rows)
    write_csv("request_source_manifest.csv", ["stand", "property_id", "profile", "request_url", "parameters", "bbox_epsg_3857", "response_sha256", "response_bytes", "decoded_width", "decoded_height", "gsd_m_per_px", "detector_input_sha256", "detector_input_path"], manifest_rows)
    combinations = [(left, right) for left in ("PRESENT", "ABSENT", "UNKNOWN") for right in ("PRESENT", "ABSENT", "UNKNOWN")]
    counts = Counter((state(record["pair"]["legacy_0225"]["result"]), state(record["pair"]["native15"]["result"])) for record in records if record["valid"])
    valid_count = sum(record["valid"] for record in records)
    write_csv("PHASE_G3_TRANSITIONS.csv", ["legacy_0225_status", "native15_status", "count", "percentage_of_valid"], [[a, b, counts[(a, b)], round(100 * counts[(a, b)] / max(valid_count, 1), 4)] for a, b in combinations])
    (OUT / "results.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
    post = {**pre, "head_after": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "blobs_after": {path: blob(path) for path in FREEZE_FILES}, "all_blobs_unchanged": all(blob(path) == value for path, value in pre["blobs"].items())}
    (OUT / "DETECTOR_FREEZE_MANIFEST_POST.json").write_text(json.dumps(post, indent=2), encoding="utf-8")
    summary = Counter(row[3] for row in geometry_rows)
    report = f"""# Phase G3: Freeze-compatible estate-scale A/B

## Verdict

**Estate validity: {'CLEAN' if valid_count == len(runnable) else 'PARTIAL'}.** Frozen candidate rows: {len(eligible)}; deduplicated runnable parcels: {len(runnable)}; valid pairs: {valid_count}. The direct paired protocol is identical to G2 except that it is applied estate-wide.

**Detection effect:** see the complete nine-cell matrix in `PHASE_G3_TRANSITIONS.csv`. **Geometry effect:** {summary['MATERIAL']} material, {summary['MINOR']} minor, and {summary['STABLE']} stable PRESENT-to-PRESENT comparisons under criteria fixed before output inspection.

## Required answers

1. Universe: `PHASE_G3_UNIVERSE.csv` gives every frozen GIS row, filter, duplicate, and runnable reason.
2. Deduplication uses the historical safe-stand filename last-wins rule.
3. Each pair uses one identical 450 m EPSG:3857 extent at 2000 and 3000 pixels.
4. Service, JPEG, bilinear interpolation, CRS, crop and mask preprocessing are invariant; request hashes are in `request_source_manifest.csv`.
5. The exact frozen detector ran twice per valid image; repeat stability is in `PHASE_G3_DETECTOR_AB.csv`.
6. No detector score, semantic score, rejection reason, or candidate count is emitted by the frozen blob; null values are recorded rather than invented.
7. All nine PRESENT/ABSENT/UNKNOWN transitions are listed, including zero counts.
8. Materiality criteria were fixed before the run in `DETECTOR_FREEZE_MANIFEST_PRE.json`.
9. Stand 365 is classified by those fixed criteria in `PHASE_G3_GEOMETRY_CHANGES.csv`.
10. Source/overlay panels exist for every transition and material geometry case; review labels are neutral `AMBIGUOUS` without ground truth.
11. Root-cause fields only name triggered measurable criteria; no detector retuning occurred.
12. G2 controls 677, 420, and 408 remain in the estate output but are unweighted in interpretation.
13. No historical-byte equality is claimed for current live AGS.
14. Recommendation: retain this result as detector-only diagnostic evidence; do not rerank or alter frozen behavior without a separately authorized decision.
"""
    (OUT / "PHASE_G3_REPORT.md").write_text(report, encoding="utf-8")


if __name__ == "__main__":
    main()
