# W4 listing-only visual profile

**Status:** FROZEN LISTING-ONLY PROFILE  
**Listing:** Property24 117571900  
**Candidate imagery or candidate identities accessed:** No  
**Ground-truth research performed:** No

## Acquisition

- The supplied Property24 URL returned HTTP 200 and its response HTML and headers
  are preserved locally.
- 59 accessible Property24 stills were downloaded with source URL, byte size, and
  SHA-256 recorded in `LISTING_EVIDENCE_MANIFEST.json`.
- One exposed YouTube embed was acquired through the repaired automatic video
  stack. The original MP4 is 854.774 seconds at 3840x2160, 25 fps; its
  acquisition manifest and SHA-256 are retained.
- The video was coarsely scanned across its duration and 24 diverse, non-redundant
  exterior frames were selected. This is below the 30-frame cap and covers
  aerial context, front approach, pool/patio, garden/boundary, rear facade, and
  late aerial views.

## Stated facts

| Feature | Finding | Status |
| --- | --- | --- |
| Land / erf area | 1,251 m2 | OBSERVED (listing structured facts) |
| Floor area | 660 m2 | OBSERVED (listing structured facts) |
| Bedrooms / bathrooms | 4 / 4.5 | OBSERVED (listing structured facts) |
| Garage | 3 garages | OBSERVED (listing structured facts) |
| Pool | Yes; listing describes solar heating and a heat pump | OBSERVED (listing text and media) |
| Solar | 28 solar panels; 15 kW inverter and battery backup stated | OBSERVED (listing text); roof-panel configuration is visually partial |
| Greenbelt / water | Garden directly against greenbelt and dam | OBSERVED (listing text and aerial/video context) |
| Corner / internal | No defensible observation | UNKNOWN |

## Visual intelligence

| Component | Finding | Status |
| --- | --- | --- |
| Pool geometry | Long, narrow rectilinear pool alongside a timber-deck patio; exact dimensions are not defensible | OBSERVED |
| House-pool relation | Pool sits immediately adjacent to the rear/entertainment facade and covered patio | OBSERVED |
| Building / massing | Contemporary two-level rectangular/linear massing with broad glazing and a substantial covered outdoor area | OBSERVED |
| Roof | Predominantly low-pitch/flat dark roof planes; roof detail is partly obscured in ground frames | OBSERVED / PARTIAL |
| Solar visual evidence | Roof-mounted panels appear in aerial footage; exact count/configuration cannot be determined visually | OBSERVED / UNKNOWN |
| Driveway / garage | Front approach and garage-side massing are visible; three garages are stated, but bay layout is not fully visible | PARTIAL |
| Garden / open space | Landscaped garden, mature trees, timber decks, and lawn are visible | OBSERVED |
| Boundary / greenbelt / water | Rear garden has a planted boundary facing open greenbelt/dam context; precise parcel boundary location is not inferred from listing media | OBSERVED / INFERRED |
| Orientation | No compass orientation asserted | UNKNOWN |

## Funnel input declaration

The land area is reliable: `listing_area_m2=1251`, `listing_area_reliable=true`.
Pool expectation is affirmative: `listing_has_pool=true`. These are the only
listing facts used to begin the prescribed Funnel v1 candidate workflow.

## Blindness declaration

This profile contains only information acquired from the supplied listing and
its exposed media. It does not use a street address, cadastral reference,
candidate imagery, prior W2/W3 outputs, duplicate listings, maps, Street View,
reverse-image search, agent knowledge, or ground truth.
