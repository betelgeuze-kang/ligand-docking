# CASP17 Competitive Floor Batch Native/Provenance Unlock Kit

- generated: `2026-06-02T06:17:16+09:00`
- status: `casp17_competitive_floor_batch_native_provenance_unlock_kit_ready_for_operator_fill`
- targets ready/blocked/total: `3/0/3`
- target ids: `H1319,H1321,H2324`
- fields per-target/total: `13/39`
- actions required/bundle: `12/12`
- packet/workorder/runway ready: `3/0/0`
- inputs prediction/ts/native-path/native-file/provenance/manifest/runway/workorder: `3/3/3/0/3/3/3/3`
- provenance/evidence/identity: `0/0/0`
- proof/author: `0/0`
- coordinate copies in kit: `0`
- first blocked: `H1319` `native_pdb_missing`
- batch folder: `casp17/competitive_floor_batch_native_provenance_unlock_kit`

## Targets

| target | status | fields | actions | native | provenance | evidence | identity |
| --- | --- | ---: | ---: | ---: | --- | --- | --- |
| `H1319` | `casp17_competitive_floor_first_native_provenance_unlock_kit_ready_for_operator_fill` | `13` | `4` | `0` | `false` | `false` | `false` |
| `H1321` | `casp17_competitive_floor_first_native_provenance_unlock_kit_ready_for_operator_fill` | `13` | `4` | `0` | `false` | `false` | `false` |
| `H2324` | `casp17_competitive_floor_first_native_provenance_unlock_kit_ready_for_operator_fill` | `13` | `4` | `0` | `false` | `false` | `false` |

## Claim Boundary

CASP17 competitive-floor batch native/provenance unlock operator kit only. It collects all blocked native/provenance target packets into one operator-fill workspace with per-target folders, a batch intake CSV, action matrix, and rerun commands. It does not fetch native structures, copy coordinates, fill or trust provenance, clear no-leak evidence, compute native accuracy, serialize a CASP author code, or submit to CASP.
