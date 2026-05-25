# H1319 -> H1311 Replacement Workorder

- replace_target_name: Human astrovirus VA1 capsid spike - antibody 7C8 complex
- candidate_target_name: NRAS17.3.2_Q61K_HLAA1
- scope: `complex`
- selection_status: `selected_for_replacement_workorder`
- workorder_status: `native_and_provenance_required`
- prediction_pdb: `runs/casp17_prediction_jobs_current/H1311/H1311_model_1.pdb`
- raw_validation_json: `runs/casp17_internal_physics_raw_validations_current/H1311_raw_confidence_calibration.json`
- scorecard_json: `runs/casp17_internal_scorecards_current/H1311_internal_scorecard.json`
- native_dropzone_pdb: `casp17/competitive_floor_target_identity_clearance_replacement_workorders/H1319_to_H1311_NRAS17.3.2_Q61K_HLAA1/native/H1311_native.pdb`
- provenance_template_csv: `casp17/competitive_floor_target_identity_clearance_replacement_workorders/H1319_to_H1311_NRAS17.3.2_Q61K_HLAA1/provenance_template.csv`
- manifest_stub_csv: `casp17/competitive_floor_target_identity_clearance_replacement_workorders/H1319_to_H1311_NRAS17.3.2_Q61K_HLAA1/manifest_stub.csv`

## Stop Conditions

- Do not apply this replacement to the live clearance queue until no-leak provenance is operator-cleared.
- Do not reuse the same candidate target id for multiple replacement slots without an explicit operator decision.
- Do not import this manifest stub into identity intake automatically.

## Next Action

fill replacement native dropzone and no-leak provenance template, then run operator intake
