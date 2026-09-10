#!/usr/bin/env python3
"""Build the post-freeze, diagnostic-only Waterfall W2 VLM review package."""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.imagery.ags_client import AGSAerialClient

SOURCE = ROOT / "data" / "investigations" / "waterfall_w2_rl5480_blind"
W1_GEOJSON = ROOT / "data" / "estates" / "waterfall_country_estate" / "waterfall_country_estate_w1.geojson"
OUT = ROOT / "data" / "investigations" / "waterfall_w2_rl5480_vlm"
PACKAGE = OUT / "portable_package"
W1_SHA256 = "6a375bf542bcff28c6a3ee862f9e0c3c9a5395d0497b4159027c40b75cf7be3a"
LISTING_SHA256 = "2e354ad931df2fdfa7dd509f73a0551ee6e3d934cb265dcbe4e47e8ef7fba2b4"
RANKING_SHA256 = "93b488bef582d5a97f5dc034cca4eded86520912ac6cebec28620cbd149b4a0e"
TOP10 = (
    (1, "972", 19, "2033220", 0.7878),
    (2, "838", 19, "2032570", 0.7829),
    (3, "1018", 19, "2033278", 0.7771),
    (4, "906", 19, "2033195", 0.7763),
    (5, "3269", 105, "2083833", 0.7751),
    (6, "1002", 19, "2033255", 0.7749),
    (7, "3323", 105, "2083663", 0.7739),
    (8, "1169", 19, "2032908", 0.7739),
    (9, "897", 19, "2033185", 0.7734),
    (10, "1081", 19, "2033104", 0.7727),
)
LISTING_ALLOWLIST = (
    ("strong_pool_rear", "02_01.jpg"),
    ("pool_house", "08_02.jpg"),
    ("garage_driveway", "01_25.jpg"),
    ("whole_house_roof", "11_07.jpg"),
    ("garden_open_space", "34_37.jpg"),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(OUT).as_posix()


def json_write(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def verify_freezes() -> list[dict[str, Any]]:
    checks = (
        ("listing_visual_observations.json", LISTING_SHA256),
        ("ranking_freeze.json", RANKING_SHA256),
    )
    result = []
    for name, expected in checks:
        actual = sha256(SOURCE / name)
        if actual != expected:
            raise RuntimeError(f"frozen {name} hash mismatch: {actual}")
        result.append({"artifact": name, "sha256": actual})
    if sha256(W1_GEOJSON) != W1_SHA256:
        raise RuntimeError("immutable W1 GeoJSON hash mismatch")
    ranking = json.loads((SOURCE / "ranking_full.json").read_text(encoding="utf-8"))
    if len(ranking) != 1010:
        raise RuntimeError("official frozen ranking must contain exactly 1,010 candidates")
    expected = [{"rank": r, "stand_number": s, "extension": e, "property_id": p, "total_score": score}
                for r, s, e, p, score in TOP10]
    actual = [{key: row[key] for key in expected[0]} for row in ranking[:10]]
    if actual != expected:
        raise RuntimeError("official frozen Top-10 does not match the required ranking")
    return result


def feature_index() -> dict[str, dict[str, Any]]:
    collection = json.loads(W1_GEOJSON.read_text(encoding="utf-8"))
    wanted = {item[3] for item in TOP10}
    features = {
        str(feature["properties"]["pie_property_id"]): feature
        for feature in collection["features"]
        if str(feature["properties"]["pie_property_id"]) in wanted
    }
    if set(features) != wanted:
        raise RuntimeError("frozen W1 geometry is incomplete for the official Top-10")
    return features


def bounds(feature: dict[str, Any]) -> tuple[float, float, float, float]:
    points = [point for ring in feature["geometry"]["rings"] for point in ring]
    lon = [float(point[0]) for point in points]
    lat = [float(point[1]) for point in points]
    # Match W2's fixed 135 m context crop while never exporting coordinates.
    cx, cy = sum(lon) / len(lon), sum(lat) / len(lat)
    margin = 0.00075
    return cx - margin, cy - margin, cx + margin, cy + margin


def draw_overlay(image_path: Path, feature: dict[str, Any], output: Path) -> None:
    min_lon, min_lat, max_lon, max_lat = bounds(feature)
    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    for ring in feature["geometry"]["rings"]:
        pixels = [
            ((float(lon) - min_lon) / (max_lon - min_lon) * image.width,
             (max_lat - float(lat)) / (max_lat - min_lat) * image.height)
            for lon, lat in ring
        ]
        if len(pixels) >= 3:
            draw.line(pixels + [pixels[0]], fill=(0, 255, 0), width=4)
    image.save(output, quality=92)


def export_candidates(features: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    client = AGSAerialClient(timeout_s=90.0)
    records = []
    candidate_dir = PACKAGE / "candidates"
    candidate_dir.mkdir(parents=True, exist_ok=True)
    for rank, stand, extension, property_id, score in TOP10:
        min_lon, min_lat, max_lon, max_lat = bounds(features[property_id])
        crop = candidate_dir / f"rank_{rank:02d}_stand_{stand}_ext_{extension}_id_{property_id}_native15.jpg"
        crop.write_bytes(client.export_bbox(
            min_lon=min_lon, min_lat=min_lat, max_lon=max_lon, max_lat=max_lat,
            width=900, height=900, year=2023,
        ))
        overlay = crop.with_name(crop.stem + "_parcel_overlay.jpg")
        draw_overlay(crop, features[property_id], overlay)
        records.append({
            "official_rank": rank, "stand": stand, "extension": extension,
            "property_id": property_id, "official_score": score,
            "native15_crop": rel(crop), "parcel_overlay": rel(overlay),
            "frozen_detector_pool_region": "NOT_EXPORTED_BY_FROZEN_W2",
            "frozen_detector_pool_state": "YES",
        })
    return records


def export_listing() -> list[dict[str, str]]:
    records = []
    target = PACKAGE / "listing_views"
    target.mkdir(parents=True, exist_ok=True)
    for role, source_name in LISTING_ALLOWLIST:
        source = SOURCE / "listing_media" / source_name
        destination = target / f"{role}.jpg"
        shutil.copyfile(source, destination)
        records.append({"role": role, "path": rel(destination)})
    return records


def export_frozen_listing_observations() -> str:
    """Retain frozen visual statements while excluding listing URL and text metadata."""
    source = json.loads((SOURCE / "listing_visual_observations.json").read_text(encoding="utf-8"))
    payload = {
        "schema_version": "waterfall-w2-listing-observations-v1-sanitized-export",
        "source_sha256": LISTING_SHA256,
        "listing_reference": "RL5480",
        "ground_truth_recovery": "NOT_STARTED",
        "observations": [
            {
                "feature": item["feature"],
                "state": item["state"],
                "confidence": item["confidence"],
                "source_images": item["source_images"],
                "expected_aerial_visibility": item["expected_aerial_visibility"],
                "detail": item["detail"],
            }
            for item in source["observations"]
        ],
    }
    destination = PACKAGE / "frozen_listing_visual_observations.json"
    json_write(destination, payload)
    return rel(destination)


def contact_sheet(candidates: list[dict[str, Any]], listing: list[dict[str, str]]) -> Path:
    cell_w, cell_h = 420, 500
    sheet = Image.new("RGB", (cell_w * 3, cell_h * 5), "white")
    draw = ImageDraw.Draw(sheet)
    items = [(f"Candidate #{row['official_rank']}", OUT / row["parcel_overlay"]) for row in candidates]
    items += [(f"Listing: {row['role']}", OUT / row["path"]) for row in listing]
    for index, (label, path) in enumerate(items):
        image = Image.open(path).convert("RGB")
        image.thumbnail((cell_w - 16, cell_h - 55))
        x, y = (index % 3) * cell_w, (index // 3) * cell_h
        sheet.paste(image, (x + (cell_w - image.width) // 2, y + 5))
        draw.text((x + 8, y + cell_h - 44), label, fill="black")
        if label.startswith("Candidate"):
            row = candidates[index]
            draw.text((x + 8, y + cell_h - 24),
                      f"stand {row['stand']} ext {row['extension']} ID {row['property_id']} score {row['official_score']}",
                      fill="black")
    output = OUT / "W2_TOP10_CONTACT_SHEET.jpg"
    sheet.save(output, quality=92)
    return output


def write_manual_review(candidates: list[dict[str, Any]], listing: list[dict[str, str]]) -> None:
    rows = [
        "# Waterfall W2 Top-10 Manual Review",
        "",
        "Diagnostic-only visual comparison. This is not an identity determination, ranking update, hard gate, or ground-truth recovery.",
        "",
        "Listing references: " + ", ".join(f"`{item['role']}`" for item in listing) + ".",
        "Each candidate panel contains its native15 crop and frozen-W1 parcel boundary overlay. "
        "The W2 frozen detector reported pool `YES`, but did not export a pool-region geometry; no region is reconstructed here.",
        "",
        "| Rank | Stand | Ext | Property ID | Frozen score | Panel | Review prompts |",
        "| ---: | --- | ---: | --- | ---: | --- | --- |",
    ]
    for row in candidates:
        rows.append(
            f"| {row['official_rank']} | {row['stand']} | {row['extension']} | {row['property_id']} | "
            f"{row['official_score']:.4f} | `{row['parcel_overlay']}` | Parcel boundary; native15 crop; "
            "pool region unavailable from freeze; roof structure; driveway access; immediate context. |"
        )
    rows.extend([
        "",
        "Review constraints: do not infer ownership, parcel membership, compass orientation, addresses, identities, "
        "or complete garage counts. Treat non-visible evidence as `UNKNOWN`, not `NO`. Stand size is informational only (at most 5%).",
        "",
    ])
    (OUT / "W2_TOP10_MANUAL_REVIEW.md").write_text("\n".join(rows), encoding="utf-8")


def write_schemas() -> None:
    adapter = {
        "schema_version": "vlm-evidence-adapter-v1",
        "diagnostic_only": True,
        "production_integration": "PROHIBITED",
        "observation_fields": {
            "source_image_or_frame": "required string",
            "feature": "required string",
            "observation": "required string",
            "state": ["OBSERVED", "INFERRED", "UNKNOWN"],
            "confidence": "number 0..1 subject to caps",
            "aerial_relevance": ["HIGH", "MEDIUM", "LOW", "UNKNOWN"],
            "caveat": "required string",
        },
        "confidence_caps": {
            "direct_visible": 1.0,
            "perspective_form": 0.85,
            "cross_view_relation_unless_directly_visible": 0.80,
            "ownership_parcel_neighbour_membership_unless_independent_gis_proves": 0.40,
        },
        "rules": [
            "Never convert not-visible to NO.",
            "Compass is UNKNOWN unless independently proven.",
            "Total garage counts are UNKNOWN unless complete frontage is visibly covered.",
            "Observations are not hard truth, hard gates, or ranking changes.",
        ],
    }
    comparison = {
        "schema_version": "waterfall-w2-vlm-comparison-v1",
        "candidate": {"official_rank": "integer", "stand": "string", "extension": "integer", "property_id": "string"},
        "fields": ["pool", "house_roof", "house_pool_relation", "driveway_garage", "parcel_context", "neighbour_context"],
        "per_field": {"verdict": ["MATCH", "PARTIAL", "CONFLICT", "UNKNOWN"], "confidence": "0..1", "reason": "string"},
        "output": {"overall_compat": "MATCH|PARTIAL|CONFLICT|UNKNOWN", "supports": ["string"], "conflicts": ["string"], "unknowns": ["string"]},
        "constraints": [
            "No identity declaration or address/name metadata.",
            "UNKNOWN cannot cause hard rejection.",
            "Do not assume common or neighbour facilities are owned by the candidate.",
            "Stand size is informational only (<=5%) and not a major discriminator.",
            "Record detector/VLM disagreement without resolving it.",
        ],
    }
    json_write(OUT / "vlm_evidence_adapter_v1.schema.json", adapter)
    json_write(OUT / "vlm_comparison.schema.json", comparison)


def manifest(candidates: list[dict[str, Any]], listing: list[dict[str, str]], observations: str) -> Path:
    files = sorted(path for path in OUT.rglob("*") if path.is_file() and path.name != "export_manifest.json")
    records = [{"path": rel(path), "sha256": sha256(path), "bytes": path.stat().st_size} for path in files]
    payload = {
        "schema_version": "waterfall-w2-vlm-portable-manifest-v1",
        "created_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "scope": "post-freeze visual diagnostic only; target identity remains UNKNOWN",
        "ground_truth_recovery": "NOT_STARTED",
        "frozen_inputs": {"w1_geojson_sha256": W1_SHA256, "listing_visual_sha256": LISTING_SHA256, "ranking_sha256": RANKING_SHA256},
        "listing_image_count": len(listing),
        "candidate_image_count": len(candidates) * 2,
        "candidates": candidates,
        "listing_views": listing,
        "frozen_listing_observations": observations,
        "files": records,
    }
    destination = OUT / "export_manifest.json"
    json_write(destination, payload)
    return destination


def make_zip() -> Path:
    destination = OUT / "waterfall_w2_rl5480_vlm_portable.zip"
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(PACKAGE.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(OUT).as_posix())
        for name in ("W2_TOP10_MANUAL_REVIEW.md", "W2_TOP10_CONTACT_SHEET.jpg", "vlm_evidence_adapter_v1.schema.json", "vlm_comparison.schema.json", "export_manifest.json", "export_manifest.sha256"):
            archive.write(OUT / name, name)
    return destination


def main() -> int:
    verify_freezes()
    if OUT.exists():
        raise RuntimeError(f"refusing to overwrite existing diagnostic output: {OUT}")
    PACKAGE.mkdir(parents=True)
    candidates = export_candidates(feature_index())
    listing = export_listing()
    observations = export_frozen_listing_observations()
    contact_sheet(candidates, listing)
    write_manual_review(candidates, listing)
    write_schemas()
    manifest_path = manifest(candidates, listing, observations)
    (OUT / "export_manifest.sha256").write_text(sha256(manifest_path) + "\n", encoding="ascii")
    zip_path = make_zip()
    print(json.dumps({"zip_path": str(zip_path), "zip_sha256": sha256(zip_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
