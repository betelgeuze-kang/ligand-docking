# Local Delivery Runbook

## Canonical Preflight

Run the delivery preflight from the repo root:

```bash
python3 tools/run_local_delivery_preflight.py
```

Before running this preflight or any ROCm accuracy bench, export `TORCH_BLAS_PREFER_HIPBLASLT=0` by default. The unsupported-architecture hipBLASLt message is a backend fallback, not a test failure, so we keep the variable fixed to make CI and delivery logs clean; the environment manifest refresh is the evidence step and must capture the actual process value in its env vars / accelerator env snapshot, with intentional supported-hardware overrides recorded as the override value instead. If the value is missing from the captured manifest, treat that as a reproducibility and log-cleanliness gap rather than an accuracy failure, and rerun the capture or leave a manifest note before delivery-ready wording. The verdict text should mirror the same default-or-override state when that setting matters to the run.

Relative to commercial tools, the current stack is roughly 80-85% of a restricted local-delivery analysis service, 70-80% on the tracked accuracy-parity scorecard, and 55-65% of a broad commercial platform. The next improvement order is keep-green regression, broader external held-out coverage, scorer/router deployment guardrails, UX/report packaging, and the separate post-P0 commercial expansion queue.

Transporter AQP1/GLUT1 evidence closure and CA2/PXR closure are post-P0 follow-up work only: AQP1 is first-wave, GLUT1 is second-wave, and CA2/PXR stay prep-only until placeholder/provenance and `replacement_reference_binding_kcal_mol` are closed.

The preflight is a green, non-dry-run evidence refresh (`summary.overall_ok=true`, `verdict_gate_required_ok=true`), and `runs/local_delivery_verdict_gate_current.json` currently reports `summary.delivery_ready=true`, `verdict=delivery_ready`, `p0_blocker_count=0`, `hard_blocker_count=0`, and `commercialization_queue_clear=true`. The current `accuracy_gate`, requirements/environment lock, latest canonical top-level nightly reentry evidence, and wetlab selected-allatom evidence are green; the PDE atomized parameterization/local-min packet reports `parameterization_ready_count=7`, `protein_local_minimization_ready_count=7`, `validated_repair_count=7`, and the selected-allatom burndown reports `hard_block_count=0`. This restricted local-delivery status may be used only for the scoped `kinase,gpcr,ion_channel` bundle and must not be widened into broad commercial all-atom/wetlab readiness. The transporter negative-evidence lane remains outside this bundle, and the next bundle step is delivery-ready only when the final bundle validator also passes.

The current state is green for the restricted local-delivery scope; keep the wording narrow and use delivery-ready wording only inside that scope. The general GPCR-family/router/platform claim remains separate and is not part of the delivery-ready state; the ADRB2 pharmacophore evidence below is target-specific candidate evidence only.

### Hard Verification Smoke

Before any delivery bundle is assembled or any verdict wording is drafted, run the hard local smoke that exercises the current gate path. Treat the outputs as evidence, not as something to massage into green.

```bash
python3 -m pytest -q tests/unit/test_morton_presort.py tests/unit/test_accuracy_gate.py tests/unit/test_run_preflight_gate.py tests/unit/test_run_local_delivery_preflight.py tests/unit/test_build_local_delivery_verdict_gate.py
TORCH_BLAS_PREFER_HIPBLASLT=0 python3 tools/run_preflight_gate.py --targets Chignolin --samples 2 --steps 10 --runs 1 --benchmark-replicas 1 --speedup-per-target-threshold 0 --label morton_neighbor_fix_smoke
```

If the smoke remains red, keep the bundle blocked/internal-review and carry the red evidence forward unchanged.

### Hard Lock And Verdict Validation

Before any delivery-ready wording is drafted, also run the hard lock and manifest checks so the current gate state is recorded rather than inferred:

```bash
python3 tools/build_local_delivery_requirements_lock.py
python3 tools/build_local_delivery_environment_manifest.py
python3 tools/build_local_delivery_verdict_gate.py
python3 tools/validate_local_delivery_bundle.py --bundle-dir <bundle_dir>
```

These commands are evidence refreshes, not green-making commands. If the requirements/environment lock still shows missing, loose/source, or missing-file required inputs, keep the bundle blocked/internal-review and record the gap instead of suppressing it. Unpinned requirement inputs are acceptable only when the generated lock text records the resolved versions for the local-delivery required set. If a rescue attempt is part of the current evidence set, run `python3 tools/validate_wetlab_tcruzi_pde_allatom_rescue_attempt.py` first and then refresh `python3 tools/build_local_delivery_verdict_gate.py` before `python3 tools/validate_local_delivery_bundle.py`; the rescue validator is evidence-integrity only and does not clear the wetlab hard gate or the queue.

Current status snapshot:

- P0-A accuracy_gate burndown is green in the current representative run: `pass=true`, failed metrics `0`, `avg_neighbor_jaccard=1.0`, and Morton presort neighbor/self-pair parity has `total_pair_outliers=0`.
- A is green for the local-delivery required set: `installed=13/13`, `missing=0`, `loose_sources=0`, `requirements_lock_complete=true`, and `environment_lock_complete=true`. The seven API/train/deploy/optional packages remain recorded as optional/deferred evidence and do not count as required local-delivery coverage.
- B is green: downstream execute evidence and the canonical top-level nightly summary are keep-green, so stage6 is no longer a representative P0 blocker. Downstream execute is supporting-only evidence and cannot replace the top-level nightly artifact. The strict canonical reentry handoff is `runs/nightly_stage6_top_level_reentry_packet_current.md` together with `runs/nightly_stage6_top_level_reentry_profile_current.json`, and that pair remains supporting-only evidence.
- C is green for wetlab selected-allatom metric evidence: `runs/wetlab_selected_allatom_gate_burndown_packet_current.json` reports `hard_block_count=0`, and `runs/wetlab_tcruzi_pde_atomized_parameterization_minimization_packet_current.json` reports `parameterization_ready_count=7`, `protein_local_minimization_ready_count=7`, and `validated_repair_count=7`. The final verdict gate is also green for the restricted scope: `runs/local_delivery_verdict_gate_current.json` currently reports `summary.delivery_ready=true`, `verdict=delivery_ready`, `p0_blocker_count=0`, and `commercialization_queue_clear=true`.
- The next bundle step is `python3 tools/build_local_delivery_bundle.py` followed immediately by `python3 tools/validate_local_delivery_bundle.py --bundle-dir <bundle_dir>`; delivery-ready wording is allowed only if that final validator passes and the scope remains restricted.

The current state is green end-to-end for the restricted local-delivery scope. Keep any broader platform, transporter, router, or unattended-operation wording out of the bundle.

### GPCR 100k Scale-up Status

운영자 주의: the general GPCR 100k family/commercial claim remains `claim_safe=false/blocked`. The ADRB2 beta-blocker-like pharmacophore candidate is target-specific evidence only, with router/general-family promotion still disallowed.

- `residual-v4 apply` failed on the core lane with `PR-AUC=0.3888` and `top20=0.15`.
- `linear C100` full rerun is reject negative evidence with `PR-AUC=0.2367` and `top20=0.05`.
- `gpcr_core_decoy_intrusion_v1` was executed shadow-first and remains blocked: `PR-AUC=0.3910`, `PR-AUC CI low=0.0183`, `top20=0.15`, failed at `stage6_operational_gate`.
- `gpcr_core_decoy_intrusion_v1` guarded apply core 100k was rerun on 2026-05-02 after moving heavy artifacts off the full `/mnt` device; it still fails the core gate (`PR-AUC=0.3890`, `PR-AUC CI low=0.0195`, `top20=0.15`) and remains reject/negative evidence.
- The refreshed scale-up KPI surface now resolves packaged-copy timing evidence instead of treating the frozen wrapper files as missing: `missing_artifact_count=0`, planning-ready `6/6`.
- The 100k benchmark remains blocked on measured evidence too: guardrails are pass `0`, fail `5`, pending `0`, and the slowest measured end-to-end speedup is only `0.458x` for `ion_trpv1_chembl50_full` versus the `>=1.8x` threshold.
- `gpcr_adrb2_beta_blocker_pharmacophore_v1` adds an ADRB2 beta-blocker/aryloxypropanolamine SMARTS reward as a target-specific residual candidate. The shadow residual-score audit is green (`binding_score_composite_v7_residual_shadow`, `PR-AUC=1.0000`, `PR-AUC CI low=1.0000`, `top20=0.30`, `positive_count=6`), but shadow evidence is not delivery or router-promotion evidence.
- The guarded apply run for the ADRB2 core 100k lane is green (`binding_score_composite_v7_residual_active`, `PR-AUC=1.0000`, `PR-AUC CI low=1.0000`, `top20=0.30`, `positive_count=6`, strict gate pass).
- The guarded apply run for the ADRB2 `ChEMBL50` 100k lane is green (`PR-AUC=0.9662`, `PR-AUC CI low=0.9264`, `top20=1.00`, `positive_count=56`, strict gate pass), but it remains bounded target-specific support rather than a general GPCR family claim.
- Treat `gpcr_core_decoy_intrusion_v1` and `gpcr_core_linear_rescore_v1` as comparison candidates only; they stay shadow/guarded-apply candidates, not immediate claim lanes. Do not claim them until the same full 100k gate is green under shadow or guarded apply evidence, with core and `ChEMBL50` lanes reported separately.
- The current triage packet is `runs/gpcr_scaleup_regression_triage_current.json`: candidate count `6`, comparison-only count `6`, reject evidence count `5`, and `primary_blocker_task=gpcr_core_full`.
- Do not widen this into GPCR-family, router-promotion, or commercial scale-up wording until a non-leaky family-held-out validation packet and family scorecard are current and green.

### Wetlab Rescue Sequence

Use this operator checklist when geometry rescue must be rerun; it is separate from the normal bundle-assembly flow and stays blocked/internal-review until the selected geometry, binding, and claim/equivalence blockers are all green.

1. Refresh `runs/wetlab_selected_allatom_repair_packet_current.md` as the next execution reference only.
2. Confirm `current_artifact_is_pointer=true`; if it is not, stop and reconcile before rerunning. Then open `attempt_dir`, read `attempt_state_json`, and verify `attempt_id`, `attempt_sequence`, `input_fingerprint_sha256`, `input_fingerprints` / `input_fingerprint_ledger`, and `attempt_artifacts`; audit the immutable rescue evidence by attempt path, not by the current pointer.
3. Move to a rescue-only branch/lane and regenerate the lane artifact bundle from the current repair packet.
4. Run `python3 tools/run_wetlab_tcruzi_pde_allatom_rescue.py --top-k 8 --filter-mode strict_then_near_fill --execute`.
5. Run `python3 tools/validate_wetlab_tcruzi_pde_allatom_rescue_attempt.py`; proceed only when `rescue_attempt_validation=pass`, and if it is not pass, stop blocked/internal-review and do not trust the attempt evidence.
6. Immediately run `python3 tools/build_local_delivery_verdict_gate.py` so the refreshed gate snapshots the rescue validator's `rescue_attempt_validation_*` fields and source artifacts.
7. Inspect the rescue summary before spending more compute: `top_k_effective` may be lower than requested, and any `rescue_review_band_mismatch_count > 0` is fail-closed evidence rather than a pass signal. If the rescue passes scoring but still shows a top-k shortfall or band mismatch, record the attempt as blocked/internal-review, rebuild the lane from the same post-slice review surface/score source until `rescue_review_band_mismatch_count=0`, rerun `python3 tools/run_wetlab_tcruzi_pde_allatom_rescue.py --top-k 8 --filter-mode strict_then_near_fill --execute`, and do not treat any downstream refresh as evidence until the rerun is validated. A pass here only confirms attempt-evidence integrity; it does not clear wetlab selected-allatom or the downstream queue.
8. Build the review packet.
9. Refresh `current_results_index`.
10. Refresh `partnering_stack`.
11. Refresh the final campaign/dashboard, burndown, queue/status, and verdict artifacts.
12. Treat claim/equivalence inputs as readiness evidence only when selected geometry and binding support are green and the current strict-release or accepted representative policy artifacts are present and source-consistent. Placeholder or missing data stays blocked/internal-review and cannot be counted as readiness evidence or used to justify a downstream refresh. `allatom_rescue_stage2_manifest` (`target,trajectory_npz,...`) is only a claim-input manifest and cannot be auto-converted, column-renamed, or otherwise promoted into the strict-release external manifest. No threshold relaxation, fake-pass, manual pass, stronger-physics pre-execution, archived/smoke strict-summary auto-adoption, or claim-equivalence shortcut is allowed.

This standardizes the same sequence before each paid local delivery:

1. strict accuracy preflight gate
2. local unit-test smoke
3. local requirements lock refresh
4. local environment manifest refresh
5. local engine provenance refresh
6. family expansion refresh
7. local engine commercialization queue rebuild
8. commercialization status report rebuild
9. local delivery verdict gate refresh

The provenance refresh should name the existing in-repo engine surfaces, not a new engine implementation.
The verdict gate is a read-only audit wrapper over the already-produced nightly, wetlab, queue, and status artifacts. The bundle writer is responsible for the persisted-vs-fresh fingerprint check and the package checksum list. The preflight is the evidence refresh; it does not itself decide delivery-ready wording.
If the operator wants to make a score-uplift or architecture-accuracy claim for a family, read `docs/family_scorecard_calibration_plan.md` first and verify the family-held-out scorecard, hard-decoy stability, calibration, and geometry/contact gate for that same family packet. The same frozen input, baseline, and held-out family packet must be used for the scorecard, baseline comparison, and acceptance profile. If those checks are not current and green, keep the wording blocked/internal-review or staged/review-only.
For scoped family claims, use explicit identity columns in the frozen packet, such as `--identity-col target --identity-col ligand_id`. The packet `family` column must be nonblank and must not use the reserved input family name `overall`. If no `--identity-col` is supplied, the builder stays in family/label-only mode and does not run a separate target/ligand completeness check, identity-columns completeness check, or duplicate explicit-identity check. When identity columns are present, blank target or ligand identity values are a frozen-packet drift risk and the scorecard builder rejects the packet before writing claim evidence. If explicit identity columns collapse two rows onto the same canonical row identity (`family`, `label`, ordered identity columns), emit a duplicate-row-identity warning, block the scorecard, and deduplicate the packet or rewrite the claim packet before delivery. Keep the same ordered `identity_columns` list across candidate and baseline packets; if the baseline scorecard's `summary.identity_columns` is missing or different, the scorecard is scorecard-level blocked and must not be used for score-uplift, architecture-accuracy, or delivery-ready wording. Record `row_identity_schema_version` with the packet so the hash meaning stays fixed; candidate/baseline schema-version mismatches are scorecard-level blocked, and legacy baselines without a schema version should be regenerated before they are used as delivery-ready evidence. If `--packet-id` is present, treat it as a human alias only and compare packets by `predictions_csv_sha256`, `row_identity_sha256`, `row_identity_schema_version`, and the ordered `identity_columns` list.
For scoped family claims, also confirm required-family coverage, `predictions_csv_sha256`, `row_identity_sha256`, and the score-resolution diagnostics before drafting any verdict text. A tie-heavy or packet-mismatched scorecard should stay in conservative wording. If target, ligand, family, label, or row order changes, restart the claim cycle instead of comparing score deltas.
If you attach a family scorecard JSON to the bundle, pass it through the bundle builder with `--family-scorecard-json <scorecard.json>` so `manifest.json.family_scorecards` can record its source path, bundle path, checksum, and summary status. That attachment bookkeeping does not change the row identity, `identity_columns`, `--packet-id`, or hard-fail rules used by scorecard generation.

### Viewer And Evidence UI Contract

`DESIGN.md` is the source of truth for the viewer/local-delivery evidence UI. If the local-delivery, nightly, or wetlab evidence surface needs restyling, change `DESIGN.md` plus the relevant `viewer/` source and regenerate the generated output artifact; do not hand-patch downstream generated artifacts. Treat `design-md` work as presentation-only; it cannot change pass/fail state or convert a blocked bundle into delivery-ready.

Keep the evidence screen hierarchy stable: `hero -> status strip -> workflow -> evidence sections`. The hero and status strip should make the gate state obvious first, the workflow section should guide the next operator action, and the evidence sections should carry the longer proof trail.

P0 gates and scientific thresholds are not softened by presentation changes. The design layer only improves evidence clarity and review speed; it never changes the pass/fail criteria.

Primary outputs:

- `runs/local_delivery_preflight_current.json`
- `runs/local_delivery_preflight_current.md`
- `runs/local_ci_tests_summary.json`
- `runs/local_delivery_requirements_lock_current.json`
- `runs/local_delivery_requirements_lock_current.md`
- `runs/local_delivery_requirements_lock_current.txt`
- `runs/local_delivery_engine_provenance_current.json`
- `runs/local_delivery_engine_provenance_current.md`
- `runs/local_delivery_environment_manifest_current.json`
- `runs/local_delivery_environment_manifest_current.md`
- `runs/local_engine_commercialization_queue_current.json`
- `runs/local_engine_commercialization_queue_current.md`
- `runs/nightly_stage6_top_level_reentry_packet_current.json`
- `runs/nightly_stage6_top_level_reentry_packet_current.md`
- `runs/nightly_stage6_top_level_reentry_profile_current.json`
- `commercialization_status_report.md`
- `runs/local_delivery_verdict_gate_current.json`
- `runs/local_delivery_verdict_gate_current.md`
- `docs/local_delivery_p0_gate.md`
- `docs/local_delivery_engine_provenance.md`
- `docs/family_scorecard_calibration_plan.md`
- `docs/local_delivery_bundle_schema.md`
- `docs/local_delivery_dependency_freeze.md`
- `docs/local_delivery_environment_baseline.md`

## P0 Gate

P0 starts here: do not issue a delivery-ready verdict unless the current preflight evidence, requirements lock, environment manifest, and verdict-gate artifacts are fresh; `runs/local_delivery_verdict_gate_current.json` reports `summary.delivery_ready=true`; the final bundle validator reports `summary.overall_ok=true` and `summary.delivery_ready_policy_ok=true`; wetlab selected-allatom is pass with no hard/semi-hard blockers; and the commercialization queue is clear. The current snapshot is green for the restricted `kinase,gpcr,ion_channel` local-delivery scope: `delivery_ready=true`, `p0_blocker_count=0`, `hard_blocker_count=0`, and `commercialization_queue_clear=true`. The review packet -> `current_results_index` -> `partnering_stack` -> final/dashboard -> burndown -> verdict chain must stay on the same metric source, and any mismatch is a source-consistency regression rather than pass evidence. The nightly stage6 summary is keep-green evidence with `top_priority_status=keep_green`. If `runs/wetlab_selected_allatom_repair_packet_current.md` exists, treat it as a future regression/retry reference, not as proof of pass. The current stage3 smoke and downstream execute artifacts are supporting-only evidence.

Use these artifacts as the operator rollup:

- `runs/local_delivery_preflight_current.json`
- `runs/local_delivery_preflight_current.md`
- `runs/local_delivery_environment_manifest_current.json`
- `runs/local_delivery_environment_manifest_current.md`
- `runs/nightly_gate_burndown_packet_current.json`
- `runs/nightly_gate_burndown_packet_current.md`
- `runs/nightly_stage6_top_level_reentry_packet_current.json`
- `runs/nightly_stage6_top_level_reentry_packet_current.md`
- `runs/nightly_stage6_top_level_reentry_profile_current.json`
- `runs/ligand_htvs_nightly_2026-04-26_summary.json`
- `runs/ligand_htvs_nightly_2026-04-26_smoke_stage3_summary.json`
- `runs/wetlab_selected_allatom_gate_burndown_packet_current.json`
- `runs/wetlab_selected_allatom_gate_burndown_packet_current.md`
- `runs/local_engine_commercialization_queue_current.json`
- `runs/local_engine_commercialization_queue_current.md`
- `commercialization_status_report.md`

The `local_delivery_verdict_gate` output is the conservative final gate over those existing artifacts. It does not rerun the engine or prove the science. Read `runs/local_delivery_verdict_gate_current.json` and use delivery-ready wording only when `summary.delivery_ready=true`, the review packet -> `current_results_index` -> `partnering_stack` -> final/dashboard -> burndown -> verdict chain is on the same metric source, the final bundle validator reports `summary.overall_ok=true` and `summary.delivery_ready_policy_ok=true`, and `manifest.json` / `manifest.md` record `verdict_gate_fingerprint_check.status=pass`, `ok=true`, `comparison_performed=true`, and `mismatch_count=0`. If either check is false, the bundle can still be shared as a blocked bundle for internal review, but the verdict must stay negative/internal-review and the manifest must name the mismatch reason. A downstream execute pass or rerun artifact is helpful evidence, but it is supporting-only evidence and does not replace the verdict path.
Treat the gate JSON as an audit wrapper over the existing artifacts: its `source_artifacts` entries should carry `path`, `present`, `required`, `status`, `sha256`, `size_bytes`, `mtime_ns`, `mtime_epoch`, `mtime_local`, `generated_at`, `json_valid`, and `parse_error`. The final bundle validator is the last local verification step before delivery-ready wording; it checks `checksums.sha256`, `manifest.json` / `manifest.md`, required files, and `verdict_gate_fingerprint_check.status=pass`, `ok=true`, `comparison_performed=true`, and `mismatch_count=0`. The checksum policy excludes `checksums.sha256` itself and the validator's own `validation.json` / `validation.md`; every other bundle file must be listed exactly once.

## Canonical Flow

Use the same order every time:

1. `python3 tools/run_local_delivery_preflight.py`
2. run the scoped local job for the delivery request
3. rerun `python3 tools/run_local_delivery_preflight.py`
4. verify `current_results_index.summary.partnering_stack_artifact_complete=true`; then verify `runs/wetlab_partnering_stack_current.json` and `runs/wetlab_partnering_stack_current.md` are full `wetlab_partnering_stack_ready` artifacts with `artifact_completeness=full_partnering_stack`, the selected-allatom metric source chain, selected-allatom gates, and freshness/source provenance; if the flag is false/missing or they only expose `summary.status="ok"`, stop blocked/internal-review and record blocker `partnering_stack_placeholder_or_incomplete`
5. assemble the delivery bundle from the refreshed artifacts plus the exact run outputs:
   `python3 tools/build_local_delivery_bundle.py --bundle-tag <tag> --request-summary "<summary>" --delivery-scope "<scope>" --claim-scope "<claim_scope>" --verdict "<allowed verdict sentence>" --rerun-command "python3 tools/run_local_delivery_preflight.py" --config-path <config> --artifact-path <artifact> [--family-scorecard-json <scorecard.json>]`
6. validate the assembled bundle with `python3 tools/validate_local_delivery_bundle.py --bundle-dir <bundle_dir>`
7. issue a verdict using `docs/local_delivery_claim_policy.md`

Use these companion docs during steps 5 and 6:

- `docs/local_delivery_p0_gate.md`
- `docs/local_delivery_engine_provenance.md`
- `docs/local_delivery_bundle_schema.md`
- `docs/local_delivery_dependency_freeze.md`
- `docs/local_delivery_environment_baseline.md`
- `docs/local_delivery_manifest_template.md`
- `docs/local_delivery_verdict_template.md`

The bundle builder copies `environment/engine_provenance.json` and `environment/engine_provenance.md` alongside the environment manifest and requirements lock.
The bundle validator is the final local verification step before any delivery-ready wording is used.

## Verdict Guardrails

Do not issue a delivery-ready verdict when:

- the preflight wrapper is not green
- the current preflight, environment manifest, or verdict-gate artifact is missing, stale, or mismatched, so blocked/internal-review evidence has not been established yet
- the current requirements lock is incomplete, missing, loose, or unpinned
- `runs/local_delivery_verdict_gate_current.json` does not report `summary.delivery_ready=true`
- the final bundle validator does not report `summary.overall_ok=true` and `summary.delivery_ready_policy_ok=true`
- `runs/local_delivery_verdict_gate_current.json` source artifact fingerprints do not match the current bundle/work record or look stale
- `manifest.json` / `manifest.md` do not record `verdict_gate_fingerprint_check.status=pass`, `ok=true`, `comparison_performed=true`, and `mismatch_count=0`
- `runs/local_delivery_environment_manifest_current.json` / `runs/local_delivery_environment_manifest_current.md` do not record the actual `TORCH_BLAS_PREFER_HIPBLASLT` export, or an intentional override is not echoed in the verdict notes
- `current_results_index.summary.partnering_stack_artifact_complete` is not `true`, or `runs/wetlab_partnering_stack_current.json` / `runs/wetlab_partnering_stack_current.md` is placeholder/minimal (`summary.status="ok"` only) or missing `wetlab_partnering_stack_ready`, `artifact_completeness=full_partnering_stack`, the selected-allatom metric source chain, selected-allatom gates, or freshness/source provenance; record blocker `partnering_stack_placeholder_or_incomplete` and keep the bundle blocked/internal-review
- the review packet -> `current_results_index` -> `partnering_stack` -> final/dashboard -> burndown -> verdict disagree on the metric source or metric value, even if downstream execute artifacts look promising, because downstream execute is supporting-only evidence
- for P0-C, the review band and numeric `mean_min_distance_A` must come from the same post-slice review surface/score source; `runs/wetlab_rescue_three_bead_candidates_current.json` is only a ranking seed/fallback, not band authority, and after any mismatch the lane must be rebuilt until `rescue_review_band_mismatch_count=0` before rerunning `strict_then_near_fill` or treating downstream refreshes as evidence
- `commercialization_status_report.md` still shows wetlab selected-all-atom as an open hard blocker, the claim metric is missing, or the claim gate / hard / semi-hard blockers remain open; the commercialization queue is downstream of wetlab selected-allatom and should not be treated as independently clear
- the commercialization queue is still blocked
- the result scope falls outside `kinase`, `ion_channel`, or `gpcr`
- transporter or broad platform wording appears in the bundle
- scorecard-level baseline comparison or acceptance-profile language is being treated as delivery-ready wording
- the bundle validator may record a fingerprint mismatch for a blocked/internal-review bundle, but that state does not promote the bundle to delivery-ready
- score-uplift or architecture-accuracy wording is being used without the family-held-out scorecard baseline described in `docs/family_scorecard_calibration_plan.md`
- any bundled family scorecard reports `summary.scorecard_level_status` other than `pass` or `summary.acceptance_overall_pass == false`; blocked scorecards may stay in blocked/internal-review bundles as diagnostics, but they cannot support delivery-ready wording
- the bundle carries no family scorecard; that absence does not by itself create a new delivery-ready blocker here, but score-uplift and architecture-accuracy claims still need scorecard evidence

## Heavy Artifact Cleanup

Keep the `runs/` summary, evidence, manifest, and verdict artifacts as preserved evidence. Cleanup is limited to heavy trajectory frames, derived caches, and similar large intermediates under `ligand_heavy_runs`; do not treat those cleanup steps as a way to prune the delivery record.

`ligand_heavy_runs` cleanup is housekeeping only. It does not change the delivery claim, any measured metric, or the `claim_safe=false` GPCR scale-up boundary described below.

Before deleting anything, run a dry-run inventory first and compare the candidate delete list against the manifest or explicit path list for the exact objects to remove. If the dry-run output or manifest check is missing, stale, or ambiguous, stop and keep the data.

## Dry Run

To preview the exact step order without executing it:

```bash
python3 tools/run_local_delivery_preflight.py --dry-run
```

The preflight summary can only mark `verdict_gate_fingerprint_check.status=pending_bundle_check`; the actual persisted-vs-fresh comparison is performed by `tools/build_local_delivery_bundle.py` while writing `manifest.json` and `manifest.md`.
