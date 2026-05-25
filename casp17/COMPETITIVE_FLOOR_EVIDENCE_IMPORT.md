# CASP17 Competitive-Floor Evidence Import

- generated: `2026-05-25T23:05:32+09:00`
- import_status: `ready_for_intake`
- apply_mode: `applied`
- import_csv: `/tmp/pytest-of-betelgeuze/pytest-70/test_evidence_import_apply_cop0/import.csv`
- rows/actions: `1/2`
- file/value actions: `1/1`
- ready copy/update/apply: `0/0/0`
- applied/copied/ledger-updated: `2/1/1`
- awaiting file/value/clearance/ref: `0/0/0/0`
- blocked: `0`
- first open: `priority_001_REQUIRED_MONOMER_001` `prediction_pdb` `copied_to_dropzone`
- next action: run this tool with --apply after review to copy the PDB into the dropzone

## Import Rows

| rank | dropzone | kind | class | column | status | source/proposed | destination | blocker |
| ---: | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `priority_001_REQUIRED_MONOMER_001` | `file` | `core_file` | `prediction_pdb` | `copied_to_dropzone` | `/tmp/pytest-of-betelgeuze/pytest-70/test_evidence_import_apply_cop0/T9001_prediction.pdb` | `/tmp/pytest-of-betelgeuze/pytest-70/test_evidence_import_apply_cop0/priority_001_REQUIRED_MONOMER_001/evidence_dropzone/files/core/T9001_prediction.pdb` | `-` |
| 2 | `priority_001_REQUIRED_MONOMER_001` | `value` | `target_identity` | `target_id` | `ledger_updated` | `T9001` | `/tmp/pytest-of-betelgeuze/pytest-70/test_evidence_import_apply_cop0/priority_001_REQUIRED_MONOMER_001/FIELD_VALUE_LEDGER.csv` | `-` |

## Claim Boundary

Local competitive-floor evidence import only. It creates and audits a single import CSV for cleared historical benchmark evidence, and optional --apply copies local PDB files into dropzones or updates FIELD_VALUE_LEDGER.csv rows. It does not choose targets, clear no-leak provenance, fetch native structures, score native accuracy, run predictors, mutate row_fill.csv, or submit to CASP.
