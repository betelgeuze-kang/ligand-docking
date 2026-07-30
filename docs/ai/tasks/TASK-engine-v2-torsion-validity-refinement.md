# TASK-engine-v2-torsion-validity-refinement

## Goal

Add one receipt-bound, fail-closed torsion-aware refinement slice after the
Engine V2 V6 rigid-clearance ensemble and measure it on historical development
data without opening the fresh holdout.

## Scope

- Diagnose remaining V6 invalid-pose checks and exact rotor availability.
- Rotate only topology-proven single-bond subtrees under deterministic bounds.
- Retain every V6 source candidate and add/select variants only by runtime-safe
  receptor/ligand geometry objectives recorded in self-hashed receipts.
- Freeze the development-selected final receptor-penalty window and restore
  exact V6 coordinates, torsions, and accepted-step accounting when it rejects
  an evaluated variant.
- Prune only selection-window states proven unreachable under the receptor
  nonincrease invariant, with receipt-bound skip/stop reasons.
- Bind candidate diagnostics to the complete refinement receipt.

## Non-goals

- No fresh holdout, active CASP17 target work, external predictor, public/native
  structure lookup, RMSD/PoseBusters-led runtime selection, or product promotion.
- No scoring redesign, broad conformer search, push, merge, or deployment.

## Likely Files Or Search Targets

- `betelgeuze_engine_v2/docking/torsion_contact_refinement.py`
- `betelgeuze_engine_v2/benchmark/public_redocking_benchmark.py`
- `tools/run_engine_v2_public_redocking_300.py`
- `tests/unit/test_engine_v2_element_contact_round8.py`
- `tests/unit/test_engine_v2_public_redocking_runner_stage7.py`

## Verification

- Focused refinement, receipt, runner, and benchmark-contract pytest suites.
- `./scripts/ai-verify.sh` and `git diff --check`.
- Historical-development V6 A/B with failure-inclusive denominators.
- Actual final-code rerun of every case affected by the frozen selection window.

## Stop Conditions

- Stop if exact movable subtrees cannot be derived without ambiguous chemistry.
- Do not claim improvement unless V6 aggregate validity/RMSD is non-regressed.
- Preserve unsupported typed failures and all CASP/no-leak boundaries.

## Risk Level

R2
