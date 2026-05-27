# HIST_BBA5 Calibration Request

This request keeps model1 and best-of-5 calibration explicit before promotion.
- target_id: `HIST_BBA5`
- scope: `monomer`
- prediction_pdb: `data/internal_structures_refined/nightly/2026-02-19-ops-full-dashboard-r1/visual_post_internal_post_bba5_sample000_step00020.pdb`
- prediction_fingerprint: `size=7870;sha256_16=d8d2a2e5acf15c7e`
- native_pdb: `data/native/bba5.pdb`
- native_fingerprint: `size=1913;sha256_16=0359e928b0f87cf8`
- operator_clearance_csv: `runs/casp17_historical_identity_seed_operator_clearance_current.csv`
- blockers: `no_leak_evidence_ref_required,leakage_clearance_required,operator_clearance_required,operator_required,prediction_created_at_required_iso_date,native_release_date_required_iso_date,prediction_generated_before_native_release_required,public_template_or_native_used_for_prediction_must_be_false,other_team_model_used_must_be_false,post_release_information_used_must_be_false,current_casp17_target_must_be_false,selected_model_rank_required_1_to_5,best_model_rank_required_1_to_5,selected_native_metric_required_numeric,best_native_metric_required_numeric,selected_score_required_numeric,best_score_required_numeric,ablation_manifest_ref_required`

Required operator work:
- fill selected_model_rank and best_model_rank with values from 1 to 5
- fill selected_native_metric and best_native_metric after no-leak native scoring
- fill selected_score and best_score from the internal ranking surface
- keep selected_native_metric <= best_native_metric
