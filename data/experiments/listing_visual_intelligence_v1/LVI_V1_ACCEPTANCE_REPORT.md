# LVI v1 acceptance report

## Scope

The extractor ran on all ordinary Property24 media exposed by the two supplied
listing pages: 57 photo frames for `117539389` and 36 photo frames for
`117255083`. One video URL was inventoried for `117255083`; no video frame was
downloaded by the permitted media parser. No identity, GIS, candidate, ranking,
address, or G9H observation was used as an extraction input.

## Ten acceptance criteria

| Criterion | 117539389 | 117255083 | Result |
|---|---|---|---|
| 1. Roof form | Frame labels retain roof-bearing exterior views, but form is UNKNOWN | UNKNOWN | Not established |
| 2. Roof appearance/colour | UNKNOWN | UNKNOWN | Not established |
| 3. Pool geometry beyond presence | Repeated pool cues, no reliable contour | Repeated pool cues, no reliable contour | Not established |
| 4. Pool-to-house relation | UNKNOWN | UNKNOWN | Not established |
| 5. Driveway/garage geometry | UNKNOWN | UNKNOWN | Not established |
| 6. Road/frontage geometry | UNKNOWN | UNKNOWN | Not established |
| 7. Distinctive neighbours | Structures remain UNKNOWN_STRUCTURE | UNKNOWN_STRUCTURE | Not established |
| 8. Exterior evidence from interiors | Interior frames retained, exterior linkage unresolved | Retained, unresolved | Partial |
| 9. Cross-frame fusion | Repeated pool cue relationship only | Repeated pool cue relationship only | Partial |
| 10. Eliminate incompatible aerial candidates | Not enough structured geometry | Not enough structured geometry | No |

## Acceptance result

**FAIL / diagnostic baseline.** LVI v1 proves complete media inventory,
frame-level provenance, multi-label retention, separated text/visual evidence,
and a contradiction-ready schema. The deterministic visual pass does not yet
extract materially useful roof, pool geometry, frontage, garage, or neighbour
fingerprints. This is an honest baseline rather than an identity or ranking
result. The fingerprints are frozen unchanged before the permitted human
comparison.
