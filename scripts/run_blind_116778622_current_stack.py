#!/usr/bin/env python3
"""Current-stack regression freeze of Property24 116778622.

IMPROVED-STACK REGRESSION TEST of listing 116778622 against
carlswald_north_corrected_002. Previous PR #20 freeze is not an input.

Stack (unchanged Scoring v2 weights): Hybrid extraction + FastSAM adapter +
Corner Gate v1 + Pool Object Validation v1 + Pool Inventory NO/UNKNOWN
safety v1.1.0. Water colour is not used.

This script is freeze-only. It does not look up street, stand, coordinates,
archives, PR #20 ranks, or any other ground-truth identity. STOP after freeze.
PR #31 scoring recommendations are not implemented.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.gis.estate_ags_matching.blind_116273255_complete_estate import (
    load_inventory_pool_obs_v1_1_0,
    run_freeze,
    scan_prior_listing_artifacts,
    sha256_file,
)
from backend.gis.estate_ags_matching.hybrid_geometry_ranking_test import (
    listing_evidence_from_hybrid_block,
    scoring_ready_frames,
)
from backend.gis.estate_ags_matching.os_scoring_v2 import V2_WEIGHTS_NO_BUILDING

LISTING_ID = "116778622"
LISTING_URL = (
    "https://www.property24.com/for-sale/carlswald-north-estate/midrand/gauteng/12743/116778622"
)
# New directory so the historical PR #20 freeze tree is not overwritten.
OUT_DIR = ROOT / "data/investigations/blind_116778622_current_stack"
INVENTORY_LABEL = "estate_property_inventory_v1.1.0_pool_obs"
HISTORICAL_PR20_DIR = ROOT / "data/investigations/blind_116778622_complete_estate"

FROZEN_WEIGHTS = {
    "pool_presence": 0.14,
    "shape_v2": 0.36,
    "spatial_v2": 0.22,
    "aerial": 0.12,
    "exterior": 0.06,
    "gis": 0.03,
    "stand_size": 0.07,
}

SOURCE_LABEL = {
    "yoloe": "YOLOE",
    "yoloe_sam2": "YOLOE/SAM2",
    "fastsam_fallback": "FastSAM fallback",
}


def _verify_freeze_hash() -> str:
    freeze_path = OUT_DIR / "freeze.json"
    recorded = (OUT_DIR / "freeze.sha256").read_text(encoding="utf-8").strip()
    on_disk = sha256_file(freeze_path)
    if on_disk != recorded:
        raise SystemExit(f"freeze hash mismatch on_disk={on_disk} recorded={recorded}")
    print(f"  verified on-disk sha256={on_disk}")
    return on_disk


def _adapter_observational_report(hybrid_path: Path) -> dict:
    if not hybrid_path.is_file():
        return {"hybrid_block_missing": True}
    block = json.loads(hybrid_path.read_text(encoding="utf-8"))
    frames = list(block.get("frames") or [])
    accepted = scoring_ready_frames(frames)
    accepted_ids = {str(frame.get("media_id")) for frame in accepted}
    rows = []
    for frame in frames:
        media_id = frame.get("media_id")
        source = str(frame.get("source") or "")
        scoring_ready = bool(frame.get("scoring_ready"))
        if scoring_ready and str(media_id) in accepted_ids:
            decision = "ACCEPTED"
        elif scoring_ready:
            decision = "REJECTED"
        else:
            decision = "NOT_SCORING_READY"
        geom = (frame.get("dominant") or {}).get("geometry") or {}
        pov = frame.get("pool_object_validation") or {}
        rows.append(
            {
                "media_id": media_id,
                "source": source,
                "source_label": SOURCE_LABEL.get(source, source),
                "viewpoint": frame.get("viewpoint"),
                "scoring_ready": scoring_ready,
                "adapter": decision,
                "pov_status": pov.get("final_status"),
                "pov_confidence": pov.get("final_pool_object_confidence"),
                "geometry_quality": frame.get("geometry_quality"),
                "aspect_ratio": geom.get("aspect_ratio"),
                "compactness": geom.get("compactness"),
                "solidity": geom.get("solidity"),
                "n_major_indents": geom.get("n_major_indents"),
                "pool_to_house_spatial": False,
            }
        )
    evidence = listing_evidence_from_hybrid_block(block)
    return {
        "frames": rows,
        "scoring_ready_ids": evidence.get("scoring_ready_ids"),
        "chosen_id": evidence.get("chosen_id"),
        "chosen_source": evidence.get("chosen_source"),
        "fastsam_used": bool((evidence.get("feature_sources") or {}).get("fastsam_used")),
        "n_scoring_ready_accepted": len(accepted),
        "pool_to_house_spatial_available": False,
    }


def _write_report(freeze: dict, marker: dict, adapter: dict, digest: str, prior: dict) -> Path:
    acq = freeze.get("acquisition") or {}
    pool = freeze.get("listing_pool_gate") or {}
    estate_pool = freeze.get("estate_pool_gate") or {}
    corner = freeze.get("listing_corner") or {}
    estate_corner = freeze.get("estate_corner_gate") or {}
    listing_pov = freeze.get("listing_pool_object_validation") or {}
    cand_pov = freeze.get("candidate_pool_object_validation") or {}
    ranking = freeze.get("ranking") or {}
    quality = ranking.get("quality") or {}
    top20 = ranking.get("top20") or []
    top5 = ranking.get("top5") or []
    scenes = acq.get("scene_counts") or {}
    panels = marker.get("panels") or []
    chosen = listing_pov.get("chosen_id")
    fingerprint = listing_pov.get("official_fingerprint") or "NO_SHAPE_SIGNAL"
    inv = (freeze.get("ranking_configuration") or {}).get("inventory_counts") or {}
    lines = [
        "# Current-stack regression freeze — listing 116778622 on `carlswald_north_corrected_002`",
        "",
        "**IMPROVED-STACK REGRESSION TEST.** Not a first-time blind. Previous PR #20 freeze "
        "is preserved at `data/investigations/blind_116778622_complete_estate/` and was **not** "
        "used as ranking input.",
        "",
        "Accuracy test on Hybrid extraction + FastSAM adapter + Corner Gate v1 + "
        "Pool Object Validation v1 + **Pool Inventory NO/UNKNOWN safety v1.1.0**. "
        "Scoring v2 weights unchanged. Water colour is not used. PR #31 recommendations "
        "(omit-null pad, pool-scale, building-footprint scoring) are **not** implemented.",
        "",
        f"- **Freeze path:** `data/investigations/blind_116778622_current_stack/freeze.json`",
        f"- **On-disk SHA256** (matches `freeze.sha256`, verified after write): `{digest}`",
        f"- **Official score:** `hybrid_v2`",
        f"- **Universe:** 400 unique erven",
        f"- **Inventory:** `{INVENTORY_LABEL}` (YES={inv.get('YES')} NO={inv.get('NO')} UNKNOWN={inv.get('UNKNOWN')})",
        f"- **Ground truth applied to ranking:** no",
        f"- **Ground-truth recovery in this test:** **not performed** (STOP after freeze)",
        f"- **PR #20 comparison in this test:** **not performed** (STOP after freeze)",
        f"- **Geometry-discrimination class:** **{quality.get('class')}**",
        "- **Do not treat Top 1 as truth.** Top 5 is for manual visual inspection.",
        "",
        "## A. Blindness / regression isolation",
        "",
        "Before freeze: no street / stand / erf-number / coordinate / archived-identity / "
        "agent-cross-listing / Private Property / GIS-parcel / unique-stand-size reverse lookup / "
        "prior advertisement / seller-social search. PR #20 ranking, shortlist, candidate identities, "
        "panels, and conclusions were not read as ranking inputs. Photos downloaded fresh. "
        f"Historical PR #20 freeze tree left untouched at `{HISTORICAL_PR20_DIR.relative_to(ROOT)}`.",
        "",
        f"Prior-path inventory (excluded from ranking): `{prior}`.",
        "",
        "## B. Acquisition",
        "",
        f"**{'Fresh' if acq.get('acquisition_fresh') else acq.get('media_source')}.** "
        f"{acq.get('photos_downloaded')}/{acq.get('listing_photo_count')} photos downloaded, "
        f"{acq.get('photos_reused_from_disk')} reused, **{acq.get('photos_failed')} failed**. "
        f"Video **{'YES' if acq.get('video_available') else 'NO'}** ({acq.get('video_count')}). "
        "Title / street / stand omitted from freeze.",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Property type | {acq.get('property_type')} |",
        f"| Erf size | {acq.get('erf_size_sqm')} m² |",
        f"| Floor size | {acq.get('floor_size_sqm')} m² |",
        f"| Bedrooms | {acq.get('bedrooms')} |",
        f"| Listing photos | {acq.get('listing_photo_count')} ({acq.get('photos_downloaded_fresh')} fresh, {acq.get('photos_failed')} failed) |",
        f"| Video | {'YES' if acq.get('video_available') else 'NO'} (count={acq.get('video_count')}) |",
        f"| CLIP interior | {scenes.get('interior', 0)} |",
        f"| CLIP exterior | {acq.get('exterior_photo_count')} |",
        f"| CLIP driveway | {acq.get('driveway_photo_count')} |",
        f"| CLIP garden/patio | {acq.get('garden_photo_count')} |",
        f"| CLIP aerial | {scenes.get('aerial', 0)} |",
        f"| CLIP `pool_garden` | {acq.get('pool_photo_count')} |",
        f"| Feature hits | {', '.join(acq.get('feature_hits') or []) or 'none'} |",
        "",
        f"CLIP scene counts: `{scenes}`.",
        "",
        f"Useful pool frames: `{acq.get('useful_pool_views')}`.",
        "",
        f"Useful exterior: `{acq.get('useful_exterior_views')}`.",
        "",
        f"Useful driveway: `{acq.get('useful_driveway_garage_views')}`.",
        "",
        f"Useful aerial: `{acq.get('useful_aerial_views')}`.",
        "",
        "## C. Pool Gate",
        "",
        f"Listing **POOL = {pool.get('listing_pool_status')}**, determined from listing evidence **before** estate ranking.",
        "",
        f"Reason: `{pool.get('listing_pool_reason') or pool.get('reason')}`",
        "",
        "| | Count |",
        "| --- | ---: |",
        f"| Starting parcels | {estate_pool.get('starting_candidates')} |",
        f"| Inventory YES / NO / UNKNOWN | {inv.get('YES')} / {inv.get('NO')} / {inv.get('UNKNOWN')} |",
        f"| YES survivors | {estate_pool.get('yes_survivors')} |",
        f"| UNKNOWN survivors | {estate_pool.get('unknown_survivors')} |",
        f"| Candidates removed (confident NO) | {estate_pool.get('no_removed') or estate_pool.get('parcels_removed_confident_no')} |",
        f"| Candidates retained | **{estate_pool.get('final_survivor_count')}** |",
        f"| Reduction | {estate_pool.get('percentage_reduction')}% |",
        "",
        "## D. Corner Gate v1",
        "",
        f"Listing **CORNER = {corner.get('listing_corner')}** (confidence={corner.get('confidence')}, source=`{corner.get('evidence_source')}`, high_confidence={corner.get('high_confidence')}).",
        "",
        f"Reason: `{corner.get('visual_reason')}`. Frames: `{corner.get('frame_ids')}`.",
        "",
        f"Gate action: `{estate_corner.get('gate_action')}`.",
        "",
        f"Pool Gate survivors **{estate_pool.get('final_survivor_count')} → Corner Gate survivors {estate_corner.get('final_survivor_count')}** "
        f"(removed confident parcel NO={estate_corner.get('parcels_removed_confident_no')}; "
        f"YES/NO/UNKNOWN parcel survivors={estate_corner.get('yes_survivors')}/{estate_corner.get('no_survivors')}/{estate_corner.get('unknown_survivors')}).",
        "",
        "## E. Pool Object Validation v1 (listing)",
        "",
        f"Official fingerprint: **{fingerprint}**.",
        "",
        f"Official pick: `{chosen}` source=`{listing_pov.get('chosen_source')}` viewpoint=`{listing_pov.get('chosen_viewpoint')}`.",
        "",
        f"Selection reason: `{listing_pov.get('chosen_reason')}`.",
        "",
        "Pool-to-house spatial evidence: **not available** (Hybrid v1 omits viewpoint-incompatible pool–house terms).",
        "",
        "Per-frame POV / adapter:",
        "",
        "| media_id | viewpoint | extractor | scoring_ready | adapter | POV | POV conf | quality | aspect | principal |",
        "| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in adapter.get("frames") or []:
        lines.append(
            f"| {row.get('media_id')} | {row.get('viewpoint')} | {row.get('source_label')} | "
            f"{row.get('scoring_ready')} | {row.get('adapter')} | {row.get('pov_status')} | "
            f"{row.get('pov_confidence')} | {row.get('geometry_quality')} | {row.get('aspect_ratio')} | "
            f"{next((item.get('principal_pool_candidate') for item in (listing_pov.get('per_frame') or []) if item.get('media_id')==row.get('media_id')), None)} |"
        )
    lines.extend(
        [
            "",
            "## F. Pool Object Validation v1 (candidates, copies only)",
            "",
            f"OS JSON rewritten: **{cand_pov.get('os_json_rewritten')}**. Ranked={cand_pov.get('n_ranked')}.",
            "",
            f"CONFIRMED={cand_pov.get('CONFIRMED')} UNKNOWN={cand_pov.get('UNKNOWN')} REJECTED={cand_pov.get('REJECTED')} missing={cand_pov.get('missing')}.",
            "",
            "## G. Scoring v2 freeze (unchanged weights)",
            "",
            "Weights: pool_presence 0.14, shape_v2 0.36, spatial_v2 0.22, aerial 0.12, exterior 0.06, gis 0.03, stand_size 0.07.",
            "",
            f"Ranked survivors: **{ranking.get('n_candidates')}**.",
            "",
            f"| #1 | #2 | #5 | #10 | #20 |",
            f"| --- | --- | --- | --- | --- |",
            f"| {quality.get('score_1')} | {quality.get('score_2')} | {quality.get('score_5')} | {quality.get('score_10')} | {quality.get('score_20')} |",
            "",
            f"Class: **{quality.get('class')}** ({quality.get('discrimination_mode')}).",
            "",
            "### Top 20",
            "",
            "| rank | stand | township | area_sqm | total | pool inv | OS/POV | corner | shape_v2 | spatial_v2 | pool_presence | aerial | exterior | gis | stand_size |",
            "| ---: | --- | --- | ---: | ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in top20:
        contrib = row.get("evidence_contributors") or {}
        lines.append(
            f"| {row.get('rank')} | {row.get('stand_number')} | {row.get('township')} | {row.get('area_sqm')} | "
            f"{row.get('score')} | {row.get('inventory_pool_status')} | "
            f"{row.get('candidate_pov_status') or row.get('os_pool_status')} | {row.get('parcel_corner')} | "
            f"{row.get('shape_v2')} | {row.get('spatial_v2')} | {contrib.get('pool_presence')} | "
            f"{contrib.get('aerial')} | {contrib.get('exterior')} | {contrib.get('gis')} | {contrib.get('stand_size')} |"
        )
    lines.extend(
        [
            "",
            "### Top 5 stands + panels",
            "",
        ]
    )
    for row, panel in zip(top5, panels or [None] * 5):
        lines.append(
            f"- **#{row.get('rank')}** stand `{row.get('stand_number')}` score={row.get('score')} "
            f"shape_v2={row.get('shape_v2')} spatial_v2={row.get('spatial_v2')} "
            f"pool={row.get('inventory_pool_status')} corner={row.get('parcel_corner')} "
            f"panel=`{panel}`"
        )
    lines.extend(
        [
            "",
            "## H. STOP",
            "",
            "Freeze is committed. Manual Top-5 assessment, PR #20 comparison, and ground-truth "
            "recovery come next. Do not recover ground truth, rerank, retune Scoring v2, or "
            "implement PR #31 recommendations from this report.",
            "",
        ]
    )
    path = OUT_DIR / "REPORT.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze-only", action="store_true", default=True)
    parser.add_argument("--skip-listing-pool-object", action="store_true")
    parser.add_argument("--skip-panels", action="store_true")
    args = parser.parse_args()
    if dict(V2_WEIGHTS_NO_BUILDING) != FROZEN_WEIGHTS:
        raise SystemExit(f"Scoring v2 weights changed: {dict(V2_WEIGHTS_NO_BUILDING)}")
    if not HISTORICAL_PR20_DIR.is_dir():
        raise SystemExit("historical PR #20 freeze directory missing; cannot preserve it")
    prior = scan_prior_listing_artifacts(LISTING_ID)
    print("Phase 1 — acquire, Pool Gate (v1.1.0 overlay), Corner Gate, POV overlay, Scoring v2 freeze")
    print("STOP after freeze. Ground-truth recovery and PR #20 comparison are not part of this run.")
    print(f"  prior artefacts (excluded from ranking input): {prior}")
    inventory = load_inventory_pool_obs_v1_1_0()
    result = run_freeze(
        listing_id=LISTING_ID,
        listing_url=LISTING_URL,
        out_dir=OUT_DIR,
        observe_objects=not args.skip_listing_pool_object,
        write_panels=not args.skip_panels,
        force_fresh_photos=True,
        ignore_frozen_hybrid_json=True,
        apply_corner_gate=True,
        apply_candidate_pov=True,
        inventory_records=inventory,
        inventory_label=INVENTORY_LABEL,
    )
    marker = result["marker"]
    print(f"  freeze={OUT_DIR / 'freeze.json'}")
    print(f"  sha256={marker['sha256']}")
    print(f"  listing_pool={marker['listing_pool_status']}")
    print(f"  pool_gate_survivors={marker.get('pool_gate_survivors')}")
    print(f"  listing_corner={marker.get('listing_corner')} corner_survivors={marker.get('corner_gate_survivors')}")
    print(f"  n_ranked={marker['n_candidates']} panels={len(marker.get('panels') or [])}")
    digest = _verify_freeze_hash()
    adapter = _adapter_observational_report(OUT_DIR / "hybrid_block.json")
    (OUT_DIR / "adapter_observational.json").write_text(
        json.dumps(adapter, indent=2) + "\n",
        encoding="utf-8",
    )
    freeze = json.loads((OUT_DIR / "freeze.json").read_text(encoding="utf-8"))
    report_path = _write_report(freeze, marker, adapter, digest, prior)
    print(
        "  adapter_accepted="
        f"{adapter.get('n_scoring_ready_accepted')} chosen={adapter.get('chosen_id')} "
        f"source={adapter.get('chosen_source')} fastsam_used={adapter.get('fastsam_used')}"
    )
    print(f"  report={report_path}")
    print("Freeze complete. Do not look up ground truth or PR #20 ranks from this script.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
