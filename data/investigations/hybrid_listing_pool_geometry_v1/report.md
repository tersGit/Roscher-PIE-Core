# Hybrid Pool Geometry v1

Listing-side extractor: frozen viewpoint gate → YOLOE-11s/11m (`swimming pool`, with generic recall prompts) → optional SAM 2.1 tiny from YOLOE box → FastSAM presence/fallback only.

Frozen and unmodified: production ranking, OS v1, Scoring v2, native15, viewpoint-gate *rules*, FastSAM implementation, PR #12 benchmark outputs. **No estate rerank.** Water colour is not used as geometry or matching evidence. No listing/stand hardcodes, no jacuzzi/L/octagon rules.

**Official visual quality gate: PASS.**  
**No 330-candidate ranking in this PR.** Hybrid is stable enough to freeze as the listing-side geometry extractor. The next justified experiment is a frozen native15 / Scoring v2 comparison.

Panels: `data/investigations/hybrid_listing_pool_geometry_v1/{listing}/panels/`

## Architecture (source hierarchy)

Exactly one source per eligible frame:

| source | when |
|---|---|
| `yoloe_sam2` | Valid YOLOE pool + SAM2 box refine with IoU ≥ 0.45 and no area explosion |
| `yoloe` | Valid YOLOE pool; SAM2 rejected or unhelpful |
| `fastsam_fallback` | No valid YOLOE; FastSAM box → SAM2 passed extra compactness/structure checks. **Not scoring-ready** |
| `presence_only` | FastSAM suggests a pool object, no valid boundary |
| `no_usable_geometry` | blocked viewpoint or nothing found |

FastSAM never overrides a valid YOLOE/SAM2 boundary. Scoring-ready geometry is **only** `yoloe` / `yoloe_sam2` on overview/elevated/ground-exterior viewpoints. Close-ups are recorded, not overview-ready.

YOLOE gate (generic): detector conf, closure/area, contamination, clipping, smear compactness, bathtub/interior, close-up. CLIP “deck” is **not** a reject (that prompt includes coping). A text-prompt hit is not sufficient.

## Dark-overview investigation (no colour)

Frames 116978058-003/005/006/009/033, generic automatable settings only.

| change | effect |
|---|---|
| conf 0.04 | Sometimes a large mask at conf &lt; 0.08 that **fails** the validation gate |
| imgsz 1024 | Tiny jacuzzi fragments (area ~0.003), not the main pool |
| prompt `outdoor swimming pool` / `residential swimming pool` | **Recovers 009 and 033** at conf ≥ 0.18, area ~0.20–0.25 |
| YOLOE-11s vs 11m | 11s recovered 009/033/037/038; 11m recovered 008. Hybrid keeps both |
| FastSAM box → SAM2 | Fallback on 003/006; **not** scoring-ready |
| tighter crops | not required once prompt variants ran |

Early-exit bug (low-conf large blob blocking later prompts) was fixed generically. 003/005/006 remain YOLOE misses (honest FN).

## Regression (visual)

**116978058**

| frame | result |
|---|---|
| 008 | **READY `yoloe_sam2`**. Main-pool cyan; jacuzzi purple secondary. Cleaner than PR #11. Listing chosen frame |
| 009 | READY `yoloe` after `outdoor swimming pool`. Main pool + jacuzzi secondary. SAM2 unhelpful |
| 033 | READY `yoloe_sam2` but noisier (masonry leak). Listing still prefers 008 |
| 003/005/006 | YOLOE miss; 003/006 FastSAM fallback **not** scoring-ready; 005 presence only |
| 025 | YOLOE spa close-up, **not** overview |
| 023 | FastSAM fallback on a patio table — **not** scoring-ready |
| 001/051 | blocked |

**116273255**

| frame | result |
|---|---|
| 037 | **READY `yoloe_sam2` q=0.74**. Deck excluded; PR #12 improvement retained |
| 038 | **READY `yoloe_sam2`**. Visible L / inner corner; deck excluded |
| 008 | READY `yoloe_sam2`. Steps/deck not the pool |
| 029 | no usable geometry (bathtub) |
| 036 | presence only (cover/net, railing) |
| 007/020 | no usable geometry |

## Multi-frame

Masks are not merged. Listing evidence = strongest valid overview (`yoloe_sam2` / `yoloe`). Several FastSAM fallbacks cannot outweigh 008 or 038. Geometry marked **oblique**; no manufactured nadir area.

## A–K

**A. YOLOE recall on eligible pool frames**  
116978058 overviews: 3/7 scoring-ready (008, 009, 033). 003/005/006 still FN. Close-up 025 detected but gated.  
116273255 pool/elevated with a visible pool: 3/4 (008, 037, 038). 036 cover missed.

**B. Frames using YOLOE+SAM2**  
116978058: 008, 033.  
116273255: 008, 037, 038.

**C. Frames requiring FastSAM fallback** (not scoring-ready)  
116978058: 003, 006, 011, 023.  
116273255: none as fallback; 036 presence only.

**D. Main vs secondary**  
Generic largest-plausible vs smaller separated component. 008 and 009 keep the spa as secondary; it does not replace the main pool. No listing-specific jacuzzi rule.

**E. 116978058**  
At least one reliable observation (008 `yoloe_sam2`). Jacuzzi does not replace the main pool. Lawn smears are not scoring-ready. Dark 003/005/006 remain YOLOE FNs.

**F. 116273255**  
PR #12 037/038 improvement retained. Timber deck excluded. Visible concavity represented. 008 steps not promoted as the pool. 029 bathtub rejected.

**G. Remaining false positives**  
023 patio-table FastSAM fallback (suppressed: not scoring-ready). 033 scoring-ready but noisy; listing_best is still 008.

**H. Remaining false negatives**  
Dark overviews 003/005/006; covered 036; distant/occluded 026.

**I. CPU runtime**  
This diagnostic (extract + dark probe): **~259 s**, peak RSS **~4.2 GiB** (YOLOE + SAM2 + FastSAM + CLIP). Load YOLOE-11s 0.15 s, 11m 0.07 s, SAM2.1-t 0.20 s. After viewpoint filter, a 40–60 photo listing should stay in a few minutes on CPU. No GPU.

**J. Quality gate?**  
**PASS** after visual inspection. Criteria met: 037/038 retained; FPs suppressed from scoring-ready set; main/secondary improved; ≥1 reliable 116978058 frame; no colour geometry.

**K. Next experiment?**  
**Yes — a frozen native15 / Scoring v2 comparison**, in a later authorised PR. Do **not** rerank 330 in this PR. Hybrid v1 is stable enough to freeze as the listing-side geometry extractor for that comparison.
