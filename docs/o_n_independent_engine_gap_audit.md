# O(N) Independent Engine Gap Audit

Date: 2026-06-21

Scope: current `betelgeuze-kang/ligand-docking` product runtime path for restricted ligand HTVS/backmapping. This is a code audit only; it does not promote a release claim.

## Executive Verdict

The P0 neighbor path is materially improved but not complete. The product KPI/evidence smoke path now requires provided cell-list neighbors for the forcefield and core compatibility bridge, product-required contracts reject reference `full_neighbor_pairs`/NxN diagnostics, product-adjacent diagnostics use `CellListNeighborProvider` instead of dense `torch.cdist`, and the runtime scaling gate records fixed-density coordinates, `nxn_allocation_observed`, memory-per-atom, and rebuild telemetry. Local and ROCm clean-container fixed-density release scaling for `N={1000,2000,4000,8000}` are ready with no blockers. Real ROCm clean-container `RustHipNeighborProvider` parity for `N={216,1000}` is ready with no blockers after normalizing Rust/HIP adapter distances to the product PBC minimum-image contract. Direct `ProductForceField.energy_forces()` now defaults to product-neighbor-required mode, and KPI force-term smokes for dense-fallback terms pass provider pairs. The remaining release blockers are direct term-level reference fallbacks for small reference use and keeping the self-hosted workflow receipt current after the uncommitted source changes are pushed.

Current status: `blocked_p0_o_n_neighbor_path`.

## Current P0 Evidence

- `betelgeuze_engine/physics/neighbor.py` contains:
  - `CellListNeighborProvider` with cutoff, skin, rebuild stride, optional PBC minimum image, max-neighbor cap, max-atoms-per-cell cap, overflow diagnostics, and compact `[B,N,K]` rows.
  - `neighbor_pairs_from_rust_hip_tensors()` and `RustHipNeighborProvider`, which adapt Rust/HIP compact tensors and fail closed without CUDA/backend support.
  - Rust/HIP adapter distances are recomputed from the adapter's PBC minimum-image displacement tensor, so `NeighborPairs.dist` matches the product compact-neighbor contract even when backend raw distance tensors are not already PBC-normalized.
  - `full_neighbor_pairs()` remains, marked by diagnostics as `reference_only` with `nxn_allocation_observed=true`.
- `betelgeuze_engine/physics/forcefield.py` defaults `product_neighbor_required=True`; it rejects missing neighbors, overflow, `nxn_allocation_observed=true`, and reference neighbor sources unless a small reference test explicitly opts out with `product_neighbor_required=False`.
- `betelgeuze_engine/contracts/result.py` now rejects product-required aggregate results with `full_neighbor_pairs`, `reference_full_pairs`, overflow, or `nxn_allocation_observed=true`, while keeping small reference validation legal outside product-required mode.
- `core/forcefield.py::ForceField.product_energy_forces()` now defaults `product_neighbor_required=True`, and the KPI/transition shim callers pass explicit `provided_cell_list` pairs.
- `monitor/physics_guard.py`, `tools/product/collect_feature_matrix.py`, and `tools/product/report_sparse_checkpoints.py` now use `CellListNeighborProvider` for overlap/contact/clash diagnostics instead of dense `torch.cdist`; provider overflow is fail-closed.
- `betelgeuze_engine/benchmark/runtime_scaling.py` now uses `CellListNeighborProvider` rather than the old capped dense-window probe, and records:
  - fixed-density cubic grid coordinates
  - `nxn_allocation_observed`
  - `fixed_density_ready`
  - `release_atom_counts_ready`
  - `memory_per_atom_linear_ready`
  - `max_memory_peak_mb_per_atom`
  - `total_rebuild_count`
  - row-level provider status, overflow, memory-per-atom, and rebuild cost.
- `tools/product/build_ai_md_engine_kpi_report.py` and `tools/product/build_ai_md_product_evidence_bundle.py` now gate runtime neighbor-cap evidence on `provided_cell_list`, provider-ready rows, no overflow, no NxN allocation, bounded memory-per-atom, and rebuild evidence. KPI aggregate forcefield smokes pass provider pairs with `product_neighbor_required=True`, and KPI force-term smokes for `legacy_lj`, `directional_hbond`, `hydrophobic_contact`, and `screened_electrostatics` pass provider pairs instead of relying on term-level dense fallback.
- `betelgeuze_engine/validation/force_checks.py` still supports small reference validation by default, but now accepts an optional provider pair builder so KPI finite-difference, invariance, and drift checks can run without implicit dense reference allocation.
- `tests/unit/test_product_neighbor_entrypoint_static_guards.py` statically guards product KPI/runtime aggregate forcefield calls so future regressions must include explicit `pairs=` and `product_neighbor_required=True`; it also blocks KPI force-term smoke calls for dense-fallback term aliases when no pairs are supplied.
- `tools/product/run_runtime_neighbor_release_scaling.py` provides the self-hosted release-scale CLI. Its default atom counts are `1000,2000,4000,8000`; it writes compact JSON/MD/SVG evidence and exits nonzero if the configured release atom counts are not covered.
- `deploy/verify_product_image.sh` runs the release-scale scaling CLI inside the ROCm product container during `PRODUCT_IMAGE_VERIFY_MODE=rocm-runtime`, and the product image receipt now requires `runtime_neighbor_release_scaling_ready=true` for `product_image_smoke_ready`.
- `tools/product/run_rust_hip_neighbor_provider_parity.py` compares CPU `CellListNeighborProvider` and real `RustHipNeighborProvider` compact pair sets, PBC-normalized distances, and LJ energy/force results. `deploy/verify_product_image.sh` now runs it inside the ROCm product container and requires `rust_hip_neighbor_provider_parity_ready=true` for `product_image_smoke_ready`.
- `.github/workflows/product-image-smoke.yml` surfaces the release scaling status in the ROCm runtime summary. This remains on `[self-hosted, linux, rocm]`, not GitHub-hosted runners.
- Focused local verification after this slice:
  - `python3 -m pytest -q tests/unit/test_product_neighbor_entrypoint_static_guards.py tests/unit/test_collect_feature_matrix.py tests/unit/test_sparse_checkpoint_helpers.py tests/unit/test_monitor_physics_guard.py tests/unit/test_betelgeuze_engine_scaffold.py tests/unit/test_engine_transition_shims.py tests/unit/test_build_ai_md_engine_kpi_report.py tests/unit/test_build_ai_md_product_evidence_bundle.py tests/unit/test_runtime_neighbor_release_scaling.py -x --tb=short` passed with `181 passed`.
  - Default runtime scaling smoke returned ready for fixed-density `N={64,125,216}` with pair counts `{384,750,1296}`, pair-count slope `~1.0`, `nxn_allocation_observed=False`, `fixed_density_ready=True`, `memory_per_atom_linear_ready=True`, and `release_atom_counts_ready=False`.
  - `python3 tools/product/run_runtime_neighbor_release_scaling.py --atom-counts 1000,2000,4000,8000 --release-atom-counts 1000,2000,4000,8000 --repeats 3 --warmup-repeats 1 --out-json runs/runtime_neighbor_release_scaling_current.json --out-md runs/runtime_neighbor_release_scaling_current.md --out-svg runs/runtime_neighbor_release_scaling_current.svg` exited `0`.
  - Release scaling receipt summary: status `runtime_neighbor_release_scaling_ready`, blockers `[]`, pair counts `{6000,11634,23776,48000}`, pair-count slope `1.003116`, pair-count R2 `0.999745`, duration slope `0.937647`, duration R2 `0.998746`, max memory/atom `0.487070 MB`, total rebuild count `8`, total rebuild duration `23.323675 s`, `nxn_allocation_observed=False`, all rows ready.
  - `PRODUCT_IMAGE_VERIFY_MODE=rocm-runtime PRODUCT_IMAGE_RELEASE_SCALING_ATOM_COUNTS=1000,2000,4000,8000 PRODUCT_IMAGE_RELEASE_SCALING_REPEATS=3 PRODUCT_IMAGE_RELEASE_SCALING_WARMUP_REPEATS=1 PRODUCT_IMAGE_RUST_HIP_PARITY_ATOM_COUNTS=216,1000 bash deploy/verify_product_image.sh` exited `0` under approved local Docker/ROCm access after rebuilding the product image from the current source tree.
  - Product image receipt summary: status `product_image_smoke_ready`, `container_runtime_rust_hip_backend_enabled=True`, kernel `compute_nonbonded_nblist_gpu`, visible device `AMD Radeon RX 6900 XT`, `tier_alpha_adrb2_dispatch_smoke_pass`, `product_runner_claim_metadata_ready=True`, `runtime_neighbor_release_scaling_ready=True`, `rust_hip_neighbor_provider_parity_ready=True`, `external_state_mutated=False`, `docker_state_mutated=True`.
  - ROCm container release scaling receipt summary: status `runtime_neighbor_release_scaling_ready`, blockers `[]`, release atom counts `{1000,2000,4000,8000}`, pair-count slope `1.003116`, pair-count R2 `0.999745`, max memory/atom `0.628977 MB`, `nxn_allocation_observed=False`, all rows ready.
  - `python3 -m pytest -q tests/unit/test_betelgeuze_engine_scaffold.py tests/unit/test_rust_hip_neighbor_provider_parity.py -x --tb=short` passed with `50 passed`.
  - ROCm clean-container Rust/HIP provider parity ran inside `deploy/verify_product_image.sh` from the rebuilt product image. Receipt summary: status `rust_hip_neighbor_provider_parity_ready`, blockers `[]`, atom counts `{216,1000}`, CPU/Rust-HIP pair counts `{1296,6000}`, max distance absolute delta `0.0`, max energy absolute error `4.7683716e-07`, max energy relative error `1.4503823e-07`, max force absolute error `0.0`, `nxn_allocation_observed=False`, all rows ready.
  - `python3 -m pytest -q tests/unit/test_runtime_neighbor_release_scaling.py` passed and verifies ready evidence for configured counts plus fail-closed `release_atom_counts_not_covered` behavior.
  - `python3 -m pytest -q tests/unit/test_betelgeuze_engine_scaffold.py tests/unit/test_build_ai_md_engine_kpi_report.py tests/unit/test_build_ai_md_product_evidence_bundle.py tests/unit/test_product_neighbor_entrypoint_static_guards.py tests/unit/test_runtime_neighbor_release_scaling.py tests/unit/test_rust_hip_neighbor_provider_parity.py -x --tb=short` passed with `167 passed` after the default product-neighbor-required flip.
  - `python3 -m pytest -q tests/unit/test_product_neighbor_entrypoint_static_guards.py tests/unit/test_betelgeuze_engine_scaffold.py tests/unit/test_build_ai_md_engine_kpi_report.py -x --tb=short` passed with `56 passed` after adding the KPI force-term dense-fallback static guard.

## Remaining P0 Blockers

1. Direct forcefield dense fallback now requires explicit reference opt-out.
   - `betelgeuze_engine/physics/forcefield.py` defaults `product_neighbor_required=True`.
   - If `pairs is None`, default calls fail closed before `full_neighbor_pairs()` can run.
   - Explicit `product_neighbor_required=False` still permits `full_neighbor_pairs()` for small reference tests only.
   - Required state: keep product runners/API paths on provider pairs and prevent new claim/evidence paths from opting out.

2. Term-level fallback can still allocate dense reference pairs.
   - `legacy_lj`, `directional_hbond`, `hydrophobic_contact`, and `screened_electrostatics` call `full_neighbor_pairs()` when invoked without `pairs`.
   - Their math is compact-safe when pairs are supplied through `neighbor_displacements()` and `neighbor_upper_mask()`.
   - KPI force-term smokes and validations now pass provider pairs, and static guards block known KPI dense-fallback aliases.
   - Required state: keep this fallback limited to small direct term reference tests and validation defaults; add broader guards if new product term entry points appear.

3. Fixed-density release-scale benchmark has local and ROCm clean-container evidence.
   - The runtime benchmark supports fixed-density coordinates and explicit `release_atom_counts`.
   - Local `N={1000,2000,4000,8000}` evidence is ready and blocked by no local gate.
   - The ROCm product-image runtime smoke ran `tools/product/run_runtime_neighbor_release_scaling.py` inside the product container with `N={1000,2000,4000,8000}` and produced a ready product-image receipt.
   - Required state: keep this receipt current on the self-hosted workflow required check after the uncommitted source changes are pushed.

4. Product-adjacent contact/clash/overlap diagnostics are provider-backed.
   - `monitor/physics_guard.py` builds compact overlap neighbors with `CellListNeighborProvider`.
   - `tools/product/collect_feature_matrix.py` computes contact edge count and largest component from compact provider rows, without constructing an adjacency distance matrix.
   - `tools/product/report_sparse_checkpoints.py` counts nonbonded clash pairs from compact provider rows.
   - Required state: keep overflow fail-closed and add runner/API evidence that these diagnostics are not used to reopen unbenchmarked claims.

5. Contract keeps `full_neighbor_pairs` legal only outside product-required mode.
   - `betelgeuze_engine/contracts/result.py` permits `"full_neighbor_pairs"` so small reference tests can validate the legacy fallback.
   - Product-required aggregates now reject reference sources and NxN diagnostics.
   - API and `betelgeuze_product` surfaces do not directly call forcefields; product KPI/runtime aggregate calls are covered by static guard tests.
   - Required state: keep reference mode out of claim/evidence paths as new entry points are added.

6. Large-N Rust/HIP provider parity is now covered at `N=1000`; broader performance parity is still pending.
   - `betelgeuze_engine/validation/force_checks.py` compares against `full_neighbor_pairs()`.
   - `tools/product/run_rust_hip_neighbor_provider_parity.py` compares CPU cell-list vs real Rust/HIP provider without dense reference allocation for `N={216,1000}`.
   - Required state: keep small-N dense validation reference-only, keep the ROCm parity receipt current in self-hosted workflow runs, and add broader provider performance parity only after the direct product fallback paths are fully locked.

## Allowed Reference-Only NxN Uses

- `full_neighbor_pairs()` in small unit tests and dense reference parity tests.
- `betelgeuze_engine/validation/force_checks.py` for small-N validation only.
- `betelgeuze_engine/benchmark/runtime_scaling.py::build_capped_neighbor_pairs()` as historical/reference helper only, not the product scaling gate.

## Gap Matrix

| Area | Current state | Required state |
| --- | --- | --- |
| Neighbor provider | Python cell-list and Rust/HIP adapter exist; current product KPI/runtime aggregate calls have static guards | Product runners/API always require provider pairs |
| Dense fallback | Product forcefield defaults product-required; explicit reference opt-out remains for small tests | Prevent claim/evidence/API paths from opting out |
| Force terms | Compact-safe with pairs; KPI dense-fallback term smokes now pass provider pairs; direct term fallback remains for small tests | Product path never invokes terms without provider pairs |
| Scaling gate | Fixed-density fast smoke plus local and ROCm clean-container `1k,2k,4k,8k` release evidence ready | Keep required self-hosted workflow receipt current after push |
| EvidenceBundle | Runtime neighbor-cap gate rejects NxN rows and product image receipt requires release scaling readiness | Keep product-image receipt attached and public benchmark blockers honest |
| Product-adjacent tools | Contact/clash/overlap diagnostics use `CellListNeighborProvider` and fail closed on overflow | Keep claim boundary closed until release-scale evidence covers these paths |
| Rust/HIP parity | Tensor adapter tests and real ROCm `N={216,1000}` provider parity exist | Keep self-hosted parity receipt current; broaden performance parity after direct fallback lock |
| Restricted families | Profiles/gates exist elsewhere | Tie `gpcr/kinase/ion_channel` pilot semantic gates to product E2E |

## Next Implementation Slices

1. Keep the ROCm product-image release-scaling and Rust/HIP provider-parity receipts current in GitHub Actions after commit/push.
2. Add broader static/contract coverage for any future product term entry points that could bypass provider pairs.
3. Move from P0 runtime locking into the first P1 topology/manifest blocker once the self-hosted receipts are green on the pushed source.
