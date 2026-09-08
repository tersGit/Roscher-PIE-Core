# PHASE G8 property-layout feature schema

Capture features as observations only: `feature_type`, `evidence_status`, `source_artifact`, geometry/contour reference, confidence, frame/source identifier, and free-text limitation. No G5 label, weight, threshold, score adjustment, or tuning field is permitted.

Supported feature types include `BUILDING`, `POOL`, `ROAD`, `DRIVEWAY`, `GARDEN`, `OUTBUILDING`, `WATER_FEATURE`, `BACKUP_POWER_SYSTEM`, `INVERTER`, `BATTERY_STORAGE`, and `SOLAR_PANELS`.

`BACKUP_POWER_SYSTEM`, `INVERTER`, and `BATTERY_STORAGE` are electrical-layout observations and never infer `SOLAR_PANELS`. `SOLAR_PANELS` is recorded only with direct visual evidence; `VISUALLY_CONFIRMED` means panels are visibly distinguishable in the captured frame, not inferred from power equipment.
