# SHAPE_V2_FORENSIC — listing 116778622 (PR #32 diagnostic)

Diagnostic experiment only. PR #32 freeze files and Scoring v2 production weights were not modified.

- Freeze SHA256 (verified unchanged): `dce17f82162920ceeb6d39c2aa2b456a5bcdb16399ecfeb853e7892a0b694a29`
- Official fingerprint: `116778622-005` (YOLOE/SAM2, `pool_overview`)
- Production Shape v2 weight remains **0.36** (untouched)
- Recomputed listing descriptors match freeze listing_shape: **True**

## Phase 9 decision

**MIXED FAILURE**

1. **Not a wrong-pool swap on Stand 540.** The scored OS contour is the in-parcel blob on the rectangular pool (native15 crop + OS mask/contour). The neighbouring freeform pool in the padded crop is **not** the contour that entered Shape v2. FastSAM is leaky (jagged edges; OS class `kidney_or_curved`) but Family v1 still labels 540 RECTANGULAR.
2. **Stand 411 is a POV-promoted REJECTED blob.** Native OS status is `REJECTED`; ranking overlay flipped status without changing the contour. The contour is a leaky compact rectangle (plus pond/paving), not the listing curve.
3. **Listing segmentation of the object is correct** (photo-005 traces the water) **but the scoring contour is lossy**: the frame cuts the pool (fake straight edge), Hybrid class is `rectangular`, 64-pt resample, PCA. Family v1 still recovers KIDNEY_CURVED from angle-entropy/sharp_frac. Shape v2 almost ignores that signal (`sharp_frac` weight **0.03**).
4. **Shape v2 descriptor failure is the dominant reason 540 scores 0.8161.** Elongation + chamfer + Hu + solidity treat two compact blobs as similar after rotation/scale normalisation. The rectangle-versus-curved mismatch lives in unused or near-unused terms (angle entropy is not a Shape v2 input).
5. **A hard family gate is not safe.** On labelled listing 115503057, stand 401 would be wrongly hard-rejected (rank 5 → 252; LAP_ELONGATED vs listing KIDNEY_CURVED).

Pool Shape Family v1 should be **retained diagnostic-only** in this PR. It is **not** promoted into production Shape v2 and is **not** a hard gate on ranking. Historical check: do not hard-reject known true stands. Stand 338 never had `shape_v2` (OS REJECTED) so a shape gate cannot rescue that case.

## Phase 1 — Exact contours that entered Shape v2

### First question

**Is PIE scoring the visually obvious square pool on 540 and 411, or a different extracted shape?**

- **540: the in-parcel rectangular pool, not the neighbour freeform.** The native15 crop contains two pools; the OS mask sits on the **upper/in-parcel rectangle**. FastSAM is leaky (staircase edges, OS class `kidney_or_curved`, rectangularity 0.65) but Family v1 still recovers RECTANGULAR from low angle-entropy / high sharp_frac. Visual: `panels/shape_v2_pipeline/stand_540.jpg`.
- **411: a rectangular OS blob that OS itself rejected.** Aerial shows a small rectangle next to a circular pond; the mask leaks into the pond/paving. Native status `REJECTED` / `low_pool_evidence`; POV overlay only changed `pool.status`. Visual: `panels/shape_v2_pipeline/stand_411.jpg`.
- **Listing 005: the real curved/waist pool in the night photo.** The mask traces the water, but the **bottom of the photo cuts the pool**, so the raw contour has a fake straight edge. Hybrid qualitative class is already `rectangular`. After 64-pt resample + PCA the scoring polyline looks like a compact 4-corner blob (`n_corners=4` in freeze listing_shape). Family v1 still calls it **KIDNEY_CURVED** (1 indent, high angle-entropy, low sharp_frac) — the curved family, not a rectangle.

Because the 540 contour is the in-parcel rectangle, **this is not a stop-at-segmentation-only case.** Segmentation of 540 is leaky (jagged FastSAM; OS class `kidney_or_curved`) but the scored object is still the square pool. Shape v2 then over-matches it to the listing.

Exact JSON dumps: `shape_v2_exact_contours/`. Pipeline panels: `panels/shape_v2_pipeline/`.

### Listing 116778622-005

- Extractor: YOLOE/SAM2 Hybrid; `contour_image` 64-pt resample; qualitative Hybrid class `rectangular`
- Point count: 64
- Scaled (400 px) rectangularity=0.6985 solidity=0.9572 elongation=1.324 circularity=0.7244 sharp_frac=0.1562 angle_entropy=0.6787 n_major_indents=1
- Shape v2 normalisation: center → PCA-align major axis → flip heavier half to +x → scale to unit max radius → chamfer with 4 axis flips
- Hybrid raw indents: 1; freeze n_major_indents in listing_shape: 1

### Top-5 OS contours

| Stand | Native OS status | After POV | Native OS class | area_m² | OS rectangularity | Shape Family v1 |
| --- | --- | --- | --- | ---: | ---: | --- |
| 540 | CONFIRMED | CONFIRMED | kidney_or_curved | 14.31 | 0.6497 | RECTANGULAR (0.67) |
| 411 | REJECTED | CONFIRMED | kidney_or_curved | 25.71 | 0.754 | RECTANGULAR (0.68) |
| 591 | CONFIRMED | CONFIRMED | rectangular | 35.12 | 0.8406 | RECTANGULAR (0.64) |
| 897 | CONFIRMED | CONFIRMED | rectangular | 23.42 | 0.801 | RECTANGULAR (0.66) |
| 871 | CONFIRMED | CONFIRMED | irregular | 25.83 | 0.7412 | COMPOUND_IRREGULAR (0.87) |

## Phase 2 — Shape v2 component decomposition

Production weights (unchanged): elongation 0.22, chamfer 0.18, hu 0.16, solidity 0.10, n_indents 0.08, max_indent 0.08, n_corners 0.08, circularity 0.05, **sharp_frac 0.03**, radial_cv 0.02.

| Candidate | Final shape_v2 | elongation | chamfer | hu | solidity | n_indents | max_indent | n_corners | circularity | sharp_frac | radial_cv |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 540 | 0.8161 | 0.8787 | 0.7794 | 0.6973 | 0.9498 | 0.7500 | 0.9236 | 0.8750 | 0.7711 | 0.5138 | 0.9043 |
| 411 | 0.7519 | 0.9005 | 0.6639 | 0.4297 | 0.9436 | 0.7500 | 0.9872 | 0.6250 | 0.9856 | 0.5138 | 0.8770 |
| 591 | 0.7750 | 0.9270 | 0.7000 | 0.3066 | 0.9456 | 0.7500 | 0.9510 | 1.0000 | 0.9693 | 0.6527 | 0.8667 |
| 897 | 0.7683 | 0.6574 | 0.7271 | 0.5077 | 0.9364 | 1.0000 | 0.9932 | 1.0000 | 0.8653 | 0.5831 | 0.8870 |
| 871 | 0.7653 | 0.9604 | 0.7338 | 0.4382 | 0.7844 | 0.5000 | 0.9514 | 1.0000 | 0.7733 | 0.6527 | 0.9527 |

### Why Stand 540 obtains 0.8161

Reconstructed combined = **0.8161** (freeze `shape_v2=0.8161`).

Weighted contributions:

| Term | weight | similarity | contribution |
| --- | ---: | ---: | ---: |
| elongation | 0.22 | 0.8787 | 0.1933 |
| chamfer | 0.18 | 0.7794 | 0.1403 |
| hu | 0.16 | 0.6973 | 0.1116 |
| solidity | 0.1 | 0.9498 | 0.095 |
| n_indents | 0.08 | 0.75 | 0.06 |
| max_indent | 0.08 | 0.9236 | 0.0739 |
| n_corners | 0.08 | 0.875 | 0.07 |
| circularity | 0.05 | 0.7711 | 0.0386 |
| sharp_frac | 0.03 | 0.5138 | 0.0154 |
| radial_cv | 0.02 | 0.9043 | 0.0181 |

**Overpowering terms:** elongation, chamfer, Hu, solidity (weights 0.22+0.18+0.16+0.10). These are scale/rotation-invariant compactness stats. After PCA both listing and 540 look like compact blobs.

**Underweighted mismatch:** `sharp_frac` (curves vs polygon corners) has weight **0.03**. Indent count mismatch is cheap (`n_indents` scale=4). **Angle entropy is not in Shape v2 at all.**

Chamfer after PCA+4 flips is high — a rectangle and a mildly waisted freeform are close once both are unit-scaled and axis-aligned. Chamfer is **tolerant**, not the sole failure.

## Phase 3 — Contour normalisation ablation

Chamfer similarity `1/(1+4·mean_nn)` (best of 4 axis flips). Pre-final stages are unit-scaled so listing-photo vs aerial 0–1 frames are comparable. `final` is `pca_normalize` as Shape v2 uses.

| Stage | vs 540 | vs 411 |
| --- | ---: | ---: |
| raw | 0.7424 | 0.6293 |
| translated | 0.7424 | 0.6293 |
| scale | 0.7424 | 0.6293 |
| rotation | 0.7794 | 0.6639 |
| resampled | 0.7465 | 0.6261 |
| final | 0.7794 | 0.6639 |

Interpretation:

- **Translation-only / raw (unit-scaled, no PCA)** already yields a high chamfer if both contours are compact blobs of similar AABB aspect.
- **Scale normalisation** removes pool-size (540 is ~14 m²). Expected for cross-source matching, but it also removes a cue that 540 is a small rectangle.
- **Rotation / PCA** is required for aerial vs street-view yaw, but it makes a square and a freeform share a major-axis frame, after which chamfer is easy to satisfy.
- **64-point resample** is applied to the listing Hybrid contour before freeze; OS contours keep native vertices then PCA. Resample rounds the listing waist toward a 4-corner blob (`n_corners=4`). Production `_resample` picks arc-length bins (no linear interpolation).
- **No convex-hull substitution** is used as the scored contour.

Normalisation is a **contributing** failure (PCA + unit scale + chamfer tolerance), not the only one. Descriptor choice is the larger issue: the pipeline throws away the curve-vs-polygon signal.

## Phase 4–5 — Pool Shape Family v1

Geometry-only classifier. No water colour, no stand identity, no listing-id hardcoding.

- Listing `116778622-005` → **KIDNEY_CURVED** (conf 0.53): high_angle_entropy_low_sharp_fraction

| Id | Family | Conf | vs listing | frozen shape_v2 |
| --- | --- | ---: | --- | ---: |
| 116778622-005 | KIDNEY_CURVED | 0.53 | self | None |
| 540 | RECTANGULAR | 0.67 | incompatible | 0.8161 |
| 411 | RECTANGULAR | 0.68 | incompatible | 0.7519 |
| 591 | RECTANGULAR | 0.64 | incompatible | 0.775 |
| 897 | RECTANGULAR | 0.66 | incompatible | 0.7683 |
| 871 | COMPOUND_IRREGULAR | 0.87 | partial | 0.7653 |

Validation panel: `panels/shape_family_validation.jpg`.

Confusion / limitation cases:

- Listing 005 is **KIDNEY_CURVED** (conf 0.53) rather than FREEFORM: one major indent + solidity 0.96. Visually it is still the curved/asymmetric pool; the important split vs 540/411 is curved vs polygonal, which the classifier gets right.
- 540/411 leaky masks look jagged in the pipeline panel, but angle-entropy still marks them polygonal → RECTANGULAR. That is the intended coarse split.
- 871 COMPOUND_IRREGULAR matches the aerial L/boot pool (not a rectangle).
- 401 (labelled GT for 115503057) is LAP_ELONGATED — correct on the OS contour.
- 338 OS REJECTED blob is RECTANGULAR — a gating risk if REJECTED contours are allowed into a hard family gate.
- 868 is KIDNEY_CURVED (single indent). 624/648/401 are LAP_ELONGATED.

## Phase 6 — Diagnostic compatibility (not production)

Policy (not tuned to a winner): incompatible multiplier **0.20**, partial **0.55**, compatible **1.0**. UNKNOWN never rejects.

### A. Hard reject (Top 20 only, diagnostic)

Clearly incompatible families are dropped from diagnostic ranking A. UNKNOWN is kept.

### B. Penalty (replace Shape v2 contribution only; other frozen terms untouched)

| Stand | frozen rank | family | compat | frozen shape_v2 | adj shape_v2 | frozen score | adj score |
| --- | ---: | --- | --- | ---: | ---: | ---: | ---: |
| 540 | 1 | RECTANGULAR | incompatible | 0.8161 | 0.1632 | 0.7404 | 0.5054 |
| 411 | 2 | RECTANGULAR | incompatible | 0.7519 | 0.1504 | 0.7276 | 0.5111 |
| 591 | 3 | RECTANGULAR | incompatible | 0.775 | 0.155 | 0.7274 | 0.5042 |
| 897 | 4 | RECTANGULAR | incompatible | 0.7683 | 0.1537 | 0.719 | 0.4977 |
| 871 | 5 | COMPOUND_IRREGULAR | partial | 0.7653 | 0.4209 | 0.7118 | 0.5878 |

## Phase 8 — PR #32 Top 20 diagnostic

| Stand | frozen rank | family | listing family | compat | shape_v2 | adj score | diag rank (penalty, among Top20) | hard-reject |
| --- | ---: | --- | --- | --- | ---: | ---: | ---: | --- |
| 540 | 1 | RECTANGULAR | KIDNEY_CURVED | incompatible | 0.8161 | 0.5054 | 11 | True |
| 411 | 2 | RECTANGULAR | KIDNEY_CURVED | incompatible | 0.7519 | 0.5111 | 9 | True |
| 591 | 3 | RECTANGULAR | KIDNEY_CURVED | incompatible | 0.775 | 0.5042 | 12 | True |
| 897 | 4 | RECTANGULAR | KIDNEY_CURVED | incompatible | 0.7683 | 0.4977 | 14 | True |
| 871 | 5 | COMPOUND_IRREGULAR | KIDNEY_CURVED | partial | 0.7653 | 0.5878 | 5 | False |
| 640 | 6 | UNKNOWN | KIDNEY_CURVED | no_decision | 0.7702 | 0.7078 | 1 | False |
| 382 | 7 | COMPOUND_IRREGULAR | KIDNEY_CURVED | partial | 0.6685 | 0.5977 | 4 | False |
| 898 | 8 | RECTANGULAR | KIDNEY_CURVED | incompatible | 0.6892 | 0.5069 | 10 | True |
| 644 | 9 | RECTANGULAR | KIDNEY_CURVED | incompatible | 0.7325 | 0.493 | 15 | True |
| 1/373 | 10 | RECTANGULAR | KIDNEY_CURVED | incompatible | 0.8285 | 0.4644 | 20 | True |
| 673 | 11 | RECTANGULAR | KIDNEY_CURVED | incompatible | 0.7277 | 0.4918 | 16 | True |
| 629 | 12 | RECTANGULAR | KIDNEY_CURVED | incompatible | 0.6746 | 0.4996 | 13 | True |
| 502 | 13 | ROUND_OVAL | KIDNEY_CURVED | partial | 0.712 | 0.5773 | 6 | False |
| 672 | 14 | COMPOUND_IRREGULAR | KIDNEY_CURVED | partial | 0.7002 | 0.5771 | 7 | False |
| 4/870 | 15 | RECTANGULAR | KIDNEY_CURVED | incompatible | 0.76 | 0.4705 | 19 | True |
| 350 | 16 | RECTANGULAR | KIDNEY_CURVED | incompatible | 0.7058 | 0.485 | 18 | True |
| 572 | 17 | KIDNEY_CURVED | KIDNEY_CURVED | compatible | 0.6572 | 0.687 | 2 | False |
| 545 | 18 | COMPOUND_IRREGULAR | KIDNEY_CURVED | partial | 0.6959 | 0.5697 | 8 | False |
| 1105 | 19 | KIDNEY_CURVED | KIDNEY_CURVED | compatible | 0.7786 | 0.6818 | 3 | False |
| 523 | 20 | LAP_ELONGATED | KIDNEY_CURVED | incompatible | 0.6605 | 0.4896 | 17 | True |

If 540/411 stayed high **without** the family layer, that is exactly the Shape v2 failure. **With** the diagnostic penalty they fall (frozen 1–4 → diagnostic 9–14 among Top 20) because KIDNEY_CURVED vs RECTANGULAR is incompatible.

Caveat: diagnostic Top-20 #1 under the penalty is stand **640 UNKNOWN** (`no_decision` passthrough, shape_v2 kept). Compatible KIDNEY_CURVED candidates 572 and 1105 rise to #2/#3. That is **not** a claim that 640 or 572 is the true stand (listing remains unlabelled). UNKNOWN passthrough is why a hard gate must not be shipped yet.

## Phase 7 — Historical regression (summary)

Full tables: `SHAPE_FAMILY_REGRESSION.md`. Ground-truth stand numbers are report labels only.

| Listing | GT | frozen rank → penalty rank | hard-rejected? |
| --- | --- | --- | --- |
| 115503057 | 401 | 5 → 252 | **YES (wrongly)** |
| 117262832 | 338 | 122 → 31 | YES on REJECTED blob family; `shape_v2` was already null |
| 117170887 | 641 | n/a | GT absent from candidates |

Stand 401 is a **lap-elongated** OS contour against a listing contour that Family v1 called KIDNEY_CURVED. A hard family gate would have dropped the labelled true stand from rank 5 to 252. That is the generalisation bar: **do not promote hard reject**.

Stand 338 never entered Shape v2 (`shape_v2=null`, OS REJECTED). Penalty rank rose only because other candidates lost shape contribution; the REJECTED blob was still classified RECTANGULAR and would be hard-dropped. A shape-family gate cannot be described as fixing 338.

## Recommendation

| Option | Verdict |
| --- | --- |
| Reject Shape Family v1 | No — it separates this error class using geometry Shape v2 ignores |
| Retain diagnostic-only | **Yes (this PR)** |
| Promote to candidate gating | Not yet — need more labelled cases; hard-reject would drop many compact rectangles against any curved listing photo |
| Incorporate into Shape v2 | Candidate follow-up: raise `sharp_frac` / add angle-entropy; do **not** retune weights inside this forensic |

Do not merge family gating into production in this task.

