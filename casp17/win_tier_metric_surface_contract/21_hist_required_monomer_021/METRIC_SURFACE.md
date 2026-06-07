# hist_REQUIRED_MONOMER_021 Win-Tier Metric Surface

- status: `awaiting_strict_blind_evidence_files`
- target_id: `REQUIRED_MONOMER_021`
- scope: `monomer`
- prediction_pdb: `runs/casp17_historical_benchmark_predictions_current/REQUIRED_MONOMER_021_prediction.pdb`
- native_pdb: `runs/casp17_historical_benchmark_natives_current/REQUIRED_MONOMER_021_native.pdb`
- required/core/extension metrics: `11/6/5`
- official_archive_baseline_policy: `excluded_from_competitive_proof`
- blockers: `strict_blind_replacement_identity_required,core_files_required,no_leak_required,ablation_required,calibration_required,ablation_layer_prediction_pdb_missing,best_model_rank_required_1_to_5,best_native_metric_required_numeric,best_score_required_numeric,current_casp17_target_must_be_false,leakage_clearance_required,native_pdb_not_found,native_release_date_required_iso_date,operator_clearance_required,other_team_model_used_must_be_false,placeholder_target_id,post_release_information_used_must_be_false,prediction_created_at_required_iso_date,prediction_generated_before_native_release_required,prediction_pdb_not_found,public_template_or_native_used_for_prediction_must_be_false,selected_model_rank_required_1_to_5,selected_native_metric_required_numeric,selected_score_required_numeric,leakage_clearance_missing_or_not_clear,native_pdb_missing,prediction_pdb_missing`

## Metric Requirements

| metric | family | fit | output | status |
| --- | --- | --- | --- | --- |
| `GDT_TS` | `monomer_domain` | `scope_core_metric` | `casp17/win_tier_metric_surface_contract/21_hist_required_monomer_021/metrics/monomer/gdt_ts.json` | `awaiting_strict_blind_evidence_files` |
| `lDDT` | `monomer_domain` | `scope_core_metric` | `casp17/win_tier_metric_surface_contract/21_hist_required_monomer_021/metrics/monomer/lddt.json` | `awaiting_strict_blind_evidence_files` |
| `TM-score` | `monomer_domain` | `scope_core_metric` | `casp17/win_tier_metric_surface_contract/21_hist_required_monomer_021/metrics/monomer/tm_score.json` | `awaiting_strict_blind_evidence_files` |
| `RMSD` | `geometry` | `scope_core_metric` | `casp17/win_tier_metric_surface_contract/21_hist_required_monomer_021/metrics/geometry/rmsd.json` | `awaiting_strict_blind_evidence_files` |
| `GDT_HA` | `monomer_domain` | `scope_core_metric` | `casp17/win_tier_metric_surface_contract/21_hist_required_monomer_021/metrics/monomer/gdt_ha.json` | `awaiting_strict_blind_evidence_files` |
| `MolProbity` | `model_quality` | `scope_core_metric` | `casp17/win_tier_metric_surface_contract/21_hist_required_monomer_021/metrics/model_quality/molprobity.json` | `awaiting_strict_blind_evidence_files` |
| `DockQ` | `complex_interface` | `complex_or_interface_category_slot_required` | `casp17/win_tier_metric_surface_contract/21_hist_required_monomer_021/metrics/complex/dockq.json` | `awaiting_strict_blind_evidence_files` |
| `ICS` | `complex_interface` | `complex_or_interface_category_slot_required` | `casp17/win_tier_metric_surface_contract/21_hist_required_monomer_021/metrics/complex/ics.json` | `awaiting_strict_blind_evidence_files` |
| `IPS` | `complex_interface` | `complex_or_interface_category_slot_required` | `casp17/win_tier_metric_surface_contract/21_hist_required_monomer_021/metrics/complex/ips.json` | `awaiting_strict_blind_evidence_files` |
| `LDDT-PLI` | `ligand_pose` | `organic_ligand_category_slot_required` | `casp17/win_tier_metric_surface_contract/21_hist_required_monomer_021/metrics/ligand/lddt_pli.json` | `awaiting_strict_blind_evidence_files` |
| `BiSyRMSD` | `ligand_pose` | `organic_ligand_category_slot_required` | `casp17/win_tier_metric_surface_contract/21_hist_required_monomer_021/metrics/ligand/bisyrmsd.json` | `awaiting_strict_blind_evidence_files` |

## Claim Boundary

Local CASP17 win-tier metric-surface contract only. It creates per-slot metric input and output requirements for strict-blind historical replay. It does not compute official CASP scores, download large external model pools, import official archive submissions as internal predictions, or claim current CASP17 target accuracy.
