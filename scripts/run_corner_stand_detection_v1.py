#!/usr/bin/env python3
"""Corner Stand Detection v1 — estate GIS layer, listing evidence, Corner Gate.

Does not rewrite historical blind freezes or Scoring v2 weights.
The 117262832 path is a retrospective diagnostic, not a new blind test.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.gis.estate_ags_matching.blind_116273255_complete_estate import (  # noqa: E402
    load_gis_002,
    load_inventory_002,
    sha256_file,
)
from backend.gis.estate_ags_matching.corner_stand_diagnostics_v1 import (  # noqa: E402
    render_estate_layer,
    render_listing_proof,
    render_parcel_proof,
    select_proof_parcels,
)
from backend.gis.estate_ags_matching.estate_property_inventory_v1 import pass1_parcels, safe_stand  # noqa: E402
from backend.gis.estate_ags_matching.listing_corner_evidence_v1 import (  # noqa: E402
    inspect_frame_roads,
    observe_listing_corner,
)
from backend.gis.estate_ags_matching.listing_corner_gate_v1 import apply_pool_then_corner_gate  # noqa: E402
from backend.gis.estate_ags_matching.os_scoring_v2 import V2_WEIGHTS_NO_BUILDING  # noqa: E402
from backend.gis.estate_ags_matching.parcel_corner_v1 import classify_estate, load_road_payload  # noqa: E402

OUT = ROOT / "data/investigations/corner_stand_detection_v1"
ROADS = ROOT / "data/gis/carlswald_north_roads_v1.json"
FREEZE_DIR = ROOT / "data/investigations/blind_117262832_complete_estate"
FROZEN_SHA = "32ecd4b526d4a299e143c869761664a9ed7a4b2d9ae65aba6ed300583a1dd10a"
FROZEN_TOP5 = ("654", "467", "405", "644", "456")
LISTING_ID = "117262832"
EXPECTED_WEIGHTS = {
    "pool_presence": 0.14,
    "shape_v2": 0.36,
    "spatial_v2": 0.22,
    "aerial": 0.12,
    "exterior": 0.06,
    "gis": 0.03,
    "stand_size": 0.07,
}


def _hybrid_viewpoints(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    views: dict[str, str] = {}
    for row in (payload.get("listing") or {}).get("per_frame_extraction_quality") or []:
        if row.get("media_id") and row.get("viewpoint"):
            views[str(row["media_id"])] = str(row["viewpoint"])
    for frame in payload.get("frames") or []:
        if frame.get("media_id") and frame.get("viewpoint"):
            views.setdefault(str(frame["media_id"]), str(frame["viewpoint"]))
    return views


def _listing_text() -> str:
    # Visual path is primary. Optional live description is used only for corner phrases.
    try:
        import httpx
        from backend.parsers.property24 import USER_AGENT, parse_listing_html

        url = (
            "https://www.property24.com/for-sale/carlswald-north-estate/"
            "midrand/gauteng/12743/117262832"
        )
        with httpx.Client(timeout=30.0, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
            html = client.get(url).text
        listing = parse_listing_html(html, url, LISTING_ID)
        return listing.description or ""
    except Exception:
        return ""


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    panels = OUT / "proof_panels"
    panels.mkdir(parents=True, exist_ok=True)

    freeze_hash = sha256_file(FREEZE_DIR / "freeze.json")
    recorded = (FREEZE_DIR / "freeze.sha256").read_text(encoding="utf-8").strip()
    if freeze_hash != recorded or recorded != FROZEN_SHA:
        raise SystemExit(f"historical freeze hash changed: {freeze_hash}")
    if dict(V2_WEIGHTS_NO_BUILDING) != EXPECTED_WEIGHTS:
        raise SystemExit("Scoring v2 weights changed")

    parcels = pass1_parcels(load_gis_002())
    roads = load_road_payload(ROADS)
    layer = classify_estate(parcels, roads)
    (OUT / "estate_corner_layer.json").write_text(
        json.dumps({k: v for k, v in layer.to_dict().items() if k != "records"}, indent=2) + "\n",
        encoding="utf-8",
    )
    (OUT / "parcel_corner_records.jsonl").write_text(
        "\n".join(json.dumps(row.to_dict()) for row in layer.records) + "\n",
        encoding="utf-8",
    )
    render_estate_layer(parcels, layer.records, roads, panels / "estate_corner_layer.png")

    selected = select_proof_parcels(parcels, layer.records)
    proof_index: dict[str, list[str]] = {}
    for kind, rows in selected.items():
        names = []
        for i, (parcel, rec) in enumerate(rows, start=1):
            dest = panels / f"{kind}_{i:02d}_stand_{safe_stand(str(rec.stand_number))}.jpg"
            render_parcel_proof(parcel, rec, roads, dest)
            names.append(str(dest.relative_to(ROOT)))
        proof_index[kind] = names

    photos_dir = FREEZE_DIR / "photos"
    viewpoints = _hybrid_viewpoints(FREEZE_DIR / "hybrid_block.json")
    photos = {
        path.stem: path.read_bytes()
        for path in sorted(photos_dir.glob(f"{LISTING_ID}-*.jpg"))
        if path.is_file()
    }
    listing_text = _listing_text()
    evidence = observe_listing_corner(text=listing_text, photos=photos, viewpoints=viewpoints)
    listing_public = evidence.to_dict()
    listing_public["frames"] = [
        frame
        for frame in evidence.frames
        if frame.get("visual_yes") or str(frame.get("viewpoint") or "") in {"aerial_near_nadir", "elevated_exterior", "video"}
    ]
    (OUT / "listing_corner_evidence.json").write_text(
        json.dumps(listing_public, indent=2) + "\n",
        encoding="utf-8",
    )

    proof_frame = None
    for frame in evidence.frames:
        if frame.get("visual_yes"):
            proof_frame = frame
            break
    if proof_frame is None:
        for media_id in (f"{LISTING_ID}-003", f"{LISTING_ID}-039"):
            if media_id in photos:
                proof_frame = inspect_frame_roads(
                    photos[media_id], media_id=media_id, viewpoint=viewpoints.get(media_id, "aerial_near_nadir")
                )
                break
    if proof_frame and proof_frame.get("media_id") in photos:
        render_listing_proof(
            photos[str(proof_frame["media_id"])],
            proof_frame,
            panels / "listing_corner_evidence.jpg",
            listing_corner=evidence.classification,
            confidence=evidence.confidence,
            reason=evidence.visual_reason,
        )

    inventory = load_inventory_002()
    candidates = [{"stand_number": row["stand_number"], "property_id": row.get("property_id")} for row in parcels]
    pool, corner = apply_pool_then_corner_gate(
        candidates,
        inventory,
        "YES",
        [row.to_dict() for row in layer.records],
        evidence.classification,
        listing_evidence=evidence,
    )

    by_stand = {str(row.stand_number): row for row in layer.records}
    survivor_ids = {str(row.get("stand_number")) for row in corner.survivors}
    top5 = []
    for stand in FROZEN_TOP5:
        rec = by_stand.get(stand)
        cls = None if rec is None else rec.classification
        top5.append(
            {
                "stand_number": stand,
                "parcel_corner": cls,
                "confidence": None if rec is None else rec.confidence,
                "reason": None if rec is None else rec.reason,
                "distinct_road_names": None if rec is None else rec.distinct_road_names,
                "would_remove": rec is not None and stand not in survivor_ids,
                "known_false_status_used": False,
            }
        )

    gt_path = FREEZE_DIR / "ground_truth.json"
    true_stand = None
    true_diag = None
    if gt_path.is_file():
        gt = json.loads(gt_path.read_text(encoding="utf-8"))
        true_stand = str(gt.get("confirmed_stand") or "")
        rec = by_stand.get(true_stand)
        true_diag = {
            "stand_number": true_stand,
            "parcel_corner": None if rec is None else rec.classification,
            "confidence": None if rec is None else rec.confidence,
            "reason": None if rec is None else rec.reason,
            "distinct_road_names": None if rec is None else rec.distinct_road_names,
            "retained": true_stand in survivor_ids,
            "identity_used_in_classification": False,
            "identity_source": "after_freeze_ground_truth_json",
        }

    diagnostic = {
        "experiment": "corner_stand_detection_v1",
        "not_a_new_blind_test": True,
        "historical_freeze_untouched": True,
        "historical_freeze_sha256": freeze_hash,
        "scoring_v2_weights": dict(V2_WEIGHTS_NO_BUILDING),
        "scoring_v2_unchanged": dict(V2_WEIGHTS_NO_BUILDING) == EXPECTED_WEIGHTS,
        "pipeline": "listing acquisition → Pool Gate → Corner Gate → Hybrid / Scoring v2",
        "estate_counts": {
            "parcels": layer.n_parcels,
            "YES": layer.n_yes,
            "NO": layer.n_no,
            "UNKNOWN": layer.n_unknown,
            "roads": layer.n_roads,
            "intersections": layer.n_intersections,
        },
        "curved_road_rule": layer.curved_road_rule,
        "listing_117262832": listing_public,
        "gate_reduction": {
            "estate_parcels": layer.n_parcels,
            "pool_gate": pool.total_survivors,
            "corner_gate": corner.total_survivors,
            "pool_gate_detail": {
                "starting": pool.starting_count,
                "survivors": pool.total_survivors,
                "removed_confident_no": pool.removed_confident_no,
            },
            "corner_gate_detail": corner.to_dict() | {
                "survivor_parcel_ids": None,
                "removed_parcel_ids": None,
                "unresolved_parcel_ids": None,
                "n_survivors": corner.total_survivors,
                "n_removed": len(corner.removed),
                "n_unresolved": len(corner.unresolved),
            },
            "summary": f"{layer.n_parcels} → Pool Gate: {pool.total_survivors} → Corner Gate: {corner.total_survivors} → Scoring v2 ranking",
        },
        "frozen_top5_counterfactual": top5,
        "true_stand_diagnostic": true_diag,
        "proof_panels": proof_index,
        "listing_proof": "data/investigations/corner_stand_detection_v1/proof_panels/listing_corner_evidence.jpg",
        "estate_layer": "data/investigations/corner_stand_detection_v1/proof_panels/estate_corner_layer.png",
    }
    # strip huge id lists from nested to_dict
    diagnostic["gate_reduction"]["corner_gate_detail"].pop("survivor_parcel_ids", None)
    diagnostic["gate_reduction"]["corner_gate_detail"].pop("removed_parcel_ids", None)
    diagnostic["gate_reduction"]["corner_gate_detail"].pop("unresolved_parcel_ids", None)
    (OUT / "retrospective_counterfactual.json").write_text(json.dumps(diagnostic, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "estate": diagnostic["estate_counts"],
        "listing": {
            "classification": evidence.classification,
            "confidence": evidence.confidence,
            "source": evidence.evidence_source,
            "frames": evidence.frame_ids,
        },
        "gates": diagnostic["gate_reduction"]["summary"],
        "top5": top5,
        "true_stand": true_diag,
        "freeze_sha": freeze_hash,
    }, indent=2))


if __name__ == "__main__":
    main()
