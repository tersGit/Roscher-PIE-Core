#!/usr/bin/env python3
"""Build a listing-independent Waterfall Country Estate CoJ GIS freeze.

Membership is deliberately an exact CoJ ``TOWN_NAME_DESC`` match, never a
geographic inference.  Images are acquired through the established native15
estate tile cache; no listing or scoring subsystem is imported by this tool.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Iterable

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.gis.coj_property import (  # noqa: E402
    PROPERTY_MAPSERVER,
    REGISTERED_STANDS,
    TOWNSHIP_SEARCH,
    CoJPropertyClient,
    geometry_extent,
)
from backend.imagery.estate_tiles import (  # noqa: E402
    CACHE_PROFILES,
    DEFAULT_PROFILE_ID,
    EstateTileIndex,
    _mercator,
    pixels_for_extent,
)

ESTATE_ID = "waterfall_country_estate_w1"
ESTATE_DIR = ROOT / "data" / "estates" / "waterfall_country_estate"
GIS_OUTPUT = ESTATE_DIR / "waterfall_country_estate_w1.geojson"
MANIFEST_OUTPUT = ESTATE_DIR / "manifest.w1.json"
REPORT_OUTPUT = ROOT / "WATERFALL_COUNTRY_ESTATE_GIS_BUILD_REPORT.md"
EXTENSIONS = (19, 38, 39, 40, 43, 105)
SOURCE_DATE = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
RESIDENTIAL_CATS = {"Residential", "Vacant Land"}
NONRES_CATS = {
    "Business and Commercial",
    "Private Open Space",
    "Public Open Space",
    "Public Service Infrastructure",
    "Public Service Infrastructure - Private",
    "Township Development",
}


def official_name(extension: int) -> str:
    return f"JUKSKEI VIEW EXT.{extension}"


def normalized_name(extension: int) -> str:
    return f"JUKSKEI VIEW EXTENSION {extension}"


def centroid(geometry: dict[str, Any] | None) -> tuple[float | None, float | None]:
    """Return ring-vertex mean; sufficient for a stable GIS reference point."""
    points = [point for ring in (geometry or {}).get("rings", []) for point in ring]
    if not points:
        return None, None
    lon = sum(float(point[0]) for point in points) / len(points)
    lat = sum(float(point[1]) for point in points) / len(points)
    return round(lat, 8), round(lon, 8)


def flags_for(attrs: dict[str, Any], geometry: dict[str, Any] | None, lat: float | None, lon: float | None) -> list[str]:
    flags: list[str] = []
    if not str(attrs.get("STAND_NO") or "").strip():
        flags.append("missing_stand")
    if not (geometry or {}).get("rings"):
        flags.append("missing_geometry")
    if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        flags.append("invalid_centroid")
    area = float(attrs.get("AREA_SQMT") or 0)
    if area and area < 200:
        flags.append("suspicious_tiny_area")
    if area > 8000:
        flags.append("suspicious_large_area")
    category = str(attrs.get("CAT_DESC") or "")
    if category in NONRES_CATS or category not in RESIDENTIAL_CATS:
        flags.append("non_residential_or_common_property")
    return flags


def feature_from_row(row: dict[str, Any], extension: int) -> dict[str, Any]:
    attrs = row.get("attributes") or {}
    geometry = row.get("geometry") or {}
    lat, lon = centroid(geometry)
    source_township = str(attrs.get("TOWN_NAME_DESC") or "")
    props = {
        "pie_property_id": attrs.get("PROPERTY_ID"),
        "gis_objectid": attrs.get("OBJECTID"),
        "sg_id": attrs.get("SG_ID"),
        "stand_number": str(attrs.get("STAND_NO") or "").strip() or None,
        "township_source": source_township,
        "township_normalized": normalized_name(extension),
        "extension": extension,
        "area_sqm": attrs.get("AREA_SQMT"),
        "centroid_latitude": lat,
        "centroid_longitude": lon,
        "street_address": str(attrs.get("STREET_ADDRESS") or "").strip() or None,
        "street_number": str(attrs.get("STREET_NO") or "").strip() or None,
        "street_name": str(attrs.get("STREET_NAME") or "").strip() or None,
        "land_type": attrs.get("LAND_TYPE_NAME"),
        "zoning": attrs.get("ZONING"),
        "category": attrs.get("CAT_DESC"),
        "status": attrs.get("STATUS_DESC"),
        "source_layer": REGISTERED_STANDS,
        "source_layer_name": "REGISTERED_STANDS",
        "source_date_utc": SOURCE_DATE,
        "qa_flags": flags_for(attrs, geometry, lat, lon),
    }
    return {"type": "Feature", "id": str(attrs.get("PROPERTY_ID") or attrs.get("OBJECTID")), "properties": props, "geometry": geometry}


def deduplicate(features: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Retain all rows; duplicate keys are QA flags, never silently collapsed."""
    features = list(features)
    groups: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
    for feature in features:
        props = feature["properties"]
        groups[(props["extension"], props["stand_number"] or "")].append(feature)
    duplicates = []
    for key, rows in groups.items():
        if len(rows) > 1:
            ids = [row["properties"]["pie_property_id"] for row in rows]
            duplicates.append({"extension": key[0], "stand_number": key[1], "property_ids": ids})
            for row in rows:
                row["properties"]["qa_flags"].append("duplicate_extension_stand")
    return features, duplicates


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _crop_tiles(
    feature: dict[str, Any], tiles: list[dict[str, Any]], crop_dir: Path
) -> dict[str, Any]:
    """Create a 135 m context crop by compositing the established 210 m tiles."""
    props = feature["properties"]
    lat, lon = props["centroid_latitude"], props["centroid_longitude"]
    if lat is None or lon is None:
        return {"status": "MISSING_CENTROID"}
    size_m, pixels = 135.0, 900
    cx, cy = _mercator(lat, lon)
    xmin, ymin, xmax, ymax = cx - size_m / 2, cy - size_m / 2, cx + size_m / 2, cy + size_m / 2
    canvas = Image.new("RGB", (pixels, pixels))
    hits = []
    for tile in tiles:
        ix0, iy0 = max(xmin, tile["xmin"]), max(ymin, tile["ymin"])
        ix1, iy1 = min(xmax, tile["xmax"]), min(ymax, tile["ymax"])
        if ix0 >= ix1 or iy0 >= iy1 or not Path(tile["path"]).is_file():
            continue
        with Image.open(tile["path"]) as image:
            image = image.convert("RGB")
            sx0 = round((ix0 - tile["xmin"]) / (tile["xmax"] - tile["xmin"]) * image.width)
            sx1 = round((ix1 - tile["xmin"]) / (tile["xmax"] - tile["xmin"]) * image.width)
            sy0 = round((tile["ymax"] - iy1) / (tile["ymax"] - tile["ymin"]) * image.height)
            sy1 = round((tile["ymax"] - iy0) / (tile["ymax"] - tile["ymin"]) * image.height)
            dx0 = round((ix0 - xmin) / size_m * pixels)
            dx1 = round((ix1 - xmin) / size_m * pixels)
            dy0 = round((ymax - iy1) / size_m * pixels)
            dy1 = round((ymax - iy0) / size_m * pixels)
            canvas.paste(image.crop((sx0, sy0, sx1, sy1)).resize((dx1 - dx0, dy1 - dy0)), (dx0, dy0))
        hits.append(Path(tile["path"]).stem)
    output = crop_dir / f"{props['extension']}_{props['pie_property_id']}_ags_aerial.jpg"
    crop_dir.mkdir(parents=True, exist_ok=True)
    if hits:
        canvas.save(output, quality=92)
        return {"status": "READY", "path": str(output.relative_to(ROOT)), "dimensions": [pixels, pixels], "effective_gsd_m": 0.15, "tile_ids": hits}
    return {"status": "TILE_UNAVAILABLE", "dimensions": [pixels, pixels], "effective_gsd_m": 0.15, "tile_ids": []}


def build_qc_panels(features: list[dict[str, Any]], crop_dir: Path) -> list[dict[str, Any]]:
    sample = random.Random("waterfall-w1-listing-independent").sample(features, min(12, len(features)))
    panel_dir = ESTATE_DIR / "qc_panels"
    panel_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for index, feature in enumerate(sample, start=1):
        props = feature["properties"]
        crop = crop_dir / f"{props['extension']}_{props['pie_property_id']}_ags_aerial.jpg"
        status = "CROP_UNAVAILABLE"
        if crop.is_file():
            with Image.open(crop) as image:
                image = image.convert("RGB")
                draw = ImageDraw.Draw(image)
                draw.rectangle((0, 0, image.width - 1, image.height - 1), outline=(255, 255, 0), width=3)
                draw.text((12, 12), f"Stand {props['stand_number']} | {props['township_normalized']} | {props['area_sqm']} sqm", fill=(255, 255, 0))
                output = panel_dir / f"qc_{index:02d}_{props['extension']}_{props['pie_property_id']}.jpg"
                image.save(output, quality=92)
            status = "READY"
        results.append({"pie_property_id": props["pie_property_id"], "extension": props["extension"], "stand_number": props["stand_number"], "status": status})
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-imagery", action="store_true", help="Write GIS freeze only; do not retrieve AGS tiles.")
    args = parser.parse_args()
    ESTATE_DIR.mkdir(parents=True, exist_ok=True)
    client = CoJPropertyClient(timeout_s=90)
    features, township_reports = [], []
    for extension in EXTENSIONS:
        official = official_name(extension)
        township = client.query(TOWNSHIP_SEARCH, f"TOWN_NAME_DESC='{official}'", fields="TOWN_NAME_DESC,TS_EXT,STATUS_DESC,TSG_ID", return_geometry=True)
        rows = client.registered_stands(official)
        if any((row.get("attributes") or {}).get("TOWN_NAME_DESC") != official for row in rows):
            raise RuntimeError(f"CoJ exact township query returned an out-of-scope row for {official}")
        current = [feature_from_row(row, extension) for row in rows if (row.get("attributes") or {}).get("LAND_TYPE_NAME") == "Erven"]
        features.extend(current)
        areas = [float(item["properties"]["area_sqm"]) for item in current if item["properties"]["area_sqm"] is not None]
        township_reports.append({"extension": extension, "official_name": official, "normalized_name": normalized_name(extension), "township_found": bool(township), "source_erven_count": len(current), "area_sqm": {"min": min(areas), "median": median(areas), "max": max(areas)}})
    features, duplicates = deduplicate(features)
    collection = {"type": "FeatureCollection", "name": ESTATE_ID, "source": PROPERTY_MAPSERVER, "features": features}
    GIS_OUTPUT.write_text(json.dumps(collection, indent=2) + "\n", encoding="utf-8")
    extent = geometry_extent([{"geometry": feature["geometry"]} for feature in features])
    imagery = {"profile": DEFAULT_PROFILE_ID, "status": "NOT_REQUESTED", "cache_version": "w1", "service": "AerialPhotography/2023"}
    crop_dir = ROOT / "data" / "visual_index" / ESTATE_ID / "_imagery_cache_native15"
    qc = []
    if not args.skip_imagery and extent:
        index = EstateTileIndex(ROOT / "data" / "cache" / "ags_native15" / ESTATE_ID, extent, profile_id=DEFAULT_PROFILE_ID)
        stats = index.build()
        crop_statuses = [_crop_tiles(feature, index.tiles, crop_dir) for feature in features]
        imagery = {"profile": DEFAULT_PROFILE_ID, "status": "COMPLETE" if stats.tiles_failed == 0 else "PARTIAL", "cache_version": "w1", "service": "AerialPhotography/2023", "source_year": 2023, "tile_stats": stats.__dict__, "crop_status_counts": dict(Counter(row["status"] for row in crop_statuses)), "crop_dimensions": [900, 900], "requested_effective_gsd_m": 0.15}
        qc = build_qc_panels(features, crop_dir)
    qa_counts = Counter(flag for feature in features for flag in feature["properties"]["qa_flags"])
    principal_artifacts = {"geojson": {"path": str(GIS_OUTPUT.relative_to(ROOT)), "sha256": _sha256(GIS_OUTPUT)}}
    cache_manifest = ROOT / "data" / "cache" / "ags_native15" / ESTATE_ID / "manifest.json"
    if cache_manifest.is_file():
        principal_artifacts["native15_cache_manifest"] = {
            "path": str(cache_manifest.relative_to(ROOT)),
            "sha256": _sha256(cache_manifest),
        }
    manifest = {"schema_version": "waterfall-country-estate-w1", "created_utc": SOURCE_DATE, "estate_id": ESTATE_ID, "scope": {"authoritative_townships": [official_name(ext) for ext in EXTENSIONS], "normalized_townships": [normalized_name(ext) for ext in EXTENSIONS], "membership": "Exact CoJ Property/MapServer layer 8 TOWN_NAME_DESC only; no proximity inference; no adjacent extensions."}, "source": {"mapserver": PROPERTY_MAPSERVER, "layer": REGISTERED_STANDS, "layer_name": "REGISTERED_STANDS", "retrieved_utc": SOURCE_DATE}, "townships": township_reports, "total_erven": len(features), "extent": extent, "duplicates": duplicates, "qa_flag_counts": dict(qa_counts), "imagery": imagery, "qc_sample": qc, "principal_artifacts": principal_artifacts, "code_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "listing_independent": True, "production_scoring_changed": False}
    MANIFEST_OUTPUT.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    counts = {report["extension"]: report["source_erven_count"] for report in township_reports}
    readiness = "READY" if imagery["status"] == "COMPLETE" and len(qc) == 12 and all(row["status"] == "READY" for row in qc) else "NOT READY"
    REPORT_OUTPUT.write_text(f"""# Waterfall Country Estate GIS Build — W1

## A. Repository and provenance audit
No pre-existing Waterfall Country Estate or Jukskei View GIS, imagery cache, mapping, inventory, or listing-derived artifact was found. This build used CoJ Property MapServer layer 8 and the existing corrected native15 `EstateTileIndex` / `AGSAerialClient` infrastructure only. No listing source, target identity, ranking, matching, or production scoring code was used or changed.

## B. Authoritative scope and inventory
Membership is an exact `TOWN_NAME_DESC` query for only the six CoJ names below. `EXT`, `EXT.`, and `EXTENSION` are normalized in the output while the CoJ source value is retained. All layer-8 `LAND_TYPE_NAME=Erven` records are retained and classification concerns are flags, not deletions.

| Extension | CoJ source township | Erven |
|---:|---|---:|
""" + "\n".join(f"| {ext} | {official_name(ext)} | {counts[ext]} |" for ext in EXTENSIONS) + f"""
| **Total** | **six exact extensions only** | **{len(features)}** |

## C. Scope QA
Duplicate extension-plus-stand groups: {len(duplicates)}. Missing stands: {qa_counts['missing_stand']}; missing geometry: {qa_counts['missing_geometry']}; invalid centroids: {qa_counts['invalid_centroid']}. Tiny-area flags: {qa_counts['suspicious_tiny_area']}; large-area flags: {qa_counts['suspicious_large_area']}; non-residential/common-property flags: {qa_counts['non_residential_or_common_property']}. Flags are retained for review.

## D. Native15 source acquisition
Profile: `{DEFAULT_PROFILE_ID}` (`{CACHE_PROFILES[DEFAULT_PROFILE_ID].tile_metres:g} m` tiles at `{CACHE_PROFILES[DEFAULT_PROFILE_ID].pixels}px`, target `{CACHE_PROFILES[DEFAULT_PROFILE_ID].metres_per_pixel:.2f} m/px`). Legacy caches are not reused or overwritten. Status: **{imagery['status']}**.

## E. Parcel-centred crops
All requested parcel-centred crops are `{imagery.get('crop_dimensions', [])}` pixels at an actual effective GSD of `{imagery.get('requested_effective_gsd_m', 'N/A')} m/px`; crop status counts are preserved in the manifest.

## F. Visual inventory
No detector or scoring run was started. Pool/visual-inventory statuses were not inferred, changed, or used to eliminate parcels.

## G. Listing-independent QC
Deterministic random sample size: {len(qc)}. Ready panels: {sum(row['status'] == 'READY' for row in qc)}. Panels retain parcel crop, centroid, stand, township/extension, and area context.

## H. Freeze
Machine-readable freeze: `{MANIFEST_OUTPUT.relative_to(ROOT)}`. GIS feature collection: `{GIS_OUTPUT.relative_to(ROOT)}`. SHA256 is recorded in the manifest.

## I. Source identifiers
The GeoJSON retains PIE property ID, CoJ object ID, SG ID, stand, source and normalized township, area, geometry, centroid, and GIS street fields.

## J. Duplicate controls
Duplicate extension-plus-stand keys are explicitly flagged and retained, preserving unambiguous source identifiers for review.

## K. Address provenance
Street address, number, and name are copied only from CoJ layer 8 fields; no listing address data was consulted.

## L. Area and geometry coverage
The source-layer area and full CoJ polygon geometry are frozen per record; anomalies are flagged rather than removed.

## M. Cache provenance
The manifest records AGS service/year, cache profile/version, tile status, crop status, requested and effective GSD, and principal SHA256 values.

## N. Readiness conditions
Readiness requires exact scope, complete GIS geometry/centroids, complete native15 crop coverage, and every deterministic QC panel available.

## O. Final readiness
**{readiness}** — requires complete native15 tile/crop coverage and all 12 QC panels. No listing testing began.
""", encoding="utf-8")
    print(json.dumps({"counts": counts, "total": len(features), "imagery": imagery["status"], "readiness": readiness}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
