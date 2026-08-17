# PR #25 forensic — Corner Gate counterfactual (not a rerun)

PIE was not modified. Scores were not recomputed. Historical freeze files were not rewritten.

Machine-readable twin: `forensic.json`.
Proof: `panels/listing_official_vs_338_rejected_pool.jpg`.

## 1. Verified historical SHA256

```
32ecd4b526d4a299e143c869761664a9ed7a4b2d9ae65aba6ed300583a1dd10a
```

On-disk `freeze.json` matches `freeze.sha256` and the PR #25 lock. Freeze commit `4f24f3f`.

## 2. Stand 338 original frozen rank

**122 / 332** (SUMMERSET EXT.6). Frozen total score **0.5847**.

These are freeze/`all_candidates.json` values, not recalculated.

| Field | Frozen value |
| --- | --- |
| Rank | **122 / 332** |
| Extension | SUMMERSET EXT.6 |
| Total score | **0.5847** |
| Inventory pool | UNKNOWN |
| OS status | **REJECTED** (`os_high_conf_pool=false`) |
| Pool-presence score / contrib | 0.5-neutral / **0.07** (weight 0.14) |
| `shape_v2` | **null** |
| Shape contribution | **0.18** (0.5 × 0.36) |
| Spatial score / contrib | null / **0.11** (0.5 × 0.22) |
| Aerial similarity / contrib | 0.7943 / **0.0953** |
| Exterior similarity / contrib | 0.7396 / **0.0444** |
| GIS contrib | **0.015** (0.5 × 0.03, constant) |
| Stand-size contrib | **0.07** (perfect; listing 869 = GIS 869) |
| Genuine evidence sum | **0.2097** (aerial + exterior + stand size) |
| Neutral/default sum | **0.375** (pool presence + shape + spatial + GIS) |
| % actual evidence vs padding | **35.86% evidence / 64.14% padding** |

## 3. Stand 338 vs frozen false Top 5

Frozen PR #25 components only. Corner Gate is **not** in this table. Known-false status was not used.

| | **338** | **654** | **467** | **405** | **644** | **456** |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Frozen rank / score | 122 / 0.5847 | 1 / 0.7725 | 2 / 0.7479 | 3 / 0.7393 | 4 / 0.7388 | 5 / 0.7362 |
| OS | REJECTED | CONFIRMED | CONFIRMED | CONFIRMED | PROBABLE | CONFIRMED |
| `shape_v2` | **null** | 0.8744 | 0.7776 | 0.7623 | 0.7691 | 0.7687 |
| Shape contrib | 0.18 | 0.3148 | 0.2799 | 0.2744 | 0.2769 | 0.2767 |
| Pool-presence contrib | 0.07 | 0.14 | 0.14 | 0.14 | 0.14 | 0.14 |
| Spatial contrib | 0.11 | 0.11 | 0.11 | 0.11 | 0.11 | 0.11 |
| Aerial sim / contrib | 0.7943 / 0.0953 | 0.7982 / 0.0958 | 0.7706 / 0.0925 | 0.7681 / 0.0922 | 0.8193 / 0.0983 | 0.7689 / 0.0923 |
| Exterior sim / contrib | 0.7396 / 0.0444 | 0.7236 / 0.0434 | 0.7113 / 0.0427 | 0.7141 / 0.0428 | 0.7487 / 0.0449 | 0.6971 / 0.0418 |
| GIS contrib | 0.015 | 0.015 | 0.015 | 0.015 | 0.015 | 0.015 |
| Stand-size contrib | **0.07** | 0.0535 | 0.0679 | 0.0648 | 0.0537 | 0.0603 |

Every false Top-5 stand beat 338 for the same principal frozen reasons:

1. **`shape_v2`** — they had an accepted OS contour (contrib 0.27–0.31 vs 338’s 0.18 padding).
2. **Pool presence** — 0.14 vs 338’s 0.07 padding.

Spatial and GIS are identical 0.5-neutral on all six. Aerial/exterior are near-ties (644 has a small aerial edge). Stand size **helped 338** and still lost.

## 4. Candidate-side pool geometry (frozen OS v1)

What the frozen stack stored for stand 338 — not improved, not regenerated.

| Question | Frozen finding |
| --- | --- |
| OS pool status | **REJECTED** |
| Detection method | CLIP on FastSAM proposal; notes `rejected_as_road_shadow_or_roof` |
| Contour available in OS JSON | Yes (69 points) |
| Contour used in Scoring v2 | **No** |
| Aspect | 1.49 |
| Convexity (solidity proxy) | 0.9234 |
| Compactness | 0.6313 |
| Shape class | kidney_or_curved |
| Area | 49.65 m² |
| Centroid (norm / px) | (0.415, 0.502) / (163.5, 231.4) |
| Major indents / dir. changes | not stored on OS v1 payload → UNKNOWN |
| Pool–house | `relationships.pool_house = null`; leftover `old_pool_to_house_dist = 0.182` |
| CLIP | pool **0.019**, roof **0.498** |

Native15 of 338 shows an elongated rectangular backyard pool. The frozen blob sits on dark water/shadow against the house, labelled kidney, CLIP-as-roof.

**Was stand 338’s candidate pool geometry correctly represented?**

**MISSING**

A rejected in-parcel blob exists (POOR if inspected), but Scoring v2 saw **no pool geometry**. `shape_v2` is null. That is the ranking representation.

Proof (frozen contours only):
`panels/listing_official_vs_338_rejected_pool.jpg`

Left: listing photo `039` + official Hybrid 64-pt contour (cyan). Right: 338 native15 + frozen OS rejected contour (orange). Orange is **not** a Scoring v2 input.

## 5. Shape-specific forensic

Official listing fingerprint (freeze):

- frame `117262832-039`, FastSAM, aerial/near-nadir
- aspect **2.418**, solidity **0.946**, 1 major indent, **5** directional changes
- class irregular; relative area **0.0027**; centroid **(0.648, 0.058)** — near the **top of the frame**

That is a small high-frame object, not the glowing courtyard rectangle visible in the same photo. Distinctive Contour v2 independently shows a large pool mask discarded; that diagnostic was **not** a ranking input.

Why `shape_v2` is null for 338: OS REJECTED, so no candidate contour entered `shape_v2_similarity`. Contribution is the missing-neutral 0.18.

False Top 5 were **genuinely closer to the official (wrong) fingerprint** (`shape_v2` 0.76–0.87). The shape model did not secretly down-rank 338; it never saw 338’s pool.

## 6. Corner-Gate counterfactual

**COUNTERFACTUAL FILTERED RANK — NOT A RERUN**

Start with the frozen 332-row order. Apply PR #26 Corner Gate labels only (listing YES, confidence 0.86, high). Remove parcel `NO`. Keep `YES` and `UNKNOWN`. Do not touch scores.

**Stand 338 original rank: 122 / 332**
→
**Stand 338 Corner-Gate-filtered rank: 29 / 98**

Frozen score remains **0.5847**.

### New first 10 survivors (unchanged frozen scores)

| Filtered rank | Orig. rank | Stand | Frozen score | Corner | OS | `shape_v2` |
| ---: | ---: | --- | ---: | --- | --- | ---: |
| 1 | 4 | 644 | 0.7388 | UNKNOWN | PROBABLE | 0.7691 |
| 2 | 10 | 4/870 | 0.7327 | UNKNOWN | CONFIRMED | 0.7413 |
| 3 | 21 | 1/870 | 0.7165 | UNKNOWN | CONFIRMED | 0.7349 |
| 4 | 24 | 591 | 0.7127 | YES | CONFIRMED | 0.7595 |
| 5 | 26 | 897 | 0.7101 | UNKNOWN | CONFIRMED | 0.7228 |
| 6 | 28 | 665 | 0.7094 | UNKNOWN | CONFIRMED | 0.6682 |
| 7 | 29 | 502 | 0.7093 | YES | CONFIRMED | 0.7620 |
| 8 | 31 | 545 | 0.7078 | YES | CONFIRMED | 0.6580 |
| 9 | 35 | 17/908 | 0.7046 | UNKNOWN | CONFIRMED | 0.8021 |
| 10 | 37 | 350 | 0.7022 | YES | CONFIRMED | 0.7055 |

All ten still have measured OS geometry. 338 is not in this shortlist.

## 7. Corner Gate effect (verified from diagnostic records, not hard-coded)

| | |
| --- | ---: |
| Before | **332** |
| After | **98** |
| Removed | 234 (**70.48%**) |
| Originally above 338 | **121** |
| Of those removed by Corner Gate | **93** |
| Of those retained | **28** |
| Absolute rank improvement | **93** (122 → 29) |
| % of field scoring worse than 338, before | **63.55%** |
| % of field scoring worse than 338, after | **70.41%** |

False Top 5 from actual `parcel_corner_records.jsonl`:

| Stand | PARCEL_CORNER | Gate |
| --- | --- | --- |
| 654 | NO | **removed** |
| 467 | NO | **removed** |
| 405 | NO | **removed** |
| 644 | UNKNOWN | **retained** (new filtered rank 1) |
| 456 | NO | **removed** |

Matches PR #26 diagnostics.

## 8. Shape-only diagnostic (frozen `shape_v2` sort only)

122 of 332 have measured `shape_v2`. Stand 338 does not.

Nulls placed after all measured shapes, original frozen order among nulls:

`Stand 338 shape-only rank = 124 / 332`

Among measured-shape candidates: **unranked / 122**.

After Corner Gate (30 measured-shape survivors among 98; 338 still null; first among remaining nulls):

`Stand 338 shape-only + Corner Gate diagnostic rank = 31 / 98`

Corner Gate shrinks the field. It does not give 338 a shape match. The 30 surviving measured-shape stands still sit above it on shape.

## 9. Root causes (supported only)

1. **CANDIDATE_GEOMETRY_FAILURE** — OS REJECTED 338; `shape_v2` never entered.
2. **POOL_PRESENCE_FAILURE** — 0.07 vs 0.14 for every frozen Top-5 stand.
3. **LISTING_GEOMETRY_FAILURE** — official FastSAM `039` contour is a small top-of-frame object, not the courtyard rectangle that shape_v2 matched against.
4. **SHAPE_SIMILARITY_FAILURE** — false Top 5 really are closer to that official fingerprint; 338 was not compared.
5. **CONTEXT_FILTER_MISSING** — PR #25 had no Corner Gate. High-confidence listing YES would have removed 4/5 false Top 5.

Not supported as the miss: `WEIGHTING_FAILURE`, `AERIAL_VISUAL_FAILURE`, `EXTERIOR_VISUAL_FAILURE`, `GIS/STAND_SIZE_DISTORTION` (stand size helped 338), `INVENTORY/DATA_FAILURE` (UNKNOWN survived Pool Gate).

## 10. Decision

### B. CORNER GATE HELPS, BUT SHAPE/GEOMETRY STILL FAILS

Corner Gate is a strong filter (332 → 98, 122 → 29, 4/5 false Top 5 gone). Stand 338 does **not** enter a serious shortlist. The 28 candidates still above it, and the entire filtered Top 10, have measured OS geometry. Frozen 338 pool representation is **MISSING** from Scoring v2.

This is not A (geometry is not reasonably represented; rank 29/98 is not near Top 5). Not C (93-place move is not limited). Not D (the failure mode is readable from the freeze).

Stop. Next experiment should be a new blind listing. PIE was not changed.
