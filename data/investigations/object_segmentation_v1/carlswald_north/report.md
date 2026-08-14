# Object segmentation v1 — Carlswald North (native15)

Experimental layer only. Ranking, CLIP listing extraction and frozen blob
extractors are unchanged. Listing 116978058 was not reranked. No ground truth
was used.

Acquisition remains native15 (210 m @ 1400 px = 0.15 m/px). AGS downloads: **0**.

## Phase 1 — model options

| Item | Result |
|---|---|
| Python | 3.12 |
| GPU | none (torch 2.13.0+cpu, 4 cores) |
| Present | OpenCV, NumPy, Pillow, OpenCLIP ViT-B-32, timm, scikit-image |
| Installed for this experiment | `ultralytics` 8.3.253 (no extra OpenCV/SAM2 stack) |
| Weights | FastSAM-s.pt 23 MB in `data/cache/models/` (gitignored) |
| Rejected | SAM2 (heavy, CUDA-oriented) |

Architecture used:

```
FastSAM-s region proposals (+ water / roof seeds)
        → CLIP + geometry + parcel mask
        → pool / building / driveway masks
        → parcel-relative spatial fingerprint
```

Colour is supporting evidence only. Pool acceptance requires CLIP `pool ≥ 0.40`
so roof/shadow/driveway blobs are not promoted.

Expected runtime for 337 parcels: **~5 minutes CPU** (measured 0.83 s/parcel
after warmup; 330 unique native15 crops in 275 s).

## Phase 6 — diagnostic set (native15 only)

Stands: 677, 612, 570, 420, 585, 408, 365, 491, 447, 370.

Panels: `data/investigations/object_segmentation_v1/carlswald_north/panels/`

| Stand | New pool | Area m² | Building m² | Driveway | Old blob pool |
|---|---|---|---|---|---|
| 677 | CONFIRMED | 20.89 | 438 | PROBABLE east | True (wrong blob historically) |
| 612 | REJECTED | — | 936 | UNKNOWN | True (false positive) |
| 570 | REJECTED | — | 955 | PROBABLE east | False (native15 already dropped FP) |
| 420 | CONFIRMED | 37.91 | 502 | PROBABLE west | True |
| 585 | PROBABLE | 31.48 | 980 | PROBABLE north | True |
| 408 | UNKNOWN | — | 134 | UNKNOWN | True (neighbour/shadow FP) |
| 365 | CONFIRMED | 32.47 | 225 | PROBABLE south | True |
| 491 | CONFIRMED | 45.09 | 512 | PROBABLE north | True |
| 447 | REJECTED | — | 395 | PROBABLE south | True (false positive) |
| 370 | REJECTED | — | 531 | PROBABLE west | False |

Visible in-parcel pools on this set: **677, 420, 585, 365, 491, 370**.
No in-parcel pool: **612, 570, 408, 447**.

## Phase 7 — native15 A/B failure checks

| Check | Result |
|---|---|
| Stand 677 — stop selecting roof/shadow/driveway as pool? | **YES** — CONFIRMED on the small rectangular backyard pool (~21 m²) |
| Stand 612 — same test? | **YES** — neighbour kidney pool excluded; in-parcel candidate REJECTED |
| Stand 408 — same test? | **YES** — neighbour pool outside parcel; status UNKNOWN |
| Stand 420 — follow the actual pool curve? | **YES** — CONFIRMED 38 m² kidney/curved mask on the subject pool |
| Stand 570 — keep rejecting the road-shadow false positive? | **YES** — neighbour dark pool excluded; in-parcel candidate REJECTED |

## Phase 8 — quality gate (visual, no ground truth)

POOL: **9/10** correct localisation given whether a pool is visible.
Miss: stand **370** (dark teal pool; CLIP scores it as roof/road, not pool).

BUILDING: **9/10** main-building localisation.
Miss: stand **408** (main footprint only ~134 m², split into 3 masses).
Stand 365 is undersized (~225 m²) but the mask sits on the house.

DRIVEWAY: **8/10** usable access (PROBABLE with a visible paved mask).
Unknown: **612, 408**.

Gate: **PASS** (pool did not fail badly). Estate-wide run was executed.

## Phase 9 — estate-wide

- Unique native15 crops: **330** (337 GIS candidates; 7 stand numbers collide across SUMMERSET EXT.6 / EXT.13 and share one crop file)
- Processed: **330**
- AGS downloads: **0**
- Wall time: **275 s** (mean **0.83 s/parcel**)
- Output: `json/`, `masks/` (pool/building/driveway PNGs), `estate_summary.json`
- Stored separately from frozen fingerprints so this experiment can be rolled back

Estate-wide status counts (330 parcels):

| Layer | CONFIRMED | PROBABLE | REJECTED | UNKNOWN |
|---|---|---|---|---|
| Pool | 78 | 17 | 132 | 103 |
| Building | 266 | 61 | — | 3 |
| Driveway | 1 | 191 | — | 138 |

Old blob extractor `present=True` on 199/330 crops. New layer
CONFIRMED+PROBABLE on 95/330. The drop is mostly rejection of roof/shadow/neighbour
blobs, not a claim that only 95 properties have pools.

## Phase 10 — comparison vs frozen extractors (no rerank)

A. **Pool contour** — **YES, when CLIP confirms.** 677/420/585/365/491 follow water
edges instead of roof/shadow/driveway. Materially more accurate than the HSV blob
on those stands. Dark-water pools (370) are still missed.

B. **House footprint** — **YES, mostly.** FastSAM + roof seeds recover a coherent
main mass on 9/10 diagnostic stands. Better than grey-percentile blobs. 408 is
still fragmented.

C. **Driveway/access** — **YES, as a dedicated layer.** 8/10 diagnostic stands have
a usable paved mask plus entry/side. The old extractor only had `paved_frac`.
UNKNOWN remains neutral.

D. **Pool–house spatial relationship** — **YES, when the pool is CONFIRMED/PROBABLE.**
Parcel-relative centroids and a metre vector exist for 677, 420, 585, 365, 491.
They are empty (correctly) when there is no in-parcel pool. Not available for 370.

## Answers

1. **Pool localisation accuracy?** 9/10 on the diagnostic set (5/6 of visible pools; 370 missed). Estate-wide 95 CONFIRMED+PROBABLE vs 199 old blob positives — stricter, not fully recalled.
2. **Building localisation accuracy?** 9/10 diagnostic. Estate-wide 327/330 CONFIRMED or PROBABLE (quality of those masks not fully reviewed).
3. **Driveway localisation accuracy?** 8/10 diagnostic usable. Estate-wide 192/330 PROBABLE/CONFIRMED.
4. **Are pool contours materially more accurate?** **Yes** on CLIP-confirmed pools (especially 420’s curve and 677’s small rectangle). Not yet for dark teal water.
5. **Is the pool–house spatial relationship materially more reliable?** **Yes** whenever the pool is confirmed — it is no longer a roof-to-blob vector.
6. **Good enough to replace the old blob extractor?** **Not as a drop-in.** Use this layer experimentally. Do not retune ranking until dark-pool recall and 408-style roofs are tighter.
7. **Estimated runtime for 337 properties?** **~5 minutes CPU** at 0.83 s/parcel, **0 AGS downloads** if native15 crops are cached. First parcel pays CLIP/FastSAM load (~4 s).

## What was not done

- No ranking weight changes
- No rerank of listing 116978058
- No ground truth
- No request finer than native15
