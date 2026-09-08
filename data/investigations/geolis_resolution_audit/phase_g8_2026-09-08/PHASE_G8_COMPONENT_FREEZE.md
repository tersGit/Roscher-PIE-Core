# PHASE G8 component freeze

| Component | Frozen authority | Pin |
|---|---|---|
| Native15 imagery profile | Phase F/AGS 2023 `native15` profile | `backend/imagery/estate_tiles.py`: Git blob `c1b9a01399689f4d67cc640cb7f1d9319b107f72`, SHA-256 `9ab94e68e76cf39fc03ad4ad3cc25d228c8a4f9310e00bd3a714bd0e170da604`; 0.15 m/px; `AerialPhotography/2023` |
| Detector lineage | G3 detector freeze | commit `6c53661e15d1bda968318cbac7cc244ed7497789` |
| PR27 validator source | PR #27 exact historical source | commit `9e5e727fa28749e90b95730084ec97cb98dfbddf`, object `032690307476dcfb2bb5d06e469cb66892b87398` |
| Parcel/GIS source | Current parcel/GIS source | `data/gis/carlswald_north_corrected_002.json`: Git blob `508fdd0b90a9a6af851d5b3a92fe5489a0c876f2`, SHA-256 `431c41041f508252e016829795e824232e6f22afa00f5111c8b4a9123f6b7e83` |

The current checkout's validator and detector source hashes are not the historical PR27/G3 objects. A prospective runner must record the frozen Git object identifiers above and must not label current checkout code as historical PR27/G3 without an exact object comparison.
