# Waterfall W3-V visual retrieval forensic verdict

## Verdict: B — observability / unknown modelling failure

The retrieval output cannot support a candidate-level visual conflict claim.
The dominant source is the state design: `CONFLICT` is the residual path after
a narrow HSV pool component fails the `>=0.46` threshold, while the only
unknown triggers (`shadow > 0.24` or `vegetation > 0.58`) were never reached.
Thus the zero emitted unknowns are an implementation consequence, not evidence
of complete observability.

The permitted W1 source crops add a second, independent observability limit:
they lack a parcel or candidate binding. In the deterministic 32-crop sample,
no directly visible, candidate-bound contradiction could be established;
32/32 cases should be unknown under the audit rule. The audited genuine
conflict rate is **0.0%**; the audited should-be-unknown rate is **100.0%**.
These are audit classification rates, not target-identification accuracy.

## Required findings

| Question | Finding |
|---|---|
| Is `UNKNOWN` reachable? | Yes by strict code condition; no in this frozen universe (0/1,010). |
| Why are there zero unknowns? | Maximum shadow (0.215465) and vegetation (0.340490) never cross thresholds of 0.24 and 0.58. |
| What drives the 1,008 conflicts? | Residual failure to produce an HSV water component with score >=0.46, not a direct visual contradiction. |
| Is the pool contribution weak? | Yes: 992 rows have no retained component, normalized water median is 0, and the 0.30 term is largely unavailable despite its high weight. |
| Are building, driveway, open-space, and parcel claims available? | Building/outdoor/access are only continuous proxies; driveway and parcel states are absent, and parcel has no CSV output. |
| Is house-pool relation informative? | No: normalized relation is 0.5 for every row. |
| Is the shortlist trustworthy for candidate identification? | No. It remains a frozen score ordering, but its visual conflict labels and conjunction claims are not candidate-auditable from the permitted source. |
| Can this method be reused? | Only after separating non-detection from contradiction, emitting component-level unknowns, preserving candidate-to-imagery/parcel binding for audit, and validating that relation and parcel/driveway measures are actually produced. It must not be reused as evidence of a visual match or conflict in its current form. |

## Freeze attestation

Pre- and post-audit SHA256 checks matched:

- target profile: `56aca3c5d9d680a1a69dd19680d885fe38793c45900133f762267332d16d04bc`;
- full-universe scores: `1de39d913051ad054a834cfa7ce0145c94f7cf138c845c1abb8e406f0e376827`;
- shortlist: `d3fb1697aa7f0a292996b040f73cbc39192caac40742e20fafa91a655d17253b`.

No audit artifact changes the frozen retrieval inputs or creates a candidate
ranking.
