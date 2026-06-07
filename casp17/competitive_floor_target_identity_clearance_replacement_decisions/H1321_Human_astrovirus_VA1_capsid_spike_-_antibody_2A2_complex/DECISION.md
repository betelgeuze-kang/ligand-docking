# H1321 Replacement Decision

- decision_status: `open_operator_decision`
- candidate rows: `4`
- safe unique ready candidates: `0` `-`
- duplicate ready candidates: `1` `H1311`
- next_action: fill the new unique candidate intake template or explicitly approve duplicate candidate reuse with no-leak rationale, then rerun replacement workorders

## Decision Paths

- new unique candidate intake: `casp17/competitive_floor_target_identity_clearance_replacement_decisions/H1321_Human_astrovirus_VA1_capsid_spike_-_antibody_2A2_complex/new_unique_candidate_intake.csv`
- duplicate reuse exception: `casp17/competitive_floor_target_identity_clearance_replacement_decisions/H1321_Human_astrovirus_VA1_capsid_spike_-_antibody_2A2_complex/duplicate_reuse_exception.csv`

## Candidate Evidence

| rank | candidate | resolution | queue | source | blockers |
| ---: | --- | --- | --- | --- | --- |
| 1 | `H1311` NRAS17.3.2_Q61K_HLAA1 | `blocked_duplicate_candidate_assignment` | `candidate_ready_for_operator_clearance` | `source_ready` | `duplicate_candidate_target_id` |
| 2 | `H1332` Fab 047-09_1A02 binding influenza virus H1 HA Canceled - preprint. | `blocked_cancelled_target` | `blocked_missing_local_prediction` | `blocked_cancelled_target` | `local_prediction_missing,raw_validation_missing,scorecard_missing,target_cancelled,fasta_missing,blocked_cancelled_target,blocked_missing_local_prediction` |
| 3 | `T1313` P66 | `blocked_current_target_collision` | `blocked_current_target_collision` | `blocked_current_target_collision` | `current_target_name_collision,local_prediction_missing,raw_validation_missing,scorecard_missing,fasta_missing,blocked_current_target_collision` |
| 4 | `H1312` EXT1-EXT2-2BAV4 | `blocked_current_target_collision` | `blocked_current_target_collision` | `blocked_current_target_collision` | `current_target_name_collision,local_prediction_missing,raw_validation_missing,scorecard_missing,fasta_missing,blocked_current_target_collision` |

## Claim Boundary

Local CASP17 replacement decision bundle only. It creates operator-facing decision files for duplicate replacement blockers, including a new-unique-candidate intake template and a duplicate-reuse exception template. It does not choose a new target, approve duplicate reuse, fetch native structures, clear no-leak provenance, score native accuracy, mutate replacement workorders, or submit to CASP.
