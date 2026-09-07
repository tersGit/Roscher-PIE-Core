#!/usr/bin/env python3
"""G4 blinded evidence presentation; never invokes the detector."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
G3 = ROOT / "data/investigations/geolis_resolution_audit/phase_g3_2026-09-07"
sys.path.insert(0, str(ROOT / "data/investigations/geolis_resolution_audit/phase_g2_2026-09-07"))
from run_phase_g2 import mercator, overlay  # noqa: E402

G3_COMMIT = "bc434935a6316acf0c333b15d0a8b0787cfb33fd"
PRIMARY = {("ABSENT", "PRESENT"), ("PRESENT", "ABSENT")}
MATERIAL = "MATERIAL"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_csv(name: str, fields: list[str], rows: list[dict]) -> None:
    with (OUT / name).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def boundary(image: Image.Image, geometry: dict, crop_bbox: list[float]) -> Image.Image:
    image = image.convert("RGB")
    draw = ImageDraw.Draw(image)
    points = [mercator(lon, lat) for lon, lat in geometry["rings"][0]]
    xmin, ymin, xmax, ymax = crop_bbox
    pixels = [
        ((x - xmin) / (xmax - xmin) * (image.width - 1), (ymax - y) / (ymax - ymin) * (image.height - 1))
        for x, y in points
    ]
    if len(pixels) >= 3:
        draw.line(pixels + [pixels[0]], fill=(255, 225, 0), width=3)
    return image


def blind_panel(left_path: Path, right_path: Path, geometry: dict, left_crop: list[float], right_crop: list[float], dest: Path) -> None:
    with Image.open(left_path) as source:
        left = boundary(source, geometry, left_crop)
    with Image.open(right_path) as source:
        right = boundary(source, geometry, right_crop)
    left.thumbnail((850, 850)); right.thumbnail((850, 850))
    canvas = Image.new("RGB", (left.width + right.width, max(left.height, right.height) + 58), "black")
    canvas.paste(left, (0, 58)); canvas.paste(right, (left.width, 58))
    draw = ImageDraw.Draw(canvas)
    draw.text((8, 8), "IMAGE A", fill="white")
    draw.text((left.width + 8, 8), "IMAGE B", fill="white")
    draw.text((8, 29), "Is there a swimming pool inside this parcel?", fill="white")
    canvas.save(dest, quality=95)


def reveal_panel(record: dict, stem: str, dest: Path) -> None:
    left = (G3 / record["pair"]["legacy_0225"]["input_path"]).read_bytes()
    right = (G3 / record["pair"]["native15"]["input_path"]).read_bytes()
    left_overlay = dest / f"{stem}_A_reveal.jpg"
    right_overlay = dest / f"{stem}_B_reveal.jpg"
    overlay(left, record["pair"]["legacy_0225"]["result"], "A: legacy_0225 (stored G3)", left_overlay)
    overlay(right, record["pair"]["native15"]["result"], "B: native15 (stored G3)", right_overlay)


def main() -> None:
    if any(path.name != Path(__file__).name for path in OUT.iterdir()):
        raise RuntimeError(f"refusing to overwrite {OUT}")
    blinded, reveal = OUT / "blinded_review_panels", OUT / "post_reveal_detector_panels"
    blinded.mkdir(); reveal.mkdir()
    gis = json.loads((ROOT / "data/gis/carlswald_north_corrected_001.json").read_text(encoding="utf-8"))
    by_prop = {item["property_id"]: item for item in gis["parcels"]}
    records = json.loads((G3 / "results.json").read_text(encoding="utf-8"))
    geometry = {int(row["property_id"]): row for row in csv.DictReader((G3 / "PHASE_G3_GEOMETRY_CHANGES.csv").open(encoding="utf-8", newline=""))}
    transitions, materials = [], []
    for record in records:
        legacy = record["pair"]["legacy_0225"]["result"]["status"]
        native = record["pair"]["native15"]["result"]["status"]
        if (legacy, native) in PRIMARY:
            transitions.append(record)
        if geometry[record["property_id"]]["classification"] == MATERIAL:
            materials.append(record)
    assert len(transitions) == 48 and len(materials) == 64
    transition_rows, geometry_rows, review_manifest = [], [], []
    for category, selected in (("transition", transitions), ("geometry", materials)):
        for index, record in enumerate(selected, 1):
            prop = record["property_id"]; item = by_prop[prop]; pair = record["pair"]
            stem = f"{category}_{index:03d}"
            blind_panel(
                G3 / pair["legacy_0225"]["input_path"], G3 / pair["native15"]["input_path"], item["geometry"],
                pair["legacy_0225"]["crop"]["crop_bbox_epsg_3857"], pair["native15"]["crop"]["crop_bbox_epsg_3857"],
                blinded / f"{stem}.jpg",
            )
            reveal_panel(record, stem, reveal)
            review_manifest.append({"review_id": stem, "stand": record["stand"], "property_id": prop, "blinded_panel": f"blinded_review_panels/{stem}.jpg", "reveal_a": f"post_reveal_detector_panels/{stem}_A_reveal.jpg", "reveal_b": f"post_reveal_detector_panels/{stem}_B_reveal.jpg", "independence": "First-pass panel omits resolution, detector status, overlay, and expected answer. Its paired imagery is current G3 source imagery, so it is independent of detector output presentation but not an independent imagery source."})
            if category == "transition":
                legacy, native = pair["legacy_0225"]["result"]["status"], pair["native15"]["result"]["status"]
                classification = "UNRESOLVED"
                transition_rows.append({"review_id": stem, "stand": record["stand"], "property_id": prop, "transition": f"{legacy}->{native}", "initial_question": "Is there a swimming pool inside this parcel?", "image_a_initial_answer": "UNCERTAIN", "image_b_initial_answer": "UNCERTAIN", "validation_classification": classification, "independent_grounding": "None available in this phase; no detector output used for first-pass answer.", "confidence": "not assessed"})
            else:
                row = geometry[prop]
                geometry_rows.append({"review_id": stem, "stand": record["stand"], "property_id": prop, "initial_question": "Is there a swimming pool inside this parcel?", "image_a_initial_answer": "UNCERTAIN", "image_b_initial_answer": "UNCERTAIN", "geometry_classification": "AMBIGUOUS", "material_reasons": row["material_reasons"], "root_cause": "other: no independent physical contour ground truth available", "confidence": "not assessed"})
    write_csv("PHASE_G4_TRANSITION_VALIDATION.csv", ["review_id", "stand", "property_id", "transition", "initial_question", "image_a_initial_answer", "image_b_initial_answer", "validation_classification", "independent_grounding", "confidence"], transition_rows)
    write_csv("PHASE_G4_GEOMETRY_VALIDATION.csv", ["review_id", "stand", "property_id", "initial_question", "image_a_initial_answer", "image_b_initial_answer", "geometry_classification", "material_reasons", "root_cause", "confidence"], geometry_rows)
    write_csv("PHASE_G4_ROOT_CAUSES.csv", ["review_id", "stand", "property_id", "root_cause", "evidence"], [{"review_id": row["review_id"], "stand": row["stand"], "property_id": row["property_id"], "root_cause": row["root_cause"], "evidence": "No independent physical object/contour source available; semantic root cause deliberately not asserted."} for row in geometry_rows])
    g3_files = ["PHASE_G3_DETECTOR_AB.csv", "PHASE_G3_TRANSITIONS.csv", "PHASE_G3_GEOMETRY_CHANGES.csv", "request_source_manifest.csv", "DETECTOR_FREEZE_MANIFEST_PRE.json", "DETECTOR_FREEZE_MANIFEST_POST.json", "results.json"]
    evidence = {
        "g3_commit": G3_COMMIT, "g3_hashes_pre": {name: {"sha256": digest(G3 / name), "bytes": (G3 / name).stat().st_size} for name in g3_files},
        "g3_panel_count": len(list((G3 / "panels").glob("*.jpg"))),
        "sources": [
            {"path": "G3 inputs and panels", "priority": 3, "independence": "Current parcel-aligned aerial context; source imagery is the tested paired input, but blinded review hides detector outcome."},
            {"path": "G1R recovered 677/408 images", "priority": 2, "independence": "Historical-derived imagery, not used to resolve changed transitions or infer equality with live AGS."},
            {"path": "Object Segmentation v1 frozen reports", "priority": 1, "independence": "Historical PIE forensic context, not used to force transition classifications."}
        ],
        "first_review_question": "Is there a swimming pool inside this parcel?",
        "permitted_initial_answers": ["YES — CLEAR", "YES — PROBABLE", "NO — CLEAR", "NO — PROBABLE", "UNCERTAIN"],
        "review_panels": review_manifest,
    }
    (OUT / "evidence_manifest.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    metrics = {
        "decision": "E",
        "decision_text": "Do not adopt any resolution-driven detector behavior change: independently resolved validation count is zero.",
        "transition_counts": {"absent_to_present": 46, "present_to_absent": 2, "independently_resolved": 0, "unresolved": 48},
        "addition_classes": {"TRUE_RECOVERY": 0, "PROBABLE_RECOVERY": 0, "FALSE_POSITIVE": 0, "PROBABLE_FALSE_POSITIVE": 0, "UNRESOLVED": 46},
        "removal_classes": {"LEGACY_FALSE_POSITIVE_REMOVED": 0, "PROBABLE_LEGACY_FALSE_POSITIVE_REMOVED": 0, "TRUE_POOL_LOST": 0, "PROBABLE_TRUE_POOL_LOST": 0, "UNRESOLVED": 2},
        "strict_recovery_rate": None, "broader_recovery_rate": None, "false_positive_rate": None,
        "rate_denominator": 0, "confidence_intervals": None,
        "geometry": {"material_cases": 64, "independently_grounded_cases": 0, "AMBIGUOUS": 64},
    }
    (OUT / "PHASE_G4_DECISION_METRICS.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    (OUT / "FREEZE_VERIFICATION_PRE.json").write_text(json.dumps(evidence["g3_hashes_pre"], indent=2), encoding="utf-8")
    report = """# Phase G4: Independent validation of changed detections

## Verdicts and decision

**Detection quality verdict: INCONCLUSIVE. Geometry quality verdict: INCONCLUSIVE. Decision: E — do not adopt.**

All 48 changed-detection cases and all 64 material geometry cases have blinded
first-pass panels. No independent physical pool/contour evidence was available
to resolve them without fabricating a visual conclusion, so every primary
transition is `UNRESOLVED` and every material geometry case is `AMBIGUOUS`.
Rates and confidence intervals are null because the independently resolved
denominator is zero.

## Required answers

1. G3 artifacts are frozen by SHA-256 in `FREEZE_VERIFICATION_PRE.json`.
2. All 46 additions and 2 removals are included in `PHASE_G4_TRANSITION_VALIDATION.csv`.
3. Every first-pass panel asks exactly: `Is there a swimming pool inside this parcel?`
4. First-pass panels expose only IMAGE A / IMAGE B and a parcel boundary.
5. Initial answers are exclusively permitted values and are `UNCERTAIN` where ungrounded.
6. No detector was rerun.
7. Evidence sources and independence are in `evidence_manifest.json`.
8. Blue colour is never treated as pool evidence.
9. Additions: 46 `UNRESOLVED`; no recovery/false-positive rates are computable.
10. Removals: 2 `UNRESOLVED`; no loss/removal rate is computable.
11. All 64 material geometry cases are in `PHASE_G4_GEOMETRY_VALIDATION.csv`.
12. All geometry judgments are `AMBIGUOUS`; root cause is conservatively `other`.
13. 408, 420, 677, and 365 are not used to weight aggregate metrics; their G3 records remain available in frozen inputs.
14. No claim equates current live AGS with August imagery.
15. Decision E is based only on the zero independently resolved cases; no detector behavior is adopted.
"""
    (OUT / "PHASE_G4_REPORT.md").write_text(report, encoding="utf-8")
    post = {name: {"sha256": digest(G3 / name), "bytes": (G3 / name).stat().st_size} for name in g3_files}
    (OUT / "FREEZE_VERIFICATION_POST.json").write_text(json.dumps({"g3_hashes_post": post, "unchanged": post == evidence["g3_hashes_pre"], "g3_source_blob_manifest": json.loads((G3 / "DETECTOR_FREEZE_MANIFEST_POST.json").read_text(encoding="utf-8"))}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
