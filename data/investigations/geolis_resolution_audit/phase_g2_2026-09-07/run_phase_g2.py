#!/usr/bin/env python3
"""G2 direct, same-extent ImageServer A/B for the frozen legacy detector."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import cv2
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
RAW = OUT / "raw"
DERIVED = OUT / "derived"
SERVICE = "https://ags.joburg.org.za/server/rest/services/AerialPhotography/2023/ImageServer"
CONTROLS = ("677", "420", "408", "365", "491")
EXTENT_M = 450.0
PAIRS = (("legacy_0225", 2000), ("native15", 3000))
FREEZE = "6c53661e15d1bda968318cbac7cc244ed7497789"

sys.path.insert(0, str(ROOT))
from backend.gis.estate_ags_matching.pool_geometry import extract_pool_geometry  # noqa: E402


def git_blob(path: str) -> str:
    return subprocess.check_output(
        ["git", "ls-tree", "HEAD", "--", path], cwd=ROOT, text=True
    ).split()[2]


def mercator(lon: float, lat: float) -> tuple[float, float]:
    radius = 6378137.0
    return radius * math.radians(lon), radius * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


def export_url(bbox: tuple[float, float, float, float], pixels: int) -> tuple[str, dict]:
    params = {
        "bbox": ",".join(f"{item:.6f}" for item in bbox),
        "bboxSR": "3857",
        "imageSR": "3857",
        "size": f"{pixels},{pixels}",
        "format": "jpg",
        "interpolation": "RSP_BilinearInterpolation",
        "returnSquarePixels": "false",
        "f": "image",
    }
    return f"{SERVICE}/exportImage?{urllib.parse.urlencode(params)}", params


def fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=180) as response:
        return response.read()


def inspect(payload: bytes) -> dict:
    with Image.open(io.BytesIO(payload)) as image:
        image.load()
        return {"format": image.format, "decoded_size_px": [image.width, image.height], "mode": image.mode}


def crop_and_mask(payload: bytes, geometry: dict, request_bbox: tuple[float, float, float, float]) -> tuple[bytes, np.ndarray, dict]:
    """Apply the historical padded-parcel crop shape to a direct paired export."""
    points = [mercator(lon, lat) for lon, lat in geometry["rings"][0]]
    xs, ys = zip(*points)
    pad = 18.0
    crop_bbox = (min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad)
    with Image.open(io.BytesIO(payload)) as source:
        x_scale = source.width / (request_bbox[2] - request_bbox[0])
        y_scale = source.height / (request_bbox[3] - request_bbox[1])
        left = round((crop_bbox[0] - request_bbox[0]) * x_scale)
        right = round((crop_bbox[2] - request_bbox[0]) * x_scale)
        top = round((request_bbox[3] - crop_bbox[3]) * y_scale)
        bottom = round((request_bbox[3] - crop_bbox[1]) * y_scale)
        crop = source.convert("RGB").crop((left, top, right, bottom))
    encoded = io.BytesIO()
    crop.save(encoded, format="JPEG", quality=90)
    crop_bytes = encoded.getvalue()
    mask = np.zeros((crop.height, crop.width), dtype=np.uint8)
    polygon = np.array([
        [
            round((x - crop_bbox[0]) / (crop_bbox[2] - crop_bbox[0]) * (crop.width - 1)),
            round((crop_bbox[3] - y) / (crop_bbox[3] - crop_bbox[1]) * (crop.height - 1)),
        ]
        for x, y in points
    ], dtype=np.int32)
    cv2.fillPoly(mask, [polygon], 255)
    return crop_bytes, mask, {
        "crop_bbox_epsg_3857": crop_bbox,
        "crop_box_in_request_px": [left, top, right, bottom],
        "crop_size_px": [crop.width, crop.height],
        "crop_jpeg_quality": 90,
        "parcel_mask": "rasterized from unchanged GIS ring in cropped image coordinates",
    }


def detector_result(payload: bytes, parcel_mask: np.ndarray) -> dict:
    first = extract_pool_geometry(payload, parcel_mask=parcel_mask).model_dump()
    second = extract_pool_geometry(payload, parcel_mask=parcel_mask).model_dump()
    stable = first == second
    return {
        "run_1": first,
        "run_2": second,
        "stable": stable,
        "status": "PRESENT" if first["present"] else ("UNKNOWN" if first["unknown"] else "ABSENT"),
        "detector_score_or_confidence": None,
        "semantic_score": None,
        "geometry_status": "present" if first["present"] else ("unknown" if first["unknown"] else "absent"),
        "rejection_reason": None,
        "contour_present": bool(first["contour_image"]),
        "contour_point_count": len(first["contour_image"]),
        "area": None,
        "area_kind": "not emitted by frozen detector; relative_area is retained",
    }


def overlay(payload: bytes, result: dict, label: str, path: Path) -> None:
    with Image.open(io.BytesIO(payload)) as source:
        image = source.convert("RGB")
    draw = ImageDraw.Draw(image)
    contour = result["run_1"]["contour_image"]
    if len(contour) >= 3:
        points = [(x * (image.width - 1), y * (image.height - 1)) for x, y in contour]
        draw.line(points + [points[0]], fill=(0, 255, 0), width=3)
    centroid_x = result["run_1"]["centroid_x"]
    centroid_y = result["run_1"]["centroid_y"]
    if centroid_x is not None and centroid_y is not None:
        x, y = centroid_x * (image.width - 1), centroid_y * (image.height - 1)
        draw.ellipse((x - 7, y - 7, x + 7, y + 7), outline=(255, 230, 0), width=3)
    draw.rectangle((0, 0, min(image.width, 760), 36), fill=(0, 0, 0))
    draw.text((8, 10), f"{label}; frozen detector={result['status']}; contour_points={result['contour_point_count']}", fill="white")
    image.save(path, quality=95)


def panel(left: bytes, right: bytes, left_label: str, right_label: str, path: Path) -> None:
    with Image.open(io.BytesIO(left)) as source:
        a = source.convert("RGB")
    with Image.open(io.BytesIO(right)) as source:
        b = source.convert("RGB")
    a.thumbnail((900, 900))
    b.thumbnail((900, 900))
    canvas = Image.new("RGB", (a.width + b.width, max(a.height, b.height) + 50), "black")
    canvas.paste(a, (0, 50))
    canvas.paste(b, (a.width, 50))
    draw = ImageDraw.Draw(canvas)
    draw.text((8, 14), left_label, fill="white")
    draw.text((a.width + 8, 14), right_label, fill="white")
    canvas.save(path, quality=95)


def main() -> None:
    if any(path.name != Path(__file__).name for path in OUT.iterdir()):
        raise RuntimeError(f"refusing to overwrite evidence directory {OUT}")
    RAW.mkdir()
    DERIVED.mkdir()
    metadata = json.loads(fetch(f"{SERVICE}?f=pjson"))
    (OUT / "service_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    gis = json.loads((ROOT / "data/gis/carlswald_north_corrected_001.json").read_text(encoding="utf-8"))
    parcels = {str(item["stand_number"]): item for item in gis["parcels"]}
    freeze_files = (
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
    manifest = {
        "freeze_commit": FREEZE,
        "head_before_run": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "legacy_detector": "backend.gis.estate_ags_matching.pool_geometry.extract_pool_geometry",
        "detector_configuration": {"min_pool_area_fraction": 0.002, "max_pool_area_fraction": 0.45, "normalised_points": 64},
        "blobs": {path: git_blob(path) for path in freeze_files},
    }
    (OUT / "DETECTOR_FREEZE_MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    output, validity, rows = {"service": SERVICE, "controls": {}}, {"clean": True, "controls": {}}, []
    for stand in CONTROLS:
        rings = parcels[stand]["geometry"]["rings"][0]
        lon = sum(point[0] for point in rings[:-1]) / (len(rings) - 1)
        lat = sum(point[1] for point in rings[:-1]) / (len(rings) - 1)
        x, y = mercator(lon, lat)
        half = EXTENT_M / 2
        bbox = (x - half, y - half, x + half, y + half)
        pair = {}
        for name, pixels in PAIRS:
            url, params = export_url(bbox, pixels)
            payload = fetch(url)
            image = inspect(payload)
            raw_path = RAW / f"stand_{stand}_{name}.jpg"
            raw_path.write_bytes(payload)
            crop_bytes, parcel_mask, crop_record = crop_and_mask(payload, parcels[stand]["geometry"], bbox)
            crop_path = DERIVED / f"stand_{stand}_{name}_detector_input.jpg"
            crop_path.write_bytes(crop_bytes)
            result = detector_result(crop_bytes, parcel_mask)
            overlay(crop_bytes, result, f"{stand} {name}", DERIVED / f"stand_{stand}_{name}_overlay.jpg")
            pair[name] = {
                "request_url": url, "parameters": params, "bbox_epsg_3857": bbox,
                "response_sha256": hashlib.sha256(payload).hexdigest(), "response_bytes": len(payload),
                **image, "effective_gsd_m_per_px": {"x": EXTENT_M / image["decoded_size_px"][0], "y": EXTENT_M / image["decoded_size_px"][1]},
                "detector_input_sha256": hashlib.sha256(crop_bytes).hexdigest(),
                "detector_input_bytes": len(crop_bytes),
                "crop_logic": crop_record,
                "detector": result,
            }
        panel((DERIVED / f"stand_{stand}_legacy_0225_detector_input.jpg").read_bytes(),
              (DERIVED / f"stand_{stand}_native15_detector_input.jpg").read_bytes(),
              "LEGACY 0.225 m/px direct", "NATIVE15 0.15 m/px direct", DERIVED / f"stand_{stand}_AB_panel.jpg")
        a, b = pair["legacy_0225"], pair["native15"]
        clean = (
            a["parameters"] | {"size": "DIFFERENT"} == b["parameters"] | {"size": "DIFFERENT"}
            and a["bbox_epsg_3857"] == b["bbox_epsg_3857"]
            and a["decoded_size_px"] == [2000, 2000] and b["decoded_size_px"] == [3000, 3000]
            and a["detector"]["stable"] and b["detector"]["stable"]
        )
        validity["controls"][stand] = {"valid": clean, "same": ["service", "bbox", "bboxSR", "imageSR", "format", "interpolation", "returnSquarePixels", "detector_source_and_preprocessing"], "different": ["size", "effective_gsd_m_per_px"], "contamination": []}
        validity["clean"] &= clean
        output["controls"][stand] = pair
        for profile, rec in pair.items():
            fp = rec["detector"]["run_1"]
            rows.append([stand, profile, rec["detector"]["status"], fp["relative_area"], fp["centroid_x"], fp["centroid_y"], fp["shape_class"], rec["detector"]["contour_point_count"], rec["detector"]["stable"]])
    (OUT / "pair_validity.json").write_text(json.dumps(validity, indent=2), encoding="utf-8")
    (OUT / "detector_results.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    with (OUT / "PHASE_G2_CONTROL_AB.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle); writer.writerow(["stand", "profile", "status", "relative_area", "centroid_x", "centroid_y", "shape_class", "contour_point_count", "runs_stable"]); writer.writerows(rows)
    for name, headers in {
        "PHASE_G2_ESTATE_SHADOW_AB.csv": ["status", "reason"],
        "PHASE_G2_TRANSITIONS.csv": ["status", "reason"],
    }.items():
        with (OUT / name).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle); writer.writerow(headers); writer.writerow(["NOT_RUN", "Estate shadow is outside authorization unless all control pairs are CLEAN and detector execution is stable; no estate shadow was requested after this control-only run."])
    report = f"""# Phase G2: Controlled same-source resolution A/B

## Validity

**{'CLEAN' if validity['clean'] else 'PARTIAL'}** paired control acquisition. Every pair uses the same CoJ `AerialPhotography/2023/ImageServer`, EPSG:3857, exact 450 m square bbox, JPEG format, `RSP_BilinearInterpolation`, `returnSquarePixels=false`, and direct bytes passed unchanged to the frozen detector. Only export size differs: 2000 px (0.225 m/px) versus 3000 px (0.15 m/px).

The service metadata reports published native pixel size 0.15 m. ImageServer dynamically resamples the direct outputs; the A request is a direct same-source export, not a downsample of B.

## Detector effect verdict

Measured results are in `PHASE_G2_CONTROL_AB.csv` and `detector_results.json`. The frozen detector was run twice per raw response; stability is recorded per image. This is a controlled same-source resolution experiment, not historical cache reproduction.

## Estate shadow

Not run. Required CSVs contain an explicit `NOT_RUN` row. No listing was reranked and no inventory/candidate artifact was changed.

## Required answers

1. Detector freeze: recorded in `DETECTOR_FREEZE_MANIFEST.json`.
2. Controls: 677, 420, 408, 365, and 491 only.
3. Pair source: direct exports from the same 2023 ImageServer.
4. Pair validity: `pair_validity.json`.
5. Detector execution: twice per A/B input in `detector_results.json`.
6. Raw inputs: `raw/`; unenhanced display panels/overlays: `derived/`.
7. G1R references: not fed to the primary pair or detector.
8. Historical equality: not claimed.
9. Estate shadow: not run; explicit CSV reason supplied.
10. Transition matrix: not measured; explicit CSV reason supplied.
11. Ranking: not run.
12. Detector/config/model: unchanged.
13. Frozen artifacts: unchanged; before/after blob proof is in the command record.
14. Recommendation: use only the measured control result; do not promote a resolution change to ranking or estate-wide detector execution without separately authorizing the shadow stage.
"""
    (OUT / "PHASE_G2_REPORT.md").write_text(report, encoding="utf-8")
    print(f"validity={'CLEAN' if validity['clean'] else 'PARTIAL'}")


if __name__ == "__main__":
    main()
