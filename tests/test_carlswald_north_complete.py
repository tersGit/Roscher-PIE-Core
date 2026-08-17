"""Complete Carlswald North EXT.3+6+13 dataset and FastSAM-miss diagnostic.

Does not require FastSAM. Frozen 001 GIS/inventory bytes must remain unchanged.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from backend.gis.carlswald_north_complete import (
    COMPLETE_002_PATH,
    COMPLETE_CARLSWALD_NORTH,
    FROZEN_001_PATH,
    freeze_summary_table,
)
from backend.gis.coj_property import OFFICIAL_SUMMERSET_EXT
from backend.gis.dataset_registry import (
    FROZEN_CARLSWALD_NORTH_001,
    find_datasets_for_estate,
    require_active_dataset,
)
from backend.gis.estate_ags_matching.estate_property_inventory_v1 import pass1_parcels
from backend.gis.estate_ags_matching.fastsam_miss_diagnostic import MISS_STANDS, REFERENCE_STAND
from backend.gis.estate_ags_matching.listing_pool_gate_v1 import apply_listing_pool_gate

ROOT = Path(__file__).resolve().parents[1]
FROZEN_001_GIS_SHA = "1bab3126fdfa9d397857f67f2d0cb65ddc410fc5d82afaf1a823c63018f56608"
FROZEN_001_INV_SHA = "3bc02c09c293d011b8f2d866b2075e3e9863cc9af9db5c054faa0dc722aca861"
INV_001 = ROOT / "data/estate_inventory/carlswald_north_corrected_001/current.jsonl"
OS_PY = ROOT / "backend/vision/object_segmentation.py"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_frozen_001_gis_and_inventory_bytes_untouched():
    assert FROZEN_001_PATH.is_file()
    assert _sha(FROZEN_001_PATH) == FROZEN_001_GIS_SHA
    assert INV_001.is_file()
    assert _sha(INV_001) == FROZEN_001_INV_SHA
    assert pass1_parcels(json.loads(FROZEN_001_PATH.read_text(encoding="utf-8")))
    assert len(pass1_parcels(json.loads(FROZEN_001_PATH.read_text(encoding="utf-8")))) == 330


def test_official_summerset_includes_ext3_authoritatively():
    assert OFFICIAL_SUMMERSET_EXT[3] == "SUMMERSET EXT.3"
    assert OFFICIAL_SUMMERSET_EXT[6] == "SUMMERSET EXT.6"
    assert OFFICIAL_SUMMERSET_EXT[13] == "SUMMERSET EXT.13"


def test_complete_002_contains_ext3_and_keeps_330():
    require_active_dataset(COMPLETE_CARLSWALD_NORTH)
    require_active_dataset(FROZEN_CARLSWALD_NORTH_001)
    dataset = json.loads(COMPLETE_002_PATH.read_text(encoding="utf-8"))
    assert dataset["dataset_id"] == "carlswald_north_corrected_002"
    assert "SUMMERSET EXT.3" in dataset["townships"]
    assert dataset["not_inferred_from_proximity"] is True
    assert dataset["source_layer_name"] == "REGISTERED_STANDS"
    unique = pass1_parcels(dataset)
    assert len(unique) == 400
    towns = {row["township"] for row in unique}
    assert towns == {"SUMMERSET EXT.3", "SUMMERSET EXT.6", "SUMMERSET EXT.13"}
    ext3 = [row for row in unique if row["township"] == "SUMMERSET EXT.3"]
    assert len(ext3) == 70
    frozen = pass1_parcels(json.loads(FROZEN_001_PATH.read_text(encoding="utf-8")))
    frozen_ids = {row["property_id"] for row in frozen}
    complete_ids = {row["property_id"] for row in unique}
    assert frozen_ids <= complete_ids
    assert len(complete_ids - frozen_ids) == 70
    table = {row["extension"]: row for row in freeze_summary_table(dataset)}
    assert table["EXT.3"]["source_parcels"] == 78
    assert table["EXT.3"]["included_unique_properties"] == 70
    assert table["EXT.6"]["source_parcels"] == 280
    assert table["EXT.6"]["included_unique_properties"] == 212
    assert table["EXT.13"]["source_parcels"] == 136
    assert table["EXT.13"]["included_unique_properties"] == 118
    assert table["TOTAL"]["included_unique_properties"] == 400
    quality = dataset["geometry_quality"]
    assert quality["duplicate_property_ids_after_pass1"] == []
    assert quality["cross_township_stand_numbers"] == []
    assert quality["missing_geometry"] == 0


def test_registry_keeps_both_001_and_002_active():
    matches = find_datasets_for_estate("Carlswald North Estate")
    ids = [item["dataset_id"] for item in matches]
    assert "carlswald_north_corrected_001" in ids
    assert "carlswald_north_corrected_002" in ids
    assert "carlswald_north_001" not in ids


def test_os_v1_source_not_modified_in_this_change():
    text = OS_PY.read_text(encoding="utf-8")
    assert 'imgsz=512' in text
    assert 'retina_masks=True' in text
    assert 'notes=["no_pool_candidate"]' in text


def test_miss_stand_list_matches_pr16():
    assert REFERENCE_STAND == "677"
    assert MISS_STANDS == ["339", "408", "1/437", "1/520", "1/631", "459", "462", "543", "675"]


def test_complete_inventory_reuses_330_when_present():
    path = ROOT / "data/estate_inventory/carlswald_north_corrected_002/current.jsonl"
    if not path.is_file():
        return
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 400
    reused = sum(1 for row in rows if row.get("reused") or "reused_from_frozen_001" in (row.get("diagnostic_flags") or []))
    assert reused == 330
    ext3 = [row for row in rows if row.get("township") == "SUMMERSET EXT.3"]
    assert len(ext3) == 70
    counts = {"YES": 0, "NO": 0, "UNKNOWN": 0}
    for row in rows:
        counts[row["pool_status"]] += 1
    gate_yes = apply_listing_pool_gate(rows, rows, "YES")
    gate_no = apply_listing_pool_gate(rows, rows, "NO")
    assert gate_yes.unknown_survivors == counts["UNKNOWN"]
    assert gate_no.unknown_survivors == counts["UNKNOWN"]
    assert gate_yes.removed_confident_no == counts["NO"]
    assert gate_no.removed_confident_yes == counts["YES"]
    # Frozen 001 inventory still the original bytes.
    assert _sha(INV_001) == FROZEN_001_INV_SHA
    assert sum(1 for row in ext3 if row.get("fastsam_invoked")) == 70


def test_miss_diagnostic_crop_wh_matches_os_when_present():
    miss_dir = ROOT / "data/investigations/estate_property_inventory_v1/fastsam_miss"
    latest = miss_dir / "latest.json"
    if not latest.is_file():
        return
    payload = json.loads(latest.read_text(encoding="utf-8"))
    assert payload["os_v1_modified"] is False
    assert payload["fastsam_config_modified"] is False
    os_dir = ROOT / "data/investigations/object_segmentation_v1/carlswald_north/json"
    for stand in ["677", "339", "408", "1_437", "1_520", "1_631", "459", "462", "543", "675"]:
        rec = json.loads((miss_dir / f"{stand}.json").read_text(encoding="utf-8"))
        os_payload = json.loads((os_dir / f"{stand}.json").read_text(encoding="utf-8"))
        assert rec["crop_wh"] == os_payload["crop_wh"]
        assert rec["crop_matches_os_v1_wh"] is True
    assert payload["recommended_experiment"]["implement_now"] is False
