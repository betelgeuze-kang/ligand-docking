# CASP17 Competitive Floor Native/Provenance Metric Unlock Bridge

- generated: `2026-06-02T05:51:38+09:00`
- status: `casp17_competitive_floor_native_provenance_metric_unlock_bridge_blocked_awaiting_operator_values`
- targets ready/blocked/total: `0/3/3`
- packet/workorder/runway ready: `3/0/0`
- metric requirements: `27`
- inputs prediction/ts/native-path/native-file/provenance-template/manifest/runway/workorder: `3/3/3/0/3/3/3/3`
- packet actions native/evidence/provenance/manifest/total: `3/3/3/3/12`
- native candidates blocked/no-candidate/total: `4/1/5`
- provenance/evidence/identity cleared: `0/0/0`
- proof/author: `0/0`
- first blocked: `H1319` `native_pdb_missing`

## Targets

| target | status | metrics | native | provenance | evidence | identity | next action |
| --- | --- | ---: | ---: | --- | --- | --- | --- |
| `H1319` | `blocked_awaiting_native_provenance_values` | `9` | `0` | `blocked` | `missing` | `blocked` | place operator-cleared native PDB in the native dropzone |
| `H1321` | `blocked_awaiting_native_provenance_values` | `9` | `0` | `blocked` | `missing` | `blocked` | place operator-cleared native PDB in the native dropzone |
| `H2324` | `blocked_awaiting_native_provenance_values` | `9` | `0` | `blocked` | `missing` | `blocked` | place operator-cleared native PDB in the native dropzone |

## Claim Boundary

CASP17 competitive-floor native/provenance metric unlock bridge only. It joins the target metric runway, native/provenance operator packet completion audit, and clearance workorder audit to show which operator values unlock native metric execution. It does not fetch native structures, fill operator values, clear no-leak provenance, compute native accuracy, serialize a CASP author code, or submit to CASP.
