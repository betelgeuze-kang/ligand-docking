# CASP17 Target Identity Clearance Replacement Source Repair

- generated: `2026-05-26T04:45:56+09:00`
- replacement_source_repair_status: `awaiting_sequence`
- candidates: `4`
- source-ready/predict/validate/sequence/cancelled/collision: `0/0/0/1/1/2`
- source repair docs: `4`
- first open: `H1311` `awaiting_sequence`
- first next action: provide reviewed FASTA before local prediction can be generated

## Candidate Repair Rows

| candidate | status | replace | fasta | prediction | validation | scorecard | blockers | next action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `H1311` | `awaiting_sequence` | `H1319;H1321` | `-` | `-` | `-` | `-` | `fasta_missing,local_prediction_missing,raw_validation_missing,scorecard_missing` | provide reviewed FASTA before local prediction can be generated |
| `H1312` | `blocked_current_target_collision` | `H1319;H1321` | `-` | `-` | `-` | `-` | `current_target_name_collision,fasta_missing,local_prediction_missing,raw_validation_missing,scorecard_missing` | choose a non-colliding replacement target or prove no current-target leakage |
| `H1332` | `blocked_cancelled_target` | `H1319;H1321` | `-` | `-` | `-` | `-` | `target_cancelled,fasta_missing,local_prediction_missing,raw_validation_missing,scorecard_missing` | exclude this replacement unless an operator explicitly reopens the canceled target rationale |
| `T1313` | `blocked_current_target_collision` | `H1319;H1321` | `-` | `-` | `-` | `-` | `current_target_name_collision,fasta_missing,local_prediction_missing,raw_validation_missing,scorecard_missing` | choose a non-colliding replacement target or prove no current-target leakage |

## Claim Boundary

Local CASP17 competitive-floor replacement source repair only. It decomposes replacement candidates into sequence, prediction, validation, scorecard, cancellation, and collision blockers before they can be considered for clearance. It does not invent sequences, fetch native structures, clear no-leak provenance, mutate workorders/operator intake, score native accuracy, choose final replacements, or submit to CASP.
