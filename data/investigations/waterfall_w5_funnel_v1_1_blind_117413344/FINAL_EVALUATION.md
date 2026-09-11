# W5 Hierarchical Retrieval Funnel v1.1 strict blind evaluation

**Verdict: UNLABELLED**

## Protocol facts

1. The target was Property24 listing `117413344` in Waterfall Country Estate.
2. Listing-only evidence was frozen in commit
   `a6798369541e5f8badb23655a87540141b563e93`.
3. The profile freeze file SHA-256 is
   `21c3e39f68cd3be8d5a74d572df66d25768fc28b74fcab2c858e10a670d305e6`.
4. Automatic acquisition preserved the HTTP response, sanitized response
   headers, 49 exposed stills, provenance, byte counts, and SHA-256 values in
   `LISTING_EVIDENCE_MANIFEST.json`.
5. No supported listing video was exposed; therefore no video frames were
   acquired.
6. The frozen listing inputs were reliable land area **1,205 m2** and
   affirmative pool expectation; floor area was **820 m2**.
7. The listing-only VLI observed a pool plus heated jacuzzi, immediately
   adjacent to the residence's entertainment façade; roof layout remained
   partial and no orientation was inferred.
8. The W1 universe was exactly 1,010 parcels from commit
   `e86b156b3f8ac099cd386b9de2b3b2ba609c0635`; GeoJSON SHA-256 was
   `6a375bf542bcff28c6a3ee862f9e0c3c9a5395d0497b4159027c40b75cf7be3a`.
9. Candidate evidence used only the recovered original native15 imagery,
   read-only, through the frozen v1.1 implementation commit
   `2f9268783e3eb1d2a1f0c039b976833dc67fc543`.
10. The v1.1 priority distribution was A **272**, B **365**, C **251**, and
    D **122**; all candidates remained recoverable.
11. A was processed first. Its sufficient-evidence assessment had 272 serious
    candidates, top coverage 0.000, one supporting component, combined support
    0.425, and a 30-candidate near-top set.
12. The frozen triggers `LOW_TOP_CANDIDATE_COVERAGE`,
    `NON_UNIQUE_TOP_SET`, and `INSUFFICIENT_COMBINED_SUPPORT` required each
    A→B, A+B→C, and A+B+C→D expansion. Pool unknown rate was recorded but was
    not an expansion trigger.
13. Immediate expensive workload was **272/1,010**, a **73.07%** reduction
    versus exhaustive immediate processing. Total work was **1,010/1,010**
    after justified expansion, a **0.00%** total reduction.
14. For the conceptual frozen-v1 workload comparison only, its initial
    <=10% group would contain A+B = **637** candidates, of which **536** have
    unknown pool state; its existing high-unknown fallback would then add C
    for **888** immediate candidates. v1.1 deferred **616** candidates from
    that conceptual immediate workload (**69.37%**), while retaining full
    recovery.
15. The anonymous score, band, expansion, top-30/top-10, proof-panel, and
    instrumentation artifacts were frozen in commit
    `a2a35c9cd4c699623d3844faa34cf00114e0b370`; `BLIND_FREEZE.sha256` has
    SHA-256 `1da05cd141ea8acbdb495d1c273ce4c443334b3c040a4e9c8f3a1f546d530ae2`.
    `BLIND_TOP10_IDENTITY_ATTACHMENT.csv` then added W1 property/stand/
    extension metadata without modifying the sealed ranking.
16. Permitted post-freeze ground-truth inquiry found no independently
    verifiable target parcel. Ground truth is **UNAVAILABLE**, accuracy is
    **UNLABELLED**, and no recovery or rank-accuracy claim is made.

## Result

This first strict blind run confirms the frozen v1.1 mechanism followed its
pre-registered A→B→C→D evidence-sufficiency path without tuning, new filters,
VLM use, production-code changes, or identity leakage before rank freeze.
Because independent target identity is unavailable, the required verdict is
**UNLABELLED**, not a promotion, promise, revision, or failure conclusion.
