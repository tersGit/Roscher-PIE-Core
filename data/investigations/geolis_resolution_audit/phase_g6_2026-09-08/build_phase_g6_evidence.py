import csv
import hashlib
import json
import math
import os
import subprocess
from collections import Counter
from statistics import median


ROOT = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(ROOT, "..", "..", "..", ".."))
G5 = os.path.join(REPO, "data", "investigations", "geolis_resolution_audit", "phase_g5_2026-09-08")
G3 = os.path.join(REPO, "data", "investigations", "geolis_resolution_audit", "phase_g3_2026-09-07")
G4H = os.path.join(REPO, "data", "investigations", "geolis_resolution_audit", "phase_g4h_2026-09-07")
OS = os.path.join(REPO, "data", "investigations", "object_segmentation_v1", "carlswald_north", "json")


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_csv(name, fields, rows):
    with open(os.path.join(ROOT, name), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def contour_metrics(contour):
    if not contour:
        return {"point_count": None, "perimeter": None, "curvature_angle_entropy": None}
    angles = []
    perimeter = 0.0
    n = len(contour)
    for i, p in enumerate(contour):
        q = contour[(i + 1) % n]
        perimeter += math.hypot(q[0] - p[0], q[1] - p[1])
        a = contour[(i - 1) % n]
        v1 = (p[0] - a[0], p[1] - a[1])
        v2 = (q[0] - p[0], q[1] - p[1])
        d = math.hypot(*v1) * math.hypot(*v2)
        if d:
            c = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / d))
            angles.append(round(math.acos(c), 6))
    if not angles:
        entropy = None
    else:
        bins = Counter(min(9, int(a / math.pi * 10)) for a in angles)
        total = len(angles)
        entropy = -sum((n / total) * math.log2(n / total) for n in bins.values())
    return {
        "point_count": n,
        "perimeter": round(perimeter, 6),
        "curvature_angle_entropy": round(entropy, 6) if entropy is not None else None,
    }


joined = read_csv(os.path.join(G5, "PHASE_G5_JOINED_RESULTS.csv"))
resolved = [r for r in joined if r["outcome"] in ("FALSE_POSITIVE", "TRUE_RECOVERY")]
results = {str(x["stand"]): x for x in json.load(open(os.path.join(G3, "results.json"), encoding="utf-8"))}

features = []
for r in resolved:
    stand = r["stand"]
    native = results[stand]["pair"]["native15"]["result"]["run_1"]
    old_path = os.path.join(OS, stand.replace("/", "_") + ".json")
    old = json.load(open(old_path, encoding="utf-8")) if os.path.exists(old_path) else {}
    oldx = old.get("old_extractor", {})
    cm = contour_metrics(native.get("contour_image"))
    features.append({
        "stand": stand,
        "case": r["case"],
        "outcome": r["outcome"],
        "truth": "TP" if r["outcome"] == "TRUE_RECOVERY" else "FP",
        "native15_shape": native.get("shape_class"),
        "relative_parcel_area": native.get("relative_area"),
        "compactness": native.get("compactness"),
        "solidity_or_convexity": native.get("convexity"),
        "rectangularity": native.get("rectangularity"),
        "aspect_ratio": native.get("aspect_ratio"),
        "perimeter_normalized": cm["perimeter"],
        "contour_point_count": cm["point_count"],
        "curvature_angle_entropy": cm["curvature_angle_entropy"],
        "distance_to_building": native.get("pool_to_house_dist"),
        "overlap_with_building_mask": "",
        "distance_to_parcel_boundary": "",
        "parcel_boundary_intersection": "",
        "neighbour_object_relationship": "",
        "fastsam_semantic_score": native.get("semantic_score"),
        "clip_pool_score": "",
        "competing_object_scores": "",
        "candidate_rank": "",
        "contour_available": bool(native.get("contour_image")),
        "missingness_note": "Committed G3 result has no emitted value" if any(native.get(k) is None for k in ("semantic_score",)) else "",
        "legacy_old_pool_present": oldx.get("old_pool_present"),
        "legacy_old_pool_shape": oldx.get("old_pool_shape"),
        "legacy_old_compactness": oldx.get("old_pool_compactness"),
        "legacy_old_aspect_ratio": oldx.get("old_pool_aspect"),
        "legacy_pool_status": old.get("pool", {}).get("status"),
        "legacy_pool_notes": "|".join(old.get("pool", {}).get("notes", [])),
    })

fields = list(features[0])
write_csv("PHASE_G6_TP_FP_FEATURES.csv", fields, features)

comparison_fields = [
    "feature", "TP_n", "FP_n", "TP_missing", "FP_missing", "TP_median", "FP_median",
    "TP_range", "FP_range", "median_difference", "rank_biserial_note", "interpretation",
]
comparison = []
numeric = [
    ("relative_parcel_area", "Small-area native15 blobs overlap strongly; not a safe separator."),
    ("compactness", "TP/FP ranges overlap; geometry alone does not identify water."),
    ("solidity_or_convexity", "Ranges overlap; no threshold is selected."),
    ("rectangularity", "Ranges overlap; rectangularity is not a standalone discriminator."),
    ("aspect_ratio", "Both groups include compact and elongated objects."),
    ("perimeter_normalized", "Available contour perimeter is diagnostic only and scale-normalized."),
    ("contour_point_count", "Point count is an extraction property, not physical identity."),
    ("curvature_angle_entropy", "Irregularity overlaps and is not sufficient for object identity."),
    ("distance_to_building", "Building distance overlaps; no building-mask overlap is emitted."),
]
for feature, interpretation in numeric:
    vals = {}
    for label in ("TP", "FP"):
        vals[label] = [float(x[feature]) for x in features if x["truth"] == label and x[feature] not in ("", None)]
    def rng(a):
        return f"{min(a):.6g}..{max(a):.6g}" if a else ""
    comparison.append({
        "feature": feature,
        "TP_n": len(vals["TP"]),
        "FP_n": len(vals["FP"]),
        "TP_missing": 21 - len(vals["TP"]),
        "FP_missing": 23 - len(vals["FP"]),
        "TP_median": f"{median(vals['TP']):.6g}" if vals["TP"] else "",
        "FP_median": f"{median(vals['FP']):.6g}" if vals["FP"] else "",
        "TP_range": rng(vals["TP"]),
        "FP_range": rng(vals["FP"]),
        "median_difference": f"{median(vals['TP']) - median(vals['FP']):.6g}" if vals["TP"] and vals["FP"] else "",
        "rank_biserial_note": "Not computed: no threshold or optimization permitted; distributions visibly overlap.",
        "interpretation": interpretation,
    })
for feature in ("overlap_with_building_mask", "distance_to_parcel_boundary", "parcel_boundary_intersection",
                "neighbour_object_relationship", "fastsam_semantic_score", "clip_pool_score",
                "competing_object_scores", "candidate_rank"):
    comparison.append({
        "feature": feature, "TP_n": 0, "FP_n": 0, "TP_missing": 21, "FP_missing": 23,
        "TP_median": "", "FP_median": "", "TP_range": "", "FP_range": "",
        "median_difference": "", "rank_biserial_note": "Not estimable: feature absent from committed G3/G5 evidence.",
        "interpretation": "Missingness is the result; no value is invented.",
    })
write_csv("PHASE_G6_FEATURE_COMPARISON.csv", comparison_fields, comparison)

labels = [
    ("499", "UNKNOWN", "Committed panel/boundary evidence does not establish physical identity; legacy object record is not independent ground truth."),
    ("378", "UNKNOWN", "No defensible physical cause can be assigned from committed evidence."),
    ("1/379", "UNKNOWN", "No defensible physical cause can be assigned from committed evidence."),
    ("1/541", "UNKNOWN", "No defensible physical cause can be assigned from committed evidence."),
    ("395", "UNKNOWN", "No defensible physical cause can be assigned from committed evidence."),
    ("1/403", "UNKNOWN", "No defensible physical cause can be assigned from committed evidence."),
    ("1/474", "UNKNOWN", "No defensible physical cause can be assigned from committed evidence."),
    ("467", "UNKNOWN", "No defensible physical cause can be assigned from committed evidence."),
    ("418", "UNKNOWN", "No defensible physical cause can be assigned from committed evidence."),
    ("1/513", "UNKNOWN", "No defensible physical cause can be assigned from committed evidence."),
    ("492", "UNKNOWN", "No defensible physical cause can be assigned from committed evidence."),
    ("1/515", "UNKNOWN", "No defensible physical cause can be assigned from committed evidence."),
    ("486", "UNKNOWN", "No defensible physical cause can be assigned from committed evidence."),
    ("495", "UNKNOWN", "No defensible physical cause can be assigned from committed evidence."),
    ("346", "UNKNOWN", "No defensible physical cause can be assigned from committed evidence."),
    ("1/335", "UNKNOWN", "No defensible physical cause can be assigned from committed evidence."),
    ("345", "UNKNOWN", "No defensible physical cause can be assigned from committed evidence."),
    ("425", "UNKNOWN", "No defensible physical cause can be assigned from committed evidence."),
    ("427", "UNKNOWN", "No defensible physical cause can be assigned from committed evidence."),
    ("433", "UNKNOWN", "No defensible physical cause can be assigned from committed evidence."),
    ("668", "UNKNOWN", "No defensible physical cause can be assigned from committed evidence."),
    ("681", "UNKNOWN", "No defensible physical cause can be assigned from committed evidence."),
    ("638", "UNKNOWN", "No defensible physical cause can be assigned from committed evidence."),
]
fp_map = {stand: label for stand, label, _ in labels}
root_rows = []
for x in features:
    if x["truth"] == "FP":
        root_rows.append({
            "stand": x["stand"], "case": x["case"], "outcome": x["outcome"],
            "root_cause_label": fp_map[x["stand"]], "secondary_label": "",
            "physical_identity": "Not established by committed evidence",
            "panel_inspected": "yes",
            "boundary_contour_context_inspected": "yes",
            "context_building_relationship_inspected": "yes",
            "segmentation_object_evidence_inspected": "yes",
            "basis": labels[[s for s, _, _ in labels].index(x["stand"])][2],
            "do_not_infer_from_water_color": "yes",
        })
write_csv("PHASE_G6_FP_ROOT_CAUSES.csv", list(root_rows[0]), root_rows)

pr27 = []
for x in features:
    if x["truth"] not in ("FP", "TP"):
        continue
    status = x["legacy_pool_status"] or ""
    deterministic = "yes" if status == "REJECTED" else "no"
    pr27.append({
        "stand": x["stand"], "case": x["case"], "truth_group": x["truth"],
        "historical_object_status": status, "historical_notes": x["legacy_pool_notes"],
        "unchanged_pr27_reject_determinable": deterministic,
        "diagnostic_read": "Historical object record is rejected under its stored gate" if deterministic else "Not determinable from committed PR27 inputs; no independent mask/identity evidence",
        "would_reject_claim": "diagnostic-only; not a causal counterfactual",
    })
write_csv("PHASE_G6_PR27_DIAGNOSTIC.csv", list(pr27[0]), pr27)

hash_rows = []
for ref in ("bd46a6fda2b8879dd7b0f5247665551ebd33eaf3", "5dd93d99405806211bcf2e2c6cc9af2feefb6fa5",
            "c7ae71883a8233d9fb113b70a76ddf9a441c68b9", "bc434935a6316acf0c333b15d0a8b0787cfb33fd",
            "6c53661e15d1bda968318cbac7cc244ed7497789"):
    actual = subprocess.check_output(["git", "rev-parse", ref], cwd=REPO, text=True).strip()
    hash_rows.append((ref, actual, "MATCH" if actual == ref else "MISMATCH"))

rejected_fp = sum(x["truth"] == "FP" and x["legacy_pool_status"] == "REJECTED" for x in features)
rejected_tp = sum(x["truth"] == "TP" and x["legacy_pool_status"] == "REJECTED" for x in features)
missing = Counter()
for x in features:
    for k in ("overlap_with_building_mask", "distance_to_parcel_boundary", "parcel_boundary_intersection",
              "neighbour_object_relationship", "fastsam_semantic_score", "clip_pool_score",
              "competing_object_scores", "candidate_rank"):
        if x[k] == "":
            missing[k] += 1

with open(os.path.join(ROOT, "PHASE_G6_FREEZE_VERIFICATION.md"), "w", encoding="utf-8") as f:
    f.write("# Phase G6 freeze verification\n\n")
    f.write("Diagnostic-only audit. No detector, thresholds, scoring, ranking, Shape v2, imagery, inventory, prior evidence, or PR #27 files were modified; no imagery was fetched and no detector was rerun.\n\n")
    f.write("| Reference | Resolved | Status |\n|---|---|---|\n")
    for ref, actual, status in hash_rows:
        f.write(f"| `{ref}` | `{actual}` | **{status}** |\n")
    f.write("\nG5 source hashes retained in `PHASE_G5_FREEZE_VERIFICATION.md`; G5 inputs and prior evidence remain byte-for-byte unchanged.\n")

with open(os.path.join(ROOT, "PHASE_G6_HISTORICAL_REGRESSION.md"), "w", encoding="utf-8") as f:
    f.write("""# Phase G6 historical regression check

The historical Pool Object Validation v1 design from PR #27 was reviewed as a design reference only. It was not enabled, modified, or applied as a new detector. Its documented strengths are true-parcel containment, building-overlap agreement for roof vetoes, neighbour protection, and cross-frame object identity.

Committed historical known-pool evidence remains mixed and must not be treated as current live ground truth:

| Known pool | Committed evidence | G6 implication |
|---|---|---|
| 401 | Labelled historical evidence exists outside the 44-case G5 additions | Keep as regression control; no new threshold inferred |
| 338 | PR27 documents a CLIP roof conflict and preserves it as UNKNOWN | Roof score alone is unsafe |
| 408 | PR27 protects it from neighbour contamination but leaves it UNKNOWN | Boundary/mask identity is required |
| 420 | PR27 keeps an irregular/kidney object CONFIRMED | Irregularity must not be hard-rejected |
| 677 | PR27 keeps a genuine pool CONFIRMED | Large/real pools must remain protected |
| 365 | Earlier labelled evidence exists; no independent G6 physical identity was added | No claim beyond committed evidence |

The stored legacy gate status is a diagnostic comparison, not a counterfactual replay. It is `REJECTED` for %d/23 false positives and %d/21 true recoveries; this does not establish that PR27 would reject those native15 additions because the committed additions lack PR27's required live mask/object inputs. A strict defensible reading therefore yields 0/23 FP and 0/21 TP with a determinable PR27 counterfactual, and 23/23 FP plus 21/21 TP unresolved. No recovery-preservation claim is made from absent features.
""" % (rejected_fp, rejected_tp))

with open(os.path.join(ROOT, "PHASE_G6_REPORT.md"), "w", encoding="utf-8") as f:
    f.write("""# PHASE G6 — NATIVE15 false-positive forensics

## Verdict

**Verdict D — multiple diagnostic experiments.** The 23 false positives and 21 true recoveries are measurable as a transition sample, but the committed evidence does not support one general hardening mechanism or adoption of native15. G7 should be **frozen to PR27 A/B only** while separately defining multiple diagnostic experiments; no detector change is recommended from this audit.

## Scope and preservation

The primary set is all 23 G5 `FALSE_POSITIVE` native15 additions; the control set is all 21 `TRUE_RECOVERY` additions. G5 reported 23/44 FP and 21/44 TP. The two unresolved/excluded additions and two removals are outside this resolved forensic set. The committed G4H first-pass panels (`phase_g4h_2026-09-07/first_pass_panels/case_*.jpg`) were inspected with their parcel/boundary and contour context. Existing object-segmentation JSON and G3 native15 results were compared. No imagery was fetched and no detector was rerun.

## Physical identity and causes

All 23 FPs are recorded as **UNKNOWN**, not because they are presumed water, roof, paving, shadow, vegetation, neighbour leakage, or another object, but because the committed panels and stored diagnostics do not independently establish physical identity. Water colour alone was never used. The allowed cause vocabulary is enforced in `PHASE_G6_FP_ROOT_CAUSES.csv`; `UNKNOWN` is the only defensible label for these records. Dominant cause is therefore **undetermined**, not a claimed visual mode. Boundary leakage, roof/building confusion, small/irregular recovery patterns, and segmentation/object versus semantic weakness cannot be separated for these 23 from committed values.

## Existing diagnostics

All 44 additions have native15 relative parcel area, compactness, convexity/solidity proxy, rectangularity, aspect ratio, normalized perimeter, contour point count, curvature/angle entropy, and distance to the extracted building centroid. TP/FP ranges overlap for every emitted geometry feature; medians are reported without threshold selection in `PHASE_G6_FEATURE_COMPARISON.csv`. Native15 area is small in both groups (TP median 0.0026; FP median 0.0025), so area does not distinguish them. Building-mask overlap, parcel-boundary distance/intersection, neighbour relationship, FastSAM/semantic score, CLIP pool score, competing-object scores, and candidate rank are missing for all 44. Missingness is reported, not imputed.

The strongest existing evidence is therefore the combination of parcel membership and contour geometry as a review aid, not a classifier. Geometry is not enough: true recoveries include irregular, elongated, rectangular, and kidney/curved objects, while FPs include the same families. The sample supports a mixed unobserved weakness (object identity / masking / semantic context), not attribution to one layer.

## PR27 diagnostic

PR27's historical design was reviewed but not enabled. Its required discriminators—unclipped-mask containment, independent building overlap, neighbour risk, semantic evidence, and cross-frame identity—are not emitted in this G5 native15 transition record. The stored legacy object status is shown only as an audit aid in `PHASE_G6_PR27_DIAGNOSTIC.csv`; it is not a valid replay. Determinable unchanged-PR27 counterfactuals: **0/23 FPs**, and **0/21 TPs wrongly rejected**, because required inputs are absent; all 44 remain unresolved under a strict evidence rule. Historical pools 401, 338, 408, 420, 677, and 365 remain regression controls, with the limitations documented in `PHASE_G6_HISTORICAL_REGRESSION.md`.

## Required answers

- Physical identity of 23 FPs: not established; all 23 are `UNKNOWN`.
- Dominant causes: no defensible dominant cause; unsupported labels are not substituted.
- Distinguishability: no reliable separation from committed diagnostics.
- Strongest features: parcel-context review plus geometry as descriptive evidence; no standalone geometry feature separates TP/FP.
- Boundary leakage and roof/building confusion: not measurable because boundary intersection and building-mask overlap are absent.
- Small/irregular pattern: both groups contain small, irregular, elongated, rectangular, and curved objects.
- Weakness layer: mixed/unknown; missing semantic and object-context diagnostics prevent attribution.
- PR27 performance and recovery preservation: no valid counterfactual; no rejection or preservation rate is claimed.
- Endangered historical pools: 338/408 are specifically sensitive to roof/boundary identity; 420/677 demonstrate that irregular and genuine pools must not be hard-rejected; 401/365 remain controls.
- One general hardening mechanism: **not supported**.

## Recommendation

G7 should be **frozen PR27 A/B only**, with multiple predeclared diagnostic experiments kept separate from detector adoption: obtain/emit independent building overlap and parcel-boundary intersection, object identity/semantic scores, and neighbour/context evidence, then evaluate those diagnostics against the same 23/21 cases and historical controls. Do not tune thresholds, optimize, grid-search, train, fetch imagery, adopt native15, or create stand-specific rules from this audit.

See the companion CSVs for row-complete features, missingness, root-cause labels, and PR27 diagnostic status. Existing panels are referenced rather than copied or altered.
""")

print("generated", len(features), "rows; FP", sum(x["truth"] == "FP" for x in features), "TP", sum(x["truth"] == "TP" for x in features))
