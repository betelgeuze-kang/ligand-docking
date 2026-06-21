# OpenCode worker slice: WaterDisplacementProxyTerm guarded force implementation

Web access: disabled.

## Goal

Implement the missing v2 guarded force term `WaterDisplacementProxyTerm` and wire it into the same product KPI/evidence-bundle gates used by the existing guarded terms.

## Scope

Allowed files:

- `betelgeuze_engine/physics/terms/water_displacement_proxy.py` (new)
- `betelgeuze_engine/physics/terms/__init__.py`
- `betelgeuze_engine/physics/forcefield.py`
- `tools/product/build_ai_md_engine_kpi_report.py`
- `tools/product/build_ai_md_product_evidence_bundle.py`
- `tests/unit/test_betelgeuze_engine_scaffold.py`
- `tests/unit/test_build_ai_md_engine_kpi_report.py`
- `tests/unit/test_build_ai_md_product_evidence_bundle.py`

Do not broaden into GUI, Docker, GitHub Actions, CASP target lookup, or unrelated docs.

## Term contract

Add `WaterDisplacementProxyTerm` with `name = "water_displacement_proxy"`.

Behavior:

- It is opt-in guarded, not part of `default_force_term_registry()`.
- It is part of `guarded_force_term_registry()`.
- It returns `TermResult` with energy, forces, diagnostics, and claim metadata.
- It is claim-safe only when:
  - `topology_fidelity == "sequence_mapped"`
  - `ligand_topology_valid is True`
  - `ligand_topology_claim_safe` is true when present
  - `water_displacement_model_valid is True`
  - valid `ligand_atom_indices` are present
  - valid `water_displacement_site_indices` or `hydration_site_indices` are present
- It must fail closed with zero energy/forces and explicit blockers for:
  - non-sequence-mapped topology
  - invalid ligand topology
  - unvalidated water displacement model
  - missing/invalid ligand indices
  - missing/invalid water site indices
  - invalid optional water site weights
  - policy cap exceeded
- Use only atom/site indices into `state.coords`, not absolute coordinates, so finite-difference, translation invariance, and rotation equivariance tests are meaningful.

Suggested proxy energy:

```text
E = -k_water * sum_{ligand atom i, water site j} weight_j * exp(-0.5 * (distance(i,j)/sigma)^2)
```

Use autograd forces. Default conservative caps:

- `k_water = 0.05`
- `sigma = 1.0`
- `max_abs_energy = 20.0`
- `max_force_norm = 10.0`
- `max_active_pair_count = 4096`

Include cap metadata matching `PocketWallTerm`, `TorsionPriorTerm`, and `TopologyPenaltyTerm`.

## KPI/bundle wiring

- Add `water_displacement_proxy` to guarded registry expected names and required guarded term set.
- Add a valid KPI smoke fixture with finite-difference force error `< 1e-5`.
- Add missing metadata, unvalidated model, invalid topology, invalid weights, and cap-exceeded blockers.
- Add a `guarded_term_rows` entry and forcefield guarded claim-row coverage.
- Add product bundle validator checks for the new term’s valid row and blocker rows.

## Tests to run

Run at least:

```bash
python3 -m pytest -q tests/unit/test_betelgeuze_engine_scaffold.py -k "water_displacement or guarded_force_term_registry"
python3 -m pytest -q tests/unit/test_build_ai_md_engine_kpi_report.py tests/unit/test_build_ai_md_product_evidence_bundle.py
```

## Return format

Return only a concise summary:

- changed files
- tests run
- P0/P1 findings or blockers
- P2/nits

Do not read `.env*`. Do not commit, push, delete, deploy, upload, or mutate external state.
