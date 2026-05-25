# CASP17 Competitive-Floor Target Identity Clearance Manifest Sync

- generated: `2026-05-26T02:17:04+09:00`
- clearance_manifest_sync_status: `awaiting_provenance`
- apply_mode: `dry_run`
- rows ready/awaiting/blocked/synced: `0/3/0/0`
- changed/applied fields: `0/0`
- first open: `H1319` `awaiting_provenance`
- next action: complete the no-leak provenance template before syncing the manifest stub

## Sync Rows

| target | status | provenance | manifest | changed | applied | blockers | next action |
| --- | --- | --- | --- | ---: | ---: | --- | --- |
| `H1319` | `awaiting_provenance` | `blocked` | `present` | 0 | 0 | `leakage_clearance_required,operator_clearance_required,prediction_created_at_required_iso_date,native_release_date_required_iso_date,prediction_generated_before_native_release_required,public_template_or_native_used_for_prediction_must_be_false,other_team_model_used_must_be_false,post_release_information_used_must_be_false,current_casp17_target_must_be_false` | complete the no-leak provenance template before syncing the manifest stub |
| `H1321` | `awaiting_provenance` | `blocked` | `present` | 0 | 0 | `leakage_clearance_required,operator_clearance_required,prediction_created_at_required_iso_date,native_release_date_required_iso_date,prediction_generated_before_native_release_required,public_template_or_native_used_for_prediction_must_be_false,other_team_model_used_must_be_false,post_release_information_used_must_be_false,current_casp17_target_must_be_false` | complete the no-leak provenance template before syncing the manifest stub |
| `H2324` | `awaiting_provenance` | `blocked` | `present` | 0 | 0 | `leakage_clearance_required,operator_clearance_required,prediction_created_at_required_iso_date,native_release_date_required_iso_date,prediction_generated_before_native_release_required,public_template_or_native_used_for_prediction_must_be_false,other_team_model_used_must_be_false,post_release_information_used_must_be_false,current_casp17_target_must_be_false` | complete the no-leak provenance template before syncing the manifest stub |

## Claim Boundary

Local competitive-floor target identity clearance manifest sync only. It copies already-cleared provenance fields into the matching per-target manifest stub when --apply is explicitly provided. It preserves prediction/native paths, does not fetch native structures, does not clear no-leak provenance, does not choose targets, does not score native accuracy, and does not submit to CASP.
