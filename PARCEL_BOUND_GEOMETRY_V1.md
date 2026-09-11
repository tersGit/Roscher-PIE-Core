# PIE Parcel-Bound Geometry Evidence v1

## Scope

`backend/gis/estate_ags_matching/parcel_bound_geometry_v1.py` is an opt-in,
typed evidence representation. It consumes caller-provided parcel, pool, and
building masks. It does not fetch imagery, infer identities, run a detector,
change production scoring, alter Funnel v1.2 lane semantics, or alter Funnel
v1.3 thresholds/gates/rescue rules.

## Admission

For high-confidence v1.3 listing areas, geometry accepts only the ordinary
`+/-10%` universe: A is `<=5%`, B is `>5%` through `<=10%`. Candidates above
10% are unavailable until an actual v1.3 `RescueActivation` includes their
rescue level. Non-high confidence preserves the existing fallback universe.

## Binding preregistration

Binding is measured against the true parcel mask, never the padded crop.
`PARCEL_BOUND` requires at least 98% object-mask coverage inside the parcel.
At most 5% intersection is `OUTSIDE_PARCEL`; intermediate coverage is
`AMBIGUOUS`. Thus an object materially crossing a boundary is not bound merely
because its centroid lies inside. Outside and ambiguous objects cannot become
discriminating evidence.

## Schema and quality

The machine-readable `ParcelBoundGeometryRecord` records source/frame/date/GSD
when known, parcel and mask provenance, observability, binding coverage and
confidence, object confidence, quality, parcel-normalized centroid, area,
ratios, OBB/aspect/orientation, compactness/rectangularity/convexity,
elongation, boundary relation, multiple-water evidence, building complexity,
and pool-building relation. Missing or unsuitable input is represented as
`UNKNOWN`; non-detection never means no pool.

Only `HIGH`, or preregistered `MEDIUM`, parcel-bound records may adapt to v1.2
through `lane_evidence`. Distinctiveness is one rarity component only when the
exact measured signature occurs once in the caller-supplied normal population;
there are no fixed geometry weights. Low/unknown evidence stays recoverable.
