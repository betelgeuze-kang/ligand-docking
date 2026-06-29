# PM Priority Queue Status - 2026-06-29

Status basis: `main` checkout at `05f4f4f0` before this note was added, local read-only commands, local `.betelgeuze/` draft packets, and GitHub PR state checked at 2026-06-29 22:12 KST.

Claim boundary: this is a PM status note only. It does not promote release readiness, paid-pilot readiness, G1 closure, solver-product readiness, external benchmark closure, customer evidence completion, or GPU/HIP solver truth.

Machine-readable refresh:

```bash
gh pr list --state open --json number,title,url > .betelgeuze/github_open_prs_current.json
python3 tools/build_pm_priority_queue_status.py \
  --out-json .betelgeuze/pm_priority_queue_status_current.json \
  --out-csv .betelgeuze/pm_priority_queue_status_current.csv \
  --out-md .betelgeuze/pm_priority_queue_status_current.md
```

Current rollup result: `blocked_pm_priority_queue`, `ready_item_count=6`, `blocked_item_count=2`, `first_blocked_item_id=2`, `technical_blockers=[f2g_authoritative_surfaces_missing,f2h_blocked_until_f2g_audit]`.

## Queue Snapshot

| PM item | Current status | Evidence | Next action |
| --- | --- | --- | --- |
| 0. stale PR cleanup | closed | `gh pr list --state open` returned `[]`; PRs `#29`, `#35`, and `#36` are `MERGED`. | No stale web/docs PR remains ambiguously open. Keep future PRs rebased and CI-scoped. |
| 1. readiness snapshot/doc sync | documented blocked | Stored source-of-truth gate is `blocked_product_release_source_of_truth_gate`, `row_count=156`, `pass_count=85`, `blocker_count=71`; local no-protected-write recalculation reports `pass_count=64`, `blocker_count=92`. | Do not promote readiness. If protected evidence refresh is approved, run the release refresh chain, then rerun source-of-truth and release decision gates. |
| 2. F2g support/elastic-link audit | blocked before audit | `.betelgeuze/f2g_f2h_surface_preflight.local.json` is `blocked_f2g_f2h_surface_preflight` with 8 blockers: missing `implementation/phase1`, productization evidence dir, real-MGT input surface, `real_per_element` tangent surface, near-null mode packet, support/elastic-link context, F2g audit, and F2h prerequisite. | Restore the F2/G1 real-MGT implementation and diagnostic input surfaces; then run the non-promoting support/elastic-link reconciliation audit. |
| 3. F2h lightweight continuation | blocked by F2g | Same F2g/F2h preflight reports `f2g_audit_ready=false`, `f2h_continuation_allowed=false`, `g1_promotion_allowed=false`. | Do not start continuation until the F2g local audit exists. |
| 4. Developer Preview baseline clean | action register ready, gates still blocked | `docs/developer_preview_final_gate_action_register.md` lists six final gates with owner command, expected output, current blocker, and next action. | Execute the six DP gates in priority order in a clean checkout; record reviewed receipts under `.betelgeuze/` before considering protected artifact refresh. |
| 5. external benchmark receipts | draft workflow ready, receipts missing | `.betelgeuze/external_benchmark_receipt_queue_batch_update.json` has four rows for `hardest_external_10case`, `korean_public_structures`, `peer_spd_hinge`, and `tpu_hffb`; each is `missing_not_attached`, no `receipt_url`, dry-run failed on missing default manifest. | Operator must create/confirm queue rows and attach real receipt URLs only after external closure evidence exists. |
| 6. customer shadow intake | schema ready, 0/3 cases | `config/customer_shadow_evidence_intake_template.csv`, `tools/build_customer_shadow_evidence_status.py`, and tests are present. `.betelgeuze/customer_shadow_evidence_status_current.json` is `blocked_customer_shadow_evidence_status`, completed cases `0`, missing cases `3`. | Collect three real customer-shadow metadata rows with customer-retained raw data and reviewer signoff; do not store private raw data. |
| 7. GPU/HIP after CPU parity | plan ready, product intake blocked | `docs/gpu_hip_parity_after_cpu_plan.md` keeps GPU/HIP as performance/residency after CPU closure. ROCm environment and product ROCm benchmark receipts are ready, but `runs/product_production_ai_gpu_return_intake_current.json` remains `blocked_product_production_ai_gpu_return_intake`. | Keep GPU/HIP non-promoting until CPU reference closure, device residency, CPU/GPU residual parity, full GPU regeneration return, and post-return validation chain all close. |

## Open Technical Blocker

The first unresolved technical gate remains F2g. The current checkout cannot produce `implementation/phase1/release_evidence/productization/g1_support_elastic_link_reconciliation_audit.local.json` because the authoritative real-MGT assembled tangent and support/elastic-link diagnostic inputs are absent. Any F2h continuation before that audit would violate the PM ordering.

## Non-Promotion Invariants

- Recent F2/G1 diagnostics remain non-promoting.
- Missing blocker ids such as `full_load_gate_not_closed`, `full_mesh_nonlinear_equilibrium_not_closed`, `material_newton_breadth_not_closed`, and `production_rocm_hip_residency_not_closed` are not closure.
- External benchmark tracks are not PASS without receipt URL or closure evidence.
- Customer shadow mock/fixture rows do not count toward the three real-case minimum.
- GPU/HIP receipts do not replace CPU residual, Jacobian/JVP, or Newton closure.
