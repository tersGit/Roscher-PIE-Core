#!/usr/bin/env python3
"""Read-only UNKNOWN diagnostic for Estate Property Inventory v1.

Does not modify current.jsonl, OS v1, FastSAM, Scoring v2, Hybrid geometry,
native15 cache, ranking, or listing-pool-gate semantics.
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.gis.dataset_registry import CORRECT_CARLSWALD_NORTH
from backend.gis.estate_ags_matching.estate_inventory_unknown_diagnostic import (
    KNOWN_DIAGNOSTIC_STANDS,
    analyse_unknowns,
    conservative_v11_simulation,
    coverage_report,
    load_gis,
    load_inventory_rows,
    load_os,
    select_panel_stands,
)
from backend.gis.estate_ags_matching.estate_property_inventory_v1 import parcel_bbox, pass1_parcels, safe_stand
from backend.imagery.ags_client import AGSAerialClient, AGSError
from backend.imagery.estate_tiles import PADDING_METRES, NATIVE_PIXEL_SIZE_M
from backend.vision.object_segmentation import parcel_mask_from_geometry

ESTATE_ID = CORRECT_CARLSWALD_NORTH
OUT = ROOT / "data" / "investigations" / "estate_property_inventory_v1" / "unknown_diagnostic"
CROP_DIR = OUT / "diagnostic_crops"
PANEL_DIR = OUT / "panels"
INVENTORY_CURRENT = ROOT / "data" / "estate_inventory" / ESTATE_ID / "current.jsonl"


def _font(size: int = 14):
    path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    return ImageFont.truetype(str(path), size) if path.is_file() else ImageFont.load_default()


def _probe_ext3() -> dict:
    """Live CoJ probe. Isolated from the frozen GIS dataset file."""
    try:
        from backend.gis.coj_property import CoJPropertyClient, geometry_extent

        client = CoJPropertyClient(timeout_s=45.0)
        rec = client.township_record("SUMMERSET EXT.3")
        stands = client.registered_stands("SUMMERSET EXT.3")
        erven = [item for item in stands if (item.get("attributes") or {}).get("LAND_TYPE_NAME") == "Erven"]
        residential = [
            item
            for item in erven
            if (item.get("attributes") or {}).get("CAT_DESC") == "Residential"
            and str((item.get("attributes") or {}).get("ZONING") or "").startswith("Residential")
            and not str((item.get("attributes") or {}).get("STAND_NO") or "").startswith("RE/")
            and ((item.get("attributes") or {}).get("AREA_SQMT") or 0) < 8000
        ]
        return {
            "queried": True,
            "township_found": rec is not None,
            "township_status": None if rec is None else (rec.get("attributes") or {}).get("STATUS_DESC"),
            "erven": len(erven),
            "approx_pass1_residential": len(residential),
            "extent": geometry_extent(erven) if erven else None,
            "sample_stands": [
                (item.get("attributes") or {}).get("STAND_NO") for item in residential[:8]
            ],
            "inside_gated_bbox": True,
            "in_frozen_dataset": False,
        }
    except Exception as exc:  # noqa: BLE001
        return {"queried": True, "error": f"{type(exc).__name__}: {exc}"}


def _fetch_crop(parcel: dict, dest: Path) -> dict:
    geom = parcel["geometry"]
    bbox = parcel_bbox(geom)
    pad = PADDING_METRES / 111_320
    min_lon, min_lat, max_lon, max_lat = bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad
    width_m = max((max_lon - min_lon) * 111_320, 8.0)
    height_m = max((max_lat - min_lat) * 111_320, 8.0)
    width = max(64, min(1400, int(round(width_m / NATIVE_PIXEL_SIZE_M))))
    height = max(64, min(1400, int(round(height_m / NATIVE_PIXEL_SIZE_M))))
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and dest.stat().st_size > 1000:
        return {"path": str(dest), "reused": True, "width": width, "height": height}
    client = AGSAerialClient(timeout_s=60.0)
    dest.write_bytes(
        client.export_bbox(
            min_lon=min_lon,
            min_lat=min_lat,
            max_lon=max_lon,
            max_lat=max_lat,
            width=width,
            height=height,
            year=2023,
        )
    )
    return {"path": str(dest), "reused": False, "width": width, "height": height}


def _draw_contour(overlay: np.ndarray, contour, color, thickness=2) -> None:
    if not contour:
        return
    h, w = overlay.shape[:2]
    pts = np.array([[int(float(x) * (w - 1)), int(float(y) * (h - 1))] for x, y in contour], np.int32)
    if len(pts) >= 3:
        cv2.polylines(overlay, [pts], True, color, thickness)


def _draw_panel(crop_bgr: np.ndarray, parcel: dict, os_payload: dict | None, diag: dict | None, title: str) -> np.ndarray:
    h, w = crop_bgr.shape[:2]
    geom = parcel.get("geometry") or {}
    pmask = parcel_mask_from_geometry((w, h), geom)
    orig = crop_bgr.copy()
    parcel_vis = crop_bgr.copy()
    contours, _ = cv2.findContours(pmask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(parcel_vis, contours, -1, (0, 255, 255), 2)
    pool_vis = crop_bgr.copy()
    bld_vis = crop_bgr.copy()
    combo = crop_bgr.copy()
    cv2.drawContours(combo, contours, -1, (0, 255, 255), 1)
    pool = {} if os_payload is None else (os_payload.get("pool") or {})
    building = {} if os_payload is None else (os_payload.get("building") or {})
    _draw_contour(pool_vis, pool.get("contour"), (255, 180, 40), 2)
    _draw_contour(combo, pool.get("contour"), (255, 180, 40), 2)
    _draw_contour(bld_vis, building.get("contour"), (40, 80, 255), 2)
    _draw_contour(combo, building.get("contour"), (40, 80, 255), 2)
    tiles = [orig, parcel_vis, pool_vis, bld_vis, combo]
    row = np.concatenate(tiles, axis=1)
    bar_h = 72
    bar = np.zeros((bar_h, row.shape[1], 3), dtype=np.uint8)
    rgb = Image.fromarray(bar[:, :, ::-1])
    draw = ImageDraw.Draw(rgb)
    os_status = None if not pool else pool.get("status")
    notes = [] if not pool else pool.get("notes")
    clip = (pool or {}).get("clip") or {}
    line1 = title
    line2 = (
        f"OS pool={os_status} notes={notes} clip_pool={float(clip.get('pool') or 0):.3f} "
        f"inv={None if diag is None else diag.get('inventory_pool_status')}"
    )
    line3 = (
        f"reason={None if diag is None else diag.get('primary_reason')} "
        f"subtype={None if diag is None else diag.get('rejected_subtype')} "
        f"proposed=diagnostic_only_see_report"
    )
    draw.text((8, 6), line1, font=_font(16), fill=(240, 240, 240))
    draw.text((8, 28), line2[:180], font=_font(13), fill=(210, 210, 210))
    draw.text((8, 48), line3[:180], font=_font(13), fill=(210, 210, 210))
    bar = np.array(rgb)[:, :, ::-1]
    return np.concatenate([bar, row], axis=0)


def _proposed_hard_filter(diag: dict | None, inventory_status: str) -> str:
    if inventory_status == "YES":
        return "likely YES — already inventory YES; keep for listing-NO gate"
    if inventory_status == "NO":
        return "likely NO — already inventory NO; keep for listing-YES gate"
    if diag is None:
        return "genuinely UNKNOWN"
    if diag.get("primary_reason") == "partially_outside_parcel":
        return "genuinely UNKNOWN — neighbour/mask bleed; not safe YES"
    if diag.get("os_pool_status") == "REJECTED":
        return "genuinely UNKNOWN for hard filter — REJECTED is not absence (dark-miss risk)"
    if diag.get("unknown_solely_because_building_inadequate"):
        return "genuinely UNKNOWN for hard filter until absence evidence independent of roof mask"
    return "genuinely UNKNOWN"


def main() -> int:
    if not INVENTORY_CURRENT.is_file():
        print("missing inventory current.jsonl", file=sys.stderr)
        return 1
    dataset = load_gis()
    inventory = load_inventory_rows()
    coverage = coverage_report(dataset, inventory)
    ext3 = _probe_ext3()
    coverage["summerset_ext_3_probe"] = ext3
    coverage["intended_extensions_user"] = ["SUMMERSET EXT.3", "SUMMERSET EXT.6", "SUMMERSET EXT.13"]
    coverage["ext3_in_frozen_dataset"] = "SUMMERSET EXT.3" in (coverage["townships_in_dataset"] or [])
    coverage["dataset_complete_for_frozen_ext6_ext13"] = (
        coverage["unique_erven_after_property_id_dedup"] == 330
        and coverage["os_v1_fingerprints_for_pass1"] == 330
        and coverage["inventory_rows"] == 330
    )
    coverage["dataset_complete_for_gated_estate_incl_ext3"] = False
    coverage["stop_optimisation"] = bool(ext3.get("township_found")) and not coverage["ext3_in_frozen_dataset"]

    unknown = analyse_unknowns(inventory)
    simulation = conservative_v11_simulation(inventory, unknown)
    parcels = {str(p["stand_number"]): p for p in pass1_parcels(dataset)}
    diag_by_stand = {str(row["stand_number"]): row for row in unknown["rows"]}
    sample = select_panel_stands(unknown, inventory)
    OUT.mkdir(parents=True, exist_ok=True)
    CROP_DIR.mkdir(parents=True, exist_ok=True)
    PANEL_DIR.mkdir(parents=True, exist_ok=True)

    panel_rows = []
    ags_ok = 0
    ags_fail = 0
    for stand in sample:
        parcel = parcels.get(stand)
        os_payload = load_os(stand)
        diag = diag_by_stand.get(stand)
        inv_status = next((r.get("pool_status") for r in inventory if r.get("stand_number") == stand), None)
        crop_path = CROP_DIR / f"{safe_stand(stand)}_diagnostic.jpg"
        fetch = {"error": "no parcel"}
        crop_bgr = None
        if parcel:
            try:
                fetch = _fetch_crop(parcel, crop_path)
                crop_bgr = cv2.imread(str(crop_path))
                ags_ok += 1
            except (AGSError, OSError, ValueError) as exc:
                fetch = {"error": str(exc)}
                ags_fail += 1
                if os_payload and os_payload.get("crop_wh"):
                    w, h = os_payload["crop_wh"]
                    crop_bgr = np.zeros((int(h), int(w), 3), np.uint8)
        if crop_bgr is not None and parcel is not None:
            panel = _draw_panel(
                crop_bgr,
                parcel,
                os_payload,
                diag,
                f"Stand {stand}  inventory={inv_status}  diagnostic only",
            )
            panel_path = PANEL_DIR / f"{safe_stand(stand)}_unknown_diagnostic.jpg"
            cv2.imwrite(str(panel_path), panel, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
        else:
            panel_path = None
        panel_rows.append(
            {
                "stand_number": stand,
                "inventory_pool_status": inv_status,
                "diagnostic": diag,
                "known_example": stand in KNOWN_DIAGNOSTIC_STANDS,
                "hard_filter_recommendation": _proposed_hard_filter(diag, str(inv_status or "UNKNOWN")),
                "crop": fetch,
                "panel": None if panel_path is None else str(panel_path),
            }
        )

    payload = {
        "production_ranking_modified": False,
        "inventory_current_modified": False,
        "os_v1_modified": False,
        "listing_pool_gate_semantics_modified": False,
        "coverage": coverage,
        "unknown_analysis": {
            k: unknown[k]
            for k in unknown
            if k != "rows"
        },
        "unknown_rows": unknown["rows"],
        "simulation": simulation,
        "panels": panel_rows,
        "ags_crops_ok": ags_ok,
        "ags_crops_failed": ags_fail,
        "false_exclusion_risks": [
            {
                "rank": 1,
                "mode": "REJECTED_to_NO",
                "effect": "genuine pool discarded when listing has pool",
                "example": "Stand 370 dark-teal is OS REJECTED with CLIP pool 0.029 / roof 0.325",
                "hard_filter": "unsafe",
            },
            {
                "rank": 2,
                "mode": "no_pool_candidate_to_NO_when_detector_misses",
                "effect": "unsegmented in-parcel pool discarded when listing has pool",
                "example": "same failure class as 370 if FastSAM+water seeds produce no candidate",
                "hard_filter": "residual risk; building-quality gate does not actually protect this",
            },
            {
                "rank": 3,
                "mode": "partially_outside_to_YES",
                "effect": "neighbour pool kept as YES and discarded when listing has no pool",
                "example": "stands 658, 633, 1/334, 1105",
                "hard_filter": "unsafe YES",
            },
            {
                "rank": 4,
                "mode": "OS_CONFIRMED_false_positive_YES",
                "effect": "non-pool discarded when listing has no pool",
                "example": "current 91 YES inherit OS v1 false-positive risk",
                "hard_filter": "accepted OS v1 YES risk; do not add weaker YES",
            },
        ],
        "recommended_next_experiment": (
            "Add SUMMERSET EXT.3 to the Carlswald North GIS dataset as an explicit, "
            "reviewed boundary change (not a silent edit), rebuild native15 crops + OS v1 "
            "for those erven, then repeat inventory. Do not convert REJECTED to NO first."
        ),
    }
    (OUT / "latest.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "stop_optimisation": coverage["stop_optimisation"],
        "ext3": {k: ext3.get(k) for k in ("township_found", "erven", "approx_pass1_residential", "extent")},
        "coverage_330": coverage["unique_erven_after_property_id_dedup"],
        "unknown_primary": unknown["primary_reason_counts"],
        "rejected_subtypes": unknown["rejected_subtype_counts"],
        "building_only_unknown": unknown["unknown_solely_building_inadequate_n"],
        "simulation_classified_pct_current": simulation["current_v1"]["classified_pct"],
        "simulation_classified_pct_upper_no": simulation["upper_bound_if_building_gate_dropped_for_no"]["classified_pct"],
        "panels": len(panel_rows),
        "ags_ok": ags_ok,
        "ags_fail": ags_fail,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
