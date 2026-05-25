# CASP17 Competitive-Floor Target Identity Clearance Workorder Audit

- generated: `2026-05-26T03:04:46+09:00`
- clearance_workorder_audit_status: `blocked`
- clearance_workorder_status: `awaiting_native_or_provenance`
- audit pass/blocked/total: `0/3/3`
- prediction/native/provenance/manifest ready: `3/0/0/0`
- prediction protein atoms/coordinate-valid: `1855/3`
- native protein atoms/coordinate-valid: `0/0`
- identity discovery blockers blocked/cleared: `3/0`
- local evidence refs present/blocked/waiting: `0/3/0`
- local evidence content verified/blocked: `0/0`
- manifest/provenance matched/mismatches: `0/0`
- native/prediction distinct/same/waiting: `0/0/3`
- first blocked: `H1319` `blocked`
- next action: complete target-origin and no-leak evidence review before native/provenance promotion

## Audit Rows

| target | audit | native | atoms | protein atoms | chains | coordinates | identity blockers | prediction | pred atoms | pred protein atoms | pred chains | pred coordinates | provenance | evidence | evidence content | manifest | manifest/provenance | native/prediction | blockers | next action |
| --- | --- | --- | ---: | ---: | ---: | --- | --- | --- | ---: | ---: | ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `H1319` | `blocked` | `missing` | 0 | 0 | 0 | `waiting_on_native` | `blocked` | `present` | 497 | 497 | 3 | `valid` | `blocked` | `missing` | `waiting_on_evidence_ref` | `blocked` | `waiting_on_provenance` | `waiting_on_native` | `native_pdb_missing,identity_discovery_no_leak_clearance_required,operator_required,evidence_ref_required,leakage_clearance_required,operator_clearance_required,prediction_created_at_required_iso_date,native_release_date_required_iso_date,prediction_generated_before_native_release_required,public_template_or_native_used_for_prediction_must_be_false,other_team_model_used_must_be_false,post_release_information_used_must_be_false,current_casp17_target_must_be_false,manifest_native_pdb_not_found,manifest_leakage_clearance_required,manifest_prediction_created_at_required,manifest_native_release_date_required,manifest_prediction_generated_before_native_release_required,manifest_public_template_or_native_used_for_prediction_required,manifest_other_team_model_used_required,manifest_post_release_information_used_required,manifest_current_casp17_target_required,manifest_operator_clearance_required,manifest_waiting_on_provenance_template` | complete target-origin and no-leak evidence review before native/provenance promotion |
| `H1321` | `blocked` | `missing` | 0 | 0 | 0 | `waiting_on_native` | `blocked` | `present` | 502 | 502 | 3 | `valid` | `blocked` | `missing` | `waiting_on_evidence_ref` | `blocked` | `waiting_on_provenance` | `waiting_on_native` | `native_pdb_missing,identity_discovery_no_leak_clearance_required,operator_required,evidence_ref_required,leakage_clearance_required,operator_clearance_required,prediction_created_at_required_iso_date,native_release_date_required_iso_date,prediction_generated_before_native_release_required,public_template_or_native_used_for_prediction_must_be_false,other_team_model_used_must_be_false,post_release_information_used_must_be_false,current_casp17_target_must_be_false,manifest_native_pdb_not_found,manifest_leakage_clearance_required,manifest_prediction_created_at_required,manifest_native_release_date_required,manifest_prediction_generated_before_native_release_required,manifest_public_template_or_native_used_for_prediction_required,manifest_other_team_model_used_required,manifest_post_release_information_used_required,manifest_current_casp17_target_required,manifest_operator_clearance_required,manifest_waiting_on_provenance_template` | complete target-origin and no-leak evidence review before native/provenance promotion |
| `H2324` | `blocked` | `missing` | 0 | 0 | 0 | `waiting_on_native` | `blocked` | `present` | 856 | 856 | 5 | `valid` | `blocked` | `missing` | `waiting_on_evidence_ref` | `blocked` | `waiting_on_provenance` | `waiting_on_native` | `native_pdb_missing,identity_discovery_no_leak_clearance_required,operator_required,evidence_ref_required,leakage_clearance_required,operator_clearance_required,prediction_created_at_required_iso_date,native_release_date_required_iso_date,prediction_generated_before_native_release_required,public_template_or_native_used_for_prediction_must_be_false,other_team_model_used_must_be_false,post_release_information_used_must_be_false,current_casp17_target_must_be_false,manifest_native_pdb_not_found,manifest_leakage_clearance_required,manifest_prediction_created_at_required,manifest_native_release_date_required,manifest_prediction_generated_before_native_release_required,manifest_public_template_or_native_used_for_prediction_required,manifest_other_team_model_used_required,manifest_post_release_information_used_required,manifest_current_casp17_target_required,manifest_operator_clearance_required,manifest_waiting_on_provenance_template` | complete target-origin and no-leak evidence review before native/provenance promotion |

## Claim Boundary

Local competitive-floor target identity clearance workorder audit only. It verifies per-target native dropzones, local no-leak evidence references, provenance templates, and manifest stubs before any manual promotion. It does not fetch native structures, verify external URLs, clear no-leak provenance, choose historical targets, score native accuracy, mutate identity intake files, or submit to CASP.
