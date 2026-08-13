# CoJ AGS parcel resolution investigation

Investigation only. Matching, CLIP, scoring, segmentation, ranking, and production tile/crop settings were **not** changed.

## Success question

PARTIALLY — PIE is not using full native 15 cm AGS detail. Current 280 m / 1400 px tiles sample at 0.20 m/px (1.33× coarser than 0.15 m/px). Direct AGS requests at native sampling recover extra roof-edge, pool-outline, solar-panel and paving detail. Requests past native (1600–3200 for these bboxes) add interpolation only. Fix: retile the cache at 0.15 m/px. Do not revert to per-parcel live AGS, and do not default parcel exports to 1600+.

## Service metadata

- Service: `AerialPhotography/2023` (2023 ImageServer)
- Native pixel size (EPSG:3857): **0.14999999999963293 × 0.14999999999963257 m** — catalog rasters named `2023_COJ_RGB_15cm_*`
- Advertised maxima: height **4100**, width **15000**. All tested sizes including 2400 and 3200 are within limits; every request returned HTTP 200 `image/jpeg` at the exact requested dimensions.
- Default resampling: `Bilinear`; every request used `RSP_BilinearInterpolation`
- Default JPEG quality: 75
- keyProperties: LowCellSize=0.14999999999963262, HighCellSize=291.6, MaxCellSize=14580
- Pyramid / LOD: no `tileInfo` table on the ImageServer. Catalog identify (EPSG:3857) returns the 15 cm source raster plus mosaic overviews `Ov_i02_L03`…`L06` at LowPS ≈ 3.6, 10.8, 32.4, 97.2 m. Parcel requests in this test are 0.03–0.62 m/px, so they hit the **15 cm dataset**, not those coarse overviews. Source rasters also advertise HighPS up to ~1.2 m (internal pyramid).
- Identify must use `sr=3857` (WGS84 identify returned an error).

## Method

- One fixed bbox per parcel: production padded AABB (polygon + 18 m via `PADDING_METRES/111320`), then centre-expanded to a **square Web Mercator envelope**. AGS `exportImage` with N×N already squares the short axis; locking the square keeps coverage and pixel isotropy identical at every size.
- Same year (2023), CRS (EPSG:3857), interpolation (`RSP_BilinearInterpolation`).
- Sizes requested **directly from AGS** (`f=image`): 256, 400, 800, 1200, 1600, 2400, 3200. Files are raw response bytes, not locally resized copies. A parallel `f=json` call recorded returned width/height/extent.
- Detail tests (not “looks sharper”): Canny edge density, Sobel gradient, connected edge components, uncapped SIFT, ORB, 16×16 spatial occupancy, Laplacian variance, FFT high-frequency energy, SSIM of downsample/upscale pairs (bilinear and cubic).
- Native request size = `bbox_side_m / 0.15`. Finer than 0.15 m/px is flagged `UPSCALED — NO EXPECTED ADDITIONAL SOURCE DETAIL`.
- Current PIE crop: Carlswald Stand 677 uses the **production** tile-cache crop. Blue Hills 34/36 have no production cache in this repo; crops were generated with the **same algorithm** (280 m tiles @ 1400 px ≈ 0.20 m/px, 18 m pad).

## Parcels

- **stand_34** — Blue Hills (BLUE HILLS EXT.8), 5028.0 m², 56 THE PADDOCKS CRESCENT. Square bbox **136.3 m**. Native-matched request **909 px**. Source raster `2023_COJ_RGB_15cm_AO103` LowPS=0.15 HighPS=1.2.
- **stand_36** — Blue Hills (BLUE HILLS EXT.8), 5663.0 m², 44 THE PADDOCKS CRESCENT. Square bbox **159.3 m**. Native-matched request **1062 px**. Source raster `2023_COJ_RGB_15cm_AO103` LowPS=0.15 HighPS=1.2.
- **stand_677** — Carlswald North (SUMMERSET EXT.13), 936.0 m². Square bbox **90.8 m**. Native-matched request **605 px**. Source raster `2023_COJ_RGB_15cm_AP103` LowPS=0.15 HighPS=1.2.

Carlswald North uses **Stand 677** (SUMMERSET EXT.13): clearly visible rectangular pool. Stands 420 and 408 also have pools; 677 is the first preferred listed option.

## Results table

| parcel | requested px | metres/px | file size | keypoints | edge detail | pool usefulness | roof usefulness | driveway usefulness | native detail gained? |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| stand_34 | 256 | 0.5324 | 15603 | 805 | 0.2256 | 1 | 1 | 1 | below native — additional source detail still available |
| stand_34 | 400 | 0.3407 | 30558 | 1820 | 0.1827 | 2 | 2 | 2 | below native — additional source detail still available |
| stand_34 | 800 | 0.1704 | 102112 | 6396 | 0.147 | 3 | 3 | 3 | approaching native — most remaining source detail |
| stand_34 | 1200 | 0.1136 | 180421 | 8930 | 0.086 | 4 | 4 | 4 | just past native — last source samples vs 800; slightly oversampled vs 0.15 |
| stand_34 | 1600 | 0.0852 | 265314 | 8710 | 0.0437 | 4 | 4 | 4 | UPSCALED — NO EXPECTED ADDITIONAL SOURCE DETAIL |
| stand_34 | 2400 | 0.0568 | 457466 | 8746 | 0.0136 | 3 | 4 | 3 | UPSCALED — NO EXPECTED ADDITIONAL SOURCE DETAIL |
| stand_34 | 3200 | 0.0426 | 679356 | 8578 | 0.0055 | 3 | 3 | 3 | UPSCALED — NO EXPECTED ADDITIONAL SOURCE DETAIL |
| stand_36 | 256 | 0.6221 | 14944 | 912 | 0.2288 | 1 | 1 | 1 | below native — additional source detail still available |
| stand_36 | 400 | 0.3982 | 35757 | 2065 | 0.2277 | 2 | 2 | 2 | below native — additional source detail still available |
| stand_36 | 800 | 0.1991 | 123304 | 7721 | 0.1993 | 3 | 3 | 3 | approaching native — most remaining source detail |
| stand_36 | 1200 | 0.1327 | 223124 | 14996 | 0.1434 | 4 | 4 | 4 | at native source resolution (~0.15 m/px) |
| stand_36 | 1600 | 0.0995 | 330603 | 16316 | 0.09 | 4 | 4 | 4 | UPSCALED — NO EXPECTED ADDITIONAL SOURCE DETAIL |
| stand_36 | 2400 | 0.0664 | 570276 | 16366 | 0.033 | 3 | 4 | 3 | UPSCALED — NO EXPECTED ADDITIONAL SOURCE DETAIL |
| stand_36 | 3200 | 0.0498 | 838490 | 16153 | 0.0149 | 3 | 3 | 3 | UPSCALED — NO EXPECTED ADDITIONAL SOURCE DETAIL |
| stand_677 | 256 | 0.3545 | 16358 | 888 | 0.2232 | 1 | 1 | 1 | below native — additional source detail still available |
| stand_677 | 400 | 0.2269 | 36477 | 1907 | 0.195 | 2 | 2 | 2 | below native — additional source detail still available |
| stand_677 | 800 | 0.1135 | 96007 | 5853 | 0.1161 | 4 | 4 | 3 | just past native (native ≈ 605 px) — last source samples vs 400 |
| stand_677 | 1200 | 0.0756 | 165331 | 6066 | 0.0643 | 4 | 4 | 3 | UPSCALED — NO EXPECTED ADDITIONAL SOURCE DETAIL |
| stand_677 | 1600 | 0.0567 | 241834 | 6064 | 0.0362 | 4 | 4 | 3 | UPSCALED — NO EXPECTED ADDITIONAL SOURCE DETAIL |
| stand_677 | 2400 | 0.0378 | 418293 | 5936 | 0.014 | 3 | 4 | 3 | UPSCALED — NO EXPECTED ADDITIONAL SOURCE DETAIL |
| stand_677 | 3200 | 0.0284 | 619792 | 5924 | 0.0067 | 3 | 3 | 3 | UPSCALED — NO EXPECTED ADDITIONAL SOURCE DETAIL |

Usefulness: 0 unusable, 1 barely visible, 2 usable, 3 clear, 4 highly detailed — from 1:1 geographic chips (roof / pool / driveway), not from file size. Edge density is Canny mean and **falls** as images are oversampled (gradients spread); do not treat a lower edge-density number as “less detail” across different output sizes. Keypoints are **uncapped SIFT**. Compare keypoints across sizes using the upscale pairs below, not raw counts.

## Pixel–ground vs native 0.15 m

| parcel | bbox side (m) | native px (side/0.15) | 400 m/px | 800 m/px | 1200 m/px | 1600 m/px | first UPSCALED size |
|---|---:|---:|---:|---:|---:|---:|---|
| stand_34 | 136.3 | 909 | 0.3407 | 0.1704 | 0.1136 | 0.0852 | 1200 |
| stand_36 | 159.3 | 1062 | 0.3982 | 0.1991 | 0.1327 | 0.0995 | 1200 |
| stand_677 | 90.8 | 605 | 0.2269 | 0.1135 | 0.0756 | 0.0567 | 800 |

## Detail vs interpolation

Diagnostic: upsample the lower AGS image to the higher size (bilinear, matching AGS) and compare to the actual higher AGS request. If the higher request is interpolated from the same source pixels, SSIM is very high (~0.97+) and extra SIFT/HF is small. If it contains new source samples, SSIM drops and Laplacian / HF / SIFT rise.

### stand_34

- Native-matched size: **909 px** (136.3 m / 0.15 m).
- Smallest tested size that reaches native: **1200 px**.
- Current PIE crop: 532×681 at **0.200 m/px** (simulated_280m_1400px_pipeline).

- `400_vs_upscaled_256`: SSIM(hi vs bilinear-up lo)=0.8979, SSIM(hi vs cubic-up lo)=0.8977, SSIM(lo vs downsampled hi)=0.9392, SIFT hi/up=1820/1466, Laplacian hi/up=488.3/166.6, HF hi/up=0.4828/0.3618.
- `800_vs_upscaled_400`: SSIM(hi vs bilinear-up lo)=0.8309, SSIM(hi vs cubic-up lo)=0.8392, SSIM(lo vs downsampled hi)=0.9194, SIFT hi/up=6396/2096, Laplacian hi/up=271.5/27.2, HF hi/up=0.4364/0.2064.
- `1200_vs_upscaled_800`: SSIM(hi vs bilinear-up lo)=0.9601, SSIM(hi vs cubic-up lo)=0.9586, SSIM(lo vs downsampled hi)=0.9704, SIFT hi/up=8930/6421, Laplacian hi/up=84.9/45.8, HF hi/up=0.3114/0.2438.
- `1600_vs_upscaled_800`: SSIM(hi vs bilinear-up lo)=0.9560, SSIM(hi vs cubic-up lo)=0.9525, SSIM(lo vs downsampled hi)=0.9704, SIFT hi/up=8710/6133, Laplacian hi/up=38.8/16.3, HF hi/up=0.2458/0.1738.
- `1600_vs_upscaled_1200`: SSIM(hi vs bilinear-up lo)=0.9769, SSIM(hi vs cubic-up lo)=0.9743, SSIM(lo vs downsampled hi)=0.9788, SIFT hi/up=8710/7477, Laplacian hi/up=38.8/23.6, HF hi/up=0.2458/0.1979.
- `2400_vs_upscaled_1600`: SSIM(hi vs bilinear-up lo)=0.9817, SSIM(hi vs cubic-up lo)=0.9797, SSIM(lo vs downsampled hi)=0.9849, SIFT hi/up=8746/7849, Laplacian hi/up=14.1/8.6, HF hi/up=0.2132/0.1725.
- `3200_vs_upscaled_1600`: SSIM(hi vs bilinear-up lo)=0.9815, SSIM(hi vs cubic-up lo)=0.9780, SSIM(lo vs downsampled hi)=0.9847, SIFT hi/up=8578/7771, Laplacian hi/up=7.7/3.8, HF hi/up=0.2079/0.1591.

- Current crop vs AGS overlap at 1200 px (same padded rectangle): SSIM(current vs AGS downsampled to current)=0.7011, SSIM(AGS vs current upscaled)=0.6737, SIFT current/AGS-overlap=3748/6755, Laplacian current/AGS-at-current-size=376.0/249.9.

### stand_36

- Native-matched size: **1062 px** (159.3 m / 0.15 m).
- Smallest tested size that reaches native: **1200 px**.
- Current PIE crop: 596×795 at **0.200 m/px** (simulated_280m_1400px_pipeline).

- `400_vs_upscaled_256`: SSIM(hi vs bilinear-up lo)=0.7942, SSIM(hi vs cubic-up lo)=0.8086, SSIM(lo vs downsampled hi)=0.9156, SIFT hi/up=2065/1319, Laplacian hi/up=982.7/110.9, HF hi/up=0.5343/0.2972.
- `800_vs_upscaled_400`: SSIM(hi vs bilinear-up lo)=0.7857, SSIM(hi vs cubic-up lo)=0.8012, SSIM(lo vs downsampled hi)=0.9130, SIFT hi/up=7721/3292, Laplacian hi/up=616.8/50.3, HF hi/up=0.4930/0.2269.
- `1200_vs_upscaled_800`: SSIM(hi vs bilinear-up lo)=0.9422, SSIM(hi vs cubic-up lo)=0.9426, SSIM(lo vs downsampled hi)=0.9602, SIFT hi/up=14996/10397, Laplacian hi/up=208.4/97.1, HF hi/up=0.3749/0.2854.
- `1600_vs_upscaled_800`: SSIM(hi vs bilinear-up lo)=0.9340, SSIM(hi vs cubic-up lo)=0.9323, SSIM(lo vs downsampled hi)=0.9605, SIFT hi/up=16316/10034, Laplacian hi/up=91.0/33.7, HF hi/up=0.2874/0.1898.
- `1600_vs_upscaled_1200`: SSIM(hi vs bilinear-up lo)=0.9700, SSIM(hi vs cubic-up lo)=0.9680, SSIM(lo vs downsampled hi)=0.9740, SIFT hi/up=16316/13151, Laplacian hi/up=91.0/53.9, HF hi/up=0.2874/0.2294.
- `2400_vs_upscaled_1600`: SSIM(hi vs bilinear-up lo)=0.9771, SSIM(hi vs cubic-up lo)=0.9752, SSIM(lo vs downsampled hi)=0.9825, SIFT hi/up=16366/14102, Laplacian hi/up=30.5/17.6, HF hi/up=0.2187/0.1678.
- `3200_vs_upscaled_1600`: SSIM(hi vs bilinear-up lo)=0.9759, SSIM(hi vs cubic-up lo)=0.9722, SSIM(lo vs downsampled hi)=0.9824, SIFT hi/up=16153/13878, Laplacian hi/up=14.7/6.8, HF hi/up=0.2034/0.1436.

- Current crop vs AGS overlap at 1200 px (same padded rectangle): SSIM(current vs AGS downsampled to current)=0.6995, SSIM(AGS vs current upscaled)=0.6707, SIFT current/AGS-overlap=5939/11544, Laplacian current/AGS-at-current-size=643.5/386.0.

### stand_677

- Native-matched size: **605 px** (90.8 m / 0.15 m).
- Smallest tested size that reaches native: **800 px**.
- Current PIE crop: 453×430 at **0.200 m/px** (production_carlswald_crop).

- `400_vs_upscaled_256`: SSIM(hi vs bilinear-up lo)=0.8327, SSIM(hi vs cubic-up lo)=0.8463, SSIM(lo vs downsampled hi)=0.9341, SIFT hi/up=1907/1630, Laplacian hi/up=1517.1/206.5, HF hi/up=0.5384/0.3307.
- `800_vs_upscaled_400`: SSIM(hi vs bilinear-up lo)=0.9220, SSIM(hi vs cubic-up lo)=0.9180, SSIM(lo vs downsampled hi)=0.9562, SIFT hi/up=5853/3654, Laplacian hi/up=212.6/72.3, HF hi/up=0.3311/0.2274.
- `1200_vs_upscaled_800`: SSIM(hi vs bilinear-up lo)=0.9731, SSIM(hi vs cubic-up lo)=0.9711, SSIM(lo vs downsampled hi)=0.9800, SIFT hi/up=6066/5072, Laplacian hi/up=66.5/37.5, HF hi/up=0.2402/0.1868.
- `1600_vs_upscaled_800`: SSIM(hi vs bilinear-up lo)=0.9709, SSIM(hi vs cubic-up lo)=0.9670, SSIM(lo vs downsampled hi)=0.9801, SIFT hi/up=6064/4966, Laplacian hi/up=30.3/13.3, HF hi/up=0.2119/0.1523.
- `1600_vs_upscaled_1200`: SSIM(hi vs bilinear-up lo)=0.9823, SSIM(hi vs cubic-up lo)=0.9800, SSIM(lo vs downsampled hi)=0.9835, SIFT hi/up=6064/5477, Laplacian hi/up=30.3/19.0, HF hi/up=0.2119/0.1749.
- `2400_vs_upscaled_1600`: SSIM(hi vs bilinear-up lo)=0.9855, SSIM(hi vs cubic-up lo)=0.9837, SSIM(lo vs downsampled hi)=0.9878, SIFT hi/up=5936/5602, Laplacian hi/up=11.3/7.0, HF hi/up=0.1914/0.1612.
- `3200_vs_upscaled_1600`: SSIM(hi vs bilinear-up lo)=0.9856, SSIM(hi vs cubic-up lo)=0.9826, SSIM(lo vs downsampled hi)=0.9878, SIFT hi/up=5924/5665, Laplacian hi/up=6.5/3.2, HF hi/up=0.1922/0.1534.

- Current crop vs AGS overlap at 800 px: SSIM is **not** a fair pixel-alignment metric here (0.14). The production crop is a rectangle cut from an estate-aligned 280 m tile; the AGS overlap is cut from a square envelope of the same pad, so coverage and phase differ. Treat the visual `current_vs_ags` sheet and the SIFT count (2540 → 5081 on the native overlap) as the evidence, not SSIM.

### How to read the numbers

- **400 → 800** is the large genuine-detail step on all three parcels (SSIM of 800 vs upscaled-400 is ~0.79–0.92, not 0.97). Roof ridges, pool coping and solar-panel grids become usable. Laplacian of the current 0.20 m/px crop can exceed Laplacian of native AGS *downsampled* to the same size because the tile crop is aliased; extra SIFT on the native overlap is the detail that was missing.
- **800 → 1200** still adds source samples on Blue Hills (native ~910–1060 px; 800 is 0.17–0.20 m/px). SSIM ~0.94–0.96. Carlswald 677 native is ~605 px, so 800 is already past native (SSIM 1200 vs 800 ~0.97).
- **1200 → 1600 → 2400 → 3200**: SSIM ≥ 0.97 vs bilinear upscale. 1:1 chips look softer, not sharper. This is interpolation plus JPEG. Flag: **UPSCALED — NO EXPECTED ADDITIONAL SOURCE DETAIL**.

## Object-specific notes

### Stand 34 (Blue Hills EXT.8, pool + tiled roof + solar + court)

- Roof: 256 barely a mass; 400 usable outline; 800 ridges/hips and 8 solar panels clear; 1200 tile rows and panel gaps; 1600+ no new geometry.
- Pool: rectangular courtyard pool. Coping and steps become clear at 800–1200. 2400+ softens the rim.
- Driveway: tan paving vs lawn. Boundary usable at 400, brick/paving texture at 1200. Oversized requests do not add joints.

### Stand 36 (Blue Hills EXT.8, light roof, dark pool, long driveway)

- 800 px is **0.199 m/px — the same sampling as the current 280 m / 1400 px tile cache**. 1200 px (0.133 m/px) is the first tested size at/finer than native and is where roof edges, the dark pool rectangle, and a thin utility line become crisp.
- 400→1600 upscale sheet: mow lines / canopy texture exist in AGS 1600 and are absent from upscaled 400 — real source detail, but most of that gain is already present by 1200.

### Stand 677 (Carlswald North / SUMMERSET EXT.13, rectangular pool)

- Production crop is 453×430 @ 0.20 m/px. Direct AGS 400 is 0.227 m/px (slightly worse). Direct AGS 800 is 0.113 m/px (past native 0.15).
- Pool contour, parapet roof edges, parked cars, and neighbour solar-panel grid are materially clearer on native-matched AGS than on the production crop. Individual paving stones still do not resolve — 15 cm imagery cannot provide that.

## Current PIE crop vs direct AGS

**C — Direct per-parcel AGS can retrieve more native detail than the cached tiles, because the tiles are sampled coarser than source. Do not switch to live per-parcel AGS; raise tile sampling to native 0.15 m/px and keep local crops.**

This is not outcome A (tiles do **not** already preserve 15 cm). It is also not a 2–3× collapse: current tiles are 0.20 vs 0.15 m/px (**1.33× coarser linearly, 1.78× fewer samples per m²**). That gap is visible on roof hips, pool coping, solar-panel splits and paving/lawn boundaries. It is the cache that throws detail away, not AGS refusing 15 cm.

Blue Hills 34/36 comparison crops were generated with the production algorithm (no Blue Hills cache in this repo). Carlswald 677 uses the real production crop from `carlswald_north_corrected_001`.

## Recommended acquisition (not applied)

- `recommended_ags_parcel_resolution`: **native-matched (bbox_side_m / 0.15); empirically 800 px for ~90 m envelopes, 1200 px for ~135–160 m envelopes**
- `recommended_metres_per_pixel`: **0.15**

Empirically for these bboxes:

- 256 / 400 px: insufficient for roof/pool/driveway fingerprinting
- 800 px: major improvement; reaches native on ~90 m Carlswald envelopes; still ~0.17–0.20 m/px on larger Blue Hills envelopes
- 1200 px: reaches native on Blue Hills 34/36 envelopes
- 1600 px: little additional source information
- 2400 / 3200: interpolation only (visually softer)

Do **not** default PIE to 1600×1600 parcel exports. That wastes time on oversized JPEG encode (3–6 s vs ~1–2 s at 800–1200) with no extra native samples once `metres/px < 0.15`.

Production `DEFAULT_TILE_METRES=280` / `DEFAULT_PIXELS=1400` were not modified.

## If tile cache is the limit

Do **not** revert to one AGS request per parcel (the 337/786 pattern). Keep a tiled cache at native 0.15 m/px, crop locally with the existing 18 m pad.

Carlswald North padded estate footprint ≈ 1456 × 1070 m.

| tile m | tile px | m/px | tiles | cache MB est. | fetch s est. | native? |
|---:|---:|---:|---:|---:|---:|---|
| 280 | 1400 | 0.200 | 24 | 7.14 | 60.0 | no |
| 280 | 1867 | 0.150 | 24 | 12.7 | 84.8 | yes |
| 210 | 1400 | 0.150 | 42 | 12.49 | 105.0 | yes |
| 150 | 1000 | 0.150 | 80 | 12.14 | 133.6 | yes |
| 120 | 800 | 0.150 | 117 | 11.37 | 149.4 | yes |

Keep tiled cache (do not revert to per-parcel AGS). Use 210 m tiles at 1400 px or 280 m tiles at 1867 px so cache pixels match 0.15 m native. Local 18 m pad crops then inherit native resolution.

**Best tradeoff: 210 m tiles at 1400 px (0.15 m/px).** Same per-tile JPEG class as today, more tiles, native ground sampling, local crops inherit 15 cm. Alternative with fewer tiles: keep 280 m tiles but request **1867 px** (native; larger files, still well under the 4100 height cap).

Expected effect on parcel crops: a ~30 m stand + 18 m pad (~66 m) would go from ~330 px today to ~440 px at native — not a new sensor, but the missing third of linear samples on roof edges and pool rims.

## Comparison sheets

- `data/investigations/ags_resolution/comparisons/stand_34_resolutions.jpg`
- `data/investigations/ags_resolution/comparisons/stand_34_roof_chips.jpg`
- `data/investigations/ags_resolution/comparisons/stand_34_pool_chips.jpg`
- `data/investigations/ags_resolution/comparisons/stand_34_driveway_chips.jpg`
- `data/investigations/ags_resolution/comparisons/stand_34_400_upscale_vs_1600.jpg`
- `data/investigations/ags_resolution/comparisons/stand_34_800_upscale_vs_1200.jpg`
- `data/investigations/ags_resolution/comparisons/stand_34_current_vs_ags.jpg`
- `data/investigations/ags_resolution/comparisons/stand_36_resolutions.jpg`
- `data/investigations/ags_resolution/comparisons/stand_36_roof_chips.jpg`
- `data/investigations/ags_resolution/comparisons/stand_36_pool_chips.jpg`
- `data/investigations/ags_resolution/comparisons/stand_36_driveway_chips.jpg`
- `data/investigations/ags_resolution/comparisons/stand_36_400_upscale_vs_1600.jpg`
- `data/investigations/ags_resolution/comparisons/stand_36_800_upscale_vs_1200.jpg`
- `data/investigations/ags_resolution/comparisons/stand_36_current_vs_ags.jpg`
- `data/investigations/ags_resolution/comparisons/stand_677_resolutions.jpg`
- `data/investigations/ags_resolution/comparisons/stand_677_roof_chips.jpg`
- `data/investigations/ags_resolution/comparisons/stand_677_pool_chips.jpg`
- `data/investigations/ags_resolution/comparisons/stand_677_driveway_chips.jpg`
- `data/investigations/ags_resolution/comparisons/stand_677_400_upscale_vs_1600.jpg`
- `data/investigations/ags_resolution/comparisons/stand_677_800_upscale_vs_1200.jpg`
- `data/investigations/ags_resolution/comparisons/stand_677_current_vs_ags.jpg`

## Request logs

Raw AGS JPEGs and per-request HTTP/bbox/runtime JSON:

- `data/investigations/ags_resolution/stand_34/` — `256.jpg` … `3200.jpg`, `requests.json`, `metrics.json`, `current_pie_crop.jpg`, `current_vs_ags.json`
- `data/investigations/ags_resolution/stand_36/` — same
- `data/investigations/ags_resolution/stand_677/` — same
- `data/investigations/ags_resolution/imageserver_metadata.json`

Reproduce: `python3 scripts/investigate_ags_resolution.py` then `python3 scripts/finalize_ags_resolution_report.py`.
