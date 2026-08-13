#!/usr/bin/env python3
"""Build and visually verify the corrected Carlswald North (SUMMERSET EXT.6 + EXT.13) dataset."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.gis.coj_property import OFFICIAL_SUMMERSET_EXT, CoJPropertyClient, geometry_extent
from backend.gis.dataset_registry import (
    CORRECT_CARLSWALD_NORTH,
    DEPRECATED_CARLSWALD_NORTH_001,
    require_active_dataset,
)
from backend.imagery.ags_client import AGSAerialClient

OUTPUT = ROOT / "data/investigations/carlswald_north_corrected"
DATASET_JSON = ROOT / "data/gis" / f"{CORRECT_CARLSWALD_NORTH}.json"
OVERVIEW = OUTPUT / "estate_overview.jpg"

RESIDENTIAL_CATS = {"Residential", "Vacant Land"}
NONRES_HINTS = {
    "Public Open Space",
    "Private Open Space",
    "Public Service Infrastructure",
    "Public Service Infrastructure - Private",
    "Business and Commercial",
}


def _project(lon, lat, extent, width, height):
    x = (lon - extent["min_longitude"]) / max(extent["max_longitude"] - extent["min_longitude"], 1e-12)
    y = (extent["max_latitude"] - lat) / max(extent["max_latitude"] - extent["min_latitude"], 1e-12)
    return int(x * (width - 1)), int(y * (height - 1))


def classify_parcel(attrs: dict) -> str:
    cat = attrs.get("CAT_DESC") or ""
    zoning = attrs.get("ZONING") or ""
    stand = str(attrs.get("STAND_NO") or "")
    if cat in NONRES_HINTS or zoning in {"Reservation of land", "Public Garage", "Ecclesiastical"}:
        return "non_residential"
    if stand.startswith("RE/") or "Remainder" in stand:
        return "township_remainder"
    if cat == "Vacant Land":
        return "vacant"
    if cat == "Residential" and zoning.startswith("Residential"):
        return "residential"
    return "other"


def main() -> int:
    require_active_dataset(CORRECT_CARLSWALD_NORTH)
    print("TASK 1 — deprecated mapping")
    print(f"  {DEPRECATED_CARLSWALD_NORTH_001} is marked incorrect and cannot be selected for Carlswald North.")
    print(f"  Imagery/cache for that id is not deleted.")

    client = CoJPropertyClient()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    township_reports = []
    all_features = []

    print("\nTASK 2 — CoJ GIS township query (official names)")
    print(f"{'Township':<22} {'erven':>6}  extent")
    for ext in (2, 6, 13):
        official = OFFICIAL_SUMMERSET_EXT[ext]
        township = client.township_record(official)
        stands = client.registered_stands(official) if township or True else []
        # still query stands even if township polygon missing
        stands = client.registered_stands(official)
        erven = [item for item in stands if (item.get("attributes") or {}).get("LAND_TYPE_NAME") == "Erven"]
        extent = geometry_extent(erven)
        township_reports.append(
            {
                "requested": f"SUMMERSET EXTENSION {ext}",
                "official_name": official,
                "township_found": township is not None,
                "township_status": None if township is None else township["attributes"].get("STATUS_DESC"),
                "erven": len(erven),
                "extent": extent,
            }
        )
        print(
            f"{official:<22} {len(erven):6d}  "
            f"{extent if extent else 'NOT FOUND IN COJ GIS'}"
        )
        all_features.extend(erven)

    if not all_features:
        print("BLOCKER: no parcels retrieved")
        return 1

    combined = geometry_extent(all_features)
    print(f"\nCombined parcels: {len(all_features)}")
    print(f"Combined extent: {combined}")

    gated = client.gated_community("Carlswald North Estate")
    gated_extent = None
    if gated:
        gated_extent = geometry_extent([gated])
        print(f"CoJ gated community 'Carlswald North Estate' extent: {gated_extent}")

    print("\nTASK 3 — AGS overview")
    pad = 0.0008
    overview_extent = {
        "min_longitude": combined["min_longitude"] - pad,
        "max_longitude": combined["max_longitude"] + pad,
        "min_latitude": combined["min_latitude"] - pad,
        "max_latitude": combined["max_latitude"] + pad,
    }
    width, height = 2200, 1600
    aerial = AGSAerialClient(timeout_s=90.0).export_bbox(
        min_lon=overview_extent["min_longitude"],
        min_lat=overview_extent["min_latitude"],
        max_lon=overview_extent["max_longitude"],
        max_lat=overview_extent["max_latitude"],
        width=width,
        height=height,
        year=2023,
    )
    image = Image.open(__import__("io").BytesIO(aerial)).convert("RGB")
    draw = ImageDraw.Draw(image)
    colors = {
        "SUMMERSET EXT.6": (0, 220, 255),
        "SUMMERSET EXT.13": (80, 255, 120),
    }
    nonres = []
    for feature in all_features:
        attrs = feature["attributes"]
        kind = classify_parcel(attrs)
        town = attrs.get("TOWN_NAME_DESC")
        outline = colors.get(town, (255, 255, 255))
        if kind == "non_residential":
            outline = (255, 80, 80)
            nonres.append(attrs)
        rings = (feature.get("geometry") or {}).get("rings") or []
        for ring in rings:
            pts = [_project(x, y, overview_extent, image.width, image.height) for x, y in ring]
            if len(pts) >= 3:
                draw.line(pts + [pts[0]], fill=outline, width=1)
    draw.text((16, 12), "Carlswald North corrected: SUMMERSET EXT.6 (cyan) + EXT.13 (green)", fill=(255, 255, 255))
    draw.text((16, 32), "Red = open space / PSI / non-residential. EXT.2 not present in CoJ GIS.", fill=(255, 200, 200))
    OVERVIEW.parent.mkdir(parents=True, exist_ok=True)
    image.save(OVERVIEW, quality=92)
    print(f"  wrote {OVERVIEW}")

    classes = {}
    for feature in all_features:
        kind = classify_parcel(feature["attributes"])
        classes[kind] = classes.get(kind, 0) + 1
    print(f"  class counts: {classes}")
    print(f"  obvious non-residential/open-space/PSI parcels: {len(nonres)}")

    # contiguity: bbox overlap already known; write dataset
    parcels = []
    for feature in all_features:
        attrs = feature["attributes"]
        parcels.append(
            {
                "stand_number": str(attrs.get("STAND_NO")),
                "property_id": attrs.get("PROPERTY_ID"),
                "township": attrs.get("TOWN_NAME_DESC"),
                "area_sqm": attrs.get("AREA_SQMT"),
                "land_type": attrs.get("LAND_TYPE_NAME"),
                "zoning": attrs.get("ZONING"),
                "category": attrs.get("CAT_DESC"),
                "status": attrs.get("STATUS_DESC"),
                "class": classify_parcel(attrs),
                "geometry": feature.get("geometry"),
            }
        )
    payload = {
        "dataset_id": CORRECT_CARLSWALD_NORTH,
        "townships": ["SUMMERSET EXT.6", "SUMMERSET EXT.13"],
        "excluded_townships": ["CARLSWALD ESTATE", "CARLSWALD ESTATE EXT.1", "CARLSWALD ESTATE EXT.21", "CARLSWALD ESTATE EXT.64"],
        "summerset_ext_2": "not_present_in_coj_gis",
        "township_reports": township_reports,
        "parcel_count": len(parcels),
        "extent": combined,
        "gated_carlswald_north_estate_extent": gated_extent,
        "class_counts": classes,
        "parcels": parcels,
    }
    DATASET_JSON.parent.mkdir(parents=True, exist_ok=True)
    DATASET_JSON.write_text(json.dumps(payload), encoding="utf-8")
    print(f"\nTASK 4 dataset written: {DATASET_JSON}")
    print("Inspect overview before matching. Matching is a separate step.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
