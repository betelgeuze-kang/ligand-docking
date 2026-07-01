# Product Stage and Roadmap - 2026-06-30

Audience: owner, product, science, engineering, verification

PM stance: 30-year senior PM review. The product is evaluated by what can be safely sold, demonstrated, operated, and defended with evidence, not by how much code exists.

## Executive Diagnosis

The product is currently a **restricted Tier-alpha pilot / operator-reviewed technical preview**, not a paid-pilot-ready commercial solver and not a broad molecular-discovery platform.

What is real:

- Local product/accounting machinery is strong: many gates emit structured blockers, no-mutation flags, fingerprints, and operator next actions.
- Restricted local product surfaces are partly ready: delivery/pilot packets, operational quality, capability surface, ROCm environment, and several evidence contracts are present.
- The repo has a clear fail-closed culture: current gates generally block overclaims rather than hiding them.

What is not yet real:

- G1/F2 solver closure is not available in this checkout. F2g/F2h are blocked because the real-MGT, `real_per_element` assembled tangent, near-null mode packet, and support/elastic-link context are absent.
- Release readiness is blocked by stale/source-of-truth and final refresh gates.
- Scientific validity is not claim-grade for broad docking/MD/free-energy/platform positioning.
- Developer Preview is not clean-baseline ready.
- Customer shadow evidence is schema-ready but has 0/3 real cases.
- External benchmark receipts are workflow-ready but receipt-missing.

The right commercial posture is therefore:

> Sell only as an operator-reviewed, local, restricted pilot/evidence-bundle workflow after final release freshness and DP baseline gates close. Do not sell as an autonomous solver, AlphaFold-like structure engine, calibrated Delta G/FEP engine, broad GPCR/platform system, or production AI/GPU solver until the named evidence gates close.

## Evidence Snapshot

| Area | Current evidence | PM interpretation |
| --- | --- | --- |
| PM queue | `.betelgeuze/pm_priority_queue_status_current.json`: `blocked_pm_priority_queue`, `ready_item_count=6`, `blocked_item_count=2` | Queue hygiene is mostly under control; F2g/F2h are the remaining technical blockers. |
| F2g/F2h | `.betelgeuze/f2g_f2h_surface_preflight.local.json`: `blocker_count=8`, no real-MGT/tangent/near-null/support context candidates | Cannot honestly perform requested support/elastic-link audit or continuation from current checkout. |
| Independent readiness | `scripts/check_independent_product_readiness.py`: `blocked_independent_product_readiness`, `pass_count=5`, `blocker_count=2` | Restricted product is close in accounting terms, but release source-of-truth and final refresh gates block readiness. |
| Release source of truth | `runs/product_release_source_of_truth_gate_current.json`: `blocked_product_release_source_of_truth_gate`, `pass_count=85`, `blocker_count=71`, `stale_artifact_count=37` | Too stale for release/pilot claims. Needs refresh discipline before any customer promise. |
| Release decision | `runs/goal_release_decision_gate_current.json`: `blocked_goal_release_decision`, `release_allowed=false`, `full_commercial_release_allowed=false`, `blocker_count=5` | Not release-ready. |
| Delivery/pilot packets | `product_delivery_evidence_contract_ready`, `product_pilot_packet_ready` | Packaging/evidence surface exists, but it is downstream of blocked release/customer/science gates. |
| API customer flow | `blocked_api_customer_flow_release_evidence`, `pass_count=4/6`, `blocker_count=2` | API customer-flow release evidence is not ready; Tier alpha dispatch smoke and bundle refresh remain. |
| Developer Preview | `docs/developer_preview_final_gate_action_register.md`: six final gates defined, all still pending receipts | DP is organized but not clean-baseline ready. |
| External benchmarks | four tracked items are `missing_not_attached`; dry-run blocked on missing default manifest | Operational evidence queue exists; no benchmark receipt closure. |
| Customer shadow | schema ready, `completed_customer_shadow_case_count=0`, required `3` | Future commercial readiness is blocked until real reviewed customer metadata rows exist. |
| GPU/HIP | ROCm environment and local benchmark ready; `product_production_ai_gpu_return_intake` blocked | GPU/HIP is performance/residency evidence only, not solver-truth or production residual promotion. |
| Science frontier | `blocked_science_accuracy_frontier`, public benchmark p05 below claim-grade floor and R8/R9 receipts pending | Restricted science diagnostics exist, but broad/commercial accuracy claims are blocked. |

## Product Stage

| Stage | Definition | Current state |
| --- | --- | --- |
| Lab prototype | Code paths and diagnostics exist. | Passed. |
| Evidence-accounted prototype | Gates, receipts, and claim boundaries exist. | Mostly passed. This is the product's strongest area. |
| Restricted technical preview | Operator can show scoped local workflow without broad claims. | Partially passed, blocked by Developer Preview final gates and API customer-flow release evidence. |
| Restricted paid pilot | Customer-facing evidence bundle, clean baseline, shadow intake, release freshness, and support playbook are ready. | Not yet. |
| Commercial scientific solver | Validated science claims, external benchmarks, row-level public holdouts, customer outcomes, and operational SLOs are defensible. | Not yet. |
| Broad platform | Enterprise workflow, security, governance, scale, wetlab/external validation, and broad claim review are complete. | Not yet. |

Current label: **Restricted Tier-alpha pilot, pre-paid-pilot, evidence-accounted but science/preview/release blocked.**

## Strategic Product Thesis

The winning wedge is not "general molecular AI platform." That claim is too broad for the current evidence.

The defensible wedge is:

> A local, operator-reviewed molecular docking/structure-analysis evidence workbench that produces auditable, fail-closed packets and exposes exactly what is ready, blocked, stale, or unsupported.

The product should lean into trust and governance first:

- "We do not overclaim."
- "Every claim has a receipt."
- "Every blocker is visible."
- "Customer raw data stays customer-retained."
- "GPU/HIP and AI are accelerators only after reference parity."

## Roadmap

### Phase 0 - Stabilize the Truth Surface

Goal: make the current state impossible to misunderstand.

Time horizon: immediate, 1-2 weeks.

Must close:

1. Release source-of-truth refresh
   - Evidence required: `product_release_source_of_truth_gate` blocker count materially reduced to zero for release freshness, or every contradiction explicitly documented.
   - Current blocker: `blocker_count=71`, `stale_artifact_count=37`.
   - Owner action: run approved release refresh chain, then rerun source-of-truth and release decision gates.

2. Final release refresh gates
   - Evidence required: `final_gate_verification_ready=true`, `final_gate_blocker_count=0`.
   - Current blocker: `final_gate_blocker_count=3`.

3. PM queue rollup stays canonical
   - Evidence required: `tools/build_pm_priority_queue_status.py` remains the reusable PM queue rollup.
   - Current result: 6/8 ready, F2g/F2h blocked.

Exit criteria:

- No stale readiness count ambiguity.
- No hidden release blockers.
- Release/pilot language still blocked unless gates prove otherwise.

### Phase 1 - Unblock the Core Solver Diagnostic Lane

Goal: restore the missing F2/G1 diagnostic inputs and produce the non-promoting audit requested by PM.

Time horizon: 1-3 weeks after the missing implementation surfaces are restored.

Must close:

1. Restore authoritative F2/G1 surfaces
   - Required surfaces: `implementation/phase1`, real-MGT input/model, `real_per_element` assembled tangent, near-null mode packet, support/elastic-link context.
   - Evidence required: `.betelgeuze/f2g_f2h_surface_preflight.local.json` no longer reports the 8 current missing-surface blockers.

2. F2g support/elastic-link reconciliation audit
   - Required output: `implementation/phase1/release_evidence/productization/g1_support_elastic_link_reconciliation_audit.local.json`.
   - Must include: near-null dominant DOFs, node IDs, DOF types, support membership, constrained/free state, elastic-link degree, distance/hops to support, support/free-space consistency, link endpoint mapping, stiffness stats, ranked findings.
   - Guardrail: non-promoting only, no pinning, no continuation, no G1 claim.

3. F2h lightweight continuation
   - Start condition: F2g audit exists.
   - Evidence required: load-scale `0.1 -> 0.2 -> 0.4`, residual histories, stop reasons, monotonicity/mode comparison.
   - Guardrail: no 0.656 regeneration, no G1 closure claim.

Exit criteria:

- F2g explains weak restraint vs mapping gap vs geometric softening.
- F2h demonstrates whether regularized Newton is stable beyond `load_scale=0.1`.
- G1 remains blocked or becomes promotable only through an explicit acceptance packet.

### Phase 2 - Make Developer Preview Showable

Goal: move from "technically interesting" to "safe to demo."

Time horizon: 2-4 weeks, parallel to Phase 1 where possible.

Six final gates:

1. Clean-checkout benchmark regeneration
2. Silent import loss zero
3. Selected medium models pass or approved review
4. Large models crash/OOM-free
5. Linux/Windows reproducibility
6. New-user core workflow observation

Evidence required:

- For each gate, a receipt under `.betelgeuze/` first.
- Only after review, protected evidence refresh may be considered.

Exit criteria:

- Developer Preview no longer depends on tribal knowledge or local hidden state.
- A new technical user can run the core workflow and produce fail-closed receipts.
- No AI/GNN/surrogate-truth claim is introduced.

### Phase 3 - Restricted Paid Pilot Readiness

Goal: establish a minimal customer-safe commercial motion.

Time horizon: 4-8 weeks after Phase 0/2 progress.

Must close:

1. API customer-flow release evidence
   - Current state: `blocked_api_customer_flow_release_evidence`, `pass_count=4/6`.
   - Evidence required: Tier alpha dispatch smoke, API E2E/restricted execution evidence, bundle validation artifacts.

2. Customer shadow intake
   - Current state: schema ready, `0/3` completed cases.
   - Evidence required: three reviewed `customer_shadow` rows, customer-retained raw data, `redistribution_allowed=false`, anonymized summary, reviewer signoff.

3. External benchmark receipt workflow
   - Current state: four rows `missing_not_attached`.
   - Evidence required: real receipt URL/closure evidence, not dry-run-only.

4. Support and sales boundary
   - Package: "restricted local pilot with operator-reviewed evidence bundles."
   - Explicitly excluded: autonomous solver, broad platform, AlphaFold parity, calibrated Delta G/FEP, wetlab hit.

Exit criteria:

- Customer can see the workflow without private raw data entering repo.
- Support can explain every blocker.
- Pilot terms match actual evidence.

### Phase 4 - Scientific Claim Upgrade

Goal: turn restricted diagnostics into defensible scientific claims.

Time horizon: 2-4 months.

Must close:

1. R8 full-scope claim closure
   - Current state: full commercial matrix blocked, `blocked_matrix_row_count=12`.
   - Evidence required: reviewed local evidence artifacts and approval tokens for scope-breadth receipts.

2. R9 engine refinement / public benchmark promotion
   - Current state: R9 statistical support and claim-grade gates blocked.
   - Evidence required: 51 DockQ/lDDT-PLI/internal DeltaG metric source payloads reviewed, materialized, and bootstrap Spearman p05 above claim floor.

3. Accuracy ligand-ranking blocker
   - Current state: restricted science accuracy can be ready, broad/commercial claim remains blocked.
   - Evidence required: broad GPCR claim review, scorer/router promotion, external/public benchmark evidence.

4. MD/free-energy baseline
   - Current state: proxy/blocker state.
   - Evidence required: exact topology/provenance, PME/PBC/constraints, ensemble checks, reference trajectory, convergence/overlap diagnostics for any Delta G/FEP claim.

Exit criteria:

- Claims map to row-level evidence.
- Marketing/API/report language can be safely widened only where evidence passes.

### Phase 5 - Production AI and GPU/HIP

Goal: use acceleration and residual intelligence without changing solver truth.

Time horizon: after CPU/reference gates are stable; do not make this a shortcut.

Must close:

1. Production AI registry promotion
   - Current state: `blocked_production_ai_registry_promotion_priority_packet`, top gate `default_residual_mode_guarded`.
   - Evidence required: guarded operator receipt, approval token, validation-chain review, customer-facing mutation disabled until approved.

2. GPU return intake
   - Current state: `blocked_product_production_ai_gpu_return_intake`.
   - Evidence required: full GPU regeneration summary, identity-locked manifest CSV, post-regeneration validation chain.

3. HIP parity after CPU reference
   - Required: same residual formula, same JVP/operator, no CPU fallback, device residency, CPU/GPU residual parity.

Exit criteria:

- GPU/HIP is faster and resident, not a substitute for CPU/reference closure.
- Residual mode remains `shadow` until guarded promotion is explicitly approved.

### Phase 6 - Enterprise Platform

Goal: move from operator-run local pilot to repeatable enterprise product.

Time horizon: 4-9 months after paid pilot evidence.

Must close:

- Versioned API/SDK/CLI
- PostgreSQL/durable queue/object storage
- GPU scheduler
- OIDC/RBAC and tenant isolation
- Audit logs, provenance, metrics/tracing
- Retry/idempotency
- Hosted smoke tests and recovery drills

Exit criteria:

- Customer operations no longer depend on manual local runbooks.
- Tenant isolation/security claims are tested, not assumed.
- SLOs and incident playbooks exist.

## 30/60/90-Day Operating Plan

### First 30 days

- Fix release source-of-truth and refresh final gates.
- Restore or locate F2/G1 real-MGT diagnostic surfaces.
- Execute DP gates A/B/F first: clean checkout, silent import loss, new-user workflow.
- Convert customer shadow schema into three operator-ready intake requests.
- Keep all broad claims frozen.

### Days 31-60

- Complete F2g audit if surfaces are restored.
- Run F2h only after F2g.
- Close API customer-flow release evidence.
- Turn external benchmark draft rows into real operator receipt queue entries.
- Start R8/R9 receipt fill work in priority order.

### Days 61-90

- Decide whether restricted paid pilot is supportable.
- If yes, package pilot as evidence-bundle workflow with strict claim boundary.
- If no, keep Developer Preview internal and continue R8/R9/customer shadow closure.
- Begin enterprise architecture decomposition only after paid-pilot wedge is stable.

## Kill Criteria and No-Go Rules

- No paid pilot if release source-of-truth remains stale/blocked.
- No G1/solver claim if F2g/F2h remain blocked or non-promoting.
- No customer evidence claim without three real reviewed customer-shadow rows.
- No external benchmark claim without receipt URL or closure evidence.
- No GPU/HIP claim as solver truth before CPU/reference parity.
- No broad platform claim before enterprise governance, security, and hosted operations pass.

## Recommended Next Engineering Slice

The next highest-leverage engineering task is not another broad feature. It is:

> Restore the F2/G1 real-MGT diagnostic surfaces or document their authoritative source, then rerun `tools/build_f2g_f2h_surface_preflight.py`.

If that preflight turns green, proceed immediately to the F2g support/elastic-link reconciliation audit. If it stays blocked, shift engineering energy to Developer Preview gates A/B/F and release freshness while the missing solver inputs are recovered.

## 2026-06-30 Execution Update

사용자 지시에 따라 로드맵 기간은 대기하지 않고 바로 최우선 엔지니어링 slice를 진행했다.

- `tools/build_f2g_f2h_surface_preflight.py`를 재실행했고 현재 checkout은 여전히 `blocked_f2g_f2h_surface_preflight`, `blocker_count=8`이다.
- 더미 JSON이나 placeholder surface로 gate를 속이지 않도록, `tools/build_f2g_f2h_authoritative_surface_recovery_packet.py`를 추가했다.
- 새 recovery packet은 `.betelgeuze/f2g_f2h_authoritative_surface_recovery_packet.local.json`에 8개 복구 항목을 구조화한다.
- 현재 다음 실제 실행 항목은 `implementation/phase1`의 권위 F2/G1 구현 tree를 원본 branch 또는 보호 archive에서 복구한 뒤 preflight를 다시 돌리는 것이다.
- F2g audit, F2h continuation, G1/solver claim promotion은 계속 금지 상태다.
