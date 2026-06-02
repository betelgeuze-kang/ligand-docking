# H2324 Native/Provenance Operator Packet

- target: `T Cell Receptor N17.2, complex (5 chains)`
- status: `open_actions`
- actions native/evidence/provenance/manifest: `1/1/1/1`
- metric requirements: `9`
- prediction: `runs/casp17_prediction_jobs_current/H2324/H2324_model_1.pdb`
- native dropzone: `casp17/competitive_floor_target_identity_clearance_workorders/H2324_T_Cell_Receptor_N17.2_complex_5_chains/native/H2324_native.pdb`
- provenance template: `casp17/competitive_floor_target_identity_clearance_workorders/H2324_T_Cell_Receptor_N17.2_complex_5_chains/provenance_template.csv`
- manifest stub: `casp17/competitive_floor_target_identity_clearance_workorders/H2324_T_Cell_Receptor_N17.2_complex_5_chains/manifest_stub.csv`
- metric runway: `casp17/competitive_floor_target_identity_metric_runway/H2324_T_Cell_Receptor_N17_2_complex_5_chains/METRIC_RUNWAY.md`
- native candidates blocked/no-candidate/total: `0/1/1`
- proof/author: `false/false`
- blockers: `native_pdb_missing,manifest_native_pdb_not_found,evidence_ref_required,identity_discovery_no_leak_clearance_required,operator_required,leakage_clearance_required,operator_clearance_required,prediction_created_at_required_iso_date,native_release_date_required_iso_date,prediction_generated_before_native_release_required,public_template_or_native_used_for_prediction_must_be_false,other_team_model_used_must_be_false,post_release_information_used_must_be_false,current_casp17_target_must_be_false,manifest_leakage_clearance_required,manifest_prediction_created_at_required,manifest_native_release_date_required,manifest_prediction_generated_before_native_release_required,manifest_public_template_or_native_used_for_prediction_required,manifest_other_team_model_used_required,manifest_post_release_information_used_required,manifest_current_casp17_target_required,manifest_operator_clearance_required,native_candidate_missing`

## Actions

| lane | field | artifact | action |
| --- | --- | --- | --- |
| `native_dropzone` | `native_pdb` | `casp17/competitive_floor_target_identity_clearance_workorders/H2324_T_Cell_Receptor_N17.2_complex_5_chains/native/H2324_native.pdb` | `Place an operator-cleared native protein PDB in the native dropzone; ensure it is distinct from the prediction and has valid ATOM coordinates.` |
| `no_leak_evidence` | `evidence_ref` | `casp17/competitive_floor_target_identity_clearance_workorders/H2324_T_Cell_Receptor_N17.2_complex_5_chains/provenance_template.csv` | `Create a local evidence file that names the target and no-leak review, then write that path into the provenance template evidence_ref field.` |
| `provenance_fields` | `provenance_template_required_fields` | `casp17/competitive_floor_target_identity_clearance_workorders/H2324_T_Cell_Receptor_N17.2_complex_5_chains/provenance_template.csv` | `Fill no-leak/operator clearance, prediction/native dates, and all true/false provenance confirmations in the provenance template.` |
| `manifest_stub_sync` | `manifest_stub_fields` | `casp17/competitive_floor_target_identity_clearance_workorders/H2324_T_Cell_Receptor_N17.2_complex_5_chains/manifest_stub.csv` | `After provenance is ready, sync the cleared provenance fields into the manifest stub and rerun the clearance cycle.` |

## Claim Boundary

CASP17 competitive-floor native/provenance operator packet only. It groups existing target-identity native dropzone, no-leak evidence, provenance, manifest, native-candidate, and metric-runway links for operator fill. It does not fetch native structures, clear no-leak provenance, copy coordinates, compute native accuracy, serialize a CASP author code, promote identities, mutate intake files, or submit to CASP.
