# CASP17 Strict-Blind Internal Prediction Source Gate

- generated: `2026-06-10T23:18:19+09:00`
- status: `internal_prediction_source_ready_for_first_slot_dropzone`
- required benchmark/target/scope: `hist_REQUIRED_MONOMER_001` `REQUIRED_MONOMER_001` `monomer`
- manifest rows: `1`
- checks pass/blocked/total: `16/0/16`
- manifest: `casp17/strict_blind_internal_prediction_source_audit/hist_REQUIRED_MONOMER_001/internal_prediction_source_manifest_template.csv`
- prediction/dropzone: `casp17/historical_seed_strict_blind_replacement_evidence_dropzones/01_hist_required_monomer_001/prediction/replacement_prediction.pdb` `casp17/historical_seed_strict_blind_replacement_evidence_dropzones/01_hist_required_monomer_001/prediction/replacement_prediction.pdb`
- first blocker: `-` `-`

## Checks

| check | status | required | actual | blocker | next action |
| --- | --- | --- | --- | --- | --- |
| `manifest_exists` | `pass` | `one internal source manifest row` | `casp17/strict_blind_internal_prediction_source_audit/hist_REQUIRED_MONOMER_001/internal_prediction_source_manifest_template.csv` | `-` | - |
| `source_id_internal` | `pass` | `non-official internal source_id` | `internal_pre_native_run_001` | `-` | - |
| `target_id_present` | `pass` | `target_id present` | `REQUIRED_MONOMER_001` | `-` | - |
| `scope_matches` | `pass` | `monomer` | `monomer` | `-` | - |
| `manifest_prediction_pdb_present` | `pass` | `prediction_pdb path` | `casp17/historical_seed_strict_blind_replacement_evidence_dropzones/01_hist_required_monomer_001/prediction/replacement_prediction.pdb` | `-` | - |
| `manifest_prediction_pdb_exists` | `pass` | `existing local prediction PDB` | `casp17/historical_seed_strict_blind_replacement_evidence_dropzones/01_hist_required_monomer_001/prediction/replacement_prediction.pdb` | `-` | - |
| `dropzone_prediction_pdb_exists` | `pass` | `first-slot prediction dropzone PDB present` | `casp17/historical_seed_strict_blind_replacement_evidence_dropzones/01_hist_required_monomer_001/prediction/replacement_prediction.pdb` | `-` | - |
| `prediction_pdb_has_atom_records` | `pass` | `ATOM or HETATM records` | `casp17/historical_seed_strict_blind_replacement_evidence_dropzones/01_hist_required_monomer_001/prediction/replacement_prediction.pdb` | `-` | - |
| `prediction_created_at_present` | `pass` | `ISO date` | `2024-06-03` | `-` | - |
| `native_release_date_present` | `pass` | `ISO date` | `2025-02-01` | `-` | - |
| `prediction_before_native` | `pass` | `prediction_created_at < native_release_date` | `2024-06-03/2025-02-01` | `-` | - |
| `native_authority_ref_present` | `pass` | `native authority reference` | `rcsb:9b0l` | `-` | - |
| `creation_evidence_ref_present` | `pass` | `prediction creation evidence reference` | `casp17/strict_blind_internal_prediction_source_audit/hist_REQUIRED_MONOMER_001/evidence/timestamp.md` | `-` | - |
| `no_leak_evidence_ref_present` | `pass` | `no-leak evidence reference` | `casp17/strict_blind_internal_prediction_source_audit/hist_REQUIRED_MONOMER_001/evidence/no_leak.md` | `-` | - |
| `method_summary_present` | `pass` | `method summary` | `internal pre-native prediction package for first strict-blind slot` | `-` | - |
| `operator_clearance_present` | `pass` | `operator clearance approved/clear` | `approved` | `-` | - |

Local CASP17 strict-blind internal prediction source gate only. It validates operator-provided manifest fields, prediction PDB presence, basic PDB atom records, chronology, no-leak evidence, and operator clearance for the first historical strict-blind slot. It does not create or copy prediction files, approve provenance, mutate strict-blind intake CSVs, compute CASP metrics, push remotes, or submit to CASP.
