import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V2_DIR = ROOT / "data" / "experiments" / "listing_visual_intelligence_v2"


def test_required_artifacts_exist():
    required = [
        "LVI_V2_METHOD_AUDIT.md",
        "LVI_V2_MEDIA_INVENTORY.csv",
        "LVI_V2_VIDEO_INVENTORY.csv",
        "LVI_V2_SELECTED_FRAMES.csv",
        "LVI_V2_FRAME_OBSERVATIONS.jsonl",
        "LVI_V2_VIDEO_RELATIONSHIPS.json",
        "LVI_V2_SCENE_RELATIONSHIPS.json",
        "LVI_V2_FEATURE_EVALUATION.csv",
        "LVI_V2_FAILURE_ANALYSIS.csv",
        "LVI_V2_ACCEPTANCE_REPORT.md",
        "LVI_V2_FREEZE_MANIFEST.json",
    ]
    for name in required:
        assert (V2_DIR / name).exists(), name


def test_selected_frames_holder_has_two_listing_panels():
    for listing_id in ("117539389", "117255083"):
        frame_dir = V2_DIR / listing_id / "FRAME_PANELS"
        video_dir = V2_DIR / listing_id / "VIDEO_PANELS"
        assert frame_dir.is_dir(), frame_dir
        assert video_dir.is_dir(), video_dir
        assert any(frame_dir.iterdir()), frame_dir
        assert (video_dir / "README.md").exists(), video_dir / "README.md"


def test_frame_observations_are_valid_jsonl_and_unknown_or_possible_only():
    with (V2_DIR / "LVI_V2_FRAME_OBSERVATIONS.jsonl").open("r", encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle if line.strip()]
    assert rows
    for row in rows:
        assert row["value"] in {"UNKNOWN", "POSSIBLE"}
        assert row["listing_id"] in {"117539389", "117255083"}


def test_feature_eval_is_acceptance_ready():
    with (V2_DIR / "LVI_V2_FEATURE_EVALUATION.csv").open("r", newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    assert any(row["feature"] == "roof.pitch" for row in rows)
    assert any(row["feature"] == "pool.geometry" for row in rows)
