# LVI v3 post-freeze G9H evaluation

## Protocol

The blind LVI v3 observation bundle was committed as `be94c9604145f40884bda7ca04d1d4efbdb3fc77` before this document was created and before any G9H substantive record was read. This evaluation reads the locked G9H human review and companion neighbour, road/driveway, and pool audits only after that freeze. It does not modify, regenerate, or reinterpret frozen observations.

## Result

LVI v3 is a **partial acceptance**: it passes the still-media preservation and structured visual-observation requirement, while failing the required full neighbourhood/frontage understanding requirement.

Compared with v2's zero structured roof/pool/garage/garden results, v3 directly recovered:

| Listing | Recovered |
|---|---|
| `117539389` | two-storey facade, dark red-brown tiled low-pitch hip-like roof sections, curvilinear pool family adjacent to rear facade, double garage facade |
| `117255083` | pool-facing single-storey wing and two-storey garage section, light-grey tiled low-pitch hip-like roof sections, rectilinear pool family adjacent to pool-facing facade, mature trees/lawn/separate garden building |

Both pool shape-family and pool-to-house adjacency observations are recovered as direct multi-view observations. They are not substituted for contour curvature, scale-normalized aspect ratio, orientation, or a property-centred coordinate system.

The distinctive neighbouring high-pitched green zinc/metal roof was **not independently recovered**. Road/driveway geometry was visible in the retained listing corpus according to G9H but was not structured by v3, so it is `VISIBLE_BUT_MISSED`, rather than an unsupported claim that it was absent. No conflicting direct observation was issued.

## Video impact

`117255083`'s public Property24-discovered YouTube embed is now recorded, proving that v2's zero keyframes was an acquisition/preservation failure rather than evidence of source-video absence. The embed returned YouTube's `This video is not available` at v3 retrieval time, so no original video, drone footage, keyframes, or temporal relations were available. `117539389` had no discovered embed. Video therefore made no scene-understanding improvement in this run.

## Next architecture

Use source-preserving media acquisition with a retryable archival handoff, then combine a caption-capable VLM, explicit segmentation for roof/pool/driveway/road/neighbour structures, and a property-centred calibrated relationship layer. Require per-field provenance, visibility and `UNKNOWN`; do not join to candidate, GIS, identity, scoring, or ranking workflows.

## Scope confirmation

This evaluation performed no identity, address, erf, GIS, candidate generation, G9 Top5/Top20 inspection, ranking, reranking, scoring change, Native15 candidate comparison, pool-detector, PR27, or production work.
