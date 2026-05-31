# HIST_GB1_MINI prediction_not_before_native Repair

- action: `first_slot_repair_005`
- status: `open_repair_action`
- repair class: `chronology`
- candidate: `HIST_GB1_MINI` `hist_seed_gb1_mini`
- field/dropzone field: `prediction_created_at` `prediction_pdb`
- evidence pointer: `prediction_created_at=2026-02-19;native_release_date=1991-05-15`
- next action: attach a prediction artifact created before the authoritative native release date

## Claim Boundary

Local CASP17 first-slot candidate repair board only. It decomposes fail-closed local-candidate blockers into operator repair actions for chronology, provenance, ablation, calibration, and missing source files. It does not create evidence, approve candidates, mutate intake CSVs, compute CASP metrics, or submit to CASP.
