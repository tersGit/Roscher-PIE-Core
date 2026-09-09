import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "experiments" / "listing_visual_intelligence_v3"


def test_blind_freeze_has_complete_provenance():
    manifest = json.loads((OUT / "LVI_V3_BLIND_FREEZE_MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "BLIND_OBSERVATIONS_FROZEN_BEFORE_G9H_READ"
    assert "G9H input" in manifest["prohibitions_observed"]
    assert manifest["files"]


def test_recovered_video_is_not_misreported_as_absent():
    with (OUT / "LVI_V3_VIDEO_INVENTORY.csv").open(newline="", encoding="utf-8") as handle:
        rows = {row["listing_id"]: row for row in csv.DictReader(handle)}
    assert rows["117255083"]["video_status"] == "SOURCE_EMBED_DISCOVERED_BUT_UNAVAILABLE"
    assert rows["117255083"]["embed_urls"]


def test_observations_separate_unknowns_and_direct_visual_evidence():
    with (OUT / "LVI_V3_FRAME_OBSERVATIONS.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert any(row["directness"] == "DIRECT_AND_MULTI_VIEW" for row in rows)
    assert any(row["value"] == "UNKNOWN_OR_NOT_SUFFICIENTLY_VISIBLE" for row in rows)


def test_post_freeze_evaluation_does_not_change_manifested_outputs():
    manifest = json.loads((OUT / "LVI_V3_BLIND_FREEZE_MANIFEST.json").read_text(encoding="utf-8"))
    for record in manifest["files"]:
        path = OUT / record["path"]
        import hashlib
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record["sha256"]
