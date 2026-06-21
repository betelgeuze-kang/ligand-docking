# TASK-ID: Tier Beta BioDiscovery Vertical Slice Worker

## Worker Path

Use OpenCode as a scoped implementation worker. Web access is disabled.

## Goal

Implement a narrow local-only Tier-beta structure-based ligand screening vertical-slice substrate that Codex can review and integrate.

## Scope

- Read the goal baseline docs named in the objective before editing.
- Prefer new canonical code under `betelgeuze_engine/**`.
- Keep `core/**` compatibility-only; do not broaden legacy core surfaces.
- Create or update a typed service that accepts local PDB/mmCIF text or path plus SMILES/SDF input and performs:
  - protein/ligand preparation
  - topology validation
  - pocket resolution
  - pose ensemble generation
  - scoring/ranking
  - top-K refine
  - optional short deterministic stability simulation
  - signed result manifest / evidence bundle-like artifact
- Use deterministic local calculations only. No external data, downloads, public PDB lookup, AlphaFold/ColabFold/ESMFold/OmegaFold, template/native lookup, or other-team models.
- Fail closed on invalid ligand, ambiguous chirality, placeholder protein/topology, unsupported metal/cofactor, dense/reference NxN product path, neighbor overflow, and unsigned result.
- Add focused direct tests for service success and negative paths if time allows.

## Preferred Files

- New files under `betelgeuze_engine/biodiscovery/**` or similar canonical package.
- `betelgeuze_engine/physics/dense_guard.py` may be adopted if useful; do not delete it.
- Tests under `tests/unit/` with tiny inline/local fixtures.

## Avoid Unless Necessary

- Do not make broad edits to `api/product.py`; Codex will handle API router split/integration.
- Do not modify `runs/**` except a tiny machine-readable receipt only if your implementation has a clear writer and Codex can review it.
- Do not stage, commit, push, deploy, submit, delete, or mutate external state.
- Do not inspect `.env*` files.

## Verification

Run only focused tests for files you changed when safe. Do not run full pytest.

## Return Summary

Return at most 80 lines:

- changed files
- focused checks run and pass/fail
- key contract decisions
- remaining blockers

Do not paste full logs or full diffs.
