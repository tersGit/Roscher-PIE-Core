#!/usr/bin/env python3
"""Bind frozen opaque W3-V retrieval ranks to W1 labels after score freeze."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scores", required=True, type=Path)
    parser.add_argument("--source-crops", required=True, type=Path)
    parser.add_argument("--geojson", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    score_rows = list(csv.DictReader(args.scores.open(encoding="utf-8")))
    if len(score_rows) != 1010:
        raise RuntimeError(f"Expected 1010 frozen score rows, found {len(score_rows)}.")
    selected = score_rows[:30]
    sha_to_path = {hashlib.sha256(path.read_bytes()).hexdigest(): path for path in args.source_crops.glob("*_ags_aerial.jpg")}
    if len(sha_to_path) != 1010:
        raise RuntimeError("Frozen crop SHA map is incomplete or contains duplicate content.")
    features = json.loads(args.geojson.read_text(encoding="utf-8"))["features"]
    properties = {str(feature["properties"]["pie_property_id"]): feature["properties"] for feature in features}
    output_rows = []
    for row in selected:
        path = sha_to_path.get(row["crop_sha256"])
        if path is None:
            raise RuntimeError("A frozen shortlist digest was not found in the authorized crop corpus.")
        property_id = path.name.split("_")[1]
        props = properties.get(property_id)
        if props is None:
            raise RuntimeError(f"No W1 feature matches frozen crop property ID {property_id}.")
        output_rows.append({
            "retrieval_rank": row["retrieval_rank"],
            "top10": "YES" if int(row["retrieval_rank"]) <= 10 else "NO",
            "crop_sha256": row["crop_sha256"],
            "pie_property_id": property_id,
            "extension": props["extension"],
            "stand_number": props["stand_number"],
            "area_sqm": props["area_sqm"],
            "water_state": row["water_state"],
            "uncertainty": row["uncertainty"],
            "water_rectangularity": row["water_rectangularity"],
            "water_aspect": row["water_aspect"],
            "building_normalized": row["building_normalized"],
            "relation_normalized": row["relation_normalized"],
            "outdoor_normalized": row["outdoor_normalized"],
            "access_normalized": row["access_normalized"],
            "visibility": row["visibility"],
            "retrieval_score": row["retrieval_score"],
        })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output_rows[0]))
        writer.writeheader()
        writer.writerows(output_rows)
    print(f"shortlist_rows={len(output_rows)} top10=10")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
