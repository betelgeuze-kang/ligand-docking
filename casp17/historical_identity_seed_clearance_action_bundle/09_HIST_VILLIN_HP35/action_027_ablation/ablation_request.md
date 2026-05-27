# HIST_VILLIN_HP35 Ablation Manifest Request

This request records the ablation evidence needed before seed promotion.
- target_id: `HIST_VILLIN_HP35`
- scope: `monomer`
- prediction_pdb: `data/internal_structures_refined/nightly/2026-02-19-ops-full-dashboard-r1/visual_post_internal_post_villin_hp35_sample000_step00020.pdb`
- prediction_fingerprint: `size=11765;sha256_16=8bd771efc6ca4c50`
- native_pdb: `data/native/villin_hp35.pdb`
- native_fingerprint: `size=2868;sha256_16=53e11674a3494e5e`
- operator_clearance_csv: `runs/casp17_historical_identity_seed_operator_clearance_current.csv`
- blockers: `no_leak_evidence_ref_required,leakage_clearance_required,operator_clearance_required,operator_required,prediction_created_at_required_iso_date,native_release_date_required_iso_date,prediction_generated_before_native_release_required,public_template_or_native_used_for_prediction_must_be_false,other_team_model_used_must_be_false,post_release_information_used_must_be_false,current_casp17_target_must_be_false,selected_model_rank_required_1_to_5,best_model_rank_required_1_to_5,selected_native_metric_required_numeric,best_native_metric_required_numeric,selected_score_required_numeric,best_score_required_numeric,ablation_manifest_ref_required`

Required operator work:
- provide a local ablation_manifest_ref file
- include which recursive/refinement/model-selection layers were present
- include enough rows to reproduce selected-vs-best comparison context
