# Estate Property Inventory v1 — UNKNOWN diagnostic (read-only)

Does **not** modify `current.jsonl`, OS v1, FastSAM, Scoring v2, Hybrid Pool
Geometry, native15, production ranking, or Listing Pool Gate semantics.
Colour is not used in scoring. No inventory statuses were converted.

**Stop optimisation:** SUMMERSET EXT.3 is a proclaimed CoJ township inside the
Carlswald North gated-community bbox and is absent from the frozen GIS dataset.
Classification-rate conclusions below are for the current EXT.6+EXT.13 subset
only.

## A. Carlswald dataset completeness

| Item | Value |
|---|---|
| GIS source | `carlswald_north_corrected_001` |
| Source parcels | **416** (all Erven) |
| Unique stand / property_id in source | **407** / **407** |
| Townships in frozen dataset | SUMMERSET **EXT.6** (280) + **EXT.13** (136) |
| Requested at dataset build | EXT.**2** (not in CoJ), EXT.6, EXT.13 |
| EXT.3 in frozen dataset | **No** |
| Live CoJ probe EXT.3 | **PROCLAIMED**, 78 erven, ~69 residential pass-1, extent inside gated bbox |
| Gated community extent | 28.089924–28.102245 E, −25.971944–−25.963785 |
| Search extent used | union of EXT.6+EXT.13 parcels (almost the gated bbox) |
| Excluded wrong-estate townships | CARLSWALD ESTATE* (previous incorrect mapping) |
| OS v1 fingerprints | **330/330** pass-1 unique erven |
| Native15 crops on disk this run | diagnostic AGS sample only (19); estate cache still gitignored |
| Inventory rows | **330** |

Excluded from GIS pass 1 (79 of 416): 47 RE/ remainders, 31 non-residential
(6 of those also huge/RE), 1 residential remainder stand 372 at 27 924 m².

Estate boundaries were **not** silently changed.

## B. Why the inventory contains 330 unique erven

Previous “larger” numbers are not a missing-crop bug:

1. **416** = every CoJ Erven in EXT.6+EXT.13, including parks, infrastructure, RE/.
2. **337** = GIS pass 1 (same filter as production ranking): Erven, not
   non-residential, not `RE/`, area &lt; 8000 m².
3. **330** = unique `property_id` after collapsing **7 duplicate GIS rows**
   (same stand + same property_id, all in EXT.6). There are **zero**
   cross-township stand collisions. The OS v1 note that “7 stands collide
   across EXT.6/EXT.13” is incorrect; they are duplicate records in EXT.6.

330 is **complete for the frozen EXT.6+EXT.13 residential/vacant search set**.
It is **incomplete for Carlswald North / Summerset EXT.3+6+13**: EXT.3 exists
and was never requested (EXT.2 was requested instead and does not exist).

Because EXT.3 is missing, UNKNOWN-rate optimisation is **stopped**. The
179/330 analysis below describes the current subset only.

## C. UNKNOWN reason distribution (179)

All 179 have usable native15-sized OS crops (`crop_wh` min ≥ 249 px).

| Primary reason | n | % of UNKNOWN |
|---|---:|---:|
| OS `REJECTED` (not absence) | 116 | 64.8% |
| no pool candidate + inadequate building mask | 43 | 24.0% |
| pool candidate, confidence insufficient | 16 | 8.9% |
| `partially_outside_parcel` / neighbour-bleed | 4 | 2.2% |
| **Total** | **179** | **100%** |

Imagery-quality UNKNOWNs: **0**. Ambiguous-object / other: folded into REJECTED
subtypes.

## D. REJECTED analysis (132 = 116 + 16)

OS notes: 90 `rejected_as_road_shadow_or_roof`, 42 `low_pool_evidence`.

CLIP rival among REJECTED: roof 108, shadow 14, road 5, lawn 3, driveway 2.

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

Known examples (inventory **not** changed):

| Stand | OS | Visual (this diagnostic) | Hard-filter |
|---|---|---|---|
| **370** | REJECTED roof CLIP 0.029 | **Real turquoise in-parcel pool**; OS masked a dark roof rectangle | Must stay UNKNOWN. REJECTED→NO would discard the correct property |
| **447** | REJECTED, CLIP 0.32 | Dark irregular tree-shadow candidate; neighbours have bright pools | UNKNOWN |
| **570** | REJECTED shadow CLIP 0.017 | Driveway/house shadow; no in-parcel pool | Visually empty, but REJECTED cannot become NO (370 class) |
| **612** | REJECTED CLIP 0.25 kidney | Neighbour dark kidney in the crop; in-parcel candidate weak | UNKNOWN (not YES) |
| **408** | no_candidate + poor building | Neighbour bright pool **outside** yellow boundary | Not YES. See §E |

REJECTED is **not** converted to NO.

## E. Safe-NO analysis

Current v1 NO = `no_pool_candidate` **and** adequate building segmentation (60).

Of the 179 UNKNOWN:

- good full-parcel imagery: **179/179**
- no in-parcel OS candidate: **43** (all of these are UNKNOWN *only* because the building mask failed the v1 quality gate)
- UNKNOWN solely because building segmentation was inadequate: **43**

**Building quality should not be the theory of “no pool”.** A pool does not
require a successful roof mask.

**But dropping that gate is unsafe with OS v1.** Stand **339**: bright blue
**in-parcel** pool, OS `no_pool_candidate`, UNKNOWN only because the building
mask is fragmented/undersized (~141 m², 3 masses). Promoting the 43 to NO
would hard-discard 339 when a listing has a pool.

High-confidence NO needs parcel-wide evidence that the detector actually
looked at the water body class and found none — not “FastSAM returned no blob”
and not “roof mask looks OK”. OS v1 does not provide that.

So: **“failed to detect” ≠ “sufficient evidence of absence.”** Keep the 43 as
UNKNOWN.

## F. Safe-YES opportunities

Current YES (91) are OS CONFIRMED/PROBABLE fully in-parcel. Visual control
(Stand 677) matches: CLIP 0.99 on the backyard rectangle.

Possible extra YES (diagnostic only, **not applied**):

- 4 `partially_outside_parcel` (658 CONFIRMED, 633/1105/1/334 PROBABLE). 658 and
  1/334 look like **subject** pools clipped by the GIS line, not neighbour
  theft. Still not safe hard-YES until GIS/mask policy is reviewed.
- 16 “genuine-looking” REJECTED (e.g. 411 CLIP 0.54 on a backyard rectangle).
  Could be covers, spas, or true pools. Not safe hard-YES.

No UNKNOWN is recommended for hard YES in v1.1.

## G. Representative visual findings

Panels: `data/investigations/estate_property_inventory_v1/unknown_diagnostic/panels/`
(19 AGS native15 diagnostic crops; **not** written into the frozen tile cache).

| Stand | Inventory | Visual proposed (diagnostic only) |
|---|---|---|
| 677 | YES | likely YES — gold-standard in-parcel pool |
| 420 | YES | likely YES |
| 1/355 | NO | likely NO — trampoline, neighbour pool outside |
| 370 | UNKNOWN | **likely YES visually**, UNKNOWN for hard filter — detector missed the pool |
| 339 | UNKNOWN | **likely YES visually**, UNKNOWN for hard filter — `no_pool_candidate` miss |
| 411 | UNKNOWN | likely YES visually / genuinely UNKNOWN for gate |
| 658, 1/334 | UNKNOWN | subject pool clipped by GIS — genuinely UNKNOWN for hard YES |
| 408 | UNKNOWN | likely NO visually (neighbour pool outside) — keep UNKNOWN |
| 570, 337 | UNKNOWN | likely NO visually — keep UNKNOWN (REJECTED ≠ absence) |
| 447, 612 | UNKNOWN | genuinely UNKNOWN / neighbour context |

## H. Estimated conservative v1.1 coverage

On the **current 330 only** (EXT.3 still missing):

| | YES | NO | UNKNOWN | (YES+NO)/N |
|---|---:|---:|---:|---:|
| **Current v1** | 91 | 60 | 179 | **45.8%** |
| **Conservative v1.1 (recommended)** | 91 | 60 | 179 | **45.8%** |
| Unsafe upper bound if 43 → NO | 91 | 103 | 136 | 58.8% |

**80–90% is not safely reachable** with frozen OS v1. The 132 REJECTED plus
detector misses (370, 339) dominate UNKNOWN. Safety beats the percentage
target. Do not force classifications.

## I. Pool Gate reduction comparison

Gate semantics unchanged. Simulation only.

| | Start | Removed | YES | NO | UNKNOWN | Survivors | Reduction |
|---|---:|---:|---:|---:|---:|---:|---:|
| PR #15 listing YES | 330 | 60 NO | 91 | 0 | 179 | **270** | 18.18% |
| Conservative v1.1 listing YES | 330 | 60 NO | 91 | 0 | 179 | **270** | 18.18% |
| Unsafe 43→NO listing YES | 330 | 103 NO | 91 | 0 | 136 | 227 | 31.21% |
| PR #15 listing NO | 330 | 91 YES | 0 | 60 | 179 | **239** | 27.58% |
| Conservative v1.1 listing NO | 330 | 91 YES | 0 | 60 | 179 | **239** | 27.58% |

Recommended: **keep PR #15 reductions**. The unsafe 43→NO path would discard
Stand 339.

## J. False-exclusion risks (hard filter)

Ranked:

1. **REJECTED → NO** — Stand 370: real pool, OS rejected a roof blob. Listing-YES
   gate would drop the correct erf. **Unsafe.**
2. **`no_pool_candidate` → NO** — Stand 339: real bright pool, zero OS
   candidate. Building-gate currently saves it. **Unsafe to drop that protection
   as an absence rule; also unsafe to treat no-candidate as absence.**
3. **`partially_outside` → YES** — neighbour-pool YES, then listing-NO gate
   drops a no-pool listing’s true house. 408 shows the neighbour pattern.
   **Unsafe YES.**
4. **OS CONFIRMED false-positive YES** — inherited by the current 91. Lower
   than (1)–(3); do not add weaker YES.

Reliable for hard filter today: **inventory YES** (listing-NO gate) and
**inventory NO** (listing-YES gate) as already defined. Everything else stays
UNKNOWN. UNKNOWN is preferable to a dangerous hard class.

## K. Raw Council GIS imagery proof sample

Stand **677** (inventory YES, OS v1 pool CONFIRMED, CLIP 0.992). House, pool,
driveway and garden are all visible. Source is City of Johannesburg AGS
`AerialPhotography/2023` — not Google/Bing.

Open the labelled panel:

`data/investigations/estate_property_inventory_v1/unknown_diagnostic/ags_raw_proof/677_ags_native15_raw_proof.jpg`

Raw crop (no overlays):

`data/investigations/estate_property_inventory_v1/unknown_diagnostic/ags_raw_proof/677_ags_native15_raw_crop.jpg`

| Item | Value |
|---|---|
| Estate / township | Carlswald North / SUMMERSET EXT.13 |
| Imagery source | `https://ags.joburg.org.za/server/rest/services/AerialPhotography/2023/ImageServer` |
| Imagery date/version | CoJ Aerial Photography 2023 (service has no timeInfo) |
| Native GSD | **0.15 × 0.15 m/px** (`pixelSizeX/Y` on the ImageServer) |
| Cache profile | native15 (210 m tile × 1400 px = 0.15 m/px) |
| Source tile ID | `tile_2023_native15_04_03` |
| Primary mosaic raster | `2023_COJ_RGB_15cm_AP103` (Category=Primary, LowPS=0.15) |
| Resampled? | **No.** Requested GSD equals native 0.15 m/px. AGS still applies `RSP_BilinearInterpolation` / default Bilinear. |
| How the crop was made | Live `exportImage` of that native15 tile, then **integer pixel crop** (`crop_parcel`, JPEG quality 90). Production estate cache is gitignored and was not present in this VM. |
| Crop pixels | **605 × 402** (matches OS v1 `crop_wh`) |
| Approx ground | 90.8 × 70.3 m (erf 936 m² plus 18 m pad) |
| Pool | ≈ 41.2 × 26.6 px (6.18 × 3.99 m); OS area 928.5 px / 20.89 m² |
| House/roof | ≈ 197.1 × 128.8 px (29.56 × 19.32 m); OS area 19 457.5 px / 437.79 m² |
| Driveway | width ≈ 50.5 px (7.57 m) by min-area-rect of the OS paved mask; length ≈ 98.2 px; 1 650.5 px / 37.14 m² |

Panel 1 is the actual analysis pixels at 1:1. No contrast stretch, sharpen, or satellite substitute.

## L. Recommended single next experiment

**Add SUMMERSET EXT.3 to the Carlswald North GIS dataset as an explicit,
reviewed boundary change** (do not silently edit `carlswald_north_corrected_001`
in this diagnostic). Rebuild native15 crops + OS v1 for those ~69 residential
erven, then rebuild the inventory.

Do **not** convert UNKNOWN/REJECTED to NO first. Detector recall — not the
building-quality gate — is the coverage blocker, and EXT.3 means the 330-parcel
UNKNOWN rate is not an estate-wide number.
