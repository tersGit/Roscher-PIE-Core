#!/usr/bin/env python3
"""Diagnostic re-eval for Pool Object Validation v1.

Does not rewrite historical freezes, OS v1 JSON, GIS inventory, or rankings.
Outputs belong under data/investigations/pool_object_validation_v1/.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.gis.estate_ags_matching.hybrid_listing_pool_geometry_v1 import (  # noqa: E402
    FrameGeometry,
    combine_listing_frames,
)
from backend.gis.estate_ags_matching.os_scoring_v2 import V2_WEIGHTS_NO_BUILDING  # noqa: E402
from backend.gis.estate_ags_matching.pool_object_validation_v1 import (  # noqa: E402
    infer_image_size_from_geometry,
    mask_from_norm_contour,
    true_parcel_mask_from_geometry,
    validate_os_payload,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/investigations/pool_object_validation_v1"
OS_DIR = ROOT / "data/investigations/object_segmentation_v1/carlswald_north/json"
GIS_PATH = ROOT / "data/gis/carlswald_north_corrected_001.json"
CROP_DIR = ROOT / "data/visual_index/carlswald_north_corrected_001/_imagery_cache_native15"
STANDS = ("338", "677", "612", "408", "420", "570", "370")
LISTINGS = ("116978058", "116889694", "117262832")
FREEZE_SHA = {
    "117262832": "32ecd4b526d4a299e143c869761664a9ed7a4b2d9ae65aba6ed300583a1dd10a",
    "116978058": "8cf975a7a14326c520dbfcdba48a73d24df6e3605de1632d6174abab72d97628",
    "116889694": "69b8ea31f1ecdb77311937b2e3db829ef14ecea33b8534d2730a5ed57d331465",
    "116778622": "3eb8f54dc03f804cff519b65d7f452444ff91e7c4133a9ec7b9b638a3337875f",
    "116273255": "227a67c7100639300916d3a405da6030ff90b5d1dff54209c0160290c24ba500",
    "116223230": "be73a1615c5f87f678f9c4948c0d41b22d3f166aea3f10eb05b1ed6e98404126",
}
FROZEN_WEIGHTS = {
    "pool_presence": 0.14,
    "shape_v2": 0.36,
    "spatial_v2": 0.22,
    "aerial": 0.12,
    "exterior": 0.06,
    "gis": 0.03,
    "stand_size": 0.07,
}


def _gis() -> dict[str, dict]:
    return {str(p["stand_number"]): p for p in json.loads(GIS_PATH.read_text(encoding="utf-8"))["parcels"]}


def _hybrid_frames(listing_id: str) -> list[FrameGeometry]:
    block = json.loads((ROOT / f"data/investigations/blind_{listing_id}_complete_estate/hybrid_block.json").read_text(encoding="utf-8"))
    frames = []
    for item in block.get("frames") or []:
        dom = item.get("dominant") if isinstance(item.get("dominant"), dict) else None
        frames.append(
            FrameGeometry(
                media_id=item.get("media_id") or "",
                viewpoint=item.get("viewpoint") or "",
                source=item.get("source") or "",
                source_reason=item.get("source_reason") or "",
                scoring_ready=bool(item.get("scoring_ready")),
                pool_present=bool(item.get("pool_present")),
                yoloe_conf=float(item.get("yoloe_conf") or 0.0),
                n_components=int(item.get("n_components") or 0),
                dominant=dom,
                secondary=item.get("secondary") if isinstance(item.get("secondary"), dict) else None,
                component_relation=item.get("component_relation") or {},
                descriptors=item.get("descriptors") or {},
                contour_image=None if not dom else dom.get("contour_image"),
                spa_relationship=item.get("spa_relationship"),
                geometry_quality=float(item.get("geometry_quality") or 0.0),
                scoring_ready_reason=item.get("scoring_ready_reason") or "",
            )
        )
    return frames


def _draw_overlay(width: int, height: int, parcel, building, road, pool, crop_bgr=None) -> np.ndarray:
    if crop_bgr is not None:
        canvas = cv2.resize(crop_bgr, (width, height))
    else:
        canvas = np.full((height, width, 3), 32, np.uint8)
    if parcel is not None:
        canvas[parcel] = (canvas[parcel] * 0.65 + np.array([40, 90, 40])).astype(np.uint8)
        cnts, _ = cv2.findContours(parcel.astype(np.uint8) * 255, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(canvas, cnts, -1, (80, 220, 80), 2)
    if building is not None:
        cnts, _ = cv2.findContours(building.astype(np.uint8) * 255, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(canvas, cnts, -1, (40, 160, 255), 2)
    if road is not None:
        cnts, _ = cv2.findContours(road.astype(np.uint8) * 255, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(canvas, cnts, -1, (180, 180, 180), 2)
    if pool is not None:
        cnts, _ = cv2.findContours(pool.astype(np.uint8) * 255, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(canvas, cnts, -1, (0, 255, 255), 2)
    return canvas


def _legend(canvas: np.ndarray, lines: list[str]) -> np.ndarray:
    pad = 8 + 18 * len(lines)
    out = np.full((canvas.shape[0] + pad, canvas.shape[1], 3), 18, np.uint8)
    out[pad:] = canvas
    y = 16
    for line in lines:
        cv2.putText(out, line[:90], (8, y), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (240, 240, 240), 1, cv2.LINE_AA)
        y += 18
    return out


def _stand_panel(stand: str, payload: dict, gis_geom: dict | None, val) -> np.ndarray:
    geom = (payload.get("pool") or {}).get("geometry") or {}
    size = infer_image_size_from_geometry(geom) or (400, 400)
    width, height = size
    crop_path = CROP_DIR / f"{stand}_ags_aerial.jpg"
    crop = cv2.imread(str(crop_path)) if crop_path.is_file() else None
    parcel = true_parcel_mask_from_geometry((width, height), gis_geom)
    pool = mask_from_norm_contour((payload.get("pool") or {}).get("contour"), width, height)
    bld = mask_from_norm_contour((payload.get("building") or {}).get("contour"), width, height)
    drv = mask_from_norm_contour((payload.get("driveway") or {}).get("contour"), width, height)
    overlay = _draw_overlay(width, height, parcel, bld, drv, pool, crop)
    clip = (payload.get("pool") or {}).get("clip") or {}
    sig = val.signals
    lines = [
        f"Stand {stand}  OLD={(payload.get('pool') or {}).get('status')}  NEW={val.final_status}  conf={val.final_pool_object_confidence}",
        f"old CLIP pool={float(clip.get('pool') or 0):.3f} roof={float(clip.get('roof') or 0):.3f} shadow={float(clip.get('shadow') or 0):.3f}",
        f"parcel_in={sig.parcel_containment} edge={sig.parcel_edge_risk} bld={sig.building_overlap} road={sig.road_overlap}",
        f"geom={sig.geometry_plausibility} area={sig.area_plausibility} yard={sig.yard_context} neighbour={sig.neighbour_risk}",
        f"reasons={','.join(val.reason_codes)[:80]}",
        "green=true parcel  orange=building  grey=driveway  cyan=candidate  (crop if available)",
    ]
    labeled = _legend(overlay, lines)
    return labeled


def _listing_frame_panel(frame: FrameGeometry, status_note: str) -> np.ndarray:
    contour = None
    if isinstance(frame.dominant, dict):
        contour = frame.dominant.get("contour_image") or frame.contour_image
    canvas = np.full((280, 320, 3), 28, np.uint8)
    if contour:
        pts = np.array([[int(p[0] * 319), int(p[1] * 279)] for p in contour], np.int32)
        if len(pts) >= 3:
            cv2.polylines(canvas, [pts], True, (0, 255, 255), 2)
            cx = int(np.mean(pts[:, 0]))
            cy = int(np.mean(pts[:, 1]))
            cv2.circle(canvas, (cx, cy), 4, (0, 0, 255), -1)
    val = frame.pool_object_validation or {}
    geom = (frame.dominant or {}).get("geometry") or {}
    clip = (frame.dominant or {}).get("clip") or {}
    lines = [
        f"{frame.media_id[-3:]} {frame.viewpoint} {frame.source}",
        f"{status_note} ready={frame.scoring_ready} principal={getattr(frame, 'principal_pool_candidate', False)}",
        f"status={val.get('final_status')} role={getattr(frame, 'object_role', val.get('object_role'))} area={geom.get('relative_area')}",
        f"aspect={geom.get('aspect_ratio')} sol={geom.get('solidity')} CLIP pool={float(clip.get('pool') or 0):.3f}",
        f"centroid={((frame.dominant or {}).get('centroid_xy'))}",
    ]
    return _legend(canvas, lines)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "panels").mkdir(exist_ok=True)
    gis = _gis()
    candidate_rows = []
    for stand in STANDS:
        payload = json.loads((OS_DIR / f"{stand}.json").read_text(encoding="utf-8"))
        val = validate_os_payload(payload, gis_geometry=(gis.get(stand) or {}).get("geometry"))
        row = {
            "stand": stand,
            "old_status": (payload.get("pool") or {}).get("status"),
            "old_notes": (payload.get("pool") or {}).get("notes"),
            "old_clip": (payload.get("pool") or {}).get("clip"),
            "new": val.to_dict(),
        }
        candidate_rows.append(row)
        if stand in {"338", "612", "408", "570", "420"}:
            panel = _stand_panel(stand, payload, (gis.get(stand) or {}).get("geometry"), val)
            cv2.imwrite(str(OUT / "panels" / f"candidate_{stand}.jpg"), panel)
        print(f"OS {stand}: OLD={(payload.get('pool') or {}).get('status')} NEW={val.final_status} reasons={val.reason_codes}", flush=True)

    listing_rows = {}
    for listing_id in LISTINGS:
        frames = _hybrid_frames(listing_id)
        old_block = json.loads((ROOT / f"data/investigations/blind_{listing_id}_complete_estate/hybrid_block.json").read_text(encoding="utf-8"))
        old_chosen = (old_block.get("listing") or {}).get("chosen_id")
        summary = combine_listing_frames(frames)
        listing_rows[listing_id] = {
            "old_chosen_id": old_chosen,
            "new_chosen_id": summary.get("chosen_id"),
            "new_viewpoint": summary.get("chosen_viewpoint"),
            "new_source": summary.get("chosen_source"),
            "frame_selection_reason": summary.get("frame_selection_reason"),
            "n_principal_candidates": summary.get("n_principal_candidates"),
            "clusters": summary.get("multiframe_clusters"),
            "per_frame": summary.get("per_frame_extraction_quality"),
        }
        print(f"LIST {listing_id}: OLD={old_chosen} NEW={summary.get('chosen_id')}", flush=True)
        if listing_id == "117262832":
            useful = [f for f in frames if str(f.media_id)[-3:] in {"003", "037", "038", "039"}]
            tiles = []
            for frame in useful:
                note = "NEW OFFICIAL" if frame.media_id == summary.get("chosen_id") else ("OLD OFFICIAL" if frame.media_id.endswith("039") else "")
                tiles.append(_listing_frame_panel(frame, note))
            if tiles:
                max_h = max(t.shape[0] for t in tiles)
                padded = [np.pad(t, ((0, max_h - t.shape[0]), (0, 0), (0, 0))) for t in tiles]
                grid = np.hstack(padded)
                cv2.imwrite(str(OUT / "panels" / "listing_117262832_frames.jpg"), grid)
            old_f = next((f for f in frames if str(f.media_id).endswith("039")), None)
            new_f = next((f for f in frames if f.media_id == summary.get("chosen_id")), None)
            if old_f and new_f:
                pair = np.hstack(
                    [
                        cv2.resize(_listing_frame_panel(old_f, "OLD OFFICIAL 039"), (360, 360)),
                        cv2.resize(_listing_frame_panel(new_f, "NEW OFFICIAL"), (360, 360)),
                    ]
                )
                cv2.imwrite(str(OUT / "panels" / "listing_117262832_old_vs_new.jpg"), pair)

    freeze_ok = {}
    for listing_id, digest in FREEZE_SHA.items():
        path = ROOT / f"data/investigations/blind_{listing_id}_complete_estate/freeze.sha256"
        recorded = path.read_text(encoding="utf-8").strip() if path.is_file() else None
        freeze_ok[listing_id] = recorded == digest

    row338 = next(r for r in candidate_rows if r["stand"] == "338")
    list832 = listing_rows["117262832"]
    courtyard = list832["new_chosen_id"] in {"117262832-037", "117262832-038"}
    report = {
        "version": "pool_object_validation_v1",
        "ranking_weights_unchanged": V2_WEIGHTS_NO_BUILDING == FROZEN_WEIGHTS,
        "historical_freeze_hashes_ok": freeze_ok,
        "candidates": candidate_rows,
        "listings": listing_rows,
        "verdicts": {
            "stand_338_old": row338["old_status"],
            "stand_338_new": row338["new"]["final_status"],
            "stand_338_independent_signals": row338["new"]["final_status"] != "REJECTED"
            or "clip" not in " ".join(row338["new"].get("reason_codes") or []).lower(),
            "listing_117262832_principal_pool": "YES" if courtyard else "NO",
            "regression_570_rejected": next(r["new"]["final_status"] for r in candidate_rows if r["stand"] == "570")
            == "REJECTED",
            "regression_612_not_confirmed": next(r["new"]["final_status"] for r in candidate_rows if r["stand"] == "612")
            != "CONFIRMED",
            "regression_408_not_confirmed": next(r["new"]["final_status"] for r in candidate_rows if r["stand"] == "408")
            != "CONFIRMED",
        },
        "panel_paths": sorted(str(p.relative_to(ROOT)) for p in (OUT / "panels").glob("*.jpg")),
        "note": "Diagnostic only. Frozen OS JSON and blind freeze trees were not rewritten.",
    }
    (OUT / "results.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    md = OUT / "REPORT.md"
    md.write_text(
        "\n".join(
            [
                "# Pool Object Validation v1 — diagnostic re-eval",
                "",
                "Historical freezes and OS v1 JSON were not modified. Ranking weights were not changed.",
                "",
                f"- Stand 338 OLD `{row338['old_status']}` → NEW `{row338['new']['final_status']}`",
                f"- Reasons: `{', '.join(row338['new'].get('reason_codes') or [])}`",
                f"- Listing 117262832 OLD `{list832['old_chosen_id']}` → NEW `{list832['new_chosen_id']}`",
                f"- Principal courtyard pool: **{'YES' if courtyard else 'NO'}**",
                f"- 570 REJECTED: **{report['verdicts']['regression_570_rejected']}**",
                f"- 612 not CONFIRMED: **{report['verdicts']['regression_612_not_confirmed']}**",
                f"- 408 not CONFIRMED: **{report['verdicts']['regression_408_not_confirmed']}**",
                f"- Freeze hashes unchanged: **{all(freeze_ok.values())}**",
                f"- Weights unchanged: **{report['ranking_weights_unchanged']}**",
                "",
                "Panels: `data/investigations/pool_object_validation_v1/panels/`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps(report["verdicts"], indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
