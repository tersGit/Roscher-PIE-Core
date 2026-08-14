# Pool Boundary Extraction v1

Generic Stage A (pool present?) vs Stage B (physical coping/perimeter) diagnostic on listings **116978058** and **116273255**.

Frozen and unmodified: production ranking, OS v1, Scoring v2, native15 crops, PR #8 viewpoint-gate *rules*, PR #10 colour-independent object diagnostic. **No estate rerank.** No listing/stand hardcodes. No L-pool or octagon rules. Water colour is not used to define the polygon.

**Official visual quality gate: FAIL.**  
**Success criteria (useful physical geometry on at least one overview from BOTH listings): not met.**  
Automated listing gate after inspection-driven tightening: 116978058 pass on 008 only; 116273255 fail (0 scoring-ready frames). Visual inspection does **not** treat 008 as native15-comparable.

Artefacts: `data/investigations/pool_boundary_extraction_v1/{116978058,116273255}/panels/` (original | overlay) and `latest.json`.

## What was tested

Stage A reuses frozen PR #8 viewpoint classification. Colour-blob contours from Listing Evidence v2 are recorded only as a prior diagnostic, not as Stage B polygons.

Stage B methods (generic combinations):

| method | role |
|---|---|
| FastSAM object proposals + CLIP class | Stage A seed / object presence. **Cannot pass the perimeter gate.** |
| `local_ridge_snap` | Short outward-normal snap of the object contour onto grayscale Sobel ridges |
| `coping_ring_lsd` | LSD segments in a dilated-minus-eroded ring; drop wall-climb; greedy chain |
| Geometric closure / area / compactness | Gate, not a detector |
| CLIP on the proposal crop | Pool vs wall / vegetation / furniture / bathtub / interior / deck |
| Multi-frame dominant-axis corroboration | Confidence only; **cannot promote** a weak-structure contour |
| `vanishing_rectification` | Two LSD families + minAreaRect homography; marked oblique unless families look orthogonal |

Hard rule: no RGB/HSV/water-hue/saturation/brightness or listing-to-aerial colour similarity is used to define the pool polygon.

## A. Boundary recovery success for 116978058

**Partial on one overview. Not scoring-ready.**

| frame | viewpoint | automated | visual | notes |
|---|---|---|---|---|
| 008 | pool_overview | ACCEPT `local_ridge_snap` struct=0.49 | **Best recovery** | Follows main-pool coping-to-grass on far/left/right; **ignores background jacuzzi**; jittery vs straight masonry; messy near-camera right corner |
| 003 / 005 / 006 | pool_overview | REJECT | Lawn smear / jacuzzi-platform blob | FastSAM union swallows lawn. Gate now correctly rejects |
| 009 | pool_overview | REJECT struct=0.41 | Lawn leak on far/right edge | Same family as 008 but weaker structure |
| 033 | pool_overview | REJECT | LSD traces coping well; chained polygon fails area | Ridge contour includes deck masonry and a spike |
| 025 | pool_closeup | REJECT `closeup_not_overview` | Correct | LSD follows jacuzzi *platform*, not the spa rim |
| 023 | ground_level_exterior | REJECT | Patio table / tile grid, not the distant pool | Correct reject |
| 001 / 002 / 051 / 052 | unusable / interior | REJECT | Agent headshots / interiors | Viewpoint gate holds |

008 is **materially more of the main-pool perimeter** than the previous water-fragment/smear extractor (LEV2 kept only jacuzzi close-up 025 and internal cyan slivers). It is still a jittery oblique outline, not a closed coping polygon with trustworthy corners.

008 geometry (image-space, not nadir): compactness 0.137, solidity 0.915, aspect 3.98, straight-edge proportion 0.34, curved 0.66, n_corners=4, n_major_indents=1. No semantic shape name is assigned.

## B. Boundary recovery success for 116273255

**No.** Automated gate: 0 scoring-ready frames. Visual: no overview recovers a recognisable rectilinear/concave planform.

| frame | viewpoint | automated | visual | notes |
|---|---|---|---|---|
| 037 | pool_overview | REJECT | Cuts across water; swallows timber deck and planter; **misses inner corner** | FastSAM/ridge object region ≠ coping |
| 038 | pool_overview | REJECT | Diagonal cut at the pillar; includes wet deck; no 90° inner corner | Same failure |
| 008 | elevated_exterior | REJECT | Polygon on **tiled steps**, not the L-pool | Correct reject after gate tighten |
| 036 | elevated_exterior | REJECT | Furniture/chair contour; pool under cover/net | Correct |
| 029 | pool_closeup | REJECT | Bathtub / shower | Correct |
| 020 | labelled pool_overview | REJECT `no_pool_object_proposal` | Interior landing, no pool | Correct |
| 007 | ground_level_exterior | REJECT | Front driveway, no pool | Correct |
| 001 / 002 | unusable | REJECT | Agent headshots | Correct |

LSD *does* find some far coping segments on 037/038, but chaining cannot close a pillar-occluded inner corner and readily includes deck-board lines.

## C. Best-performing extraction method

**`local_ridge_snap` on a CLIP-validated FastSAM object seed**, and only when that seed is already close to the pool (116978058-008).

- FastSAM+CLIP is useful for **Stage A presence**. FastSAM masks are not perimeters (lawn, deck, platform).
- `coping_ring_lsd` often has high `structural_support` (0.8–1.0) because chained fragments lie *on* LSD segments, but greedy endpoint chaining yields `implausible_perimeter_area` (tiny fragments or over-closed blobs).
- Ridge snap beats FastSAM union when the object seed is the pool; it still tracks deck/lawn/steps when the seed is wrong.

## D. Did perspective rectification help?

**No, not in a way that is safe to use.**

008 is the only frame the pipeline marked `rectification.reliable=true` (`orthogonal_line_families`, principal-angle delta 80.6°). Visual inspection: LSD families mix coping, window frames, and the jacuzzi platform. minAreaRect of a jittery contour is a weak pool-plane estimate. All other frames are `oblique` / `weak_minarea_proxy`.

Do not treat rectified descriptors as nadir-compatible measurements.

## E. Did multi-frame corroboration help?

**No. The first pass hurt.**

Dominant-axis agreement promoted FastSAM lawn blobs (003/005/006) and the tiled-steps contour (116273255-008) to ACCEPT. After the gate redesign, corroboration may raise confidence but **cannot waive** `structural_support < 0.48` and cannot make a FastSAM mask scoring-ready. It did not recover the 116273255 inner corner.

Multi-frame is corroboration of axes, not fusion of image-space contours (those were not merged).

## F. False positives remaining

Now **rejected by the automated gate** (were false-ACCEPT before tightening):

| listing | object | frames |
|---|---|---|
| 116978058 | lawn smear / garden leakage | 003, 005, 006, 009 |
| 116978058 | jacuzzi platform as spa perimeter | 025 (also close-up blocked) |
| 116978058 | patio table / tile grid | 023 |
| 116273255 | tiled steps | 008 |
| 116273255 | timber deck + planter | 037, 038 |
| 116273255 | furniture / railing / pool cover | 036 |
| 116273255 | bathtub | 029 |
| 116273255 | interior landing | 020 |
| both | agent headshots | 001, 002 |
| 116978058 | interiors | 051, 052 |

Remaining **proposal** contamination (rejected, but still the strongest contour the methods can offer): deck vs coping, steps vs pool, lawn vs coping, LSD on windows/railings/deck boards. Reflections and tiny water fragments are no longer the polygon source (colour blobs are not Stage B).

## G. Quality-gate reliability

| gate | result |
|---|---|
| Previous automated gate (PR #10 / first PBE pass) | False-passed closed polygons (trees/wall/furniture; lawn blobs; tiled steps) |
| Tightened automated gate | Matches visual rejects on those controls. FastSAM mask cannot pass. Structure floor 0.48 is not waived by multi-frame. Close-ups, interiors, bathtubs blocked |
| 116978058 automated | ACCEPT 008 only |
| 116273255 automated | FAIL (0 ready) |
| **Official visual gate** | **FAIL** — 008 is the only plausible overview contour and is still jittery / corner-broken / oblique. A large closed polygon is not sufficient; 008 would be a false *scoring-ready* pass if used against native15 OS contours |

Visual inspection remains mandatory. The redesigned gate is stricter and no longer false-passes the named controls, but it still cannot certify coping geometry.

## H. Trustworthy enough to compare against native15 OS pool contours?

**No.**

008 is an oblique, jittery coping-to-grass trace. Compactness 0.14 is smear-like even when the region is roughly the pool. Straight masonry is not recovered. 116273255 has no usable planform (missing concave inner corner, deck included). Comparing these polygons to native15 OS pool contours would measure extractor failure, not listing-to-parcel agreement.

## I. Remaining technical bottleneck

Not object presence. Not ranking. Not colour.

**Physical perimeter assembly from structure, under occlusion and adjacent deck/lawn.**

Precise gaps:

1. FastSAM (and CLIP crops) return a *pool-object region*. Adjacent timber deck, wet paving, lawn, and steps join that region. Stage B inherits the error.
2. Ridge snap follows local intensity, so it hugs grass/coping contrast when lucky and walks onto lawn/deck/steps when not. It does not lock to long straight coping segments, so corners smear.
3. LSD *does* see many true coping segments, plus deck boards, grout, railings, and windows. Greedy ring chaining cannot build a closed coping polygon of plausible area, and has no model of a pillar as an inner corner / occlusion.
4. Homography from minAreaRect + mixed line families is not a pool-plane rectification.
5. Multi-frame axis agreement is too weak a geometric constraint to transfer a coping segment from 037 to 038.

Next generic work (still no listing-specific shapes, still no rerank): constrained polygon from coping-ring LSD (not greedy chain); CLIP on a *contour band* to reject vegetation/deck/steps; treat pillars as occluders rather than cuts across water; only then revisit pool-plane rectification from two *coping* line families.

## Phase 5 — ranking

**Not run.** No 330-candidate rerank. No Scoring v2 weight change. No production `combined_score` change.

## Controls vs named failure modes

| required control | outcome |
|---|---|
| 116273255 trees / wall / furniture / pillar | 036 furniture REJECT; 037/038 pillar cuts water (rejected, not solved) |
| 116273255 pool cover/net | 036 REJECT |
| 116273255 bathtub | 029 REJECT |
| 116273255 interior landing | 020 REJECT |
| 116978058 reflections / tiny water fragments | No colour-blob polygon; 008 uses structure |
| 116978058 jacuzzi close-up | 025 REJECT closeup |
| 116978058 garden/background leakage | 003/005/006/009 REJECT |
| 116978058 smeared pool blobs | FastSAM unions REJECT |

## Answers (A–I)

- **A.** Partial: 008 recovers more of the main-pool perimeter than the smear extractor; not scoring-ready.
- **B.** No: 037/038 do not preserve rectilinear/concave structure.
- **C.** `local_ridge_snap` on a pool-like FastSAM seed; FastSAM alone is not a perimeter.
- **D.** No (claimed orthogonal families on 008 are not a trustworthy pool-plane).
- **E.** No (first pass promoted false positives; after tightening it does not recover B).
- **F.** Lawn, deck, steps, furniture, jacuzzi platform still appear as *proposals*; gate now rejects them.
- **G.** Automated gate no longer false-passes the named controls; visual gate still FAIL for scoring-ready geometry.
- **H.** No.
- **I.** Coping-constrained polygon assembly under deck adjacency and pillar occlusion — not colour, not ranking.
