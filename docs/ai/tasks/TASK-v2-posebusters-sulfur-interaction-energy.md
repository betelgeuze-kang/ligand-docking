# TASK-v2-posebusters-sulfur-interaction-energy

## Goal

Preregister and execute a failure-inclusive neutral-thioether O-H donor
interaction-energy gate for the three observed Meeko `SA` versus Open Babel
`S` cases, alongside the exact AutoDock4 pair semantics.

## Scope

- Bind the prior QM-ESP and default-Vina invariance receipts, exact Vina 1.2.7
  source, PySCF 2.14.0, and PySCF-dispersion 1.5.0 before calculation.
- Freeze three environment-matched thioether models, one methanol O-H donor,
  six S-H distances, one orientation control, and every complex/ghost geometry.
- Compute fixed-geometry B3LYP-D3(BJ)/def2-SVP Boys-Bernardi counterpoise
  energies with one native thread and retain every SCF result or failure.
- Reproduce the exact AD4 `S-HD` van der Waals and `SA-HD` hydrogen-bond
  formulas, weights, profiles, and preregistered model-level decisions.
- Preserve the full 308-row denominator and explicit 305 scope abstentions.

## Non-goals

- Do not generalize one O-H donor or three models to all thioethers or donors.
- Do not treat a model complex as a ligand/receptor benchmark or full AD4 score.
- Do not optimize geometry, tune thresholds after results, or promote product.

## Likely Files Or Search Targets

- `betelgeuze_engine_v2/benchmark/public_posebusters_sulfur_interaction_energy.py`
- package exports, CLI metadata, workflow/package guards, focused unit tests
- public API, status, release, and scientific evidence roadmap docs

## Verification

- Focused unit/CLI/security tests, Ruff, `git diff --check`.
- Exact protocol registration before QM; source-tree and installed-wheel rerun.
- Two byte-identical wheels; preserve every failure and abstention row.

## Stop Conditions

- Follow `AGENTS.md`; never inspect `.env*` or mutate external state.
- Stop rather than weakening source, runtime, counterpoise, denominator, or
  claim gates.

## Risk Level

R3
