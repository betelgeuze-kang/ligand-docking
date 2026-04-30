# Local Delivery Claim Policy

## Delivery Model

This policy applies to local-run delivery only.

- work is executed on a controlled local machine
- outputs are delivered as result bundles, not as a hosted service
- verdicts are scoped to the exact family, config, and artifact set used in the run

## Allowed Initial Scope

- `kinase`
- `ion_channel`
- `gpcr`

These are the only families that should be described as delivery-ready in the initial local-delivery phase, and only when the current gating artifacts are green. The current P0 delivery claim stays limited to this scope. The post-P0 expansion queue for PDE translation quality, transporter AQP1/GLUT1 evidence closure, CA2/PXR packet closure, and IDP broader-promotion guardrails is separate and does not broaden delivery-ready wording.

## Allowed Claims

- `The current local-delivery workflow is suitable for guarded validation delivery on kinase, ion-channel, and GPCR tasks only.`
- `The current delivery verdict is limited to the restricted kinase, ion_channel, and gpcr scope.`
- `The current delivery verdict is based on the exact artifacts in the attached bundle.`
- `Nightly reliability and wetlab selected-all-atom gates are treated as hard blockers for delivery readiness.`
- `The delivery result is valid only for the scope, profile, and machine assumptions documented in the bundle.`
- `Transporter work remains staged or review-only until direct evidence closure is complete.`
- `CA2/PXR packet work remains partial-authoritative or review-only until the packet lanes close.`
- `IDP broader-promotion work remains blocked until the bounded lane and guardrails are resolved.`
- `Scorecard-level baseline comparison and acceptance-profile results are not delivery-ready verdicts by themselves.`
- Delivery-ready wording is allowed only when `python3 tools/validate_local_delivery_bundle.py --bundle-dir <bundle_dir>` reports `summary.overall_ok=true` and `summary.delivery_ready_policy_ok=true`, `runs/local_delivery_verdict_gate_current.json` reports `summary.delivery_ready=true`, the gate's `source_artifacts` fingerprints match the current bundle/work record, and `manifest.json` / `manifest.md` record `verdict_gate_fingerprint_check.status=pass`, `ok=true`, `comparison_performed=true`, and `mismatch_count=0`. If `family_scorecards` are bundled, every included scorecard must also report `summary.scorecard_level_status="pass"` and `summary.acceptance_overall_pass != false`. Any intentional ROCm `TORCH_BLAS_PREFER_HIPBLASLT` override must also be visible in the environment manifest and the verdict text before the wording can be called delivery-ready.
- Bundled scorecards are additive evidence; they do not change the row identity, `identity_columns`, `--packet-id`, or hard-fail rules already documented in this policy.

## Score And Architecture-Accuracy Claims

- Any claim that a family's score, ranking, or architecture accuracy improved must cite the relevant held-out family scorecard.
- The same frozen input, baseline, and held-out family packet must be used for the scorecard, the baseline comparison, and the acceptance profile.
- The absence of bundled family scorecards does not by itself add a delivery-ready blocker under this policy; it only means score-uplift and architecture-accuracy claims still need scorecard evidence.
- If no `--identity-col` is supplied, the builder stays in family/label-only mode and does not run a separate target/ligand completeness check, identity-columns completeness check, or duplicate explicit-identity check.
- Keep input `family` values nonblank, and do not use `overall` as an input family because it is reserved for aggregate scorecard metrics.
- Keep the scorecard blocked if any required family is missing from the frozen packet. For the scoped local-delivery lane, that includes `gpcr`, `ion_channel`, and `kinase` whenever they are required by the claim packet.
- Use `predictions_csv_sha256` to pin the exact frozen CSV bytes and `row_identity_sha256` to pin the ordered row-identity payload. A changed `row_identity_sha256` means the packet itself drifted, not just the score.
- When identity columns are explicitly supplied, blank target or ligand identity values are a frozen-packet drift risk and the scorecard builder rejects the packet before writing claim evidence.
- If explicit identity columns collapse two rows onto the same canonical row identity (`family`, `label`, ordered `identity_columns`), emit a duplicate-row-identity warning, treat the scorecard as blocked, and deduplicate the packet or rewrite the claim packet before delivery.
- If the baseline scorecard's `summary.identity_columns` is missing or does not match the candidate packet's ordered `identity_columns` list, treat the scorecard as scorecard-level blocked and do not use it for score-uplift, architecture-accuracy, or delivery-ready wording.
- Record `row_identity_schema_version` with the row-identity metadata. It fixes the meaning of `row_identity_sha256`; candidate and baseline schema-version mismatches are scorecard-level blocked.
- If a baseline scorecard predates `row_identity_schema_version`, treat it as legacy, regenerate it if you need delivery-ready evidence, and do not use the legacy artifact itself as delivery-ready proof.
- If the packet carries `--packet-id`, treat it as a human alias only; the authoritative contract is `predictions_csv_sha256`, `row_identity_sha256`, `row_identity_schema_version`, and the ordered `identity_columns` list.
- A baseline `summary.identity_columns` mismatch or missing field is scorecard-level blocked; `row_identity_schema_version`, `top_k`, `lower_better`, and `row_identity_sha256` mismatches keep score-uplift language blocked and prevent delivery-ready wording.
- If `score_unique_ratio` is low or `score_tie_ratio` / `score_mode_ratio` is high, treat top-k/AP as coarse and lower the claim language instead of calling it strong uplift.
- Baseline comparison and acceptance profile are scorecard-level artifacts only; they do not make the bundle delivery-ready and they do not override verdict gates.
- Any delivery-ready wording for that claim is allowed only when the same family packet also passes hard-decoy stability, calibration, and geometry/contact gate checks.
- Use family-specific axes only:
  - GPCR orthosteric/contact
  - ion_channel membrane/charge/geometry
  - kinase hinge/ATP-site
- If the family scorecard is missing or any of the four checks is mixed, keep the claim `blocked`, `internal-review`, `staged`, or `review-only`.
- Do not widen a family scorecard claim into broad platform, cross-family, or transporter scope.
- This is an additional claim rule, not a replacement for the bundle validator, verdict gate, nightly gate, or wetlab gate.

## Allowed Internal Claims

- `The repo contains stronger evidence for kinase, ion_channel, and gpcr than for transporter.`
- `The repo contains separate post-P0 planning queues for PDE translation quality, transporter AQP1/GLUT1 closure, CA2/PXR packet closure, and IDP broader-promotion boundaries.`
- `Viewer and refresh reproducibility can remain keep-green guardrails while nightly and wetlab are the main active blockers.`
- `A family may remain commercially restricted even if related staging surfaces or reviewer packets already exist.`
- `A local-delivery-ready verdict is narrower than a general platform commercialization claim.`
- `A local_delivery_verdict_gate is a conservative wrapper over the current nightly, wetlab, queue, and status artifacts; it is not a scientific proof or a new engine run.`
- `Family scorecard baseline is required before any score-uplift or architecture-accuracy claim.`
- On ROCm, the hipBLASLt unsupported-architecture warning is a backend fallback, not an accuracy failure; routine local-delivery runs should pin `TORCH_BLAS_PREFER_HIPBLASLT=0`, and the environment manifest must record the actual exported value in the env vars / accelerator env snapshot.
- If a supported-GPU hipBLASLt test intentionally overrides that setting, record the override value there and in the verdict text; if the value or verdict echo is missing from the captured manifest, rerun the capture or leave a manifest note because that is a reproducibility/log-cleanliness issue, not an accuracy failure.
- A bundled family scorecard may remain blocked for internal review as diagnostic evidence, but its blocked status must stay recorded and it cannot authorize delivery-ready wording.
- If `summary.delivery_ready=false`, or the gate's source fingerprints look stale or mismatched, or the final bundle validator reports `summary.overall_ok=false` or `summary.delivery_ready_policy_ok=false`, the bundle may still be shared as a blocked bundle for internal review, but not as delivery-ready. In that case, the manifest must record the mismatch reason.

## Disallowed Claims

- `The platform is broadly commercial-ready across all supported molecular families.`
- `Transporter delivery is commercially ready today.`
- `The current delivery verdict covers transporter, CA2/PXR, or IDP broader-promotion readiness.`
- `The current result bundle proves broad platform commercialization readiness.`
- `The current result bundle proves transporter delivery readiness before AQP1/GLUT1 evidence closure.`
- `The current result bundle proves CA2 or PXR broader readiness before packet closure.`
- `The current result bundle proves IDP broader promotion readiness before the bounded lane guardrails close.`
- `The stack is suitable for unattended automatic external decision-making without guardrails.`
- `The repo is production-ready as a hosted multi-tenant service.`
- `The current evidence supports prospective wet-lab hit-discovery claims.`
- `The current result bundle proves general commercial readiness beyond the attached scope.`
- `A family scorecard result, baseline comparison, or acceptance profile proves delivery readiness by itself.`
- `A family scorecard claim is used to justify broad platform, cross-family, or transporter scope expansion.`
- `A family scorecard claim is treated as delivery-ready when required-family coverage is incomplete, the packet identity hash changes, or the scorecard is tie-heavy.`
- Any delivery-ready wording when a bundled family scorecard reports `summary.scorecard_level_status` other than `pass` or `summary.acceptance_overall_pass == false`.
- Any delivery-ready wording while `summary.delivery_ready=false`.
- Any delivery-ready wording while the final bundle validator reports `summary.overall_ok=false` or `summary.delivery_ready_policy_ok=false`.

## Hard Delivery Blockers

Do not issue a delivery-ready verdict if any of the following are true:

- `runs/nightly_gate_burndown_packet_current.json` or `runs/nightly_gate_burndown_packet_current.md` still report a failed nightly gate
- `runs/wetlab_selected_allatom_gate_burndown_packet_current.json` or `runs/wetlab_selected_allatom_gate_burndown_packet_current.md` still report a failed selected all-atom gate
- `runs/local_engine_commercialization_queue_current.json` or `runs/local_engine_commercialization_queue_current.md` still show nightly reliability or wetlab selected-allatom as open blockers
- `python3 tools/validate_local_delivery_bundle.py --bundle-dir <bundle_dir>` does not report `summary.overall_ok=true` and `summary.delivery_ready_policy_ok=true`
- `runs/local_delivery_verdict_gate_current.json` does not report `summary.delivery_ready=true`
- `runs/local_delivery_verdict_gate_current.json` source artifact fingerprints do not match the current bundle/work record or look stale
- `manifest.json` / `manifest.md` do not record `verdict_gate_fingerprint_check.status=pass`, `ok=true`, `comparison_performed=true`, and `mismatch_count=0`
- `runs/local_delivery_environment_manifest_current.json` / `runs/local_delivery_environment_manifest_current.md` do not record the actual `TORCH_BLAS_PREFER_HIPBLASLT` export, or an intentional override is not echoed in the verdict text
- any bundled family scorecard reports `summary.scorecard_level_status` other than `pass` or `summary.acceptance_overall_pass == false`
- commercialization queue logic is known to overstate execute success or wetlab readiness under partial artifacts
- the delivery preflight or local CI smoke is red
- the baseline scorecard's `summary.identity_columns` is missing or does not match the candidate packet's ordered `identity_columns` list
- the explicit identity packet still carries a duplicate-row-identity warning and has not been deduplicated or rewritten

## Required Artifacts For A Delivery-Ready Verdict

- `commercialization_status_report.md`
- `runs/local_engine_commercialization_queue_current.json`
- `runs/local_engine_commercialization_queue_current.md`
- `runs/nightly_gate_burndown_packet_current.json`
- `runs/nightly_gate_burndown_packet_current.md`
- `runs/wetlab_execution_readiness_queue_current.json`
- `runs/wetlab_selected_allatom_gate_burndown_packet_current.json`
- `runs/wetlab_selected_allatom_gate_burndown_packet_current.md`
- `runs/local_delivery_verdict_gate_current.json`
- `runs/local_delivery_verdict_gate_current.md`
- the exact run config/profile used for the delivered result
- the delivered result files and summary metrics

## Restricted-Scope Rule

If transporter, CA2/PXR, or IDP broader-promotion remains evidence-blocked:

- those lanes must stay out of delivery-ready wording
- transporter outputs must be labeled `review-only`, `staged`, or `not yet claim-safe`
- CA2/PXR outputs may be labeled `partial-authoritative` or `review-only`
- IDP broader-promotion outputs must stay `blocked` or `review-only`
- the bundle must say that commercial scope is restricted to `kinase`, `ion_channel`, and `gpcr`
- broad platform wording and general commercialization wording stay disallowed

## Verdict Language

### Allowed Short Verdict

- `Delivery-ready for guarded local validation on the scoped kinase / ion-channel / GPCR workflow documented in this bundle.`

Use only when `python3 tools/validate_local_delivery_bundle.py --bundle-dir <bundle_dir>` reports `summary.overall_ok=true` and `summary.delivery_ready_policy_ok=true`, `runs/local_delivery_verdict_gate_current.json` reports `summary.delivery_ready=true`, the source fingerprints match the current bundle/work record, and `manifest.json` / `manifest.md` record `verdict_gate_fingerprint_check.status=pass`, `ok=true`, `comparison_performed=true`, and `mismatch_count=0`.

### Allowed Restricted Verdict

- `Delivery-ready only for the attached restricted scope; not a general commercialization verdict for all families.`

Use only when `python3 tools/validate_local_delivery_bundle.py --bundle-dir <bundle_dir>` reports `summary.overall_ok=true` and `summary.delivery_ready_policy_ok=true`, `runs/local_delivery_verdict_gate_current.json` reports `summary.delivery_ready=true`, the source fingerprints match the current bundle/work record, `manifest.json` / `manifest.md` record `verdict_gate_fingerprint_check.status=pass`, `ok=true`, `comparison_performed=true`, and `mismatch_count=0`, and you want the scope boundary restated.

### Required Internal-Review Verdict

- `Internal-review only; not delivery-ready for commercial handoff because current hard blockers remain open and/or source artifact fingerprints are stale or mismatched.`

Use this when:

- `summary.delivery_ready=false`
- `manifest.json` / `manifest.md` record `verdict_gate_fingerprint_check.status` is not `pass` or `ok=false`
- `runs/local_delivery_verdict_gate_current.json` source artifact fingerprints do not match the current bundle/work record or look stale
- `python3 tools/validate_local_delivery_bundle.py --bundle-dir <bundle_dir>` does not report `summary.overall_ok=true` and `summary.delivery_ready_policy_ok=true`
- nightly reliability is still open
- wetlab selected-all-atom gating is still open
- the preflight is red
- rerun reproducibility is not yet locked down
- the bundle depends on ambiguous or overstated artifacts
