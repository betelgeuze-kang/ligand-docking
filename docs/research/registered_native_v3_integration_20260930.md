# Registered native-v3 source-to-execution integration

The installed native-v4 candidate runner now has an opt-in registered-pose D3
v3 path. It joins source-record chemical identity to canonical prepared inputs,
original OpenMM charge tokens, fixed receptor/method cohort, actual candidate
execution, report verification and completed-run reuse. The
[versioned contract](../engine_v2_registered_native_v3.md) describes the supported
inputs and limits. Existing v1/v2 protocols retain their behavior.

## Verified software behavior

The current change passes **255 distinct focused tests** with zero failures,
errors or skips in the final runs:

| Scope | Passed |
|---|---:|
| Native source/v1-v2 comparison/runtime profile and registered adapter | 89 |
| Registered chemistry, original XML charge and metadata-only boundary | 32 |
| Native-v3 actual source rederivation, execution, reuse and mutations | 18 |
| Existing installed comparator and read-only readiness diagnostics | 116 |

The direct runner cannot bypass preflight: two distinct Ki identities, complete
candidate requests, common method/receptor/frame/settings, source-bound stereo,
charge and initial geometry apply in both paths. Verified source denominators
survive admission failure; unknown source counts remain null. New regression
checks reject completed rows dated before their attempt, nested timing scopes
that exceed their enclosing duration, unexplained row fields and resealed
report/summary substitutions. The metadata-only descriptor validator remains
usable without importing Torch or the physics implementation.

The exact product wheel SHA-256 is
`4429c86e5e71014a720bfce4a611940f53b26e847a862cfb355a66fe0741afbd`.
All 514 Python package sources and 516 owned package files were compared with
the checkout and installed bytes. The public version-gated CLI ran outside
the checkout with isolated Python; no checkout `tools` module was imported.
Existing CPU replay dependencies were explicitly reused, so this local test
does not establish a fresh dependency installation. CI now includes a fresh
venv v3 probe; hosted completion must be checked separately against its head.

Two synthetic candidates were evaluated in all four arms. The three engine
arms made six candidate calls in total: **6 successful initial force calls,
0 failed force calls and 12 score calls**. Both molecules start at the declared
model equilibrium; refinement takes zero steps and baseline wins the selection.
These observations verify wiring, accounting and reuse, not useful iterative
refinement or pose recovery. The similarity and engine scores retain different
quantities and are never combined into an affinity score.

`verify-run` succeeded, and completed-run `resume` preserved the exact result
bytes while guards prohibited new worker, score and force calls. Scorer setup
still includes reference intraligand arithmetic. The installed probe's enclosing
CLI/check scope was 14.1024 seconds; the process including import/startup took
15.7251 seconds. The 11.6820-second run stage is nested within those scopes.
Fixture preparation, wheel build/install, dependency preparation and human work
are separate; this is not a speed comparison or end-to-end service timing.

An independent standard-library-only diagnostic read the actual installed
snapshot and confirmed its two candidates, one cohort, report denominators and
force/score counters. Its result remains `diagnostic_only`: it did not rederive
raw source chemistry, reopen molecular reports for physical verification or
perform new model fitting or molecular evaluation.

## Failed attempts and remaining requirements

The first integration fixture exposed an initial receptor/ligand overlap after
explicit hydrogen completion. After a declared synthetic receptor placement
change, the second exposed missing angle/torsion coverage; the existing force
evaluator rejected it. The final fixture supplies all topology paths, equilibrium
bond/angle terms and explicit zero torsions. No product threshold or acceptance
check was weakened. Both failed test logs remain retained. An initial installed
probe stopped at import because isolated Python correctly excluded user-site
Torch; explicit reuse of the retained CPU dependency root resolved that local
environment issue before any molecular run.

Real experimental admission remains zero. Source roles, protected evaluation
outcomes and weights were unchanged. The earlier PR49/SRO observations retain
their original source manifests and failed-refinement decisions. The preceding
529-test CPU baseline is historical evidence, not the test count for this newer
change. Independent real active/inactive contrasts, converged useful refinement,
matched scientific comparisons, full preparation-through-storage cost, HIP
parity and service qualification remain unfinished.

The [evidence index](../evidence/registered_native_v3_integration_v1.json) binds
the test records, source manifests, wheel audit, installed inputs/results,
failed attempts and independent diagnostic. The
[retained packet](/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-registered-native-v3-20260930-s46fb4ep/README.md)
also identifies the reused dependency directory that must remain available.
