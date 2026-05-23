# Local Delivery Verdict Template

## Purpose

Use this template to write the final bundle verdict without drifting outside the local-delivery-only claim boundary. The allowed initial scope is limited to `kinase`, `ion_channel`, and `gpcr`.

This wording is intended for bundles assembled by `python3 tools/build_local_delivery_bundle.py`.
The final local bundle validator is `python3 tools/validate_local_delivery_bundle.py --bundle-dir <bundle_dir>`.

Current status snapshot: the current `accuracy_gate` is `pass=true` with failed metrics `0`, and the Morton presort neighbor/self-pair parity smoke records `total_pair_outliers=0`; the requirements/environment lock is green for the local-delivery required set (`installed=13/13`, `missing=0`, `loose_sources=0`, `requirements_lock_complete=true`, `environment_lock_complete=true`, `optional_missing_count=7`). The canonical top-level nightly reentry evidence and wetlab selected-allatom evidence are current. The selected-allatom burndown is green with `hard_block_count=0`, and the PDE atomized parameterization/local-min packet reports `parameterization_ready_count=7`, `protein_local_minimization_ready_count=7`, and `validated_repair_count=7`. `runs/local_delivery_verdict_gate_current.json` currently reports `summary.delivery_ready=true`, `verdict=delivery_ready`, `p0_blocker_count=0`, `hard_blocker_count=0`, and `commercialization_queue_clear=true`, aligned with `runs/local_engine_commercialization_queue_current.json` (`queue_clear=true`, `blocked_count=0`, `top_priority_status=keep_green`). The next packaging step may use delivery-ready wording only after the final bundle validator passes; any bundle must still stay within the restricted local-delivery scope.
The bundle path is currently green for the restricted local-delivery scope: `runs/local_delivery_verdict_gate_current.json` reports `summary.delivery_ready=true`, and the commercialization queue is clear. If `runs/wetlab_selected_allatom_repair_packet_current.md` exists, it can still serve as a next-execution reference for future regressions, but it does not widen the current delivery-ready state.

The next packaging path is `python3 tools/build_local_delivery_bundle.py` -> `python3 tools/validate_local_delivery_bundle.py --bundle-dir <bundle_dir>`; use delivery-ready wording only when the validator and verdict gate are both green.

Relative to commercial tools, the current stack is roughly 80-85% of a restricted local-delivery analysis service, 70-80% on the tracked accuracy-parity scorecard, and 55-65% of a broad commercial platform. The next improvement order is keep-green regression, broader external held-out coverage, scorer/router deployment guardrails, and UX/report packaging.

## Verdict Rules

- Pick exactly one verdict sentence. Do not combine sentences.
- Keep the verdict narrow. Do not imply transporter coverage or general platform readiness.
- Use the exact bundle artifacts as the basis for the verdict.
- Before any delivery-ready wording is used, the requirements/environment lock must be green and `runs/local_delivery_verdict_gate_current.json` must report `summary.delivery_ready=true`; A/B/C must also all be green: the current preflight, requirements lock, environment manifest, and verdict-gate artifacts are fresh; the canonical top-level nightly summary is green; the review packet -> `current_results_index` -> `partnering_stack` -> final/dashboard -> burndown -> verdict chain is source-consistent; the current strict-release or accepted representative claim/equivalence policy artifacts are present and source-consistent; archived/smoke strict summaries and rescue-state JSON have not been auto-adopted; and wetlab selected all-atom is pass with `mean_min_distance_A <= 2.500` and no open hard/semi-hard blockers.
- The preflight and nightly stage6 evidence are supporting-only evidence and do not replace the separate verdict gate, even when execute/no-execute outputs exist. The commercialization queue may be treated as clear only after wetlab selected-allatom is green. Stage3 smoke and downstream execute artifacts are supporting-only evidence and do not replace the verdict gate.
- If review packet, `current_results_index`, `partnering_stack`, final/dashboard, burndown, or verdict ever disagree on the metric source or metric value again, treat the mismatch as a canonical-source freshness regression; keep the values artifact-specific and do not treat any surface as pass evidence while the strict threshold is missed or another wetlab hard blocker remains open.
- If any part of A/B/C is not green, including missing or fail-closed current/source-consistent claim/equivalence policy evidence, use the internal-review sentence only and stop.
- Do not fake-pass the gate, perform threshold relaxation, manual-pass the evidence, or manipulate outputs to manufacture delivery-ready wording; the verdict must reflect the recorded local outputs exactly.
- `python3 tools/validate_local_delivery_bundle.py --bundle-dir <bundle_dir>` must report `summary.overall_ok=true` and `summary.delivery_ready_policy_ok=true` before any delivery-ready wording is used.
- `runs/local_delivery_verdict_gate_current.json` must report `summary.delivery_ready=true`, the gate's `source_artifacts` fingerprints must match the current bundle/work record after the persisted-vs-fresh comparison, including the `current_results_index` and `partnering_stack` labels, and `manifest.json` / `manifest.md` must record `verdict_gate_fingerprint_check.status=pass`, `ok=true`, `comparison_performed=true`, and `mismatch_count=0` before any delivery-ready wording is used.
- If `summary.delivery_ready=false`, or the fingerprints look stale or mismatched, or `verdict_gate_fingerprint_check.status` is not `pass`, or `current_results_index` or `partnering_stack` are absent, stale, or mismatched, or the rescue validator's `rescue_attempt_validation_*` snapshot is absent, stale, or mismatched, or the final bundle validator reports `summary.overall_ok=false` or `summary.delivery_ready_policy_ok=false`, the bundle may still be shared as a blocked bundle for internal review, but the verdict must be internal-review only and must not say delivery-ready. The manifest must keep the mismatch reason.
- For rescue runs, confirm the immutable attempt ledger before reusing any output: `attempt_id`, `attempt_sequence`, `input_fingerprint_sha256`, `input_fingerprints` / `input_fingerprint_ledger`, `attempt_dir`, `attempt_state_json`, `attempt_artifacts`, and `current_artifact_is_pointer` must agree. The current artifact is only a pointer, and the attempt path is the evidence record. Run `python3 tools/validate_wetlab_tcruzi_pde_allatom_rescue_attempt.py`, then refresh `python3 tools/build_local_delivery_verdict_gate.py` before any downstream review packet/queue/status refresh so the gate summary/source_artifacts snapshot can mirror the rescue validator's `rescue_attempt_validation_*` fields. If `rescue_attempt_validation` is not pass, do not reuse the attempt evidence and keep the verdict blocked/internal-review only. A pass on the rescue validator only confirms attempt-evidence integrity; it does not clear wetlab selected-allatom or the downstream queue.
- If `family_scorecards` are present in the bundle, every included scorecard must also report `summary.scorecard_level_status="pass"` and `summary.acceptance_overall_pass != false` before any delivery-ready wording is used.
- A bundled scorecard may stay in a blocked/internal-review bundle as diagnostic evidence, but its manifest entry must stay blocked and delivery-ready wording is forbidden while it remains blocked.
- If a required family is missing, if an input `family` value is blank or uses the reserved aggregate name `overall`, if no `--identity-col` is supplied then do not invent a separate target/ligand completeness check, identity-columns completeness check, or duplicate explicit-identity check, if the candidate and baseline do not share the same ordered `identity_columns` list, or the baseline scorecard's `summary.identity_columns` is missing or different, if `row_identity_schema_version` differs, if any declared identity value is blank, if explicit identity columns create a duplicate canonical row identity, if `row_identity_sha256` changes, or if the scorecard is tie-heavy, keep the verdict blocked or internal-review only even when the rest of the bundle is clean. Declared blank identity values should normally fail scorecard generation before verdict drafting. If a packet has `--packet-id`, treat it as a human alias only; the authoritative contract is `predictions_csv_sha256`, `row_identity_sha256`, `row_identity_schema_version`, and the ordered `identity_columns` list.
- If `current_results_index.summary.partnering_stack_artifact_complete` is not `true`, or `runs/wetlab_partnering_stack_current.json` or `runs/wetlab_partnering_stack_current.md` is placeholder/minimal, only reports `summary.status="ok"`, or lacks `wetlab_partnering_stack_ready`, `artifact_completeness=full_partnering_stack`, the selected-allatom metric/source/gates, or freshness/source provenance, record blocker `partnering_stack_placeholder_or_incomplete` and keep the verdict blocked/internal-review only.
- A delivery-ready verdict is not itself a score-uplift or architecture-accuracy claim; if the bundle text makes those claims, they must separately satisfy `docs/family_scorecard_calibration_plan.md`.
- A scorecard baseline, baseline comparison, or acceptance profile is scorecard-level only; it does not make the verdict delivery-ready by itself.
- The absence of bundled family scorecards does not by itself block delivery-ready wording in this template; it only means score-uplift and architecture-accuracy claims still need scorecard evidence under the calibration plan.
- Claim/equivalence inputs are post-gate review artifacts only; they can contribute to final readiness only after wetlab selected-allatom is green, the current/source-consistent strict release summary exists, the real external accuracy CSV with `target,avg_rmsd_aligned,avg_rmsd_vs_native_aligned` exists, the strict-release external manifest rows pass path-existence, coordinate-load, engine, representation-atom-count, and target-registry checks, and `T. cruzi PDE` has its target registration/profile/canonical reference path in place. `python3 tools/build_allatom_claim_evidence_handoff.py` then summarizes the ready handoff state: direct and upstream inputs are present, the claim-input CSV (`target,trajectory_npz,...`) stays separate from the strict external manifest, and the preflight accuracy gate CSV remains core gate evidence only rather than a substitute for the external claim CSV.
- If the bundle is valid but the operator wants to emphasize the scope boundary, use the restricted verdict.

## Copy-Ready Verdicts

### Delivery-Ready For Guarded Local Validation

`Delivery-ready for guarded local validation on the scoped kinase / ion-channel / GPCR workflow documented in this bundle.`

Use this only when:

- the final preflight is green and the requirements/environment lock is green
- the nightly gate passes
- the wetlab selected all-atom gate passes
- the bundle is complete and reproducible
- the final bundle validator reports `summary.overall_ok=true` and `summary.delivery_ready_policy_ok=true`
- `runs/local_delivery_verdict_gate_current.json` reports `summary.delivery_ready=true`
- the gate's `source_artifacts` fingerprints match the current bundle/work record after the persisted-vs-fresh comparison, including `current_results_index` and `partnering_stack`
- `manifest.json` / `manifest.md` record `verdict_gate_fingerprint_check.status=pass`, `ok=true`, `comparison_performed=true`, and `mismatch_count=0`
- if `family_scorecards` are present, each included scorecard reports `summary.scorecard_level_status="pass"` and `summary.acceptance_overall_pass != false`
- the verdict stays within the allowed local-delivery scope

### Delivery-Ready Only For Restricted Scope

`Delivery-ready only for the attached restricted scope; not a general commercialization verdict for all families.`

Use this when:

- the bundle is valid
- the scope must stay explicitly limited to `kinase`, `ion_channel`, and `gpcr`
- you want to prevent the verdict from being read as a broad platform claim
- the requirements/environment lock is green and `runs/local_delivery_verdict_gate_current.json` reports `summary.delivery_ready=true`
- the final bundle validator reports `summary.overall_ok=true` and `summary.delivery_ready_policy_ok=true`
- `runs/local_delivery_verdict_gate_current.json` reports `summary.delivery_ready=true`
- the gate's `source_artifacts` fingerprints match the current bundle/work record after the persisted-vs-fresh comparison, including `current_results_index` and `partnering_stack`
- `manifest.json` / `manifest.md` record `verdict_gate_fingerprint_check.status=pass`, `ok=true`, `comparison_performed=true`, and `mismatch_count=0`
- if `family_scorecards` are present, each included scorecard reports `summary.scorecard_level_status="pass"` and `summary.acceptance_overall_pass != false`

### Internal-Review Only

Internal-review only is the fallback verdict when `summary.delivery_ready=false`, the source chain drifts, or the final bundle validator fails. Keep it narrow, record the exact mismatch reason in `manifest.md`, and do not widen the scope beyond the attached restricted bundle.

Use this when:

- any part of A/B/C is still open
- the current preflight, requirements lock, environment manifest, or verdict gate artifacts are missing or stale
- nightly stage6 keep-green evidence is being treated as a substitute for the separate verdict gate
- wetlab selected-all-atom gating is still open, claim/equivalence evidence is missing or fail-closed, or the claim-attached review chain is not source-consistent
- the review packet -> `current_results_index` -> `partnering_stack` -> final/dashboard -> burndown -> verdict chain is not source-consistent, or any of those surfaces differ on the metric source or metric value; keep the discrepancy as a canonical-source freshness regression and do not treat any surface as pass evidence while the strict threshold is missed or another wetlab hard blocker remains open
- `runs/local_delivery_verdict_gate_current.json` still reports `summary.delivery_ready=false`
- the commercialization queue still reports blockers
- the current `accuracy_gate` regresses from `pass=true`
- `summary.delivery_ready=false`
- `manifest.json` / `manifest.md` record `verdict_gate_fingerprint_check.status` is not `pass` or `ok=false`
- `runs/local_delivery_verdict_gate_current.json` source artifacts look stale or mismatched
- `python3 tools/validate_local_delivery_bundle.py --bundle-dir <bundle_dir>` does not report `summary.overall_ok=true` and `summary.delivery_ready_policy_ok=true`
- if `family_scorecards` are present, any included scorecard is blocked or has `summary.acceptance_overall_pass == false`
- the rescue attempt/fingerprint ledger (`attempt_id`, `attempt_sequence`, `input_fingerprint_sha256`, `input_fingerprints` / `input_fingerprint_ledger`, `attempt_dir`, `attempt_state_json`, `attempt_artifacts`, `current_artifact_is_pointer`) is missing, stale, or mismatched
- nightly stage6 is being counted as a blocker even though it is keep-green
- wetlab selected-all-atom gating is still open
- the preflight or requirements lock is not green
- rerun reproducibility is not yet locked down
- the bundle depends on ambiguous or overstated artifacts

## Do Not Say

- broad commercialization-ready
- transporter scope promotion
- scorecard-level baseline comparison or acceptance-profile wording used as if it were a verdict
- score-uplift wording when the scorecard is tie-heavy or the frozen packet identity changed
- delivery-ready wording when required-family coverage is incomplete
- delivery-ready wording when the requirements lock is incomplete
- delivery-ready wording when optional/API/train/deploy dependencies are being counted as required local-delivery coverage
- unattended external decision-making ready
- hosted platform ready
- prospective wet-lab hit-discovery claims
- any sentence that widens scope beyond the attached bundle
- delivery-ready wording when any bundled family scorecard reports `summary.scorecard_level_status` other than `pass` or `summary.acceptance_overall_pass == false`
- delivery-ready wording when `summary.delivery_ready=false`
- delivery-ready wording when claim/equivalence policy evidence is missing, fail-closed, is a rescue-state JSON, or would need archived/smoke auto-adoption instead of a current/source-consistent run
- delivery-ready wording when a stage3 smoke or downstream execute artifact is being treated as a substitute for the canonical top-level nightly summary, or when keep-green nightly stage6 evidence is being used to bypass the separate verdict gate
- delivery-ready wording when the verdict gate reports `summary.delivery_ready=false`
- delivery-ready wording when the commercialization queue still reports blockers
- delivery-ready wording when the current `accuracy_gate` regresses from `pass=true`
- fake-pass, threshold-relax, or output-massage the blocker evidence into a green verdict
- delivery-ready wording when the preflight accuracy gate CSV is being treated as the external accuracy CSV, or when the real external accuracy CSV is missing `target,avg_rmsd_aligned,avg_rmsd_vs_native_aligned`
- delivery-ready wording when stronger-physics pre-execution is being implied as a substitute for claim/equivalence closure
- delivery-ready wording when the final bundle validator reports `summary.overall_ok=false` or `summary.delivery_ready_policy_ok=false`
- delivery-ready wording when `verdict_gate_fingerprint_check.status` is not `pass` or `ok=false`
- delivery-ready wording when source artifact fingerprints do not match the current bundle/work record
- delivery-ready wording when the current preflight, requirements lock, environment manifest, or verdict gate artifacts are missing or stale
- delivery-ready wording when claim/equivalence inputs are being used before wetlab selected-allatom is green or when placeholder data is being treated as final readiness evidence

## Where To Use The Wording

- In `manifest.json`, store one verdict sentence exactly.
- In `manifest.md`, repeat the same sentence and add a short reason line if needed, including the `verdict_gate_fingerprint_check` result when the bundle is blocked/internal-review.
- In outbound notes, never upgrade the verdict beyond the exact sentence chosen here.
- If `summary.delivery_ready=false`, use the internal-review sentence only.
