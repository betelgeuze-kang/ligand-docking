# CASP17 Current Queue Rollover Hygiene Audit

- generated: `2026-06-03T00:38:35+09:00`
- status: `current_queue_rollover_hygiene_stale_generated_folders_retained`
- surfaces pass/stale/blocked/total: `0/3/0/3`
- active/actual folders: `35/73`
- missing/stale folders: `0/38`
- first stale: `current_upload_review_packet` `casp17/current_upload_review_packet/01_h2319_human_astrovirus_va1_capsid_spike_-_antibody_7c8_complex`

## Surfaces

| surface | status | active | actual | missing | stale | first stale | next action |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| `current_upload_review_packet` | `stale_generated_folders_retained` | 8 | 18 | 0 | 10 | `casp17/current_upload_review_packet/01_h2319_human_astrovirus_va1_capsid_spike_-_antibody_7c8_complex` | operator-approved cleanup may remove stale generated folders after confirming no decisions were entered |
| `current_upload_operator_decision_kit` | `stale_generated_folders_retained` | 8 | 18 | 0 | 10 | `casp17/current_upload_operator_decision_kit/01_h2319` | operator-approved cleanup may remove stale generated folders after confirming no decisions were entered |
| `current_post_native_scoring_scaffold` | `stale_generated_folders_retained` | 19 | 37 | 0 | 18 | `casp17/current_post_native_scoring_scaffold/01_h2319` | operator-approved cleanup may remove stale generated folders after confirming no decisions were entered |

## Claim Boundary

CASP17 current queue rollover hygiene audit only. It compares active manifest folder references against generated direct-child folders for current upload review, operator decision, and post-native scoring surfaces. It does not delete, move, archive, or clean folders, submit to CASP, serialize an author code, compute native accuracy, or mark strict-blind competitive proof.
