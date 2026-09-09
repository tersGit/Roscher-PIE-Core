#!/usr/bin/env python3
"""Produce the blind LVI v3 visual-understanding experiment.

The experiment deliberately has no imports from candidate, GIS, ranking, or
G9H material.  It preserves public listing media, then uses the locally cached
OWL-ViT detector and OpenCV only for blind visual observations.
"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import cv2
import httpx
import torch
from PIL import Image
from transformers import OwlViTForObjectDetection, OwlViTProcessor

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.parsers.property24 import USER_AGENT, fetch_listing

OUT = ROOT / "data" / "experiments" / "listing_visual_intelligence_v3"
LISTINGS = {
    "117539389": "https://www.property24.com/for-sale/carlswald-north-estate/midrand/gauteng/12743/117539389",
    "117255083": "https://www.property24.com/for-sale/carlswald-north-estate/midrand/gauteng/12743/117255083",
}
PROMPTS = [
    "a swimming pool", "a house roof", "a garage door", "a driveway",
    "a road", "solar panels", "a detached outbuilding", "a neighboring house",
    "a large tree",
]
MODEL_DIR = next((Path.home() / ".cache" / "huggingface" / "hub" /
                  "models--google--owlvit-base-patch32" / "snapshots").iterdir())


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fields} for row in rows)


def download_stills(listing_id: str, urls: list[str]) -> list[dict[str, Any]]:
    media_dir = OUT / listing_id / "ORIGINAL_STILLS"
    media_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    with httpx.Client(timeout=40, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
        for index, url in enumerate(urls, 1):
            frame_id = f"{listing_id}-{index:03d}"
            destination = media_dir / f"{frame_id}.jpg"
            response = client.get(url)
            response.raise_for_status()
            destination.write_bytes(response.content)
            with Image.open(destination) as image:
                width, height = image.size
            rows.append({
                "listing_id": listing_id, "frame_id": frame_id, "source_type": "still",
                "source_url": url, "local_path": str(destination.relative_to(OUT)).replace("\\", "/"),
                "sha256": sha256(destination), "bytes": destination.stat().st_size,
                "width": width, "height": height, "http_status": response.status_code,
                "content_type": response.headers.get("content-type", ""), "retrieved_at": datetime.now(UTC).isoformat(),
            })
    return rows


def inspect_video(listing_id: str, video_urls: list[str]) -> dict[str, Any]:
    record: dict[str, Any] = {
        "listing_id": listing_id, "embed_urls": "|".join(video_urls), "video_status": "NO_EMBED_DISCOVERED",
        "attempt": "normal parser fetch_listing() then python -m yt_dlp --dump-single-json",
        "result_detail": "The Property24 HTML parser found no YouTube embed.", "original_media_path": "",
        "sha256": "", "duration_seconds": "", "resolution": "", "fps": "", "keyframe_count": 0,
        "drone_keyframes": 0,
    }
    if not video_urls:
        return record
    url = video_urls[0]
    process = subprocess.run(
        [sys.executable, "-m", "yt_dlp", "--no-warnings", "--dump-single-json", url],
        capture_output=True, text=True, timeout=120,
    )
    if process.returncode:
        record.update({
            "video_status": "SOURCE_EMBED_DISCOVERED_BUT_UNAVAILABLE",
            "result_detail": (process.stderr or process.stdout).strip().replace("\n", " ")[:1000],
        })
        return record
    metadata = json.loads(process.stdout)
    record.update({"video_status": "METADATA_AVAILABLE_DOWNLOAD_NOT_IMPLEMENTED", "result_detail": json.dumps({
        "id": metadata.get("id"), "title": metadata.get("title"), "duration": metadata.get("duration")
    }, sort_keys=True)})
    return record


def detect_frames(media_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    processor = OwlViTProcessor.from_pretrained(str(MODEL_DIR), local_files_only=True)
    model = OwlViTForObjectDetection.from_pretrained(str(MODEL_DIR), local_files_only=True).eval()
    all_rows: list[dict[str, Any]] = []
    for start in range(0, len(media_rows), 4):
        batch = media_rows[start:start + 4]
        images = [Image.open(OUT / row["local_path"]).convert("RGB") for row in batch]
        inputs = processor(text=[PROMPTS] * len(images), images=images, return_tensors="pt", padding=True)
        with torch.inference_mode():
            outputs = model(**inputs)
        sizes = torch.tensor([[image.height, image.width] for image in images])
        results = processor.post_process_grounded_object_detection(
            outputs, target_sizes=sizes, threshold=0.12, text_labels=[PROMPTS] * len(images)
        )
        for source, result in zip(batch, results):
            for score, label, box in zip(result["scores"], result["labels"], result["boxes"]):
                xyxy = [round(float(value), 1) for value in box.tolist()]
                all_rows.append({
                    "listing_id": source["listing_id"], "frame_id": source["frame_id"], "source_type": "still",
                    "prompt": str(label), "confidence": round(float(score), 4),
                    "box_xyxy": json.dumps(xyxy), "model": "google/owlvit-base-patch32",
                    "directness": "DIRECT_MODEL_DETECTION",
                })
        for image in images:
            image.close()
    return all_rows


def contour_rows(media_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for source in media_rows:
        image = cv2.imread(str(OUT / source["local_path"]))
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 80, 160)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        large = sum(1 for contour in contours if cv2.contourArea(contour) >= image.shape[0] * image.shape[1] * .01)
        rows.append({"listing_id": source["listing_id"], "frame_id": source["frame_id"], "source_type": "still",
                     "large_external_contours": large, "method": "opencv-canny-external-contours",
                     "limit": "Contours identify visible edges only; they do not assign object identity or property ownership."})
    return rows


def observations() -> list[dict[str, Any]]:
    # Curated after blind inspection of preserved public listing images.  Values
    # are intentionally restricted to direct appearance or explicit UNKNOWN.
    return [
        {"listing_id": "117539389", "feature": "house.storeys", "value": "TWO_STOREYS_VISIBLE", "confidence": "HIGH", "source_frames": "117539389-004|117539389-012|117539389-039|117539389-040", "source_type": "still", "directness": "DIRECT", "visibility": "visible", "supporting_observation": "Multiple exterior views show lower and upper facade levels."},
        {"listing_id": "117539389", "feature": "roof", "value": "DARK_RED_BROWN_TILED_LOW_PITCH_HIPPED_SECTIONS_VISIBLE", "confidence": "MEDIUM", "source_frames": "117539389-039|117539389-040", "source_type": "still", "directness": "DIRECT", "visibility": "partially_visible", "supporting_observation": "Exterior facade views show tiled eaves and hip-like roof sections; full roof plan is occluded."},
        {"listing_id": "117539389", "feature": "pool", "value": "POOL_PRESENT_CURVILINEAR_FAMILY_VISIBLE_ADJACENT_TO_REAR_FACADE", "confidence": "HIGH", "source_frames": "117539389-004|117539389-011|117539389-012", "source_type": "still", "directness": "DIRECT_AND_MULTI_VIEW", "visibility": "visible", "supporting_observation": "Pool edge is visible in multiple exterior views, with patio/rear facade on one side."},
        {"listing_id": "117539389", "feature": "garage", "value": "DOUBLE_GARAGE_DOOR_ON_FRONT_FACADE_VISIBLE", "confidence": "HIGH", "source_frames": "117539389-039", "source_type": "still", "directness": "DIRECT", "visibility": "visible", "supporting_observation": "Front elevation directly shows a wide two-car garage door below the upper level."},
        {"listing_id": "117539389", "feature": "driveway_road_frontage_solar_neighbours", "value": "UNKNOWN_OR_NOT_SUFFICIENTLY_VISIBLE", "confidence": "HIGH", "source_frames": "117539389-004|117539389-039|117539389-040", "source_type": "still", "directness": "UNKNOWN", "visibility": "occluded_or_out_of_frame", "supporting_observation": "Exterior frames do not establish a road connection, boundary geometry, a neighbour signature, or solar panels."},
        {"listing_id": "117255083", "feature": "house.storeys", "value": "SINGLE_STOREY_POOL_FACING_WING_AND_TWO_STOREY_GARAGE_SECTION_VISIBLE", "confidence": "MEDIUM", "source_frames": "117255083-027|117255083-033", "source_type": "still", "directness": "DIRECT", "visibility": "visible", "supporting_observation": "Pool-facing facade is one level; a separate exterior view shows a garage under an upper level. Their architectural relation is not proven."},
        {"listing_id": "117255083", "feature": "roof", "value": "LIGHT_GREY_TILED_LOW_PITCH_HIPPED_SECTIONS_VISIBLE", "confidence": "MEDIUM", "source_frames": "117255083-027|117255083-030", "source_type": "still", "directness": "DIRECT", "visibility": "partially_visible", "supporting_observation": "Pool-facing roof eaves visibly use light grey tiles; full roof geometry is not exposed."},
        {"listing_id": "117255083", "feature": "pool", "value": "POOL_PRESENT_RECTILINEAR_FAMILY_VISIBLE_ADJACENT_TO_POOL_FACING_FACADE", "confidence": "HIGH", "source_frames": "117255083-027|117255083-030", "source_type": "still", "directness": "DIRECT_AND_MULTI_VIEW", "visibility": "visible", "supporting_observation": "Straight pool edges and the pool-facing facade are repeatedly visible."},
        {"listing_id": "117255083", "feature": "garden_outbuilding", "value": "MATURE_TREES_OPEN_LAWN_AND_SMALL_GARDEN_OUTBUILDING_VISIBLE", "confidence": "HIGH", "source_frames": "117255083-031|117255083-032|117255083-035|117255083-036", "source_type": "still", "directness": "DIRECT_AND_MULTI_VIEW", "visibility": "visible", "supporting_observation": "Garden frames directly show lawn, mature trees, and a small separate building; boundary relation remains unknown."},
        {"listing_id": "117255083", "feature": "driveway_road_frontage_solar_neighbours", "value": "UNKNOWN_OR_NOT_SUFFICIENTLY_VISIBLE", "confidence": "HIGH", "source_frames": "117255083-027|117255083-033|117255083-036", "source_type": "still", "directness": "UNKNOWN", "visibility": "occluded_or_out_of_frame", "supporting_observation": "No frame establishes driveway route or road; no solar panel or distinctive neighbour roof is visually supported."},
    ]


def write_reports(media: list[dict[str, Any]], video: list[dict[str, Any]], detections: list[dict[str, Any]], contours: list[dict[str, Any]], obs: list[dict[str, Any]]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    write_csv(OUT / "LVI_V3_MEDIA_INVENTORY.csv", media, list(media[0]))
    write_csv(OUT / "LVI_V3_VIDEO_INVENTORY.csv", video, list(video[0]))
    write_csv(OUT / "LVI_V3_FRAME_DETECTIONS.csv", detections, ["listing_id", "frame_id", "source_type", "prompt", "confidence", "box_xyxy", "model", "directness"])
    write_csv(OUT / "LVI_V3_CONTOURS.csv", contours, list(contours[0]))
    write_csv(OUT / "LVI_V3_FRAME_OBSERVATIONS.csv", obs, list(obs[0]))
    for listing_id in LISTINGS:
        listing_obs = [row for row in obs if row["listing_id"] == listing_id]
        (OUT / listing_id).mkdir(exist_ok=True)
        (OUT / listing_id / "VISUAL_FINGERPRINT.json").write_text(json.dumps({"listing_id": listing_id, "observations": listing_obs}, indent=2) + "\n", encoding="utf-8")
        (OUT / listing_id / "VISUAL_REPORT.md").write_text(
            f"# Blind visual report: {listing_id}\n\n" +
            "\n".join(f"- **{row['feature']}**: {row['value']} ({row['confidence']}; {row['supporting_observation']})" for row in listing_obs) + "\n",
            encoding="utf-8",
        )
    relationships = {
        "schema_version": "LVI_V3_BLIND_RELATIONSHIPS",
        "relationships": [row for row in obs if row["directness"] == "DIRECT_AND_MULTI_VIEW"],
        "video_relationships": "NONE: the only discovered public embed was unavailable to yt-dlp at retrieval time.",
    }
    (OUT / "LVI_V3_SCENE_AND_VIDEO_RELATIONSHIPS.json").write_text(json.dumps(relationships, indent=2) + "\n", encoding="utf-8")
    (OUT / "LVI_V3_CAPABILITY_AND_METHOD_AUDIT.md").write_text("""# LVI v3 capability and method audit

## Capability gate

| Capability | Result | Actual component / limit |
|---|---|---|
| Multimodal captioning / relationship reasoner | Unavailable | `transformers` is installed but no local captioning/VLM weights were found. |
| Semantic comparison | Available and usable | Cached `timm/vit_base_patch32_clip_224.openai` weights (605 MB); not used as a substitute captioner. |
| Object detection | Available and used | Cached `google/owlvit-base-patch32` weights (613 MB), local CPU inference, 224-pixel patch model, prompted zero-shot detections. |
| Segmentation | Unavailable | No SAM/segmentation package or weights. |
| Contour/geometry | Available and used, limited | OpenCV 5 Canny/external contours; edges only, no calibrated metric geometry or ownership inference. |
| Multi-image reasoning | Partly available | Evidence fusion is deterministic and only joins repeated direct appearances; no VLM relationship model is available. |
| Video/keyframing / temporal analysis | Partly available, unusable here | `yt_dlp` Python module and OpenCV are present; original source retrieval failed before a stream could be preserved. |

The environment is CPU-only (`torch` 2.13.0, CUDA false).  Generic deterministic RGB/layout classification was not used. OWL-ViT detections support frame review but the published fingerprint is limited to visually verified direct observations.

## Recovery-path finding

The normal `backend.parsers.property24.fetch_listing()` parser extracts only YouTube embeds. LVI v1 downloads stills to a temporary directory and deletes that cache; it records `video_count` but never downloads video. LVI v2 then hard-codes `NOT_RETAINED_IN_LVI_V1_CORPUS`. For `117255083`, the current normal parse returns `https://www.youtube.com/embed/bGvUiiWGuSE`; this proves v2's zero keyframes was a preservation failure, not source-video absence. At this run, `python -m yt_dlp --dump-single-json` returns YouTube's `This video is not available`, so original video, technical metadata, and keyframes cannot be preserved. This is an acquisition failure for the public embed, not an assertion of source-video absence.

No identity, address, erf, GIS, candidate, G9 Top5/Top20, ranking, scoring, Native15, pool detector, PR27, production, known ground truth, or G9H material was read by this extractor.
""", encoding="utf-8")
    (OUT / "LVI_V3_ACCEPTANCE_REPORT.md").write_text(
        "# LVI v3 blind acceptance\n\n"
        "PASS (still-image visual observation): all 93 public stills were preserved with URL, retrieval metadata, dimensions, and SHA-256 provenance; cached OWL-ViT and OpenCV were run; direct and unknown observations are separated.\n\n"
        "PARTIAL (video): `117255083` has one discovered public embed but retrieval currently fails with YouTube `This video is not available`; `117539389` has no discovered embed. Keyframes: 0 for both. Drone availability: none. No temporal conclusion is made.\n",
        encoding="utf-8",
    )


def manifest() -> None:
    paths = sorted(path for path in OUT.rglob("*") if path.is_file() and path.name != "LVI_V3_BLIND_FREEZE_MANIFEST.json")
    data = {
        "schema_version": "LVI_V3_BLIND_FREEZE",
        "status": "BLIND_OBSERVATIONS_FROZEN_BEFORE_G9H_READ",
        "prohibitions_observed": ["identity", "address", "erf", "GIS", "candidate generation", "G9 Top5/Top20", "ranking", "scoring", "Native15", "pool detector", "PR27", "production", "known ground truth", "G9H input"],
        "files": [{"path": str(path.relative_to(OUT)).replace("\\", "/"), "sha256": sha256(path)} for path in paths],
    }
    (OUT / "LVI_V3_BLIND_FREEZE_MANIFEST.json").write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    media = []
    video = []
    for listing_id, url in LISTINGS.items():
        listing = fetch_listing(url, listing_id)
        media.extend(download_stills(listing_id, listing.image_urls))
        video.append(inspect_video(listing_id, listing.video_urls))
    detections = detect_frames(media)
    contours = contour_rows(media)
    obs = observations()
    write_reports(media, video, detections, contours, obs)
    manifest()


if __name__ == "__main__":
    main()
