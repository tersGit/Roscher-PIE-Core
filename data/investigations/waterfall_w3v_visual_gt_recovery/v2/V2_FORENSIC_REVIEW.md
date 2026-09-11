# Waterfall W3-V V2 forensic review

## Review protocol

Review occurred only after commits `e52ea56` (full output freeze) and
`7dccb7b` (top-30 freeze). Each panel is the original frozen W1 crop with the
candidate's W1 parcel boundary in red. No external imagery, property identity
record, address, stand label, historical rank, or production score was opened.

The red boundary is a binding aid rather than a detector result. Features
outside it are explicitly excluded from candidate support. The panels are
listed and integrity-protected by `proof_panels.sha256`.

## Evidence review

| Frozen rank range | Candidates | Visible parcel-bound support | Visible conflict | Unknown / coverage qualification |
|---|---:|---|---|---|
| 1-6 | 6 | Pool, building, relation, driveway, open space, and parcel components scoreable | None directly visible | No unknown component; coverage 0.683300-0.696475 |
| 7-27 | 21 | Pool, building, relation, open space, and parcel components scoreable | None directly visible | Driveway remains `UNKNOWN`; coverage 0.596895-0.650515 |
| 28-29 | 2 | Building, relation, open space, and parcel components scoreable; pool is only partial | None directly visible | Driveway remains `UNKNOWN`; coverage 0.634030-0.641870 |
| 30 | 1 | Pool, building, relation, open space, and parcel components scoreable | None directly visible | Driveway remains `UNKNOWN`; coverage 0.571455 |

The raw panels show dense neighboring development and adjacent pools. This
makes parcel binding material: apparent geometry outside the red outline was
not treated as candidate evidence. No direct geometry contradiction was
recorded merely because a feature was absent, weak, shadowed, or outside the
parcel. In particular, the unknown driveway evidence in 24 shortlist rows
does not become a conflict or a penalty.

## Review conclusion

The frozen shortlist contains multiple visually plausible, parcel-bound
retrieval candidates. Its leading scores are close and aerial evidence is
not capable of establishing a unique identity. The review therefore records
support, coverage, and retained unknowns only; it does not designate a winner.
