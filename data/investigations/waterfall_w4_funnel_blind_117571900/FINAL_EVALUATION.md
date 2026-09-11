# W4 final evaluation

## Protocol status

- Listing-only profile freeze: commit `e2838eb123347c0f75b62cda983a94259ceaf604`;
  profile SHA-256 `5ceea53a2a0f98f4afcf74cf5d3b2c50b50a0e18ce08a15332e6f7cc9ba79dfb`.
- Blind Funnel v1 prediction freeze: commit
  `180b3b8010f863ff87f4f38100b6146ad327e156`; freeze-file SHA-256
  `8051258544ba6eb689fa268fe8ff1dd84f929acdab532211519e13dc0806deae`.
- W1 source universe is exactly 1,010 parcels at
  `e86b156b3f8ac099cd386b9de2b3b2ba609c0635`; W1 GeoJSON SHA-256 is
  `6a375bf542bcff28c6a3ee862f9e0c3c9a5395d0497b4159027c40b75cf7be3a`.
- Funnel implementation is exactly commit
  `0e92a524ce4f9f01b9c1573576376e4de8c747b7`; no production scoring,
  ranking, or detector was modified.

## Listing intelligence

The listing supplied a reliable 1,251 m2 land area and 660 m2 floor area, a
YES pool with long narrow rectilinear geometry beside the rear entertainment
facade, 28 stated solar panels (visual count/configuration unknown), three
stated garages (visual layout partial), landscaped garden, and stated
greenbelt/dam adjacency. It exposed 59 stills and a 854.774-second original
video. The video coarse scan and fine exterior extraction retained 24 diverse
exterior frames.

## Funnel results

| Stage | Count |
| --- | ---: |
| Universe | 1,010 |
| T1 (<=10%) | 428 |
| T2 (>10% through <=20%) | 468 |
| T3 (>20%; recoverable) | 114 |
| NORMAL | 0 |
| T1 initial queue | 428 |
| T2 added | 468 |
| Expensive queue | 896 |
| T3 retained for recovery | 114 |

T2 expansion was triggered only by `high_unknown_pool_observability`: 356 of
428 T1 parcels were `UNKNOWN`. T1 pool states were **72 OBSERVED_POOL, 0
OBSERVED_NO_POOL, and 356 UNKNOWN**. Unknowns were retained, and missing
detection was never converted to pool absence. The documented estimated
reduction in initial expensive work was **11.29%** (114 of 1,010 deferred to
the recoverable T3 path); full-universe recoverability remains 100%.

The retained component sequence was pool geometry, pool-house relation,
building/roof/massing, solar, driveway/garage, open space/garden,
greenbelt/boundary, and legitimate listing exterior. Candidate evidence states
are recorded per row in `FULL_EXPERIMENTAL_SCORES.csv`; all parcel-bound
evidence is separate from identity recovery.

## Top 10 after blind rank freeze

| Rank | Property | Stand / extension | Tier | Final score | Pool state | Coverage | Support / conflict / unknown |
| ---: | ---: | --- | --- | ---: | --- | ---: | --- |
| 1 | 2033329 | 943 / 19 | T1 | 1.0625 | OBSERVED_POOL | 0.714 | 6 / 0 / 2 |
| 2 | 2033232 | 982 / 19 | T2 | 1.0375 | OBSERVED_POOL | 0.714 | 6 / 0 / 2 |
| 3 | 2033278 | 1018 / 19 | T2 | 1.0375 | OBSERVED_POOL | 0.714 | 6 / 0 / 2 |
| 4 | 2033131 | 1058 / 19 | T1 | 1.0800 | OBSERVED_POOL | 0.571 | 5 / 0 / 3 |
| 5 | 2032596 | 858 / 19 | T1 | 1.0800 | OBSERVED_POOL | 0.571 | 5 / 0 / 3 |
| 6 | 2032590 | 854 / 19 | T1 | 1.0800 | OBSERVED_POOL | 0.571 | 5 / 0 / 3 |
| 7 | 2033015 | 1126 / 19 | T1 | 1.0800 | OBSERVED_POOL | 0.571 | 5 / 0 / 3 |
| 8 | 2033369 | 865 / 19 | T1 | 1.0800 | OBSERVED_POOL | 0.571 | 5 / 0 / 3 |
| 9 | 2033010 | 1122 / 19 | T1 | 1.0800 | OBSERVED_POOL | 0.571 | 5 / 0 / 3 |
| 10 | 2032936 | 1133 / 19 | T1 | 1.0800 | OBSERVED_POOL | 0.571 | 5 / 0 / 3 |

`BLIND_TOP10.csv`, `BLIND_TOP30.csv`, and 30 parcel-bound blind proof panels
were generated only after the blind ranking commit. `Qwen32B` was **not used**:
the broad 896-candidate expensive queue is not a naturally serious small set,
and no local Qwen32B host was available. No simulated VLM result was created.

## Ground truth and verdict

**GROUND TRUTH=UNAVAILABLE**

**ACCURACY EVALUATION=UNLABELLED**

No true stand/extension/PIE ID, tier survival, rank comparisons, or
counterfactual accuracy metrics can be reported without a defensible independent
identity source. **VERDICT=UNLABELLED.**
