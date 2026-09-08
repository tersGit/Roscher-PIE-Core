# Phase G9H freeze verification

## Verified source boundary

G9H was created only after verifying the frozen G9 source commit:

| Item | Verified value |
|---|---|
| Frozen G9 commit | `17e161ab3ce25c81003c2aa510ec5ab8e1ba2b88` |
| Listing 117539389 `freeze.json` SHA-256 | `f9bf7cc020f2bed15aca4eb9cd7db39ff212442e49839fa62520cbe7c8e937ad` |
| Listing 117255083 `freeze.json` SHA-256 | `552798918d47a53ca14adc2745a4abfcdcf3a95bb659e0a986324acbad84313a` |
| `rankings_frozen` | `true` for both listings |
| `ground_truth_applied` | `false` for both listings |
| Candidate count | 332 for both listings |
| Production ranking modified | `false` |
| Colour used in ranking | `false` |
| Stand size used as hard filter | `false` |

The computed SHA-256 values match the committed `freeze.sha256` values.
The frozen G9 verification also records native15 raw evidence as diagnostic,
the historical PR #27 result as `UNKNOWN/not runnable` where exact
compatibility was unavailable, and no identity recovery.

## G9H non-interference attestation

G9H adds only the six human-blind-review records in this directory. It does
not modify G9 input/output evidence, detector code, PR #27, Shape v2,
imagery, production scoring, ranking, thresholds, candidate inventory, or
component freeze. No ground truth, address, erf number, identity, true
stand, or equivalent recovery was performed or recorded.

This attestation and the human observation in
`PHASE_G9H_HUMAN_BLIND_REVIEW.md` are pre-reveal records and must remain
immutable after any later authorized reveal.
