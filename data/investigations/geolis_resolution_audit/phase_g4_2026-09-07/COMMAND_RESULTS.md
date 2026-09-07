# Phase G4 command results

```text
G3 commit ancestry: bc434935a6316acf0c333b15d0a8b0787cfb33fd (HEAD before G4)
G3 required artifacts: SHA-256 recorded before blinded material generation
python data\investigations\geolis_resolution_audit\phase_g4_2026-09-07\run_phase_g4.py
```

The G4 collector reads committed G3 detector results and input images only. It
does not import or invoke `extract_pool_geometry`, make network requests, or
modify G3 evidence. It generated 48 blinded transition panels and 64 blinded
material-geometry panels, each with a separate post-reveal stored-result
overlay pair.

```text
G3_EVIDENCE_AND_FROZEN_BLOBS_UNCHANGED
G4_EVIDENCE_SCOPE_ONLY
```

No detector test was rerun because G4 evaluates the committed G3 result set;
rerunning would violate its evidence-freeze constraint.
