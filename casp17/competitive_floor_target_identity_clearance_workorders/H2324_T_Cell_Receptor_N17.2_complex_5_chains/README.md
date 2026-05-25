# H2324 Target Identity Clearance Workorder

- target_name: T Cell Receptor N17.2, complex (5 chains)
- scope: `complex`
- workorder_status: `native_and_provenance_required`
- prediction_pdb: `runs/casp17_prediction_jobs_current/H2324/H2324_model_1.pdb`
- ts_prediction_pdb: `runs/casp17_predictions_current/H2324TS.pdb`
- native_dropzone_pdb: `casp17/competitive_floor_target_identity_clearance_workorders/H2324_T_Cell_Receptor_N17.2_complex_5_chains/native/H2324_native.pdb`
- provenance_template_csv: `casp17/competitive_floor_target_identity_clearance_workorders/H2324_T_Cell_Receptor_N17.2_complex_5_chains/provenance_template.csv`
- manifest_stub_csv: `casp17/competitive_floor_target_identity_clearance_workorders/H2324_T_Cell_Receptor_N17.2_complex_5_chains/manifest_stub.csv`

## Stop Conditions

- Do not use this as a historical/no-leak benchmark row until native release date and provenance are confirmed.
- Do not mark operator clearance unless prediction generation predates native release.
- Do not use public/template/native structures, other-team models, or post-release information for prediction.
- Do not import this stub into identity intake automatically.

## Next Action

place a cleared native PDB and complete the no-leak provenance template
