# Post-P0 Evidence Closure Status

## Purpose

This note is an operator map for the post-P0 lanes that stay outside the current local delivery claim. The restricted local P0 delivery state is green, but the GPCR scale-up regression guardrail is still the primary blocker for any commercial claim expansion. The current delivery claim remains limited to `kinase`, `ion_channel`, and `gpcr`. Do not use this note to widen delivery wording or to treat recovery-band signal as claim-safe or router/platform-ready; `claim_promotion_allowed=false` stays in force. The non-ADRB2 freeze workflow is no longer blocked on launch prerequisites: freeze, frozen-candidate scoreability, family-held-out, and leakage audit are green. Claim review remains blocked by the actual guarded 100k rerun metrics: CI-low and top20 stability.

## Claim Boundary

- `runs/post_p0_claim_blocker_rollup_current.json` is the current cross-lane blocker rollup. It keeps `claim_promotion_allowed=false` and orders the post-P0 work as GPCR CI-low/top20 scoring recovery first, then PDE translation quality, then transporter, CA2, PXR, and IDP boundaries.
- GPCR recovery candidates (`gpcr_core_decoy_intrusion_v1`, `gpcr_core_linear_rescore_v1`, `gpcr_core_mismatch_contact_rescore_v1`, `gpcr_core_structure_support_rescore_v1`) stay comparison-only shadow/guarded-apply lanes. The `positive_count >= 9` frozen-packet launch prerequisite, family-held-out scorecard, and leakage audit are now green, but no claim promotion is allowed until the full 100k claim-review gate clears CI-low and top20 stability.
- `gpcr_core_mismatch_contact_rescore_v1` completed the 2026-05-02 safesync/cache-disabled guarded apply run, but the operational gate still failed (`PR-AUC=0.3836`, `PR-AUC CI low=0.0157`, `top20=0.15`), so it remains reject evidence only.
- `gpcr_core_structure_support_rescore_v1` completed the 2026-05-03 guarded apply rollout run with recovery-band ranking signal (`PR-AUC=0.592849548112706`, `ROC-AUC=0.9961310119404976`, `top20=0.25`, `strict_gate_pass=true`), but the operational gate still failed on `ranking_pr_auc_ci_low=0.12868359671529103 < 0.45`; it remains reject/comparison evidence.
- The frozen non-ADRB2 guarded 100k rerun completed with `positive_count=9`, `stage2 ok_rows=40000`, leakage audit `pass=true`, and family-held-out `pass`, but it failed claim review: `PR-AUC=0.22869872098030358`, `PR-AUC CI low=0.0019312183264511504`, and `top20=0.10`.
- `runs/gpcr_ci_low_recovery_packet_current.json` is the current operator packet for this blocker: positive ranks are `[1, 2, 94, 715, 816, 1101, 1413, 3138, 5298]`, top20 hit count is `2/20`, top20 ceiling is `0.45`, and the low CI confirms that the remaining blocker is ranking quality, not positive coverage.
- `runs/gpcr_guarded_100k_rank_failure_diagnostics_current.json` narrows the ranking blocker: all three non-ADRB2 positives are tail-ranked (`HTR2A` global rank `1413`, `OPRM1` `3138`, `DRD2` `5298`), and target-internal decoy intrusion remains active. The next scoring candidate must be claim-locked and family-balanced; do not patch by threshold relaxation or label/decoy-name leakage.
- `config/gpcr_non_adrb2_positive_candidates_v1.csv` is the curated candidate input schema for the GPCR non-ADRB2 positive freeze workflow. It now carries three ChEMBL_36 non-ADRB2 human GPCR positives (`DRD2`, `HTR2A`, `OPRM1`). `runs/gpcr_non_adrb2_positive_candidates_leakage_audit_current.json` is `pass=true`, and `runs/gpcr_positive_coverage_freeze_packet_current.json` is `frozen=true` with `positive_count=9`, `new_non_adrb2_positive_count=3`, `distinct_positive_gpcr_target_count=4`, and `leakage_audit_pass=true`; the freeze is green and this does not change `claim_promotion_allowed=false`.
- `runs/gpcr_positive_coverage_expansion_packet_current.json` is the current positive-coverage expansion packet. It records `observed_positive_count=6`, `minimum_positive_count_for_frozen_packet=9`, `minimum_non_leaky_positive_additions=3` (the non-leaky GPCR +3 requirement), `full_100k_guarded_rerun_eligible=false`, and selected ChEMBL50 ADRB2 candidate rows with `target_specific_adrb2_bias_review_required`; treat this packet as the candidate leakage-audit review surface before freeze, and keep these rows coverage-only/review-required, not router/platform claim evidence.
- `runs/gpcr_family_heldout_scorecard_current.json` is the current family-held-out scorecard. It is now `scorecard_level_status=pass` with `gpcr_positive_count=9` and distinct positive targets `ADRB2_GPCR_BLIND`, `CHEMBL217_DRD2_HUMAN`, `CHEMBL224_HTR2A_HUMAN`, and `CHEMBL233_OPRM1_HUMAN`.
- `runs/gpcr_family_heldout_scorecard_guardrail_current.json` is the current family-held-out guardrail wrapper. It is `green`, but this still does not promote the claim by itself without the full 100k CI-low/top20 gate.
- `runs/gpcr_frozen_candidate_profile_support_current/summary.json` is `profile_ready=true` after materializing RCSB native structures and ligand-centroid pocket checks for DRD2 `6CM4`, HTR2A `6A93`, and OPRM1 `8EF6`; all three centroid validations are `pass`.
- `runs/gpcr_frozen_candidate_scoreability_current.json` is the scorer/native/profile coverage check for the frozen non-ADRB2 candidates. It is now `pass=true` with `blocker_count=0`, `freeze_positive_count=9`, and `profile_positive_count=9`, covering profile targets, hard-decoy targets, native paths, ranking labels, eval splits, target meta, and ligand meta.
- `runs/gpcr_guarded_100k_rerun_readiness_current.json` is the current guarded rerun readiness packet. It separates launch readiness from claim review: `launch_eligible=true` with no launch blockers, while `eligible=false` / `claim_review_eligible=false` remains blocked only by `ci_low_below_threshold` and `top20_stability_not_green`. Do not relaunch the same guarded packet as claim evidence; fix scoring/ranking quality first.
- `fixed_family_reference` scaling is wired and executed as a guarded comparison-only rerun lane. Current stats are fit-role only (`runs/gpcr_score_reference_stats_current.json`: `reference_row_count=24`, `eval_role_used_in_reference_count=0`, feature stats `12/12`), and the decoy-intrusion candidate set-spec is `runs/gpcr_scaleup_100k_fixed_reference_decoy_intrusion_candidate_current/specs/gpcr_core_decoy_intrusion_100k_fixed-ref-decoy-intrusion100k.json`. The 2026-05-02 full 100k run completed but failed (`PR-AUC=0.0328`, `PR-AUC CI low=0.0045`, `top20=0.05`), so it is reject evidence, not a recovery.
- PDE translation quality stays on the `binding_energy_proxy` → `pose RMSD` → `backmapping` → `local minimization survival` order; keep `claim_promotion_allowed=false` until that sequence closes.
- Heavy cleanup under `ligand_heavy_runs` is storage housekeeping only. The 2026-05-02 cleanup deleted 189 stale `stage2_trajectory_frames` payloads (`98125333296` bytes). The 2026-05-03 follow-up manifests are `runs/ligand_heavy_runs_cleanup_*_2026-05-03.json`; the execute pass deleted_count=12 remaining raw trajectory payloads (`556010987428` bytes), and the structure-support rerun cleanup deleted the stalled partial payload (`38346317024` bytes) plus the completed rollout payload (`51265129536` bytes). After cleanup `/` usage is `57%` with `runs/local_heavy_runs` at `28K`. Keep `runs/` summary/evidence artifacts, manifests, and verdict records intact; delete only heavy trajectory frames/cache after a dry-run inventory matches the manifest or explicit delete list. Cleanup does not change the delivery claim, any metric, or the current GPCR `claim_safe=false` boundary.
- Transporter AQP1/GLUT1 remains an evidence-closure track outside the delivery claim.
- CA2 stays prep-only outside the delivery claim until placeholder/provenance and `replacement_reference_binding_kcal_mol` closure are complete.
- PXR stays prep-only / partial-authoritative outside the delivery claim until placeholder/provenance closure and all `replacement_reference_binding_kcal_mol` rows are closed.
- No fabricated kcal/mol, no threshold relaxation, no delivery-ready wording.

### GPCR CI-low Recovery Packet

- Refresh the cross-lane blocker rollup with `python3 tools/build_post_p0_claim_blocker_rollup.py`.
- `runs/gpcr_ci_low_recovery_packet_current.md` is the operator packet for the current GPCR blocker: `## Metric Table` carries `ranking_pr_auc_ci_low`, `ranking_topk_hit_rate_max_possible`, and `ranking_positive_count`; `## Rank And Bootstrap Diagnostics` carries `positive_ranks` and `top20_missing_positives`; `## Recommended Next Actions` keeps the next hard blocker order.
- `runs/gpcr_guarded_100k_rank_failure_diagnostics_current.md` is the operator packet for the current rank-quality blocker; it carries positive global/within-target ranks and top decoy intrusions.
- Refresh it with `python3 tools/build_gpcr_ci_low_recovery_packet.py --triage-json runs/gpcr_scaleup_regression_triage_current.json`.
- Refresh the positive-coverage expansion packet with `python3 tools/build_gpcr_positive_coverage_expansion_packet.py`; inspect `## Selected Candidate Rows` before freezing any new 100k rerun packet.
- Refresh the non-ADRB2 candidate leakage audit with `python3 tools/build_gpcr_non_adrb2_candidate_leakage_audit.py`, then refresh the freeze packet with `python3 tools/build_gpcr_positive_coverage_freeze_packet.py`; `frozen=true` is necessary but not sufficient for launch.
- Refresh frozen-candidate profile support with `python3 tools/build_gpcr_frozen_candidate_profile_support.py --native-source-csv config/gpcr_non_adrb2_native_sources_v1.csv`, then refresh frozen-candidate scoreability with `python3 tools/build_gpcr_frozen_candidate_scoreability_packet.py --profile-json runs/gpcr_frozen_candidate_profile_support_current/profile.json`; both are green now but remain non-claim-authorizing.
- Refresh the family-held-out scorecard and guardrail with the current guarded rerun rows: `python3 tools/build_gpcr_family_heldout_scorecard.py --rows-csv runs/ligand_stress_validation_2026-05-03_gpcr_frozen_nonadrb2_guarded100k_p0_n100000_r1_stage5_ranking_rows.csv --summary-json runs/ligand_stress_validation_2026-05-03_gpcr_frozen_nonadrb2_guarded100k_p0_n100000_r1_stage5_ranking_summary.json` then `python3 tools/build_gpcr_family_heldout_scorecard_guardrail.py`.
- Refresh guarded full-100k readiness with `python3 tools/build_gpcr_guarded_100k_rerun_readiness.py --leakage-audit-json runs/ligand_stress_validation_2026-05-03_gpcr_frozen_nonadrb2_guarded100k_p0_n100000_r1_stage0_leakage_summary.json`; `launch_eligible=true` is only a rerun launch signal and still does not set `claim_promotion_allowed=true`.
- `claim_safe=false` stays in force; this packet is comparison-only and does not widen the delivery claim.

### Transporter AQP1 / GLUT1

Current status:

- `runs/transporter_commercialization_closure_queue_current.json`: `queue_row_count=6`, `first_wave_target=AQP1`, `second_wave_target=GLUT1`, `current_phase=blocker_closure_seed_row_promotion`
- `runs/transporter_binder_verdict_progress_current.json`: manual verdict backlog cleared, `6/6` complete
- `runs/transporter_placeholder_burndown_queue_current.md`: `placeholder_queue_rows=12`
- `runs/aqp1_first_seed_row_packet_current.md`, `runs/aqp1_first_wave_source_confirmation_packet_current.md`, `runs/aqp1_follow_on_source_confirmation_packet_current.md`, `runs/glut1_second_wave_source_confirmation_packet_current.md`

Claim boundary:

- AQP1 is first-wave, GLUT1 is second-wave.
- `AqB013` stays the exact-human-activity hold and `replacement_reference_binding_kcal_mol` stays blank.
- `AqB011` stays review-only until exact target-pair evidence is curated.
- `cytochalasin B` stays the GLUT1 second-wave lead.

Next refresh:

```bash
python3 tools/run_transporter_membrane_scaffold_check.py
python3 tools/build_transporter_membrane_readiness.py
```

### CA2

Current status:

- `runs/ca2_core_ligand_ledger_current.json`: core ledger now has `ligand_count=3`, `ready_for_packet_count=3`, `placeholder_ligand_id_count=0`.
- `runs/ca2_packet_replacement_readiness_current.json`: replacement workbook remains blocked, `ready_row_count=0/12`, `blocked_row_count=12`, most common missing field `replacement_ligand_id`.
- The active blocker set is still synchronized replacement workbook closure: `replacement_ligand_id`, `replacement_reference_binding_kcal_mol`, `replacement_source`, `replacement_smiles`, and `replacement_scaffold`.

Claim boundary:

- CA2 is prep-only and stays outside the delivery claim until the replacement workbook is filled and the synchronized triple-edit back into reference/split/meta is complete.

Next refresh:

```bash
python3 tools/build_ca2_packet_replacement_workbook.py
python3 tools/build_ca2_packet_replacement_readiness.py
```

### PXR

Current status:

- `runs/pxr_ligand_packet_fill_workbook_current.json`: `packet_count=2`, `ligand_row_count=8`, `packets_ready_for_policy_freeze=2`, `placeholder_row_count=0`
- `runs/pxr_packet_fill_readiness_current.json`: `queue_row_count=14`, `ready_for_apply_row_count=8`, `blocked_row_count=6`, `most_common_missing_field=replacement_reference_binding_kcal_mol`
- `runs/pxr_quantitative_provenance_packet_current.json`: quantitative provenance blocker ledger; do not fill quantitative binder fields until an explicit human PXR value/proxy is attached
- `runs/pxr_pending_resolution_packet_current.json`: review-only rows stay locked, deferred rows stay parked
- `runs/pxr_next_verification_slice_current.json`: unresolved rows stay deferred unless target-specific human activity supports safer classification

Claim boundary:

- PXR is prep-only / partial-authoritative and stays outside the delivery claim until placeholder/provenance closure and all `replacement_reference_binding_kcal_mol` rows are closed.

Next refresh:

```bash
python3 tools/build_pxr_ligand_packet_fill_workbook.py
python3 tools/validate_pxr_packet_fill_readiness.py
```

If you are working the review-only/defer ledger instead, keep that work on `runs/pxr_pending_resolution_packet_current.json` and `runs/pxr_next_verification_slice_current.json` rather than delivery wording.

## Reminder

These lanes are evidence-closure work only. They do not change the current delivery claim.
