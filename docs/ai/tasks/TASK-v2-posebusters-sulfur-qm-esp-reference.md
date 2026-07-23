# TASK-v2-posebusters-sulfur-qm-esp-reference

## Goal

Preregister and execute an installable, failure-inclusive QM electrostatic-
potential comparison for the exact sulfur cases exposed by the Open Babel
charge/type receipt.

## Scope

- Bind the exact PoseBusters archive, preparation artifacts, comparison receipt,
  PySCF 2.14.0 wheel, implementation, configuration, and CPU runtime identities.
- Register before execution: fixed source start-SDF geometry, explicit H atoms,
  RHF/6-31G*, single thread, strict SCF convergence, and no geometry optimization.
- Use deterministic four-shell 1.4/1.6/1.8/2.0 vdW surfaces and compare the QM
  field with actual Meeko and Open Babel PDBQT charge-site fields.
- Retain all 308 rows: four scoped sulfur cases plus every failure/abstention.
- Report per-shell/global weighted MAE, RMSE, signed error, maximum error,
  relative RMSE, field correlation, convergence, energy, and exact artifacts.

## Non-goals

- Do not treat atom-centered charges, PySCF, or either implementation as an
  absolute scientific oracle or open a product/chemistry claim.
- Do not use ESP alone to adjudicate `SA` versus `S` hydrogen-bond typing.
- Do not optimize geometry, tune thresholds after results, or expand chemistry.

## Likely Files Or Search Targets

- `betelgeuze_engine_v2/benchmark/public_posebusters_*`
- `packaging/engine-v2/pyproject.toml`
- `tests/unit/test_engine_v2_prepared_ligand_diagnostic.py`
- public API, status, release, and scientific evidence roadmap docs

## Verification

- Focused unit/CLI/security tests, Ruff, architecture guard, `git diff --check`.
- Byte-exact protocol registration, source-tree and installed-wheel exact rerun.
- Two byte-identical package builds; preserve every production failure row.

## Stop Conditions

- Follow `AGENTS.md`; never inspect `.env*` or mutate external state.
- Stop rather than weakening source, runtime, SCF, denominator, or claim gates.

## Risk Level

R3
