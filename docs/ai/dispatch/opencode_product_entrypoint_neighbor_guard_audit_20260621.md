# OpenCode read-only audit: product entrypoint neighbor guard

Web access: disabled.

Goal: audit the current worktree for product/API/runner entry points that can evaluate product forcefield or product-adjacent runtime evidence without explicit provider-backed neighbors or product neighbor guards. Do not edit files, stage, commit, push, delete, run Docker, or mutate external state.

Context:
- Product forcefield product mode must not use `full_neighbor_pairs()` or dense NxN distance tensors.
- `ProductForceField.energy_forces(..., product_neighbor_required=True)` now rejects reference/NxN/overflow diagnostics.
- `core.ForceField.product_energy_forces()` defaults `product_neighbor_required=True`.
- `tools/product/collect_feature_matrix.py`, `tools/product/report_sparse_checkpoints.py`, and `monitor/physics_guard.py` were converted to `CellListNeighborProvider`-backed diagnostics.

Scope:
- Inspect likely product/API/runner surfaces:
  - `betelgeuze_product/**/*.py`
  - `tools/product/**/*.py`
  - `api/**/*.py` if present
  - `core/forcefield.py`
  - `betelgeuze_engine/physics/forcefield.py`
  - `betelgeuze_engine/benchmark/runtime_scaling.py`
  - relevant unit tests
- Search for:
  - `ProductForceField`, `default_product_forcefield`, `product_energy_forces(`
  - `.energy_forces(` on product forcefields
  - `full_neighbor_pairs`
  - `torch.cdist`
  - `neighbor_product_required`, `product_neighbor_required`
- Ignore explicit small reference tests and CASP-only internal physics tools unless they are product/API/runner paths.

Return a concise summary only:
- P0/P1 findings with file:line references.
- Whether API/runner paths still need a static guard test.
- Smallest recommended code/test changes for this slice.
- Focused tests to run.

Do not include full logs.
