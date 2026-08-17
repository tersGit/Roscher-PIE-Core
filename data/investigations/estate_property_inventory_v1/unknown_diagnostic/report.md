# Estate Property Inventory v1.1 — UNKNOWN diagnostic (read-only)

Does **not** modify `current.jsonl`, OS v1, FastSAM, Scoring v2, Hybrid Pool
Geometry, native15, production ranking, or Listing Pool Gate semantics.
Colour is not used in scoring. No inventory statuses were converted.

**Dataset stop:** `carlswald_north_corrected_001` is **not** the complete
intended Carlswald North / Summerset EXT.3+6+13 search area. UNKNOWN counts
below are for the frozen EXT.6+EXT.13 subset of **330** unique erven only.
Estate boundaries were not silently changed.

## A. Dataset completeness

| Item | Value |
|---|---|
| GIS source | `carlswald_north_corrected_001` |
| Source GIS parcels | **416** Erven |
| Unique stand / property_id in source | **407** / **407** |
| Selection method | CoJ township pull of requested Summerset extensions; GIS pass 1 = Erven, not non-residential, not `RE/`, area &lt; 8000 m² (same as production ranking) |
| Extensions in frozen dataset | SUMMERSET **EXT.6** (280) + **EXT.13** (136) |
| EXT.3 | **Absent.** Live CoJ: PROCLAIMED, 78 erven, ~69 residential pass-1, extent inside gated bbox |
| Requested at dataset build | EXT.**2** (not in CoJ), EXT.6, EXT.13. EXT.3 was never requested |
| Wrong-estate exclusions | CARLSWALD ESTATE* (deprecated incorrect mapping) |
| Pass-1 exclusions | **79** of 416: 47 `RE/` remainders, 31 non-residential, 1 huge remainder (stand 372, 27 924 m²) |
| Duplicates removed | **7** extra GIS rows in EXT.6 (same stand + same property_id). **Zero** cross-township collisions |
| Final unique residential erven | **330** |
| OS v1 fingerprints | **330/330** |
| Native15 | All 330 OS crops exist (`crop_wh` min ≥ 249 px, 0.15 m/px). Estate tile cache is gitignored; this run used live AGS `exportImage` for visual review |

Why 330: 416 source → 337 pass-1 rows → 330 unique `property_id`.

330 is complete for frozen EXT.6+EXT.13. It is **incomplete** for the intended
estate (EXT.3+6+13). Classification-rate claims are not estate-wide.

## B. UNKNOWN distribution (179 / 179)

Primary reason from frozen OS v1 evidence. Secondary flags allowed.

| Primary reason | n | % |
|---|---:|---:|
| OS `REJECTED` | 116 | 64.80% |
| good imagery + no pool candidate (also inadequate building segmentation) | 43 | 24.02% |
| weak / ambiguous pool candidate | 16 | 8.94% |
| `partially_outside_parcel` | 4 | 2.23% |
| inadequate parcel mask | 0 | 0% |
| poor imagery / coverage | 0 | 0% |
| **Total** | **179** | **100%** |

Secondary flags (not additive to 179): neighbour-bleed on the 4
`partially_outside` rows; roof/shadow/vegetation/object confusion folded into
REJECTED subtypes (see E); inadequate building segmentation on all 43
no-candidate rows.

## C. Safe-NO findings

Current v1 NO = `no_pool_candidate` **and** adequate building segmentation
(60 parcels). That rule was **not** changed.

A Stand 677–scale pool is ≈ **41 × 27 px** (6.2 × 4.0 m) at 0.15 m/px.

Of every UNKNOWN (179):

| Question | Result |
|---|---|
| Entire GIS erf bbox visible on a native15 crop? | **179/179** yes (`crop_wh` min ≥ 249 px) |
| Imagery GSD sufficient to see a 677-scale pool if unobstructed? | **179/179** yes |
| Any OS in-parcel pool candidate? | **136** yes (116 REJECTED + 16 weak + 4 partial). **43** OS `no_pool_candidate` |
| UNKNOWN solely because building segmentation failed the v1 NO gate? | **43** |
| Does a failed roof mask prevent seeing a pool elsewhere on the erf? | **No.** A pool does not require a roof. The building gate is not a theory of absence |

Visual review of **all 43** no-candidate AGS crops with GIS boundary:

| Visual class | n | Stands |
|---|---:|---|
| Missed bright in-parcel pool | 9 | 339, 408, 1/437, 1/520, 1/631, 459, 462, 543, 675 |
| Dark possible in-parcel pool | 1 | 448 |
| Canopy / vegetation — cannot certify absence | 2 | 406, 497 |
| No credible in-parcel pool (vacant, construction, or empty yard) | **31** | remaining of the 43 |

**Answer to the main question:** 31 of 179 UNKNOWN erven have complete usable
0.15 m/px imagery and no credible visual evidence of an in-parcel pool. They
are the only *potential* high-confidence NO set.

They are **not** safe to convert with an automated rule. The other 12 of the
43 share the same OS signature (`no_pool_candidate` + poor building) and
include obvious 677-scale pools (339, 408, 1/437, 1/520, 1/631, 459, 462,
543, 675). Stand **408** was previously read as neighbour-only; the GIS
boundary on the AGS crop shows the bright rectangle **inside** the erf.

Failed to detect ≠ evidence of absence. Conservative automated extra NO = **0**.

## D. Safe-YES findings

No UNKNOWN is promoted to YES.

| Class | n | Notes |
|---|---:|---|
| Likely genuine missed pool (no OS candidate) | 9 | listed in C; stay UNKNOWN |
| Dark / teal | 2 | **370** (REJECTED roof blob; real turquoise pool). **448** (dark rectangle, no candidate) |
| Weak / unusual / small candidate | 16 | e.g. 411 CLIP 0.54 backyard rectangle — cover/spa/true pool possible |
| Partially outside (subject pool clipped by GIS) | 4 | 658 CONFIRMED; 633, 1105, 1/334 PROBABLE. Not safe hard-YES |
| Neighbour correctly excluded | several of the 31 | e.g. **1/335**, 1/379, 395, 547 — neighbour pool outside yellow line |
| Obvious false positive / shadow object | REJECTED majority | see E |
| Genuinely ambiguous | 447, 612, 411 | stay UNKNOWN |

Known stands: **677** remains the confirmed YES reference. **370** likely YES
visually, UNKNOWN for the gate. **408** is a missed in-parcel pool, not a
neighbour exclusion. **447 / 570 / 612** stay UNKNOWN.

## E. OS REJECTED findings (132 = 116 primary + 16 weak)

REJECTED is **not** absence. It is “a blob was proposed and refused.”

| Subtype | n |
|---|---:|
| roof / object | 80 |
| low-evidence roof | 18 |
| low-confidence genuine-looking | 16 |
| low-evidence shadow | 6 |
| shadow | 5 |
| road / neighbour context | 4 |
| vegetation | 2 |
| driveway | 1 |

REJECTED mostly protects against false-positive YES (roof/shadow). It also
**hides at least one genuine YES** (Stand 370). Converting REJECTED → NO is
**UNSAFE FOR HARD GATE**. Converting the 16 low-confidence candidates → YES
is **UNSAFE FOR HARD GATE**.

## F. Visual proof-panel paths

Directory: `data/investigations/estate_property_inventory_v1/unknown_diagnostic/stratified_eight/`

| # | Stand | File | Inventory | Diagnostic interpretation |
|---|---|---|---|---|
| 1 | 677 | `677_confirmed_pool_reference.jpg` | YES | likely YES |
| 2 | 392 | `392_likely_safe_no_good_imagery.jpg` | UNKNOWN | likely NO (vacant); remain UNKNOWN for gate |
| 3 | 2/379 | `2_379_unknown_only_poor_building.jpg` | UNKNOWN | likely NO visually; remain UNKNOWN (same OS signature as 339) |
| 4 | 411 | `411_genuine_ambiguous_candidate.jpg` | UNKNOWN | remain UNKNOWN |
| 5 | 370 | `370_dark_teal_potential_pool.jpg` | UNKNOWN | likely YES visually; remain UNKNOWN |
| 6 | 1/335 | `1_335_neighbour_pool_correctly_excluded.jpg` | UNKNOWN | likely NO visually; neighbour pools outside GIS line |
| 7 | 570 | `570_shadow_object_false_candidate.jpg` | UNKNOWN | likely NO visually; REJECTED ≠ absence |
| 8 | 406 | `406_observability_failure.jpg` | UNKNOWN | remain UNKNOWN — canopy could hide a 677-scale pool |

Contact sheets of all 43 no-candidate reviews:
`data/investigations/estate_property_inventory_v1/unknown_diagnostic/safe_no_review/review_sheet_{1-6}.jpg`

Stand 677 native15 source proof (unchanged):
`data/investigations/estate_property_inventory_v1/unknown_diagnostic/ags_raw_proof/677_ags_native15_raw_proof.jpg`

## G. Current vs simulated inventory

Simulation only. `current.jsonl` unchanged.

| | YES | NO | UNKNOWN | (YES+NO)/330 |
|---|---:|---:|---:|---:|
| **Current v1 / conservative v1.1** | 91 | 60 | 179 | **45.76%** |
| Unsafe: drop building gate (43 → NO) | 91 | 103 | 136 | 58.79% |
| Unsafe: convert 31 visual-empty → NO | 91 | 91 | 148 | 55.15% |

Conservative v1.1 **does not add YES or NO**. 80–90% is not safely reachable
with frozen OS v1.

## H. Current vs simulated Pool Gate reduction

| | Start | Removed | YES | UNKNOWN | Survivors | Reduction |
|---|---:|---:|---:|---:|---:|---:|
| PR #15 listing YES | 330 | 60 NO | 91 | 179 | **270** | 18.18% |
| Conservative v1.1 listing YES | 330 | 60 NO | 91 | 179 | **270** | 18.18% |
| Unsafe 43→NO listing YES | 330 | 103 NO | 91 | 136 | 227 | 31.21% |
| Unsafe 31 visual-empty listing YES | 330 | 91 NO | 91 | 148 | 239 | 27.58% |
| PR #15 listing NO | 330 | 91 YES | 0 | 179 | **239** | 27.58% |
| Conservative v1.1 listing NO | 330 | 91 YES | 0 | 179 | **239** | 27.58% |

Recommended: **keep PR #15** (330→270 / 330→239). The 43→NO path would
hard-discard 339, 408, 1/437, 1/520, 1/631, 459, 462, 543 and 675 when a
listing has a pool.

## I. False-exclusion risks

| Proposed rule | Could it mark a genuine pool as NO? | Could it mark a non-pool as YES? | Rank |
|---|---|---|---|
| REJECTED → NO | Yes — 370 | — | **UNSAFE FOR HARD GATE** |
| `no_pool_candidate` → NO (drop building gate) | Yes — 339, 408, 1/437, 1/520, 1/631, 459, 462, 543, 675 | — | **UNSAFE FOR HARD GATE** |
| Visual-empty subset of the 43 → NO | Residual: canopy (406, 497), dark water (448 class), GIS-line error | — | **PROBABLY SAFE BUT NEEDS TESTING** — not automated |
| Current v1 NO (no candidate + adequate building) | Residual OS miss on a well-segmented roof is possible but not observed in the 43 (those misses had *poor* building) | — | **SAFE FOR HARD GATE** (keep) |
| Weak REJECTED → YES | — | Yes — covers/spas/shadow rectangles | **UNSAFE FOR HARD GATE** |
| `partially_outside` → YES | — | Yes — 408-style neighbour if GIS clips the wrong way | **UNSAFE FOR HARD GATE** |
| Current v1 YES (OS CONFIRMED/PROBABLE in-parcel) | — | Inherited OS false-positive risk on the 91 | **SAFE FOR HARD GATE** (keep; do not weaken) |

UNKNOWN remains preferable to a dangerous hard class.

## J. Single recommended next experiment

**Investigate the OS v1 / FastSAM miss mode on the documented
`no_pool_candidate` stands that nevertheless contain a 677-scale in-parcel
pool (339, 408, 1/437, 1/520, 1/631, 459, 462, 543, 675), without changing
the detector, native15, scoring, or the inventory.**

Until that miss class is understood, no UNKNOWN→NO rule is safe for the
Listing Pool Gate. Do not drop the building-quality gate, and do not convert
REJECTED to NO.

EXT.3 remains a separate dataset-completeness fix and should not be mixed
into this recall diagnostic. Do not silently edit `carlswald_north_corrected_001`.
