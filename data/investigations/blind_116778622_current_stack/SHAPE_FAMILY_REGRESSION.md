# SHAPE_FAMILY_REGRESSION

Diagnostic A/B only. Frozen rankings were not rewritten. Production weights were not changed.

Listing 116778622-005 Shape Family v1: **KIDNEY_CURVED** (0.53).

Method: reuse each investigation's `hybrid_block.json` listing contour and `all_candidates.json` frozen `score` / `shape_v2`. Classify OS contours with Pool Shape Family v1. Penalty rerank uses `adjusted_total_score` (shape contribution only). Hard-reject drops incompatible families then keeps frozen `score` order.

Ground-truth stand numbers are **report labels only**. They are not scoring inputs.

## Labelled / strong-evidence cases

| Listing | GT stand | old frozen rank | diag rank (penalty) | hard-rejected? | listing family | GT family | compatibility | notes |
| --- | --- | ---: | ---: | --- | --- | --- | --- | --- |
| 115503057 | 401 | 5 | 252 | True | KIDNEY_CURVED | LAP_ELONGATED | incompatible | Stand 401 labelled (rank-5 forensic) |
| 117262832 | 338 | 122 | 31 | True | KIDNEY_CURVED | RECTANGULAR | incompatible | Stand 338 forensic |
| 117170887 | 641 | n/a | n/a | n/a | KIDNEY_CURVED | n/a | n/a | Stand 641 labelled (inventory miss): GT absent from all_candidates |
| 116978058 | — | — | — | — | FREEFORM | — | — | unlabelled 116978058; unlabelled |
| 116889694 | — | — | — | — | None | — | — | unlabelled 116889694; unlabelled |
| 116223230 | — | — | — | — | COMPOUND_IRREGULAR | — | — | unlabelled 116223230; unlabelled |
| 116778622 | — | — | — | — | FREEFORM | — | — | PR #20 complete-estate freeze (same listing, different stack); unlabelled |

## Per-listing notes

### 115503057 — Stand 401 labelled (rank-5 forensic)

- Listing family: `KIDNEY_CURVED` conf=0.55 (high_angle_entropy_low_sharp_fraction)
- Candidates: 367; hard-rejected: 154
- Report-only GT 401: frozen rank **5** → penalty rank **252**; hard-rejected=True; shape_v2=0.7712
- Penalty Top 5:
  - stand 868: old 1 → diag 1 family=KIDNEY_CURVED compat=compatible shape_v2=0.8261
  - stand 444: old 6 → diag 2 family=KIDNEY_CURVED compat=compatible shape_v2=0.8231
  - stand 572: old 13 → diag 3 family=KIDNEY_CURVED compat=compatible shape_v2=0.8209
  - stand 352: old 14 → diag 4 family=UNKNOWN compat=no_decision shape_v2=0.7319
  - stand 456: old 21 → diag 5 family=KIDNEY_CURVED compat=compatible shape_v2=0.6983

### 117262832 — Stand 338 forensic

- Listing family: `KIDNEY_CURVED` conf=0.615 (high_angle_entropy_low_sharp_fraction)
- Candidates: 332; hard-rejected: 154
- Report-only GT 338: frozen rank **122** → penalty rank **31**; hard-rejected=True; shape_v2=None
- Penalty Top 5:
  - stand 467: old 2 → diag 1 family=UNKNOWN compat=no_decision shape_v2=0.7776
  - stand 456: old 5 → diag 2 family=KIDNEY_CURVED compat=compatible shape_v2=0.7687
  - stand 658: old 8 → diag 3 family=UNKNOWN compat=no_decision shape_v2=0.742
  - stand 899: old 17 → diag 4 family=UNKNOWN compat=no_decision shape_v2=0.7188
  - stand 535: old 18 → diag 5 family=UNKNOWN compat=no_decision shape_v2=0.7456

### 117170887 — Stand 641 labelled (inventory miss)

- Listing family: `KIDNEY_CURVED` conf=0.55 (high_angle_entropy_low_sharp_fraction)
- Candidates: 98; hard-rejected: 49
- Report-only GT 641 is **not** in all_candidates.
- Penalty Top 5:
  - stand 868: old 2 → diag 1 family=KIDNEY_CURVED compat=compatible shape_v2=0.8785
  - stand 572: old 4 → diag 2 family=KIDNEY_CURVED compat=compatible shape_v2=0.8188
  - stand 1105: old 19 → diag 3 family=KIDNEY_CURVED compat=compatible shape_v2=0.7711
  - stand 640: old 22 → diag 4 family=UNKNOWN compat=no_decision shape_v2=0.7489
  - stand 545: old 1 → diag 5 family=COMPOUND_IRREGULAR compat=partial shape_v2=0.8763

### 116978058 — unlabelled 116978058

- Listing family: `FREEFORM` conf=0.61 (high_angle_entropy_low_sharp_fraction)
- Candidates: 332; hard-rejected: 158
- Penalty Top 5:
  - stand 365: old 9 → diag 1 family=UNKNOWN compat=no_decision shape_v2=0.8008
  - stand 899: old 13 → diag 2 family=UNKNOWN compat=no_decision shape_v2=0.8087
  - stand 535: old 18 → diag 3 family=UNKNOWN compat=no_decision shape_v2=0.7618
  - stand 658: old 35 → diag 4 family=UNKNOWN compat=no_decision shape_v2=0.7366
  - stand 467: old 37 → diag 5 family=UNKNOWN compat=no_decision shape_v2=0.7501

### 116889694 — unlabelled 116889694

- Listing family: `None` conf=None (None)
- Candidates: 332; hard-rejected: 0
- Penalty Top 5:
  - stand 435: old 1 → diag 1 family=COMPOUND_IRREGULAR compat=no_decision shape_v2=None
  - stand 626: old 2 → diag 2 family=RECTANGULAR compat=no_decision shape_v2=None
  - stand 451: old 3 → diag 3 family=RECTANGULAR compat=no_decision shape_v2=None
  - stand 583: old 4 → diag 4 family=LAP_ELONGATED compat=no_decision shape_v2=None
  - stand 545: old 5 → diag 5 family=COMPOUND_IRREGULAR compat=no_decision shape_v2=None

### 116223230 — unlabelled 116223230

- Listing family: `COMPOUND_IRREGULAR` conf=0.889 (multiple_indents_or_low_solidity)
- Candidates: 332; hard-rejected: 158
- Penalty Top 5:
  - stand 446: old 1 → diag 1 family=COMPOUND_IRREGULAR compat=compatible shape_v2=0.8084
  - stand 582: old 7 → diag 2 family=COMPOUND_IRREGULAR compat=compatible shape_v2=0.7259
  - stand 482: old 12 → diag 3 family=COMPOUND_IRREGULAR compat=compatible shape_v2=0.702
  - stand 678: old 13 → diag 4 family=UNKNOWN compat=no_decision shape_v2=0.7378
  - stand 545: old 14 → diag 5 family=COMPOUND_IRREGULAR compat=compatible shape_v2=0.7155

### 116778622 — PR #20 complete-estate freeze (same listing, different stack)

- Listing family: `FREEFORM` conf=0.53 (high_angle_entropy_low_sharp_fraction)
- Candidates: 332; hard-rejected: 158
- Penalty Top 5:
  - stand 678: old 9 → diag 1 family=UNKNOWN compat=no_decision shape_v2=0.6037
  - stand 340: old 56 → diag 2 family=UNKNOWN compat=no_decision shape_v2=0.4807
  - stand 365: old 63 → diag 3 family=UNKNOWN compat=no_decision shape_v2=0.5315
  - stand 535: old 65 → diag 4 family=UNKNOWN compat=no_decision shape_v2=0.4823
  - stand 639: old 68 → diag 5 family=UNKNOWN compat=no_decision shape_v2=0.4565

## Generalisation bar

The family layer must not be judged by whether 116778622 'looks better' (that listing is unlabelled). The bar is: do not hard-reject known true stands; do not invent listing-specific rules.

**Hard-reject failed that bar on listing 115503057:** labelled stand 401 went 5 → 252 and was marked incompatible (listing KIDNEY_CURVED vs candidate LAP_ELONGATED). Penalty-only also tanks 401. Family v1 is therefore **diagnostic-only**.

Stand 338 (`shape_v2=null`, OS REJECTED) is **out of Shape v2** already; a shape-family gate cannot be blamed for rank 122 and must not be described as fixing that case. Diagnostic A still hard-rejects its REJECTED blob (classified RECTANGULAR vs listing KIDNEY_CURVED) — gating risk on non-scoring contours. Penalty rank 122 → 31 is an artefact: null `shape_v2` is not penalised while incompatible high-shape candidates are.

Stand 641 is missing from OS/inventory; scoring-side family logic cannot surface it.

Listing 116889694 has **no scoring-ready Hybrid frame** (`n_scoring_ready=0`); family is UNKNOWN/None and every candidate is `no_decision`.

