# CASP17 Strict-Blind Internal Prediction Source Gate

- generated: `2026-06-10T22:46:11+09:00`
- status: `awaiting_internal_prediction_source_gate_fields`
- required benchmark/target/scope: `hist_REQUIRED_MONOMER_001` `REQUIRED_MONOMER_001` `monomer`
- manifest rows: `1`
- checks pass/blocked/total: `3/13/16`
- manifest: `casp17/strict_blind_internal_prediction_source_audit/hist_REQUIRED_MONOMER_001/internal_prediction_source_manifest_template.csv`
- prediction/dropzone: `-` `casp17/historical_seed_strict_blind_replacement_evidence_dropzones/01_hist_required_monomer_001/prediction/replacement_prediction.pdb`
- first blocker: `source_id_internal` `internal_source_id_missing_or_external`

## Checks

| check | status | required | actual | blocker | next action |
| --- | --- | --- | --- | --- | --- |
| `manifest_exists` | `pass` | `one internal source manifest row` | `casp17/strict_blind_internal_prediction_source_audit/hist_REQUIRED_MONOMER_001/internal_prediction_source_manifest_template.csv` | `-` | - |
| `source_id_internal` | `blocked` | `non-official internal source_id` | `` | `internal_source_id_missing_or_external` | set source_id to an internal pre-native prediction source, not an official archive or MassiveFold pool |
| `target_id_present` | `pass` | `target_id present` | `REQUIRED_MONOMER_001` | `-` | - |
| `scope_matches` | `pass` | `monomer` | `monomer` | `-` | - |
| `manifest_prediction_pdb_present` | `blocked` | `prediction_pdb path` | `` | `prediction_pdb_missing` | point prediction_pdb at the verified internal prediction PDB |
| `manifest_prediction_pdb_exists` | `blocked` | `existing local prediction PDB` | `` | `prediction_pdb_not_found` | place the internal prediction PDB at the manifest path |
| `dropzone_prediction_pdb_exists` | `blocked` | `first-slot prediction dropzone PDB present` | `casp17/historical_seed_strict_blind_replacement_evidence_dropzones/01_hist_required_monomer_001/prediction/replacement_prediction.pdb` | `dropzone_prediction_pdb_missing` | copy the verified internal prediction PDB into the first-slot prediction dropzone |
| `prediction_pdb_has_atom_records` | `blocked` | `ATOM or HETATM records` | `` | `prediction_pdb_has_no_atom_records` | provide a structurally valid PDB with atom records |
| `prediction_created_at_present` | `blocked` | `ISO date` | `` | `prediction_created_at_missing_or_invalid` | enter a verifiable prediction creation date before native release |
| `native_release_date_present` | `blocked` | `ISO date` | `` | `native_release_date_missing_or_invalid` | enter the authoritative native public release date |
| `prediction_before_native` | `blocked` | `prediction_created_at < native_release_date` | `/` | `prediction_not_before_native` | use only prediction evidence created before the native structure was public |
| `native_authority_ref_present` | `blocked` | `native authority reference` | `` | `native_authority_ref_missing` | attach authoritative native source reference |
| `creation_evidence_ref_present` | `blocked` | `prediction creation evidence reference` | `` | `creation_evidence_ref_missing` | attach independent timestamp evidence for the internal prediction |
| `no_leak_evidence_ref_present` | `blocked` | `no-leak evidence reference` | `` | `no_leak_evidence_ref_missing` | attach no-leak provenance for the internal prediction source |
| `method_summary_present` | `blocked` | `method summary` | `` | `method_summary_missing` | summarize the internal prediction method and source package |
| `operator_clearance_present` | `blocked` | `operator clearance approved/clear` | `` | `operator_clearance_missing` | set operator_clearance after reviewing the prediction source and provenance |

Local CASP17 strict-blind internal prediction source gate only. It validates operator-provided manifest fields, prediction PDB presence, basic PDB atom records, chronology, no-leak evidence, and operator clearance for the first historical strict-blind slot. It does not create or copy prediction files, approve provenance, mutate strict-blind intake CSVs, compute CASP metrics, push remotes, or submit to CASP.
