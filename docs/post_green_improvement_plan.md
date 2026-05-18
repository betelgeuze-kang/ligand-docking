# Post-Green Improvement Plan

요약: 기존 P0 green 기준선은 이력으로 보존하고, 2026-05-18 현재 제한 local delivery verdict와 local engine queue는 green으로 동기화되어 있다. post-goal 정확도 parity도 tracked scorecard 기준 green이므로, 다음 작업은 이 상태를 유지하면서 scorer deployment/router/platform claim을 별도 guardrail로 관리하는 것이다.

## Boundary

- Keep the committed historical green baseline for audit, but treat the current verdict artifact as source of truth.
- Present delivery-ready wording only for the restricted local scope while `runs/local_delivery_verdict_gate_current.json` reports `delivery_ready=true` and the queue/verdict mismatch remains false.
- This note is a post-green operating plan, not a scope expansion memo.

## Priority Order

1. Preserve the baseline and current source-of-truth state
   - Treat [`docs/local_delivery_p0_gate.md`](local_delivery_p0_gate.md) and [`docs/local_delivery_claim_policy.md`](local_delivery_claim_policy.md) as the claim boundary.
   - Current source of truth: `runs/local_delivery_verdict_gate_current.json` reports `verdict=delivery_ready`, `p0_blocker_count=0`, and queue/verdict mismatch is false.
   - Current readiness/gap accounting is also closed for the tracked local scope: `runs/commercialization_readiness_current.json` reports `tracked_readiness_accounting_closed=true`, and `runs/commercialization_gap_burndown_current.json` reports `tracked_gap_accounting_closed=true`, `blocked_count=0`, `raw_blocked_bucket_count=2`, `parked_or_review_only_blocked_count=2`.
2. Follow the post-P0 expansion queue
   - Read [`docs/post_p0_commercial_expansion_queue.md`](post_p0_commercial_expansion_queue.md) next.
   - Current local engine commercialization queue is clear: `runs/local_engine_commercialization_queue_current.json` reports `queue_clear=true`, `blocked_count=0`.
   - The active lane is keep-green monitoring plus scorer deployment separation: use `runs/accuracy_parity_scorecard_current.md`, `runs/gpcr_a1_accuracy_repair_queue_current.md`, and the nightly reliability artifacts referenced by the status report.
3. Keep P0 wording narrow
   - `AQP1` / `GLUT1`, `CA2` / `PXR`, and IDP broader promotion remain outside restricted P0 delivery wording even where accounting closure exists.
   - Do not restyle the current P0 delivery claim as transporter, broad platform, or IDP-broader readiness.
   - The tracked accuracy-parity scorecard is green, but do not restyle that as unrestricted platform deployment or unattended decision-making.
4. Scale-up guardrail
   - The tracked scale-up suite is green as of 2026-05-13: `commercialization_ready_suite_count=3/3`.
   - Pending milestones: none in `runs/ligand_scaleup_suite_status_current.json`.
   - The 1M package is quality claim-safe with `claim_safe_status=claim_safe_size_shift_speed_diagnostic`; keep throughput wording tied to equal-size speedpack A/B, and treat 1M speed as diagnostic scale evidence.
   - Do not widen the GPCR ranking evidence into scorer deployment, router promotion, or platform claims.
5. Latest closure evidence
   - PDE selected all-atom hard block is closed: `runs/wetlab_selected_allatom_gate_burndown_packet_current.json` reports `hard_block_count=0`.
   - PDE atomized parameterization/local minimization is closed: `runs/wetlab_tcruzi_pde_atomized_parameterization_minimization_packet_current.json` reports `parameterization_ready_count=7`, `protein_local_minimization_ready_count=7`.
   - OpenMM multi-target evidence is current: `runs/openmm_2bead_strict_multitarget_current_summary.json` covers 11 targets.
   - GPCR A1 independent repeat plus out-of-fold crossfit replay is green: `runs/gpcr_rank_rescue_crossfit_repeat_r1_evidence_packet_current.json` reports PR-AUC `0.8719`, PR CI-low `0.7612`, top20 `1.00`, and blockers `[]`.
   - Accuracy parity scorecard is green: `runs/accuracy_parity_scorecard_current.json` reports `status=green`, `pass_row_count=5`, `blocked_row_count=0`.

## Guardrails

- No threshold relaxation.
- No fake-pass.
- No transporter claim promotion, CA2/PXR claim promotion, or IDP broader-promotion claim.
- No unrestricted platform-deployment or automatic router/scorer-promotion claim from the tracked scorecard alone.
- No local delivery-ready wording outside the restricted local scope.
- No expensive lane before the active scorecard/repair queue says the rerun is eligible.
- Keep P0 evidence and new experiments in separate queues.

## Local Verification

```bash
rg -n "post_p0_commercial_expansion_queue|AQP1|GLUT1|CA2|PXR|IDP broader" docs/post_green_improvement_plan.md docs/post_p0_commercial_expansion_queue.md docs/local_delivery_p0_gate.md docs/local_delivery_claim_policy.md
rg -n "accuracy_parity|gpcr_a1|status=green|post_goal_accuracy_parity" commercialization_status_report.md runs/accuracy_parity_scorecard_current.md runs/gpcr_a1_accuracy_repair_queue_current.md
rg -n "local_delivery_ready|effective_delivery_ready|local_engine_queue_clear|local_delivery_verdict" commercialization_status_report.md
python3 - <<'PY'
import json
for path in [
    "runs/local_delivery_verdict_gate_current.json",
    "runs/local_engine_commercialization_queue_current.json",
    "runs/commercialization_readiness_current.json",
    "runs/commercialization_gap_burndown_current.json",
    "runs/wetlab_selected_allatom_gate_burndown_packet_current.json",
    "runs/accuracy_parity_scorecard_current.json",
]:
    data = json.load(open(path, encoding="utf-8"))
    print(path, {k: data.get(k) for k in ("delivery_ready", "verdict", "queue_clear", "blocked_count", "hard_block_count", "status")})
    summary = data.get("summary", {})
    print("summary", {k: summary.get(k) for k in ("tracked_readiness_accounting_closed", "tracked_gap_accounting_closed", "raw_blocked_bucket_count", "parked_or_review_only_blocked_count")})
PY
sed -n '1,220p' docs/local_delivery_p0_gate.md
```

## Reference Artifacts

- `docs/local_delivery_p0_gate.md`
- `docs/local_delivery_claim_policy.md`
- `docs/post_p0_commercial_expansion_queue.md`
- `docs/local_delivery_readiness_plan.md`
- `docs/local_delivery_runbook.md`
- `runs/wetlab_selected_allatom_repair_packet_current.md`
- `runs/wetlab_selected_allatom_gate_burndown_packet_current.md`
- `runs/local_delivery_verdict_gate_current.json`
- `runs/local_engine_commercialization_queue_current.json`
- `runs/accuracy_parity_scorecard_current.md`
- `runs/gpcr_a1_accuracy_repair_queue_current.md`
- `commercialization_status_report.md`
- `runs/gpcr_residual_prototype_spec_current.md`
- `runs/gpcr_residual_ab_summary_current.md`
- `runs/ligand_scaleup_100k_pilot_current.md`
