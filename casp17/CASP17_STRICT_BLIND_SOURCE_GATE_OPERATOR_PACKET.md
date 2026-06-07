# CASP17 Strict-Blind Source Gate Operator Packet

- generated: `2026-06-01T03:04:13+09:00`
- status: `awaiting_source_gate_operator_values`
- required benchmark/target/scope: `hist_REQUIRED_MONOMER_001` `REQUIRED_MONOMER_001` `monomer`
- operator CSV: `casp17/strict_blind_source_gate_operator_packet/hist_REQUIRED_MONOMER_001/source_gate_operator_values.csv`
- manifest: `casp17/strict_blind_internal_prediction_source_audit/hist_REQUIRED_MONOMER_001/internal_prediction_source_manifest_template.csv`
- operator ready/awaiting/total: `0/11/11`
- patch ready/awaiting: `0/11`
- manifest/file/derived actions: `9/1/1`
- first field: `source_id` `awaiting_operator_value`

## Operator Fields

| field | kind | status | required format | next action |
| --- | --- | --- | --- | --- |
| `source_id` | `manifest_value` | `awaiting_operator_value` | internal source id; must not start official_archive/casp_official/massivefold_external | set source_id to an internal pre-native prediction source, not an official archive or MassiveFold pool |
| `prediction_pdb` | `file` | `awaiting_operator_value` | local pre-native prediction PDB path with ATOM/HETATM records | point prediction_pdb at the verified internal prediction PDB; place the internal prediction PDB at the manifest path; provide a structurally valid PDB with atom records |
| `prediction_pdb_dropzone` | `file` | `awaiting_file_copy` | first-slot prediction dropzone PDB copy path | copy the verified internal prediction PDB into the first-slot prediction dropzone |
| `prediction_created_at` | `manifest_value` | `awaiting_operator_value` | YYYY-MM-DD prediction creation date | enter a verifiable prediction creation date before native release |
| `native_release_date` | `manifest_value` | `awaiting_operator_value` | YYYY-MM-DD authoritative native release date | enter the authoritative native public release date |
| `prediction_created_at/native_release_date` | `manifest_value` | `awaiting_derived_date_order` | derived: prediction_created_at < native_release_date | use only prediction evidence created before the native structure was public |
| `native_authority_ref` | `manifest_value` | `awaiting_operator_value` | artifact path or URI for authoritative native source | attach authoritative native source reference |
| `creation_evidence_ref` | `manifest_value` | `awaiting_operator_value` | artifact path or URI for independent prediction timestamp evidence | attach independent timestamp evidence for the internal prediction |
| `no_leak_evidence_ref` | `manifest_value` | `awaiting_operator_value` | artifact path or URI for no-leak provenance evidence | attach no-leak provenance for the internal prediction source |
| `method_summary` | `manifest_value` | `awaiting_operator_value` | short internal prediction method/source summary | summarize the internal prediction method and source package |
| `operator_clearance` | `manifest_value` | `awaiting_operator_value` | approved/clear/cleared/true/yes/operator_clear/operator_approved | set operator_clearance after reviewing the prediction source and provenance |

Local CASP17 strict-blind source-gate operator packet only. It turns the first-slot source-gate field board into an operator-fill CSV and manifest patch preview. It preserves existing operator values, but it does not apply them to the manifest, copy files, approve provenance, compute CASP metrics, push remotes, or submit to CASP.
