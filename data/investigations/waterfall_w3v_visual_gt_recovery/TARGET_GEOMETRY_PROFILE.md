# Waterfall W3-V target geometry profile

## Freeze declaration

This profile was created before any W1 parcel, crop, overlay, candidate record, or
candidate imagery was inspected for this experiment. It is derived only from the
already-frozen pre-ground-truth W3-V listing/video evidence enumerated below. It
does not infer compass direction from listing imagery.

Source provenance:

- `data/investigations/waterfall_w3v_video_augmented_blind/listing_visual_observations.json`
- `data/investigations/waterfall_w3v_video_augmented_blind/selected_exterior_manifest.json`
- `data/investigations/waterfall_w3v_video_augmented_blind/selected_exterior/01_front_entry_0015s.jpg`
- `data/investigations/waterfall_w3v_video_augmented_blind/selected_exterior/08_rear_house_pool_0450s.jpg`
- `data/investigations/waterfall_w3v_video_augmented_blind/selected_exterior/09_pool_long_side_0480s.jpg`
- `data/investigations/waterfall_w3v_video_augmented_blind/selected_exterior/13_pool_house_context_0600s.jpg`
- `data/investigations/waterfall_w3v_video_augmented_blind/selected_exterior/14_elevated_terrace_context_1095s.jpg`

## OBSERVED

| Feature | Target-only visual observation |
|---|---|
| Pool | A compact, rectilinear in-ground pool with strongly parallel long sides is visible. A complete overhead outline and dimensions are not visible. |
| Pool finish/edge | Pale coping and a warm-toned timber-like deck occur on at least one long pool edge; planted boundary wall at an end/side. |
| House-pool relation | Pool is directly beside the rear living/patio zone, with a narrow lawn/paved strip between/along the pool and house. The pool long axis appears broadly aligned with the rear façade/patio edge in ground imagery. |
| Outdoor space | Small, manicured lawn, hardscape patio, covered patio/seating, folding glass doors, and intentional planting are visible; no broad rear lawn is visible. |
| Building massing | Large contemporary two-storey residence, predominantly flat/parapet roof, rectilinear volumes, tall glazed entry/void, elevated roof-terrace area with glass balustrade. |
| Front | Paved approach, boundary wall, landscaping, stone-clad feature wall, and a garage-side façade are visible. |
| Context | Dense, modern detached-house neighbourhood; high/visible surrounding terrain from an elevated terrace; immediate neighbours have mixed flat and pitched/hip-like roof forms. |

## INFERRED

| Feature | Inference and restriction |
|---|---|
| Pool aerial signature | Likely a small, high-aspect rectangular blue/dark-water or light-coping feature adjacent to a rectilinear building and patio. It may be partially hidden by shadow, roof, vegetation, cover, or image resolution. |
| Candidate layout | Stronger aerial candidates should jointly show a substantial contemporary rectilinear roof mass, a compact near-building rectangular pool, limited rear open turf, and paved/front access context. No one feature is dispositive. |
| Scale | Visual scale suggests a domestic pool rather than a large estate/recreation pool. Exact length, width, parcel size, and building floor area are unknown and must not be treated as measured facts. |
| Roof expression | Flat/parapet surfaces and terrace-like roof geometry may be visible from aerial imagery, but roof material/height and viewing date can obscure this signal. |

## UNKNOWN

- Identity, address, stand number, location, ground truth, and any prior candidate
  or ranking result.
- Compass orientation; no direction is inferred from listing imagery.
- Parcel boundary, street geometry, ownership, land size, driveway extent, and
  garage count.
- Full pool outline, dimensions, exact pool/house spacing, and exact relation to
  a dominant parcel edge.
- Whether the elevated view establishes geographic terrain, direction, or a
  uniquely identifying neighbourhood feature.
- Whether the target remains visually unchanged in W1 imagery.

## Retrieval-use constraints

The search may score pool-like geometry as `YES`, `NO`, or `UNKNOWN`; `NO` is not
an elimination gate. The profile requires conjunction scoring across independent
visible cues, preserves uncertainty, and prohibits identity, rank, filename,
address, compass, or stand-derived features.

Profile state: FROZEN_PENDING_SHA256
