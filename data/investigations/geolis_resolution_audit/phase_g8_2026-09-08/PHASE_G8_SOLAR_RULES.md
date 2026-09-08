# PHASE G8 solar and backup-power rules

1. Record `SOLAR_PANELS` independently from `BACKUP_POWER_SYSTEM`, `INVERTER`, and `BATTERY_STORAGE`.
2. Do not infer solar from an inverter, battery, electrical cabinet, estate convention, listing prose, or any absence of contrary evidence.
3. Use `VISUALLY_CONFIRMED` only when panels are visible in an identified image/frame; retain its frame and geometry reference.
4. Use `PRESENT_UNCONFIRMED`, `NOT_OBSERVED`, or `UNKNOWN` for all other cases.
5. These fields are descriptive and carry no detector, validator, ranking, or decision weight in G8.
