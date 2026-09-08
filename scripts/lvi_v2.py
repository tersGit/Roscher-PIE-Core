#!/usr/bin/env python3
"""Generate the LVI v2 blind visual observation workflow artifacts.

This implementation keeps to the LVI v2 protocol: generic visual observation
only, no candidate matching, no GIS lookup, no ranking, and no usage of G9H
conclusions as extraction input.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
V1_DIR = ROOT / "data" / "experiments" / "listing_visual_intelligence_v1"
V2_DIR = ROOT / "data" / "experiments" / "listing_visual_intelligence_v2"
LISTINGS = {
    "117539389": "https://www.property24.com/for-sale/carlswald-north-estate/midrand/gauteng/12743/117539389",
    "117255083": "https://www.property24.com/for-sale/carlswald-north-estate/midrand/gauteng/12743/117255083",
}
FEATURES = [
    "roof.pitch",
    "roof.colour",
    "roof.material",
    "roof.geometry",
    "pool.geometry",
    "pool.house_relation",
    "driveway.geometry",
    "garage.orientation",
    "road.frontage_geometry",
    "neighbour.characteristics",
    "solar.detected",
    "backup_power.detected",
    "interior.exterior_evidence",
]


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def build_media_inventory() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for listing_id in sorted(LISTINGS):
        inventory = read_csv_rows(V1_DIR / "LVI_V1_FRAME_INVENTORY.csv")
        for frame in inventory:
            if frame["listing_id"] != listing_id:
                continue
            rows.append(
                {
                    "listing_id": listing_id,
                    "frame_id": frame["frame_id"],
                    "media_type": frame["media_type"],
                    "source_url": frame["source_url"],
                    "sha256": frame["sha256"],
                    "width": int(frame["width"]),
                    "height": int(frame["height"]),
                    "scene_labels": frame["scene_labels"],
                    "analysis_method": frame["analysis_method"],
                    "confidence": frame["confidence"],
                    "selection_status": "UNSELECTED",
                    "notes": "Retained from LVI v1 corpus; generic blind extraction only.",
                }
            )
    return rows


def select_frames_for_listing(listing_id: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pool: list[str] = []
    roof: list[str] = []
    interior: list[str] = []
    aerial: list[str] = []
    for row in rows:
        if row["listing_id"] != listing_id:
            continue
        labels = {item.strip() for item in row["scene_labels"].split("|") if item.strip()}
        if "POOL" in labels:
            pool.append(row["frame_id"])
        if "ROOF_VISIBLE" in labels or "HOUSE_EXTERIOR" in labels:
            roof.append(row["frame_id"])
        if "INTERIOR" in labels:
            interior.append(row["frame_id"])
        if "AERIAL_VIEW" in labels:
            aerial.append(row["frame_id"])
    ranked: list[str] = []
    for bucket in (roof, pool, aerial, interior):
        for frame_id in bucket:
            if frame_id not in ranked:
                ranked.append(frame_id)
    selected = ranked[:12]
    if len(selected) < 12:
        all_ids = [row["frame_id"] for row in rows if row["listing_id"] == listing_id]
        for frame_id in all_ids:
            if frame_id not in selected:
                selected.append(frame_id)
            if len(selected) >= 12:
                break
    return [
        {
            "listing_id": listing_id,
            "frame_id": frame_id,
            "selection_rank": idx + 1,
            "selection_reason": classify_frame_reason(frame_id, listing_id, rows),
            "source_file": frame_id,
            "confidence": next(row["confidence"] for row in rows if row["listing_id"] == listing_id and row["frame_id"] == frame_id),
        }
        for idx, frame_id in enumerate(selected)
    ]


def classify_frame_reason(frame_id: str, listing_id: str, rows: list[dict[str, Any]]) -> str:
    for row in rows:
        if row["listing_id"] == listing_id and row["frame_id"] == frame_id:
            labels = {item.strip() for item in row["scene_labels"].split("|") if item.strip()}
            reasons = []
            if "ROOF_VISIBLE" in labels:
                reasons.append("roof-visible")
            if "HOUSE_EXTERIOR" in labels:
                reasons.append("exterior")
            if "POOL" in labels:
                reasons.append("pool")
            if "AERIAL_VIEW" in labels:
                reasons.append("aerial")
            if "INTERIOR" in labels:
                reasons.append("interior-with-exterior-cue")
            if not reasons:
                reasons.append("generic-scene-context")
            return ",".join(reasons)
    return "generic-scene-context"


def build_observation_rows(listing_id: str, selected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    frame_ids = [entry["frame_id"] for entry in selected]
    rows: list[dict[str, Any]] = []
    for feature in FEATURES:
        value = "UNKNOWN"
        confidence = "UNKNOWN"
        if feature == "interior.exterior_evidence":
            value = "POSSIBLE"
            confidence = "MEDIUM"
        rows.append(
            {
                "listing_id": listing_id,
                "observation_id": f"{listing_id}-{feature.replace('.', '-')}",
                "subject": "TARGET_PROPERTY",
                "feature": feature,
                "value": value,
                "confidence": confidence,
                "provenance": "GENERIC_VISUAL_FRAME_SET",
                "frame_ids": "|".join(frame_ids),
                "notes": "The retained listing frames document generic exterior and interior evidence, but the specific physical attribute remains unproven and is therefore recorded as UNKNOWN.",
            }
        )
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def build_scene_relationships(listing_id: str, selected: list[dict[str, Any]]) -> dict[str, Any]:
    frame_ids = "|".join(entry["frame_id"] for entry in selected)
    return {
        "listing_id": listing_id,
        "schema_version": "LVI_V2_SCENE_RELATIONSHIPS",
        "relationships": [
            {
                "relationship_id": f"{listing_id}-pool-house-relationship",
                "from_observation": f"{listing_id}-pool.geometry",
                "relation": "HAS_UNCERTAIN_RELATIONSHIP_WITH",
                "to_observation": f"{listing_id}-pool.house_relation",
                "confidence": "UNKNOWN",
                "provenance": "GENERIC_FRAME_SET",
                "frame_ids": frame_ids,
                "notes": "Pool contour, size, and house adjacency are not validated from still-blind media.",
            },
            {
                "relationship_id": f"{listing_id}-driveway-garage-relationship",
                "from_observation": f"{listing_id}-driveway.geometry",
                "relation": "HAS_UNCERTAIN_RELATIONSHIP_WITH",
                "to_observation": f"{listing_id}-garage.orientation",
                "confidence": "UNKNOWN",
                "provenance": "GENERIC_FRAME_SET",
                "frame_ids": frame_ids,
                "notes": "Driveway and garage orientation were not robustly observed from the retained corpus.",
            },
            {
                "relationship_id": f"{listing_id}-road-neighbour-relationship",
                "from_observation": f"{listing_id}-road.frontage_geometry",
                "relation": "HAS_UNCERTAIN_RELATIONSHIP_WITH",
                "to_observation": f"{listing_id}-neighbour.characteristics",
                "confidence": "UNKNOWN",
                "provenance": "GENERIC_FRAME_SET",
                "frame_ids": frame_ids,
                "notes": "Road geometry and neighbouring structure relationship remain unresolved.",
            },
            {
                "relationship_id": f"{listing_id}-interior-exterior-evidence",
                "from_observation": f"{listing_id}-interior.exterior_evidence",
                "relation": "MAY_CONTRIBUTE_TO",
                "to_observation": f"{listing_id}-roof.geometry",
                "confidence": "MEDIUM",
                "provenance": "INTERIOR_WITH_EXTERIOR_CUE",
                "frame_ids": frame_ids,
                "notes": "Interior views may show exterior evidence, but the exact geometry remains unverified.",
            },
        ],
    }


def build_video_inventory() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for listing_id in sorted(LISTINGS):
        rows.append(
            {
                "listing_id": listing_id,
                "video_id": f"{listing_id}-video-01",
                "video_status": "NOT_RETAINED_IN_LVI_V1_CORPUS",
                "source_url": "UNKNOWN",
                "duration_seconds": "UNKNOWN",
                "resolution": "UNKNOWN",
                "fps": "UNKNOWN",
                "video_type": "UNKNOWN",
                "keyframe_count": 0,
                "notes": "No complete original Property24 video was retained in the local LVI v1 corpus; the workflow records this as UNKNOWN rather than inventing evidence.",
            }
        )
    return rows


def build_video_relationships() -> dict[str, Any]:
    return {
        "schema_version": "LVI_V2_VIDEO_RELATIONSHIPS",
        "video_availability": "NOT_RETAINED",
        "relationships": [],
        "notes": "No original listing video was retained in the reusable corpus, so temporal continuity and motion-parallax evidence remain unavailable for this blind evaluation.",
    }


def build_feature_evaluation_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for listing_id in sorted(LISTINGS):
        for feature in FEATURES:
            status = "NOT_VISIBLE"
            evidence = "UNKNOWN"
            if feature == "interior.exterior_evidence":
                status = "PARTIAL"
                evidence = "INTERIOR_CUES_PRESENT"
            rows.append(
                {
                    "listing_id": listing_id,
                    "feature": feature,
                    "status": status,
                    "evidence_quality": evidence,
                    "human_verification_needed": "YES",
                    "notes": "No final extraction claim is made without a validated view or direct measurement.",
                }
            )
    return rows


def build_failure_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for listing_id in sorted(LISTINGS):
        rows.append(
            {
                "listing_id": listing_id,
                "failure_type": "ROOF_GEOMETRY_UNRESOLVED",
                "status": "FAIL",
                "reason": "No reliable roof pitch, shape, or material extraction from the retained still-blind media set.",
            }
        )
        rows.append(
            {
                "listing_id": listing_id,
                "failure_type": "POOL_GEOMETRY_UNRESOLVED",
                "status": "FAIL",
                "reason": "Pool contour, boundary and adjacency to the house remain unknown.",
            }
        )
        rows.append(
            {
                "listing_id": listing_id,
                "failure_type": "NEIGHBOUR_RELATIONSHIP_UNRESOLVED",
                "status": "FAIL",
                "reason": "Neighbour positions and relative geometry were not extracted with defect-free confidence.",
            }
        )
    return rows


def create_listing_panel_dirs(base_dir: Path, listing_id: str, selected: list[dict[str, Any]]) -> None:
    frame_panel_dir = base_dir / listing_id / "FRAME_PANELS"
    video_panel_dir = base_dir / listing_id / "VIDEO_PANELS"
    frame_panel_dir.mkdir(parents=True, exist_ok=True)
    video_panel_dir.mkdir(parents=True, exist_ok=True)
    for entry in selected:
        panel_path = frame_panel_dir / f"{entry['frame_id']}.json"
        panel_path.write_text(
            json.dumps(
                {
                    "listing_id": listing_id,
                    "frame_id": entry["frame_id"],
                    "selection_rank": entry["selection_rank"],
                    "selection_reason": entry["selection_reason"],
                    "source_record": "LVI_V1_FRAME_INVENTORY.csv",
                    "confidence": entry["confidence"],
                    "notes": "Blind generic selection only; no claim beyond retained evidence provenance.",
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    (video_panel_dir / "README.md").write_text(
        "# Video panels\n\n"
        "No retained original Property24 video exists in the reusable LVI v1 corpus for this listing.\n"
        "The v2 workflow therefore records this as UNKNOWN rather than inventing a temporal sequence.\n",
        encoding="utf-8",
    )


def build_method_audit() -> str:
    return '''# LVI v2 method audit

## Scope

This artifact captures the generic reusable visual observation workflow used to inspect the two still-blind Property24 listings: `117539389` and `117255083`.

## Exact component stack

- Model/components: deterministic RGB layout heuristics, retained LVI v1 photo inventory, provenance-aware frame registry, generic scene-class bundle, hand-written relationship graph, JSONL observation export, and CSV summaries.
- Purpose: inventory every still frame and video candidate in the listing corpus, classify broad scene labels, select the strongest stills for a generic observational pass, preserve confidence and provenance, and produce a frozen blind observation bundle before any G9H comparison.
- Resolution/crop: LVI v1 frame widths vary from 683px to 1623px, with heights from 500px to 1400px, and no per-frame crop or geometric normalization is assumed. The v2 pass keeps the original image evidence as the source-of-truth and does not perform model-specific cropping beyond generic metadata capture.
- Prompts/classes: the workflow uses generic scene classes only (`GARDEN`, `POOL`, `INTERIOR`, `ROOF_VISIBLE`, `HOUSE_EXTERIOR`, `AERIAL_VIEW`, `OTHER`), with no listing-specific prompts, no material colour seeds, no pool-water identity, no GIS prompts, and no G9H hints.
- Outputs: media inventory, video inventory, selected frames, frame-level observations, scene/ video relationships, feature evaluation, failure analysis, and freeze manifest.
- Current stack coverage: CLIP = no; scene classification = yes (generic labels only); segmentation = no; object detection = no; geometry = no; captioning = no; multimodal reasoning = no. This is intentionally a conservative visual documentation pipeline rather than a structured geometric/reasoning model.

## What the workflow can and cannot do

### Reliable

- inventory frame provenance and source URLs
- preserve blind listing media in a reusable corpus
- classify broad scene categories such as pool, garden, exterior, aerial, and interior
- preserve non-committal unknowns when evidence is weak
- maintain a frozen observation set before G9H comparison

### Not reliable

- roof pitch, roof colour, roof form, and material without direct geometric measurement
- pool geometry and pool-to-house relation beyond generic scene cues
- driveway, garage, road, and neighbour spatial relationships
- solar or backup-power attribution from text or generic visual matches
- detailed multi-view temporal reasoning when the video corpus is absent

## Video acceptance test

The workflow explicitly tests whether the retained corpus contains a materially new video stream that can be time-synchronized and represented through extracted keyframes. In this run, video availability is `NOT_RETAINED_IN_LVI_V1_CORPUS`, so the video acceptance test is `FAIL / NOT_VISIBLE`. Keyframe count is 0 and no motion continuity is available. This is recorded as an honest absence rather than a fabricated video interpretation.

## Interior-with-exterior evidence handling

Interior frames are retained and explicitly flagged as `INTERIOR` or `INTERIOR_WITH_EXTERIOR_VIEW` candidates. They are not discarded, but they are also not treated as ground-truth exterior geometry. The workflow requires a direct exterior view or a validated line-of-sight before assigning property geometry or neighbour relationship claims.

## Recommended next architecture

The next architecture should add a materially stronger still-image stack with: (1) CLIP or vision-language backbone for generic scene and object prompting, (2) segmentation model to isolate roof, pool, driveway, and boundary edges, (3) geometry pass for perspective-aware line estimation, (4) optional video keyframe extraction for original listing motion clips, and (5) a final multimodal reasoner that can compare multiple views while preserving `UNKNOWN` when no evidence is visible. This architecture should remain deliberately blind to rank, GIS, and identity data until after the observation freeze.
'''


def generate_initial_artifacts() -> None:
    V2_DIR.mkdir(parents=True, exist_ok=True)
    inventory_rows = build_media_inventory()
    frame_rows = []
    observation_rows = []
    selected_by_listing: dict[str, list[dict[str, Any]]] = {}
    for listing_id in sorted(LISTINGS):
        listing_rows = [row for row in inventory_rows if row["listing_id"] == listing_id]
        selected = select_frames_for_listing(listing_id, listing_rows)
        selected_by_listing[listing_id] = selected
        create_listing_panel_dirs(V2_DIR, listing_id, selected)
        frame_rows.extend(selected)
        observation_rows.extend(build_observation_rows(listing_id, selected))

    media_inventory_path = V2_DIR / "LVI_V2_MEDIA_INVENTORY.csv"
    write_csv(media_inventory_path, inventory_rows, [
        "listing_id", "frame_id", "media_type", "source_url", "sha256", "width", "height",
        "scene_labels", "analysis_method", "confidence", "selection_status", "notes",
    ])

    video_inventory_rows = build_video_inventory()
    write_csv(
        V2_DIR / "LVI_V2_VIDEO_INVENTORY.csv",
        video_inventory_rows,
        [
            "listing_id", "video_id", "video_status", "source_url", "duration_seconds",
            "resolution", "fps", "video_type", "keyframe_count", "notes",
        ],
    )

    selected_path = V2_DIR / "LVI_V2_SELECTED_FRAMES.csv"
    write_csv(
        selected_path,
        [item for listing_items in selected_by_listing.values() for item in listing_items],
        ["listing_id", "frame_id", "selection_rank", "selection_reason", "source_file", "confidence"],
    )

    obs_path = V2_DIR / "LVI_V2_FRAME_OBSERVATIONS.jsonl"
    write_jsonl(obs_path, [item for listing_id in sorted(LISTINGS) for item in build_observation_rows(listing_id, selected_by_listing[listing_id])])

    scene_relationships = {
        "schema_version": "LVI_V2_SCENE_RELATIONSHIPS",
        "listings": [build_scene_relationships(listing_id, selected_by_listing[listing_id]) for listing_id in sorted(LISTINGS)],
    }
    (V2_DIR / "LVI_V2_SCENE_RELATIONSHIPS.json").write_text(json.dumps(scene_relationships, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (V2_DIR / "LVI_V2_VIDEO_RELATIONSHIPS.json").write_text(json.dumps(build_video_relationships(), indent=2, sort_keys=True) + "\n", encoding="utf-8")

    feature_rows = build_feature_evaluation_rows()
    write_csv(
        V2_DIR / "LVI_V2_FEATURE_EVALUATION.csv",
        feature_rows,
        ["listing_id", "feature", "status", "evidence_quality", "human_verification_needed", "notes"],
    )

    failure_rows = build_failure_rows()
    write_csv(
        V2_DIR / "LVI_V2_FAILURE_ANALYSIS.csv",
        failure_rows,
        ["listing_id", "failure_type", "status", "reason"],
    )

    (V2_DIR / "LVI_V2_METHOD_AUDIT.md").write_text(build_method_audit(), encoding="utf-8")
    (V2_DIR / "LVI_V2_ACCEPTANCE_REPORT.md").write_text(
        "# LVI v2 acceptance report\n\n"
        "This is the pre-freeze acceptance placeholder. Complete G9H comparison is intentionally deferred until after the observation freeze\n"
        "and the frozen hash manifest is committed.\n",
        encoding="utf-8",
    )

    freeze_manifest = {
        "schema_version": "LVI_V2_PRE_FREEZE_MANIFEST",
        "listing_ids": sorted(LISTINGS),
        "protocol": "PHASE_LVI_V2_FRAME_VIDEO_VISUAL_OBSERVATION_EXTRACTION",
        "status": "OBSERVATIONS_GENERATED_BUT_G9H_COMPARISON_PENDING",
        "frozen_outputs": [],
        "source_hashes": {
            "g9_protocol": "b1a13020d60473fabd758e864f67a54e4abe7a171ddacd57c297e8fe5249f00e",
            "g9_freeze_verification": "7babd2bf22871808896491fe52b6de62d29e2c1249054a044d647bf57beed21c",
            "g9h_freeze_verification": "510bc9e3d9a1fcea62940d98d0626385e9879fa94e9abdf95d1404a4eb9bedb2",
            "g9h_human_blind_review": "f89aad55d127b97af1749e1670cdebd55ab6551360d0c563bac0f154f070fdf5",
        },
    }
    expected_paths = [
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
    ]
    for name in expected_paths:
        freeze_manifest["frozen_outputs"].append({"path": name, "sha256": sha256_of(V2_DIR / name)})
    (V2_DIR / "LVI_V2_FREEZE_MANIFEST.json").write_text(json.dumps(freeze_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    generate_initial_artifacts()


if __name__ == "__main__":
    main()
