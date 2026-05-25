# CASP17 Competitive-Floor Identity Intake Bundle

- generated: `2026-05-26T00:14:39+09:00`
- identity_intake_status: `awaiting_identity`
- identity/readiness status: `awaiting_identity` `awaiting_identity`
- rows ready/awaiting/blocked: `0/15/0`
- missing fields: `60`
- file actions unlocked: `0`
- first open: `priority_001_REQUIRED_MONOMER_001` `awaiting_identity` missing `4`
- apply identity: `python3 tools/run_casp17_competitive_floor_identity_unlock_round.py --apply-identity`
- verify: `python3 tools/build_casp17_competitive_floor_execution_board.py && python3 tools/build_casp17_competitive_floor_readiness_gate.py`

## Intake Rows

| priority | dropzone | status | missing | current benchmark | current target | proposed benchmark | proposed target | evidence ref | clearance | next action |
| ---: | --- | --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| 1 | `priority_001_REQUIRED_MONOMER_001` | `awaiting_identity` | 4 | `hist_REQUIRED_MONOMER_001` | `REQUIRED_MONOMER_001` | `-` | `-` | `-` | `-` | fill proposed_benchmark_id, proposed_target_id, evidence_ref, operator_clearance |
| 2 | `priority_002_REQUIRED_MONOMER_002` | `awaiting_identity` | 4 | `hist_REQUIRED_MONOMER_002` | `REQUIRED_MONOMER_002` | `-` | `-` | `-` | `-` | fill proposed_benchmark_id, proposed_target_id, evidence_ref, operator_clearance |
| 3 | `priority_003_REQUIRED_MONOMER_003` | `awaiting_identity` | 4 | `hist_REQUIRED_MONOMER_003` | `REQUIRED_MONOMER_003` | `-` | `-` | `-` | `-` | fill proposed_benchmark_id, proposed_target_id, evidence_ref, operator_clearance |
| 4 | `priority_004_REQUIRED_MONOMER_004` | `awaiting_identity` | 4 | `hist_REQUIRED_MONOMER_004` | `REQUIRED_MONOMER_004` | `-` | `-` | `-` | `-` | fill proposed_benchmark_id, proposed_target_id, evidence_ref, operator_clearance |
| 5 | `priority_005_REQUIRED_MONOMER_005` | `awaiting_identity` | 4 | `hist_REQUIRED_MONOMER_005` | `REQUIRED_MONOMER_005` | `-` | `-` | `-` | `-` | fill proposed_benchmark_id, proposed_target_id, evidence_ref, operator_clearance |
| 6 | `priority_006_REQUIRED_MONOMER_006` | `awaiting_identity` | 4 | `hist_REQUIRED_MONOMER_006` | `REQUIRED_MONOMER_006` | `-` | `-` | `-` | `-` | fill proposed_benchmark_id, proposed_target_id, evidence_ref, operator_clearance |
| 7 | `priority_007_REQUIRED_MONOMER_007` | `awaiting_identity` | 4 | `hist_REQUIRED_MONOMER_007` | `REQUIRED_MONOMER_007` | `-` | `-` | `-` | `-` | fill proposed_benchmark_id, proposed_target_id, evidence_ref, operator_clearance |
| 8 | `priority_008_REQUIRED_MONOMER_008` | `awaiting_identity` | 4 | `hist_REQUIRED_MONOMER_008` | `REQUIRED_MONOMER_008` | `-` | `-` | `-` | `-` | fill proposed_benchmark_id, proposed_target_id, evidence_ref, operator_clearance |
| 9 | `priority_009_REQUIRED_MONOMER_009` | `awaiting_identity` | 4 | `hist_REQUIRED_MONOMER_009` | `REQUIRED_MONOMER_009` | `-` | `-` | `-` | `-` | fill proposed_benchmark_id, proposed_target_id, evidence_ref, operator_clearance |
| 10 | `priority_010_REQUIRED_MONOMER_010` | `awaiting_identity` | 4 | `hist_REQUIRED_MONOMER_010` | `REQUIRED_MONOMER_010` | `-` | `-` | `-` | `-` | fill proposed_benchmark_id, proposed_target_id, evidence_ref, operator_clearance |
| 11 | `priority_011_REQUIRED_COMPLEX_001` | `awaiting_identity` | 4 | `hist_REQUIRED_COMPLEX_001` | `REQUIRED_COMPLEX_001` | `-` | `-` | `-` | `-` | fill proposed_benchmark_id, proposed_target_id, evidence_ref, operator_clearance |
| 12 | `priority_012_REQUIRED_COMPLEX_002` | `awaiting_identity` | 4 | `hist_REQUIRED_COMPLEX_002` | `REQUIRED_COMPLEX_002` | `-` | `-` | `-` | `-` | fill proposed_benchmark_id, proposed_target_id, evidence_ref, operator_clearance |
| 13 | `priority_013_REQUIRED_COMPLEX_003` | `awaiting_identity` | 4 | `hist_REQUIRED_COMPLEX_003` | `REQUIRED_COMPLEX_003` | `-` | `-` | `-` | `-` | fill proposed_benchmark_id, proposed_target_id, evidence_ref, operator_clearance |
| 14 | `priority_014_REQUIRED_COMPLEX_004` | `awaiting_identity` | 4 | `hist_REQUIRED_COMPLEX_004` | `REQUIRED_COMPLEX_004` | `-` | `-` | `-` | `-` | fill proposed_benchmark_id, proposed_target_id, evidence_ref, operator_clearance |
| 15 | `priority_015_REQUIRED_COMPLEX_005` | `awaiting_identity` | 4 | `hist_REQUIRED_COMPLEX_005` | `REQUIRED_COMPLEX_005` | `-` | `-` | `-` | `-` | fill proposed_benchmark_id, proposed_target_id, evidence_ref, operator_clearance |

## Claim Boundary

Local competitive-floor identity intake bundle only. It exposes the operator-entered benchmark_id/target_id identity fields needed to unlock downstream file and value evidence plans. It does not choose historical targets, clear no-leak provenance, fetch native structures, score native accuracy, run predictors, mutate row_fill.csv, apply imports, or submit to CASP.
