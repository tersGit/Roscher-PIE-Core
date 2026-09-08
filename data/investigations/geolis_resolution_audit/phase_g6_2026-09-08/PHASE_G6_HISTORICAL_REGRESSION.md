# Phase G6 historical regression check

The historical Pool Object Validation v1 design from PR #27 was reviewed as a design reference only. It was not enabled, modified, or applied as a new detector. Its documented strengths are true-parcel containment, building-overlap agreement for roof vetoes, neighbour protection, and cross-frame object identity.

Committed historical known-pool evidence remains mixed and must not be treated as current live ground truth:

| Known pool | Committed evidence | G6 implication |
|---|---|---|
| 401 | Labelled historical evidence exists outside the 44-case G5 additions | Keep as regression control; no new threshold inferred |
| 338 | PR27 documents a CLIP roof conflict and preserves it as UNKNOWN | Roof score alone is unsafe |
| 408 | PR27 protects it from neighbour contamination but leaves it UNKNOWN | Boundary/mask identity is required |
| 420 | PR27 keeps an irregular/kidney object CONFIRMED | Irregularity must not be hard-rejected |
| 677 | PR27 keeps a genuine pool CONFIRMED | Large/real pools must remain protected |
| 365 | Earlier labelled evidence exists; no independent G6 physical identity was added | No claim beyond committed evidence |

The stored legacy gate status is a diagnostic comparison, not a counterfactual replay. It is `REJECTED` for 10/23 false positives and 5/21 true recoveries; this does not establish that PR27 would reject those native15 additions because the committed additions lack PR27's required live mask/object inputs. A strict defensible reading therefore yields 0/23 FP and 0/21 TP with a determinable PR27 counterfactual, and 23/23 FP plus 21/21 TP unresolved. No recovery-preservation claim is made from absent features.
