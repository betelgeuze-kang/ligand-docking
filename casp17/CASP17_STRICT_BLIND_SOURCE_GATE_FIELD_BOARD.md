# CASP17 Strict-Blind Source Gate Field Board

- generated: `2026-06-01T02:51:17+09:00`
- status: `awaiting_source_gate_field_fills`
- required benchmark/target/scope: `hist_REQUIRED_MONOMER_001` `REQUIRED_MONOMER_001` `monomer`
- manifest: `casp17/strict_blind_internal_prediction_source_audit/hist_REQUIRED_MONOMER_001/internal_prediction_source_manifest_template.csv`
- source gate: `awaiting_internal_prediction_source_gate_fields` checks pass/blocked/total `3/13/16`
- field actions manifest/file/manifest-file/total: `9/2/0/11`
- blocked checks covered: `13`
- first field: `source_id` `manifest_value` `internal_source_id_missing_or_external`

## Field Actions

| field | kind | checks | blockers | destination | next action |
| --- | --- | --- | --- | --- | --- |
| `source_id` | `manifest_value` | `source_id_internal` | `internal_source_id_missing_or_external` | `casp17/strict_blind_internal_prediction_source_audit/hist_REQUIRED_MONOMER_001/internal_prediction_source_manifest_template.csv` | set source_id to an internal pre-native prediction source, not an official archive or MassiveFold pool |
| `prediction_pdb` | `file` | `manifest_prediction_pdb_present,manifest_prediction_pdb_exists,prediction_pdb_has_atom_records` | `prediction_pdb_missing,prediction_pdb_not_found,prediction_pdb_has_no_atom_records` | `` | point prediction_pdb at the verified internal prediction PDB; place the internal prediction PDB at the manifest path; provide a structurally valid PDB with atom records |
| `prediction_pdb_dropzone` | `file` | `dropzone_prediction_pdb_exists` | `dropzone_prediction_pdb_missing` | `casp17/historical_seed_strict_blind_replacement_evidence_dropzones/01_hist_required_monomer_001/prediction/replacement_prediction.pdb` | copy the verified internal prediction PDB into the first-slot prediction dropzone |
| `prediction_created_at` | `manifest_value` | `prediction_created_at_present` | `prediction_created_at_missing_or_invalid` | `casp17/strict_blind_internal_prediction_source_audit/hist_REQUIRED_MONOMER_001/internal_prediction_source_manifest_template.csv` | enter a verifiable prediction creation date before native release |
| `native_release_date` | `manifest_value` | `native_release_date_present` | `native_release_date_missing_or_invalid` | `casp17/strict_blind_internal_prediction_source_audit/hist_REQUIRED_MONOMER_001/internal_prediction_source_manifest_template.csv` | enter the authoritative native public release date |
| `prediction_created_at/native_release_date` | `manifest_value` | `prediction_before_native` | `prediction_not_before_native` | `casp17/strict_blind_internal_prediction_source_audit/hist_REQUIRED_MONOMER_001/internal_prediction_source_manifest_template.csv` | use only prediction evidence created before the native structure was public |
| `native_authority_ref` | `manifest_value` | `native_authority_ref_present` | `native_authority_ref_missing` | `casp17/strict_blind_internal_prediction_source_audit/hist_REQUIRED_MONOMER_001/internal_prediction_source_manifest_template.csv` | attach authoritative native source reference |
| `creation_evidence_ref` | `manifest_value` | `creation_evidence_ref_present` | `creation_evidence_ref_missing` | `casp17/strict_blind_internal_prediction_source_audit/hist_REQUIRED_MONOMER_001/internal_prediction_source_manifest_template.csv` | attach independent timestamp evidence for the internal prediction |
| `no_leak_evidence_ref` | `manifest_value` | `no_leak_evidence_ref_present` | `no_leak_evidence_ref_missing` | `casp17/strict_blind_internal_prediction_source_audit/hist_REQUIRED_MONOMER_001/internal_prediction_source_manifest_template.csv` | attach no-leak provenance for the internal prediction source |
| `method_summary` | `manifest_value` | `method_summary_present` | `method_summary_missing` | `casp17/strict_blind_internal_prediction_source_audit/hist_REQUIRED_MONOMER_001/internal_prediction_source_manifest_template.csv` | summarize the internal prediction method and source package |
| `operator_clearance` | `manifest_value` | `operator_clearance_present` | `operator_clearance_missing` | `casp17/strict_blind_internal_prediction_source_audit/hist_REQUIRED_MONOMER_001/internal_prediction_source_manifest_template.csv` | set operator_clearance after reviewing the prediction source and provenance |

Local CASP17 strict-blind source-gate field board only. It condenses internal prediction source-gate checks into unique field/file actions for the first strict-blind slot. It does not fill operator values, copy evidence files, approve provenance, compute CASP metrics, push remotes, or submit to CASP.
