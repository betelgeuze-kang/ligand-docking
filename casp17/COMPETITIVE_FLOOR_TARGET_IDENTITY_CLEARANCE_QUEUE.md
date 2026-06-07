# CASP17 Competitive-Floor Target Identity Clearance Queue

- generated: `2026-05-26T03:04:46+09:00`
- clearance_queue_status: `awaiting_target_identity_clearance`
- discovery_status: `review_required`
- review targets: `3`
- prediction/TS/native/provenance-cleared: `3/3/0/0`
- identity discovery blockers: `3`
- ready for manifest scaffold: `0`
- awaiting prediction/native-or-clearance/no-leak: `0/3/0`
- first open: `H1319` `awaiting_native_or_clearance`
- next action: provide a cleared native PDB and complete no-leak/operator provenance review

## Queue

| target | scope | clearance | identity blockers | prediction | TS | native | provenance | blockers | next action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `H1319` | `complex` | `awaiting_native_or_clearance` | `no_leak_clearance_required` | `present` | `present` | `missing` | `needs_operator_clearance` | `native_pdb_missing,no_leak_provenance_not_cleared,operator_clearance_required` | provide a cleared native PDB and complete no-leak/operator provenance review |
| `H1321` | `complex` | `awaiting_native_or_clearance` | `no_leak_clearance_required` | `present` | `present` | `missing` | `needs_operator_clearance` | `native_pdb_missing,no_leak_provenance_not_cleared,operator_clearance_required` | provide a cleared native PDB and complete no-leak/operator provenance review |
| `H2324` | `complex` | `awaiting_native_or_clearance` | `no_leak_clearance_required` | `present` | `present` | `missing` | `needs_operator_clearance` | `native_pdb_missing,no_leak_provenance_not_cleared,operator_clearance_required` | provide a cleared native PDB and complete no-leak/operator provenance review |

## Claim Boundary

Local competitive-floor target identity clearance queue only. It converts local target identity discoveries into operator clearance work items and checks local prediction/native/provenance files. It does not choose historical targets, clear no-leak provenance, fetch native structures, score native accuracy, mutate intake CSV files, or submit to CASP.
