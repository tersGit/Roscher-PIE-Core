# W3-V independent ground-truth recovery evidence

## Scope and blind boundary

This record documents an independent, public-source recovery attempt for MyProperty
listing `2150462`. It was prepared without reading W1 parcel candidates, W3-S
ranking data, the W3-V PIE ranking, Qwen ranking data, model scores, or either
model's candidate set.

**Frozen rank files first accessed:** not yet accessed at the time this
ground-truth artifact was created and frozen.

## Result

| Field | Result |
|---|---|
| Ground-truth stand / extension | UNAVAILABLE |
| Address | UNAVAILABLE (the estate locality is known; no property-specific address was publicly recovered) |
| Area | UNAVAILABLE as a parcel attribute |
| Confidence | UNAVAILABLE |
| Reason | Multiple independent public listing records corroborate the same marketed home, but each withholds a property-specific street address, stand, cadastral reference, coordinate, or parcel map pin. Estate-level addresses cannot identify the listed house. |

No W1 GIS extension-universe lookup was performed: the required independently
supported stand/address candidate was not recovered. Consequently, no CoJ parcel,
property identifier, geometry, or parcel-area value is asserted.

## Public-source captures

Capture date: 2026-09-11. URLs below are exact capture targets.

| Source | Exact URL | Capture / evidence |
|---|---|---|
| Target marketplace | `https://www.myproperty.co.za/en-za/for-sale/house/gauteng/midrand/waterfall-country-estate/5-bedroom/2150462` | Direct capture returned HTTP 429. The URL identifies the target but supplied no recoverable address during this run. |
| Agency duplicate | `https://www.luxlivproperty.com/waterfall-country-estate-house-for-sale-2150462` | Agency page explicitly identifies property ref `2150462`, embeds video `P6UEdM5xy8M`, names Waterfall Country Estate/Midrand, and reports 5 beds, 5.5 baths, 4 garages, 780 m2 floor area, and 1,010 m2 land area. The map iframe queries the estate, not a house address. Agents shown: Marussia van der Merwe, Viktoria Morreno, and Schalk Visser. |
| Independent marketplace duplicate | `https://www.privateproperty.co.za/for-sale/gauteng/johannesburg/midrand/waterfall/waterfall-country-estate/T4199338` | Independently hosted duplicate advert at R17,890,000 with the same narrative and estate-only structured postal locality. It includes a “Request Street Address” control rather than publishing one. |
| Independent marketplace duplicate | `https://www.property24.com/for-sale/waterfall-country-estate/midrand/gauteng/15697/117413007` | Independently hosted duplicate advert: title “Ultra Modern Five Bedroom Home For Sale in Waterfall Country Estate,” 5 bedrooms, 5.5 bathrooms, 780 m2 floor size, R17,890,000, and agent Joelle Mc Master De Freitas / Engel & Volkers MLC. Its JSON-LD address is estate locality only. |
| Syndicated duplicate | `https://www.findmy.co.za/property/details/Unveiling-Serenity-Luxurious-Living-at-Its-Finest-in-Waterfall-Country-Estate/5904` | Independently hosted syndicated record connects the matching title, 5 bedrooms, 780 m2, LuxLiv/Joelle McMaster/Marussia van der Merwe, and video `P6UEdM5xy8M`; its `streetAddress` field contains only “Waterfall Country Estate, Midrand, Gauteng, South Africa.” |
| Video metadata | `https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v=P6UEdM5xy8M&format=json` | YouTube oEmbed identifies the video as “What Does an R18M SBE MASTERPIECE in Waterfall Country Estate Look Like?” by LuxLiv Property Group. The agency and syndicated records independently associate this video with the target marketing record. |

The agency, Private Property, Property24, and FindMy records are substantially
independent publication surfaces for the marketed home. They establish listing
identity and the video linkage, but **not parcel identity**. Repeated estate
locality text is not treated as corroboration of a specific street address.

## Visual cross-check status

No recovered parcel exists to compare against aerial, map, or street-level imagery.
The following labels therefore distinguish target-material facts from parcel-match
claims.

| Feature | Target-material status | Recovered-parcel comparison | Finding |
|---|---|---|---|
| Rectilinear pool relative to house | UNKNOWN | UNKNOWN | The public listing text confirms a 7 m x 3.5 m pool and deck; its plan shape/orientation and a parcel comparison were not established. |
| Patio / deck / lawn | OBSERVED (listing description) | UNKNOWN | The agency duplicate describes an openable/enclosed patio and deck; no parcel is available for confirmation. |
| House massing | UNKNOWN | UNKNOWN | No parcel-level aerial comparison performed. |
| Front glazed entry | UNKNOWN | UNKNOWN | No parcel-level street or aerial comparison performed. |
| Garages / driveway | OBSERVED (listing metadata: four-car garage) | UNKNOWN | Garage count is published; driveway form/location cannot be compared without a parcel. |
| Stone-clad element | UNKNOWN | UNKNOWN | Not independently established from the sources captured. |
| Neighbours / context / parcel open space | UNKNOWN | UNKNOWN | No candidate parcel was recovered. |

## Decision

The evidence supports the existence of one cross-published marketing record and
its video, but does not support a stand, extension, street address, cadastral
parcel, or geometry. Assigning a parcel from estate-level facts, model output, or
ranking candidates would violate the blind recovery requirement. The result is
therefore **UNAVAILABLE**, not a forced MEDIUM or LOW identity claim.
