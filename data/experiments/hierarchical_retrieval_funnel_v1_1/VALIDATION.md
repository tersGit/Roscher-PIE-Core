# Hierarchical Retrieval Funnel v1.1 W4 Validation

This frozen counterfactual is a workload regression only. It uses the W4 audit
area distribution tied to the frozen W1 geometry hash recorded in
`w4_counterfactual_validation.json`; it does not fetch imagery, rerank,
perform identity attachment, claim recall or accuracy, or change frozen W4
scores/ranks.

For W4's reliable 1,251 m2 listing area and 1,010-candidate W1 universe:

| Group | Count |
| --- | ---: |
| A: <=5% | 270 |
| B: >5% through <=10%, incremental | 158 |
| C: >10% through <=20%, incremental | 468 |
| D: >20% | 114 |

Thus A+B is 428 and A+B+C is 896. Frozen Funnel v1 immediately queued 896
candidates. v1.1 queues A's 270 immediately, deferring 626 candidates:
**69.866%** less immediate workload than v1. If the evidence assessment
requires B, A+B is 428 and still defers 468 candidates: **52.232%** less than
the frozen v1 workload. All 1,010 candidates remain recoverable.
