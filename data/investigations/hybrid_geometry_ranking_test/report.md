# Hybrid Geometry ranking test

Frozen Hybrid Pool Geometry v1 listing evidence vs frozen native15 OS v1 candidate geometry, scored with **unchanged Scoring v2 weights**.

Unmodified: Hybrid v1, production `combined_score`, OS v1, Scoring v2, native15 crops, viewpoint gates, FastSAM, YOLOE/SAM2 thresholds. No extraction retuning. No weight tuning. No colour in Hybrid scoring. No estate production rerank.

Candidates: **330** unique Carlswald North native15 parcels. Ground truth applied **only after** `rankings.json` / `all_candidates.json` were written.

**Official ranking verdict: MIXED.**

## Listing evidence used

| listing | scoring-ready frames | official shape source | excluded |
|---|---|---|---|
| 116978058 | 008, 009, 033 | **008** `yoloe_sam2` (main pool; spa recorded as secondary, not in the listing contour) | FastSAM fallback 003/006/011/023; presence-only 005; close-up 025 |
| 116273255 | 008, 037, 038 | **038** `yoloe_sam2` | presence-only 036; bathtub 029 empty |

Hybrid spatial pool–house and oblique relative area were **omitted** (not viewpoint-compatible with nadir). Scoring v2 therefore 0.5-fills `spatial_v2`. Colour is not a scoring feature.

## Variants (same weights)

1. Frozen production/native15 baseline (`combined_score`)
2. Frozen PR #5 0.5-neutral
3. Frozen Scoring v2 + previous listing fingerprint
4. Frozen Scoring v2 + Hybrid v1 scoring-ready frames (**official new ranking**)

---

## 116978058 (GT stand 365, applied after freeze)

| variant | 365 rank | 365 score | #1 | gap #1–#2 | 365 vs #1 | confidence |
|---|---:|---:|---|---:|---:|---|
| Baseline | **17** | 0.666 | 611 REJECTED 0.781 | 0.033 | −0.115 | LOW |
| PR #5 0.5-neutral | **2** | 0.781 | 404 0.782 | 0.0006 | −0.001 | LOW |
| PR #6 previous fingerprint | **3** | 0.758 | 583 0.764 | 0.005 | −0.007 | LOW |
| PR #7 multi-image | **9** | 0.670 | 457 0.736 | 0.023 | −0.066 | LOW |
| **Hybrid v2** | **4** | 0.704 | 351 0.735 | 0.028 | −0.030 | **LOW** |

Hybrid Top 5 (all CONFIRMED): **351, 463, 380, 365, 461**. REJECTED/UNKNOWN in Top 20: **0** (baseline 13).

Movement of known genuine-pool rivals:

| stand | PR #6 | Hybrid | note |
|---|---:|---:|---|
| 365 | 3 | **4** | shape_v2 0.730 → **0.777**; spatial_v2 0.818 → **null** |
| 583 | 1 | **33** | no longer outranks 365 |
| 428 | 2 | **15** | still a genuine pool; below 365 |
| 351 | 25 | **1** | elongated OS pool; highest Hybrid shape_v2 (0.822) |
| 611 | 99 | 101 | OS REJECTED stays suppressed |

Diagnostic: using the **secondary spa** as the listing contour drops 365 to **#14**. Keeping the 008 main-pool contour (spa secondary, not merged) is better than promoting the spa. It does **not** beat PR #6, which still had listing pool–house spatial from the old colour-blob fingerprint.

Cleaner 008 geometry improved `shape_v2` on 365, but PCA-normalised elongated contours also fit other genuine elongated nadir pools. Separation vs PR #6 #1–#2 gap improved (0.005 → 0.028) and is still **below** the 0.04 LOW CONFIDENCE threshold. 365’s gap to #1 **worsened**.

## 116273255 (no independent GT)

Do **not** invent a stand number. Definitive rank accuracy **cannot** be measured.

Hybrid Top 5: **1/334** 0.710 PROBABLE, **1/373** 0.702 CONFIRMED, **1/691** 0.677 CONFIRMED, **1/389** 0.664 PROBABLE, **1/450** 0.661 PROBABLE. Gap #1–#2 = **0.008 → LOW CONFIDENCE**.

Baseline Top 5 is OS **REJECTED/UNKNOWN** ~500 m² stands (stand-size + blob). Hybrid Top 20: **0** REJECTED/UNKNOWN (14 CONFIRMED / 6 PROBABLE). Blob/OS false positives are suppressed from the shortlist.

Visual: 038 listing contour is concave/boomerang. 1/373 and 1/691 share a similar nadir indent; 1/334 is a stiffer triangle. OS v1 still sometimes confirms a non-pool object while a nearby rectangular pool is unmasked — that is an OS candidate-geometry limit, not a Hybrid listing failure.

Frame diagnostics (same weights): 037 and 038 produce almost the same Top 5; 008 (steps/deck view) shifts #1 to 1/484. Rectilinear/concave listing geometry is in the descriptors, but it does **not** produce a separated ranking. No L-shaped scoring rule was added. Stand size (~500 m² listing vs EXT.6 1/xxx parcels) still pulls the shortlist.

## A–K

**A. 116978058 baseline → Hybrid rank**  
Stand 365: **#17 → #4**. Versus PR #5 #2 and PR #6 #3 this is a **drop**. Versus PR #7 #9 it is an improvement.

**B. 116978058 confidence and separation**  
Still **LOW CONFIDENCE**. #1–#2 gap 0.028 (better than PR #6 0.005, worse than the 0.04 bar). 365 is 0.030 below #1 (351). Near-tie among genuine pools, not a unique ID.

**C. 116273255 Top 5**  
1/334, 1/373, 1/691, 1/389, 1/450. All high-conf OS pools. No GT.

**D. 116273255 confidence**  
**LOW CONFIDENCE** (gap 0.008). Baseline’s moderate gap was OS-REJECTED blob/size, not a real ID.

**E. Did rectilinear/concave geometry materially affect ranking?**  
Partially in descriptors (038 `n_major_indents=1`, max_indent 0.165). 037 vs 038 diagnostics do not change the Top 5 in a material way. Not enough to separate similar genuine pools.

**F. Did secondary-component handling help?**  
On 116978058, yes versus promoting the spa (#4 vs diagnostic #14). It does not restore PR #6 spatial. No listing-specific jacuzzi rule.

**G. Were blob/OS false positives suppressed?**  
Yes. 116978058 Hybrid Top 20: 0 REJECTED (baseline 13). 116273255 Hybrid Top 20: 0 REJECTED (baseline 16). 611 stays buried.

**H. Did any new scoring artefact appear?**  
1. Missing listing spatial → all high-conf pools get `spatial_v2 = 0.5`; PR #6’s pool–house discrimination disappears.  
2. 500 m² listing stand-size still clusters EXT.6 1/xxx parcels.  
3. PCA shape matching promotes other elongated/concave OS pools (351; 1/334).  
4. CLIP aerial/exterior remain 0.5 when the candidate was outside the frozen blob shortlist.  
No colour term. No listing-specific rule.

**I. Overall verdict: MIXED**  
116978058 improves vs baseline and suppresses FPs, but does not beat PR #6 and remains LOW CONFIDENCE. 116273255 shortlist quality improves (FPs out) but rank accuracy cannot be measured. The success gate required genuine improvement on **both** listings with better separation, not merely rank.

**J. Bottleneck**  
**Both, with viewpoint-invariant comparison first.** Hybrid listing contours are usable; Scoring v2 cannot use oblique pool–house or area, so spatial is 0.5-neutral. Among remaining terms, shape_v2 cannot uniquely identify a nadir pool from one oblique contour. Stand-size is a secondary scoring artefact on 116273255.

**K. Recommended next experiment (no production integration)**  
Recover a **viewpoint-compatible pool–house spatial** from Hybrid listing frames using a building/object relation (not colour, not nadir-equivalent area). Re-run this same frozen Scoring v2 comparison. Independently establish 116273255 ground truth before treating rank as accuracy. Do not change Scoring v2 weights yet. Do not integrate Hybrid into production ranking.

Runtime: **20.7 s** after CLIP/OS caches (CPU). AGS downloads: 0.
