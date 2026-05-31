# hist_REQUIRED_MONOMER_024 Evidence Quality Audit

- status: `awaiting_evidence_files`
- ready_for_quality_review: `false`
- required target: `REQUIRED_MONOMER_024`
- scope: `monomer`
- files present/missing/required: `0/6/6`
- pdb valid/invalid: `0/0`
- supporting valid/invalid: `0/0`
- prediction/native relation: `waiting_on_pdb_pair`
- blockers: `prediction_pdb:file_missing,native_pdb:file_missing,native_authority_ref:file_missing,no_leak_evidence_ref:file_missing,ablation_manifest_ref:file_missing,calibration_values_ref:file_missing`
- next action: place all six strict-blind evidence files in the dropzone and rerun dropzones/quality audit

## File Audits

| field | type | status | atoms | CA | sha256 | blocker | path |
| --- | --- | --- | ---: | ---: | --- | --- | --- |
| `prediction_pdb` | `pdb` | `missing` | 0 | 0 | `-` | `file_missing` | `casp17/historical_seed_strict_blind_replacement_evidence_dropzones/24_hist_required_monomer_024/prediction/replacement_prediction.pdb` |
| `native_pdb` | `pdb` | `missing` | 0 | 0 | `-` | `file_missing` | `casp17/historical_seed_strict_blind_replacement_evidence_dropzones/24_hist_required_monomer_024/native/replacement_native.pdb` |
| `native_authority_ref` | `text` | `missing` | 0 | 0 | `-` | `file_missing` | `casp17/historical_seed_strict_blind_replacement_evidence_dropzones/24_hist_required_monomer_024/authority/native_authority.md` |
| `no_leak_evidence_ref` | `text` | `missing` | 0 | 0 | `-` | `file_missing` | `casp17/historical_seed_strict_blind_replacement_evidence_dropzones/24_hist_required_monomer_024/no_leak/no_leak_evidence.md` |
| `ablation_manifest_ref` | `json` | `missing` | 0 | 0 | `-` | `file_missing` | `casp17/historical_seed_strict_blind_replacement_evidence_dropzones/24_hist_required_monomer_024/ablation/ablation_manifest.json` |
| `calibration_values_ref` | `json` | `missing` | 0 | 0 | `-` | `file_missing` | `casp17/historical_seed_strict_blind_replacement_evidence_dropzones/24_hist_required_monomer_024/calibration/calibration_values.json` |

## Claim Boundary

Local CASP17 strict-blind replacement evidence quality audit only. It validates whether dropzone evidence files are present, readable, structurally plausible, and prediction/native PDBs are distinct. It does not approve no-leak provenance, select replacement targets, import values into intake CSVs, compute CASP metrics, or submit to CASP.
