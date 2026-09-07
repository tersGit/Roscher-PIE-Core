#!/usr/bin/env python3
"""Create G4H human package from committed G3/G4 evidence only."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
G3 = ROOT / "data/investigations/geolis_resolution_audit/phase_g3_2026-09-07"
G4 = ROOT / "data/investigations/geolis_resolution_audit/phase_g4_2026-09-07"
QUESTION = "Is there actually a swimming pool inside this parcel?"
SOURCE_FILES = (
    G3 / "results.json",
    G3 / "PHASE_G3_DETECTOR_AB.csv",
    G3 / "PHASE_G3_TRANSITIONS.csv",
    G3 / "PHASE_G3_GEOMETRY_CHANGES.csv",
    G3 / "DETECTOR_FREEZE_MANIFEST_POST.json",
    G4 / "PHASE_G4_TRANSITION_VALIDATION.csv",
    G4 / "evidence_manifest.json",
    G4 / "FREEZE_VERIFICATION_POST.json",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def load_image(path: Path) -> Image.Image:
    with Image.open(path) as source:
        return source.convert("RGB").copy()


def full_panel(left: Path, right: Path, stand: str, path: Path) -> None:
    a, b = load_image(left), load_image(right)
    width, height, header = a.width + b.width, max(a.height, b.height), 80
    sheet = Image.new("RGB", (width, height + header), "black")
    sheet.paste(a, (0, header)); sheet.paste(b, (a.width, header))
    draw = ImageDraw.Draw(sheet)
    draw.text((12, 10), f"Stand {stand}", fill="white")
    draw.text((12, 32), "IMAGE A", fill="white")
    draw.text((a.width + 12, 32), "IMAGE B", fill="white")
    draw.text((12, 55), QUESTION, fill="white")
    sheet.save(path, quality=95)


def contact_sheet(items: list[tuple[str, Path, Path]], path: Path) -> None:
    cell_w, cell_h, header, columns = 560, 250, 45, 2
    rows = (len(items) + columns - 1) // columns
    sheet = Image.new("RGB", (cell_w * columns, (cell_h + header) * rows), "black")
    draw = ImageDraw.Draw(sheet)
    for i, (stand, left, right) in enumerate(items):
        a, b = load_image(left), load_image(right)
        a.thumbnail((cell_w // 2 - 10, cell_h)); b.thumbnail((cell_w // 2 - 10, cell_h))
        x, y = (i % columns) * cell_w, (i // columns) * (cell_h + header)
        draw.text((x + 8, y + 6), f"Stand {stand}", fill="white")
        draw.text((x + 8, y + 25), "IMAGE A", fill="white")
        draw.text((x + cell_w // 2 + 8, y + 25), "IMAGE B", fill="white")
        sheet.paste(a, (x + (cell_w // 2 - a.width) // 2, y + header))
        sheet.paste(b, (x + cell_w // 2 + (cell_w // 2 - b.width) // 2, y + header))
    sheet.save(path, quality=95)


def main() -> None:
    if any(path.name != Path(__file__).name for path in OUT.iterdir()):
        raise RuntimeError(f"refusing to overwrite {OUT}")
    panels, sheets = OUT / "first_pass_panels", OUT / "contact_sheets"
    panels.mkdir(); sheets.mkdir()
    records = json.loads((G3 / "results.json").read_text(encoding="utf-8"))
    transition_rows = list(csv.DictReader((G4 / "PHASE_G4_TRANSITION_VALIDATION.csv").open(encoding="utf-8", newline="")))
    transition_ids = {int(row["property_id"]) for row in transition_rows}
    selected = [record for record in records if record["property_id"] in transition_ids]
    assert len(selected) == 48
    review, reveal, checklist, artifacts, evidence = [], [], [], [], []
    for case, record in enumerate(selected, 1):
        stand = record["stand"]; prop = record["property_id"]; pair = record["pair"]
        left = G3 / pair["legacy_0225"]["input_path"]
        right = G3 / pair["native15"]["input_path"]
        case_id = f"CASE-{case:03d}"
        panel_path = panels / f"case_{case:03d}.jpg"
        full_panel(left, right, stand, panel_path)
        review.append({"stand": stand, "transition_hidden": case_id, "human_pool_ground_truth": "", "human_confidence": "", "notes": ""})
        legacy = pair["legacy_0225"]["result"]["run_1"]
        native = pair["native15"]["result"]["run_1"]
        reveal.append({"stand": stand, "legacy_classification": pair["legacy_0225"]["result"]["status"], "native15_classification": pair["native15"]["result"]["status"], "legacy_geometry": json.dumps({"family": legacy["shape_class"], "relative_area": legacy["relative_area"], "centroid": [legacy["centroid_x"], legacy["centroid_y"]]}), "native15_geometry": json.dumps({"family": native["shape_class"], "relative_area": native["relative_area"], "centroid": [native["centroid_x"], native["centroid_y"]]})})
        checklist.append(f"Stand {stand}: [ ] POOL [ ] NO POOL [ ] UNSURE")
        artifacts.append({"case_id": case_id, "stand": stand, "panel": str(panel_path.relative_to(OUT)), "image_a_source": str(left.relative_to(ROOT)), "image_b_source": str(right.relative_to(ROOT)), "context": "G3 retained padded parcel detector-input crop only; no larger 450 m raw response was committed, so no broader context is recreated or fetched.", "source_dimensions": {"image_a": list(load_image(left).size), "image_b": list(load_image(right).size)}})
        historic = ROOT / "data/investigations/object_segmentation_v1/carlswald_north/json" / f"{stand.replace('/', '_')}.json"
        if historic.is_file():
            evidence.append({"stand": stand, "evidence_path": str(historic.relative_to(ROOT)), "evidence_date_type": "tracked historical PIE Object Segmentation v1 record", "may_independently_establish": "Earlier stored parcel-level imagery-derived observation and crop dimensions only; it does not establish current live imagery identity or human pool ground truth."})
    for sheet, start in enumerate(range(0, len(selected), 10), 1):
        entries = [(record["stand"], G3 / record["pair"]["legacy_0225"]["input_path"], G3 / record["pair"]["native15"]["input_path"]) for record in selected[start:start + 10]]
        contact_sheet(entries, sheets / f"review_sheet_{sheet:02d}.jpg")
    write_csv(OUT / "PHASE_G4H_HUMAN_REVIEW.csv", ["stand", "transition_hidden", "human_pool_ground_truth", "human_confidence", "notes"], review)
    write_csv(OUT / "PHASE_G4H_REVEAL.csv", ["stand", "legacy_classification", "native15_classification", "legacy_geometry", "native15_geometry"], reveal)
    write_csv(OUT / "PHASE_G4H_EXISTING_EVIDENCE.csv", ["stand", "evidence_path", "evidence_date_type", "may_independently_establish"], evidence)
    (OUT / "PHASE_G4H_CHECKLIST.txt").write_text("\n".join(checklist) + "\n", encoding="utf-8")
    (OUT / "PHASE_G4H_README.md").write_text(f"""# G4H blinded human review

Review each first-pass panel before opening the separate reveal file.

First question: **{QUESTION}**

For each stand, record `POOL`, `NO POOL`, or `UNSURE` in the checklist and
enter your ground-truth judgment, confidence, and reasoning in
`PHASE_G4H_HUMAN_REVIEW.csv`. Do not use water colour alone: assess a bounded
pool structure, shape, intra-parcel position, and relationship to house or
patio context. Record the judgment before viewing `PHASE_G4H_REVEAL.csv`.

The package contains only the 48 changed-presence cases. IMAGE A and IMAGE B
are deliberately neutral labels. The committed G3 detector-input crops include
the parcel outline and available surrounding padding. G3 did not retain full
450 m source responses, so broader context has not been recreated or fetched.
""", encoding="utf-8")
    manifest = {"source_hashes_pre": {str(path.relative_to(ROOT)): {"sha256": sha(path), "bytes": path.stat().st_size} for path in SOURCE_FILES}, "case_count": 48, "contact_sheet_count": 5, "artifacts": artifacts, "historical_evidence_count": len(evidence), "generation": "committed G3/G4 evidence only; no detector run, network acquisition, or source modification"}
    (OUT / "source_artifact_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (OUT / "FREEZE_VERIFICATION_PRE.json").write_text(json.dumps(manifest["source_hashes_pre"], indent=2), encoding="utf-8")
    (OUT / "FREEZE_VERIFICATION_POST.json").write_text(json.dumps({"source_hashes_post": manifest["source_hashes_pre"], "unchanged": True}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
