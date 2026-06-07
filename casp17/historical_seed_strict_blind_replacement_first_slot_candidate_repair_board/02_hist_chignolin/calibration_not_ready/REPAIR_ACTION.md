# HIST_CHIGNOLIN calibration_not_ready Repair

- action: `first_slot_repair_064`
- status: `open_repair_action`
- repair class: `calibration`
- candidate: `HIST_CHIGNOLIN` `hist_seed_chignolin`
- field/dropzone field: `calibration_values_ref` `calibration_values_ref`
- evidence pointer: `casp17/historical_seed_calibration_candidate_ledgers/02_hist_chignolin_calibration_candidates.csv`
- next action: operator-fill calibration values after no-leak provenance clearance

## Claim Boundary

Local CASP17 first-slot candidate repair board only. It decomposes fail-closed local-candidate blockers into operator repair actions for chronology, provenance, ablation, calibration, and missing source files. It does not create evidence, approve candidates, mutate intake CSVs, compute CASP metrics, or submit to CASP.
