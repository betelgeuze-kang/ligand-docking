# CASP17 Historical Seed Clearance Execution 3: HIST_CRAMBIN

- status: `ablation_repair_then_operator_no_leak`
- scope: `monomer`
- operator no-leak fields: `10`
- proposed fields ready: `6`
- calibration candidates: `6`
- ablation candidates: `0`
- blocked ablation fields: `1`
- fill candidates: `casp17/historical_seed_clearance_fill_candidates/03_hist_crambin/clearance_fill_candidates.csv`
- no-leak repair CSV: `casp17/historical_seed_no_leak_gap_repair_plan/03_hist_crambin/no_leak_gap_repair_fields.csv`
- ablation repair CSV: `casp17/historical_seed_ablation_gap_repair_plan/03_hist_crambin/ablation_gap_repair_candidates.csv`
- next action: repair real ablation layer evidence, then fill operator no-leak evidence fields
- blockers: `operator_no_leak_evidence_required,real_ablation_layer_required`

## Guardrail

Do not promote this row into the cleared manifest until operator no-leak evidence and required negative-control confirmations are filled with independent evidence.
