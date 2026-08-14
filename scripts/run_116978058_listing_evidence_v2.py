#!/usr/bin/env python3
"""Listing Evidence v2 diagnostic for Property24 listing 116978058.

Extraction quality gate only. Does not rerank the 330-stand estate unless
every gate criterion passes. Does not modify PR #6, PR #7, OS v1, native15
crops, or production ranking. Stand 365 is evaluation-only and is not an
input to extraction or scoring.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.gis.estate_ags_matching.listing_evidence_v2 import (
    assemble_channels,
    clip_viewpoint_scores,
    frame_public,
    observe_listing_frame,
    scoring_fingerprint_from_channels,
)
from backend.gis.estate_ags_matching.os_scoring_v2 import (
    OS_KEYS_NO_BUILDING,
    V2_WEIGHTS_NO_BUILDING,
    contour_descriptors,
    score_v2,
    v2_object_features,
)
from backend.gis.estate_ags_matching.final_candidates import assess_separation
from scripts.run_carlswald_north_corrected import stand_size_support

LISTING_ID = "116978058"
EVAL_STAND = "365"  # evaluation only; never passed into extraction
INSPECT = ("003", "005", "006", "025", "051", "052")
PHOTOS = ROOT / "data/investigations/carlswald_north_corrected" / LISTING_ID / "photos"
PR7 = ROOT / "data/investigations/os_scoring_v2" / f"carlswald_north_{LISTING_ID}" / "rerun_multi_image"
PR6_DIR = ROOT / "data/investigations/os_scoring_v2" / f"carlswald_north_{LISTING_ID}"
PR5_ALL = ROOT / "data/investigations/os_v1_ranking_experiment" / f"carlswald_north_{LISTING_ID}" / "all_candidates.json"
SEG_DIR = ROOT / "data/investigations/object_segmentation_v1/carlswald_north/json"
OUT = ROOT / "data/investigations/listing_evidence_v2" / f"carlswald_north_{LISTING_ID}"
LISTING_STAND_SQM = 972.0


def _font(size: int = 13):
    path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    return ImageFont.truetype(str(path), size) if path.is_file() else ImageFont.load_default()


def _safe(stand: str) -> str:
    return str(stand).replace("/", "_")


def load_photos() -> list[tuple[str, bytes]]:
    files = sorted(PHOTOS.glob(f"{LISTING_ID}-*.jpg")) + sorted(PHOTOS.glob(f"{LISTING_ID}-*.jpeg"))
    out = []
    for path in files:
        out.append((path.stem, path.read_bytes()))
    return out


def pr7_smear_reference() -> dict:
    latest = json.loads((PR7 / "latest.json").read_text(encoding="utf-8"))
    fusion = latest.get("fusion") or latest
    desc = fusion.get("fused_shape_descriptors") or {}
    source = fusion.get("shape_source")
    compactness = None
    for item in latest.get("listing_observations") or []:
        if item.get("media_id") == source:
            compactness = item.get("compactness")
            break
    return {
        "shape_source": source,
        "compactness": compactness,
        "circularity": desc.get("circularity"),
        "solidity": desc.get("solidity"),
        "elongation": desc.get("elongation"),
        "n_corners": desc.get("n_corners"),
        "n_major_indents": desc.get("n_major_indents"),
        "spatial_source": fusion.get("spatial_source"),
        "fused_pool_roof_ratio": fusion.get("fused_pool_roof_ratio"),
    }


def cleaner_than_pr7(best: dict | None, smear: dict) -> dict:
    if not best:
        return {"passed": False, "reason": "no_overview_contour"}
    compact = float(best.get("compactness") or 0)
    circularity = float(best.get("circularity") or 0)
    indents = int(best.get("n_major_indents") or 99)
    solidity = float(best.get("solidity") or 0)
    smear_c = float(smear.get("compactness") or 0.15)
    smear_circ = float(smear.get("circularity") or 0.26)
    smear_ind = int(smear.get("n_major_indents") or 4)
    compact_ok = compact >= max(0.30, 1.8 * smear_c)
    circ_ok = circularity >= smear_circ + 0.08
    indent_ok = indents <= min(2, smear_ind - 1)
    solid_ok = solidity >= max(0.84, (smear.get("solidity") or 0.78) + 0.04)
    passed = compact_ok and (circ_ok or indent_ok or solid_ok) and compact > smear_c + 0.10
    return {
        "passed": passed,
        "compactness": compact,
        "circularity": circularity,
        "n_major_indents": indents,
        "solidity": solidity,
        "vs_pr7_compactness": smear_c,
        "compact_ok": compact_ok,
        "circ_ok": circ_ok,
        "indent_ok": indent_ok,
        "solid_ok": solid_ok,
    }


def evaluate_gate(frames, channels: dict, smear: dict) -> dict:
    by_suffix = {f.media_id.split("-")[-1]: f for f in frames}
    f051 = by_suffix.get("051")
    interiors_spatial = [f.media_id for f in frames if f.viewpoint == "interior" and f.spatial_eligible]
    closeup_scale = [f.media_id for f in frames if f.viewpoint == "pool_closeup" and f.scale_eligible]
    shape = channels["shape"]
    best = shape.get("dominant")
    cleaner = cleaner_than_pr7(best, smear)
    compound = channels["compound_pool"]["detected"]
    channels_retained = all(key in channels for key in ("shape", "spatial", "scale", "aerial"))
    collapsed = shape.get("selection", {}).get("method") == "cluster_sum"
    checks = {
        "interiors_excluded_from_spatial": f051 is not None
        and (not f051.spatial_eligible)
        and f051.viewpoint == "interior"
        and not interiors_spatial,
        "closeups_excluded_from_nadir_scale": not closeup_scale,
        "best_overview_cleaner_than_pr7_smear": cleaner["passed"],
        "compound_water_components_detected": compound,
        "channels_retained_not_collapsed": channels_retained and not collapsed,
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "cleaner": cleaner,
        "051_viewpoint": None if f051 is None else f051.viewpoint,
        "051_spatial_eligible": None if f051 is None else f051.spatial_eligible,
        "interior_spatial_ids": interiors_spatial,
        "closeup_scale_ids": closeup_scale,
        "inspect": {
            suffix: None
            if by_suffix.get(suffix) is None
            else {
                "viewpoint": by_suffix[suffix].viewpoint,
                "pool_detected": by_suffix[suffix].pool_detected,
                "overview": by_suffix[suffix].pool_overview_eligible,
                "spatial": by_suffix[suffix].spatial_eligible,
                "scale": by_suffix[suffix].scale_eligible,
                "quality": by_suffix[suffix].contour_quality,
                "n_components": by_suffix[suffix].n_components,
                "compound": by_suffix[suffix].compound,
            }
            for suffix in INSPECT
        },
    }


def _load_seg(stand: str) -> dict:
    path = SEG_DIR / f"{_safe(stand)}.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def maybe_rerank(listing_fp, gate: dict) -> dict | None:
    if not gate["passed"] or listing_fp is None:
        return None
    frozen_rows = json.loads(PR5_ALL.read_text(encoding="utf-8"))["rows"]
    listing_shape = contour_descriptors(listing_fp.contour_normalized or listing_fp.contour_image)
    scored = []
    for item in frozen_rows:
        seg = _load_seg(str(item["stand_number"]))
        feats = v2_object_features(
            listing_fp,
            seg,
            listing_shape=listing_shape,
            listing_has_driveway=True,
            listing_driveway_side=None,
            include_building_coarse=False,
        )
        score, contrib, cov, _fac = score_v2(
            feats,
            aerial=item.get("aerial_similarity"),
            exterior=item.get("exterior_similarity"),
            stand_size=stand_size_support(LISTING_STAND_SQM, item.get("area_sqm")),
            weights=V2_WEIGHTS_NO_BUILDING,
            os_keys=OS_KEYS_NO_BUILDING,
            missing="neutral",
        )
        scored.append(
            {
                "stand_number": str(item["stand_number"]),
                "score": score,
                "coverage": cov,
                "contrib": contrib,
                "baseline_rank": item["baseline_rank"],
                "pr5_neutral_rank": item["hybrid_neutral_rank"],
            }
        )
    ranked = sorted(scored, key=lambda row: (-row["score"], row["stand_number"]))
    for i, row in enumerate(ranked, start=1):
        row["rank"] = i
    eval_row = next(row for row in ranked if row["stand_number"] == EVAL_STAND)
    sep = assess_separation([row["score"] for row in ranked[:10]])
    return {
        "eval_stand": EVAL_STAND,
        "rank": eval_row["rank"],
        "score": eval_row["score"],
        "top1": {"stand": ranked[0]["stand_number"], "score": ranked[0]["score"]},
        "gap_vs_top1": round(eval_row["score"] - ranked[0]["score"], 4),
        "top10": [{"stand": r["stand_number"], "score": r["score"]} for r in ranked[:10]],
        "separation": sep,
        "weights": "V2_WEIGHTS_NO_BUILDING unchanged",
    }


def draw_panels(photos: list[tuple[str, bytes]], frames, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    inspect_ids = {f"{LISTING_ID}-{s}" for s in INSPECT}
    ranked = sorted(frames, key=lambda f: (-f.contour_quality, f.media_id))
    chosen = []
    seen = set()
    for frame in frames:
        if frame.media_id in inspect_ids:
            chosen.append(frame)
            seen.add(frame.media_id)
    for frame in ranked:
        if frame.media_id in seen:
            continue
        if frame.pool_detected or frame.viewpoint in {"pool_overview", "pool_closeup", "interior"}:
            chosen.append(frame)
            seen.add(frame.media_id)
        if len(chosen) >= 15:
            break
    by_id = {mid: body for mid, body in photos}
    font = _font(14)
    for frame in chosen[:15]:
        body = by_id.get(frame.media_id)
        if not body:
            continue
        image = Image.open(__import__("io").BytesIO(body)).convert("RGB")
        draw = ImageDraw.Draw(image, "RGBA")
        w, h = image.size
        for i, comp in enumerate((frame.components or [])[:4]):
            xy = comp.get("contour_image") or []
            if len(xy) < 3:
                continue
            pts = [(float(x) * (w - 1), float(y) * (h - 1)) for x, y in xy]
            color = (0, 220, 80, 180) if i == 0 else (40, 160, 255, 180)
            draw.line(pts + [pts[0]], fill=color, width=3)
        label = (
            f"{frame.media_id[-3:]} {frame.viewpoint} pool={int(frame.pool_detected)} "
            f"n={frame.n_components} q={frame.contour_quality:.2f} "
            f"ov={int(frame.pool_overview_eligible)} sp={int(frame.spatial_eligible)} sc={int(frame.scale_eligible)}"
        )
        draw.rectangle([4, 4, min(w - 4, 8 + 7 * len(label)), 28], fill=(0, 0, 0, 160))
        draw.text((8, 8), label, fill=(250, 250, 250), font=font)
        image.save(dest / f"{frame.media_id}.jpg", quality=82)


def write_report(payload: dict, dest: Path) -> None:
    gate = payload["quality_gate"]
    channels = payload["channels"]
    smear = payload["pr7_smear_reference"]
    inspect = gate["inspect"]
    lines = [
        "# Listing Evidence v2 — 116978058",
        "",
        "Extraction quality gate **before** any 330-candidate rerank. Stand 365 is evaluation-only and was not an input to viewpoint classification, segmentation, or channel assembly.",
        "",
        "Frozen and unmodified: production ranking, PR #6 Scoring v2 weights, Object Segmentation v1, native15 fingerprints, PR #7 artefacts.",
        "",
        "## A. Viewpoint filtering",
        "",
        f"- 051 viewpoint: **{gate['051_viewpoint']}**; spatial eligible: **{gate['051_spatial_eligible']}**",
        f"- Interior frames contributing spatial: {gate['interior_spatial_ids'] or 'none'}",
        f"- Close-up frames contributing nadir scale: {gate['closeup_scale_ids'] or 'none'}",
        f"- Gate interiors excluded from spatial: **{gate['checks']['interiors_excluded_from_spatial']}**",
        f"- Gate close-ups excluded from nadir scale: **{gate['checks']['closeups_excluded_from_nadir_scale']}**",
        "",
        "## Explicit inspect",
        "",
        "| image | viewpoint | pool | overview | spatial | scale | quality | n_comp |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for suffix in INSPECT:
        row = inspect.get(suffix) or {}
        lines.append(
            f"| {suffix} | {row.get('viewpoint')} | {row.get('pool_detected')} | {row.get('overview')} | "
            f"{row.get('spatial')} | {row.get('scale')} | {row.get('quality')} | {row.get('n_components')} |"
        )
    shape = channels["shape"]
    lines += [
        "",
        "## B. Best usable listing frame(s)",
        "",
        f"- Shape method: **{shape['selection']['method']}**",
        f"- Chosen shape source: **{shape.get('source_ids')}** viewpoint={shape.get('viewpoint')}",
        f"- Best-single: {shape['selection'].get('best_single_id')} q={shape['selection'].get('best_single_quality')}",
        f"- Consensus good frames: {shape['selection'].get('consensus_ids')}",
        f"- Cluster-sum (recorded, not preferred): {shape['selection'].get('cluster_sum_ids')} total_q={shape['selection'].get('cluster_sum_quality_total')}",
        f"- Spatial source: {channels['spatial'].get('source_ids')} viewpoint={channels['spatial'].get('viewpoint')}",
        f"- Scale / nadir-compatible: eligible={channels['scale']['eligible']} ids={channels['scale']['source_ids']}",
        f"- Aerial-compatible: eligible={channels['aerial']['eligible']} ids={channels['aerial']['source_ids']}",
        "",
        "## C. Compound-pool detection",
        "",
        f"- Detected separable multi-component water: **{channels['compound_pool']['detected']}**",
        f"- Source frames: {channels['compound_pool']['source_ids']}",
        "",
        "## D. Contour vs PR #7 smear",
        "",
        f"- PR #7 shape source {smear.get('shape_source')}: compactness={smear.get('compactness')}, circularity={smear.get('circularity')}, solidity={smear.get('solidity')}, elongation={smear.get('elongation')}, n_indents={smear.get('n_major_indents')}",
        f"- Best v2 contour: compactness={gate['cleaner'].get('compactness')}, circularity={gate['cleaner'].get('circularity')}, solidity={gate['cleaner'].get('solidity')}, n_indents={gate['cleaner'].get('n_major_indents')}",
        f"- Substantially cleaner: **{gate['cleaner']['passed']}**",
        "",
        "## E. Pool-house geometry",
        "",
        f"- Spatial channel eligible: **{channels['spatial']['eligible']}**",
        f"- dist={channels['spatial'].get('dist')} angle={channels['spatial'].get('angle_deg')}",
        "",
        "## Quality gate",
        "",
        f"**Passed: {gate['passed']}**",
        "",
    ]
    for key, val in gate["checks"].items():
        lines.append(f"- {key}: **{val}**")
    rerank = payload.get("scoring_v2_if_gate_passed")
    lines += ["", "## F. Frozen PR #6 scorer (only if gate passed)", ""]
    if rerank is None:
        lines.append("Gate failed. No 330-candidate rerank was run. Scoring v2 weights were not touched.")
    else:
        lines.append(f"- Stand 365 rank: **#{rerank['rank']}** score={rerank['score']}")
        lines.append(f"- #1 {rerank['top1']['stand']} score={rerank['top1']['score']}")
        lines.append(f"- Gap 365 vs #1: {rerank['gap_vs_top1']}")
        lines.append(f"- Top 10: {rerank['top10']}")
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    photos = load_photos()
    print(f"photos={len(photos)}")
    frames = []
    for media_id, body in photos:
        image = Image.open(__import__("io").BytesIO(body)).convert("RGB")
        scores = clip_viewpoint_scores(image)
        frame = observe_listing_frame(media_id, body, clip_scores=scores)
        frames.append(frame)
        print(
            f"  {media_id} vp={frame.viewpoint} pool={frame.pool_detected} n={frame.n_components} "
            f"q={frame.contour_quality:.3f} ov={frame.pool_overview_eligible} "
            f"sp={frame.spatial_eligible} sc={frame.scale_eligible}"
        )
    channels = assemble_channels(frames)
    smear = pr7_smear_reference()
    gate = evaluate_gate(frames, channels, smear)
    listing_fp = scoring_fingerprint_from_channels(channels, frames) if gate["passed"] else None
    rerank = maybe_rerank(listing_fp, gate)
    draw_panels(photos, frames, OUT / "panels")
    payload = {
        "listing_id": LISTING_ID,
        "diagnostic": "listing_evidence_v2",
        "production_ranking_modified": False,
        "os_v1_modified": False,
        "pr6_modified": False,
        "pr7_modified": False,
        "stand_specific_rules": False,
        "n_photos": len(photos),
        "viewpoint_counts": dict(Counter(f.viewpoint for f in frames)),
        "frames": [frame_public(f) for f in frames],
        "channels": {
            **channels,
            "shape": {k: v for k, v in channels["shape"].items() if k not in {"dominant", "secondary"}}
            | {
                "dominant": None
                if channels["shape"]["dominant"] is None
                else {k: v for k, v in channels["shape"]["dominant"].items() if k not in {"contour_image", "contour_normalized", "norm_xy"}},
                "secondary": None
                if channels["shape"]["secondary"] is None
                else {k: v for k, v in channels["shape"]["secondary"].items() if k not in {"contour_image", "contour_normalized", "norm_xy"}},
            },
        },
        "pr7_smear_reference": smear,
        "quality_gate": gate,
        "scoring_v2_if_gate_passed": rerank,
        "eval_stand_note": "Stand 365 is evaluation-only and was not an input to extraction.",
    }
    (OUT / "latest.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    write_report(payload, OUT / "report.md")
    print("gate", json.dumps(gate["checks"], indent=2))
    print("passed", gate["passed"])
    print("wrote", OUT)


if __name__ == "__main__":
    main()
