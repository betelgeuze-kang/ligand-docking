# hist_REQUIRED_COMPLEX_010 Strict-Blind Replacement Intake

- status: `awaiting_operator_input`
- template status: `created`
- required target: `REQUIRED_COMPLEX_010`
- scope: `complex`
- filled/missing/required fields: `0/16/16`
- replacement target: `REQUIRED_CLOSED_HISTORICAL_TARGET_ID`
- intake csv: `casp17/historical_seed_strict_blind_replacement_intake/35_hist_required_complex_010/replacement_candidate_intake.csv`
- preflight csv: `casp17/historical_seed_strict_blind_replacement_intake/35_hist_required_complex_010/replacement_candidate_preflight.csv`
- blockers: `replacement_target_id_required,replacement_benchmark_id_required,target_identity_non_current_historical_required,prediction_pdb_required,native_pdb_required,native_authority_ref_required,prediction_created_at_required,native_release_date_required,prediction_generated_before_native_release_required,no_leak_evidence_ref_required,public_template_or_native_used_for_prediction_required,other_team_model_used_required,post_release_information_used_required,ablation_manifest_ref_required,calibration_values_ref_required,operator_clearance_required`
- next action: fill replacement_candidate_intake.csv with strict-blind evidence, then rerun intake preflight

## Claim Boundary

Local CASP17 historical strict-blind replacement intake/preflight only. It creates per-slot operator intake templates and validates required strict-blind evidence fields before a replacement can enter competitive proof. It does not choose replacement targets, approve no-leak provenance, fetch structures, compute CASP metrics, mutate benchmark/operator CSVs, or submit to CASP.
