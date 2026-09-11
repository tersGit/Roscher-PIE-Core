# Waterfall W3-V V2 distributions and sanity assessment

The full universe contains 1,010 scored W1 properties. Retrieval ranges from
0.003720 to 0.466261, with mean 0.107254. Mean coverage is 0.323743.

| Component | Visibility distribution | Binding distribution | Compatibility distribution |
|---|---|---|---|
| Pool | OBSERVED 161; PARTIAL 4; AMBIGUOUS 845 | IN_PARCEL 156; BOUNDARY_AMBIGUOUS 9; OUTSIDE_PARCEL 845 | MATCH 161; PARTIAL 4; UNKNOWN 845 |
| Building | OBSERVED 995; AMBIGUOUS 15 | IN_PARCEL 993; BOUNDARY_AMBIGUOUS 2; OUTSIDE_PARCEL 15 | MATCH 995; UNKNOWN 15 |
| Pool-house relation | OBSERVED 162; AMBIGUOUS 848 | IN_PARCEL 162; UNBOUND 848 | MATCH 162; UNKNOWN 848 |
| Driveway | PARTIAL 276; AMBIGUOUS 734 | IN_PARCEL 259; BOUNDARY_AMBIGUOUS 17; OUTSIDE_PARCEL 734 | PARTIAL 276; UNKNOWN 734 |
| Open space | OBSERVED 1,010 | IN_PARCEL 1,010 | MATCH 1,008; PARTIAL 2 |
| Parcel geometry | OBSERVED 995; AMBIGUOUS 15 | IN_PARCEL 995; UNBOUND 15 | MATCH 995; UNKNOWN 15 |

## Candidate-level sanity

- 972 candidates (96.24%) contain one or more `UNKNOWN` component. This is
  materially represented, as required, and is retained rather than converted
  to a conflict.
- No candidate has a direct visible compatibility conflict. Therefore 0% of
  candidates is a hard conflict, well below the 90% stop threshold.
- `OUTSIDE_PARCEL` pool and driveway detections are deliberately unbound and
  score no support. This confirms that neighboring objects did not become
  candidate-owned evidence.
- The pool-house relation is `UNKNOWN` unless both objects are visibly
  parcel-bound. It is not inferred from a missing pool detector.

The preregistered sanity rules pass. The full output may be frozen and used to
derive the independent top 30 exactly once.
