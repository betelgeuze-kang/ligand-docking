# Post-P0 Commercial Expansion Queue

## Purpose

This queue starts after the current restricted `kinase`, `ion_channel`, and `gpcr` P0 delivery claim. The restricted local delivery state is green, and the tracked restricted ligand scale-up suite is now green (`commercialization_ready_suite_count=3/3`, `pending_suite_ids=[]`). This queue is planning-only and does not widen the current delivery verdict.

As of the current artifact refresh, the tracked broad-commercialization accounting blockers are closed, not merely shifted. `runs/platform_gap_taxonomy_packet_current.json` reports `platform_accounting_closed=true`, `top_expansion_gap_id=none_tracked_platform_expansion`, `current_delivery_blocker_count=0`, `expansion_blocker_count=0`, and `evidence_blocked_placeholder_rows=0`. `runs/transporter_negative_evidence_closure_queue_current.json` reports `negative_evidence_closure_allowed=true` for the current transporter negative slots. AQP1 kcal remains functional IC50-derived surrogate evidence, not direct binding kcal.

Legacy GPCR family/router diagnostics remain claim-locked comparison material. They do not block the current restricted local-delivery verdict or the tracked restricted 1M scale-up package, and they do not promote broad GPCR/router/platform wording.

For the non-ADRB2 positive freeze workflow, `config/gpcr_non_adrb2_positive_candidates_v1.csv` is the curated candidate input schema. The intended handoff is candidate CSV -> `runs/gpcr_non_adrb2_positive_candidates_leakage_audit_current.json` -> `runs/gpcr_positive_coverage_freeze_packet_current.json` -> `runs/gpcr_frozen_candidate_profile_support_current/summary.json` -> `runs/gpcr_frozen_candidate_scoreability_current.json` -> guarded 100k rerun -> `runs/gpcr_family_heldout_scorecard_current.json` / `runs/gpcr_family_heldout_scorecard_guardrail_current.json` -> `runs/gpcr_guarded_100k_rerun_readiness_current.json`; the current freeze packet is `frozen=true` after three non-ADRB2 ChEMBL_36 positives and a pass leakage audit, profile support is `profile_ready=true`, scoreability is `pass=true`, and family-held-out is `pass=true`. This closes launch/family coverage only; `claim_promotion_allowed=false` remains unchanged. The current proxy hook is `runs/gpcr_guarded_100k_rank_failure_diagnostics_current.json` / `drd2_pose_physics_diagnostics`; the paired shadow replay eval is `runs/gpcr_family_anchor_v2_shadow_replay_eval_current.json`; keep the rest of the follow-up chain compare-only.

For the operator-facing closure map with current repo-local artifacts and next commands, see `docs/post_p0_evidence_closure_status.md` and `runs/post_p0_claim_blocker_rollup_current.md`.

## Claim Boundary

- In claim: the current restricted P0 delivery claim remains limited to `kinase`, `ion_channel`, and `gpcr`.
- Out of claim: transporter expansion, CA2/PXR packet closure, IDP broader promotion, broad GPCR-family/router generalization, broad platform readiness, and unattended decision-making.
- The tracked restricted ligand scale-up suite is green, but that does not widen the claim beyond `kinase`, `ion_channel`, and `gpcr`.
- Transporter stays out of claim even though negative placeholder accounting is closed; direct-binding kcal and broad transporter delivery wording remain no-claim unless separately curated.
- CA2/PXR stays out of claim even though review-only policy accounting is closed; rows remain locked/review-only unless a separate authoritative promotion review is opened.
- `fixed_family_reference`, `gpcr_core_decoy_intrusion_v1`, `gpcr_core_linear_rescore_v1`, `gpcr_core_mismatch_contact_rescore_v1`, and `gpcr_core_structure_support_rescore_v1` are comparison-only shadow/guarded/reject evidence; `claim_promotion_allowed=false` remains in force, `gpcr_core_family_anchor_rescore_v2` is the feature donor/baseline only, and `gpcr_core_acidic_anchor_overcontact_prior_gate_v4`/`gpcr_core_fixed_reference_live_shadow_v5` are tombstone reject evidence. They do not promote the claim or router/platform wording, and no broad GPCR/basic-amine generalization is allowed. The paired shadow replay eval artifact is `runs/gpcr_family_anchor_v2_shadow_replay_eval_current.json`; keep it compare-only with `runs/gpcr_guarded_100k_rank_failure_diagnostics_current.json`.
- The class A aminergic/opioid-like orthosteric motif-aware shadow v6 and anchor-geometry shadow v7 replays are score-only/shadow-only/active-locked reject/rework evidence. They must not be generalized into broad GPCR/basic-amine wording or promoted with full 100k reruns, threshold relaxation, or fake pass.
- The next GPCR diagnostic order is claim-locked rework/shadow/replay only: v16/adaptive support-gap review -> OPRM1 pose/anchor alignment evidence -> HTR2A decoy support discrimination -> conserved anchor/prior gating review -> broader non-leaky positive coverage -> guarded validation prep. v8/v9 atom-window scorer patches are reject evidence and should not be relaunched unchanged; v10/v11 selected-slice green and v12/v13/v14/v15/v16/adaptive frozen recovery are not enough for router/platform claim.
- The queue below is the next internal-review path, not a new claim boundary.

## Priority Queue

0. Closed accounting guardrail: transporter/AQP1/CA2/PXR
   - Current top expansion gap: `none_tracked_platform_expansion`.
   - Source of truth: `runs/transporter_negative_evidence_closure_queue_current.json`, `runs/transporter_negative_evidence_target_packets_current.json`, `runs/transporter_placeholder_burndown_queue_current.json`, and `runs/platform_gap_taxonomy_packet_current.json`.
   - Queue state: transporter placeholder-driven rows `0`, evidence-blocked placeholder rows `0`, ready/apply-covered rows `6`.
   - AQP1 functional kcal surrogate packet has `functional_kcal_surrogate_ready_count=3` and `functional_kcal_surrogate_closure_allowed=true`; keep direct binding kcal blank.
   - GLUT1 stays source-confirmation/provenance only; do not widen to direct-binding or delivery wording from those rows.
   - External Life Science Research skill crosscheck is now materialized at `runs/transporter_external_evidence_crosscheck_current.json`: AQP1 maps to UniProt `P29972` / ChEMBL target `CHEMBL4523210`, GLUT1 maps to UniProt `P11166` / ChEMBL target `CHEMBL2535`, RCSB `4PYP` confirms GLUT1 structural context, ChEMBL/BindingDB still provide `0` authoritative AQP1 negative quantitative rows, and GLUT1 ChEMBL hits remain positive inhibitor context rather than negative replacements.
   - AQP1 historical gap/request/intake packets remain attached as provenance and validator surfaces, but current accounting closure is carried by the primary functional negative evidence and functional kcal surrogate packets.
   - Target-level ChEMBL harvest and GLUT1 curation queue are archived pre-closure evidence boards, not current blockers.
   - Keep all transporter rows outside the delivery claim unless direct target-specific binding evidence is curated. Do not reopen binder staging, donor-policy work, or delivery claim wording from the closed accounting state.

     ```bash
     python3 tools/run_transporter_membrane_scaffold_check.py
     python3 tools/build_transporter_membrane_readiness.py
     python3 tools/build_transporter_external_evidence_crosscheck.py
     python3 tools/build_aqp1_negative_evidence_gap_matrix.py
     python3 tools/build_aqp1_negative_evidence_request_packet.py
     python3 tools/build_aqp1_negative_evidence_intake_gate.py
     python3 tools/build_transporter_negative_candidate_harvest.py
     python3 tools/build_transporter_negative_candidate_curation_queue.py
     python3 tools/build_transporter_negative_evidence_target_packets.py
     python3 tools/build_transporter_negative_evidence_closure_queue.py
     python3 tools/build_transporter_placeholder_burndown_queue.py
     python3 tools/build_family_expansion_status_rollup.py
     python3 tools/build_commercialization_gap_burndown.py
     python3 tools/build_platform_gap_taxonomy_packet.py
     ```

1. GPCR family/router diagnostics, claim-locked behind transporter
   - Keep `claim_safe=false`; `claim_promotion_allowed=false`; the guarded 100k frozen non-ADRB2 rerun completed, and the next hard blocker is now CI-low/top20 scoring quality, not positive coverage or family-held-out. Do not use full 100k reruns, threshold relaxation, target identity feature, or fake pass to move this lane forward, and do not generalize the v2 basic-amine feature donor into broad GPCR/basic-amine wording; the next work is OPRM1 pose/anchor alignment evidence plus HTR2A decoy support discrimination after the v16/adaptive support-gap recovery, not another blind scalar rerun.
   - The v3 family-anchor CI-stability packet `runs/gpcr_residual_prototype_spec_family_anchor_ci_stability_v3.json` is diagnostic-only (`prototype_mode=shadow_only`, `scorer_apply_allowed=false`). The v4 acidic-anchor overcontact prior gate is now implemented and profiled but rejected by score-only replay: `gpcr_acidic_anchor_overcontact_prior_gate` activated on `0/40000` rows and metrics were `PR-AUC=0.008231735935435774`, `PR-AUC CI-low=0.0009935430341614215`, `top20=0.00`; keep it as tombstone reject evidence.
   - `minimum_non_leaky_positive_additions=3` is satisfied in the frozen packet: `positive_count=9`, `new_non_adrb2_positive_count=3`, distinct positive GPCR target count `=4`, and leakage audit `pass=true`.
   - Family-held-out is green, but router/platform claim remains forbidden until the same full 100k claim-review gate clears CI-low and top20 stability.
   - `fixed_family_reference`, `gpcr_core_decoy_intrusion_v1`, `gpcr_core_linear_rescore_v1`, `gpcr_core_mismatch_contact_rescore_v1`, and `gpcr_core_structure_support_rescore_v1` stay comparison-only shadow/guarded/reject evidence; do not promote them to a claim or router/platform win until the full 100k gate, CI-low / positive coverage stability, and family-held-out scorecard are green. Use `runs/gpcr_ci_low_recovery_packet_current.md` (`## Metric Table`, `## Rank And Bootstrap Diagnostics`, `## Recommended Next Actions`) as the operator packet for the coverage check, and use `runs/external_validation_2026-05-03_family_balanced_frozen_r2_set1_core_blind_gpcr_core_full_p0_n100000_r1_stage5_ranking_summary.md` plus `..._stage5_ranking_rows.csv` for the latest r2 rank evidence. `gpcr_core_family_anchor_rescore_v2` is the feature donor/baseline for the next DRD2 motif-aware diagnostic, not broad GPCR/basic-amine generalization.
   - `gpcr_core_decoy_intrusion_v1` guarded apply core 100k was rerun on 2026-05-02 and remains reject evidence (`PR-AUC=0.3890`, `top20=0.15`).
   - `gpcr_core_mismatch_contact_rescore_v1` guarded apply core 100k completed the 2026-05-02 safesync/cache-disabled run with stable execution (`stage2 ok_rows=10000`, `failed_rows=0`) but remains reject evidence (`PR-AUC=0.3836`, `PR-AUC CI low=0.0157`, `top20=0.15`).
   - `gpcr_core_structure_support_rescore_v1` guarded apply rollout run completed on 2026-05-03 with recovery-band ranking signal (`PR-AUC=0.592849548112706`, `ROC-AUC=0.9961310119404976`, `top20=0.25`, `strict_gate_pass=true`), but it is still comparison/reject evidence only because the operational gate failed on `ranking_pr_auc_ci_low=0.12868359671529103 < 0.45`.
   - The frozen non-ADRB2 guarded 100k rerun completed with `positive_count=9`, `stage2 ok_rows=40000`, leakage audit `pass=true`, and family-held-out `pass=true`, but failed claim review (`PR-AUC=0.22869872098030358`, `PR-AUC CI low=0.0019312183264511504`, `top20=0.10`). Do not relaunch the same packet as claim evidence; fix scoring/ranking quality first.
   - `gpcr_core_family_balanced_rescore_v1` frozen guarded 100k completed after the interrupted r2 run was resumed with the same tag/spec. Stage2 reused `34186` existing trajectory rows and generated `5814` remaining rows (`40000/40000` ok rows). It recovered `PR-AUC=0.5186945103743427`, `top20=0.25`, and `strict_gate_pass=true`, but failed operational claim review on `PR-AUC < 0.55` and `ranking_pr_auc_ci_low=0.1485815545422209 < 0.45`; keep it comparison/reject evidence only. HTR2A/OPRM1 recovered to target-rank 1, but DRD2 is still buried at `global_rank=18923` / `target_rank=5315`.
   - The refreshed DRD2 diagnostic slice shows the positive is not missing the conserved acidic anchor: it contacts native `Asp114` at mean distance about `3.25 A`. The top DRD2 decoy cluster is even closer at about `2.48 A`, so the next scoring work should stay motif-aware within the class A aminergic/opioid-like orthosteric sublane as direct atom-window anchor geometry / hydrophobic-overcontact diagnostics rather than broad GPCR/basic-amine generalization.
   - `gpcr_core_family_anchor_rescore_v2` is now available as claim-locked shadow/replay only. It uses `binding_score_composite_v7_prior_active`, `gpcr_basic_amine_proxy`, conserved-anchor/prior gating, and anchor-chemistry mismatch pressure; local replay improves `PR-AUC=0.5186945103743427 -> 0.5767474245351905`, computes `ranking_pr_auc_ci_low=0.21066694653866244`, keeps top20 at `0.25`, and improves DRD2 `global_rank=18923 -> 8562`, but this is only the feature donor/baseline for the next DRD2 motif-aware diagnostic and not claim evidence because CI-low remains below `0.45`. The base pairwise diagnostic slice still has `decoys_above_positive_count=5314`, `pairwise_win_rate=0.46854685468546853`, and `ready_for_guarded_apply=false`; the refreshed shadow projection improves DRD2 decoys-above-positive to `2434` and pairwise win-rate to `0.7565756575657565`.
   - The next scorer attempt should not relaunch v4, v5, v6, v7, v8, or v9 unchanged. v4/v5 are tombstone reject evidence, v6/v7 are matching-label reject/rework evidence, and v8/v9 show atom-window reward still overpromotes hard decoys. v10 converts the repaired hard-decoy feature contract into a selected-slice green shadow replay but is not portable as-is; v11 adds weak-base gating and is selected-slice green, but complete true-base frozen replay is still blocked (`shadow_top20_positive_count=0`, DRD2 decoys above positive `498`, HTR2A `1744`, OPRM1 `261`). v12 fixes most of the DRD2 rank inversion in frozen shadow replay, v13 improves all three frozen positives, v14 is rejected because cationic occupancy reward overpromotes HTR2A decoys, v15 improves support-gap penalties, and v16 is the best all-basic top20 recovery (`DRD2 2/2/1`, `HTR2A 16/7/6`, `OPRM1 583/115/114`). Adaptive pose-preserving repair removes OPRM1 pose collapse, but the v16 adaptive gap packet still records `blocked_positive_count=3`, `positive_anchor_support_missing=2`, `positive_pose_preservation_borderline=2`, and `target_decoys_above_positive=3`. The next hard implementation is OPRM1 pose/anchor alignment evidence, HTR2A decoy support discrimination, and conditional prior gating before any guarded apply; keep `claim_promotion_allowed=false`, `scorer_apply_allowed=false`, and threshold relaxation/fake pass off-limits.
   - `fixed_family_reference` comparison-only rerun also failed the 2026-05-02 full 100k gate (`PR-AUC=0.0328`, `PR-AUC CI low=0.0045`, `top20=0.05`), so it stays reject evidence and is not a new recovery lane.

     ```bash
     python3 tools/build_gpcr_100k_failure_analysis.py
     python3 tools/build_gpcr_apply_safe_endpoint.py
     python3 tools/build_gpcr_residual_chembl50_v4_endpoint_note.py
     python3 tools/build_ligand_scaleup_kpi_table.py
     python3 tools/build_ligand_scaleup_benchmark_summary.py
     python3 tools/build_gpcr_scaleup_regression_triage.py
     python3 tools/build_gpcr_ci_low_recovery_packet.py --triage-json runs/gpcr_scaleup_regression_triage_current.json
     python3 tools/build_gpcr_drd2_pose_generation_repair_packet.py
     python3 tools/repair_gpcr_drd2_pseudo_allatom_backmapping.py --anchor-mode positive_only
     python3 tools/build_gpcr_atom_window_anchor_feature_cache.py --input-csv runs/gpcr_drd2_pseudo_allatom_repair_rows_current.csv --target CHEMBL217_DRD2_HUMAN --score-col score --top-n 0 --include-positives --out-csv runs/gpcr_atom_window_anchor_feature_cache_drd2_pseudo_allatom_repair_current.csv --out-json runs/gpcr_atom_window_anchor_feature_cache_drd2_pseudo_allatom_repair_current.json --out-md runs/gpcr_atom_window_anchor_feature_cache_drd2_pseudo_allatom_repair_current.md
     python3 tools/build_gpcr_drd2_cationic_center_geometry_cache.py
     python3 tools/build_gpcr_drd2_hard_decoy_slice_packet.py
     python3 tools/build_gpcr_drd2_hard_decoy_penalty_envelope.py
     python3 tools/build_gpcr_residual_prototype_spec.py --variant gpcr_core_cationic_pose_distortion_shadow_v10 --out-json runs/gpcr_residual_prototype_spec_cationic_pose_distortion_shadow_v10.json --out-csv runs/gpcr_residual_prototype_spec_cationic_pose_distortion_shadow_v10.csv --out-md runs/gpcr_residual_prototype_spec_cationic_pose_distortion_shadow_v10.md
     python3 tools/replay_gpcr_residual_shadow_scores.py --input-scores-csv runs/gpcr_drd2_hard_decoy_slice_packet_rows_current.csv --residual-prototype-spec-json runs/gpcr_residual_prototype_spec_cationic_pose_distortion_shadow_v10.json --out-scores-csv runs/gpcr_cationic_pose_distortion_v10_shadow_replay_scores_current.csv --out-summary-json runs/gpcr_cationic_pose_distortion_v10_shadow_replay_summary_current.json --out-summary-md runs/gpcr_cationic_pose_distortion_v10_shadow_replay_summary_current.md
     python3 tools/build_gpcr_cationic_pose_distortion_shadow_replay_review.py
     python3 tools/build_gpcr_cationic_pose_distortion_frozen_feature_cache.py --target-filter CHEMBL217_DRD2_HUMAN --ligand-filter CHEMBL301265 --anchor-mode none --out-csv runs/gpcr_cationic_pose_distortion_frozen_feature_cache_drd2_positive_current.csv --out-json runs/gpcr_cationic_pose_distortion_frozen_feature_cache_drd2_positive_current.json --out-md runs/gpcr_cationic_pose_distortion_frozen_feature_cache_drd2_positive_current.md
     python3 tools/build_gpcr_cationic_pose_distortion_frozen_feature_cache.py --target-filter CHEMBL217_DRD2_HUMAN --ligand-filter CHEMBL301265 --anchor-mode all_basic --out-csv runs/gpcr_cationic_pose_distortion_frozen_feature_cache_drd2_positive_allbasic_current.csv --out-json runs/gpcr_cationic_pose_distortion_frozen_feature_cache_drd2_positive_allbasic_current.json --out-md runs/gpcr_cationic_pose_distortion_frozen_feature_cache_drd2_positive_allbasic_current.md
     python3 tools/build_gpcr_cationic_pose_distortion_frozen_feature_cache.py --target-filter CHEMBL217_DRD2_HUMAN,CHEMBL224_HTR2A_HUMAN,CHEMBL233_OPRM1_HUMAN --row-limit 300 --anchor-mode all_basic --out-csv runs/gpcr_cationic_pose_distortion_frozen_feature_cache_allbasic_partial_current.csv --out-json runs/gpcr_cationic_pose_distortion_frozen_feature_cache_allbasic_partial_current.json --out-md runs/gpcr_cationic_pose_distortion_frozen_feature_cache_allbasic_partial_current.md
     python3 tools/build_gpcr_cationic_pose_distortion_frozen_cache_mode_review.py
     python3 tools/build_gpcr_residual_prototype_spec.py --variant gpcr_core_cationic_weakbase_rescue_shadow_v11 --out-json runs/gpcr_residual_prototype_spec_cationic_weakbase_rescue_shadow_v11.json --out-csv runs/gpcr_residual_prototype_spec_cationic_weakbase_rescue_shadow_v11.csv --out-md runs/gpcr_residual_prototype_spec_cationic_weakbase_rescue_shadow_v11.md
     python3 tools/replay_gpcr_residual_shadow_scores.py --input-scores-csv runs/gpcr_drd2_hard_decoy_slice_packet_rows_current.csv --residual-prototype-spec-json runs/gpcr_residual_prototype_spec_cationic_weakbase_rescue_shadow_v11.json --out-scores-csv runs/gpcr_cationic_weakbase_v11_shadow_replay_scores_current.csv --out-summary-json runs/gpcr_cationic_weakbase_v11_shadow_replay_summary_current.json --out-summary-md runs/gpcr_cationic_weakbase_v11_shadow_replay_summary_current.md
     python3 tools/replay_gpcr_residual_shadow_scores.py --input-scores-csv runs/gpcr_cationic_pose_distortion_frozen_feature_cache_allbasic_partial_current.csv --residual-prototype-spec-json runs/gpcr_residual_prototype_spec_cationic_weakbase_rescue_shadow_v11.json --out-scores-csv runs/gpcr_cationic_weakbase_v11_frozen_allbasic_partial_shadow_replay_scores_current.csv --out-summary-json runs/gpcr_cationic_weakbase_v11_frozen_allbasic_partial_shadow_replay_summary_current.json --out-summary-md runs/gpcr_cationic_weakbase_v11_frozen_allbasic_partial_shadow_replay_summary_current.md
     python3 tools/build_gpcr_cationic_pose_distortion_shadow_replay_review.py --input-scores-csv runs/gpcr_cationic_weakbase_v11_shadow_replay_scores_current.csv --input-summary-json runs/gpcr_cationic_weakbase_v11_shadow_replay_summary_current.json --out-json runs/gpcr_cationic_weakbase_v11_shadow_replay_review_current.json --out-md runs/gpcr_cationic_weakbase_v11_shadow_replay_review_current.md
     python3 tools/build_gpcr_cationic_pose_distortion_frozen_feature_cache.py --target-filter CHEMBL217_DRD2_HUMAN,CHEMBL224_HTR2A_HUMAN,CHEMBL233_OPRM1_HUMAN --row-limit 16500 --row-offset 0 --anchor-mode all_basic --out-csv runs/gpcr_cationic_pose_distortion_frozen_feature_cache_allbasic_truebase_16500_current.csv --out-json runs/gpcr_cationic_pose_distortion_frozen_feature_cache_allbasic_truebase_16500_current.json --out-md runs/gpcr_cationic_pose_distortion_frozen_feature_cache_allbasic_truebase_16500_current.md
     python3 tools/build_gpcr_cationic_pose_distortion_frozen_feature_cache.py --target-filter CHEMBL217_DRD2_HUMAN,CHEMBL224_HTR2A_HUMAN,CHEMBL233_OPRM1_HUMAN --row-limit 13500 --row-offset 16500 --anchor-mode all_basic --resume-existing --out-csv runs/gpcr_cationic_pose_distortion_frozen_feature_cache_allbasic_truebase_16500_current.csv --out-json runs/gpcr_cationic_pose_distortion_frozen_feature_cache_allbasic_truebase_16500_current.json --out-md runs/gpcr_cationic_pose_distortion_frozen_feature_cache_allbasic_truebase_16500_current.md
     python3 tools/replay_gpcr_residual_shadow_scores.py --input-scores-csv runs/gpcr_cationic_pose_distortion_frozen_feature_cache_allbasic_truebase_16500_current.csv --residual-prototype-spec-json runs/gpcr_residual_prototype_spec_cationic_weakbase_rescue_shadow_v11.json --out-scores-csv runs/gpcr_cationic_weakbase_v11_frozen_allbasic_truebase_full_shadow_replay_scores_current.csv --out-summary-json runs/gpcr_cationic_weakbase_v11_frozen_allbasic_truebase_full_shadow_replay_summary_current.json --out-summary-md runs/gpcr_cationic_weakbase_v11_frozen_allbasic_truebase_full_shadow_replay_summary_current.md
     python3 tools/build_gpcr_cationic_weakbase_frozen_shadow_replay_review.py --input-scores-csv runs/gpcr_cationic_weakbase_v11_frozen_allbasic_truebase_full_shadow_replay_scores_current.csv --input-summary-json runs/gpcr_cationic_weakbase_v11_frozen_allbasic_truebase_full_shadow_replay_summary_current.json --expected-complete-rows 30000
     python3 tools/build_gpcr_residual_prototype_spec.py --variant gpcr_core_synthetic_anchor_penalty_shadow_v12 --out-json runs/gpcr_residual_prototype_spec_synthetic_anchor_penalty_shadow_v12.json --out-csv runs/gpcr_residual_prototype_spec_synthetic_anchor_penalty_shadow_v12.csv --out-md runs/gpcr_residual_prototype_spec_synthetic_anchor_penalty_shadow_v12.md
     python3 tools/replay_gpcr_residual_shadow_scores.py --input-scores-csv runs/gpcr_cationic_pose_distortion_frozen_feature_cache_allbasic_truebase_16500_current.csv --residual-prototype-spec-json runs/gpcr_residual_prototype_spec_synthetic_anchor_penalty_shadow_v12.json --out-scores-csv runs/gpcr_synthetic_anchor_penalty_v12_frozen_allbasic_truebase_full_shadow_replay_scores_current.csv --out-summary-json runs/gpcr_synthetic_anchor_penalty_v12_frozen_allbasic_truebase_full_shadow_replay_summary_current.json --out-summary-md runs/gpcr_synthetic_anchor_penalty_v12_frozen_allbasic_truebase_full_shadow_replay_summary_current.md
     python3 tools/build_gpcr_cationic_weakbase_frozen_shadow_replay_review.py --input-scores-csv runs/gpcr_synthetic_anchor_penalty_v12_frozen_allbasic_truebase_full_shadow_replay_scores_current.csv --input-summary-json runs/gpcr_synthetic_anchor_penalty_v12_frozen_allbasic_truebase_full_shadow_replay_summary_current.json --expected-complete-rows 30000 --out-json runs/gpcr_synthetic_anchor_penalty_v12_frozen_shadow_replay_review_current.json --out-md runs/gpcr_synthetic_anchor_penalty_v12_frozen_shadow_replay_review_current.md
     python3 tools/build_gpcr_frozen_pose_support_gap_packet.py
     python3 tools/build_gpcr_residual_prototype_spec.py --variant gpcr_core_pose_support_gap_shadow_v13 --out-json runs/gpcr_residual_prototype_spec_pose_support_gap_shadow_v13.json --out-csv runs/gpcr_residual_prototype_spec_pose_support_gap_shadow_v13.csv --out-md runs/gpcr_residual_prototype_spec_pose_support_gap_shadow_v13.md
     python3 tools/replay_gpcr_residual_shadow_scores.py --input-scores-csv runs/gpcr_cationic_pose_distortion_frozen_feature_cache_allbasic_truebase_16500_current.csv --residual-prototype-spec-json runs/gpcr_residual_prototype_spec_pose_support_gap_shadow_v13.json --out-scores-csv runs/gpcr_pose_support_gap_v13_frozen_allbasic_truebase_full_shadow_replay_scores_current.csv --out-summary-json runs/gpcr_pose_support_gap_v13_frozen_allbasic_truebase_full_shadow_replay_summary_current.json --out-summary-md runs/gpcr_pose_support_gap_v13_frozen_allbasic_truebase_full_shadow_replay_summary_current.md
     python3 tools/build_gpcr_cationic_weakbase_frozen_shadow_replay_review.py --input-scores-csv runs/gpcr_pose_support_gap_v13_frozen_allbasic_truebase_full_shadow_replay_scores_current.csv --input-summary-json runs/gpcr_pose_support_gap_v13_frozen_allbasic_truebase_full_shadow_replay_summary_current.json --expected-complete-rows 30000 --out-json runs/gpcr_pose_support_gap_v13_frozen_shadow_replay_review_current.json --out-md runs/gpcr_pose_support_gap_v13_frozen_shadow_replay_review_current.md
     python3 tools/build_gpcr_frozen_pose_support_gap_packet.py --input-scores-csv runs/gpcr_pose_support_gap_v13_frozen_allbasic_truebase_full_shadow_replay_scores_current.csv --out-json runs/gpcr_pose_support_gap_v13_frozen_gap_packet_current.json --out-csv runs/gpcr_pose_support_gap_v13_frozen_gap_packet_current.csv --out-md runs/gpcr_pose_support_gap_v13_frozen_gap_packet_current.md
     python3 tools/build_gpcr_family_heldout_scorecard.py --rows-csv runs/ligand_stress_validation_2026-05-03_gpcr_frozen_nonadrb2_guarded100k_p0_n100000_r1_stage5_ranking_rows.csv --summary-json runs/ligand_stress_validation_2026-05-03_gpcr_frozen_nonadrb2_guarded100k_p0_n100000_r1_stage5_ranking_summary.json
     python3 tools/build_gpcr_family_heldout_scorecard_guardrail.py
     python3 tools/build_gpcr_positive_coverage_expansion_packet.py --family-scorecard-json runs/gpcr_family_heldout_scorecard_current.json
     python3 tools/build_gpcr_non_adrb2_candidate_leakage_audit.py
     python3 tools/build_gpcr_positive_coverage_freeze_packet.py
     python3 tools/build_gpcr_frozen_candidate_profile_support.py --native-source-csv config/gpcr_non_adrb2_native_sources_v1.csv
     python3 tools/build_gpcr_frozen_candidate_scoreability_packet.py --profile-json runs/gpcr_frozen_candidate_profile_support_current/profile.json
     python3 tools/build_gpcr_guarded_100k_rerun_readiness.py --leakage-audit-json runs/ligand_stress_validation_2026-05-03_gpcr_frozen_nonadrb2_guarded100k_p0_n100000_r1_stage0_leakage_summary.json
     python3 tools/build_post_p0_claim_blocker_rollup.py
     ```

   - If the raw 100k ranking CSV inputs are absent, `build_gpcr_100k_failure_analysis.py` must emit `blocked_missing_csv_inputs`; do not infer recovery from the previous snapshot alone.
   - Source of truth: `runs/ligand_scaleup_benchmark_summary_current.json` plus `runs/gpcr_100k_failure_analysis_current.json`.
   - Triage source: `runs/gpcr_scaleup_regression_triage_current.json`; use it to separate reject evidence from target-specific comparison evidence without widening the claim.
   - CI-low source: `runs/gpcr_ci_low_recovery_packet_current.json`; operator packet: `runs/gpcr_ci_low_recovery_packet_current.md` (`## Metric Table`, `## Rank And Bootstrap Diagnostics`, `## Recommended Next Actions`). Use it to inspect positive ranks, top20-missing positives, coverage ceiling, and bootstrap stability before any new recovery claim.
   - Rank failure diagnostics source: `runs/gpcr_guarded_100k_rank_failure_diagnostics_current.json`; the packet remains diagnostic-only, and the next implementation is OPRM1 pose-survival/backmapping consistency, HTR2A decoy support discrimination, conditional prior gating, and broader non-leaky positive coverage after the v15 support-gap review. Do not relaunch the same packet as claim evidence, and keep `claim_promotion_allowed=false` with threshold relaxation/fake pass forbidden.
   - DRD2 repair sources: `runs/gpcr_drd2_pose_generation_repair_packet_current.json`, `runs/gpcr_drd2_pseudo_allatom_repair_current.json`, `runs/gpcr_atom_window_anchor_feature_cache_drd2_pseudo_allatom_repair_current.json`, `runs/gpcr_drd2_cationic_center_geometry_cache_current.json`, `runs/gpcr_drd2_hard_decoy_slice_packet_current.json`, `runs/gpcr_drd2_hard_decoy_penalty_envelope_current.json`, `runs/gpcr_cationic_pose_distortion_v10_shadow_replay_review_current.json`, `runs/gpcr_cationic_pose_distortion_frozen_cache_mode_review_current.json`, `runs/gpcr_cationic_weakbase_v11_shadow_replay_review_current.json`, `runs/gpcr_cationic_weakbase_v11_frozen_shadow_replay_review_current.json`, `runs/gpcr_synthetic_anchor_penalty_v12_frozen_shadow_replay_review_current.json`, `runs/gpcr_pose_support_gap_v13_frozen_shadow_replay_review_current.json`, `runs/gpcr_truebase_anchor_occupancy_v14_frozen_shadow_replay_review_current.json`, and `runs/gpcr_truebase_gap_penalty_v15_frozen_shadow_replay_review_current.json`. Current selected-row repair is green as diagnostic materialization (`65/65` repaired, positive `14/14` heavy-atom coverage, `anchor_mode=positive_only`, positive atom-window mean `2.8214482267014858 A`, cationic-center mean `3.1999997921453787 A`). v10/v11 selected-slice is green, v12/v13/v15 frozen replay improves ranks, and v14 is preserved as reject/rework, but frozen-family portability is still blocked by positive support and pose/backmapping gaps. Keep these diagnostic-only and fix the feature-generation contract before any full guarded claim review.
   - Family-anchor v2 spec source: `runs/gpcr_residual_prototype_spec_family_anchor_v2_shadow.json`; treat it as a replay/shadow candidate and do not promote it without CI-low/full guarded validation.
   - Positive-coverage source: `runs/gpcr_positive_coverage_expansion_packet_current.json`; inspect selected candidate rows and their `target_specific_adrb2_bias_review_required` flags before adding any future coverage-expanded 100k rerun packet. The current non-ADRB2 freeze/family-held-out path is green, so the remaining claim blocker is CI-low/top20 scoring quality.
   - Freeze source: `runs/gpcr_positive_coverage_freeze_packet_current.json`; current `frozen=true` means the coverage floor is closed.
   - Profile support source: `runs/gpcr_frozen_candidate_profile_support_current/summary.json`; current `profile_ready=true` with RCSB structures DRD2 `6CM4`, HTR2A `6A93`, and OPRM1 `8EF6`, all ligand-centroid pocket validations `pass`.
   - Scoreability source: `runs/gpcr_frozen_candidate_scoreability_current.json`; current `pass=true`, `freeze_positive_count=9`, and `profile_positive_count=9` clear native/reference/split/meta/profile and hard-decoy coverage blockers.
   - Family-held-out scorecard source: `runs/gpcr_family_heldout_scorecard_current.json`; current `scorecard_level_status=pass`, `gpcr_positive_count=9`, and `gpcr_distinct_positive_target_count=4`.
   - Family-held-out guardrail source: `runs/gpcr_family_heldout_scorecard_guardrail_current.json`; current `status=green`, but router/platform claim remains forbidden until CI-low/top20 gates clear.
   - Guarded 100k readiness source: `runs/gpcr_guarded_100k_rerun_readiness_current.json`; current `launch_eligible=true`, `eligible=false`, `claim_review_eligible=false`, and blockers are `ci_low_below_threshold` plus `top20_stability_not_green`.
   - Crash/resume rule: rerun the exact same command with the same tag/spec after a shutdown. `run_external_validation_blind_sets.py` and `run_ligand_stress_validation.py` default to `--resume`, while stage2 trajectory generation now forwards `--traj-resume-existing` by default, so partial trajectory rows should be reused instead of regenerated.

2. PDE translation quality
   - Keep the T. cruzi PDE rescue/translation lane honest.
   - PDE translation은 `binding_energy_proxy` → `pose RMSD` → `backmapping` → `local minimization survival` 순서로 본다; later checks and expensive reruns must not jump ahead of earlier blockers.
   - Use the local translation annotator, rescue/validate pair, and translation-quality packet before any expensive rerun:

     ```bash
     python3 tools/build_wetlab_rescue_three_bead_candidates.py
     python3 tools/run_wetlab_tcruzi_pde_allatom_rescue.py --top-k 8 --filter-mode strict_then_near_fill --execute
     python3 tools/validate_wetlab_tcruzi_pde_allatom_rescue_attempt.py
     python3 tools/build_wetlab_tcruzi_pde_allatom_review_packet.py
     python3 tools/build_wetlab_tcruzi_pde_translation_quality_packet.py
     python3 tools/build_local_delivery_verdict_gate.py
     ```

   - Do not widen claims while `translation_quality_ready=false` or the rescue attempt is incomplete; `claim_promotion_allowed=false` stays in force until the blocker sequence closes.
   - Source of truth: `runs/wetlab_tcruzi_pde_translation_quality_packet_current.md`.

3. Transporter AQP1 / GLUT1 scaffold/readiness helper refresh
   - Sequence AQP1 first, then GLUT1; AQP1 stays first-wave and GLUT1 stays second-wave.
   - Use the validate-only scaffold check and the transporter readiness rollup:

     ```bash
     python3 tools/run_transporter_membrane_scaffold_check.py
     python3 tools/build_transporter_membrane_readiness.py
     python3 tools/build_transporter_external_evidence_crosscheck.py
     python3 tools/build_aqp1_negative_evidence_gap_matrix.py
     python3 tools/build_aqp1_negative_evidence_request_packet.py
     python3 tools/build_aqp1_negative_evidence_intake_gate.py
     python3 tools/build_transporter_negative_candidate_harvest.py
     python3 tools/build_transporter_negative_candidate_curation_queue.py
     python3 tools/build_family_expansion_status_rollup.py
     python3 tools/build_family_evidence_acquisition_queue.py
     ```

   - Keep `AQP1` and `GLUT1` dry-run/template-only, parked/review-only, until the ligand packets are frozen, donor policy is explicit, and negative evidence/provenance closure is complete; keep `bacopaside II` as the AQP1 first-wave scope, `AqB013` as the exact-human-activity guardrail, `AqB011` as the follow-on review-only row, and `cytochalasin B` as the GLUT1 second-wave lead while `replacement_reference_binding_kcal_mol` stays blank.
   - Source artifacts: `runs/transporter_commercialization_closure_queue_current.json`, `runs/transporter_binder_verdict_progress_current.json`, `runs/transporter_placeholder_burndown_queue_current.md`.
   - Source docs: `docs/transporter_membrane_runnable_scaffold_notes.md`, `docs/transporter_membrane_expansion_scaffold_plan.md`, `docs/post_p0_evidence_closure_status.md`.

4. CA2 / PXR packet closure
   - Close the packet work before any expansion candidate wording:

     ```bash
     python3 tools/build_ca2_packet_replacement_workbook.py
     python3 tools/build_ca2_packet_replacement_readiness.py
     python3 tools/build_pxr_ligand_packet_fill_workbook.py
     python3 tools/validate_pxr_packet_fill_readiness.py
     python3 tools/build_partial_authoritative_quickstart_packet.py
     ```

   - CA2 stays review-only negative closure / prep-only until the packet fields are frozen; all 12 rows remain blocked and `replacement_reference_binding_kcal_mol` is still missing.
   - PXR stays partial-authoritative / prep-only until quantitative provenance is filled and the remaining `replacement_reference_binding_kcal_mol` rows are closed; readiness is still `8/14`.
   - Source artifacts: `runs/ca2_ligand_packet_fill_workbook_current.json`, `runs/ca2_packet_replacement_workbook_current.json`, `runs/ca2_packet_replacement_readiness_current.json`, `runs/pxr_ligand_packet_fill_workbook_current.json`, `runs/pxr_packet_fill_readiness_current.json`, `runs/pxr_quantitative_provenance_packet_current.json`, `runs/pxr_pending_resolution_packet_current.json`.
   - Source docs: `docs/non_kinase_enzyme_ca2_runnable_packet_plan.md`, `docs/non_kinase_enzyme_ca2_ligand_packet_p0_plan.md`, `docs/non_kinase_enzyme_ca2_packet_replacement_workbook.md`, `docs/non_kinase_enzyme_ca2_packet_replacement_readiness.md`, `docs/nuclear_receptor_pxr_ligand_packet_fill_workbook.md`, `docs/post_p0_evidence_closure_status.md`.

5. IDP broader-promotion boundaries
   - Keep broader promotion blocked while the bounded lane is evaluated.
   - Use the broader-promotion review and resolution helpers:

     ```bash
     python3 tools/build_idp_broader_promotion_review_packet.py
     python3 tools/build_idp_broader_promotion_resolution.py
     python3 tools/build_idp_commercial_pretest_packet.py
     python3 tools/build_pretest_execution_readiness.py
     ```

   - The admitted one-wider shadow lane is still not broader promotion.
   - Source helpers: `tools/build_idp_broader_promotion_review_packet.py`, `tools/build_idp_broader_promotion_resolution.py`.

## What This Queue Does Not Do

- It does not change the current P0 verdict.
- It does not promote transporter, CA2/PXR, GPCR comparison candidates, or IDP broader-promotion evidence into claim wording.
- It does not use full 100k reruns, threshold relaxation, target identity feature, or fake pass to widen the claim.
- It does not treat the 2026-05-03 `ligand_heavy_runs` execute cleanup (`deleted_count=12`, `deleted_bytes=556010987428`) or the structure-support rerun payload cleanup (`38346317024` stalled bytes plus `51265129536` completed rollout bytes; `/` usage `57%`, `runs/local_heavy_runs` `28K`) as evidence or as a claim boundary change.
- It does not replace the current local-delivery gate, claim policy, or verdict validation flow.
