# TASK-v2-posebusters-vina-sulfur-type-invariance

## Goal

Preregister and execute an installable, failure-inclusive proof of whether the
three observed `SA`/`S` sulfur differences affect the active default Vina 1.2.7
scoring lane.

## Scope

- Bind exact preparation, Vina execution, Open Babel comparison, pose-artifact,
  Vina distribution, official-tag source-file, configuration, and runtime
  identities before rescoring.
- Freeze the three neutral-thioether cases and mutate only the target PDBQT
  atom type from `SA` to `S`, retaining the other 305 denominator rows.
- Verify from exact Vina source that both AD types map to `XS_TYPE_S_P`, default
  Vina scoring uses XS types, and sulfur is absent from the XS acceptor set.
- Rescore every retained Vina pose in both variants and require exact equality
  of every public score component.

## Non-goals

- Do not adjudicate chemical hydrogen-bond acceptor correctness or AD4 scoring.
- Do not rerun pose search, tune thresholds, change charges/coordinates, or
  promote a docking, chemistry, or product claim.

## Likely Files Or Search Targets

- `betelgeuze_engine_v2/benchmark/public_posebusters_vina_sulfur_type_invariance.py`
- package exports, CLI metadata and workflow guards
- focused unit, package, release, public API, status, and roadmap files

## Verification

- Focused unit/CLI/security tests, Ruff, `git diff --check`.
- Exact protocol registration plus source-tree and installed-wheel observation.
- Two byte-identical wheels and all failure/abstention rows retained.

## Stop Conditions

- Follow `AGENTS.md`; never inspect `.env*` or mutate external state.
- Stop rather than weakening source, runtime, mutation, equality, or claim gates.

## Risk Level

R3
