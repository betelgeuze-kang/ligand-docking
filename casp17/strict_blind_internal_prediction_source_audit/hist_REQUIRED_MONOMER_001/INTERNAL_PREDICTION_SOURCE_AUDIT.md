# CASP17 Strict-Blind Internal Prediction Source Audit

- status: `internal_prediction_source_missing_for_first_slot`
- required benchmark/target/scope: `hist_REQUIRED_MONOMER_001` `REQUIRED_MONOMER_001` `monomer`
- local candidates eligible/total: `0/17`
- source routes allowed/total: `0/17`
- official baseline ready/blocked/total: `24/24/24`
- bridge native/internal-blocked/operator-only: `2/1/6`
- first blocker: `pre_native_internal_prediction_pdb_missing`
- next action: fill internal prediction source manifest and place verified PDB in first-slot dropzone

## Rows

| source | class | status | ready/blocked/total | allowed | proof use | next action |
| --- | --- | --- | --- | --- | --- | --- |
| `required_prediction_dropzone` | `first_slot_evidence` | `missing_internal_prediction_pdb` | `0/1/1` | `false` | required_internal_prediction_evidence | place a pre-native internal prediction PDB in the first-slot prediction dropzone |
| `local_candidate_inventory` | `local_internal_candidates` | `no_local_strict_blind_prediction_candidates` | `0/17/17` | `false` | internal_candidate_review_only_until_operator_clearance | promote only a candidate with pre-native prediction timestamp, no-leak evidence, ablation, and calibration |
| `first_slot_source_route` | `route_decision` | `first_slot_requires_pre_native_monomer_source_or_replacement` | `0/17/17` | `false` | route_gate_for_internal_prediction_source | source a pre-native prediction archive for this monomer or replace with a strict-blind monomer candidate |
| `official_archive_prediction_tarballs` | `external_baseline` | `blocked_external_other_team_baseline_only` | `24/24/24` | `false` | baseline_only_not_internal_competitive_proof | keep official archive predictions in baseline lane; do not use them as internal proof |
| `native_authority_source_bridge` | `native_authority_bridge` | `first_slot_source_bridge_internal_prediction_required` | `2/7/9` | `false` | native_authority_preview_only_until_internal_prediction_supplied | provide a pre-native internal prediction PDB; use official archive files only for native authority/baseline review |
| `operator_internal_source_manifest` | `operator_template` | `ready_for_operator_internal_source_entry` | `1/0/1` | `false` | template_only_not_evidence | fill this manifest with a verified pre-native internal prediction source before intake mutation |

Local CASP17 strict-blind internal prediction source audit only. It audits whether the first historical strict-blind slot has a pre-native internal prediction source and writes an operator manifest template. It does not create prediction PDBs, download official archive tarballs, reclassify external models as internal proof, approve no-leak provenance, mutate strict-blind intake CSVs, compute CASP metrics, push remotes, or submit to CASP.
