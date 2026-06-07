# CASP17 Competitive Floor Native/Provenance Operator Packet Completion Audit

- generated: `2026-06-02T05:39:27+09:00`
- status: `casp17_competitive_floor_native_provenance_operator_packet_completion_audit_pass`
- targets pass/blocked/total: `3/0/3`
- packet files folder/readme/manifest/actions/native-candidates: `3/3/3/3/3`
- action rows expected/csv/mismatch: `12/12/0`
- native candidates expected/csv/mismatch: `5/5/0`
- lanes native/evidence/provenance/manifest: `3/3/3/3`
- inputs prediction/ts/native-path/native-file/provenance/manifest/runway/workorder: `3/3/3/0/3/3/3/3`
- coordinate copies target/out-dir: `0/0`
- proof/author: `0/0`
- first blocked: `-`

## Targets

| target | status | packet | action rows | native candidates | native file | blockers |
| --- | --- | --- | ---: | ---: | ---: | --- |
| `H1319` | `pass` | `casp17/competitive_floor_native_provenance_operator_packet/H1319_Human_astrovirus_VA1_capsid_spike_antibody_7C8_complex` | `4/4` | `2/2` | `0` | `-` |
| `H1321` | `pass` | `casp17/competitive_floor_native_provenance_operator_packet/H1321_Human_astrovirus_VA1_capsid_spike_antibody_2A2_complex` | `4/4` | `2/2` | `0` | `-` |
| `H2324` | `pass` | `casp17/competitive_floor_native_provenance_operator_packet/H2324_T_Cell_Receptor_N17_2_complex_5_chains` | `4/4` | `1/1` | `0` | `-` |

## Claim Boundary

CASP17 competitive-floor native/provenance operator packet completion audit only. It verifies target packet folders, packet manifests, action and native-candidate CSVs, upstream input links, no-coordinate-copy hygiene, and proof boundary flags. It does not fetch native structures, clear no-leak provenance, compute native accuracy, serialize a CASP author code, or submit to CASP.
