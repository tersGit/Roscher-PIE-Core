# Hierarchical Retrieval Funnel V1 Validation

## Method

The isolated module was exercised by `tests/test_retrieval_funnel.py` without
altering frozen ranking artifacts, detector outputs, or production code. The
test fixture is synthetic and verifies policy mechanics only; it is not an
accuracy claim.

## Historical-case eligibility

Historical PIE investigations were inspected after the test implementation.
The available blind listing reports for 116223230, 116273255, 116778622,
116889694, 116978058, and 117170887 explicitly state that independent
parcel-level ground truth is unavailable. 117262832 has a post-freeze true
stand note, but it is target-specific retrospective evidence rather than an
independently-labelled validation case and is not used. Waterfall W3/W3V is
excluded by scope.

Therefore no existing case can fairly report true stand tier, true survival,
true pool state, or a true experimental rank. No historical case was tuned,
rerun, or used as a proxy label.

| Case set | True stand | Tier/universe | Survival/pool state | Frozen versus funnel rank | Reduction |
| --- | --- | --- | --- | --- | --- |
| Non-W3 blind PIE reports | Not independently determinable | Not reportable | Not reportable | Not reportable | Not reportable |

## Regression diagnostic

The deterministic policy test creates a five-candidate universe with three T1,
one T2, and one T3 candidate. Low coverage expands T2, retains T3 for recovery,
and places four of five candidates in the expensive queue: a 20% reduction
before T3 recovery. This is an implementation diagnostic, not empirical runtime
or retrieval efficacy. Runtime is not measured because no live visual stages
are invoked by V1.

Machine-readable results are in
`data/experiments/hierarchical_retrieval_funnel_v1/validation_results.json`.

## Recommendation

**PROMOTE FOR FURTHER BLIND TESTING.** The policy is covered and safely
isolated, but a recommendation to integrate or rank on it would require
prospectively frozen, independently parcel-labelled cases and measured
end-to-end runtime.
