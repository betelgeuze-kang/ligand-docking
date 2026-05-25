# CASP17 Competitive-Floor Target Identity Clearance Candidate Intake Sync

- generated: `2026-05-26T03:41:39+09:00`
- candidate_intake_sync_status: `waiting_on_staged_identity`
- apply_mode: `dry_run`
- rows ready/waiting/blocked/applied: `0/15/0/0`
- applied fields: `0`
- first open: `priority_001_REQUIRED_MONOMER_001` `waiting_on_staged_identity`
- next action: wait for clearance intake staging to produce staged_for_operator_review rows

## Sync Rows

| dropzone | scope | status | candidate status | live status | benchmark | target | blockers | next action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `priority_001_REQUIRED_MONOMER_001` | `monomer` | `waiting_on_staged_identity` | `awaiting_identity` | `awaiting_identity` | `-` | `-` | `candidate_identity_values_missing` | wait for clearance intake staging to produce staged_for_operator_review rows |
| `priority_002_REQUIRED_MONOMER_002` | `monomer` | `waiting_on_staged_identity` | `awaiting_identity` | `awaiting_identity` | `-` | `-` | `candidate_identity_values_missing` | wait for clearance intake staging to produce staged_for_operator_review rows |
| `priority_003_REQUIRED_MONOMER_003` | `monomer` | `waiting_on_staged_identity` | `awaiting_identity` | `awaiting_identity` | `-` | `-` | `candidate_identity_values_missing` | wait for clearance intake staging to produce staged_for_operator_review rows |
| `priority_004_REQUIRED_MONOMER_004` | `monomer` | `waiting_on_staged_identity` | `awaiting_identity` | `awaiting_identity` | `-` | `-` | `candidate_identity_values_missing` | wait for clearance intake staging to produce staged_for_operator_review rows |
| `priority_005_REQUIRED_MONOMER_005` | `monomer` | `waiting_on_staged_identity` | `awaiting_identity` | `awaiting_identity` | `-` | `-` | `candidate_identity_values_missing` | wait for clearance intake staging to produce staged_for_operator_review rows |
| `priority_006_REQUIRED_MONOMER_006` | `monomer` | `waiting_on_staged_identity` | `awaiting_identity` | `awaiting_identity` | `-` | `-` | `candidate_identity_values_missing` | wait for clearance intake staging to produce staged_for_operator_review rows |
| `priority_007_REQUIRED_MONOMER_007` | `monomer` | `waiting_on_staged_identity` | `awaiting_identity` | `awaiting_identity` | `-` | `-` | `candidate_identity_values_missing` | wait for clearance intake staging to produce staged_for_operator_review rows |
| `priority_008_REQUIRED_MONOMER_008` | `monomer` | `waiting_on_staged_identity` | `awaiting_identity` | `awaiting_identity` | `-` | `-` | `candidate_identity_values_missing` | wait for clearance intake staging to produce staged_for_operator_review rows |
| `priority_009_REQUIRED_MONOMER_009` | `monomer` | `waiting_on_staged_identity` | `awaiting_identity` | `awaiting_identity` | `-` | `-` | `candidate_identity_values_missing` | wait for clearance intake staging to produce staged_for_operator_review rows |
| `priority_010_REQUIRED_MONOMER_010` | `monomer` | `waiting_on_staged_identity` | `awaiting_identity` | `awaiting_identity` | `-` | `-` | `candidate_identity_values_missing` | wait for clearance intake staging to produce staged_for_operator_review rows |
| `priority_011_REQUIRED_COMPLEX_001` | `complex` | `waiting_on_staged_identity` | `awaiting_identity` | `awaiting_identity` | `-` | `-` | `candidate_identity_values_missing` | wait for clearance intake staging to produce staged_for_operator_review rows |
| `priority_012_REQUIRED_COMPLEX_002` | `complex` | `waiting_on_staged_identity` | `awaiting_identity` | `awaiting_identity` | `-` | `-` | `candidate_identity_values_missing` | wait for clearance intake staging to produce staged_for_operator_review rows |
| `priority_013_REQUIRED_COMPLEX_003` | `complex` | `waiting_on_staged_identity` | `awaiting_identity` | `awaiting_identity` | `-` | `-` | `candidate_identity_values_missing` | wait for clearance intake staging to produce staged_for_operator_review rows |
| `priority_014_REQUIRED_COMPLEX_004` | `complex` | `waiting_on_staged_identity` | `awaiting_identity` | `awaiting_identity` | `-` | `-` | `candidate_identity_values_missing` | wait for clearance intake staging to produce staged_for_operator_review rows |
| `priority_015_REQUIRED_COMPLEX_005` | `complex` | `waiting_on_staged_identity` | `awaiting_identity` | `awaiting_identity` | `-` | `-` | `candidate_identity_values_missing` | wait for clearance intake staging to produce staged_for_operator_review rows |

## Claim Boundary

Local competitive-floor target identity clearance candidate-intake sync only. It copies operator-reviewed candidate intake rows into the live identity intake CSV only when --apply is explicitly provided. It does not choose targets, clear provenance, fetch native structures, score native accuracy, mutate the identity unlock kit, import evidence, run predictors, or submit to CASP.
