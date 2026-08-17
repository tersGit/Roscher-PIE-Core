"""Carlswald North complete GIS universe: Summerset EXT.3 + EXT.6 + EXT.13.

Diagnostic / dataset-completion only. Does not modify
``carlswald_north_corrected_001``, OS v1, FastSAM, native15, ranking, or
inventory classification semantics.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

from backend.gis.coj_property import (
    OFFICIAL_SUMMERSET_EXT,
    REGISTERED_STANDS,
    CoJPropertyClient,
    geometry_extent,
)
from backend.gis.dataset_registry import (
    COMPLETE_CARLSWALD_NORTH,
    FROZEN_CARLSWALD_NORTH_001,
)
from backend.gis.estate_ags_matching.estate_property_inventory_v1 import (
    geometry_sha256,
    parcel_bbox,
    pass1_parcels,
    safe_stand,
)
from backend.imagery.estate_tiles import CACHE_PROFILES, PADDING_METRES, cache_root_for, crop_dir_for

REPO_ROOT = Path(__file__).resolve().parents[2]
GIS_DIR = REPO_ROOT / "data" / "gis"
FROZEN_001_PATH = GIS_DIR / f"{FROZEN_CARLSWALD_NORTH_001}.json"
COMPLETE_002_PATH = GIS_DIR / f"{COMPLETE_CARLSWALD_NORTH}.json"
COMPLETE_EXTENSIONS = (3, 6, 13)
SOURCE_LAYER = REGISTERED_STANDS
SOURCE_LAYER_NAME = "REGISTERED_STANDS"
SOURCE_MAPSERVER = "https://ags.joburg.org.za/server/rest/services/Property/MapServer"

RESIDENTIAL_CATS = {"Residential", "Vacant Land"}
NONRES_HINTS = {
    "Public Open Space",
    "Private Open Space",
    "Public Service Infrastructure",
    "Public Service Infrastructure - Private",
    "Business and Commercial",
}


def classify_parcel(attrs: Mapping[str, Any]) -> str:
    """Same residential / remainder / non-res rules as the frozen 001 builder."""
    cat = attrs.get("CAT_DESC") or ""
    zoning = attrs.get("ZONING") or ""
    stand = str(attrs.get("STAND_NO") or "")
    if cat in NONRES_HINTS or zoning in {"Reservation of land", "Public Garage", "Ecclesiastical"}:
        return "non_residential"
    if stand.startswith("RE/") or "Remainder" in stand:
        return "township_remainder"
    if cat == "Vacant Land":
        return "vacant"
    if cat == "Residential" and str(zoning).startswith("Residential"):
        return "residential"
    return "other"


def parcel_from_feature(feature: Mapping[str, Any]) -> dict[str, Any]:
    attrs = feature.get("attributes") or {}
    return {
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
        "street_address": attrs.get("STREET_ADDRESS"),
        "sg_id": attrs.get("SG_ID"),
        "objectid": attrs.get("OBJECTID"),
    }


def query_township(client: CoJPropertyClient, ext: int) -> dict[str, Any]:
    official = OFFICIAL_SUMMERSET_EXT[ext]
    township = client.township_record(official)
    stands = client.registered_stands(official)
    erven = [item for item in stands if (item.get("attributes") or {}).get("LAND_TYPE_NAME") == "Erven"]
    parcels = [parcel_from_feature(item) for item in erven]
    attrs = (township or {}).get("attributes") or {}
    return {
        "requested": f"SUMMERSET EXTENSION {ext}",
        "official_name": official,
        "membership_basis": "authoritative_coj_town_name_desc",
        "not_inferred_from_proximity": True,
        "source_layer": SOURCE_LAYER,
        "source_layer_name": SOURCE_LAYER_NAME,
        "source_mapserver": SOURCE_MAPSERVER,
        "township_found": township is not None,
        "township_status": attrs.get("STATUS_DESC"),
        "township_area_sqm": attrs.get("AREA_SQMT"),
        "source_parcel_count": len(erven),
        "source_stand_count_all_land_types": len(stands),
        "extent": geometry_extent(erven),
        "class_counts": dict(Counter(item["class"] for item in parcels)),
        "parcels": parcels,
        "features": erven,
    }


def pass1_filter_reasons(item: Mapping[str, Any]) -> list[str]:
    reasons = []
    if item.get("land_type") != "Erven":
        reasons.append("not_erven")
    if item.get("class") in {"non_residential"}:
        reasons.append("non_residential")
    if (item.get("area_sqm") or 0) >= 8000:
        reasons.append("area_sqm>=8000")
    if not item.get("geometry"):
        reasons.append("missing_geometry")
    if not item.get("stand_number"):
        reasons.append("missing_stand_number")
    if str(item.get("stand_number") or "").startswith("RE/"):
        reasons.append("RE_remainder")
    return reasons


def extension_inclusion_stats(parcels: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    excluded = []
    pass1_rows = []
    for item in parcels:
        reasons = pass1_filter_reasons(item)
        if reasons:
            excluded.append(
                {
                    "stand_number": item.get("stand_number"),
                    "property_id": item.get("property_id"),
                    "class": item.get("class"),
                    "area_sqm": item.get("area_sqm"),
                    "reasons": reasons,
                }
            )
        else:
            pass1_rows.append(item)
    unique: dict[Any, Mapping[str, Any]] = {}
    duplicate_groups: dict[Any, list[str]] = defaultdict(list)
    for item in pass1_rows:
        key = item.get("property_id") if item.get("property_id") is not None else item.get("stand_number")
        duplicate_groups[key].append(str(item.get("stand_number")))
        unique[key] = item
    duplicate_property_ids = {
        str(key): stands for key, stands in duplicate_groups.items() if len(stands) > 1
    }
    return {
        "source_parcels": len(parcels),
        "pass1_rows_before_dedup": len(pass1_rows),
        "included_unique_properties": len(unique),
        "duplicate_property_id_groups": duplicate_property_ids,
        "duplicate_gis_rows_collapsed": len(pass1_rows) - len(unique),
        "excluded_count": len(excluded),
        "excluded_reason_counts": dict(Counter("|".join(row["reasons"]) for row in excluded)),
        "excluded": excluded,
        "class_counts_source": dict(Counter(item.get("class") for item in parcels)),
        "residential_identified": sum(1 for item in parcels if item.get("class") in {"residential", "vacant"}),
    }


def _bbox_iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ix0, iy0 = max(a[0], b[0]), max(a[1], b[1])
    ix1, iy1 = min(a[2], b[2]), min(a[3], b[3])
    iw, ih = max(0.0, ix1 - ix0), max(0.0, iy1 - iy0)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    return inter / max(area_a + area_b - inter, 1e-18)


def geometry_quality_report(pass1: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    ids = [row.get("property_id") for row in pass1]
    duplicate_ids = [pid for pid, n in Counter(ids).items() if n > 1]
    bboxes = []
    missing_geom = 0
    for row in pass1:
        bbox = parcel_bbox(row.get("geometry"))
        if bbox is None:
            missing_geom += 1
        bboxes.append((row, bbox))
    overlaps = []
    for i, (left, lb) in enumerate(bboxes):
        if lb is None:
            continue
        for right, rb in bboxes[i + 1 :]:
            if rb is None:
                continue
            iou = _bbox_iou(lb, rb)
            if iou < 0.02:
                continue
            if left.get("property_id") == right.get("property_id"):
                continue
            overlaps.append(
                {
                    "stand_a": left.get("stand_number"),
                    "stand_b": right.get("stand_number"),
                    "township_a": left.get("township"),
                    "township_b": right.get("township"),
                    "property_id_a": left.get("property_id"),
                    "property_id_b": right.get("property_id"),
                    "bbox_iou": round(iou, 4),
                }
            )
    by_town = defaultdict(list)
    for row, bbox in bboxes:
        if bbox is not None:
            by_town[str(row.get("township"))].append(bbox)
    town_extents = {}
    for town, boxes in by_town.items():
        town_extents[town] = {
            "min_longitude": min(b[0] for b in boxes),
            "min_latitude": min(b[1] for b in boxes),
            "max_longitude": max(b[2] for b in boxes),
            "max_latitude": max(b[3] for b in boxes),
        }
    centroid_outside = []
    for row, bbox in bboxes:
        if bbox is None:
            continue
        town = str(row.get("township"))
        own = town_extents.get(town)
        if own is None:
            continue
        cx = (bbox[0] + bbox[2]) / 2.0
        cy = (bbox[1] + bbox[3]) / 2.0
        pad = 0.0003
        if not (
            own["min_longitude"] - pad <= cx <= own["max_longitude"] + pad
            and own["min_latitude"] - pad <= cy <= own["max_latitude"] + pad
        ):
            centroid_outside.append({"stand_number": row.get("stand_number"), "township": town})
    return {
        "pass1_unique": len(pass1),
        "duplicate_property_ids_after_pass1": duplicate_ids,
        "missing_geometry": missing_geom,
        "overlapping_bbox_pairs_iou_ge_0_02": overlaps[:40],
        "overlapping_bbox_pair_count": len(overlaps),
        "centroids_outside_own_township_extent": centroid_outside,
        "cross_township_stand_numbers": _cross_township_stands(pass1),
    }


def _cross_township_stands(pass1: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_stand: dict[str, set[str]] = defaultdict(set)
    for row in pass1:
        by_stand[str(row.get("stand_number"))].add(str(row.get("township")))
    return [
        {"stand_number": stand, "townships": sorted(towns)}
        for stand, towns in sorted(by_stand.items())
        if len(towns) > 1
    ]


def compare_to_frozen_001(complete_parcels: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not FROZEN_001_PATH.is_file():
        return {"frozen_001_present": False}
    frozen = json.loads(FROZEN_001_PATH.read_text(encoding="utf-8"))
    frozen_pass1 = {row.get("property_id"): row for row in pass1_parcels(frozen)}
    complete_by_pid = {row.get("property_id"): row for row in complete_parcels}
    shared = sorted(set(frozen_pass1) & set(complete_by_pid), key=lambda k: str(k))
    geometry_changed = []
    township_changed = []
    for pid in shared:
        a, b = frozen_pass1[pid], complete_by_pid[pid]
        if geometry_sha256(a.get("geometry")) != geometry_sha256(b.get("geometry")):
            geometry_changed.append(str(a.get("stand_number")))
        if a.get("township") != b.get("township"):
            township_changed.append(str(a.get("stand_number")))
    only_001 = sorted(
        str(frozen_pass1[pid].get("stand_number")) for pid in frozen_pass1 if pid not in complete_by_pid
    )
    only_002 = sorted(
        str(complete_by_pid[pid].get("stand_number"))
        for pid in complete_by_pid
        if pid not in frozen_pass1
    )
    return {
        "frozen_001_present": True,
        "frozen_001_unique": len(frozen_pass1),
        "shared_property_ids": len(shared),
        "geometry_changed_stands": geometry_changed,
        "township_changed_stands": township_changed,
        "only_in_frozen_001": only_001,
        "only_in_complete_002": only_002,
        "frozen_001_bytes_untouched": True,
    }


def native15_coverage_plan(
    dataset: Mapping[str, Any],
    *,
    estate_id: str = COMPLETE_CARLSWALD_NORTH,
) -> dict[str, Any]:
    from backend.gis.estate_ags_matching.estate_property_inventory_v1 import (
        intersecting_tile_ids,
        tile_grid_records,
    )

    extent = dataset.get("extent") or {}
    tiles = tile_grid_records(extent, profile_id="native15", year=2023)
    parcels = pass1_parcels(dataset)
    by_town: dict[str, set[str]] = defaultdict(set)
    missing_geom = 0
    for parcel in parcels:
        hits = intersecting_tile_ids(parcel.get("geometry"), tiles, pad_metres=PADDING_METRES)
        if not hits:
            missing_geom += 1
        by_town[str(parcel.get("township"))].update(hits)
    cache = cache_root_for(estate_id, "native15")
    crop_dir = crop_dir_for(estate_id, "native15")
    present = 0
    for tile in tiles:
        path = cache / f"{tile['tile_id']}.jpg"
        if path.is_file() and path.stat().st_size > 1000:
            present += 1
    return {
        "profile": CACHE_PROFILES["native15"].profile_id,
        "tile_metres": CACHE_PROFILES["native15"].tile_metres,
        "metres_per_pixel": CACHE_PROFILES["native15"].metres_per_pixel,
        "grid_tiles": len(tiles),
        "tiles_on_disk": present,
        "crop_dir": str(crop_dir),
        "cache_dir": str(cache),
        "pass1_parcels_with_no_intersecting_tile": missing_geom,
        "tiles_intersecting_by_township": {k: len(v) for k, v in sorted(by_town.items())},
        "all_pass1_have_tile_intersection": missing_geom == 0 and bool(parcels),
    }


def build_complete_dataset(client: CoJPropertyClient | None = None) -> dict[str, Any]:
    client = client or CoJPropertyClient()
    township_reports = []
    all_parcels: list[dict[str, Any]] = []
    all_features: list[dict[str, Any]] = []
    per_extension = {}
    for ext in COMPLETE_EXTENSIONS:
        report = query_township(client, ext)
        parcels = report.pop("parcels")
        features = report.pop("features")
        stats = extension_inclusion_stats(parcels)
        report.update(
            {
                "residential_erven_identified": stats["residential_identified"],
                "exclusions": {
                    "count": stats["excluded_count"],
                    "reason_counts": stats["excluded_reason_counts"],
                    "rows": stats["excluded"],
                },
                "duplicate_handling": {
                    "method": "GIS pass 1 then unique property_id last-wins (same as frozen 001 / production ranking)",
                    "duplicate_property_id_groups": stats["duplicate_property_id_groups"],
                    "duplicate_gis_rows_collapsed": stats["duplicate_gis_rows_collapsed"],
                },
                "final_unique_property_count": stats["included_unique_properties"],
                "source_parcels": stats["source_parcels"],
                "pass1_rows_before_dedup": stats["pass1_rows_before_dedup"],
                "gis_geometry_coverage": {
                    "source_parcels_with_rings": sum(1 for item in parcels if (item.get("geometry") or {}).get("rings")),
                    "source_parcel_count": len(parcels),
                    "extent": report.get("extent"),
                },
            }
        )
        township_reports.append(report)
        per_extension[report["official_name"]] = {
            "source_parcels": stats["source_parcels"],
            "included_unique_properties": stats["included_unique_properties"],
            "pass1_rows_before_dedup": stats["pass1_rows_before_dedup"],
            "excluded": stats["excluded_count"],
        }
        all_parcels.extend(parcels)
        all_features.extend(features)

    combined = geometry_extent(all_features)
    gated = client.gated_community("Carlswald North Estate")
    gated_extent = geometry_extent([gated]) if gated else None
    classes = dict(Counter(item["class"] for item in all_parcels))
    payload = {
        "dataset_id": COMPLETE_CARLSWALD_NORTH,
        "version": "carlswald_north_complete_ext_3_6_13_v1",
        "townships": [OFFICIAL_SUMMERSET_EXT[ext] for ext in COMPLETE_EXTENSIONS],
        "excluded_townships": [
            "CARLSWALD ESTATE",
            "CARLSWALD ESTATE EXT.1",
            "CARLSWALD ESTATE EXT.21",
            "CARLSWALD ESTATE EXT.64",
        ],
        "summerset_ext_2": "not_present_in_coj_gis",
        "membership_basis": "authoritative CoJ TOWN_NAME_DESC on Property/MapServer layer 8 REGISTERED_STANDS",
        "not_inferred_from_proximity": True,
        "source_layer": SOURCE_LAYER,
        "source_layer_name": SOURCE_LAYER_NAME,
        "source_mapserver": SOURCE_MAPSERVER,
        "township_reports": [{k: v for k, v in row.items() if k != "exclusions"} | {
            "exclusions": {
                "count": row["exclusions"]["count"],
                "reason_counts": row["exclusions"]["reason_counts"],
            }
        } for row in township_reports],
        "parcel_count": len(all_parcels),
        "extent": combined,
        "gated_carlswald_north_estate_extent": gated_extent,
        "class_counts": classes,
        "per_extension": per_extension,
        "parcels": all_parcels,
        "frozen_001_kept_intact": True,
        "frozen_001_dataset_id": FROZEN_CARLSWALD_NORTH_001,
    }
    unique = pass1_parcels(payload)
    payload["geometry_quality"] = geometry_quality_report(unique)
    payload["compare_to_frozen_001"] = compare_to_frozen_001(unique)
    payload["pass1_unique_total"] = len(unique)
    payload["native15_coverage_plan"] = native15_coverage_plan(payload)
    # Keep bulky exclusion row lists out of the GIS JSON; they live in the freeze report.
    payload["_exclusion_rows"] = {
        row["official_name"]: row["exclusions"]["rows"] for row in township_reports
    }
    return payload


def write_complete_dataset(payload: Mapping[str, Any], path: Path | None = None) -> Path:
    dest = path or COMPLETE_002_PATH
    dest.parent.mkdir(parents=True, exist_ok=True)
    stored = dict(payload)
    stored.pop("_exclusion_rows", None)
    dest.write_text(json.dumps(stored), encoding="utf-8")
    return dest


def freeze_summary_table(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = []
    total_source = 0
    total_unique = 0
    for ext in COMPLETE_EXTENSIONS:
        name = OFFICIAL_SUMMERSET_EXT[ext]
        stats = (payload.get("per_extension") or {}).get(name) or {}
        source = int(stats.get("source_parcels") or 0)
        unique = int(stats.get("included_unique_properties") or 0)
        total_source += source
        total_unique += unique
        rows.append({"extension": f"EXT.{ext}", "official_name": name, "source_parcels": source, "included_unique_properties": unique})
    rows.append(
        {
            "extension": "TOTAL",
            "official_name": "SUMMERSET EXT.3+6+13",
            "source_parcels": total_source,
            "included_unique_properties": int(payload.get("pass1_unique_total") or total_unique),
        }
    )
    # Unique total may be < sum if any cross-extension property_id collision.
    return rows
