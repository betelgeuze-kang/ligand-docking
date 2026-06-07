# HIST_CRAMBIN calibration_not_ready Repair

- action: `first_slot_repair_065`
- status: `open_repair_action`
- repair class: `calibration`
- candidate: `HIST_CRAMBIN` `hist_seed_crambin`
- field/dropzone field: `calibration_values_ref` `calibration_values_ref`
- evidence pointer: `casp17/historical_seed_calibration_candidate_ledgers/03_hist_crambin_calibration_candidates.csv`
- next action: operator-fill calibration values after no-leak provenance clearance

## Claim Boundary

Local CASP17 first-slot candidate repair board only. It decomposes fail-closed local-candidate blockers into operator repair actions for chronology, provenance, ablation, calibration, and missing source files. It does not create evidence, approve candidates, mutate intake CSVs, compute CASP metrics, or submit to CASP.
