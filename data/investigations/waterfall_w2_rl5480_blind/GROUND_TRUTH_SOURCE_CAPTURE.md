# Waterfall W2 RL5480 ground-truth source capture

**Capture date:** 2026-09-10  
**Purpose:** Public-source recovery after the blind phase. This document does not use the
frozen PIE candidates, ranks, scores, or VLM outputs to establish identity.

## Sources

| Source | Role | Captured facts | Identity value |
| --- | --- | --- | --- |
| [MyProperty RL5480](https://www.myproperty.co.za/en-za/for-sale/house/gauteng/midrand/waterfall-country-estate/5-bedroom/rl5480) | Target listing URL supplied for W2 | 5-bedroom house in Waterfall Country Estate, Midrand. Direct retrieval returned HTTP 429 at capture time, so no undisclosed address or parcel data was obtained. | Primary target provenance, but not a usable address source at capture time. |
| [Property24 P24-117384122](https://www.property24.com/for-sale/waterfall-country-estate/midrand/gauteng/15697/117384122) | Public duplicate/listing provenance | LWP Properties; R12,800,000; 5 bedrooms; 5 bathrooms; 641 m2 floor area; Waterfall Country Estate, Midrand; describes the green-belt home, pool, three garages, 5kVA inverter, 5,000 L water storage, and Vacuflo system. The structured address says only Waterfall Country Estate, Gauteng, South Africa; the page explicitly requests contacting the agent for the street address. | Strong linkage to the advertised home through matching marketing text and attributes; no parcel identity. |
| [SA Home Traders 117384122](https://www.sahometraders.co.za/5-bedroom-house-for-sale-in-waterfall-country-estate-117384122) | Public duplicate corroboration | Reproduces the same distinctive description: solid-wood/glass-inlay entrance, two braai areas, five en-suite bedrooms, pyjama lounge, study, walk-in linen room, 5kVA inverter, 5,000 L storage, and Vacuflo. | Corroborates the Property24/LWP marketing record, but is a syndicated copy rather than an independent cadastral source. |
| [LWP listing 3341413](https://www.lwp.co.za/results/residential/for-sale/midrand/waterfall-country-estate/house/3341413/) | Originating agent listing URL | Search indexing identifies this as the LWP listing for the R12,800,000, 641 m2 five-bedroom home. Direct text extraction at capture time exposed the site's terms page rather than property details. | Agent-origin provenance; no street or parcel evidence captured. |

## Recovery result

The sources consistently identify the marketed property as a 5-bedroom Waterfall Country
Estate home marketed by LWP Properties and syndicated under Property24 listing
`117384122`. They do **not** disclose a street address, stand/erf, extension, CoJ
`property_id`, cadastral area, coordinates, title reference, or a parcel map. The
Property24 page intentionally withholds the street address.

No frozen PIE output, candidate image, stand number, score, rank, or VLM result was used
to fill any of those missing fields.
