# PR49 exact-feasible single-step development experiment

The previous SLSQP experiment evaluated 148 points but retained no improved
incumbent: all 147 moved points exceeded the original 5 kcal/mol strain limit.
This experiment isolates the missing transition: can the unchanged native
objective take even one energy-lowering step while satisfying the exact strain,
bond and geometry requirements? It is not a full minimization, product admission,
reference-pose recovery or a matched-cost comparison against SLSQP.

## Frozen protocol

Use the same registered PR49 input, 39 ligand atoms and 4,376 receptor atoms,
source-bound unconstrained ligand XML and native internal-plus-cross objective.
Neither the product solver nor the force model changes. With original total
gradient `g0`, set `d = -g0 / max_atom_norm(g0)` and evaluate the fixed ray
`x_j = x_original + alpha_j * d`, where `alpha_j = 0.05 * 2^-j` Å and
`j = 0, ..., 15`. A zero original gradient retains the original with its own
termination reason. The maximum budget is 17 objective attempts: one original
and at most 16 trials, including failures.

Select the **first** trial satisfying all of the following, without a tolerance
cushion:

- Total energy strictly decreases and satisfies
  `E_trial <= E_original + 1e-4 * alpha_j * dot(g0, d)`.
- Internal energy increase from the original is at most 5 kcal/mol.
- Every original bond-length change is at most 0.15 Å.
- All eight product geometry checks and six separate research placement checks
  are complete and pass.

Every normally returned native objective gets a full geometry call, including
energy or strain rejections and malformed numeric outputs, unless source
integrity has already failed. Native, geometry, numeric-result and publication
failures remain separate counters and terminate the step rather than fabricating
penalty energies. An observed source-integrity failure is sticky and revokes
selection. Failure or exhaustion retains the original coordinates. There are no
subsequent optimizer iterations after a successful step.

## Independent evidence and boundaries

The plan is published before native energy/force evaluations. Source files,
request inputs, runtime, original ligand and plan are guarded throughout. The
published step, full ledger, ordered native observation identities, coordinates,
canonical output and numerical audit receipts are bound through final publication.
An explicit chronological list preserves repeated-coordinate call order even
though JSON observation maps are sorted on disk.

The fixed-state OpenMM Reference audit evaluates the original and last successful
native objective observation, including a last trial whose later geometry fails.
The one-step retained coordinates must belong to that pair: either the original,
or the last evaluated accepted trial. Direct total/internal energies and gradients
are compared at unchanged absolute 1e-8 tolerances. Evaluated and unique-state
denominators remain separate. The independent packet auditor performs no new
force calls and rederives the fixed ray, exact selection, geometry, constraints,
source bindings and cost counters from recorded observations.

Maximum raw atom force at most 0.001 kcal/mol/Å remains a separate original
condition. A feasible lower-energy state alone establishes no force convergence,
KKT stationarity or product qualification. Product chirality validation is still
the declared degree-four signed-volume subset, not comprehensive stereochemistry.
PR49 remains a computational development input with no observed reference pose.
No protected evaluation outcomes, new training labels or HIP calculations are used.

The native combined call contains one internal and one cross calculation; an
additional internal call supplies the separately audited internal gradient.
Whole execution, source guards, native calls, geometry and oracle scopes overlap
and must not be added together. Upstream preparation and human work are excluded,
and CPU contention is uncontrolled.

## Executed result

The first trial, `j=0` and nominal alpha 0.05 Å, was retained. The run stopped
immediately as planned, after two native objective points: original plus one
trial. No native, geometry, record or integrity failures occurred. This establishes
one exact-feasible energy-lowering endpoint under the frozen model.

| Observation | Original | Retained research endpoint |
|---|---:|---:|
| Total energy, kcal/mol | 399.91318138974935 | 316.0533306330546 |
| Internal increase from original, kcal/mol | 0 | 0.325376507829958 |
| Maximum original-bond change, Å | 0 | 0.032742467316107415 |
| Maximum atom force, kcal/mol/Å | 745.9826324728447 | 484.6506685932101 |
| Product / research geometry gates passed | 8/8 and 6/6 | 8/8 and 6/6 |

The decrease is 83.85985075669475 kcal/mol. The unscaled initial gradient dotted
with the fixed direction is −1930.2878514205381 kcal/mol/Å; the exact recorded
Armijo upper bound is 399.90352995049227 kcal/mol. The retained energy satisfies
both sufficient decrease and strict decrease. Strain and bond limits stay 5 and
0.15, respectively. Raw force still exceeds 0.001, so `raw_force_converged=false`
and product admission remains `NOT_ADMITTED_BY_RESEARCH_EXPERIMENT`.

Both native states are independently covered by the same-math OpenMM audit:
2 requested, 2 evaluated, 2 passed and 2 unique states. Direct total/internal
energies and gradients agree within the unchanged 1e-8 absolute bounds. The
largest recorded derivative/energy binding error is 5.213e-11. The frozen
NumPy/standard-library packet audit also passed on its first execution, verifying
the fixed direction, first-eligible selection, every geometry/constraint decision,
call counts, numerical bindings and 240 preserved source/input copies. It made
zero molecular calls. The native source digest remains
`7e9ac15910499ea5d92ba29debd66acd179e3e270010fc78578720963bde06c0`.

The main process took 35.826948067 s, including the oracle audit. Combined native
calls took 4.103979984 s; the two extra internal calls took 0.242508884 s.
The core's 18 integrity checks took 11.228980243 s inside enclosing scopes.
The oracle took 9.258241201 s and made two additional native snapshots outside
the 17-point search budget. These scopes must not be summed. This single-step
task and the earlier 128-iteration task are different workloads; their wall times
establish no optimizer speedup.

Validation covers **89 pytest tests**: 49 new core, 12 new audit-selector and
28 reused derivative/geometry checks. Core and runner Ruff scopes passed. The
49-test core receipt records completed tool output, command, exit code and source
hashes; it is explicitly not a raw redirected log. The other 40-test selection
has its raw redirected log. Independent replay has a separate nine-check
synthetic self-test, excluded from the pytest total. The actual-input setup
check deliberately stopped after publishing the plan with zero force calls.

The molecular run did not need backtracking and had no rejected trial. Shortening,
exhaustion, numerical errors, mutation and publication failure are covered by
synthetic tests, not by invented molecular attempts. This result proves endpoint
feasibility for one step; continuous-path feasibility and repeated-step convergence
remain untested. See the [evidence manifest](../evidence/pr49_feasible_step_development_v1.json)
for the complete packet, frozen audit plan, raw observations and source snapshots.

## Next completion criteria

The next research milestone is a bounded repeated-step experiment. It must keep
the **original** internal-energy and bond-length reference across all iterations;
resetting the reference after each step would permit accumulated strain beyond
the declared limit. Freeze the total native-call budget and per-step backtracking
budget before execution, retain all rejections/failures, and reuse a point only
under the identical guarded source/input/runtime context.

Completion must distinguish energy-lowering feasible steps, a blocked step,
budget exhaustion and the original raw-force convergence condition. Neither
small energy changes nor a feasible last iterate can replace the 0.001 force
criterion. Product integration, physical accuracy, affinity and HIP qualification
remain separate unfinished work.
