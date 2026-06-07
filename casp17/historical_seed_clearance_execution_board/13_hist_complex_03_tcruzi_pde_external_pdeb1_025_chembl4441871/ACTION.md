# CASP17 Historical Seed Clearance Execution 13: HIST_COMPLEX_03_TCRUZI_PDE_EXTERNAL_PDEB1_025_CHEMBL4441871

- status: `ablation_repair_then_operator_no_leak`
- scope: `complex`
- operator no-leak fields: `10`
- proposed fields ready: `6`
- calibration candidates: `6`
- ablation candidates: `0`
- blocked ablation fields: `1`
- fill candidates: `casp17/historical_seed_clearance_fill_candidates/13_hist_complex_03_tcruzi_pde_external_pdeb1_025_chembl4441871/clearance_fill_candidates.csv`
- no-leak repair CSV: `casp17/historical_seed_no_leak_gap_repair_plan/13_hist_complex_03_tcruzi_pde_external_pdeb1_025_chembl4441871/no_leak_gap_repair_fields.csv`
- ablation repair CSV: `casp17/historical_seed_ablation_gap_repair_plan/13_hist_complex_03_tcruzi_pde_external_pdeb1_025_chembl4441871/ablation_gap_repair_candidates.csv`
- next action: repair real ablation layer evidence, then fill operator no-leak evidence fields
- blockers: `operator_no_leak_evidence_required,real_ablation_layer_required`

## Guardrail

Do not promote this row into the cleared manifest until operator no-leak evidence and required negative-control confirmations are filled with independent evidence.
