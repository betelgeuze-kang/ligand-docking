# Explicit 600-accepted / 641-objective development profile

`betelgeuze_product.cpu_prepared_cartesian_long_budget` is an opt-in named
profile, `accepted600_attempts641/1.0.0`. It delegates preparation, source/model
validation, preflight, execution and replay to existing shared implementations.
It does not introduce another optimizer, physics model, or version folder.
Both `fourier` and `linear_angle` remain explicit and distinct model choices.

## Resource contract

- At most 600 accepted steps and 641 optimizer objective attempts, including the
  initial objective. Unlike the legacy 40/80/160 profiles, this does **not** promise
  four trial attempts for every possible accepted step. The first exhausted cap
  stops execution; failed/rejected trials consume the objective allowance.
- Exactly the original 160-step profile controls except its accepted-step ceiling:
  3 backtracks, step size 0.001, displacement limit 0.05 angstrom, force tolerance
  0.001, Armijo 0.0001, backtrack factor 0.5, L-BFGS history 10, curvature threshold
  1e-12, neighbor and cell capacities 256. Algorithms remain explicit sd or lbfgs.
- Mandatory `--restart-verifications 0|1` allows zero or one separately counted,
  cumulative restart force evaluation. Total force-call bound is 641 or 642,
  never 2401. Work counters distinguish attempted, completed, failed and unknown.
- These are logical call bounds, not wall-clock/CPU/RSS/storage quotas. Journal
  records retain every objective, rejected trial and accepted checkpoint. Use an
  external timeout/resource controller where physical limits are required. The
  existing 40-step supervisor is unchanged and does not support this profile.

A pause is safe only after a completed journaled objective. An advancing resume
checks full accepted-state energy/forces exactly, consuming the separate restart
allowance. Replay and terminal resume perform no new graph/energy/force work.
An incomplete objective_started or restart_started reservation means unknown
actual work. Verification and resume refuse it, preserve evidence and never
reissue it. actual_force_calls is unknown (null), not zero. A killed process may
leave such an unresumable reservation. Do not edit journals to recover them.

## Explicit API and CLI

Every public operation requires the profile name, model and restart allowance.
Unknown profile names, unknown model names, mismatches against the protocol,
changed inputs, implementation, runtime or fixed controls are rejected.

```sh
python -m betelgeuze_product.cpu_prepared_cartesian_long_budget prepare \
  --profile accepted600_attempts641/1.0.0 --model fourier \
  --restart-verifications 1 --candidate-id example --evidence-kind synthetic_control \
  --ligand /absolute/ligand.json --receptor /absolute/receptor.json \
  --parameters /absolute/parameters.json --cross /absolute/cross.json \
  --source-evidence /absolute/source_evidence.json --algorithm lbfgs \
  --output /absolute/new-protocol.json
```

Use the returned SHA256 with `preflight`, `run`, `resume` or `verify`:

```sh
python -m betelgeuze_product.cpu_prepared_cartesian_long_budget run \
  --profile accepted600_attempts641/1.0.0 --model fourier \
  --restart-verifications 1 --protocol /absolute/new-protocol.json \
  --expected-protocol-sha256 SHA256 --run-dir /absolute/new-run \
  --pause-after-objective-attempts 2
```

Replace run with resume and omit the pause flag to advance. Replace run with
verify to replay. Preflight omits the run directory and does zero force work.
Python callers use the same required profile/model/restart keywords;
`budget_config(algorithm, profile=..., restart_verifications=...)` freezes controls.

## Identity and migration

The new protocol, binding, result and preflight schemas are distinct. The profile
has a frozen internal definition; user JSON cannot configure a new definition.
Its implementation digest binds the new facade and the complete existing source
closure. The shared adapter refactor changes its source digest, so old source-bound
protocols must continue to be verified with their frozen source. Never reseal or
resume historical evidence with changed source. Prepare a new independent protocol
and run directory when deliberately testing new source. Legacy public defaults,
40/80/160 control meanings and schema names are unchanged; 600 is not a fourth
legacy budget choice. Frozen archives and their hashes remain untouched.

No scientific/physical qualification follows from a larger allowance or a lower
energy. All existing promotion fields remain false. Reaching a cap is not force
convergence. This profile does not enable shape penalties or establish docking
accuracy, Hamiltonian reproduction, coordinate-frame authenticity or readiness.

Tests: `tests/unit/test_cpu_prepared_cartesian_long_budget.py` covers admission,
resource accounting, safe pause/resume, pending unknown work, both models,
source/runtime guards and CLI. Original v3 tests are run without modification.
