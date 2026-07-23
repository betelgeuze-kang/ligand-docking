# TASK-v2-posebusters-pose-scaffold-identity

## Goal

Close the PoseBusters pose-ranking intake's missing per-pose coordinate and
ligand-scaffold identities without weakening its fixed test-only or all-case
evidence boundaries.

## Scope

- Bind the exact archive, preparation, Vina/GNINA/Smina execution, and
  pose-ranking intake receipts plus their caller-pinned artifact roots.
- Derive one topology-aware coordinate digest for every generated PDBQT model
  while retaining one explicit identity row for every upstream failure row.
- Derive a pinned RDKit 2025.09.6 non-isomeric Bemis-Murcko scaffold identity
  for every case, with an explicit full-heavy-graph fallback for acyclic
  ligands.
- Verify start/reference ligand agreement and generated-pose embedded-SMILES
  equivalence to the exact start-conformer chemistry.
- Emit deterministic, private, no-overwrite materialize/verify receipts,
  packaged CLI/API exports, tests, and concise evidence documentation.

## Non-goals

- Fitting or promoting a pose-ranking scorer.
- Treating PoseBusters test labels as fit or training data.
- Filling missing RCSB/Pfam target-family assignments.
- Claiming that the acyclic fallback is a standard Bemis-Murcko scaffold.
- Producing an independent external rerun or scientific-review approval.

## Likely Files Or Search Targets

- `betelgeuze_engine_v2/benchmark/public_posebusters_pose_scaffold_identity.py`
- `betelgeuze_engine_v2/benchmark/public_posebusters_pose_ranking_intake.py`
- `betelgeuze_engine_v2/benchmark/__init__.py`
- `packaging/engine-v2/pyproject.toml`
- `tests/unit/test_engine_v2_posebusters_pose_scaffold_identity.py`
- package/release workflows and Engine v2 evidence docs

## Verification

- Focused pytest, Ruff, compileall, architecture guard, YAML parse, diff check.
- Reconstruct the exact 308-case/3-engine receipt and require byte equality.
- Confirm 1,031 successful pose identities, 872 explicit failure identities,
  complete scaffold coverage, and zero source/generated chemistry mismatch.
- Build identical wheels twice and smoke the installed CLI outside checkout.

## Stop Conditions

- Follow `AGENTS.md`; do not read `.env` files or mutate external state.
- Fail closed on runtime, archive, artifact, mapping, chemistry, or row-binding
  disagreement instead of inventing an identity.

## Risk Level

R2
