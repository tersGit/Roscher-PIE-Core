# W3-V Qwen32B blind-result freeze

BLIND PIPELINE EXECUTION=PASS
QWEN32B VLM FREEZE=COMPLETE
GROUND TRUTH RECOVERY=NOT_STARTED
STREET VIEW=NOT_STARTED
ACCURACY EVALUATION=UNLABELLED

This evidence-only freeze records the supplied external RunPod result. The original RunPod JSON is absent locally and awaiting archival. `W3V_QWEN32B_BLIND_TOP10.json` is a faithful structured local reconstruction from only the supplied ranking and metadata; its local SHA-256 is not asserted to equal the supplied canonical external JSON SHA-256.

The frozen inference used `Qwen2.5-VL-32B-Instruct-Q4_K_M`, context 32768, one slot, image-min-tokens 1024, and temperature 0. It reviewed six frozen W3-V target views and a candidate crop plus parcel overlay for each candidate. All 26 exported image hashes were verified before inference. Candidate inference was anonymous; identity was available only post-response. Ties used deterministic frozen-PIE-rank; no PIE blending occurred.

Descriptive rank movement only: PIE #1 stand1022 -> VLM#2; PIE#8 stand3060 -> VLM#1; PIE#6 stand917 -> VLM#10. With ground truth not started, this artifact makes no claim of improvement or deterioration.

No ground-truth recovery, Street View, identity/address/GIS/candidate/duplicate/reverse-image/web-identity work, rerun, rerank, or modification of frozen W3-S/W3-V ranking artifacts was performed for this freeze.
