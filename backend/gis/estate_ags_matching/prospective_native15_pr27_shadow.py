"""Write-only evidence capture for prospective native15 + PR27 shadow runs.

This module deliberately invokes neither imagery, detector, ranking, nor PR27
logic.  A future runner supplies their already-produced outputs; this module
freezes their order and persists a content-addressed evidence bundle.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Mapping, Sequence


HARNESS_VERSION = "phase_g8_native15_pr27_shadow_v1"
REQUIRED_ARTIFACTS = frozenset(
    {
        "native15_raw_crop",
        "parcel_mask",
        "candidate_mask_unclipped",
        "candidate_mask_clipped",
        "building_mask",
        "road_context",
        "semantic_scores",
        "fastsam_object_candidates",
        "cross_frame_evidence",
        "contour_geometry",
        "validator_component_scores",
        "pr27_decision_reasons",
        "request_metadata",
        "imagery_hashes",
    }
)
REQUIRED_RESULTS = frozenset(
    {
        "legacy_detector",
        "current_detector",
        "native15_raw",
        "native15_pr27_shadow",
    }
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def freeze_candidate_rankings(
    candidates: Sequence[Mapping[str, Any]], output_path: Path
) -> dict[str, Any]:
    """Persist ranked candidates before later identity recovery can occur."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "harness_version": HARNESS_VERSION,
        "identity_recovery_performed": False,
        "candidates": [dict(candidate) for candidate in candidates],
    }
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    output_path.write_text(encoded, encoding="utf-8")
    return {"path": str(output_path), "sha256": sha256_file(output_path), "count": len(candidates)}


def capture_parcel(
    *,
    output_root: Path,
    parcel_id: str,
    ranking_freeze: Mapping[str, Any],
    artifacts: Mapping[str, Path],
    results: Mapping[str, Any],
) -> dict[str, Any]:
    """Copy supplied evidence into an immutable-shaped parcel bundle.

    Artifact inputs are copied rather than regenerated. JSON evidence is
    supplied as files so all original serializations and hashes are retained.
    """
    if ranking_freeze.get("identity_recovery_performed") is not False:
        raise ValueError("candidate rankings must be frozen before identity recovery")
    missing_artifacts = REQUIRED_ARTIFACTS.difference(artifacts)
    missing_results = REQUIRED_RESULTS.difference(results)
    if missing_artifacts or missing_results:
        raise ValueError(
            f"missing artifacts={sorted(missing_artifacts)} results={sorted(missing_results)}"
        )

    parcel_dir = output_root / "parcels" / str(parcel_id)
    artifact_dir = parcel_dir / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=False)
    captured: dict[str, dict[str, str]] = {}
    for name in sorted(REQUIRED_ARTIFACTS):
        source = Path(artifacts[name])
        if not source.is_file():
            raise FileNotFoundError(f"missing required {name} artifact: {source}")
        destination = artifact_dir / f"{name}{source.suffix}"
        shutil.copy2(source, destination)
        captured[name] = {
            "path": str(destination.relative_to(parcel_dir)),
            "sha256": sha256_file(destination),
        }

    manifest = {
        "harness_version": HARNESS_VERSION,
        "parcel_id": str(parcel_id),
        "ranking_freeze": dict(ranking_freeze),
        "identity_recovery_performed_before_rank_freeze": False,
        "artifacts": captured,
        "results": {name: results[name] for name in sorted(REQUIRED_RESULTS)},
    }
    manifest_path = parcel_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest
