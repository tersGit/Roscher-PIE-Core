# Waterfall W3 Street View blind protocol

**Status:** FUTURE STAGE ONLY — DO NOT EXECUTE

No Google, Maps, or Street View query has been made for W3. This protocol may start only after all of the following immutable artifacts exist:

1. The listing-media, frame, selection, and visual-observation freeze is committed.
2. The official 1,010-candidate PIE ranking and Top 50/20/10/5 are frozen and hashed.
3. The Qwen2.5-VL-32B-Instruct Q4_K_M Top-10 package is exported and its results, if run, are frozen and hashed.

## Future procedure

1. Copy every frozen W3 artifact to a read-only evidence directory and record SHA256 checksums.
2. Query Street View only for the already-frozen candidate set under a separately authorized protocol.
3. Record source URLs, capture timestamps, panorama dates, screenshot hashes, coverage limitations, and every unavailable result.
4. Treat street-level observations as `OBSERVED`, `INFERRED`, or `UNKNOWN`; do not infer ownership, identity, address, coordinate, compass direction, or parcel membership from a view.
5. Preserve ambiguity and occlusion as `UNKNOWN`. A missing or blocked feature is never a hard `NO`.
6. Write the Street View comparison into a new post-freeze artifact. Never alter W1, listing observations, the official PIE rank, Qwen package, scores, weights, detector outputs, or their hashes.

Ground truth remains out of scope unless separately and explicitly authorized after the blind comparison record is complete.
