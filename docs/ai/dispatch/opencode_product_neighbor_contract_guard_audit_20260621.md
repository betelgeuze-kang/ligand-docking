# OpenCode read-only audit: product neighbor contract guard

Web access: disabled.

Goal: audit the current worktree for the next P0 slice of the independent product neighbor path. Do not edit files, do not stage, do not commit, do not push, do not delete, and do not mutate external state.

Scope:
- Inspect product/runtime paths that call `ProductForceField.energy_forces`, `core.ForceField.product_energy_forces`, `validate_energy_forces_contract`, and product-adjacent tools using `torch.cdist`.
- Focus on whether product mode can still silently accept `full_neighbor_pairs` or dense NxN distance tensors.
- Check likely files:
  - `betelgeuze_engine/contracts/result.py`
  - `betelgeuze_engine/physics/forcefield.py`
  - `betelgeuze_engine/physics/terms/*.py`
  - `tools/product/collect_feature_matrix.py`
  - `tools/product/report_sparse_checkpoints.py`
  - `monitor/physics_guard.py` if present
  - relevant tests under `tests/unit/`

Return a concise summary only:
- P0/P1 findings with file:line references.
- The smallest recommended code/test changes for this slice.
- Focused tests that should be run.
- Any blockers or risks.

Do not include full logs.
