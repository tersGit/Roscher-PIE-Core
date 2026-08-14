# 116273255 — colour-independent pool object diagnostic (frozen PR #8)

Frozen and unmodified: production ranking, OS v1, Scoring v2 weights, native15 crops, PR #8 viewpoint-gating rules. Water colour is not a matching feature. No stand number entered extraction or scoring. No listing-specific L-shape scoring rule.

**Official quality gate: failed after visual inspection.** An automated gate false-passed on 037/036; those contours are not pool planforms. The 330-candidate scores that were computed from that false-pass are recorded only as a diagnostic of the false-pass, and are **not** a valid rerank.

---

## Phase 1 — Listing acquisition / frozen viewpoint

51 photographs acquired. Frozen PR #8 `classify_viewpoint`:

| Viewpoint | Count |
|---|---:|
| interior (rejected) | 36 |
| ground_level_exterior | 4 |
| elevated_exterior | 4 |
| pool_overview | 3 |
| unusable_ambiguous | 2 |
| pool_closeup | 1 |
| garden_only | 1 |
| aerial_near_nadir | 0 |

Contact sheet: `panels/contact_sheet.jpg`.

Useful pool photographs (human): **008, 036, 037, 038**. The listing L-pool wraps a structural pillar; 036 shows a cover/net.

---

## A. Did viewpoint filtering work?

**Mostly yes on the PR #7 failure modes; two new CLIP mislabels.**

Worked:
- **001 / 002** agent headshots → `unusable_ambiguous`; extraction skipped. No polo-shirt pool.
- **003 / 005 / 006 / 007** front driveway → `ground_level_exterior`; no false pool object.
- **36 interiors** blocked from spatial/scale/overview. No interior contributed spatial evidence.
- Close-up **029** did not contribute nadir scale (frozen close-up block).

Failed:
- **029** is a **bathroom with a freestanding bathtub**, labelled `pool_closeup`. Frozen CLIP, not a water-colour issue.
- **020** is an interior landing, labelled `pool_overview`. Object extractor correctly found no pool.

---

## B. Was the pool reliably detected as an object without relying on water colour?

**Detected as present, not as a boundary.**

| Frame | Frozen LEV2 (colour blobs) | Colour-independent object | Visual |
|---|---|---|---|
| 008 | pool=true (cyan sliver / smear) | obj=true, **water_fragment** q=0 | true L-pool; contour smears into trees |
| 036 | pool=false | obj=true, **full_pool_planform** q=0.78 | pool with cover/net; mask is furniture/railing/wall |
| 037 | pool=false | obj=true, **full_pool_planform** q=0.89 | true L-pool; contour follows patio then **trees/wall** |
| 038 | pool=false | obj=true, **water_fragment** q=0 | true L wrapping pillar; contour climbs the house |

CLIP object presence fires on the real pool frames without an HSV cyan/dark seed. That is progress versus frozen LEV2, which missed 036/037/038 entirely. The object **mask** is still not the coping polygon. Colour was not used as the matching feature; intensity-edge snap still climbed walls, trees, and railings.

---

## C. Was the full L-shaped physical boundary recovered?

**No.** Not on 008, 036, 037, or 038. The inner corner at the house pillar is never the extracted contour. Automated `full_pool_planform` on 036/037 is a **false label**.

---

## D. Which geometric characteristics were successfully extracted?

**Visually present in the photographs, not in the contours:**

- two dominant arms
- approximately perpendicular arms
- strong concave inner corner at the pillar
- straight outer coping
- rectilinear, not kidney
- pool in the building’s inner corner, immediately adjacent

**In the extracted contours:** L-like descriptors (`two_dominant_arms`, `consistent_with_l_planform`) fired on **036, 037, and even bathtub 029**. Those flags are firing on wall-climbing polygons, not on the pool. They are not usable evidence.

008’s rejected fragment did show many indents and low compactness (0.016) — correctly called a smear.

---

## E. Did multiple listing photographs produce consistent geometry?

**Photographs yes; extractions no.**

008 / 037 / 038 show the same L wrapping the pillar. Extracted contours are mutually inconsistent smears (trees vs furniture vs house wall). Automated “stable across views” was true only because two junk masks both tripped the L-like flags.

---

## F. Was reliable pool-house spatial evidence obtained?

**No.** 036 was marked spatial-eligible on a furniture/wall mask. 037 was not spatial-eligible. No nadir/aerial frame, so no valid pool/building area ratio. Frozen LEV2 marked 008 spatial-eligible on a colour-blob fragment; that was not used for the colour-independent score.

---

## G. Did the quality gate permit a 330-candidate rerank?

**Automated gate: yes (false). Visual / official gate: no.**

Chosen automated source 037 is not a pool planform. Under the hard rule (“genuinely usable pool boundary”), the rerank is **not permitted**. Scores below were computed before visual inspection and must be ignored as a match result.

---

## H. If reranked, what were the Top 5 and confidence?

**No valid rerank.**

False-pass scores (junk 037 contour, Scoring v2 weights unchanged, all 330 native15, no colour similarity term), **low confidence**, recorded only to show what a false planform does:

Scoring v2 (invalid): 1/389 0.692, 1/450 0.683, 1/343 0.678, 1/417 0.676, 1/334 0.674. Margin 0.0087.

Baseline combined_score (invalid): 1/357 0.927, 1/516 0.898, 1/334 0.892, 1/335 0.857, 1/484 0.856. Margin 0.0294. `#1` is OS REJECTED; size ≈ 500 m² is doing the work.

Do not treat any of these stands as a match.

---

## I. What new failure modes were identified compared with 116978058?

Repeats: colour-blob LEV2 still returns interior highlights / smears; coping is obvious in the photo and absent from the contour; L/octagon-class planforms collapse; no nadir listing frame.

New on this listing:

1. **CLIP object presence without a coping boundary.** Pool is recognised; the polygon is trees, wall, railing, or furniture.
2. **Cover/net (036) does not block object detection**, but the mask still misses the water plane.
3. **L wrapping a structural pillar** splits/climbs the wall instead of following two rectilinear arms.
4. **L-geometry descriptors fire on smears and on a bathtub.** `consistent_with_l_planform` is not a planform test until the contour is on the coping.
5. **Bathtub / shower labelled `pool_closeup` (029).** Frozen viewpoint CLIP.
6. **Interior landing labelled `pool_overview` (020).**
7. **Automated quality gate false-pass.** Compactness/CLIP-confidence ≠ “follows the pool edge.”
8. **False-pass ranking again crowns ~500 m² EXT.6 `1/xxx` stands**, including OS REJECTED `#1` on baseline.

---

## J. Is the next bottleneck object detection, boundary extraction, viewpoint transformation, or scoring?

**Boundary extraction.**

Object detection (pool vs not) already works on the useful frames without water-colour thresholds. Viewpoint gating already blocks headshots and interiors from scoring. Scoring was not the limiter: there was no genuine listing contour to score.

Next generic change: recover **coping/planform polylines** (straight edges, corners, concavity) from intensity structure inside a pool-object region, and **refuse** a contour that leaves the water plane (wall-climb / tree-climb / furniture). Do not add an L-shaped special case, and do not retune Scoring v2 until that boundary exists.
