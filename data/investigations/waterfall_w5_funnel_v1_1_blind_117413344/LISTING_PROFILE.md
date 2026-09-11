# W5 listing-only visual profile

**Status:** FROZEN LISTING-ONLY PROFILE  
**Listing:** Property24 117413344  
**Candidate imagery or candidate identities accessed:** No  
**Ground-truth research performed:** No

## Acquisition

- The supplied Property24 URL returned HTTP 200; its complete response HTML and
  response headers are retained with SHA-256 values in
  `LISTING_EVIDENCE_MANIFEST.json`.
- Automatic ingestion found and downloaded all 49 exposed Property24 stills.
  Each source URL, local path, byte count, and SHA-256 is recorded in the
  manifest.
- The response exposed a 49-photo tab and no supported listing-video embed.
  Consequently, no video acquisition or frame extraction was performed.

## Stated facts

| Feature | Finding | Status |
| --- | --- | --- |
| Land / erf area | 1,205 m2 | OBSERVED (listing structured facts) |
| Floor area | 820 m2 | OBSERVED (listing structured facts) |
| Bedrooms / bathrooms | 5 / 5.5 | OBSERVED (listing structured facts) |
| Garage | 3 garages; two direct-access and one golf-cart garage described | OBSERVED (listing structured facts and text) |
| Pool | Pool and heated jacuzzi are both listed and visible | OBSERVED (listing text and stills) |
| Solar / water backup | Solar power and backup water stated | OBSERVED (listing text); roof-panel configuration UNKNOWN |
| Garden | Landscaped garden stated and visible | OBSERVED |
| Corner / external context | No defensible listing-only observation | UNKNOWN |

## Visual intelligence

| Component | Finding | Status |
| --- | --- | --- |
| Pool geometry | Rectilinear turquoise pool with a circular/oval heated-jacuzzi element at one end | OBSERVED |
| House-pool relation | Pool, jacuzzi, lawn, covered patio, and rear/side entertainment façade are immediately adjacent | OBSERVED |
| Building / massing | Large contemporary two-storey white-and-dark-trim rectilinear residence with extensive glazing and a double-volume living space | OBSERVED |
| Roof | Predominantly low-pitch dark tiled roof planes; listing stills do not support a complete roof-layout assertion | OBSERVED / PARTIAL |
| Solar visual evidence | Text states solar power; panel count and roof placement cannot be established from the available stills | UNKNOWN |
| Driveway / garage | Broad paved front court, garage-side elevation, and covered vehicle access are visible; exact bay geometry is PARTIAL | OBSERVED / PARTIAL |
| Garden / open space | Formal lawn, mature planting, and paved/covered entertainment areas are visible | OBSERVED |
| Boundary / context | Fences/walls and immediately adjacent estate houses are visible; no parcel-boundary or external-context inference is made | OBSERVED / UNKNOWN |
| Orientation | No compass orientation asserted | UNKNOWN |

## Funnel input declaration

The land area is reliable: `listing_area_m2=1205`,
`listing_area_reliable=true`. Pool expectation is affirmative:
`listing_has_pool=true`. These are the only listing facts used to begin the
prescribed frozen Funnel v1.1 candidate workflow. Solar, garage, garden, and
context observations are descriptive only and are not added as filters.

## Blindness declaration

This profile contains only information acquired from the supplied listing and
its automatically exposed media. It does not use a street address, cadastral
reference, candidate imagery, candidate identity, prior W2/W3/W4 ranks or
identities, duplicate-listing search, maps, Street View, reverse-image search,
agent knowledge, or ground truth.
