#!/usr/bin/env python3
"""Build and freeze Carlswald North complete GIS: Summerset EXT.3 + EXT.6 + EXT.13.

Does not modify carlswald_north_corrected_001. Does not change ranking or OS v1.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.gis.carlswald_north_complete import (
    COMPLETE_002_PATH,
    COMPLETE_CARLSWALD_NORTH,
    FROZEN_001_PATH,
    build_complete_dataset,
    freeze_summary_table,
    write_complete_dataset,
)
from backend.gis.coj_property import CoJPropertyClient, geometry_extent
from backend.gis.dataset_registry import require_active_dataset
from backend.imagery.ags_client import AGSAerialClient

OUT = ROOT / "data/investigations/carlswald_north_complete"
OVERVIEW = OUT / "estate_overview_ext3_6_13.jpg"


def _project(lon, lat, extent, width, height):
    x = (lon - extent["min_longitude"]) / max(extent["max_longitude"] - extent["min_longitude"], 1e-12)
    y = (extent["max_latitude"] - lat) / max(extent["max_latitude"] - extent["min_latitude"], 1e-12)
    return int(x * (width - 1)), int(y * (height - 1))


def main() -> int:
    require_active_dataset(COMPLETE_CARLSWALD_NORTH)
    assert FROZEN_001_PATH.is_file(), "frozen 001 GIS JSON must remain on disk"
    frozen_sha_before = __import__("hashlib").sha256(FROZEN_001_PATH.read_bytes()).hexdigest()

    client = CoJPropertyClient()
    payload = build_complete_dataset(client)
    write_complete_dataset(payload)
    frozen_sha_after = __import__("hashlib").sha256(FROZEN_001_PATH.read_bytes()).hexdigest()
    if frozen_sha_before != frozen_sha_after:
        raise RuntimeError("carlswald_north_corrected_001 was modified; aborting")

    OUT.mkdir(parents=True, exist_ok=True)
    table = freeze_summary_table(payload)
    print("A/B — Carlswald North complete GIS (authoritative CoJ township names)")
    print(f"{'Extension':<12} {'Source parcels':>16} {'Included unique':>18}")
    for row in table:
        print(f"{row['extension']:<12} {row['source_parcels']:>16d} {row['included_unique_properties']:>18d}")

    combined = payload["extent"]
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
        "SUMMERSET EXT.3": (255, 180, 40),
        "SUMMERSET EXT.6": (0, 220, 255),
        "SUMMERSET EXT.13": (80, 255, 120),
    }
    for feature in payload["parcels"]:
        town = feature.get("township")
        outline = colors.get(town, (255, 255, 255))
        if feature.get("class") == "non_residential":
            outline = (255, 80, 80)
        rings = (feature.get("geometry") or {}).get("rings") or []
        for ring in rings:
            pts = [_project(x, y, overview_extent, image.width, image.height) for x, y in ring]
            if len(pts) >= 3:
                draw.line(pts + [pts[0]], fill=outline, width=1)
    draw.text((16, 12), "Carlswald North complete: EXT.3 (orange) + EXT.6 (cyan) + EXT.13 (green)", fill=(255, 255, 255))
    draw.text((16, 32), "Red = open space / PSI / non-residential. Frozen 001 (EXT.6+13) kept intact.", fill=(255, 200, 200))
    image.save(OVERVIEW, quality=92)

    exclusion_rows = payload.get("_exclusion_rows") or {}
    report = {
        "dataset_id": COMPLETE_CARLSWALD_NORTH,
        "source_layer": payload["source_layer"],
        "source_layer_name": payload["source_layer_name"],
        "source_mapserver": payload["source_mapserver"],
        "membership_basis": payload["membership_basis"],
        "not_inferred_from_proximity": True,
        "table": table,
        "township_reports": payload["township_reports"],
        "geometry_quality": payload["geometry_quality"],
        "compare_to_frozen_001": payload["compare_to_frozen_001"],
        "native15_coverage_plan": payload["native15_coverage_plan"],
        "gated_extent": payload.get("gated_carlswald_north_estate_extent"),
        "extent": payload.get("extent"),
        "class_counts": payload.get("class_counts"),
        "frozen_001_sha256": frozen_sha_after,
        "frozen_001_untouched": frozen_sha_before == frozen_sha_after,
        "overview": str(OVERVIEW),
        "gis_json": str(COMPLETE_002_PATH),
        "exclusion_row_counts": {k: len(v) for k, v in exclusion_rows.items()},
    }
    (OUT / "freeze_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("dataset_id", "table", "geometry_quality", "compare_to_frozen_001", "native15_coverage_plan", "frozen_001_untouched")}, indent=2, default=str))
    print(f"wrote {COMPLETE_002_PATH}")
    print(f"wrote {OVERVIEW}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
