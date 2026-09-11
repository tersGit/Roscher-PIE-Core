#!/usr/bin/env python3
"""Render post-freeze W3-V shortlist panels with W1 parcel overlay."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw


def mercator(latitude: float, longitude: float) -> tuple[float, float]:
    radius = 6378137.0
    x = radius * math.radians(longitude)
    y = radius * math.log(math.tan(math.pi / 4 + math.radians(latitude) / 2))
    return x, y


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shortlist", required=True, type=Path)
    parser.add_argument("--source-crops", required=True, type=Path)
    parser.add_argument("--geojson", required=True, type=Path)
    parser.add_argument("--target-pool", required=True, type=Path)
    parser.add_argument("--target-context", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    rows = list(csv.DictReader(args.shortlist.open(encoding="utf-8")))
    features = {str(item["properties"]["pie_property_id"]): item for item in json.loads(args.geojson.read_text(encoding="utf-8"))["features"]}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    target_pool = Image.open(args.target_pool).convert("RGB").resize((600, 338))
    target_context = Image.open(args.target_context).convert("RGB").resize((600, 338))
    for row in rows:
        feature = features[row["pie_property_id"]]
        props = feature["properties"]
        crop = Image.open(args.source_crops / f"{row['extension']}_{row['pie_property_id']}_ags_aerial.jpg").convert("RGB")
        draw_crop = ImageDraw.Draw(crop)
        cx, cy = mercator(float(props["centroid_latitude"]), float(props["centroid_longitude"]))
        points = []
        for ring in feature["geometry"].get("rings", []):
            points.append([])
            for lon, lat in ring:
                x, y = mercator(float(lat), float(lon))
                points[-1].append(((x - (cx - 67.5)) / 135 * 900, ((cy + 67.5) - y) / 135 * 900))
        for ring in points:
            if len(ring) >= 3:
                draw_crop.line(ring, fill=(255, 230, 0), width=4, joint="curve")
        panel = Image.new("RGB", (1500, 900), "white")
        panel.paste(crop, (0, 0))
        panel.paste(target_pool, (900, 0))
        panel.paste(target_context, (900, 338))
        draw = ImageDraw.Draw(panel)
        draw.rectangle((900, 676, 1499, 899), fill=(245, 245, 245))
        draw.text((916, 692), f"Frozen retrieval rank: {row['retrieval_rank']}  |  score: {float(row['retrieval_score']):.4f}", fill="black")
        draw.text((916, 722), f"W1 Extension {row['extension']}  Stand {row['stand_number']}  Property {row['pie_property_id']}", fill="black")
        draw.text((916, 752), f"Water state: {row['water_state']}  |  uncertainty: {row['uncertainty']}", fill="black")
        draw.text((916, 782), f"Building {float(row['building_normalized']):.3f}  relation {float(row['relation_normalized']):.3f}", fill="black")
        draw.text((916, 812), "Left: W1 crop with parcel overlay. Right: target pool/context references.", fill="black")
        output = args.output_dir / f"rank_{int(row['retrieval_rank']):02d}_ext_{row['extension']}_stand_{row['stand_number']}.jpg"
        panel.save(output, quality=92)
    print(f"panels={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
