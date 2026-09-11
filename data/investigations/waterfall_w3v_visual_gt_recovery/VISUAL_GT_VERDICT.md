# W3-V visual ground-truth verdict

## Verdict

**STILL_UNAVAILABLE**

The prescribed independent full-universe search cannot be performed without
the frozen W1 native15 crop corpus. `manifest.w1.json` records 1,010 `READY`
crops and the intended native15 cache provenance, but both recorded local
paths are absent in this worktree and are ignored from Git:

- `data/visual_index/waterfall_country_estate_w1/_imagery_cache_native15/`
- `data/cache/ags_native15/waterfall_country_estate_w1/`

The frozen Git tree for the W1 source commit also contains neither path. Using
freshly requested aerial imagery would violate the requirement to search the
frozen W1 universe, so no retrieval, scoring, shortlist, panels, forensic
review, external confirmation, or identity assertion was made.

## Required artifacts

`FULL_UNIVERSE_SCORES.csv`, `SHORTLIST.csv`, `SHORTLIST_FREEZE.sha256`, and
`proof_panels/` are intentionally absent: creating empty or synthetic versions
would falsely imply that all 1,010 frozen crops were processed.

## Protocol attestation

- The target-only geometry profile was frozen and committed before W1 candidate
  imagery was accessed.
- No W1 crop or parcel imagery was accessed after the profile freeze because
  none was locally available.
- No prior ranking or candidate/prediction artifact was opened.
- No external identity confirmation was attempted.
- Previous ranks were **not** opened after identity freeze; no identity freeze
  occurred.
- Accuracy is **UNLABELLED**, not an evaluation result.
