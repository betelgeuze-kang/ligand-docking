# CASP17 Replacement Clearance Pickup Packet

- generated: `2026-05-28T01:02:26+09:00`
- replacement_pickup_status: `open_actions`
- selected/ready/awaiting/blocked-selection: `1/0/1/1`
- native missing: `1`
- required provenance fields: `11`
- operator actions: `4`
- first open: `H1319` -> `H1311`
- first open next action: place the cleared native PDB in the native dropzone

## Pickup Rows

| replace target | candidate target | pickup | native | required fields | actions | pickup md | next action | blockers |
| --- | --- | --- | --- | ---: | ---: | --- | --- | --- |
| `H1319` | `H1311` | `awaiting_operator_pickup` | `missing` | 11 | 3 | `casp17/competitive_floor_target_identity_clearance_replacement_workorders/H1319_to_H1311_NRAS17.3.2_Q61K_HLAA1/OPERATOR_PICKUP.md` | place the cleared native PDB in the native dropzone | `native_pdb_missing,operator_required,evidence_ref_required,leakage_clearance_required,operator_clearance_required,prediction_created_at_required_iso_date,native_release_date_required_iso_date,prediction_generated_before_native_release_required,public_template_or_native_used_for_prediction_must_be_false,other_team_model_used_must_be_false,post_release_information_used_must_be_false,current_casp17_target_must_be_false,manifest_native_pdb_not_found,manifest_leakage_clearance_required,manifest_prediction_created_at_required,manifest_native_release_date_required,manifest_prediction_generated_before_native_release_required,manifest_public_template_or_native_used_for_prediction_required,manifest_other_team_model_used_required,manifest_post_release_information_used_required,manifest_current_casp17_target_required,manifest_operator_clearance_required,manifest_waiting_on_provenance_template` |
| `H1321` | `H1311` | `blocked_duplicate_candidate_assignment` | `missing` | 0 | 1 | `-` | choose a different ready replacement candidate before materializing this workorder | `native_dropzone_path_missing,identity_discovery_duplicate_candidate_target_id,csv_path_missing` |

## Claim Boundary

Local CASP17 replacement clearance pickup packet only. It consolidates already-materialized replacement workorders, native dropzones, provenance templates, manifest stubs, and audit blockers for operator execution. It does not fetch native structures, clear no-leak provenance, choose final targets, score native accuracy, mutate live intake files, or submit to CASP.
