# provenance dropzone

- dropzone_folder: `casp17/competitive_floor_batch_current/priority_008_REQUIRED_MONOMER_008/evidence_dropzone`
- class_folder: `casp17/competitive_floor_batch_current/priority_008_REQUIRED_MONOMER_008/evidence_dropzone/provenance`
- open actions: `10`

| column | blocker | drop path | note |
| --- | --- | --- | --- |
| `leakage_clearance` | `leakage_clearance_requires_no_leak_clearance` | `-` | record leakage_clearance only after no-leak provenance evidence supports it |
| `prediction_method` | `prediction_method_required` | `-` | record prediction_method only after no-leak provenance evidence supports it |
| `prediction_created_at` | `prediction_created_at_requires_iso_date` | `-` | record prediction_created_at only after no-leak provenance evidence supports it |
| `native_release_date` | `native_release_date_requires_iso_date` | `-` | record native_release_date only after no-leak provenance evidence supports it |
| `prediction_generated_before_native_release` | `prediction_before_native_release_confirmation_required` | `-` | record prediction_generated_before_native_release only after no-leak provenance evidence supports it |
| `public_template_or_native_used_for_prediction` | `public_template_or_native_used_for_prediction_must_be_false` | `-` | record public_template_or_native_used_for_prediction only after no-leak provenance evidence supports it |
| `other_team_model_used` | `other_team_model_used_must_be_false` | `-` | record other_team_model_used only after no-leak provenance evidence supports it |
| `post_release_information_used` | `post_release_information_used_must_be_false` | `-` | record post_release_information_used only after no-leak provenance evidence supports it |
| `current_casp17_target` | `current_casp17_target_must_be_false` | `-` | record current_casp17_target only after no-leak provenance evidence supports it |
| `operator_clearance` | `operator_clearance_requires_no_leak_clearance` | `-` | record operator_clearance only after no-leak provenance evidence supports it |

## Claim Boundary

Local competitive-floor evidence dropzone only. It creates per-row folders, manifests, and operator notes for placing no-leak historical benchmark evidence; it does not choose targets, fetch native structures, run predictors, clear provenance, score native accuracy, or submit to CASP.
