"""Pool inventory NO vs UNKNOWN safety. Does not rewrite PR #28 freeze."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from backend.gis.estate_ags_matching.estate_property_inventory_v1 import (
    ALGORITHM_VERSION,
    INVENTORY_REVISION,
    classify_pool_from_os,
)
from backend.gis.estate_ags_matching.listing_pool_gate_v1 import (
    apply_listing_pool_gate,
    is_confident_pool_no,
    survives_listing_pool_gate,
)
from backend.gis.estate_ags_matching.pool_observability_v1 import (
    PoolObservability,
    assess_pool_observability,
    observability_from_crop,
)

ROOT = Path(__file__).resolve().parents[1]
OS_DIR = ROOT / "data/investigations/object_segmentation_v1/carlswald_north/json"
FREEZE = ROOT / "data/investigations/blind_117170887_complete_estate/freeze.json"
SHA = ROOT / "data/investigations/blind_117170887_complete_estate/freeze.sha256"
INVENTORY_002 = ROOT / "data/estate_inventory/carlswald_north_corrected_002/current.jsonl"
INVENTORY_001 = ROOT / "data/estate_inventory/carlswald_north_corrected_001/current.jsonl"


def _os(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _adequate():
    return PoolObservability(
        adequate_for_absence=True,
        crop_present=True,
        imagery_quality_ok=True,
        backyard_observable=True,
        canopy_occludes=False,
        shadow_occludes=False,
        roof_occludes=False,
        visible_open_fraction=0.65,
        canopy_fraction=0.08,
        shadow_fraction=0.06,
        roof_fraction=0.25,
        yard_pixels=6000,
        parcel_pixels=9000,
        flags=["pool_observability_adequate"],
        reason=None,
    )


def _rgb(color, size=160):
    arr = np.zeros((size, size, 3), dtype=np.uint8)
    arr[:] = color
    return arr


def test_freeze_hash_untouched():
    recorded = SHA.read_text(encoding="utf-8").strip()
    assert recorded == "96a66c8b240d8cab317d861d94582f1ba0bec84531c876fba4aaf090b4e82aa3"
    assert hashlib.sha256(FREEZE.read_bytes()).hexdigest() == recorded
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    assert [row["stand_number"] for row in freeze["ranking"]["top20"][:5]] == ["545", "868", "568", "572", "897"]


def test_frozen_inventories_bytes_untouched():
    # Overlay is a new path; 001/002 must remain the pre-fix bytes.
    assert INVENTORY_002.is_file()
    assert INVENTORY_001.is_file()
    rows = [json.loads(line) for line in INVENTORY_002.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 400
    row_641 = next(row for row in rows if str(row["stand_number"]) == "641")
    assert row_641["pool_status"] == "NO"


def test_stand_641_no_pool_candidate_is_unknown_without_observability():
    payload = _os(OS_DIR / "641.json")
    assert "no_pool_candidate" in payload["pool"]["notes"]
    result = classify_pool_from_os(payload)
    assert result.pool_status == "UNKNOWN"
    assert "no_pool_candidate_insufficient_observability" in result.diagnostic_flags
    canopy = classify_pool_from_os(
        payload,
        observability=PoolObservability(
            adequate_for_absence=False,
            crop_present=True,
            imagery_quality_ok=True,
            backyard_observable=False,
            canopy_occludes=True,
            shadow_occludes=False,
            roof_occludes=False,
            visible_open_fraction=0.1,
            canopy_fraction=0.62,
            shadow_fraction=0.1,
            roof_fraction=0.3,
            yard_pixels=5000,
            parcel_pixels=8000,
            flags=["pool_observability_inadequate", "canopy_occludes_likely_pool_area"],
            reason="canopy_occlusion",
        ),
    )
    assert canopy.pool_status == "UNKNOWN"
    assert canopy.pool_status != "NO"


def test_visible_parcel_genuine_no_pool_stays_no():
    vacant_like = {
        "pool": {"status": "UNKNOWN", "notes": ["no_pool_candidate"], "geometry": {"present": False}, "clip": {}},
        "building": {"status": "CONFIRMED", "geometry": {"present": True, "area_m2": 400}},
        "spatial": {"n_building_masses": 1},
    }
    result = classify_pool_from_os(vacant_like, observability=_adequate())
    assert result.pool_status == "NO"
    assert "pool_observability_adequate" in result.diagnostic_flags
    assert is_confident_pool_no(
        {
            "pool_status": "NO",
            "algorithm_version": ALGORITHM_VERSION,
            "diagnostic_flags": result.diagnostic_flags,
        }
    )


def test_confirmed_pool_remains_yes():
    payload = _os(OS_DIR / "677.json") if (OS_DIR / "677.json").is_file() else None
    if payload is None:
        payload = {
            "pool": {
                "status": "CONFIRMED",
                "notes": ["fastsam+clip"],
                "geometry": {"present": True, "area_m2": 40, "centroid_x": 0.3, "centroid_y": 0.3},
                "contour": [[0.2, 0.2], [0.4, 0.2], [0.4, 0.35], [0.2, 0.35], [0.2, 0.2]],
                "clip": {"pool": 0.95},
                "score": 0.95,
            },
            "building": {"status": "CONFIRMED", "geometry": {"present": True, "area_m2": 400}},
            "spatial": {"n_building_masses": 1, "pool": {"centroid_parcel": [0.4, 0.3]}},
        }
    assert classify_pool_from_os(payload).pool_status == "YES"


def test_dark_teal_rejected_stays_unknown():
    payload = _os(OS_DIR / "370.json")
    result = classify_pool_from_os(payload, observability=_adequate())
    assert payload["pool"]["status"] == "REJECTED"
    assert result.pool_status == "UNKNOWN"
    assert result.pool_status != "NO"


def test_neighbour_pool_outside_parcel_is_not_yes():
    for stand in ("408", "612"):
        result = classify_pool_from_os(_os(OS_DIR / f"{stand}.json"))
        assert result.pool_status != "YES"


def test_canopy_image_is_not_adequate_for_absence():
    rgb = _rgb((18, 72, 22))
    parcel = np.ones((160, 160), dtype=bool)
    building = np.zeros((160, 160), dtype=bool)
    building[40:90, 40:90] = True
    obs = assess_pool_observability(rgb, parcel_mask=parcel, building_mask=building)
    assert obs.canopy_occludes or not obs.adequate_for_absence
    assert obs.adequate_for_absence is False


def test_open_paved_yard_is_adequate_for_absence():
    rgb = _rgb((176, 168, 150))
    parcel = np.ones((160, 160), dtype=bool)
    building = np.zeros((160, 160), dtype=bool)
    building[20:70, 20:80] = True
    obs = assess_pool_observability(rgb, parcel_mask=parcel, building_mask=building)
    assert obs.adequate_for_absence is True
    vacant = {
        "pool": {"status": "UNKNOWN", "notes": ["no_pool_candidate"], "geometry": {"present": False}},
        "building": {"status": "CONFIRMED", "geometry": {"present": True, "area_m2": 400}},
        "spatial": {"n_building_masses": 1},
    }
    assert classify_pool_from_os(vacant, observability=obs).pool_status == "NO"


def test_shadow_and_roof_obstruction_are_unknown():
    vacant = {
        "pool": {"status": "UNKNOWN", "notes": ["no_pool_candidate"], "geometry": {"present": False}},
        "building": {"status": "CONFIRMED", "geometry": {"present": True, "area_m2": 400}},
        "spatial": {"n_building_masses": 1},
    }
    shadow = assess_pool_observability(
        _rgb((8, 8, 10)),
        parcel_mask=np.ones((160, 160), dtype=bool),
        building_mask=np.zeros((160, 160), dtype=bool),
    )
    assert shadow.adequate_for_absence is False
    assert classify_pool_from_os(vacant, observability=shadow).pool_status == "UNKNOWN"
    roof_mask = np.ones((160, 160), dtype=bool)
    roof_mask[150:] = False
    roof = assess_pool_observability(
        _rgb((176, 168, 150)),
        parcel_mask=np.ones((160, 160), dtype=bool),
        building_mask=roof_mask,
    )
    assert roof.roof_occludes or roof.yard_pixels < 400
    assert classify_pool_from_os(vacant, observability=roof).pool_status == "UNKNOWN"


def test_pool_gate_keeps_unknown_and_drops_qualified_no():
    records = [
        {"parcel_id": "yes", "stand_number": "yes", "pool_status": "YES"},
        {
            "parcel_id": "641",
            "stand_number": "641",
            "pool_status": "UNKNOWN",
            "algorithm_version": ALGORITHM_VERSION,
            "diagnostic_flags": ["no_pool_candidate_insufficient_observability"],
        },
        {
            "parcel_id": "no",
            "stand_number": "no",
            "pool_status": "NO",
            "algorithm_version": ALGORITHM_VERSION,
            "diagnostic_flags": ["no_in_parcel_candidate_after_ok_os", "pool_observability_adequate"],
        },
        {
            "parcel_id": "fake-no",
            "stand_number": "fake-no",
            "pool_status": "NO",
            "algorithm_version": ALGORITHM_VERSION,
            "diagnostic_flags": ["no_pool_candidate_insufficient_observability", "pool_observability_inadequate"],
        },
    ]
    result = apply_listing_pool_gate(records, records, "YES")
    survivors = {row["stand_number"] for row in result.survivors}
    assert "yes" in survivors
    assert "641" in survivors
    assert "fake-no" in survivors
    assert "no" not in survivors
    assert survives_listing_pool_gate("UNKNOWN", "YES") is True
    assert survives_listing_pool_gate("NO", "YES") is False


def test_revision_is_1_1_0_and_colour_not_in_inventory():
    assert INVENTORY_REVISION == "1.1.0"
    assert "1.1.0" in ALGORITHM_VERSION
    inventory = (ROOT / "backend/gis/estate_ags_matching/estate_property_inventory_v1.py").read_text(encoding="utf-8")
    gate = (ROOT / "backend/gis/estate_ags_matching/listing_pool_gate_v1.py").read_text(encoding="utf-8")
    for src in (inventory, gate):
        assert "COLOR_BGR2HSV" not in src
        assert "V2_WEIGHTS" not in src


def test_missing_crop_observability_is_unknown(tmp_path: Path):
    obs = observability_from_crop(tmp_path / "missing.jpg")
    assert obs.adequate_for_absence is False
    vacant = {
        "pool": {"status": "UNKNOWN", "notes": ["no_pool_candidate"], "geometry": {"present": False}},
        "building": {"status": "CONFIRMED", "geometry": {"present": True, "area_m2": 400}},
        "spatial": {"n_building_masses": 1},
    }
    assert classify_pool_from_os(vacant, observability=obs).pool_status == "UNKNOWN"


def test_overlay_641_is_unknown_and_listing_rerun_keeps_it():
    overlay = ROOT / "data/estate_inventory/carlswald_north_corrected_002_pool_obs_v1_1_0/current.jsonl"
    rerun = ROOT / "data/investigations/pool_inventory_no_unknown_safety_v1/listing_rerun.json"
    assert overlay.is_file()
    assert rerun.is_file()
    rows = [json.loads(line) for line in overlay.read_text(encoding="utf-8").splitlines() if line.strip()]
    by_status = {"YES": 0, "NO": 0, "UNKNOWN": 0}
    for row in rows:
        by_status[row["pool_status"]] += 1
    row_641 = next(row for row in rows if str(row["stand_number"]) == "641")
    assert len(rows) == 400
    assert by_status == {"YES": 118, "NO": 33, "UNKNOWN": 249}
    assert row_641["pool_status"] == "UNKNOWN"
    assert "no_pool_candidate_insufficient_observability" in row_641["diagnostic_flags"]
    payload = json.loads(rerun.read_text(encoding="utf-8"))
    assert payload["A_parcels_before_pool_gate"] == 400
    assert payload["D_stand_641_survives_pool_gate"] is True
    assert payload["E_corner_gate_641"]["survives"] is True
    assert payload["E_corner_gate_641"]["parcel_corner"] == "UNKNOWN"
    assert payload["F_scoring_eligible"] is True
    assert payload["G_rank"] == 75
    assert payload["H_unranked_reason"] is None
    assert payload["next_bottleneck"] == "ESTATE_POOL_EXTRACTION_MISSING_CONTOUR"
    assert payload["pass"] is True
    assert payload["freeze_modified"] is False
    assert payload["stand_641_score_row"]["shape_v2"] is None
    assert payload["stand_641_score_row"]["os_high_conf_pool"] is False

