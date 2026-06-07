# CASP17 Replacement Duplicate Resolution

- generated: `2026-05-28T01:17:31+09:00`
- duplicate_resolution_status: `operator_decision_required`
- duplicate targets: `1` `H1321`
- candidates/safe-unique/duplicate-ready: `4/0/1`
- blocked duplicate/cancelled/current-collision/missing-prediction: `1/1/2/3`
- first open: `H1321` -> `H1311` `blocked_duplicate_candidate_assignment`
- first next action: choose a new non-colliding closed protein replacement target or explicitly approve duplicate candidate reuse with no-leak rationale

## Candidate Resolution

| replace | rank | candidate | resolution | safe unique | queue | source | blockers | next action |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| `H1321` | 1 | `H1311` NRAS17.3.2_Q61K_HLAA1 | `blocked_duplicate_candidate_assignment` | `false` | `candidate_ready_for_operator_clearance` | `source_ready` | `duplicate_candidate_target_id` | choose a new non-colliding closed protein replacement target or explicitly approve duplicate candidate reuse with no-leak rationale |
| `H1321` | 2 | `H1332` Fab 047-09_1A02 binding influenza virus H1 HA Canceled - preprint. | `blocked_cancelled_target` | `false` | `blocked_missing_local_prediction` | `blocked_cancelled_target` | `local_prediction_missing,raw_validation_missing,scorecard_missing,target_cancelled,fasta_missing,blocked_cancelled_target,blocked_missing_local_prediction` | exclude this replacement unless an operator explicitly reopens the canceled target rationale |
| `H1321` | 3 | `T1313` P66 | `blocked_current_target_collision` | `false` | `blocked_current_target_collision` | `blocked_current_target_collision` | `current_target_name_collision,local_prediction_missing,raw_validation_missing,scorecard_missing,fasta_missing,blocked_current_target_collision` | choose a non-colliding replacement target or prove no current-target leakage |
| `H1321` | 4 | `H1312` EXT1-EXT2-2BAV4 | `blocked_current_target_collision` | `false` | `blocked_current_target_collision` | `blocked_current_target_collision` | `current_target_name_collision,local_prediction_missing,raw_validation_missing,scorecard_missing,fasta_missing,blocked_current_target_collision` | choose a non-colliding replacement target or prove no current-target leakage |

## Claim Boundary

Local CASP17 replacement duplicate-resolution packet only. It audits duplicate replacement workorder blockers against the replacement queue and source-repair packet, identifies whether a safe unique ready candidate exists, and leaves unsafe duplicate reuse fail-closed. It does not mutate replacement workorders, fetch native structures, clear no-leak provenance, score native accuracy, import rows into identity intake, or submit to CASP.
