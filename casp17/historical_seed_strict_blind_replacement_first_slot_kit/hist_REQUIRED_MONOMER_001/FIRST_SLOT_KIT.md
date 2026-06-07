# hist_REQUIRED_MONOMER_001 First Slot Kit

- generated: `2026-05-31T17:00:32+09:00`
- status: `awaiting_first_slot_evidence_files`
- benchmark/target/scope: `hist_REQUIRED_MONOMER_001` `REQUIRED_MONOMER_001` `monomer`
- evidence ready/open/blocked/total: `0/6/0/6`
- operator ready/open/blocked/total: `0/10/0/10`
- operator open value/evidence/clearance: `10/10/10`
- cycle: `awaiting_evidence_files` first stage `evidence_dropzones`
- kit folder: `casp17/historical_seed_strict_blind_replacement_first_slot_kit/hist_REQUIRED_MONOMER_001`
- first open: `evidence_file` `strict_blind_evidence_001` `prediction_pdb` `open_missing_file`
- next action: place prediction_pdb evidence at casp17/historical_seed_strict_blind_replacement_evidence_dropzones/01_hist_required_monomer_001/prediction/replacement_prediction.pdb

## Checklist

| group | action | field | status | source/operator file | next action |
| --- | --- | --- | --- | --- | --- |
| `evidence_file` | `strict_blind_evidence_001` | `prediction_pdb` | `open_missing_file` | `casp17/historical_seed_strict_blind_replacement_evidence_dropzones/01_hist_required_monomer_001/prediction/replacement_prediction.pdb` | place prediction_pdb evidence at casp17/historical_seed_strict_blind_replacement_evidence_dropzones/01_hist_required_monomer_001/prediction/replacement_prediction.pdb |
| `evidence_file` | `strict_blind_evidence_002` | `native_pdb` | `open_missing_file` | `casp17/historical_seed_strict_blind_replacement_evidence_dropzones/01_hist_required_monomer_001/native/replacement_native.pdb` | place native_pdb evidence at casp17/historical_seed_strict_blind_replacement_evidence_dropzones/01_hist_required_monomer_001/native/replacement_native.pdb |
| `evidence_file` | `strict_blind_evidence_003` | `native_authority_ref` | `open_missing_file` | `casp17/historical_seed_strict_blind_replacement_evidence_dropzones/01_hist_required_monomer_001/authority/native_authority.md` | place native_authority_ref evidence at casp17/historical_seed_strict_blind_replacement_evidence_dropzones/01_hist_required_monomer_001/authority/native_authority.md |
| `evidence_file` | `strict_blind_evidence_004` | `no_leak_evidence_ref` | `open_missing_file` | `casp17/historical_seed_strict_blind_replacement_evidence_dropzones/01_hist_required_monomer_001/no_leak/no_leak_evidence.md` | place no_leak_evidence_ref evidence at casp17/historical_seed_strict_blind_replacement_evidence_dropzones/01_hist_required_monomer_001/no_leak/no_leak_evidence.md |
| `evidence_file` | `strict_blind_evidence_005` | `ablation_manifest_ref` | `open_missing_file` | `casp17/historical_seed_strict_blind_replacement_evidence_dropzones/01_hist_required_monomer_001/ablation/ablation_manifest.json` | place ablation_manifest_ref evidence at casp17/historical_seed_strict_blind_replacement_evidence_dropzones/01_hist_required_monomer_001/ablation/ablation_manifest.json |
| `evidence_file` | `strict_blind_evidence_006` | `calibration_values_ref` | `open_missing_file` | `casp17/historical_seed_strict_blind_replacement_evidence_dropzones/01_hist_required_monomer_001/calibration/calibration_values.json` | place calibration_values_ref evidence at casp17/historical_seed_strict_blind_replacement_evidence_dropzones/01_hist_required_monomer_001/calibration/calibration_values.json |
| `operator_value` | `strict_blind_operator_001` | `replacement_target_id` | `open_operator_value` | `casp17/historical_seed_strict_blind_replacement_intake/01_hist_required_monomer_001/replacement_operator_values.csv` | fill operator_value for replacement_target_id in replacement_operator_values.csv |
| `operator_value` | `strict_blind_operator_002` | `replacement_benchmark_id` | `open_operator_value` | `casp17/historical_seed_strict_blind_replacement_intake/01_hist_required_monomer_001/replacement_operator_values.csv` | fill operator_value for replacement_benchmark_id in replacement_operator_values.csv |
| `operator_value` | `strict_blind_operator_003` | `target_identity_non_current_historical` | `open_operator_value` | `casp17/historical_seed_strict_blind_replacement_intake/01_hist_required_monomer_001/replacement_operator_values.csv` | fill operator_value for target_identity_non_current_historical in replacement_operator_values.csv |
| `operator_value` | `strict_blind_operator_004` | `prediction_created_at` | `open_operator_value` | `casp17/historical_seed_strict_blind_replacement_intake/01_hist_required_monomer_001/replacement_operator_values.csv` | fill operator_value for prediction_created_at in replacement_operator_values.csv |
| `operator_value` | `strict_blind_operator_005` | `native_release_date` | `open_operator_value` | `casp17/historical_seed_strict_blind_replacement_intake/01_hist_required_monomer_001/replacement_operator_values.csv` | fill operator_value for native_release_date in replacement_operator_values.csv |
| `operator_value` | `strict_blind_operator_006` | `prediction_generated_before_native_release` | `open_operator_value` | `casp17/historical_seed_strict_blind_replacement_intake/01_hist_required_monomer_001/replacement_operator_values.csv` | fill operator_value for prediction_generated_before_native_release in replacement_operator_values.csv |
| `operator_value` | `strict_blind_operator_007` | `public_template_or_native_used_for_prediction` | `open_operator_value` | `casp17/historical_seed_strict_blind_replacement_intake/01_hist_required_monomer_001/replacement_operator_values.csv` | fill operator_value for public_template_or_native_used_for_prediction in replacement_operator_values.csv |
| `operator_value` | `strict_blind_operator_008` | `other_team_model_used` | `open_operator_value` | `casp17/historical_seed_strict_blind_replacement_intake/01_hist_required_monomer_001/replacement_operator_values.csv` | fill operator_value for other_team_model_used in replacement_operator_values.csv |
| `operator_value` | `strict_blind_operator_009` | `post_release_information_used` | `open_operator_value` | `casp17/historical_seed_strict_blind_replacement_intake/01_hist_required_monomer_001/replacement_operator_values.csv` | fill operator_value for post_release_information_used in replacement_operator_values.csv |
| `operator_value` | `strict_blind_operator_010` | `operator_clearance` | `open_operator_value` | `casp17/historical_seed_strict_blind_replacement_intake/01_hist_required_monomer_001/replacement_operator_values.csv` | fill operator_value for operator_clearance in replacement_operator_values.csv |

## Verification

- `python3 tools/build_casp17_historical_seed_strict_blind_replacement_evidence_quality_audit.py`
- `python3 tools/build_casp17_historical_seed_strict_blind_replacement_operator_value_gate.py`

## Claim Boundary

Local CASP17 first-slot strict-blind replacement kit only. It narrows the current first open replacement slot into the evidence files and operator values that must be supplied before quality, import, and promotion gates can move. It does not create evidence, select targets, approve no-leak provenance, compute CASP metrics, mutate intake CSVs, or submit to CASP.
