# Phase G5 freeze verification

- Detector freeze reference commit: `6c53661e15d1bda968318cbac7cc244ed7497789` (not rerun or modified).
- Raw workbook SHA-256: `c27750519a8df1053b0c9ef1e906c0d0b9c78af950e49ea33be3fcebddf8f5df`.
- Human input locked before joins: `PHASE_G5_HUMAN_LOCKED.csv` SHA-256 `c57e81aac17d44cca5b1ae8a0f7d8ead1e291ac952aa92ba9d6a3ad57f4c6a58`.

## Existing committed source hashes

| Artifact | Expected | Actual | Status |
|---|---|---|---|
| `data\investigations\geolis_resolution_audit\phase_g3_2026-09-07\results.json` | `bd1a52f140113e7f5d0affdcfe588d9c7eb115fa8b65fff755b008564ecc48fd` | `bd1a52f140113e7f5d0affdcfe588d9c7eb115fa8b65fff755b008564ecc48fd` | UNCHANGED |
| `data\investigations\geolis_resolution_audit\phase_g3_2026-09-07\PHASE_G3_DETECTOR_AB.csv` | `1cb87575261682ab541e5c82b80be5f36d110553634de2414aa767c002de096f` | `1cb87575261682ab541e5c82b80be5f36d110553634de2414aa767c002de096f` | UNCHANGED |
| `data\investigations\geolis_resolution_audit\phase_g3_2026-09-07\PHASE_G3_TRANSITIONS.csv` | `6c811d97eed395e568e5b3ca9f82b6f4758e5db6583b29b82bacba70258beddb` | `6c811d97eed395e568e5b3ca9f82b6f4758e5db6583b29b82bacba70258beddb` | UNCHANGED |
| `data\investigations\geolis_resolution_audit\phase_g3_2026-09-07\PHASE_G3_GEOMETRY_CHANGES.csv` | `817ab1d7a9a60369df60643a6a88391e909f812f24ce9fea2e8b339683e264de` | `817ab1d7a9a60369df60643a6a88391e909f812f24ce9fea2e8b339683e264de` | UNCHANGED |
| `data\investigations\geolis_resolution_audit\phase_g3_2026-09-07\DETECTOR_FREEZE_MANIFEST_POST.json` | `1850b31b561bceb091e86f7252cd6e9b4306762fce25b9246795702bef128ba0` | `1850b31b561bceb091e86f7252cd6e9b4306762fce25b9246795702bef128ba0` | UNCHANGED |
| `data\investigations\geolis_resolution_audit\phase_g4_2026-09-07\PHASE_G4_TRANSITION_VALIDATION.csv` | `16fb066a483da0cf33353055df0a29a121b6f62869b3bd63229b198462f603b2` | `16fb066a483da0cf33353055df0a29a121b6f62869b3bd63229b198462f603b2` | UNCHANGED |
| `data\investigations\geolis_resolution_audit\phase_g4_2026-09-07\evidence_manifest.json` | `33a121c0931142427b1cc3b3be24d55256953846eb845c41ca30a7182e917c8a` | `33a121c0931142427b1cc3b3be24d55256953846eb845c41ca30a7182e917c8a` | UNCHANGED |
| `data\investigations\geolis_resolution_audit\phase_g4_2026-09-07\FREEZE_VERIFICATION_POST.json` | `87153996564c50d10d43bdbc8fe5c11706ef10039979974d9fcf94fa6dc6ea7b` | `87153996564c50d10d43bdbc8fe5c11706ef10039979974d9fcf94fa6dc6ea7b` | UNCHANGED |

Overall existing-source status: **UNCHANGED**.
No detector, imagery fetch, thresholds, scoring, Shape v2, ranking, inventory, or prior G3/G4/G4H evidence was changed.
