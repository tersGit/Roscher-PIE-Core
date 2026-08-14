# Pool Boundary model benchmark v2

CPU-only listing-side benchmark of stronger segmentation models against **frozen PR #11** FastSAM / `local_ridge_snap` boundaries.

Frozen and unmodified: production ranking, OS v1, Scoring v2, native15, viewpoint-gate rules, Pool Boundary Extraction v1. **No estate rerank.** FastSAM is not replaced. Water colour is not used as matching or geometry evidence. No listing/stand hardcodes, no L-shape or octagon rules.

**Official visual gate vs success criterion: CONDITIONAL PASS on 116273255; PARTIAL on 116978058.**  
Worth **supplementing** FastSAM on listing-side frames where YOLOE detects a pool. **Do not replace FastSAM. Do not proceed to native15 ranking in this PR.**

Panels: `data/investigations/pool_boundary_model_benchmark_v2/{listing}/panels/` (original | PR #11 | new model).

## A. Models considered

See `models_considered.md`. Short list:

| model | why considered | why not primary |
|---|---|---|
| FastSAM-s | frozen PR #11 baseline | already failing deck/lawn |
| FastSAM-x | larger same family | not a new capability |
| YOLOE-11s/11m-seg | text-prompted instance seg in existing ultralytics 8.3.253 | — **selected** |
| YOLO-World v2 | text boxes | YOLOE already returns masks |
| SAM 2.1 tiny | box/point boundary refiner, Apache weights | needs an object prompt |
| MobileSAM | smaller SAM | similar CPU cost, weaker |
| Grounding DINO + SAM2 | classic open-vocab pipeline | extra CUDA-oriented stack |
| SAM 3 | text concepts | 3.45 GB, GPU-oriented |
| YOLO11-seg COCO | fast | no swimming-pool class |

## B. Model selected and why

**YOLOE-11s-seg and YOLOE-11m-seg** with text prompt `swimming pool`, plus **SAM 2.1 tiny** prompted by the best YOLOE pool box / mask centroid (automatable, no manual clicks).

Why: already in the PIE ultralytics stack; CPU; text-prompted object (not colour); SAM2-t at imgsz 640 is ~0.3 s/frame when box-prompted, not the 23 s “segment everything” figure in the docs. SAM3 and Grounding DINO were rejected as impractical for CPU PIE.

Prompt strategies compared: text-only, multi-class text (`swimming pool`, `hot tub`, `wooden deck`, `lawn`), YOLOE box → SAM2, YOLOE centroid → SAM2.

## C. CPU / runtime

Environment: 4 vCPU, 15 GiB RAM, torch 2.13.0+cpu, no CUDA.

| item | measured |
|---|---|
| YOLOE-11s-seg | 27.8 MB weights; load 0.08 s |
| YOLOE-11m-seg | 57.5 MB weights; load 0.07 s |
| SAM 2.1 tiny | 74.5 MB weights; load 0.28 s |
| MobileCLIP text tower | **572 MB** `mobileclip_blt.ts` (YOLOE text prompts) |
| Peak RSS | **~2.1 GiB** |
| Wall clock this run | **82 s** for 17 diagnostic frames (4 YOLOE variants each; SAM2 on 9 frames) |
| YOLOE predict | ~0.14–0.4 s/frame @640 after classes are set |
| SAM2 box/point | ~0.3–1 s/frame @640 (not 23 s) |
| Typical 40–60 photo listing after viewpoint filter | **5–10 pool-overview/close-up frames** → YOLOE ~15–40 s; YOLOE+SAM2 ~30–90 s |

Inference can be limited to viewpoint-filtered pool frames. A slower model is acceptable listing-side at this cost. MobileCLIP 572 MB is the main install/RAM tax.

Licence: Ultralytics AGPL-3.0 wrapper; SAM 2 weights Apache-2.0.

## D. 116978058 result

| frame | PR #11 | new model (visual) |
|---|---|---|
| 008 overview | ACCEPT ridge, jittery, lawn leak near camera | **Better:** YOLOE-11m follows main-pool water/coping, excludes jacuzzi and most lawn. Conf only 0.09. SAM2 did not beat this mask |
| 003 / 005 / 006 / 033 | rejected lawn smears | **Miss:** YOLOE `n_dets=0` on dark reflective water |
| 009 | rejected ridge on main pool | **Miss main pool;** tiny YOLOE hit on background jacuzzi (area 0.002) |
| 025 close-up | REJECT closeup; LSD on platform | **Tight octagonal spa coping** (YOLOE-11m q=0.74). Still a close-up, not an overview |
| 023 patio | REJECT table/tiles | no pool det |
| 001 / 051 | blocked | no pool det |

Main-pool recovery depends on the water being YOLOE-visible. Dark overviews fail. 008 is the only overview with a usable new-model perimeter, and it is cleaner than PR #11.

YOLOE traces the **water–coping interface** (planform), not the outer grass–coping ring.

## E. 116273255 result

| frame | PR #11 | new model (visual) |
|---|---|---|
| 037 | REJECT: cuts water, swallows timber deck | **Materially better:** SAM2 box (YOLOE-11s q=0.74) follows water/coping, **excludes timber deck**, keeps straight edges; planter as local concavity |
| 038 | REJECT: diagonal cut at pillar, includes deck | **Materially better:** SAM2 follows visible L / inner corner, separates deck; n_major_indents=1 |
| 008 | REJECT: tiled steps | **Better:** SAM2 box (YOLOE-11s q=0.61) stays on water vs steps/deck; completeness still short of a full two-arm plan |
| 036 cover/net | REJECT furniture | no pool det (not a false positive) |
| 029 bathtub | REJECT closeup | **no swimming-pool mask**; multi-class said `hot tub` only |
| 020 landing / 007 front | no proposal | no pool det |

This is the PR #11 hard failure. 037/038 now preserve visible rectilinear/concave structure instead of swallowing the deck.

## F. Improvement over PR #11

**Yes on 116273255 (the required hard case).** Deck/steps contamination is the difference.

**Partial on 116978058:** 008 and 025 are cleaner object masks; dark main-pool overviews are worse (undetected).

SAM2 helped when the YOLOE box was already on the pool (037/038/008-116273255). It did not invent a pool on dark 116978058 overviews. Multi-class text helped controls (`hot tub` on the bathtub, `wooden deck` on driveways) but did not recover dark water.

## G. Remaining false positives / misses

- 116978058-009: jacuzzi instead of main pool
- 025: jacuzzi/spa correctly as a pool-like object; must stay viewpoint-gated as close-up
- Dark reflective main pools: **false negatives**
- Covered/netted pool 036: not detected
- CLIP “deck” scores high on true pool+coping crops (prompt includes coping stones) — do not use that as a reject
- YOLOE-11m missed 037/038 while 11s hit them — keep **11s in the listing-side mix**, not 11m alone

## H. Sufficiently accurate physical boundaries?

**On 116273255-037/038: yes enough to preserve visible rectilinear/concave planform** (success does not require the occluded pillar backside).

**On 116978058: only on 008**, and as waterline planform, not outer coping-to-grass. Not listing-wide.

Not yet trustworthy as a drop-in for every overview.

## I. Practical for automated PIE?

**Yes, listing-side, on the small viewpoint-filtered subset.** ~2 GiB RSS, <2 min/listing, no GPU. MobileCLIP 572 MB must live in `data/cache/models/` (gitignored). AGPL already implied by ultralytics FastSAM.

## J. Replace, supplement, or reject FastSAM?

**Supplement FastSAM only on listing-side pool frames where YOLOE fires.**

Do **not** replace FastSAM / PBE v1 globally: dark-water overviews still need the frozen pipeline (even if that pipeline cannot pass the PBE v1 gate). Do **not** reject YOLOE+SAM2: it is the first method that actually separates 116273255 from timber deck.

## K. Native15 comparison / ranking?

**Stop. Do not rerank.**

A later experiment may fuse YOLOE/SAM2 masks into listing evidence, then — only if authorised — compare those planforms to native15 OS pool contours. This PR does not change scoring or ranking.

## Visual inspection notes (mandatory)

Inspected original | PR #11 | new-model panels for both listings’ controls and overviews. Automated `pick_best` is not the visual gate. Official calls above are from those panels, not from CLIP/area scores.
