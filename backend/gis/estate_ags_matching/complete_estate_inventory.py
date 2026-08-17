"""Complete Carlswald North inventory (EXT.3+6+13) with frozen-001 reuse.

Does not modify ``carlswald_north_corrected_001`` inventory, OS v1, FastSAM
configuration, native15 profile, ranking, or classification semantics.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

from backend.gis.carlswald_north_complete import COMPLETE_002_PATH
from backend.gis.dataset_registry import COMPLETE_CARLSWALD_NORTH, FROZEN_CARLSWALD_NORTH_001
from backend.gis.estate_ags_matching.ags_native15_raw_proof import (
    covering_tile,
    crop_parcel_from_tile,
    download_native15_tile,
    native15_tile_grid,
    parcel_bbox,
)
from backend.gis.estate_ags_matching.estate_property_inventory_v1 import (
    ALGORITHM_VERSION,
    DEFAULT_OS_DIR,
    SEGMENTATION_SOURCE_VERSION,
    EstateInventoryStore,
    ScanStats,
    _default_segment,
    _load_crop_bgr,
    _load_os_payload,
    _os_source_hash,
    build_record,
    classify_pool_from_os,
    compute_imagery_fingerprint,
    crop_path_for,
    geometry_sha256,
    intersecting_tile_ids,
    load_inventory_records,
    os_json_path_for,
    parcel_id_of,
    pass1_parcels,
    safe_stand,
    utc_now,
)
from backend.gis.estate_ags_matching.listing_pool_gate_v1 import apply_listing_pool_gate
from backend.imagery.estate_tiles import cache_root_for, crop_dir_for

REPO_ROOT = Path(__file__).resolve().parents[3]
FROZEN_001_INVENTORY = REPO_ROOT / "data" / "estate_inventory" / FROZEN_CARLSWALD_NORTH_001
COMPLETE_OS_DIR = (
    REPO_ROOT / "data" / "investigations" / "object_segmentation_v1" / "carlswald_north_complete" / "json"
)
INVESTIGATION_OUT = (
    REPO_ROOT / "data" / "investigations" / "estate_property_inventory_v1" / "carlswald_north_complete"
)


def load_complete_dataset(path: Path | None = None) -> dict[str, Any]:
    return json.loads((path or COMPLETE_002_PATH).read_text(encoding="utf-8"))


def frozen_001_index(root: Path | None = None) -> dict[str, dict[str, Any]]:
    records = load_inventory_records(FROZEN_CARLSWALD_NORTH_001, root=root)
    index: dict[str, dict[str, Any]] = {}
    for row in records:
        pid = row.get("property_id")
        if pid is not None:
            index[str(pid)] = row
    return index


def fastsam_importable() -> bool:
    try:
        import torch  # noqa: F401
        import ultralytics  # noqa: F401
        from backend.vision.clip_encoder import load_clip  # noqa: F401
        from backend.vision.object_segmentation import FASTSAM_WEIGHTS

        return FASTSAM_WEIGHTS.is_file() and FASTSAM_WEIGHTS.stat().st_size > 1_000_000
    except Exception:
        return False


def _with_tile_id(tiles: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for tile in tiles:
        row = dict(tile)
        row["tile_id"] = str(row.get("tile_id") or row.get("stem"))
        row["stem"] = str(row.get("stem") or row["tile_id"])
        out.append(row)
    return out


def _tile_by_id(tiles: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    return {str(tile.get("tile_id") or tile.get("stem")): tile for tile in tiles}


def download_tiles_for_parcels(
    *,
    estate_id: str,
    extent: Mapping[str, float],
    parcels: Sequence[Mapping[str, Any]],
    repo_root: Path | None = None,
) -> dict[str, Any]:
    root = Path(repo_root) if repo_root is not None else REPO_ROOT
    tiles = _with_tile_id(native15_tile_grid(extent))
    needed: set[str] = set()
    for parcel in parcels:
        hits = intersecting_tile_ids(parcel.get("geometry"), tiles)
        needed.update(hits)
    cache = cache_root_for(estate_id, "native15", repo_root=root)
    cache.mkdir(parents=True, exist_ok=True)
    by_id = _tile_by_id(tiles)
    reused = downloaded = failed = 0
    failed_ids = []
    for tile_id in sorted(needed):
        tile = dict(by_id[tile_id])
        dest = cache / f"{tile_id}.jpg"
        tile["path"] = dest
        before = dest.is_file() and dest.stat().st_size > 1000
        try:
            info = download_native15_tile(tile, dest)
            if info.get("reused_local_file") or before:
                reused += 1
            else:
                downloaded += 1
        except Exception as exc:  # noqa: BLE001
            failed += 1
            failed_ids.append(f"{tile_id}: {exc}")
    return {
        "tiles_required": len(needed),
        "tiles_reused": reused,
        "tiles_downloaded": downloaded,
        "tiles_failed": failed,
        "failed_ids": failed_ids,
        "cache_dir": str(cache),
    }


def crop_parcels(
    *,
    estate_id: str,
    extent: Mapping[str, float],
    parcels: Sequence[Mapping[str, Any]],
    repo_root: Path | None = None,
) -> dict[str, Any]:
    root = Path(repo_root) if repo_root is not None else REPO_ROOT
    tiles = _with_tile_id(native15_tile_grid(extent))
    cache = cache_root_for(estate_id, "native15", repo_root=root)
    crop_dir = crop_dir_for(estate_id, "native15", repo_root=root)
    crop_dir.mkdir(parents=True, exist_ok=True)
    cropped = reused = failed = 0
    for parcel in parcels:
        dest = crop_dir / f"{safe_stand(str(parcel['stand_number']))}_ags_aerial.jpg"
        if dest.is_file() and dest.stat().st_size > 1000:
            reused += 1
            continue
        bbox = parcel_bbox(parcel.get("geometry"))
        if bbox is None:
            failed += 1
            continue
        tile = dict(covering_tile(tiles, *bbox))
        tile["path"] = cache / f"{tile['stem']}.jpg"
        if crop_parcel_from_tile(tile, parcel["geometry"], dest):
            cropped += 1
        else:
            failed += 1
    return {
        "parcels": len(parcels),
        "crops_written": cropped,
        "crops_reused": reused,
        "crops_failed": failed,
        "crop_dir": str(crop_dir),
    }


def _copy_reused_record(
    prior: Mapping[str, Any],
    *,
    estate_id: str,
    parcel: Mapping[str, Any],
    fingerprint,
    timestamp: str,
) -> dict[str, Any]:
    record = dict(prior)
    record["estate_id"] = estate_id
    record["parcel_id"] = parcel_id_of(parcel)
    record["stand_number"] = str(parcel.get("stand_number") or prior.get("stand_number"))
    record["township"] = parcel.get("township")
    record["property_id"] = parcel.get("property_id")
    record["parcel_geometry_ref"] = {
        "dataset_id": estate_id,
        "property_id": parcel.get("property_id"),
        "stand_number": record["stand_number"],
        "township": parcel.get("township"),
        "geometry_sha256": fingerprint.geometry_sha256,
    }
    record["reused"] = True
    record["fastsam_invoked"] = False
    record["scan_timestamp"] = prior.get("scan_timestamp") or timestamp
    flags = list(record.get("diagnostic_flags") or [])
    if "reused_from_frozen_001" not in flags:
        flags.append("reused_from_frozen_001")
    record["diagnostic_flags"] = sorted(set(flags))
    record["reused_from_estate_id"] = FROZEN_CARLSWALD_NORTH_001
    # Keep frozen imagery_version (native15 crop/OS fingerprint). 002's larger
    # tile grid would otherwise force a false rescan of unchanged parcels.
    return record


def build_complete_inventory(
    *,
    dataset: Mapping[str, Any] | None = None,
    store: EstateInventoryStore | None = None,
    frozen_root: Path | None = None,
    os_dir: Path | None = None,
    new_os_dir: Path | None = None,
    repo_root: Path | None = None,
    allow_fastsam: bool = True,
    download_new_tiles: bool = True,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    started = time.perf_counter()
    root = Path(repo_root) if repo_root is not None else REPO_ROOT
    dataset = dataset or load_complete_dataset()
    estate_id = COMPLETE_CARLSWALD_NORTH
    store = store or EstateInventoryStore(estate_id, root=root / "data" / "estate_inventory" / estate_id)
    os_dir = Path(os_dir) if os_dir is not None else DEFAULT_OS_DIR
    new_os_dir = Path(new_os_dir) if new_os_dir is not None else COMPLETE_OS_DIR
    parcels = pass1_parcels(dataset)
    prior = frozen_001_index(root=frozen_root)
    timestamp = utc_now()
    tiles = _with_tile_id(native15_tile_grid(dataset["extent"]))
    tile_cache = cache_root_for(estate_id, "native15", repo_root=root)

    new_parcels = []
    reused_parcels = []
    geometry_changed = []
    for parcel in parcels:
        pid = str(parcel.get("property_id"))
        geom = geometry_sha256(parcel.get("geometry"))
        existing = prior.get(pid)
        prior_geom = None if existing is None else (existing.get("parcel_geometry_ref") or {}).get("geometry_sha256")
        if existing and prior_geom == geom and existing.get("algorithm_version") == ALGORITHM_VERSION:
            reused_parcels.append(parcel)
        else:
            if existing and prior_geom != geom:
                geometry_changed.append(str(parcel.get("stand_number")))
            new_parcels.append(parcel)

    tile_stats = {"tiles_required": 0, "tiles_reused": 0, "tiles_downloaded": 0, "tiles_failed": 0}
    crop_stats = {"crops_written": 0, "crops_reused": 0, "crops_failed": 0}
    if download_new_tiles and new_parcels:
        tile_stats = download_tiles_for_parcels(
            estate_id=estate_id,
            extent=dataset["extent"],
            parcels=new_parcels,
            repo_root=root,
        )
        crop_stats = crop_parcels(
            estate_id=estate_id,
            extent=dataset["extent"],
            parcels=new_parcels,
            repo_root=root,
        )

    can_fastsam = bool(allow_fastsam and fastsam_importable())
    current: dict[str, dict[str, Any]] = {}
    stats = ScanStats(parcels_total=len(parcels))
    fastsam_runs = 0
    os_json_reused = 0
    missing = 0

    for parcel in reused_parcels:
        pid = parcel_id_of(parcel)
        crop = crop_path_for(estate_id, str(parcel["stand_number"]), repo_root=root)
        fingerprint = compute_imagery_fingerprint(
            geometry=parcel.get("geometry"),
            crop_path=crop,
            tiles=tiles,
            tile_cache_root=tile_cache,
        )
        current[pid] = _copy_reused_record(
            prior[str(parcel.get("property_id"))],
            estate_id=estate_id,
            parcel=parcel,
            fingerprint=fingerprint,
            timestamp=timestamp,
        )
        stats.parcels_reused += 1

    for parcel in new_parcels:
        pid = parcel_id_of(parcel)
        stand = str(parcel["stand_number"])
        crop = crop_path_for(estate_id, stand, repo_root=root)
        fingerprint = compute_imagery_fingerprint(
            geometry=parcel.get("geometry"),
            crop_path=crop,
            tiles=tiles,
            tile_cache_root=tile_cache,
        )
        os_path = os_json_path_for(stand, os_dir)
        new_path = os_json_path_for(stand, new_os_dir)
        os_payload = _load_os_payload(new_path) or _load_os_payload(os_path)
        extra_flags: list[str] = []
        fastsam_invoked = False
        segmentation_source = SEGMENTATION_SOURCE_VERSION
        if os_payload is not None and not fastsam_invoked:
            extra_flags.append("reused_os_v1_json")
            os_json_reused += 1
        elif can_fastsam and crop.is_file():
            bgr = _load_crop_bgr(crop)
            if bgr is None:
                extra_flags.append("crop_unreadable")
                os_payload = None
                segmentation_source = "unavailable"
                missing += 1
            else:
                os_payload = dict(_default_segment(bgr, stand, parcel.get("geometry") or {}))
                fastsam_invoked = True
                fastsam_runs += 1
                new_os_dir.mkdir(parents=True, exist_ok=True)
                new_path.write_text(json.dumps(os_payload), encoding="utf-8")
                extra_flags.append("processed_new_complete_parcel")
        else:
            extra_flags.append("missing_crop_and_os_json" if not crop.is_file() else "fastsam_unavailable")
            if not can_fastsam:
                extra_flags.append("fastsam_unavailable")
            segmentation_source = "unavailable"
            missing += 1
        if fastsam_invoked:
            stats.parcels_rescanned += 1
        else:
            stats.parcels_rescanned += 1
        classification = classify_pool_from_os(os_payload)
        record = build_record(
            estate_id=estate_id,
            parcel=parcel,
            fingerprint=fingerprint,
            classification=classification,
            scan_timestamp=timestamp,
            reused=False,
            segmentation_source=segmentation_source,
            fastsam_invoked=fastsam_invoked,
            extra_flags=extra_flags,
        )
        record["os_source_hash"] = _os_source_hash(os_payload)
        current[pid] = record
        store.append_history({**record, "history_event": "current"})

    stats.fastsam_runs = fastsam_runs
    for record in current.values():
        status = record.get("pool_status")
        if status == "YES":
            stats.yes += 1
        elif status == "NO":
            stats.no += 1
        else:
            stats.unknown += 1
    store.write_current(current)
    stats.runtime_s = time.perf_counter() - started
    summary = {
        "estate_id": estate_id,
        "parcels_total": len(parcels),
        "parcels_reused": stats.parcels_reused,
        "newly_processed": len(new_parcels),
        "rescanned": stats.parcels_rescanned,
        "fastsam_runs": fastsam_runs,
        "os_json_reused_for_new": os_json_reused,
        "missing_os_or_crop": missing,
        "geometry_changed_vs_001": geometry_changed,
        "fastsam_available": can_fastsam,
        "tile_stats": tile_stats,
        "crop_stats": crop_stats,
        "runtime_s": round(stats.runtime_s, 3),
        "yes": stats.yes,
        "no": stats.no,
        "unknown": stats.unknown,
        "algorithm_version": ALGORITHM_VERSION,
        "classification_semantics_unchanged": True,
    }
    store.write_manifest(
        {
            "schema_version": ALGORITHM_VERSION,
            "algorithm_version": ALGORITHM_VERSION,
            "estate_id": estate_id,
            "imagery_profile": "native15",
            "segmentation_source": SEGMENTATION_SOURCE_VERSION,
            "parcel_count": stats.parcels_total,
            "scan_timestamp": timestamp,
            "stats": stats.to_dict(),
            "complete_summary": summary,
            "frozen_001_reused": stats.parcels_reused,
        }
    )
    return current, summary


def gate_baselines(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    listing_yes = apply_listing_pool_gate(list(records), records, "YES")
    listing_no = apply_listing_pool_gate(list(records), records, "NO")
    listing_unk = apply_listing_pool_gate(list(records), records, "UNKNOWN")
    return {
        "listing_yes": _gate_block(listing_yes),
        "listing_no": _gate_block(listing_no),
        "listing_unknown": _gate_block(listing_unk),
    }


def _gate_block(result) -> dict[str, Any]:
    payload = result.to_dict()
    payload.pop("survivor_parcel_ids", None)
    payload.pop("removed_parcel_ids", None)
    return payload
