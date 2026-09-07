# G4H command results

## Source integrity

G4H started from committed G3 evidence `bc434935a6316acf0c333b15d0a8b0787cfb33fd`
and committed G4 evidence `c7ae71883a8233d9fb113b70a76ddf9a441c68b9`.
SHA-256 hashes for the eight source artifacts are in
`FREEZE_VERIFICATION_PRE.json` and matched after package generation.

## Generation

```text
python data\investigations\geolis_resolution_audit\phase_g4h_2026-09-07\build_g4h_package.py
```

The generator read only committed G3 detector-input crops and G4's transition
selection. It made no detector invocation, AGS/network request, image
enhancement, source modification, or production/frozen change.

## Verification

Automated validation confirms:

- exactly 48 human-review rows, with required columns and blank verdict,
  confidence, and notes fields;
- exactly 48 reveal rows and 48 checklist entries with actual stand numbers;
- 48 individual first-pass panels and five contact sheets;
- no detector-status or resolution terms in first-pass panel filenames,
  checklist, or review CSV;
- source hashes unchanged and Git changes confined to this G4H directory.
