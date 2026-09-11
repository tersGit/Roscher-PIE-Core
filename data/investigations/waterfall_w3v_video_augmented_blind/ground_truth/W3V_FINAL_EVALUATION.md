# W3-V final evaluation

## Evaluation validity

The independent ground-truth artifact was committed as
`66214f7c94b722ffb7e23bab3712f6a7aa473405` before any ranking file was
accessed. The first ranking-file access occurred at
**2026-09-11T10:00:58.4011632+02:00**.

Ground truth is **UNAVAILABLE**: public recovery corroborated the cross-published
listing and video but did not recover a property-specific address, stand, parcel,
or geometry. Therefore no ranked candidate can be truth-labeled, and any claim
that a method improved or deteriorated at top-1, top-5, or top-10 would be
unsupported.

| Measure | PIE W3-S | PIE W3-V | Qwen W3-V | Evaluation |
|---|---:|---:|---:|---|
| Ground-truth rank | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | No public parcel identity to look up. |
| Ground-truth score | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | No ground-truth candidate exists in the ranking universe. |
| Top-1 status | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | Cannot assess correctness. |
| Top-5 status | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | Cannot assess correctness. |
| Top-10 status | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | Cannot assess correctness. |

## Frozen-method observations

These are descriptive frozen-ranking observations, not correctness findings.

| Method | Top candidate | Score | Comparison |
|---|---|---:|---|
| W3-S PIE | Stand 916, ext 19, property `2034520` | 0.7558 | Listing-still ranking. |
| W3-V PIE | Stand 1022, ext 19, property `2033300` | 0.7738 | Video augmentation promoted this candidate from W3-S rank 5 to W3-V rank 1 (+4). |
| W3-V Qwen | Stand 3060, ext 39, property `2073427` | 0.750 | Qwen-only frozen ordering; this candidate is W3-V PIE rank 8. |

The W3-V PIE top ten preserved the documented W3-S movements: 1022 `5 -> 1`,
3112 `2 -> 2`, 1057 `3 -> 3`, 3036 `4 -> 4`, 1059 `7 -> 5`, 917 `6 -> 6`,
3968 `11 -> 7`, 3060 `12 -> 8`, 3241 `8 -> 9`, and 873 `9 -> 10`.

Qwen's delta relative to the frozen W3-V PIE ordering is:

| Candidate | W3-V PIE rank / score | Qwen rank / score | Qwen rank delta |
|---|---:|---:|---:|
| Stand 3060, ext 39 | 8 / 0.7621 | 1 / 0.750 | +7 |
| Stand 1022, ext 19 | 1 / 0.7738 | 2 / 0.700 | -1 |
| Stand 3112, ext 39 | 2 / 0.7733 | 3 / 0.700 | -1 |
| Stand 1057, ext 19 | 3 / 0.7725 | 4 / 0.700 | -1 |
| Stand 1059, ext 19 | 5 / 0.7678 | 5 / 0.700 | 0 |
| Stand 873, ext 19 | 10 / 0.7603 | 6 / 0.700 | +4 |
| Stand 3036, ext 38 | 4 / 0.7694 | 7 / 0.550 | -3 |
| Stand 3968, ext 40 | 7 / 0.7631 | 8 / 0.500 | -1 |
| Stand 3241, ext 39 | 9 / 0.7604 | 9 / 0.500 | 0 |
| Stand 917, ext 19 | 6 / 0.7672 | 10 / 0.300 | -4 |

No W1 GIS universe was consulted because public recovery never produced the
required independently supported candidate. The frozen results were not rerun,
reranked, tuned, or changed.

## Candidate-method outcome

| Candidate method | Outcome |
|---|---|
| Independent public identity recovery | UNAVAILABLE for parcel identity; it established listing/video linkage only. |
| W1 GIS exact-six extension lookup | NOT PERFORMED; no independently supported stand/address candidate met the prerequisite. |
| Aerial / Street View parcel comparison | NOT PERFORMED; no recovered parcel existed to compare. |
| W3-S PIE, W3-V PIE, and W3-V Qwen correctness assessment | UNAVAILABLE; no truth label. |

## Evidence integrity

| Artifact | SHA-256 |
|---|---|
| Ground-truth JSON | `cb316ee60c3f6de999b246d6f32ecd69b6a91ea117607f74184fd24af3f25fb9` |
| W3-S full ranking | `84ae1c4667b57311668b28143b46b7e12e601b287f4a49dcae07b765d9dfb457` |
| W3-S rank freeze | `c1b9c8488d0e3a6873d4298e1edfa8e5fb96afb4659bd6c381194bc65ad3587d` |
| W3-V full ranking | `b3625899516ce9ca7fb948c63ccd3fac35c8c8e4c8a914fc2201e13764317870` |
| W3-V rank freeze | `d4d3bf61d2170d142fbba95244533f71d5cff5fd877938c72029d47286c22189` |
| Local Qwen reconstruction | `932593e5ec80b935973bafb83c03b0430dd2f5df5de2945b75ee22d8406b4544` |
| Canonical external Qwen JSON (supplied reference; not present locally) | `96b5287f1d3fe26a20b27e47d93f7b55ebd6a69e09d680e7b72e6a09266f643f` |
| Qwen evidence commit | `9626037e81f546602225a91801a99b546411a27e` |
