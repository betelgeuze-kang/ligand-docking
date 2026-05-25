# CASP17 Target Identity Clearance Replacement Source Repair

- generated: `2026-05-26T04:56:54+09:00`
- replacement_source_repair_status: `ready_for_validation_scorecard`
- candidates: `4`
- source-ready/predict/validate/sequence/cancelled/collision: `0/0/1/0/1/2`
- source repair docs: `4`
- first open: `H1311` `ready_for_validation_scorecard`
- first next action: run validation and scorecard generation for this candidate

## Candidate Repair Rows

| candidate | status | replace | fasta | prediction | validation | scorecard | blockers | next action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `H1311` | `ready_for_validation_scorecard` | `H1319;H1321` | `casp17/replacement_source_fasta/H1311.fasta` | `runs/casp17_prediction_jobs_current/H1311/H1311_model_1.pdb` | `runs/casp17_internal_physics_raw_validations_current/H1311_raw_confidence_calibration.json` | `-` | `scorecard_missing` | run validation and scorecard generation for this candidate |
| `H1312` | `blocked_current_target_collision` | `H1319;H1321` | `-` | `-` | `-` | `-` | `current_target_name_collision,fasta_missing,local_prediction_missing,raw_validation_missing,scorecard_missing` | choose a non-colliding replacement target or prove no current-target leakage |
| `H1332` | `blocked_cancelled_target` | `H1319;H1321` | `-` | `-` | `-` | `-` | `target_cancelled,fasta_missing,local_prediction_missing,raw_validation_missing,scorecard_missing` | exclude this replacement unless an operator explicitly reopens the canceled target rationale |
| `T1313` | `blocked_current_target_collision` | `H1319;H1321` | `-` | `-` | `-` | `-` | `current_target_name_collision,fasta_missing,local_prediction_missing,raw_validation_missing,scorecard_missing` | choose a non-colliding replacement target or prove no current-target leakage |

## Claim Boundary

Local CASP17 competitive-floor replacement source repair only. It decomposes replacement candidates into sequence, prediction, validation, scorecard, cancellation, and collision blockers before they can be considered for clearance. It does not invent sequences, fetch native structures, clear no-leak provenance, mutate workorders/operator intake, score native accuracy, choose final replacements, or submit to CASP.
