# Local Delivery Bundle Schema

## Purpose

This schema standardizes the bundle handed over for a paid local delivery. The bundle is the auditable deliverable: it must be self-contained, reproducible, and scoped to the exact family, config, and artifact set used in the run.

The bundle documents the existing in-repo engine rather than replacing it. It should carry engine provenance, dependency freeze, environment baseline, queue/report, configs, and results for the exact engine surface used in the run.

This document follows the claim limits in `docs/local_delivery_claim_policy.md` and the operating sequence in `docs/local_delivery_runbook.md`.

For the P0 start gate, see `docs/local_delivery_p0_gate.md`.

The canonical builder for this layout is `python3 tools/build_local_delivery_bundle.py`.
The canonical validator for the assembled bundle is `python3 tools/validate_local_delivery_bundle.py --bundle-dir <bundle_dir>`, and it is the final local verification step before any delivery-ready wording is used.
Optional family scorecard JSONs supplied with `--family-scorecard-json` may also be bundled as attached evidence. When present, they are indexed in `manifest.json.family_scorecards` with source path, bundle path, checksum, and summary status. This bookkeeping is additive and does not change the existing row identity, `identity_columns`, `--packet-id`, or hard-fail policies. The preflight is a non-dry-run evidence refresh; it captures source/artifact integrity and runtime state, but it is not the delivery-ready verdict.

## Expected Engine Provenance Attachments

| Path | Status | Notes |
| --- | --- | --- |
| `runs/local_delivery_engine_provenance_current.json` | expected | Current provenance record for the in-repo engine surfaces used in the delivery. |
| `runs/local_delivery_engine_provenance_current.md` | expected | Human-readable companion to the current provenance record. |
| `environment/engine_provenance.json` | expected | Bundle copy of the same provenance record. |
| `environment/engine_provenance.md` | expected | Human-readable bundle copy. |

## Scope Rules

- The bundle is for local-run delivery only.
- Initial commercial scope stays restricted to `kinase`, `ion_channel`, and `gpcr`.
- If transporter or any other blocked family appears in the run, it must be labeled `review-only`, `staged`, or `not yet claim-safe`.
- The bundle may still be assembled as a blocked bundle for internal review when the requirements lock is incomplete, the verdict gate reports `summary.delivery_ready=false`, or the fingerprint check mismatches, including when the current `current_results_index` or `partnering_stack` source artifacts are absent, stale, or mismatched, but it is not delivery-ready.
- The bundle may support a guarded delivery verdict only when the requirements lock is complete, the top-level nightly gate is pass, wetlab selected-allatom is pass, `runs/local_delivery_verdict_gate_current.json` reports `summary.delivery_ready=true`, the final bundle validator reports `summary.overall_ok=true` and `summary.delivery_ready_policy_ok=true`, and the manifest records `verdict_gate_fingerprint_check.status=pass`, `ok=true`, `comparison_performed=true`, and `mismatch_count=0` after a persisted-vs-fresh fingerprint comparison across the full source_artifacts label set, including `current_results_index` and `partnering_stack`. The commercialization queue is downstream of wetlab selected-allatom closure and should not be treated as independently clear before that gate closes.
- `local_delivery_verdict_gate` must only summarize the current nightly, wetlab, queue, and status artifacts. It is not a scientific proof, a new engine run, or a replacement for the underlying gate files.
- The gate is the audit wrapper over the existing artifacts; the bundle records the persisted-vs-fresh fingerprint check and the package checksum list. It stays separate from the preflight evidence refresh.
- If the bundle is blocked or internal-review only, the validator may record a fingerprint mismatch, but it must not promote the bundle to delivery-ready.
- If `family_scorecards` are included, blocked scorecards may remain as internal-review diagnostics, but delivery-ready wording requires every included scorecard to report `summary.scorecard_level_status="pass"` and `summary.acceptance_overall_pass != false`.
- If `family_scorecards` are absent, do not infer a new delivery-ready blocker from this schema; it only means score-uplift and architecture-accuracy claims still need scorecard evidence under the claim policy.
- Treat `runs/nightly_stage6_top_level_reentry_packet_current.md` together with `runs/nightly_stage6_top_level_reentry_profile_current.json` as the strict canonical reentry handoff. The packet/profile pair preserves `smoke_then_full`, `KRAS_G12D,EGFR_KINASE,HIV1_PROTEASE`, `require_ood_eval=true`, and the unchanged `2.500` gate, and it remains supporting-only keep-green evidence rather than a blocker. If `runs/wetlab_selected_allatom_repair_packet_current.md` exists, treat it as the next execution reference for the wetlab rerun only; it does not replace a pass or delivery-ready verdict.

Current status snapshot: the current `accuracy_gate` is `pass=true` with failed metrics `0`, and the Morton presort neighbor/self-pair parity smoke records `total_pair_outliers=0`; the requirements/environment lock is green for the local-delivery required set (`installed=13/13`, `missing=0`, `loose_sources=0`, `requirements_lock_complete=true`, `environment_lock_complete=true`, `optional_missing_count=7`). A is closed, the preflight evidence is green, and B has a keep-green canonical top-level nightly summary. `runs/nightly_stage6_top_level_reentry_packet_current.md` together with `runs/nightly_stage6_top_level_reentry_profile_current.json` remains the strict handoff for the next canonical rerun if needed. C is green: wetlab selected-allatom reports `mean_min_distance_A=2.120 <= 2.500`, `binding_energy_proxy=-0.146 <= -0.050`, no hard/semi-hard blockers, and the review packet -> `current_results_index` -> `partnering_stack` -> final/dashboard -> burndown -> verdict chain is source-consistent. The current verdict gate reports `summary.delivery_ready=true`, `p0_blocker_count=0`, `hard_blocker_count=0`, and `commercialization_queue_clear=true` for the restricted `kinase,gpcr,ion_channel` local-delivery scope.

The verdict gate JSON should also expose `source_artifacts` entries with `label`, `path`, `present`, `required`, `status`, `sha256`, `size_bytes`, `mtime_ns`, `mtime_epoch`, `mtime_local`, `generated_at`, `json_valid`, and `parse_error` for every source artifact it read. For this contract, the `source_artifacts` label set includes the existing gate inputs plus `current_results_index` and `partnering_stack`; if either of those added artifacts is absent, stale, or mismatched, the bundle stays blocked/internal-review only.
The bundle validator should confirm `checksums.sha256`, `manifest.json`, `manifest.md`, the required files, and `verdict_gate_fingerprint_check.status=pass`, `ok=true`, `comparison_performed=true`, and `mismatch_count=0` before delivery-ready wording is used. The fingerprint comparison must cover the full `source_artifacts` label set, including `current_results_index` and `partnering_stack`. `checksums.sha256` excludes itself and the validator's own `validation.json` / `validation.md` outputs, but every other bundle file must be listed exactly once and match its recorded SHA256.

## Required Top-Level Contents

| Path | Required | Notes |
| --- | --- | --- |
| `manifest.json` | yes | Machine-readable bundle index and verdict record. |
| `manifest.md` | yes | Human-readable summary of the same bundle. |
| `checksums.sha256` | yes | SHA256 checksum list for every file in the bundle. |
| `commercialization_status_report.md` | yes | Repo-root commercialization summary, copied into the bundle. |
| `runs/local_delivery_preflight_current.json` | yes | Final preflight summary after the run is refreshed. |
| `runs/local_delivery_preflight_current.md` | yes | Human-readable preflight record. |
| `runs/local_ci_tests_summary.json` | yes | Local CI smoke summary produced by the preflight wrapper. |
| `runs/local_engine_commercialization_queue_current.json` | yes | Current delivery queue record. |
| `runs/local_engine_commercialization_queue_current.csv` | recommended | Tabular queue export for review and diffing. |
| `runs/local_engine_commercialization_queue_current.md` | yes | Human-readable queue record. |
| `runs/local_delivery_verdict_gate_current.json` | yes | Conservative final delivery-readiness gate over the current P0 artifacts; source artifacts should be fingerprinted with `path`, `present`, `required`, `status`, `sha256`, `size_bytes`, `mtime_ns`, `mtime_epoch`, `mtime_local`, `generated_at`, `json_valid`, and `parse_error`. |
| `runs/local_delivery_verdict_gate_current.md` | yes | Human-readable final gate summary. |
| `environment/environment_manifest.json` | yes | Machine/runtime snapshot for the delivery host, normally copied from `runs/local_delivery_environment_manifest_current.json`. |
| `environment/environment_manifest.md` | yes | Human-readable environment note, normally copied from `runs/local_delivery_environment_manifest_current.md`. |
| `environment/requirements_lock.json` | yes | Machine-readable dependency freeze, copied from `runs/local_delivery_requirements_lock_current.json`. |
| `environment/requirements_lock.md` | yes | Human-readable dependency-freeze summary, copied from `runs/local_delivery_requirements_lock_current.md`. |
| `environment/requirements_lock.txt` | yes | Deterministic package install input for local reruns, copied from `runs/local_delivery_requirements_lock_current.txt`. |
| `environment/engine_provenance.json` | yes | Machine-readable proof that local delivery reuses existing in-repo engine surfaces. |
| `environment/engine_provenance.md` | yes | Human-readable existing-engine provenance note. |
| `config/` | yes | Exact run config or profile used for the delivered result. |
| `artifacts/` | yes | Delivered result files, primary metrics, and any reviewer-facing summaries. |
| `artifacts/family_scorecards/` | optional | Attached family scorecard evidence copied from `--family-scorecard-json` inputs and indexed in `manifest.json.family_scorecards`. |
| `bundle.zip` | recommended | Optional single-file archive of the same bundle layout. |

Preserve the canonical filenames when copying artifacts into the bundle. Do not rename outputs just to fit the archive.

## Manifest Contract

`manifest.json` should carry, at minimum, these fields:

- `bundle_tag`
- `created_at_local`
- `source_repo_commit`
- `delivery_scope`
- `claim_scope`
- `request_summary`
- `preflight`
- `queue`
- `status_report`
- `local_delivery_verdict_gate`
- `verdict_gate_fingerprint_check`
- `environment`
- `engine_provenance`
- `artifact_index`
- `family_scorecards`
- `known_exclusions`
- `rerun_command`
- `verdict`

The `delivery_scope` and `claim_scope` fields should state the exact family scope and must not widen beyond the allowed initial scope. The `verdict` field should use the same wording rules as the claim policy.
The `engine_provenance` field should point to the current provenance record for the existing in-repo engine surfaces and, when bundled, the matching `environment/engine_provenance.*` copy.
The `verdict_gate_fingerprint_check` object should include `checked`, `ok`, `status`, `reason`, `comparison_performed`, `required_for_delivery_ready_verdict`, `matched_count`, `compared_label_count`, `mismatch_count`, `persisted_label_count`, `fresh_label_count`, and `mismatches`. It must compare persisted-vs-fresh fingerprints across the full `source_artifacts` label set, including `current_results_index` and `partnering_stack`; if either artifact is absent, stale, or mismatched, keep the bundle blocked/internal-review only. Delivery-ready wording requires `status=pass`, `ok=true`, `comparison_performed=true`, and `mismatch_count=0`.
The `family_scorecards` field, when present, should be a list of objects that keep the original scorecard status and record `source_path`, `bundle_path`, `sha256`, and a `summary` object with at least `scorecard_level_status` and `acceptance_overall_pass`.
Delivery-ready wording requires every included scorecard to report `summary.scorecard_level_status="pass"` and `summary.acceptance_overall_pass != false`. Blocked scorecards may remain in blocked/internal-review bundles as diagnostics, but their manifest entries must stay blocked and they cannot justify delivery-ready wording.
If `family_scorecards` is absent, do not infer a new delivery-ready blocker from this schema; score-uplift and architecture-accuracy claims still need scorecard evidence under the claim policy.

For copy-ready field content, use:

- `docs/local_delivery_manifest_template.md`
- `docs/local_delivery_verdict_template.md`

## Checklist

Treat a bundle as complete only when all of the following are true:

1. The request summary names the exact target, scope, and delivery date.
2. The final preflight and requirements lock are green and point to fresh queue/report artifacts.
3. The commercialization queue, status report, and local delivery verdict gate were rebuilt after the final run.
4. The final bundle validator reports `summary.overall_ok=true` and `summary.delivery_ready_policy_ok=true`, and it confirms `checksums.sha256`, `manifest.json`, `manifest.md`, the required files, and `verdict_gate_fingerprint_check.status=pass`, `ok=true`, `comparison_performed=true`, and `mismatch_count=0`. If `family_scorecards` are present, each included scorecard also reports `summary.scorecard_level_status="pass"` and `summary.acceptance_overall_pass != false` for delivery-ready wording. If not, or if any included scorecard is blocked, the bundle may still exist as a blocked bundle for internal review, but the verdict must stay negative/internal-review and the manifest must preserve the blocked scorecard status.
5. The verdict gate reports `summary.delivery_ready=true` and its `source_artifacts` fingerprints match the current bundle/work record, including `current_results_index` and `partnering_stack`, before any delivery-ready wording is used.
6. The engine provenance record, environment manifest, and requirements lock match the machine that produced the results.
7. The exact config/profile used for the run is copied into the bundle.
8. The result artifacts and their primary thresholds or metrics are present.
9. Known exclusions, caveats, and blocked families are stated explicitly.
10. The checksum file covers the entire bundle except `checksums.sha256` itself and the validator's own `validation.json` / `validation.md` outputs.
11. The verdict language is scoped and does not imply general commercialization readiness.

`python3 tools/build_local_delivery_bundle.py` copies the current requirements lock and engine provenance files into `environment/` and indexes them in the bundle manifest and checksum list.

If the requirements lock is incomplete, the verdict gate reports `summary.delivery_ready=false`, or wetlab selected-all-atom gating regresses, the bundle can still exist as a blocked bundle for internal review, but it is not delivery-ready. Nightly stage6 is keep-green and does not by itself block delivery-ready wording.
The final bundle validator can still report a fingerprint mismatch for that blocked bundle, but it must not upgrade the bundle to delivery-ready.

## Minimal Verdict Formats

- `Delivery-ready for guarded local validation on the scoped kinase / ion-channel / GPCR workflow documented in this bundle.`
- Internal-review only; not delivery-ready for commercial handoff because the current verdict gate, source-fingerprint check, or final bundle validator failed. Record the exact failed check and keep the scope restricted until the gate and validator return to green.
- `Delivery-ready only for the attached restricted scope; not a general commercialization verdict for all families.`

For outbound wording, defer to `docs/local_delivery_claim_policy.md`.
