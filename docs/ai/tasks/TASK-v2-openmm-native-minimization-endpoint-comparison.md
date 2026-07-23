# TASK-ID: v2-openmm-native-minimization-endpoint-comparison

## Goal

Execute and receipt the separate OpenMM Reference L-BFGS endpoint for all 14 frozen minimization cases without claiming algorithm or trajectory equivalence.

## Scope

- Retain all eight executable and six expected fail-closed case dispositions.
- Bind the exact prior OpenMM trace materialization, runtime, mapping, protocol, inputs, atom order, parameters, and native endpoint.
- Re-evaluate every native endpoint with Engine v2 at the identical coordinates and apply the already frozen energy/force mapping thresholds.
- Reuse the frozen per-case force and constraint tolerances for endpoint health; record ungated cross-algorithm coordinate and energy deltas.
- Provide canonical mode-0600 no-overwrite materialize/verify CLI workflow and exact reexecution.
- Keep production, two-host, independent-review, algorithm-equivalence, S0/S1, chemistry, fitting, benchmark, and product claims false.

## Likely Files

- `betelgeuze_engine_v2/offline/openmm_reference_native_minimization.py`
- package exports and Engine v2 wheel entry point
- focused OpenMM runtime, packaging, release, and documentation tests

## Verification

- Frozen configuration identity and all-case coverage.
- Same-coordinate mapping, energy nonincrease, tangent-force, constraint-residual, failure-disposition, tamper, file-mode, no-overwrite, CLI, and exact reexecution tests.
- Focused OpenMM/S0 regression, Ruff, compileall, architecture guard, package build/install, and `git diff --check`.

## Stop Conditions

- Do not provision keys, execute a production authorization, invent a second host, tune thresholds after endpoint observation, or promote any scientific/product claim.

## Risk Level

R3
