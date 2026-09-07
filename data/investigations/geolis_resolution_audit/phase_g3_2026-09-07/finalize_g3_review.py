"""Normalize G3's non-semantic material-case root-cause labels."""

from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
path = ROOT / "PHASE_G3_MANUAL_REVIEW.csv"
with path.open(encoding="utf-8", newline="") as handle:
    rows = list(csv.DictReader(handle))
for row in rows:
    row["observed_root_cause"] = (
        "other: paired frozen-detector contour selection changed; "
        "no physical-object cause established without ground truth"
    )
with path.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
