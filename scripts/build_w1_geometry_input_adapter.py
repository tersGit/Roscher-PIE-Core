#!/usr/bin/env python3
"""Materialize auditable W1 geometry-input manifests without storing masks."""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.gis.estate_ags_matching.w1_geometry_input_adapter import (
    CROP_SIZE_PX, METRES_PER_PIXEL, W1_GEOJSON_SHA256, W1InputError,
    load_authoritative_inputs, pixel_to_world, rasterize_parcel, sha256,
)

OUT = ROOT / "data/investigations/w1_geometry_input_adapter"
DEFAULT_CROP_ROOT = Path(
    r"C:\Users\ters\copilot-worktrees\Roscher-PIE-Core\tersgit-probable-winner"
    r"\data\visual_index\waterfall_country_estate_w1\_imagery_cache_native15"
)
W5 = ROOT / "data/investigations/waterfall_w5_funnel_v1_1_blind_117413344/FULL_EXPERIMENTAL_SCORES.csv"


def write_csv(name: str, fieldnames: list[str], rows: list[dict]) -> str:
    path = OUT / name
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return sha256(path)


def main() -> int:
    crop_root = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CROP_ROOT
    OUT.mkdir(parents=True, exist_ok=True)
    inputs = load_authoritative_inputs(ROOT, crop_root)
    mapping, georefs, masks, validation = [], [], [], []
    for feature, georef in inputs:
        props = feature["properties"]
        crop = Path(georef.crop_path)
        mask = rasterize_parcel(feature["geometry"], georef)
        mask_px = int(mask.sum())
        expected = float(props["area_sqm"])
        latitude = float(props["centroid_latitude"])
        # Local Web-Mercator area correction to ground square metres.
        pixel_ground_area = (METRES_PER_PIXEL * __import__("math").cos(__import__("math").radians(latitude))) ** 2
        area = mask_px * pixel_ground_area
        relative_error = abs(area - expected) / expected
        cx, cy = pixel_to_world(georef, CROP_SIZE_PX / 2, CROP_SIZE_PX / 2)
        mapping.append({"property_id": georef.property_id, "extension": georef.extension, "crop_path": georef.crop_path,
                        "crop_sha256": sha256(crop), "mapping_source": "e86b156 original _crop_tiles output template"})
        georefs.append({"property_id": georef.property_id, "crs": "EPSG:3857", "width_px": CROP_SIZE_PX, "height_px": CROP_SIZE_PX,
                        "metres_per_pixel": METRES_PER_PIXEL, "centroid_x_3857": georef.centroid_x_3857, "centroid_y_3857": georef.centroid_y_3857,
                        "xmin_3857": georef.xmin_3857, "ymin_3857": georef.ymin_3857, "xmax_3857": georef.xmax_3857, "ymax_3857": georef.ymax_3857,
                        "affine": ",".join(map(str, georef.affine)), "centre_x_3857": cx, "centre_y_3857": cy})
        masks.append({"property_id": georef.property_id, "mask_source": "on_demand_deterministic_rasterize_parcel",
                      "shape": "900x900", "nonempty": bool(mask_px), "mask_pixels": mask_px,
                      "mask_recipe_sha256": hashlib.sha256((json.dumps(feature["geometry"], sort_keys=True) + json.dumps(georef.affine)).encode()).hexdigest()})
        centroid_pixel = (CROP_SIZE_PX // 2, CROP_SIZE_PX // 2)
        validation.append({"property_id": georef.property_id, "created": True, "nonempty": bool(mask_px),
                           "centroid_inside_crop": bool(mask[centroid_pixel[1], centroid_pixel[0]]),
                           "area_source_m2": expected, "raster_area_ground_m2": round(area, 4), "relative_area_error": round(relative_error, 6),
                           "area_error_band": "<=2%" if relative_error <= .02 else ">2-5%" if relative_error <= .05 else ">5%"})
    map_hash = write_csv("W1_CROP_MAPPING.csv", list(mapping[0]), mapping)
    geo_hash = write_csv("CROP_GEOREFERENCE.csv", list(georefs[0]), georefs)
    mask_hash = write_csv("PARCEL_MASK_MANIFEST.csv", list(masks[0]), masks)
    ids = {row["property_id"] for row in mapping}
    with W5.open(newline="", encoding="utf-8") as handle:
        w5 = list(csv.DictReader(handle))
    normal = [row for row in w5 if row["priority_band"] in {"A", "B"}]
    bands = {band: [row["candidate_id"] for row in normal if row["priority_band"] == band] for band in ("A", "B")}
    if (len(bands["A"]), len(bands["B"]), len(normal)) != (272, 365, 637) or any(candidate not in ids for candidate in bands["A"] + bands["B"]):
        raise W1InputError("Frozen W5 normal candidates do not map completely to W1 inputs.")
    validation_payload = {"frozen_geojson_sha256": W1_GEOJSON_SHA256, "properties": len(validation), "validation": validation,
                          "area_bands": {band: sum(row["area_error_band"] == band for row in validation) for band in ("<=2%", ">2-5%", ">5%")}}
    (OUT / "MASK_VALIDATION.json").write_text(json.dumps(validation_payload, indent=2) + "\n", encoding="utf-8")
    invalid = [row for row in validation if not row["nonempty"] or not row["centroid_inside_crop"]]
    invalid_ids = {row["property_id"] for row in invalid}
    dry = {"input_only": True, "status": "PASS" if not invalid else "BLOCKED", "normal_total": 637,
           "priority_a": {"count": 272, "image_missing": 0, "mask_missing": sum(candidate in invalid_ids for candidate in bands["A"])},
           "priority_b": {"count": 365, "image_missing": 0, "mask_missing": sum(candidate in invalid_ids for candidate in bands["B"])},
           "rescue_373_scheduled": False}
    (OUT / "W5_INPUT_DRY_RUN.json").write_text(json.dumps(dry, indent=2) + "\n", encoding="utf-8")
    qc = {"status": "PASS" if not invalid else "BLOCKED", "mapping_bijection": {"properties": len(ids), "crops": len(mapping), "unmatched": 0},
          "artifacts": {"mapping_sha256": map_hash, "georeference_sha256": geo_hash, "mask_manifest_sha256": mask_hash},
          "crop_root": str(crop_root), "mask_storage": "on-demand only; no raster mask images committed",
          "blocked_property_ids": sorted(invalid_ids)}
    (OUT / "QC_MANIFEST.json").write_text(json.dumps(qc, indent=2) + "\n", encoding="utf-8")
    (OUT / "ADAPTER_REPORT.md").write_text(
        "# W1 geometry input adapter\n\n"
        "The authoritative source is frozen W1 GeoJSON from e86b156, SHA256 `"
        + W1_GEOJSON_SHA256 + "` (1,010 properties). Original W1 `_crop_tiles` code supplies the crop contract: "
        "a 900px square centred on its stored centroid in EPSG:3857, with 0.15 m/px and bounds centre +/-67.5 m. "
        "The crop filename is verified against that producer contract and extension; it is not treated as an independent property identifier.\n\n"
        "The reported 81/637 discrepancy is not present in the frozen W5 artifact: its A/B candidate IDs map 272/272 and "
        "365/365 to frozen W1 properties. The prior diagnostic instead marked all 637 inputs source-unavailable, so its "
        "partial join cannot be used as W1 mapping evidence.\n\n"
        "Masks are deterministically rasterized on demand from frozen polygons and affine georeferences, including rings and clipping. "
        "No manual, imagery, or FastSAM boundaries are used.\n", encoding="utf-8")
    print(json.dumps(qc, indent=2))
    if invalid:
        raise W1InputError(
            "W1 adapter blocked: original crop-centre transform does not yield a nonempty, "
            f"centroid-containing mask for {len(invalid)} properties: {sorted(invalid_ids)}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
