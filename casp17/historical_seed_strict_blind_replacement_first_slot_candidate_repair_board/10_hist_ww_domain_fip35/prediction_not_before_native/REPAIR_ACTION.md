# HIST_WW_DOMAIN_FIP35 prediction_not_before_native Repair

- action: `first_slot_repair_010`
- status: `open_repair_action`
- repair class: `chronology`
- candidate: `HIST_WW_DOMAIN_FIP35` `hist_seed_ww_domain_fip35`
- field/dropzone field: `prediction_created_at` `prediction_pdb`
- evidence pointer: `prediction_created_at=2026-02-19;native_release_date=2005-11-15`
- next action: attach a prediction artifact created before the authoritative native release date

## Claim Boundary

Local CASP17 first-slot candidate repair board only. It decomposes fail-closed local-candidate blockers into operator repair actions for chronology, provenance, ablation, calibration, and missing source files. It does not create evidence, approve candidates, mutate intake CSVs, compute CASP metrics, or submit to CASP.
