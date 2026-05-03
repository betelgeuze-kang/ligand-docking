# Post-P0 Commercial Expansion Queue

## Purpose

This queue starts after the current restricted `kinase`, `ion_channel`, and `gpcr` P0 delivery claim. It is planning-only, blocked, and does not widen the current delivery verdict. The first active queue item is GPCR scale-up recovery because the current 100k claim remains blocked. Within that lane, `claim_promotion_allowed=false` stays in force; the non-leaky GPCR +3 freeze, frozen-candidate scoreability, family-held-out scorecard, and leakage audit are green. The guarded 100k rerun completed, but claim review remains blocked by CI-low and top20 stability.

For the non-ADRB2 positive freeze workflow, `config/gpcr_non_adrb2_positive_candidates_v1.csv` is the curated candidate input schema. The intended handoff is candidate CSV -> `runs/gpcr_non_adrb2_positive_candidates_leakage_audit_current.json` -> `runs/gpcr_positive_coverage_freeze_packet_current.json` -> `runs/gpcr_frozen_candidate_profile_support_current/summary.json` -> `runs/gpcr_frozen_candidate_scoreability_current.json` -> guarded 100k rerun -> `runs/gpcr_family_heldout_scorecard_current.json` / `runs/gpcr_family_heldout_scorecard_guardrail_current.json` -> `runs/gpcr_guarded_100k_rerun_readiness_current.json`; the current freeze packet is `frozen=true` after three non-ADRB2 ChEMBL_36 positives and a pass leakage audit, profile support is `profile_ready=true`, scoreability is `pass=true`, and family-held-out is `pass=true`. This closes launch/family coverage only; `claim_promotion_allowed=false` remains unchanged.

For the operator-facing closure map with current repo-local artifacts and next commands, see `docs/post_p0_evidence_closure_status.md` and `runs/post_p0_claim_blocker_rollup_current.md`.

## Claim Boundary

- In claim: the current restricted P0 delivery claim remains limited to `kinase`, `ion_channel`, and `gpcr`.
- Out of claim: transporter expansion, CA2/PXR packet closure, IDP broader promotion, and GPCR scale-up recovery.
- Transporter stays out of claim and remains parked/review-only until `AQP1` is first-wave, `GLUT1` is second-wave, and negative evidence plus provenance closure are complete.
- CA2/PXR stays out of claim and remains prep-only until placeholder work, provenance, and `replacement_reference_binding_kcal_mol` closure are complete.
- `fixed_family_reference`, `gpcr_core_decoy_intrusion_v1`, `gpcr_core_linear_rescore_v1`, `gpcr_core_mismatch_contact_rescore_v1`, and `gpcr_core_structure_support_rescore_v1` are comparison-only shadow/guarded/reject evidence; `claim_promotion_allowed=false` remains in force, and they do not promote the claim or router/platform wording.
- The queue below is the next internal-review path, not a new claim boundary.

## Priority Queue

0. GPCR positive coverage expansion and scale-up recovery
   - Keep `claim_safe=false`; `claim_promotion_allowed=false`; the guarded 100k frozen non-ADRB2 rerun completed, and the next hard blocker is now CI-low/top20 scoring quality, not positive coverage or family-held-out.
   - `minimum_non_leaky_positive_additions=3` is satisfied in the frozen packet: `positive_count=9`, `new_non_adrb2_positive_count=3`, distinct positive GPCR target count `=4`, and leakage audit `pass=true`.
   - Family-held-out is green, but router/platform claim remains forbidden until the same full 100k claim-review gate clears CI-low and top20 stability.
   - `fixed_family_reference`, `gpcr_core_decoy_intrusion_v1`, `gpcr_core_linear_rescore_v1`, `gpcr_core_mismatch_contact_rescore_v1`, and `gpcr_core_structure_support_rescore_v1` stay comparison-only shadow/guarded/reject evidence; do not promote them to a claim or router/platform win until the full 100k gate, CI-low / positive coverage stability, and family-held-out scorecard are green. Use `runs/gpcr_ci_low_recovery_packet_current.md` (`## Metric Table`, `## Rank And Bootstrap Diagnostics`, `## Recommended Next Actions`) as the operator packet for the coverage check, and use `runs/gpcr_guarded_100k_rank_failure_diagnostics_current.json` / `.md` for the scoring-candidate `next_action`.
   - `gpcr_core_decoy_intrusion_v1` guarded apply core 100k was rerun on 2026-05-02 and remains reject evidence (`PR-AUC=0.3890`, `top20=0.15`).
   - `gpcr_core_mismatch_contact_rescore_v1` guarded apply core 100k completed the 2026-05-02 safesync/cache-disabled run with stable execution (`stage2 ok_rows=10000`, `failed_rows=0`) but remains reject evidence (`PR-AUC=0.3836`, `PR-AUC CI low=0.0157`, `top20=0.15`).
   - `gpcr_core_structure_support_rescore_v1` guarded apply rollout run completed on 2026-05-03 with recovery-band ranking signal (`PR-AUC=0.592849548112706`, `ROC-AUC=0.9961310119404976`, `top20=0.25`, `strict_gate_pass=true`), but it is still comparison/reject evidence only because the operational gate failed on `ranking_pr_auc_ci_low=0.12868359671529103 < 0.45`.
   - The frozen non-ADRB2 guarded 100k rerun completed with `positive_count=9`, `stage2 ok_rows=40000`, leakage audit `pass=true`, and family-held-out `pass=true`, but failed claim review (`PR-AUC=0.22869872098030358`, `PR-AUC CI low=0.0019312183264511504`, `top20=0.10`). Do not relaunch the same packet as claim evidence; fix scoring/ranking quality first.
   - `gpcr_core_family_balanced_rescore_v1` frozen guarded 100k completed after the interrupted r2 run was resumed with the same tag/spec. Stage2 reused `34186` existing trajectory rows and generated `5814` remaining rows (`40000/40000` ok rows). It recovered `PR-AUC=0.5186945103743427`, `top20=0.25`, and `strict_gate_pass=true`, but failed operational claim review on `PR-AUC < 0.55` and `ranking_pr_auc_ci_low=0.1485815545422209 < 0.45`; keep it comparison/reject evidence only.
   - `fixed_family_reference` comparison-only rerun also failed the 2026-05-02 full 100k gate (`PR-AUC=0.0328`, `PR-AUC CI low=0.0045`, `top20=0.05`), so it stays reject evidence and is not a new recovery lane.

     ```bash
     python3 tools/build_gpcr_100k_failure_analysis.py
     python3 tools/build_gpcr_apply_safe_endpoint.py
     python3 tools/build_gpcr_residual_chembl50_v4_endpoint_note.py
     python3 tools/build_ligand_scaleup_kpi_table.py
     python3 tools/build_ligand_scaleup_benchmark_summary.py
     python3 tools/build_gpcr_scaleup_regression_triage.py
     python3 tools/build_gpcr_ci_low_recovery_packet.py --triage-json runs/gpcr_scaleup_regression_triage_current.json
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
   - Rank failure diagnostics source: `runs/gpcr_guarded_100k_rank_failure_diagnostics_current.json`; all three non-ADRB2 positives are tail-ranked and target-internal decoy intrusion is active, so the next implementation is `claim-locked family-balanced scoring candidate implementation`. The accepted sequence is shadow/replay -> guarded apply -> full 100k claim review; do not relaunch the same packet as claim evidence, and keep `claim_promotion_allowed=false` with threshold relaxation/fake pass forbidden.
   - Positive-coverage source: `runs/gpcr_positive_coverage_expansion_packet_current.json`; inspect selected candidate rows and their `target_specific_adrb2_bias_review_required` flags before adding any future coverage-expanded 100k rerun packet. The current non-ADRB2 freeze/family-held-out path is green, so the remaining claim blocker is CI-low/top20 scoring quality.
   - Freeze source: `runs/gpcr_positive_coverage_freeze_packet_current.json`; current `frozen=true` means the coverage floor is closed.
   - Profile support source: `runs/gpcr_frozen_candidate_profile_support_current/summary.json`; current `profile_ready=true` with RCSB structures DRD2 `6CM4`, HTR2A `6A93`, and OPRM1 `8EF6`, all ligand-centroid pocket validations `pass`.
   - Scoreability source: `runs/gpcr_frozen_candidate_scoreability_current.json`; current `pass=true`, `freeze_positive_count=9`, and `profile_positive_count=9` clear native/reference/split/meta/profile and hard-decoy coverage blockers.
   - Family-held-out scorecard source: `runs/gpcr_family_heldout_scorecard_current.json`; current `scorecard_level_status=pass`, `gpcr_positive_count=9`, and `gpcr_distinct_positive_target_count=4`.
   - Family-held-out guardrail source: `runs/gpcr_family_heldout_scorecard_guardrail_current.json`; current `status=green`, but router/platform claim remains forbidden until CI-low/top20 gates clear.
   - Guarded 100k readiness source: `runs/gpcr_guarded_100k_rerun_readiness_current.json`; current `launch_eligible=true`, `eligible=false`, `claim_review_eligible=false`, and blockers are `ci_low_below_threshold` plus `top20_stability_not_green`.
   - Crash/resume rule: rerun the exact same command with the same tag/spec after a shutdown. `run_external_validation_blind_sets.py` and `run_ligand_stress_validation.py` default to `--resume`, while stage2 trajectory generation now forwards `--traj-resume-existing` by default, so partial trajectory rows should be reused instead of regenerated.

1. PDE translation quality
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

2. Transporter AQP1 / GLUT1 evidence closure
   - Sequence AQP1 first, then GLUT1; AQP1 stays first-wave and GLUT1 stays second-wave.
   - Use the validate-only scaffold check and the transporter readiness rollup:

     ```bash
     python3 tools/run_transporter_membrane_scaffold_check.py
     python3 tools/build_transporter_membrane_readiness.py
     python3 tools/build_family_expansion_status_rollup.py
     python3 tools/build_family_evidence_acquisition_queue.py
     ```

   - Keep `AQP1` and `GLUT1` dry-run/template-only, parked/review-only, until the ligand packets are frozen, donor policy is explicit, and negative evidence/provenance closure is complete; keep `bacopaside II` as the AQP1 first-wave scope, `AqB013` as the exact-human-activity guardrail, `AqB011` as the follow-on review-only row, and `cytochalasin B` as the GLUT1 second-wave lead while `replacement_reference_binding_kcal_mol` stays blank.
   - Source artifacts: `runs/transporter_commercialization_closure_queue_current.json`, `runs/transporter_binder_verdict_progress_current.json`, `runs/transporter_placeholder_burndown_queue_current.md`.
   - Source docs: `docs/transporter_membrane_runnable_scaffold_notes.md`, `docs/transporter_membrane_expansion_scaffold_plan.md`, `docs/post_p0_evidence_closure_status.md`.

3. CA2 / PXR packet closure
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

4. IDP broader-promotion boundaries
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
- It does not treat the 2026-05-03 `ligand_heavy_runs` execute cleanup (`deleted_count=12`, `deleted_bytes=556010987428`) or the structure-support rerun payload cleanup (`38346317024` stalled bytes plus `51265129536` completed rollout bytes; `/` usage `57%`, `runs/local_heavy_runs` `28K`) as evidence or as a claim boundary change.
- It does not replace the current local-delivery gate, claim policy, or verdict validation flow.
