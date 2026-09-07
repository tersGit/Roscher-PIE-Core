# Phase G4H: Human ground-truth review package

**Prepared and stopped.** This package contains exactly the 48 G3
presence-transition cases: 46 `ABSENT -> PRESENT` and two
`PRESENT -> ABSENT`. It excludes all 64 geometry-only material cases.

`first_pass_panels/` contains 48 full-resolution neutral `IMAGE A` /
`IMAGE B` panels with a parcel boundary. The inputs are the committed G3
padded parcel crops, which provide the only surrounding context retained by
G3. G3 did not commit the original 450 m raw responses, so broader aerial
context was not recreated, fetched, or substituted. `contact_sheets/`
contains five compact sheets with 8-10 cases each.

The review form is intentionally blank. Reviewers must answer the exact first
question in `PHASE_G4H_README.md` before opening
`PHASE_G4H_REVEAL.csv`. Historic PIE records listed in
`PHASE_G4H_EXISTING_EVIDENCE.csv` may establish only earlier stored
imagery-derived observations; they are not pre-labeled ground truth and do
not establish equality with current imagery.

No detector, network imagery, ranking, scoring, inventory, gate, candidate,
listing, frozen artifact, or earlier evidence was changed.
