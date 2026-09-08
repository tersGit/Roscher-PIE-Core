# Phase G5 ? Human-grounded Native15 validation

## Verdict and recommendation

**Verdict: NATIVE15 DOES NOT DEMONSTRATE A NET IMPROVEMENT IN THIS 48-CASE TRANSITION SAMPLE.** The completed review resolves 21 of 46 additions as true recoveries and 23 as false positives; 1 is unresolved and 1 is excluded. The two removals are 1 correct removal, 0 true pool lost, 1 unresolved, and 0 excluded. The resolved addition precision is 0.4773, with high-only precision 0.4878.

**Recommendation: do not adopt Native15 or change detector behavior on this evidence; retain it only for further controlled validation with independently grounded cases and no estate-wide performance claim.**

## Scope and method

- Scope is exactly the 48 committed G4H transition cases: 46 `ABSENT->PRESENT` and 2 `PRESENT->ABSENT`; no estate-wide denominator or accuracy claim is made.
- The attached workbook was copied byte-for-byte to the G5 directory before parsing. Raw wording is retained in `human_raw`.
- Normalization is conservative: percentage `YES`/`NO` maps to `POOL`/`NO_POOL`; 100/90/80% is `HIGH`, 60% is `MEDIUM`; `Vacant stand` is retained and mapped to low-confidence `NO_POOL` only as a clearly recorded vacant parcel judgment; `NO ERF` is `EXCLUDE`/invalid parcel; `UNFINISHED HOUSE` is `UNRESOLVED`; blank is `UNRESOLVED`.
- The normalized file was SHA-256 locked before joining reveal data. Joins use committed stand/case records and committed `PHASE_G4H_REVEAL.csv` plus G3 detector classifications.

## Counts and metrics

| Transition | Cases | TRUE / correct | FALSE / lost | UNRESOLVED | EXCLUDED |
|---|---:|---:|---:|---:|---:|
| ABSENT -> PRESENT | 46 | 21 TRUE_RECOVERY | 23 FALSE_POSITIVE | 1 | 1 |
| PRESENT -> ABSENT | 2 | 1 CORRECT_REMOVAL | 0 TRUE_POOL_LOST | 1 | 0 |

Addition precision is **0.4773** among resolved non-excluded additions. High-only precision is **0.4878**; high+medium precision is **0.4884**. These are transition-case metrics only.

## Confusion and error analysis

`PHASE_G5_CONFUSION_MATRIX.csv` reports transition-case-only human-truth/prediction cells, including unresolved and excluded rows. For false-positive and true-pool-lost rows, only committed panels and existing evidence were inspected. No causal detector error type could be established without unsupported imagery or assumptions; all are conservatively classified as `INSUFFICIENT_INDEPENDENT_ERROR_EVIDENCE` in `PHASE_G5_ERROR_ANALYSIS.csv`, with allowed alternatives recorded there rather than guessed.

## Explicit edge cases and limitations

- `Vacant stand` (stand 499) is not silently rewritten; exact raw wording remains available and normalized judgment is low-confidence `NO_POOL`.
- `NO ERF` (stand 692) is `EXCLUDE`, not a negative pool label and not included as a resolved truth claim.
- `UNFINISHED HOUSE` (stand 670) is `UNRESOLVED`, not a guessed pool absence.
- The blank review (stand 1/478) is `UNRESOLVED`.
- Workbook schema places reviewer wording in one ground-truth cell and leaves separate confidence/notes columns blank; embedded percentage is the only confidence signal. Combined wording and limited retained context constrain causal error analysis.
- Historic evidence is not current live imagery ground truth; no network imagery was fetched and the detector was not rerun.

## Evidence and freeze

See `PHASE_G5_FREEZE_VERIFICATION.md` for source hash verification. G5 adds only this directory and preserves prior G3/G4/G4H evidence byte-for-byte.
