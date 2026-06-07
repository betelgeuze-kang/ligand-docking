# CASP17 Historical Seed Clearance Execution 1: HIST_CHIGNOLIN

- status: `operator_no_leak_only`
- scope: `monomer`
- operator no-leak fields: `10`
- proposed fields ready: `7`
- calibration candidates: `6`
- ablation candidates: `1`
- blocked ablation fields: `0`
- fill candidates: `casp17/historical_seed_clearance_fill_candidates/02_hist_chignolin/clearance_fill_candidates.csv`
- no-leak repair CSV: `casp17/historical_seed_no_leak_gap_repair_plan/02_hist_chignolin/no_leak_gap_repair_fields.csv`
- ablation repair CSV: `casp17/historical_seed_ablation_gap_repair_plan/02_hist_chignolin/ablation_gap_repair_candidates.csv`
- next action: fill operator no-leak evidence fields, then apply prepared calibration and ablation candidates
- blockers: `operator_no_leak_evidence_required`

## Guardrail

Do not promote this row into the cleared manifest until operator no-leak evidence and required negative-control confirmations are filled with independent evidence.
