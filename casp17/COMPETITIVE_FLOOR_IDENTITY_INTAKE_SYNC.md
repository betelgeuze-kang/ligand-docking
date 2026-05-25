# CASP17 Competitive-Floor Identity Intake Sync

- generated: `2026-05-26T00:21:07+09:00`
- identity_intake_sync_status: `awaiting_intake`
- apply_mode: `dry_run`
- rows synced/ready/awaiting/blocked: `0/0/15/0`
- missing fields: `60`
- kit mismatches: `0`
- applied sync rows: `0`
- first open: `priority_001_REQUIRED_MONOMER_001` `awaiting_intake`
- next action: fill proposed_benchmark_id, proposed_target_id, evidence_ref, and operator_clearance in the intake bundle
- validate/apply command: `python3 tools/run_casp17_competitive_floor_identity_unlock_round.py --apply-identity`

## Sync Rows

| priority | dropzone | status | missing | mismatches | intake benchmark | intake target | kit benchmark | kit target | next action |
| ---: | --- | --- | ---: | ---: | --- | --- | --- | --- | --- |
| 1 | `priority_001_REQUIRED_MONOMER_001` | `awaiting_intake` | 4 | 0 | `-` | `-` | `-` | `-` | fill proposed_benchmark_id, proposed_target_id, evidence_ref, and operator_clearance in the intake bundle |
| 2 | `priority_002_REQUIRED_MONOMER_002` | `awaiting_intake` | 4 | 0 | `-` | `-` | `-` | `-` | fill proposed_benchmark_id, proposed_target_id, evidence_ref, and operator_clearance in the intake bundle |
| 3 | `priority_003_REQUIRED_MONOMER_003` | `awaiting_intake` | 4 | 0 | `-` | `-` | `-` | `-` | fill proposed_benchmark_id, proposed_target_id, evidence_ref, and operator_clearance in the intake bundle |
| 4 | `priority_004_REQUIRED_MONOMER_004` | `awaiting_intake` | 4 | 0 | `-` | `-` | `-` | `-` | fill proposed_benchmark_id, proposed_target_id, evidence_ref, and operator_clearance in the intake bundle |
| 5 | `priority_005_REQUIRED_MONOMER_005` | `awaiting_intake` | 4 | 0 | `-` | `-` | `-` | `-` | fill proposed_benchmark_id, proposed_target_id, evidence_ref, and operator_clearance in the intake bundle |
| 6 | `priority_006_REQUIRED_MONOMER_006` | `awaiting_intake` | 4 | 0 | `-` | `-` | `-` | `-` | fill proposed_benchmark_id, proposed_target_id, evidence_ref, and operator_clearance in the intake bundle |
| 7 | `priority_007_REQUIRED_MONOMER_007` | `awaiting_intake` | 4 | 0 | `-` | `-` | `-` | `-` | fill proposed_benchmark_id, proposed_target_id, evidence_ref, and operator_clearance in the intake bundle |
| 8 | `priority_008_REQUIRED_MONOMER_008` | `awaiting_intake` | 4 | 0 | `-` | `-` | `-` | `-` | fill proposed_benchmark_id, proposed_target_id, evidence_ref, and operator_clearance in the intake bundle |
| 9 | `priority_009_REQUIRED_MONOMER_009` | `awaiting_intake` | 4 | 0 | `-` | `-` | `-` | `-` | fill proposed_benchmark_id, proposed_target_id, evidence_ref, and operator_clearance in the intake bundle |
| 10 | `priority_010_REQUIRED_MONOMER_010` | `awaiting_intake` | 4 | 0 | `-` | `-` | `-` | `-` | fill proposed_benchmark_id, proposed_target_id, evidence_ref, and operator_clearance in the intake bundle |
| 11 | `priority_011_REQUIRED_COMPLEX_001` | `awaiting_intake` | 4 | 0 | `-` | `-` | `-` | `-` | fill proposed_benchmark_id, proposed_target_id, evidence_ref, and operator_clearance in the intake bundle |
| 12 | `priority_012_REQUIRED_COMPLEX_002` | `awaiting_intake` | 4 | 0 | `-` | `-` | `-` | `-` | fill proposed_benchmark_id, proposed_target_id, evidence_ref, and operator_clearance in the intake bundle |
| 13 | `priority_013_REQUIRED_COMPLEX_003` | `awaiting_intake` | 4 | 0 | `-` | `-` | `-` | `-` | fill proposed_benchmark_id, proposed_target_id, evidence_ref, and operator_clearance in the intake bundle |
| 14 | `priority_014_REQUIRED_COMPLEX_004` | `awaiting_intake` | 4 | 0 | `-` | `-` | `-` | `-` | fill proposed_benchmark_id, proposed_target_id, evidence_ref, and operator_clearance in the intake bundle |
| 15 | `priority_015_REQUIRED_COMPLEX_005` | `awaiting_intake` | 4 | 0 | `-` | `-` | `-` | `-` | fill proposed_benchmark_id, proposed_target_id, evidence_ref, and operator_clearance in the intake bundle |

## Claim Boundary

Local competitive-floor identity intake sync only. It copies operator-entered identity intake values into the identity unlock kit CSV when --apply is explicitly provided, so the existing identity validation/apply round can consume them. It does not choose targets, clear no-leak provenance, fetch native structures, score native accuracy, run predictors, mutate row_fill.csv, import evidence, or submit to CASP.
