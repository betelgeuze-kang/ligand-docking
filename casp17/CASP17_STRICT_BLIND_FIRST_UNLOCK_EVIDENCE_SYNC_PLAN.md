# CASP17 Strict-Blind First Unlock Evidence Sync Plan

- generated: `2026-06-01T21:25:41+09:00`
- status: `awaiting_first_unlock_evidence_review`
- mode: `dry_run`
- review gate: `awaiting_first_unlock_evidence_review`
- request/target: `source_request_001` `HIST_BBA5`
- actions ready/blocked/applied/total: `0/11/0/11`
- review ready/blocked fields: `0/11`
- destination: `casp17/strict_blind_source_gate_operator_packet/hist_REQUIRED_MONOMER_001/source_gate_operator_values.csv`
- first blocker: `first_unlock_evidence_sync_001` `source_id` `template_operator_value_missing`
- next action: complete first-unlock evidence review before syncing into the source gate

## Actions

| action | status | field | source value | current value | blocker | next action |
| --- | --- | --- | --- | --- | --- | --- |
| `first_unlock_evidence_sync_001` | `blocked_review_gate_not_ready` | `source_id` | `-` | `-` | `template_operator_value_missing` | complete first-unlock evidence review before syncing into the source gate |
| `first_unlock_evidence_sync_002` | `blocked_review_gate_not_ready` | `prediction_pdb` | `-` | `-` | `template_operator_value_missing` | complete first-unlock evidence review before syncing into the source gate |
| `first_unlock_evidence_sync_003` | `blocked_review_gate_not_ready` | `prediction_pdb_dropzone` | `-` | `casp17/historical_seed_strict_blind_replacement_evidence_dropzones/01_hist_required_monomer_001/prediction/replacement_prediction.pdb` | `template_operator_value_missing` | complete first-unlock evidence review before syncing into the source gate |
| `first_unlock_evidence_sync_004` | `blocked_review_gate_not_ready` | `prediction_created_at` | `-` | `-` | `template_operator_value_missing` | complete first-unlock evidence review before syncing into the source gate |
| `first_unlock_evidence_sync_005` | `blocked_review_gate_not_ready` | `native_release_date` | `-` | `-` | `template_operator_value_missing` | complete first-unlock evidence review before syncing into the source gate |
| `first_unlock_evidence_sync_006` | `blocked_review_gate_not_ready` | `prediction_created_at/native_release_date` | `-` | `/` | `template_operator_value_missing` | complete first-unlock evidence review before syncing into the source gate |
| `first_unlock_evidence_sync_007` | `blocked_review_gate_not_ready` | `native_authority_ref` | `-` | `-` | `template_operator_value_missing` | complete first-unlock evidence review before syncing into the source gate |
| `first_unlock_evidence_sync_008` | `blocked_review_gate_not_ready` | `creation_evidence_ref` | `-` | `-` | `template_operator_value_missing` | complete first-unlock evidence review before syncing into the source gate |
| `first_unlock_evidence_sync_009` | `blocked_review_gate_not_ready` | `no_leak_evidence_ref` | `-` | `-` | `template_operator_value_missing` | complete first-unlock evidence review before syncing into the source gate |
| `first_unlock_evidence_sync_010` | `blocked_review_gate_not_ready` | `method_summary` | `-` | `-` | `template_operator_value_missing` | complete first-unlock evidence review before syncing into the source gate |
| `first_unlock_evidence_sync_011` | `blocked_review_gate_not_ready` | `operator_clearance` | `-` | `-` | `template_operator_value_missing` | complete first-unlock evidence review before syncing into the source gate |

## Claim Boundary

Local CASP17 strict-blind first-unlock evidence sync plan only. It maps reviewed first-unlock operator evidence into the source-gate operator CSV, using dry-run by default. It does not approve provenance, copy prediction files, mutate source manifests, compute CASP metrics, push remotes, or submit to CASP.
