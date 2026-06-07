# hist_REQUIRED_MONOMER_017 Strict-Blind Evidence Dropzone

- status: `awaiting_strict_blind_evidence_files`
- required target: `REQUIRED_MONOMER_017`
- scope: `monomer`
- files present/missing/required: `0/6/6`
- operator values required: `10`
- patch preview: `casp17/historical_seed_strict_blind_replacement_evidence_dropzones/17_hist_required_monomer_017/replacement_intake_patch_preview.csv`
- blockers: `missing_files:6,operator_values_required:10`
- next action: place strict-blind evidence files in this dropzone, then rerun dropzone and intake preflight

## Expected Evidence Files

| field | path | status |
| --- | --- | --- |
| `prediction_pdb` | `casp17/historical_seed_strict_blind_replacement_evidence_dropzones/17_hist_required_monomer_017/prediction/replacement_prediction.pdb` | `missing` |
| `native_pdb` | `casp17/historical_seed_strict_blind_replacement_evidence_dropzones/17_hist_required_monomer_017/native/replacement_native.pdb` | `missing` |
| `native_authority_ref` | `casp17/historical_seed_strict_blind_replacement_evidence_dropzones/17_hist_required_monomer_017/authority/native_authority.md` | `missing` |
| `no_leak_evidence_ref` | `casp17/historical_seed_strict_blind_replacement_evidence_dropzones/17_hist_required_monomer_017/no_leak/no_leak_evidence.md` | `missing` |
| `ablation_manifest_ref` | `casp17/historical_seed_strict_blind_replacement_evidence_dropzones/17_hist_required_monomer_017/ablation/ablation_manifest.json` | `missing` |
| `calibration_values_ref` | `casp17/historical_seed_strict_blind_replacement_evidence_dropzones/17_hist_required_monomer_017/calibration/calibration_values.json` | `missing` |

## Claim Boundary

Local CASP17 historical strict-blind replacement evidence dropzones only. It creates per-slot folders and patch previews for the files and operator values needed by the strict-blind replacement intake. It does not select replacement targets, create evidence, approve no-leak provenance, mutate intake CSVs, compute CASP metrics, or submit to CASP.
