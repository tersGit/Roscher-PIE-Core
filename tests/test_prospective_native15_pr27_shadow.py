import json

import pytest

from backend.gis.estate_ags_matching.prospective_native15_pr27_shadow import (
    REQUIRED_ARTIFACTS,
    capture_parcel,
    freeze_candidate_rankings,
)


def test_shadow_capture_requires_frozen_rankings_and_preserves_all_evidence(tmp_path):
    ranking = freeze_candidate_rankings([{"rank": 1, "parcel_id": "new-1"}], tmp_path / "ranked.json")
    ranking["identity_recovery_performed"] = False
    artifacts = {}
    for name in REQUIRED_ARTIFACTS:
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps({"source": name}), encoding="utf-8")
        artifacts[name] = path
    result = capture_parcel(
        output_root=tmp_path / "out",
        parcel_id="new-1",
        ranking_freeze=ranking,
        artifacts=artifacts,
        results={
            "legacy_detector": {"status": "NO"},
            "current_detector": {"status": "YES"},
            "native15_raw": {"status": "YES"},
            "native15_pr27_shadow": {"status": "UNKNOWN"},
        },
    )
    assert set(result["artifacts"]) == REQUIRED_ARTIFACTS
    assert result["results"]["native15_pr27_shadow"]["status"] == "UNKNOWN"


def test_shadow_capture_rejects_identity_recovery_before_rank_freeze(tmp_path):
    with pytest.raises(ValueError, match="frozen before identity recovery"):
        capture_parcel(
            output_root=tmp_path / "out",
            parcel_id="new-1",
            ranking_freeze={"identity_recovery_performed": True},
            artifacts={},
            results={},
        )
