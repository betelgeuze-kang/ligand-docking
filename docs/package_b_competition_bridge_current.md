# Package B Competition Bridge

Machine-rendered claim-boundary bridge for the competition benchmark lane.

## Snapshot

| Field | Value |
| --- | --- |
| Status | `package_b_competition_bridge_ready` |
| Bridge ready | `true` |
| Claim lock ready | `true` |
| Competition evidence role | `competition_credibility_evidence_only` |
| Competition rollup artifact ready | `true` |
| Competition credibility evidence ready | `false` |
| Ligand commercial claim allowed | `false` |
| Ligand commercial claim unlock ready | `false` |
| Ligand commercial claim unlock requires separate promotion gate | `true` |
| Ligand commercial claim unlock blockers | `competition_credibility_evidence_not_ready; github_raw_data_policy_not_ready; package_b_claim_grade_public_benchmark_not_ready; casp16_ligand_competition_credibility_not_ready` |
| Package B required | `true` |
| Package B claim-grade ready | `false` |
| GitHub raw-data policy ready | `false` |
| Raw data stored in repo | `true` |
| Raw-data-free evidence | `false` |
| Git-tracked raw payloads | `2802` |
| Bridge blockers | `none` |
| Ligand claim blockers | `casp16_ligand_competition_credibility_not_ready; package_b_claim_grade_public_benchmark_not_ready` |
| Next action | Fill the work-order CSV from reviewed public provenance, run the apply command to validate row and aggregate readiness, then rerun with --write-intake only after the apply gate is ready. |
| Next required step | Place operator-reviewed source/checksum/materialization/scorecard receipts outside committed raw-data paths, then rebuild this manifest. |

## GitHub-Safe Artifact Classes

| Class | Allowed |
| --- | --- |
| `source_manifests` | `true` |
| `checksum_manifests` | `true` |
| `materialization_manifests` | `true` |
| `scorecard_builders` | `true` |
| `scorecard_receipts` | `true` |
| `claim_boundary_docs` | `true` |
| `raw_benchmark_payloads` | `false` |

## Bridge Checks

| Check | Ready | Claim allowed | Blockers |
| --- | --- | --- | --- |
| `competition_rollup` | `true` | `false` | `casp16_ligand_materialization_not_ready; casp16_ligand_scorecard_not_ready; capri_score_set_not_ready; bm5_capri_raw_data_committed_in_repo; casp16_ligand_competition_credibility_not_ready; package_b_claim_grade_public_benchmark_not_ready` |
| `competition_credibility_evidence` | `false` | `false` | `casp16_ligand_materialization_not_ready; casp16_ligand_scorecard_not_ready; capri_score_set_not_ready; bm5_capri_raw_data_committed_in_repo` |
| `package_b_public_benchmark_contract` | `true` | `false` | `none` |
| `package_b_claim_grade_public_benchmark` | `false` | `false` | `insufficient_total_rows; insufficient_valid_rows; insufficient_pose_metric_pass_rows; insufficient_free_energy_pairs; free_energy_spearman_or_pair_gate_not_ready; fit_and_holdout_splits_required` |
| `competition_ligand_claim_gate` | `false` | `false` | `casp16_ligand_competition_credibility_not_ready; package_b_claim_grade_public_benchmark_not_ready` |
| `github_raw_data_policy` | `false` | `false` | `bm5_capri_raw_data_committed_in_repo` |

## Claim Boundary

Competition benchmark rollup only; aggregates local CAMEO and CASP competition-lane readiness. It does not submit predictions, fetch official pages, download CASP data, import official archive models as internal predictions, promote ligand docking commercial claims, or mutate external state. CASP16, CAPRI/BM5, and CAMEO are competition credibility evidence only; ligand commercial claims remain locked unless Package B public ligand benchmark evidence is separately claim-grade ready.
