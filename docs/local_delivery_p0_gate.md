# Local Delivery P0 Gate

P0 starts here: the current local-delivery gate is green for the restricted `kinase,gpcr,ion_channel` scope. The latest `runs/local_delivery_verdict_gate_current.json` reports `summary.delivery_ready=true`, `p0_blocker_count=0`, `hard_blocker_count=0`, `commercialization_queue_clear=true`, and all required source artifacts are fingerprinted. The preflight, requirements lock, environment manifest, canonical top-level nightly reentry, wetlab selected-allatom review chain, wetlab execution readiness, and commercialization queue are aligned. Use blocked/internal-review wording only if a fresh validation regresses. The current delivery claim stays narrow and does not extend to transporter, CA2/PXR, or IDP broader-promotion wording.

Relative to commercial tools, the current stack is roughly 70-75% of a local-delivery analysis service and 40-50% of a full commercial platform. The next improvement order is family scorecards (GPCR/ion channel/kinase), CI/regression, broad benchmark, UX/report packaging, and the separate post-P0 commercial expansion queue in [`docs/post_p0_commercial_expansion_queue.md`](post_p0_commercial_expansion_queue.md). Do not widen the current verdict into transporter coverage, broad platform readiness, IDP broader promotion, or unattended decision-making.

A. Current preflight, requirements lock, environment manifest, and verdict-gate artifacts exist, are fresh, and match the current bundle/work record; the current A snapshot has `accuracy_gate pass=true`, `installed=13/13`, `missing=0`, `loose_sources=0`, `optional_missing_count=7`, `requirements_lock_complete=true`, and `environment_lock_complete=true`. Optional/API/train/deploy dependencies are recorded separately as optional/deferred evidence and do not make or break A.
B. The canonical top-level nightly reentry is green. Downstream execute-pass artifacts remain supporting-only evidence and do not override the top-level gate. The strict canonical reentry handoff is the packet/profile pair, and it remains supporting-only keep-green evidence for future reruns.
C. The wetlab selected all-atom geometry, binding, and claim-attached review chain are green: the latest review packet, `current_results_index`, `partnering_stack`, final campaign/dashboard, regenerated burndown, and verdict report selected `mean_min_distance_A=2.120 <= 2.500`, `binding_energy_proxy=-0.146 <= -0.050`, `wetlab_selected_allatom_pass=true`, and no hard/semi-hard blockers. If `runs/wetlab_selected_allatom_repair_packet_current.md` exists, use it only as a future regression/retry reference, not as the current delivery verdict.
D. The preflight itself is a green non-dry-run evidence refresh (`summary.overall_ok=true`, `verdict_gate_required_ok=true`), but the delivery-ready verdict still comes from `runs/local_delivery_verdict_gate_current.json` plus the final bundle validator.
E. The commercialization queue is clear for the current restricted local-delivery scope. The transporter negative-evidence lane remains parked outside this verdict scope, and the post-P0 queue stays separate from the current delivery claim.

If any part of A/B/C/D/E is missing, stale, or still blocked, stop at blocked/internal-review and create evidence from the current artifacts first. The verdict gate is an audit wrapper over the existing artifacts; it records the persisted-vs-fresh fingerprint check and the package checksum list. The source-consistency check spans review packet -> `current_results_index` -> `partnering_stack` -> final/dashboard -> burndown -> verdict, and any mismatch anywhere is a canonical freshness regression. The final local bundle validator sits after bundle assembly and before any delivery-ready wording is used.

Use these artifacts as the operator-facing source of truth:

- `runs/local_delivery_preflight_current.json`
- `runs/local_delivery_preflight_current.md`
- `runs/local_delivery_requirements_lock_current.json`
- `runs/local_delivery_requirements_lock_current.md`
- `runs/local_delivery_requirements_lock_current.txt`
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
- `runs/local_delivery_verdict_gate_current.json`
- `runs/local_delivery_verdict_gate_current.md`

Practical rule:

- if A is missing, stale, or still incomplete because required inputs are missing, loose/source, or absent, do not write delivery-ready wording; produce blocked/internal-review evidence from the current preflight, requirements lock, environment manifest, and verdict gate outputs first
- do not write delivery-ready wording until `runs/local_delivery_verdict_gate_current.json` reports `summary.delivery_ready=true`
- if the accuracy artifact regresses from `pass=true`, reopen the P0-A burndown and rerun the Morton presort/self-pair smoke before drafting any verdict
- do not fake-pass, perform threshold relaxation, or manipulate results to make the blocker look green; the verdict must reflect the recorded local outputs exactly
- optional/API/train/deploy dependencies are not a substitute for the required local-delivery lock; record them as optional/deferred evidence instead of counting them toward a green A
- if B is missing, stale, or the nightly stage6 summary regresses from keep-green, keep the bundle blocked/internal-review; do not treat downstream execute or stage3 smoke as a substitute for the verdict path
- if C regresses, or `mean_min_distance_A > 2.500`, or the binding proxy is too weak, or claim/equivalence evidence becomes missing/fail-closed, keep the bundle blocked/internal-review and rebuild the claim-attached review chain before reusing delivery-ready wording
- if the current strict/representative claim policy artifact becomes missing, fail-closed, or source-inconsistent, keep the bundle blocked/internal-review; do not auto-adopt archived/smoke strict summaries
- if the rescue summary reports a top-k shortfall, including `top_k_effective=4` of requested `8` in the current attempt, or any `rescue_review_band_mismatch_count > 0`, keep the bundle blocked/internal-review; record the attempt as such, rebuild the lane from the same post-slice review surface/score source until `rescue_review_band_mismatch_count=0`, and rerun rescue before using any downstream refresh as delivery-ready evidence; the candidate JSON is ranking seed/fallback only, not band authority
- if review packet -> `current_results_index` -> `partnering_stack` -> final/dashboard -> burndown -> verdict disagree on the metric source or metric value, treat that as a canonical-source freshness regression; do not treat any surface as pass evidence while the strict threshold is missed or another wetlab hard blocker remains open
- if `current_results_index.summary.partnering_stack_artifact_complete` is not `true`, or `runs/wetlab_partnering_stack_current.json` / `runs/wetlab_partnering_stack_current.md` is placeholder/minimal (`summary.status="ok"` only) or missing `wetlab_partnering_stack_ready`, `artifact_completeness=full_partnering_stack`, the selected-allatom metric source-chain, selected-allatom gates, or freshness/source provenance, keep the bundle blocked/internal-review; record blocker `partnering_stack_placeholder_or_incomplete` and do not count the partnering stack as evidence
- if `rescue_attempt_validation` is not pass, or the refreshed verdict gate does not mirror the rescue validator's `rescue_attempt_validation_*` snapshot in its summary/source_artifacts, keep the bundle blocked/internal-review and do not trust the rescue attempt evidence; a pass only confirms evidence integrity and does not clear the wetlab hard gate or the queue
- claim/equivalence inputs count only when they are current, source-consistent, and reflected through review packet -> `current_results_index` -> `partnering_stack` -> final/dashboard -> burndown -> verdict
- if D or E is still blocked, keep the bundle blocked/internal-review even when the required local-delivery lock is green
- if either gate is blocked, the bundle can stay as a blocked bundle for internal review, but it is not delivery-ready
- `python3 tools/validate_local_delivery_bundle.py --bundle-dir <bundle_dir>` must report `summary.overall_ok=true` and `summary.delivery_ready_policy_ok=true` before any delivery-ready wording is used
- the validator must confirm `checksums.sha256`, `manifest.json` / `manifest.md`, required files, and `verdict_gate_fingerprint_check.status=pass`, `ok=true`, `comparison_performed=true`, and `mismatch_count=0`
- `runs/local_delivery_verdict_gate_current.json` must report `summary.delivery_ready=true` and its `source_artifacts` fingerprints must match the current bundle/work record before any delivery-ready wording is used
- `manifest.json` / `manifest.md` must record `verdict_gate_fingerprint_check.status=pass`, `ok=true`, `comparison_performed=true`, and `mismatch_count=0` before any delivery-ready wording is used
- if `source_artifacts` fingerprints are stale or mismatched, keep the verdict negative/internal-review even if the rest of the bundle is present
- if `verdict_gate_fingerprint_check.status` is not `pass` or `ok=false`, keep the bundle blocked/internal-review and record the mismatch reason in the manifest
- if the validator records a fingerprint mismatch for a blocked/internal-review bundle, keep it blocked/internal-review and do not promote it to delivery-ready
- the allowed initial claim scope is only `kinase`, `ion_channel`, and `gpcr`
- `transporter`, broad platform, general commercialization, and unattended decision-making stay disallowed

`local_delivery_verdict_gate` is the conservative wrapper over the artifacts above.
It only reads the existing outputs; it is not a scientific proof, not a new engine run, and not a substitute for the underlying files.

Operator shortcut:

1. Read the current preflight, environment manifest, nightly gate, wetlab gate, queue, and commercialization status report.
2. Run `python3 tools/validate_local_delivery_bundle.py --bundle-dir <bundle_dir>`.
3. Read `runs/local_delivery_verdict_gate_current.json`.
4. Proceed only when A, B, C, D, and E are all green and the verdict gate reports `summary.delivery_ready=true`; otherwise stop at a blocked/internal-review verdict.
