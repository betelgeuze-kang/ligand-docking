# Explicit prepared Cartesian long budgets, version 3

This opt-in development route binds already prepared inputs to a new protocol and
runs the existing durable Cartesian executor. It does not prepare chemistry,
infer charges or force-field parameters, repair coordinates, select poses, or
establish docking quality. All scientific and product promotion fields remain
false. Shape penalties are **not supported** by this route.

## Admission and identities

Use `python -m betelgeuze_product.cpu_prepared_cartesian_budget_v3.workflow` from
an installed product wheel. Every operation requires explicit `--model fourier`
or `--model linear_angle`, `--accepted-steps 40|80|160`, and
`--restart-verifications 0|1`. The selected model, budget and restart allowance
must exactly match the protocol. Unknown fields and unsupported model names are
rejected. Linear harmonic angles retain their distinct evaluator and admission;
they are not converted into ordinary Fourier angle terms.

The frozen controls are one initial objective plus at most four trials per
accepted step: 161, 321 or 641 optimizer attempts, three backtracks, step size
0.001, maximum per-step atomic displacement 0.05 angstrom, force tolerance 0.001,
Armijo constant 0.0001, backtrack factor 0.5, and L-BFGS history size 10.
Restart verification is an additional, separately counted allowance. A 40-step
protocol allowing one restart admits at most 162 total force calls.

Versioned protocol/profile/result identities and the implementation-source digest
distinguish this route even when the distribution version remains 0.1.0. The
journal binds source system, exact initial coordinates, model/evaluator,
configuration, runtime environment and prepared protocol byte hash. Preparation
binds canonical absolute paths and SHA-256 hashes for the ligand, receptor,
parameters, cross parameters and declared source evidence. Every use rechecks
those bytes and original-source references. Source identity is not authenticity;
coordinate-frame authenticity and original-Hamiltonian reproduction remain false.

The existing four-step Fourier and linear-angle APIs and their 17-attempt limits
are unchanged. Historical v1/v2 long-budget archives are research artifacts, not
resumable v3 runs. Do not rewrite historical paths, update their source bindings,
reseal their protocols, or resume their journals. Copy approved input bytes into
a new location, retain their provenance, and explicitly prepare a new v3 protocol.

## Commands

Prepare a new protocol (the output must not exist):

```sh
python -m betelgeuze_product.cpu_prepared_cartesian_budget_v3.workflow prepare \
  --model fourier --accepted-steps 40 --restart-verifications 1 \
  --candidate-id example-development --evidence-kind prepared_real_development \
  --ligand /absolute/ligand.json --receptor /absolute/receptor.json \
  --parameters /absolute/parameters.json --cross /absolute/cross.json \
  --source-evidence /absolute/source_evidence.json --algorithm lbfgs \
  --output /absolute/new-protocol.json
```

Retain the returned `protocol_sha256`. `preflight` uses the same explicit model,
budget, restart and protocol options. It checks topology/geometry using one
preparation graph and zero energy/force calls; that graph is not optimizer work.

```sh
python -m betelgeuze_product.cpu_prepared_cartesian_budget_v3.workflow run \
  --model fourier --accepted-steps 40 --restart-verifications 1 \
  --protocol /absolute/new-protocol.json --expected-protocol-sha256 SHA256 \
  --run-dir /absolute/new-run --pause-after-objective-attempts 2
```

The pause occurs only after a completed journaled objective. Continue with
`resume`, the same arguments, and no pause option. The first advancing resume
re-evaluates the accepted state's full energy and forces once, charges that call
to the separate restart counter, and requires exact agreement. A zero allowance
cannot numerically resume an already evaluated running state. Repeated advancing
resumes cannot exceed the cumulative allowance.

`verify` replays retained observations without new graph/energy/force work or
changing journal bytes. Resuming a completed journal also performs zero new
objective work. Those operations are distinct from an advancing numerical resume.
The receipt's cumulative work counters describe the original run, not work done
by verification. An unfinished `objective_started` or `restart_started` reservation
is unknown work: verification/resume reject it, retain all evidence, set actual
force calls to unknown, and never automatically reissue it.

This route enforces call budgets, not a wall-clock limit. Launch it with an
external process timeout when a hard wall/CPU bound is required. Termination during
an objective may leave an unknown reservation; do not repair or retry that run.
Retain failed, rejected, incomplete and nonconverged results. Reaching a step or
objective cap is not convergence, even if energy decreased. Read `converged` and
the unchanged force threshold explicitly.

## Tests and extension boundary

`tests/unit/test_cpu_prepared_cartesian_budget_v3.py` checks strict admission,
unchanged old limits, mutation rejection, real synthetic model execution,
zero-work replay, exact safe resume and unknown-work refusal.
`tools/verify_prepared_cartesian_budget_install.py` exercises the installed CLI
outside checkout with isolated Python, 40-step direct/resumed equality and pending
objective/restart guards. The existing CPU workflow retains all prior checks and
adds this adapter and installed probe for Python 3.10/3.11/3.12.

All optimization observations and accepted checkpoint coordinates are retained by
the unchanged shared executor. Future diagnostics should verify and consume those
journal observations in a separate sidecar with separate work/source identities.
The shared executor's existing optional profile seam can support a separately
versioned future shape adapter. This v3 interface does not accept or enable shape
strengths, references or B0–B3 comparisons.
