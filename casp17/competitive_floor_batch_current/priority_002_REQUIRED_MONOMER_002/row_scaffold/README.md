# CASP17 Win-Tier Historical Benchmark Slot 2

- benchmark_id: `hist_REQUIRED_MONOMER_002`
- target_id: `REQUIRED_MONOMER_002`
- scope: `monomer`
- metric_profile: `TM,GDT_TS,CA_lDDT`
- current_status: `blocked`
- missing_evidence_items: `32`

## Stop Conditions

- Do not use a current CASP17 target native structure.
- Do not use public/template/native structures to create the prediction.
- Do not use other-team models.
- Do not use post-native-release information for prediction or model selection.
- Keep this slot blocked until the prediction date is before the native release date.

## Required Files

| role | template column | expected path |
| --- | --- | --- |
| `prediction_pdb` | `prediction_pdb` | `runs/casp17_historical_benchmark_predictions_current/REQUIRED_MONOMER_002_prediction.pdb` |
| `native_pdb` | `native_pdb` | `runs/casp17_historical_benchmark_natives_current/REQUIRED_MONOMER_002_native.pdb` |
| `ablation_recursive_prediction_pdb` | `recursive_prediction_pdb` | `runs/casp17_historical_ablation_predictions_current/recursive/REQUIRED_MONOMER_002TS.pdb` |
| `ablation_scored_prediction_pdb` | `scored_prediction_pdb` | `runs/casp17_historical_ablation_predictions_current/scored/REQUIRED_MONOMER_002TS.pdb` |
| `ablation_sidechain_scaffold_prediction_pdb` | `sidechain_scaffold_prediction_pdb` | `runs/casp17_historical_ablation_predictions_current/sidechain_scaffold/REQUIRED_MONOMER_002TS.pdb` |
| `ablation_sidechain_repacked_prediction_pdb` | `sidechain_repacked_prediction_pdb` | `runs/casp17_historical_ablation_predictions_current/sidechain_repacked/REQUIRED_MONOMER_002TS.pdb` |
| `ablation_sidechain_completed_prediction_pdb` | `sidechain_completed_prediction_pdb` | `runs/casp17_historical_ablation_predictions_current/sidechain_completed/REQUIRED_MONOMER_002TS.pdb` |
| `ablation_steric_relaxed_prediction_pdb` | `steric_relaxed_prediction_pdb` | `runs/casp17_historical_ablation_predictions_current/steric_relaxed/REQUIRED_MONOMER_002TS.pdb` |
| `ablation_rotamer_minimized_prediction_pdb` | `rotamer_minimized_prediction_pdb` | `runs/casp17_historical_ablation_predictions_current/rotamer_minimized/REQUIRED_MONOMER_002TS.pdb` |
| `ablation_polar_refined_prediction_pdb` | `polar_refined_prediction_pdb` | `runs/casp17_historical_ablation_predictions_current/polar_refined/REQUIRED_MONOMER_002TS.pdb` |
| `ablation_forcefield_minimized_prediction_pdb` | `forcefield_minimized_prediction_pdb` | `runs/casp17_historical_ablation_predictions_current/forcefield_minimized/REQUIRED_MONOMER_002TS.pdb` |
| `ablation_statistical_rotamer_prediction_pdb` | `statistical_rotamer_prediction_pdb` | `runs/casp17_historical_ablation_predictions_current/statistical_rotamer/REQUIRED_MONOMER_002TS.pdb` |

## Required Provenance Fields

| field | required value |
| --- | --- |
| `leakage_clearance` | `no_leak` or equivalent cleared value |
| `prediction_method` | internal method identifier |
| `prediction_created_at` | ISO date before native release |
| `native_release_date` | ISO date after prediction creation |
| `prediction_generated_before_native_release` | `true` |
| `public_template_or_native_used_for_prediction` | `false` |
| `other_team_model_used` | `false` |
| `post_release_information_used` | `false` |
| `current_casp17_target` | `false` |
| `operator_clearance` | `no_leak` or equivalent cleared value |

## After Filling This Slot

1. Update the operator template row with the real target ID, benchmark ID, file paths, provenance, and calibration values.
2. Run operator preflight/import so only ready no-leak rows are promoted.
3. Run historical benchmark, refinement-ablation, sidechain-native, and model-selection calibration packets.

This scaffold is local bookkeeping only. It does not fetch natives, score accuracy, use external predictors, or submit to CASP.
