# Post-Green Improvement Plan

요약: 현재 P0 green 기준선을 고정하고, 다음 실험은 claim-safe 개선 큐로만 분리한다.

## Boundary

- Keep the committed green baseline for the restricted `kinase,gpcr,ion_channel` scope.
- Do not blend P0 delivery-ready evidence with new experiments, retries, or exploratory runs.
- This note is a post-green operating plan, not a scope expansion memo.

## Priority Order

1. Preserve the baseline
   - Treat [`docs/local_delivery_p0_gate.md`](local_delivery_p0_gate.md) and [`docs/local_delivery_claim_policy.md`](local_delivery_claim_policy.md) as the claim boundary.
   - Keep the green baseline frozen; only the new queue moves.
2. Stale wetlab artifact cleanup
   - Once the current gate is green, use `runs/wetlab_selected_allatom_repair_packet_current.md` as a regression/retry reference.
   - Do not treat the repair packet as current proof of pass.
3. Wetlab broader readiness follow-up
   - Track the borderline `translation gate 68.1`, `binding_energy_proxy_too_weak_for_translation`, and missing backmapping / pose-validation metrics.
   - Keep the expensive lane deferred until translation and survival support improve.
4. Transporter lane
   - `AQP1` / `GLUT1` remain blocked.
   - Placeholder-driven rows: `6`.
   - Negative evidence missing: `6`.
   - Authoritative apply is blocked; keep this outside claim scope.
5. CA2 / PXR
   - `CA2` ligand ledger is `6/6` blocked with placeholder `ligand_id=6`.
   - `PXR` still needs placeholder and provenance fill.
   - Close evidence first, then revisit any scope expansion.
6. IDP
   - Keep the lane controlled and shadow-only.
   - `broader_promotion_blocked=true`.
7. Scale-up guardrail
   - The `100k` run is valid, but `gpcr_core_full` failed.
   - `commercialization_ready_suite_count=0`.
   - Pending milestones: `equal_size_ab`, `pilot_100k`, `pilot_1m`.

## Guardrails

- No threshold relaxation.
- No fake-pass.
- No transporter claim promotion or broad platform claim.
- No expensive lane before translation or survival support improves.
- Keep P0 evidence and new experiments in separate queues.

## Local Verification

```bash
rg -n "transporter.*ready|broad platform.*delivery-ready" docs/post_green_improvement_plan.md README.md README.ko.md
sed -n '1,220p' docs/local_delivery_p0_gate.md
sed -n '90,120p' docs/local_delivery_verdict_template.md
```

## Reference Artifacts

- `docs/local_delivery_p0_gate.md`
- `docs/local_delivery_claim_policy.md`
- `docs/local_delivery_readiness_plan.md`
- `docs/local_delivery_runbook.md`
- `runs/wetlab_selected_allatom_repair_packet_current.md`
- `runs/wetlab_selected_allatom_gate_burndown_packet_current.md`
- `runs/local_delivery_verdict_gate_current.json`
- `runs/local_engine_commercialization_queue_current.json`
- `commercialization_status_report.md`
- `runs/gpcr_residual_prototype_spec_current.md`
- `runs/gpcr_residual_ab_summary_current.md`
- `runs/ligand_scaleup_100k_pilot_current.md`
