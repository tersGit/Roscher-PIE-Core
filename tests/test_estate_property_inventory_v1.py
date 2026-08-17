"""Estate Property Inventory v1 — persistence, reuse, semantics. No FastSAM."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from backend.gis.estate_ags_matching.estate_property_inventory_v1 import (
    ALGORITHM_VERSION,
    INVENTORY_VERSION,
    SEGMENTATION_SOURCE_VERSION,
    EstateInventoryStore,
    build_record,
    classify_pool_from_os,
    compute_imagery_fingerprint,
    intersecting_tile_ids,
    pass1_parcels,
    scan_estate_inventory,
    sha256_text,
    tile_grid_records,
)
from backend.gis.estate_ags_matching.listing_pool_gate_v1 import (
    apply_listing_pool_gate,
    filter_before_ranking,
    survives_listing_pool_gate,
)
from backend.gis.estate_ags_matching.os_scoring_v2 import V2_WEIGHTS_NO_BUILDING

ROOT = Path(__file__).resolve().parents[1]
OS_DIR = ROOT / "data/investigations/object_segmentation_v1/carlswald_north/json"
GIS_PATH = ROOT / "data/gis/carlswald_north_corrected_001.json"
FROZEN_OS_RANKING = ROOT / "data/investigations/os_v1_ranking_experiment/carlswald_north_116978058/latest.json"
FROZEN_V2 = ROOT / "data/investigations/os_scoring_v2/carlswald_north_116978058/latest.json"


def _extent():
    return {
        "min_longitude": 28.089918,
        "max_longitude": 28.102243,
        "min_latitude": -25.971732,
        "max_latitude": -25.963765,
    }


def _parcel(stand="100", property_id=1, lon=28.095, lat=-25.968):
    return {
        "stand_number": stand,
        "property_id": property_id,
        "township": "SUMMERSET EXT.6",
        "land_type": "Erven",
        "class": "residential",
        "area_sqm": 900,
        "geometry": {
            "rings": [[
                [lon, lat],
                [lon + 0.0004, lat],
                [lon + 0.0004, lat - 0.0004],
                [lon, lat - 0.0004],
                [lon, lat],
            ]]
        },
    }


def _dataset(parcels):
    return {"dataset_id": "test_estate", "extent": _extent(), "parcels": parcels}


def _os(status, notes=None, present=True, area=40.0, clip_pool=0.9, masses=1, bldg_area=400.0, bldg_status="CONFIRMED"):
    contour = [[0.2, 0.2], [0.4, 0.2], [0.4, 0.35], [0.2, 0.35], [0.2, 0.2]] if present else None
    return {
        "stand_number": "x",
        "version": "object_segmentation_v1",
        "pool": {
            "status": status,
            "score": clip_pool,
            "clip": {"pool": clip_pool, "roof": 0.05, "shadow": 0.05, "road": 0.05, "driveway": 0.05, "lawn": 0.05},
            "notes": notes or [],
            "geometry": {
                "present": present,
                "area_m2": area if present else None,
                "centroid_x": 0.3,
                "centroid_y": 0.28,
            },
            "contour": contour,
        },
        "building": {
            "status": bldg_status,
            "geometry": {"present": True, "area_m2": bldg_area},
        },
        "spatial": {"n_building_masses": masses, "pool": {"centroid_parcel": [0.4, 0.3]}},
    }


def _write_os(dir_path: Path, stand: str, payload: dict) -> None:
    dir_path.mkdir(parents=True, exist_ok=True)
    (dir_path / f"{stand}.json").write_text(json.dumps(payload), encoding="utf-8")


def test_inventory_persistence_and_reload(tmp_path: Path):
    store = EstateInventoryStore("test_estate", root=tmp_path)
    os_dir = tmp_path / "os"
    parcel = _parcel()
    _write_os(os_dir, "100", _os("CONFIRMED"))
    current, stats = scan_estate_inventory(
        estate_id="test_estate",
        dataset=_dataset([parcel]),
        store=store,
        os_dir=os_dir,
        repo_root=tmp_path,
        allow_fastsam=False,
        scan_timestamp="2026-08-17T00:00:00Z",
    )
    assert stats.parcels_total == 1
    assert stats.parcels_rescanned == 1
    assert stats.fastsam_runs == 0
    assert current[str(parcel["property_id"])]["pool_status"] == "YES"
    reloaded = store.load_current()
    assert reloaded[str(parcel["property_id"])]["pool_status"] == "YES"
    assert reloaded[str(parcel["property_id"])]["schema_version"].startswith(INVENTORY_VERSION)
    assert store.current_path.is_file()
    line = store.current_path.read_text(encoding="utf-8").strip()
    assert json.loads(line)["estate_id"] == "test_estate"


def test_unchanged_imagery_causes_reuse(tmp_path: Path):
    store = EstateInventoryStore("test_estate", root=tmp_path)
    os_dir = tmp_path / "os"
    parcel = _parcel()
    _write_os(os_dir, "100", _os("CONFIRMED"))
    kwargs = dict(
        estate_id="test_estate",
        dataset=_dataset([parcel]),
        store=store,
        os_dir=os_dir,
        repo_root=tmp_path,
        allow_fastsam=False,
        scan_timestamp="2026-08-17T00:00:00Z",
    )
    first, _ = scan_estate_inventory(**kwargs)
    before = store.current_path.read_bytes()
    second, stats = scan_estate_inventory(**kwargs)
    assert stats.parcels_reused == 1
    assert stats.parcels_rescanned == 0
    assert stats.fastsam_runs == 0
    assert store.current_path.read_bytes() == before
    assert second[str(parcel["property_id"])]["imagery_version"] == first[str(parcel["property_id"])]["imagery_version"]


def test_changed_imagery_causes_rescan(tmp_path: Path):
    store = EstateInventoryStore("test_estate", root=tmp_path)
    os_dir = tmp_path / "os"
    parcel = _parcel()
    _write_os(os_dir, "100", _os("CONFIRMED"))
    crop_dir = tmp_path / "data/visual_index/test_estate/_imagery_cache_native15"
    crop_dir.mkdir(parents=True)
    crop = crop_dir / "100_ags_aerial.jpg"
    crop.write_bytes(b"crop-v1")
    calls = []

    def segment(bgr, stand, geometry):
        calls.append(stand)
        return _os("CONFIRMED", clip_pool=0.95)

    kwargs = dict(
        estate_id="test_estate",
        dataset=_dataset([parcel]),
        store=store,
        os_dir=os_dir,
        repo_root=tmp_path,
        allow_fastsam=True,
        segment_fn=segment,
        scan_timestamp="2026-08-17T00:00:00Z",
    )
    scan_estate_inventory(**kwargs)
    assert calls == ["100"]
    calls.clear()
    scan_estate_inventory(**kwargs)
    assert calls == []
    crop.write_bytes(b"crop-v2-changed-bytes")
    _, stats = scan_estate_inventory(**kwargs)
    assert calls == ["100"]
    assert stats.parcels_rescanned == 1
    assert stats.parcels_reused == 0
    assert stats.fastsam_runs == 1


def test_changed_tile_rescans_only_intersecting_parcel(tmp_path: Path):
    store = EstateInventoryStore("test_estate", root=tmp_path)
    os_dir = tmp_path / "os"
    a = _parcel("A", 1, lon=28.0905, lat=-25.9712)
    b = _parcel("B", 2, lon=28.1010, lat=-25.9642)
    _write_os(os_dir, "A", _os("UNKNOWN", notes=["no_pool_candidate"]))
    _write_os(os_dir, "B", _os("CONFIRMED"))
    tiles = tile_grid_records(_extent())
    cache = tmp_path / "data/cache/ags_native15/test_estate"
    cache.mkdir(parents=True)
    for tile in tiles:
        (cache / f"{tile['tile_id']}.jpg").write_bytes(f"tile-{tile['tile_id']}-v1".encode())
    kwargs = dict(
        estate_id="test_estate",
        dataset=_dataset([a, b]),
        store=store,
        os_dir=os_dir,
        repo_root=tmp_path,
        allow_fastsam=False,
        scan_timestamp="2026-08-17T00:00:00Z",
    )
    first, _ = scan_estate_inventory(**kwargs)
    a_tiles = first[str(a["property_id"])]["tile_ids"]
    b_tiles = first[str(b["property_id"])]["tile_ids"]
    exclusive = [tid for tid in a_tiles if tid not in b_tiles]
    assert exclusive, "fixture parcels should not share every tile"
    (cache / f"{exclusive[0]}.jpg").write_bytes(b"tile-changed")
    _, stats = scan_estate_inventory(**kwargs)
    assert str(a["property_id"]) in {row["parcel_id"] for row in store.load_current().values()}
    assert stats.parcels_rescanned == 1
    assert stats.parcels_reused == 1
    assert exclusive[0] in stats.changed_tiles


def test_yes_no_unknown_semantics():
    yes = classify_pool_from_os(_os("CONFIRMED"))
    assert yes.pool_status == "YES"
    assert yes.pool_count == 1
    assert yes.unknown_reason is None
    probable = classify_pool_from_os(_os("PROBABLE", notes=["fastsam+clip"], clip_pool=0.45))
    assert probable.pool_status == "YES"
    rejected = classify_pool_from_os(_os("REJECTED", notes=["rejected_as_road_shadow_or_roof"], clip_pool=0.03))
    assert rejected.pool_status == "UNKNOWN"
    assert rejected.unknown_reason == "os_rejected_weak_evidence_not_absence"
    no = classify_pool_from_os(_os("UNKNOWN", notes=["no_pool_candidate"], present=False, clip_pool=0.0))
    assert no.pool_status == "NO"
    poor = classify_pool_from_os(
        _os("UNKNOWN", notes=["no_pool_candidate"], present=False, masses=3, bldg_area=130.0)
    )
    assert poor.pool_status == "UNKNOWN"
    assert poor.unknown_reason == "no_candidate_with_poor_segmentation"


def test_unknown_never_collapsed_into_no():
    for status, notes in (
        ("REJECTED", ["low_pool_evidence"]),
        ("REJECTED", ["rejected_as_road_shadow_or_roof"]),
        ("UNKNOWN", ["no_pool_candidate"]),
        ("PROBABLE", ["fastsam+clip", "partially_outside_parcel"]),
    ):
        present = status != "UNKNOWN"
        masses = 3 if notes == ["no_pool_candidate"] else 1
        area = 130 if notes == ["no_pool_candidate"] else 400
        result = classify_pool_from_os(
            _os(status, notes=notes, present=present, masses=masses, bldg_area=area)
        )
        if notes == ["no_pool_candidate"] and masses == 3:
            assert result.pool_status == "UNKNOWN"
        elif status == "REJECTED":
            assert result.pool_status == "UNKNOWN"


def test_dark_teal_rejected_is_unknown_not_no():
    payload = json.loads((OS_DIR / "370.json").read_text(encoding="utf-8"))
    result = classify_pool_from_os(payload)
    assert payload["pool"]["status"] == "REJECTED"
    assert result.pool_status == "UNKNOWN"
    assert result.pool_status != "NO"


def test_neighbour_pool_outside_parcel_is_not_yes():
    for stand in ("408", "612"):
        payload = json.loads((OS_DIR / f"{stand}.json").read_text(encoding="utf-8"))
        result = classify_pool_from_os(payload)
        assert result.pool_status != "YES"
    bleed = classify_pool_from_os(_os("CONFIRMED", notes=["fastsam+clip", "partially_outside_parcel"]))
    assert bleed.pool_status == "UNKNOWN"
    assert bleed.unknown_reason == "pool_partially_outside_parcel"


def test_historical_observation_retained_after_update(tmp_path: Path):
    store = EstateInventoryStore("test_estate", root=tmp_path)
    os_dir = tmp_path / "os"
    parcel = _parcel()
    crop_dir = tmp_path / "data/visual_index/test_estate/_imagery_cache_native15"
    crop_dir.mkdir(parents=True)
    crop = crop_dir / "100_ags_aerial.jpg"
    crop.write_bytes(b"imagery-A")
    _write_os(os_dir, "100", _os("UNKNOWN", notes=["no_pool_candidate"], present=False))
    scan_estate_inventory(
        estate_id="test_estate",
        dataset=_dataset([parcel]),
        store=store,
        os_dir=os_dir,
        repo_root=tmp_path,
        allow_fastsam=False,
        scan_timestamp="2026-01-01T00:00:00Z",
    )
    assert store.load_current()[str(parcel["property_id"])]["pool_status"] == "NO"
    crop.write_bytes(b"imagery-B")
    _write_os(os_dir, "100", _os("CONFIRMED"))
    scan_estate_inventory(
        estate_id="test_estate",
        dataset=_dataset([parcel]),
        store=store,
        os_dir=os_dir,
        repo_root=tmp_path,
        allow_fastsam=False,
        scan_timestamp="2026-06-01T00:00:00Z",
    )
    current = store.load_current()[str(parcel["property_id"])]
    assert current["pool_status"] == "YES"
    history = store.load_history(str(parcel["property_id"]))
    statuses = [row["pool_status"] for row in history]
    assert "NO" in statuses
    assert "YES" in statuses
    versions = {row["imagery_version"] for row in history}
    assert len(versions) == 2


def test_unknown_survives_both_listing_gates():
    records = [
        {"parcel_id": "1", "stand_number": "1", "pool_status": "YES"},
        {"parcel_id": "2", "stand_number": "2", "pool_status": "NO"},
        {"parcel_id": "3", "stand_number": "3", "pool_status": "UNKNOWN", "unknown_reason": "os_rejected_weak_evidence_not_absence"},
    ]
    for listing in ("YES", "NO", "UNKNOWN"):
        result = apply_listing_pool_gate(records, records, listing)
        survivor_ids = {row["parcel_id"] for row in result.survivors}
        assert "3" in survivor_ids
        assert survives_listing_pool_gate("UNKNOWN", listing) is True
    listing_yes = apply_listing_pool_gate(records, records, "YES")
    assert {row["parcel_id"] for row in listing_yes.survivors} == {"1", "3"}
    assert listing_yes.removed_confident_no == 1
    listing_no = apply_listing_pool_gate(records, records, "NO")
    assert {row["parcel_id"] for row in listing_no.survivors} == {"2", "3"}
    assert listing_no.removed_confident_yes == 1
    listing_unk = apply_listing_pool_gate(records, records, "UNKNOWN")
    assert listing_unk.total_survivors == 3
    assert listing_unk.pct_reduction == 0.0


def test_missing_inventory_is_unknown_and_survives():
    ranked = [{"stand_number": "999", "total_score": 0.4}]
    result = apply_listing_pool_gate(ranked, [], "YES")
    assert result.total_survivors == 1
    assert result.survivors[0]["inventory_pool_status"] == "UNKNOWN"


def test_gate_runs_before_ranking_and_does_not_rescore():
    candidates = [
        {"stand_number": "1", "total_score": 0.91, "pool_status": "YES"},
        {"stand_number": "2", "total_score": 0.88, "pool_status": "NO"},
        {"stand_number": "3", "total_score": 0.50, "pool_status": "UNKNOWN"},
    ]
    survivors = filter_before_ranking(candidates, candidates, "YES")
    assert [row["stand_number"] for row in survivors] == ["1", "3"]
    assert survivors[0]["total_score"] == 0.91
    assert survivors[1]["total_score"] == 0.50


def test_existing_ranking_outputs_remain_unchanged():
    os_rank = json.loads(FROZEN_OS_RANKING.read_text(encoding="utf-8"))
    assert os_rank["production_ranking_modified"] is False
    assert os_rank["evaluation"]["baseline_rank"] == 17
    assert os_rank["evaluation"]["baseline_score"] == 0.6659
    v2 = json.loads(FROZEN_V2.read_text(encoding="utf-8"))
    assert v2["production_ranking_modified"] is False
    assert V2_WEIGHTS_NO_BUILDING["pool_presence"] == 0.14
    assert V2_WEIGHTS_NO_BUILDING["shape_v2"] == 0.36
    assert 'SEGMENTATION_VERSION = "object_segmentation_v1"' in (
        ROOT / "backend/vision/object_segmentation.py"
    ).read_text(encoding="utf-8")
    production = (ROOT / "scripts/run_carlswald_north_corrected.py").read_text(encoding="utf-8")
    assert '"pool_geom": 0.30' in production
    assert "listing_pool_gate_v1" not in production
    inventory_src = (ROOT / "backend/gis/estate_ags_matching/estate_property_inventory_v1.py").read_text(encoding="utf-8")
    gate_src = (ROOT / "backend/gis/estate_ags_matching/listing_pool_gate_v1.py").read_text(encoding="utf-8")
    for src in (inventory_src, gate_src):
        assert "COLOR_BGR2HSV" not in src
        assert "combined_score" not in src
        assert "V2_WEIGHTS" not in src
        assert "116978058" not in src
        assert "370" not in src


def test_fingerprint_is_deterministic(tmp_path: Path):
    tiles = tile_grid_records(_extent())
    parcel = _parcel()
    a = compute_imagery_fingerprint(
        geometry=parcel["geometry"],
        crop_path=tmp_path / "missing.jpg",
        tiles=tiles,
        tile_cache_root=tmp_path,
    )
    b = compute_imagery_fingerprint(
        geometry=parcel["geometry"],
        crop_path=tmp_path / "missing.jpg",
        tiles=tiles,
        tile_cache_root=tmp_path,
    )
    assert a.digest == b.digest
    assert a.tile_ids
    assert intersecting_tile_ids(parcel["geometry"], tiles) == a.tile_ids


def test_pass1_matches_production_filter():
    dataset = json.loads(GIS_PATH.read_text(encoding="utf-8"))
    parcels = pass1_parcels(dataset)
    assert len(parcels) == 330
    assert ALGORITHM_VERSION.endswith(SEGMENTATION_SOURCE_VERSION)


def test_build_record_has_required_fields():
    from backend.gis.estate_ags_matching.estate_property_inventory_v1 import ImageryFingerprint

    parcel = _parcel()
    fingerprint = ImageryFingerprint(
        digest="abc",
        profile_id="native15",
        tile_ids=["tile_2023_native15_00_00"],
        tile_hashes={},
        crop_hash=None,
        geometry_sha256="def",
        missing_tiles=["tile_2023_native15_00_00"],
        crop_present=False,
    )
    classification = classify_pool_from_os(_os("CONFIRMED"))
    record = build_record(
        estate_id="carlswald_north_corrected_001",
        parcel=parcel,
        fingerprint=fingerprint,
        classification=classification,
        scan_timestamp="2026-08-17T00:00:00Z",
        reused=False,
        segmentation_source="object_segmentation_v1",
        fastsam_invoked=False,
    )
    for key in (
        "estate_id",
        "parcel_id",
        "stand_number",
        "parcel_geometry_ref",
        "imagery_profile",
        "imagery_version",
        "scan_timestamp",
        "pool_status",
        "pool_confidence",
        "pool_count",
        "pool_centroid",
        "pool_area_m2",
        "pool_bbox",
        "normalized_pool_contour",
        "segmentation_source",
        "diagnostic_flags",
        "unknown_reason",
    ):
        assert key in record
    assert record["extensible_attributes"]["roof_footprint"] is None
    assert sha256_text("x") == hashlib.sha256(b"x").hexdigest()
