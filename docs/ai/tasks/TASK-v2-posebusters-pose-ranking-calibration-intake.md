# TASK-v2-posebusters-pose-ranking-calibration-intake

## Goal

Bind the exact Vina, GNINA, and Smina 308-case PoseBusters evaluation receipts
to the RCSB/Pfam target-family receipt as test-only pose-ranking calibration
intake without inventing missing scientific identities.

## Scope

- Verify caller-pinned canonical receipt bytes and cross-receipt identities.
- Retain every case and every evaluated pose, including failure dispositions.
- Preserve engine-specific decomposed score terms, RMSD labels, and pose validity.
- Report missing per-pose coordinate, scaffold, fit-manifest, and leakage evidence
  as blockers; never materialize a fit partition or open a product claim.
- Add a packaged CLI, public exports, tests, and concise evidence documentation.

## Non-goals

- Fitting or promoting a scorer.
- Treating PoseBusters test labels as training data.
- Inventing pose/scaffold hashes or filling incomplete Pfam annotations.
- Producing an external rerun or independent-review receipt.

## Likely Files Or Search Targets

- `betelgeuze_engine_v2/benchmark/public_posebusters_pose_ranking_intake.py`
- `betelgeuze_engine_v2/benchmark/__init__.py`
- `packaging/engine-v2/pyproject.toml`
- `tests/unit/test_engine_v2_posebusters_pose_ranking_intake.py`
- package/release workflows and Engine v2 evidence docs

## Verification

- Focused pytest, Ruff, compileall, architecture guard, YAML parse, diff check.
- Reconstruct the local 308-case receipts and confirm deterministic equality.
- Build identical wheels twice and smoke the installed CLI outside the checkout.

## Stop Conditions

- Follow `AGENTS.md`; do not read `.env` files or mutate external state.
- Stop rather than synthesizing a missing identity or training/leakage claim.

## Risk Level

R2
