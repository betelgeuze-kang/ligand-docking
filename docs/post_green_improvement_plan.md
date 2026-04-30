# Post-Green Improvement Plan

요약: 현재 P0 green 기준선을 고정하고, 다음 상용화 확장 큐는 별도 문서로 분리한다.

## Boundary

- Keep the committed green baseline for the restricted `kinase,gpcr,ion_channel` scope.
- Do not blend P0 delivery-ready evidence with new experiments, retries, or exploratory runs.
- This note is a post-green operating plan, not a scope expansion memo.

## Priority Order

1. Preserve the baseline
   - Treat [`docs/local_delivery_p0_gate.md`](local_delivery_p0_gate.md) and [`docs/local_delivery_claim_policy.md`](local_delivery_claim_policy.md) as the claim boundary.
   - Keep the green baseline frozen; only the new queue moves.
2. Follow the post-P0 expansion queue
   - Read [`docs/post_p0_commercial_expansion_queue.md`](post_p0_commercial_expansion_queue.md) next.
   - The queue order is: GPCR scale-up recovery, PDE translation quality, transporter `AQP1` / `GLUT1` evidence closure, `CA2` / `PXR` packet closure, and IDP broader-promotion guardrails.
3. Keep P0 wording narrow
   - `AQP1` / `GLUT1`, `CA2` / `PXR`, and IDP broader promotion stay review-only or partial-authoritative until their evidence lanes close.
   - Do not restyle the current P0 delivery claim as transporter, broad platform, or IDP-broader readiness.
4. Scale-up guardrail
   - The `100k` run is valid, but `gpcr_core_full` failed.
   - `commercialization_ready_suite_count=0`.
   - Pending milestones: `equal_size_ab`, `pilot_100k`, `pilot_1m`.

## Guardrails

- No threshold relaxation.
- No fake-pass.
- No transporter claim promotion, CA2/PXR claim promotion, or IDP broader-promotion claim.
- No expensive lane before translation or survival support improves.
- Keep P0 evidence and new experiments in separate queues.

## Local Verification

```bash
rg -n "post_p0_commercial_expansion_queue|AQP1|GLUT1|CA2|PXR|IDP broader" docs/post_green_improvement_plan.md docs/post_p0_commercial_expansion_queue.md docs/local_delivery_p0_gate.md docs/local_delivery_claim_policy.md
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
- `commercialization_status_report.md`
- `runs/gpcr_residual_prototype_spec_current.md`
- `runs/gpcr_residual_ab_summary_current.md`
- `runs/ligand_scaleup_100k_pilot_current.md`
