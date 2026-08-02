# Competition Benchmark Status

Machine-rendered status for the competition credibility evidence lane.
This document is generated from `runs/competition_benchmark_rollup_current.json`.

## Snapshot

| Field | Value |
| --- | --- |
| Rollup status | `competition_benchmark_rollup_ready` |
| Rollup artifact ready | `true` |
| Competition credibility evidence ready | `false` |
| Competition credibility evidence primary blocker | `casp16_ligand_materialization_not_ready` |
| Evidence role | `competition_credibility_evidence_only` |
| Operator action required | `true` |
| Blocker count | `6` |
| Next required step | Place operator-reviewed source/checksum/materialization/scorecard receipts outside committed raw-data paths, then rebuild this manifest. |
| Competition credibility extension ready | `false` |
| Ligand commercial claim allowed by competition rollup | `false` |
| Package B required for ligand commercial claims | `true` |
| GitHub raw-data policy ready | `false` |
| Raw data stored in repo | `true` |
| Raw-data-free evidence | `false` |
| Git-tracked raw-data files | `2802` |

## CAMEO Official Intake

| Field | Value |
| --- | --- |
| Intake gate | `cameo_official_results_intake_ready` |
| Intake ready | `true` |
| Result rows | `1` |
| Accepted / rejected | `1 / 0` |
| Fetch enabled | `false` |
| Local/native accuracy used | `false` |
| External state mutated | `false` |
| Primary blocker | `none` |

## CASP16 Ligand

| Field | Value |
| --- | --- |
| Source manifest | `blocked_casp16_ligand_competition_credibility` |
| Source manifest ready | `true` |
| Materialization ready | `false` |
| Scorecard ready | `false` |
| Competition credibility ready | `false` |
| Pose / affinity targets | `233 / 140` |
| Raw data committed | `false` |
| Raw data git-tracked files | `0` |
| Next action | Place operator-reviewed source/checksum/materialization/scorecard receipts outside committed raw-data paths, then rebuild this manifest. |

## BM5/CAPRI Complex

| Field | Value |
| --- | --- |
| Source manifest | `blocked_bm5_capri_complex_competition_credibility` |
| BM5 benchmark ready | `true` |
| CAPRI score set ready | `false` |
| Competition credibility ready | `false` |
| Raw data committed | `true` |
| Raw data git-tracked files | `2802` |
| Primary metric | `dockq_acceptable_rate_proxy` |
| Next action | Move BM5/CAPRI raw data out of git-tracked storage or replace it with source/checksum/materialization receipts before treating the complex benchmark as competition-credibility evidence. |

## Competition Extension Gate

| Field | Value |
| --- | --- |
| Ready | `false` |
| Blocker count | `4` |
| Primary blocker | `casp16_ligand_materialization_not_ready` |
| Blockers | `casp16_ligand_materialization_not_ready; casp16_ligand_scorecard_not_ready; capri_score_set_not_ready; bm5_capri_raw_data_committed_in_repo` |
| Custody work-order | `blocked_competition_benchmark_custody_work_order` |
| Custody work-order ready | `false` |
| Primary custody action | Place reviewed CASP16 ligand source/checksum/materialization/scorecard receipts in the configured receipt paths using the generated operator templates; keep raw target data outside committed files. |
| Primary raw-data custody action | Move BM5/CAPRI raw structures out of git-tracked storage, or replace the local checkout with source/checksum/materialization/scorecard receipts only. |
| Primary raw-data tracked files | `2802` |
| BM5/CAPRI untrack preflight | `bm5_capri_raw_data_untrack_apply_preflight_ready` |
| BM5/CAPRI untrack preflight ready | `true` |
| BM5/CAPRI untrack preflight receipt | `runs/bm5_capri_raw_data_untrack_apply_preflight_current.json` |
| BM5/CAPRI untrack generated candidates | `runs/bm5_capri_raw_data_untrack_candidates_current.txt` |
| BM5/CAPRI untrack reviewed template | `runs/bm5_capri_raw_data_reviewed_untrack_manifest_template_current.txt` |
| BM5/CAPRI untrack reviewed manifest | `OPERATOR_REVIEWED_BM5_CAPRI_RAW_DATA_UNTRACK_PATHS.txt` |
| BM5/CAPRI untrack candidate count | `2802` |
| BM5/CAPRI untrack candidates match plan | `true` |
| BM5/CAPRI untrack preview command | `python3 tools/apply_bm5_capri_raw_data_custody_plan.py --mode preview --untrack-candidates OPERATOR_REVIEWED_BM5_CAPRI_RAW_DATA_UNTRACK_PATHS.txt` |
| BM5/CAPRI untrack execute command | `python3 tools/apply_bm5_capri_raw_data_custody_plan.py --mode execute --untrack-candidates OPERATOR_REVIEWED_BM5_CAPRI_RAW_DATA_UNTRACK_PATHS.txt --approval-token APPROVE_BM5_CAPRI_RAW_DATA_UNTRACK` |
| BM5/CAPRI untrack approval token required | `APPROVE_BM5_CAPRI_RAW_DATA_UNTRACK` |
| CASP16 operator input schema ready | `true` |
| CASP16 operator templates written | `true` |
| CASP16 operator template artifacts | `runs/casp16_ligand_operator_source_manifest_template_current.csv;runs/casp16_ligand_operator_checksum_manifest_template_current.sha256;runs/casp16_ligand_operator_scorecard_rows_template_current.csv;runs/casp16_ligand_operator_receipt_fill_in_current.md` |

## GitHub Raw-Data Policy

| Field | Value |
| --- | --- |
| Ready | `false` |
| Raw-data blockers | `bm5_capri_raw_data_committed_in_repo` |
| Git-tracked raw-data files | `2802` |
| Allowed artifact classes | `source_manifests; checksum_manifests; materialization_manifests; scorecard_builders; scorecard_receipts; claim_boundary_docs` |
| Disallowed artifact classes | `raw_benchmark_payloads; raw_structure_archives; official_archive_models_as_internal_predictions` |
| Untrack preflight ready | `true` |
| Untrack preflight receipt | `runs/bm5_capri_raw_data_untrack_apply_preflight_current.json` |
| Untrack generated candidates | `runs/bm5_capri_raw_data_untrack_candidates_current.txt` |
| Untrack reviewed template | `runs/bm5_capri_raw_data_reviewed_untrack_manifest_template_current.txt` |
| Untrack reviewed manifest | `OPERATOR_REVIEWED_BM5_CAPRI_RAW_DATA_UNTRACK_PATHS.txt` |
| Untrack candidate count | `2802` |
| Untrack candidates match plan | `true` |
| Untrack preview command | `python3 tools/apply_bm5_capri_raw_data_custody_plan.py --mode preview --untrack-candidates OPERATOR_REVIEWED_BM5_CAPRI_RAW_DATA_UNTRACK_PATHS.txt` |
| Untrack execute command | `python3 tools/apply_bm5_capri_raw_data_custody_plan.py --mode execute --untrack-candidates OPERATOR_REVIEWED_BM5_CAPRI_RAW_DATA_UNTRACK_PATHS.txt --approval-token APPROVE_BM5_CAPRI_RAW_DATA_UNTRACK` |
| Required action | Keep raw benchmark payloads outside committed files; commit only source manifests, checksums, materialization manifests, scorecard builders, and claim-boundary docs. |

## Package B Bridge

| Field | Value |
| --- | --- |
| Public benchmark contract | `product_public_benchmark_contract_ready` |
| Ligand suites | `pdbbind_casf_pose_affinity; lit_pcba_virtual_screening; dude_z_decoy_smoke` |
| Public benchmark foundation ready | `true` |
| Claim-grade public benchmark ready | `false` |
| Claim-grade blockers | `insufficient_total_rows; insufficient_valid_rows; insufficient_pose_metric_pass_rows; insufficient_free_energy_pairs; free_energy_spearman_or_pair_gate_not_ready; fit_and_holdout_splits_required` |
| Ligand claim blockers | `casp16_ligand_competition_credibility_not_ready; package_b_claim_grade_public_benchmark_not_ready` |
| Bridge next action | Fill the work-order CSV from reviewed public provenance, run the apply command to validate row and aggregate readiness, then rerun with --write-intake only after the apply gate is ready. |

## Claim Boundary

Competition benchmark rollup only; aggregates local CAMEO and CASP competition-lane readiness. It does not submit predictions, fetch official pages, download CASP data, import official archive models as internal predictions, promote ligand docking commercial claims, or mutate external state. CASP16, CAPRI/BM5, and CAMEO are competition credibility evidence only; ligand commercial claims remain locked unless Package B public ligand benchmark evidence is separately claim-grade ready.

## Regeneration

```bash
python3 tools/build_competition_benchmark_rollup.py
python3 tools/build_architecture_validation_package_report.py
```
