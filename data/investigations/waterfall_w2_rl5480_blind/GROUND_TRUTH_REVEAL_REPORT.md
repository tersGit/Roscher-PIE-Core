# Waterfall W2 RL5480 ground-truth reveal report

**Reveal date:** 2026-09-10
**Scope:** Ground-truth recovery and comparison only. No PIE, VLM, scoring, observation,
or freeze artifact was modified or rerun.

## Identity outcome

| Field | Best-supported result | Confidence | Provenance |
| --- | --- | --- | --- |
| Street address | **Unavailable in public evidence captured.** | LOW | Property24 exposes only "Waterfall Country Estate, Midrand" and explicitly withholds the street address pending agent contact. |
| Erf / stand | **Unavailable.** | LOW | No public source captured connects the listing to a cadastral parcel. |
| Jukskei View extension | **Unavailable.** | LOW | No public source captured an extension value. |
| CoJ `property_id` | **Unavailable.** | LOW | No public CoJ/GIS record was found that can be tied to the listing without first knowing its parcel or address. |
| Cadastral area | **Unavailable.** | LOW | No cadastral area was captured. The 1,035 m2 advertised land size is a marketing attribute, not cadastral proof. |
| Listing identity | LWP's R12,800,000 5-bedroom Waterfall Country Estate home, syndicated as Property24 `117384122` and SA Home Traders `117384122`. | MEDIUM | Matching price, bedroom/bathroom count, 641 m2 floor area, and distinctive full marketing description; source URLs and capture notes are in [GROUND_TRUTH_SOURCE_CAPTURE.md](GROUND_TRUTH_SOURCE_CAPTURE.md). |

The marketing-listing identity is reasonably supported, but the property **is not
parcel-identified**. The duplicate portals are corroborative marketing copies, not
independent cadastral or address evidence. Accordingly, a parcel-level ground truth was
not locked.

## Frozen-result comparison

The frozen W2 universe remains the immutable 1,010-parcel ranking recorded in
`ranking_freeze.json`, with `ranking_full.json` SHA256
`42bad89411f3cfaa2835ea0abbed5140461f4c2e070e497720683ea172c01dd7` and
`ranking_full.csv` SHA256
`766fba8bdf4139aa42df2d244c8c3e52049cbae2498acd2f3d95e4187a7f6940`.

Because no true stand/erf or CoJ property identifier was recovered, no candidate can be
validly selected from the frozen full ranking. Therefore:

| Measure | Result |
| --- | --- |
| Official PIE rank / score | **NOT DETERMINABLE -- parcel ground truth unavailable.** |
| PIE Top 10 / Top 5 / Top 1 | **NOT DETERMINABLE -- parcel ground truth unavailable.** |
| Qwen32B comparison | **NOT EVALUATED BY QWEN32B BLIND TOP10** |

No Qwen post-reveal inference was run.

## Verdict

**PIE: NOT DETERMINABLE -- no parcel-level ground truth, rank, or frozen score can be
assigned.**
**VLM: NOT EVALUATED BY QWEN32B BLIND TOP10.**
**Effect on identification: NOT DETERMINABLE.**
**Dominant reason: public marketing sources withheld the street and supplied no
cadastral/CoJ parcel identifier, preventing an evidence-based join to the frozen
candidate universe.**
