# HIST_VILLIN_HP35 calibration Action

- action_rank: `26`
- action_status: `open`
- required_field: `selected/best ranks and metric values`
- blockers: `no_leak_evidence_ref_required,leakage_clearance_required,operator_clearance_required,operator_required,prediction_created_at_required_iso_date,native_release_date_required_iso_date,prediction_generated_before_native_release_required,public_template_or_native_used_for_prediction_must_be_false,other_team_model_used_must_be_false,post_release_information_used_must_be_false,selected_model_rank_required_1_to_5,best_model_rank_required_1_to_5,selected_native_metric_required_numeric,best_native_metric_required_numeric,selected_score_required_numeric,best_score_required_numeric,ablation_manifest_ref_required`
- recommended_action: enter model selection and native-metric calibration values
- unlocks: `ready_for_cleared_seed_manifest`
- verification_command: `python3 tools/build_casp17_historical_identity_seed_clearance_workorder.py`
- request_md: `casp17/historical_identity_seed_clearance_action_bundle/09_HIST_VILLIN_HP35/action_026_calibration/calibration_request.md`

## Claim Boundary

Local CASP17 historical seed-clearance action bundle only. It materializes open seed-clearance phases into per-seed request folders for operator work. Request files are templates and are intentionally not no-leak evidence. It does not fill operator clearance, certify chronology, fetch native structures, score native accuracy, mutate competitive-floor identity intake, run predictors, or submit to CASP.
