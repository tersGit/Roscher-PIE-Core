"""Create the pre-comparison LVI freeze manifest and acceptance report."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "experiments" / "listing_visual_intelligence_v1"
G9 = ROOT / "data" / "investigations" / "geolis_resolution_audit" / "phase_g9_2026-09-08"
G9H = G9 / "human_blind_review"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_sha(ref: str) -> str:
    return subprocess.check_output(["git", "rev-parse", ref], cwd=ROOT, text=True).strip()


def main() -> None:
    precomparison = []
    for path in sorted(OUT.rglob("*")):
        if path.is_file() and path.name not in {"LVI_V1_FREEZE_MANIFEST.json", "LVI_V1_HUMAN_COMPARISON.md"}:
            precomparison.append({"path": str(path.relative_to(ROOT)).replace("\\", "/"), "sha256": sha(path)})
    source_hashes = {}
    for path in [
        G9 / "PHASE_G9_PROTOCOL.md",
        G9 / "PHASE_G9_FREEZE_VERIFICATION.md",
        G9 / "PHASE_G9_COMPONENT_FREEZE.md",
        G9H / "PHASE_G9H_FREEZE_VERIFICATION.md",
        G9H / "PHASE_G9H_HUMAN_BLIND_REVIEW.md",
    ]:
        source_hashes[str(path.relative_to(ROOT)).replace("\\", "/")] = sha(path)
    manifest = {
        "schema_version": "LVI_V1_FREEZE",
        "status": "FINGERPRINTS_FROZEN_BEFORE_SUBSTANTIVE_G9H_COMPARISON",
        "listing_ids": ["117539389", "117255083"],
        "lineage_verification": {
            "g9_freeze_commit": git_sha("17e161a"),
            "g8_authority": git_sha("4381c1a"),
            "g7_authority": git_sha("85fce40"),
            "source_file_sha256": source_hashes,
        },
        "blindness_attestation": {
            "g9h_content_used_as_input": False,
            "prompts_or_labels_seeded_from_g9h": False,
            "code_contains_g9h_references": False,
            "candidate_gis_ranking_data_used": False,
            "procedural_deviation": {
                "occurred": True,
                "exact_file_accessed": "data/investigations/geolis_resolution_audit/phase_g9_2026-09-08/human_blind_review/PHASE_G9H_HUMAN_BLIND_REVIEW.md",
                "purpose": "source-package inspection while locating the attachment/frozen files",
                "content_transcribed_or_used": False,
                "extraction_restarted_after_access": True
            }
        },
        "precomparison_outputs": precomparison,
        "comparison_allowed_after": "this manifest and the fingerprint-freeze commit",
    }
    (OUT / "LVI_V1_FREEZE_MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    report = """# LVI v1 acceptance report

## Scope

The extractor ran on all ordinary Property24 media exposed by the two supplied
listing pages: 57 photo frames for `117539389` and 36 photo frames for
`117255083`. One video URL was inventoried for `117255083`; no video frame was
downloaded by the permitted media parser. No identity, GIS, candidate, ranking,
address, or G9H observation was used as an extraction input.

## Ten acceptance criteria

| Criterion | 117539389 | 117255083 | Result |
|---|---|---|---|
| 1. Roof form | Frame labels retain roof-bearing exterior views, but form is UNKNOWN | UNKNOWN | Not established |
| 2. Roof appearance/colour | UNKNOWN | UNKNOWN | Not established |
| 3. Pool geometry beyond presence | Repeated pool cues, no reliable contour | Repeated pool cues, no reliable contour | Not established |
| 4. Pool-to-house relation | UNKNOWN | UNKNOWN | Not established |
| 5. Driveway/garage geometry | UNKNOWN | UNKNOWN | Not established |
| 6. Road/frontage geometry | UNKNOWN | UNKNOWN | Not established |
| 7. Distinctive neighbours | Structures remain UNKNOWN_STRUCTURE | UNKNOWN_STRUCTURE | Not established |
| 8. Exterior evidence from interiors | Interior frames retained, exterior linkage unresolved | Retained, unresolved | Partial |
| 9. Cross-frame fusion | Repeated pool cue relationship only | Repeated pool cue relationship only | Partial |
| 10. Eliminate incompatible aerial candidates | Not enough structured geometry | Not enough structured geometry | No |

## Acceptance result

**FAIL / diagnostic baseline.** LVI v1 proves complete media inventory,
frame-level provenance, multi-label retention, separated text/visual evidence,
and a contradiction-ready schema. The deterministic visual pass does not yet
extract materially useful roof, pool geometry, frontage, garage, or neighbour
fingerprints. This is an honest baseline rather than an identity or ranking
result. The fingerprints are frozen unchanged before the permitted human
comparison.
"""
    (OUT / "LVI_V1_ACCEPTANCE_REPORT.md").write_text(report, encoding="utf-8")


if __name__ == "__main__":
    main()
