# O(N) Independent Engine Gap Audit

Date: 2026-06-21

Scope: current `betelgeuze-kang/ligand-docking` product runtime path for restricted ligand HTVS/backmapping. This is a code audit only; it does not promote any runtime claim.

## Executive Verdict

The current product forcefield path is not yet claim-safe for the new O(N) independent-engine objective. The repo has a useful Rust/HIP cell-list kernel and several fail-closed chemistry/product gates, but the Python product forcefield contract still represents neighbors as dense `[B, N, N]` tensors and falls back to `full_neighbor_pairs()` when no pairs are supplied.

Current status: `blocked_p0_o_n_neighbor_path`.

## P0 Blockers

1. Product forcefield fallback is dense NxN.
   - `betelgeuze_engine/physics/neighbor.py:15` builds `idx`, `dist`, and `mask` as `[B, N, N]`.
   - `betelgeuze_engine/physics/forcefield.py:246` calls `full_neighbor_pairs()` whenever `pairs` is omitted.
   - This means product callers can silently use O(N^2) memory/time instead of failing closed.

2. Product terms recompute dense pair distances even when neighbor pairs are provided.
   - `betelgeuze_engine/physics/terms/legacy_lj.py:22-23`
   - `betelgeuze_engine/physics/terms/screened_electrostatics.py:156-157`
   - `betelgeuze_engine/physics/terms/directional_hbond.py:23-51`
   - `betelgeuze_engine/physics/terms/hydrophobic_contact.py:23-66`
   - The `pairs.mask` may be sparse in intent, but the term math still materializes `coords.unsqueeze(2) - coords.unsqueeze(1)`.

3. Existing runtime scaling gate is not a true fixed-density/cutoff O(N) gate.
   - `betelgeuze_engine/benchmark/runtime_scaling.py:88-105` creates a dense `[B, N, N]` mask/dist packet with an index-window pattern, not a spatial cutoff/cell-list.
   - Default sizes are `8,16,32,64,128` at `runtime_scaling.py:257-261`, not `1k,2k,4k,8k+`.
   - The gate checks pair-count slope only; duration is explicitly advisory in the SVG text and there is no peak-memory-per-atom assertion.

4. Current contracts allow `full_neighbor_pairs` as valid product diagnostics.
   - `betelgeuze_engine/contracts/result.py:280` permits `neighbor_source in {"provided", "full_neighbor_pairs"}`.
   - Tests currently assert `full_neighbor_pairs` as expected product evidence, for example `tests/unit/test_betelgeuze_engine_scaffold.py:397-398` and `tests/unit/test_build_ai_md_engine_kpi_report.py:2248-2251`.
   - This conflicts with the new rule: full-pair generation must be limited to small reference tests only.

5. Neighbor parity validation is itself dense-reference based.
   - `betelgeuze_engine/validation/force_checks.py:89-90` compares candidates against `full_neighbor_pairs()`.
   - That is acceptable for small reference tests, but it cannot be the product-size parity gate for `1k+` fixed-density runs.

## Existing Assets

- Rust/HIP has a cell-list and neighbor-list builder:
  - `rust_engine/src/nonbonded_kernel.hip:197-236` builds cells.
  - `rust_engine/src/nonbonded_kernel.hip:238-340` builds capped neighbor rows with periodic minimum-image deltas.
  - `rust_engine/src/lib.rs:261` exposes `build_neighbor_list_gpu`.
- `core/rust_hip_backend.py:323-324` discovers `build_neighbor_list_gpu`.
- `core/rust_hip_backend.py:951-984` has a fused cell-list nonbonded path for `compute_nonbonded_celllist_gpu`.
- EvidenceBundle/product gates already fail closed on clean ROCm runtime receipt requirements:
  - `tools/product/build_ai_md_product_evidence_bundle.py:2727-2753`
  - `tools/product/build_ai_md_product_evidence_bundle.py:2772-2785`
- Self-hosted CI is configured to avoid GitHub-hosted minutes:
  - `.github/workflows/product-image-smoke.yml:70-78` build smoke on self-hosted Linux.
  - `.github/workflows/product-image-smoke.yml:115-123` ROCm runtime smoke on self-hosted ROCm labels.

## Gap Matrix

| Area | Current state | Required state |
| --- | --- | --- |
| Python neighbor provider | Dense `NeighborPairs` only | `NeighborProvider` with cell-list/spatial-hash, cutoff+skin, PBC minimum image, rebuild stride |
| Product forcefield | Falls back to dense full pairs | Product mode requires provider/candidate pairs; dense fallback only under explicit reference mode |
| Force terms | Several terms recompute NxN distances | Terms consume compact pair rows or provider batches without NxN tensors |
| Overflow handling | HIP builder caps rows but product gate does not own overflow semantics | Max-neighbor/cell overflow diagnostics and fail-closed claim metadata |
| Parity tests | Small dense reference only | Python reference vs Rust/HIP pair set, distance, energy, force parity |
| Scaling gate | Synthetic dense capped-window probe | Fixed-density `N={1k,2k,4k,8k+}` warm-up benchmark with runtime slope, peak memory/atom, rebuild cost, NxN allocation zero |
| EvidenceBundle | Requires runtime plot artifact, not true O(N) proof | Product claim blocked unless fixed-density O(N) gate passes |
| Restricted family semantics | Scope exists in docs/tests/profiles, but semantic pilot profile gate is not tied to O(N) runtime | `gpcr`, `kinase`, `ion_channel` pilot profiles and semantic validator required before release |

## Immediate Implementation Slice

Implement P0 in small slices:

1. Add `betelgeuze_engine.physics.neighbor.ProviderConfig`, `NeighborBuildDiagnostics`, and `CellListNeighborProvider`.
   - Output compact rows shaped `[B, N, K]` or flat `(batch, i, j, distance)` plus overflow diagnostics.
   - Include cutoff, skin, box/PBC minimum image, rebuild stride, max-neighbor cap, max-atoms-per-cell cap.
   - Keep `full_neighbor_pairs()` but mark it reference-only and guard product calls.

2. Add product fail-closed enforcement.
   - `ProductForceField.energy_forces(..., product_neighbor_required=True)` should reject missing provider/pairs in product mode.
   - Contract should distinguish `provided_cell_list`, `rust_hip_cell_list`, and `reference_full_pairs`.
   - Product EvidenceBundle should reject `reference_full_pairs`.

3. Convert one force term first.
   - Start with LJ because it is the simplest nonbonded term.
   - Make it consume compact neighbor rows without constructing `[B,N,N]` distance tensors.
   - Add finite-difference and parity tests against dense reference for small `N`.

4. Promote the benchmark.
   - Add fixed-density coordinate generator and run `N={1000,2000,4000,8000}` when resources allow.
   - Record warm-up, runtime slope, peak memory/atom, pair count/atom, rebuild count/cost, overflow count, and `nxn_allocation_observed=false`.
   - Block release when slope/memory/overflow thresholds fail.

## Current CI Note

As of this audit, the self-hosted `product-image-smoke` rerun for main commit `396b179e` is still in progress on runner `betelgeuze-rocm-betelgeuze-X570S-AORUS-ELITE`. The previous Docker disk blocker was cleared enough to pull the ROCm/PyTorch base image, but this build-only run does not prove the new P0 O(N) objective and does not include the local audit work.
