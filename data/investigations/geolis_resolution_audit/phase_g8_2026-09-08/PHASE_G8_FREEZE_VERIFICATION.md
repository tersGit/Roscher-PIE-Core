# PHASE G8 freeze verification

All authoritative commits were verified present locally:

- G7: `85fce4069aa3102bfd946e24d5eb263f078bf63e`
- G6: `313ef89b89077902aed6526bdc65da4a06c2f9c8`
- G5: `bd46a6fda2b8879dd7b0f5247665551ebd33eaf3`
- G4H: `5dd93d99405806211bcf2e2c6cc9af2feefb6fa5`
- G4: `c7ae71883a8233d9fb113b70a76ddf9a441c68b9`
- G3: `bc434935a6316acf0c333b15d0a8b0787cfb33fd`
- detector freeze: `6c53661e15d1bda968318cbac7cc244ed7497789`
- unchanged PR #27 source: `9e5e727fa28749e90b95730084ec97cb98dfbddf`

The PR27 validator's Git blob at the frozen source is `032690307476dcfb2bb5d06e469cb66892b87398`; the current working-tree file hash differs. The frozen detector's Git blob is `a58e4b9882e4d5013a664389a439ab139c844b59`; the current working-tree file hash differs. This G8 commit neither changes either implementation nor runs listings, downloads imagery, processes the five-listing sample, or uses G5 labels for tuning.

The current native15 profile is pinned at Git blob `c1b9a01399689f4d67cc640cb7f1d9319b107f72` and SHA-256 `9ab94e68e76cf39fc03ad4ad3cc25d228c8a4f9310e00bd3a714bd0e170da604`. The current parcel/GIS source is `data/gis/carlswald_north_corrected_002.json`, pinned at Git blob `508fdd0b90a9a6af851d5b3a92fe5489a0c876f2` and SHA-256 `431c41041f508252e016829795e824232e6f22afa00f5111c8b4a9123f6b7e83`.
