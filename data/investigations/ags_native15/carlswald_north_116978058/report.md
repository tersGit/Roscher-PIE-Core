# Native 0.15 m/px AGS tile cache A/B — Carlswald North listing 116978058

Isolated variable: AGS tile sampling. Pool-contour algorithm, CLIP, scoring weights, ranking, listing fingerprint, stand-size scoring, and Blue Hills were not changed. Ground truth was not consulted.

## Tile configuration

**Chosen: 210 m × 1400 px = 0.15 m/px (profile `native15`).**

Not 280 m @ 1867 px: that would keep the old geographic grid but request more pixels than `bbox / 0.15` and raise decode memory. 210 m yields `required_pixels = 210 / 0.15 = 1400` exactly, so tiles are native without oversize interpolation. Square 210 m cells stitch on a regular Web Mercator grid. Existing 18 m parcel pad is unchanged.

Caches are versioned and must not mix:

| profile | path | tile | px | m/px |
|---|---|---:|---:|---:|
| `legacy_020` (kept) | `data/cache/ags/carlswald_north_corrected_001/` | 280 m | 1400 | 0.20 |
| `native15` (new) | `data/cache/ags_native15/carlswald_north_corrected_001/` | 210 m | 1400 | 0.15 |

Each native15 tile writes bbox, width, height, effective m/px, and AGS service id in a sidecar JSON plus a cache `manifest.json`. PIE refuses to reuse a 0.20 m/px directory when native15 is requested.

## Cache build — Carlswald North corrected (337 candidates)

| | old 0.20 m/px | new 0.15 m/px |
|---|---:|---:|
| tiles required | 24 | 35 |
| downloaded | 0 | 35 |
| reused | 24 | 0 |
| failures | 0 | 0 |
| fetch runtime | 0 ms | 137257 ms |
| cache size | (existing, not deleted) | 11.24 MB |
| effective m/px | 0.200 | 0.150 |

Parcel crops were regenerated from the new tiles (not upscaled from old JPEGs).

| crop | old 0.20 | new 0.15 |
|---|---|---|
| count | 330 | 330 |
| width mean (min–max) | 397.1 (168–638) | 515.8 (249–766) |
| height mean (min–max) | 392.5 (196–609) | 506.4 (265–791) |
| mean pixel area | 155778 | 261383 |

337 GIS candidates collapse to 330 crop files because 7 stand numbers occur in both SUMMERSET EXT.6 and EXT.13 (pre-existing `{stand}_ags_aerial.jpg` collision). Old and new caches share that limit. Not introduced by native15.

## Listing fingerprint (frozen)

Loaded from the previous corrected run (`listing_pool_fingerprint.json`). present=True shape=irregular aspect=1.934 orientation=90.0. Listing-side extraction was not re-tuned.

## Final Top 10 only

**LOW CONFIDENCE — candidates insufficiently separated.**

new gaps: top1–top2=0.0334 top1–top10=0.0994. old gaps: top1–top2=0.0083 top1–top10=0.0734.

| stand | old rank | new rank | old score | new score | pool old/new | pool-house old/new | roof old/new | exterior old/new |
|---|---:|---:|---:|---:|---|---|---|---|
| 611 | 210 | 1 | 0.073 | 0.781 | 0.000/0.856 | —/0.929 | 0.537/0.568 | —/0.682 |
| 457 | 87 | 2 | 0.424 | 0.748 | 0.878/0.884 | 0.076/0.656 | 0.560/0.623 | 0.711/0.690 |
| 585 | 5 | 3 | 0.706 | 0.726 | 0.776/0.780 | 0.900/0.912 | 0.520/0.577 | —/— |
| 587 | 48 | 4 | 0.589 | 0.706 | 0.800/0.782 | 0.471/0.895 | 0.452/0.539 | —/— |
| 638 | 236 | 5 | 0.068 | 0.698 | 0.000/0.783 | —/0.732 | 0.555/0.581 | —/— |
| 538 | 178 | 6 | 0.086 | 0.694 | 0.000/0.836 | —/0.384 | 0.669/0.711 | —/0.675 |
| 643 | 224 | 7 | 0.070 | 0.693 | 0.000/0.842 | —/0.498 | 0.514/0.598 | —/0.742 |
| 491 | 9 | 8 | 0.689 | 0.691 | 0.854/0.820 | 0.459/0.530 | 0.587/0.590 | 0.715/— |
| 404 | 73 | 9 | 0.517 | 0.686 | 0.573/0.790 | 0.320/0.721 | 0.532/0.489 | —/— |
| 358 | 35 | 10 | 0.609 | 0.682 | 0.811/0.870 | 0.384/0.539 | 0.452/0.480 | —/0.738 |
| 677 | 1 | 116 | 0.757 | 0.406 | 0.838/0.788 | 0.887/0.182 | 0.522/0.549 | 0.744/— |
| 612 | 2 | 57 | 0.749 | 0.594 | 0.822/0.816 | 0.872/0.264 | 0.548/0.515 | —/— |
| 570 | 3 | 244 | 0.749 | 0.070 | 0.778/0.000 | 0.867/— | 0.685/0.598 | —/— |
| 420 | 4 | 114 | 0.730 | 0.412 | 0.838/0.836 | 0.770/0.030 | 0.522/0.588 | 0.672/0.710 |
| 447 | 6 | 41 | 0.703 | 0.619 | 0.859/0.811 | 0.566/0.287 | 0.571/0.582 | 0.735/— |
| 365 | 7 | 17 | 0.698 | 0.666 | 0.879/0.589 | 0.397/0.716 | 0.634/0.669 | 0.728/— |
| 517 | 8 | 276 | 0.697 | 0.061 | 0.748/0.000 | 0.785/— | 0.530/0.426 | —/— |
| 370 | 10 | 250 | 0.684 | 0.067 | 0.862/0.000 | 0.615/— | 0.452/0.497 | 0.737/— |

Entering Top 10: ['611', '457', '587', '638', '538', '643', '404', '358']
Leaving Top 10: ['677', '612', '570', '420', '447', '365', '517', '370']

Same-session old ranking reproduced the published 0.20 m/px Top 10 (677 first, score 0.7575). Native15 ranking is a different set: eight of ten stands change. That is mostly pool-detector flips (several former Top-10 pools become `present=False` or lock onto shadow/driveway; several former non-pools become high-scoring blobs), not a tighter identification of one property.

## Confound: tile grid vs sampling

This A/B changes **two** things at once:
1. sampling 0.20 → 0.15 m/px (intended)
2. geographic tile size 280 m → 210 m (native15 grid)

Smaller tiles change which tile `covering_tile` returns, so some parcel crops are a different window, not only a sharper copy of the same pixels (see 408: 392×427 → 318×569; 570: 301×358 → 628×547). 280 m @ 1867 px would have kept the old grid; 210 m @ 1400 px was still chosen because it hits native exactly without oversize requests. Crop-boundary overlap is a follow-up, not part of this freeze.

## Detail stands — extraction old vs new

Pool-contour algorithm unchanged. Differences below are from imagery only.

### Stand 677

- Crop: [453, 430] @ 0.20 m/px → [605, 402] @ 0.15 m/px
- Pool present: True → True; shape irregular → irregular
- rectangularity 0.5745 → 0.4329; compactness 0.2646 → 0.3347; convexity 0.7083 → 0.6422; curved 2 → 1; orientation 122.01 → 142.91
- roof area_frac 0.04743056625083423 → 0.04425599276345545; roof orient 123.69007110595703 → 138.7213134765625; paved_frac 0.20053390831151496 → 0.1921384811479791
- panel: `data/investigations/ags_native15/carlswald_north_116978058/ab_stand_677.jpg`

### Stand 612

- Crop: [331, 364] @ 0.20 m/px → [594, 579] @ 0.15 m/px
- Pool present: True → True; shape irregular → irregular
- rectangularity 0.5675 → 0.4087; compactness 0.4544 → 0.177; convexity 0.755 → 0.5582; curved 2 → 2; orientation 126.25 → 114.78
- roof area_frac 0.061987483815278376 → 0.041158563179288565; roof orient 119.05460357666016 → 127.87498474121094; paved_frac 0.20645064904883637 → 0.2090885830091357
- panel: `data/investigations/ags_native15/carlswald_north_116978058/ab_stand_612.jpg`

### Stand 570

- Crop: [301, 358] @ 0.20 m/px → [628, 547] @ 0.15 m/px
- Pool present: True → False; shape irregular → unknown
- rectangularity 0.5614 → None; compactness 0.4477 → None; convexity 0.7622 → None; curved 1 → 0; orientation 157.07 → None
- roof area_frac 0.10359323669704337 → 0.07569807519882625; roof orient 116.5650520324707 → 117.18111038208008; paved_frac 0.16331966072124576 → 0.1560334889786793
- panel: `data/investigations/ags_native15/carlswald_north_116978058/ab_stand_570.jpg`

### Stand 420

- Crop: [320, 232] @ 0.20 m/px → [536, 571] @ 0.15 m/px
- Pool present: True → True; shape irregular → irregular
- rectangularity 0.5686 → 0.5226; compactness 0.5126 → 0.3725; convexity 0.7665 → 0.6441; curved 2 → 3; orientation 90.0 → 121.76
- roof area_frac 0.029640355603448274 → 0.044272943513605355; roof orient 100.4914779663086 → 127.00647735595703; paved_frac 0.10278825431034483 → 0.13981754972946128
- panel: `data/investigations/ags_native15/carlswald_north_116978058/ab_stand_420.jpg`

### Stand 585

- Crop: [472, 418] @ 0.20 m/px → [631, 558] @ 0.15 m/px
- Pool present: True → True; shape irregular → irregular
- rectangularity 0.3902 → 0.3609; compactness 0.2418 → 0.2228; convexity 0.5952 → 0.5726; curved 2 → 2; orientation 123.69 → 122.98
- roof area_frac 0.0450693374422188 → 0.0681372799618288; roof orient 109.23067474365234 → 109.52711486816406; paved_frac 0.19215797583326574 → 0.1859794716243773
- panel: `data/investigations/ags_native15/carlswald_north_116978058/ab_stand_585.jpg`

### Stand 408

- Crop: [392, 427] @ 0.20 m/px → [318, 569] @ 0.15 m/px
- Pool present: True → True; shape irregular → irregular
- rectangularity 0.5734 → 0.4975; compactness 0.4343 → 0.3498; convexity 0.7602 → 0.7035; curved 1 → 2; orientation 90.0 → 145.01
- roof area_frac 0.024473665344357885 → 0.04275403167865946; roof orient 108.43495178222656 → 106.50436401367188; paved_frac 0.17039263011996367 → 0.19519514540571012
- panel: `data/investigations/ags_native15/carlswald_north_116978058/ab_stand_408.jpg`

### Stand 365

- Crop: [330, 440] @ 0.20 m/px → [529, 371] @ 0.15 m/px
- Pool present: True → True; shape irregular → kidney_or_curved
- rectangularity 0.548 → 0.6705; compactness 0.4158 → 0.5357; convexity 0.756 → 0.8916; curved 1 → 2; orientation 102.99 → 135.0
- roof area_frac 0.028798209366391183 → 0.038823697257195845; roof orient 162.89727210998535 → 164.6044511795044; paved_frac 0.18360192837465564 → 0.1644816288679755
- panel: `data/investigations/ags_native15/carlswald_north_116978058/ab_stand_365.jpg`

### Stand 491

- Crop: [483, 367] @ 0.20 m/px → [644, 455] @ 0.15 m/px
- Pool present: True → True; shape irregular → irregular
- rectangularity 0.5175 → 0.4689; compactness 0.3859 → 0.3774; convexity 0.6802 → 0.7013; curved 2 → 2; orientation 109.36 → 107.02
- roof area_frac 0.03349580561996152 → 0.03801788273837963; roof orient 175.01063776016235 → 174.6545548439026; paved_frac 0.13289443250348357 → 0.1411302982731554
- panel: `data/investigations/ags_native15/carlswald_north_116978058/ab_stand_491.jpg`

## Success measurement

A. Pool contour extraction: **MIXED**

Source pool rims and coping are visibly sharper (420 follows the real curve more closely; 570 drops a road-shadow false positive). Under the **frozen** contour extractor the net effect is not a reliable improvement: 677/612/408 lock onto roof, shadow, or driveway; 570 goes pool-present True→False relative to the old (wrong) blob. Mean |Δ rectangularity|=0.089 and |Δ compactness|=0.103 on dual-present stands — the numbers move because the blob often changes, not because the same pool is traced better. Do not retune the pool algorithm from this run.

B. Roof/building extraction: **NO — not material under the frozen roof extractor**

Mean |Δ roof_area_frac|=0.015. Visual roof ridges, solar-panel grids and masses are sharper in the 0.15 m/px crops; the percentile-threshold layout extractor barely moves.

C. Driveway/access extraction: **NO — not material under the frozen paved-fraction extractor**

Mean |Δ paved_frac|=0.014. Paving/lawn boundaries look sharper to the eye; there is still no dedicated driveway model.

D. Candidate separation: **NO**

Still **LOW CONFIDENCE**. top1–top2 0.0083 → 0.0334 and top1–top10 0.0734 → 0.0994, both still under the frozen thresholds (0.04 / 0.10). Rank order is *less* stable (8/10 Top-10 replacements), which is extractor scale-sensitivity, not a cleaner ID.

E. Make 0.15 m/px the permanent PIE AGS acquisition standard? **YES — as the acquisition standard; ranking still needs other work**

0.15 m/px is the native CoJ source. The 0.20 m/px cache discarded real samples. Native15 tiles (210 m @ 1400 px, versioned, local crops) should be the PIE default. This A/B does **not** show that frozen pool/roof extractors get a free accuracy win from sharper pixels; those remain a separate change.

