# HIST_UBIQUITIN_MINI No-Leak Provenance Request

CLEARANCE_EVIDENCE_STATUS: request_template

This file is an operator request template, not completed no-leak evidence.
- target_id: `HIST_UBIQUITIN_MINI`
- scope: `monomer`
- prediction_pdb: `data/internal_structures_refined/nightly/2026-02-19-ops-full-dashboard-r1/visual_post_internal_post_ubiquitin_mini_sample000_step00020.pdb`
- prediction_fingerprint: `size=25052;sha256_16=709bbeca9c5d3a05`
- native_pdb: `data/native/ubiquitin_mini.pdb`
- native_fingerprint: `size=6110;sha256_16=1a4ac95c4c3f1dbd`
- operator_clearance_csv: `runs/casp17_historical_identity_seed_operator_clearance_current.csv`
- blockers: `no_leak_evidence_ref_required,leakage_clearance_required,operator_clearance_required,operator_required,prediction_created_at_required_iso_date,native_release_date_required_iso_date,prediction_generated_before_native_release_required,public_template_or_native_used_for_prediction_must_be_false,other_team_model_used_must_be_false,post_release_information_used_must_be_false,current_casp17_target_must_be_false,selected_model_rank_required_1_to_5,best_model_rank_required_1_to_5,selected_native_metric_required_numeric,best_native_metric_required_numeric,selected_score_required_numeric,best_score_required_numeric,ablation_manifest_ref_required`

Required operator work:
- create a separate completed evidence file that names this target_id
- set leakage_clearance/operator_clearance only after review is complete
- fill prediction_created_at and native_release_date with ISO dates
- confirm prediction_generated_before_native_release=true
- confirm public_template_or_native_used_for_prediction=false
- confirm other_team_model_used=false
- confirm post_release_information_used=false
- confirm current_casp17_target=false
