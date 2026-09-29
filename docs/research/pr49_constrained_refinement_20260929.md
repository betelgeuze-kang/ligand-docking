# PR49 strain and bond constrained refinement

This development experiment asks whether the existing fixed-receptor objective
can improve the registered pose while retaining the declared internal-energy
and bond-length limits. It uses the original input and native force model;
the product solver, source digest and raw-force convergence requirement do not
change. A constrained stationary point is a separate observation, not an
unconstrained product-refinement success.

The bounded run completed with **no eligible incumbent update**. SLSQP reached
its 128-iteration limit after 148 native objective points. Every moved point
exceeded the exact strain bound; the original pose was retained. This closes
the declared experiment, not the useful-refinement goal.

## What the previous result establishes

The prior registered 32-step product refinement fails bond preservation, strain
and force convergence. Its 128-step L-BFGS successor had only six placement
checks recorded at execution. A new retrospective adapter audit now evaluates
all eight existing product geometry gates directly from those preserved
coordinates, without scoring or force calculations.

The L-BFGS final state passes all eight gates, with maximum original-bond change
0.123309526 Å below the fixed 0.15 Å bound. The baseline and 32-step product
validity documents are reproduced exactly. L-BFGS still fails the independent
strain and force conditions: +19.022436025 kcal/mol and 0.679586068 kcal/mol/Å.

Existing source-audit components attribute that strain increase to bonds
+21.974910, angles +7.022709, proper torsions +9.627672, star impropers +1.819030,
Lennard-Jones +0.373285 and Coulomb −21.795169 kcal/mol. Independent NumPy bond
distances and harmonic-bond sums corroborate these values. This decomposition
motivates explicit strain control; passing a maximum bond-displacement gate
alone does not bound the aggregate internal energy.

Product geometry includes proper rotation, original bond lengths, ligand
self-clashes, receptor clashes, declared signed-volume chirality, the declared
pocket and two element-based van der Waals overlap checks. Its chirality check
covers the declared degree-four signed-volume subset, not comprehensive E/Z,
CIP, ring or planarity validation. The separate six research placement checks
retain their own stricter all-pair distance/radius/pocket/centroid limits.

## Frozen experiment

The native objective remains internal plus receptor-cross energy. SciPy 1.12.0
SLSQP receives the objective and its analytic gradient divided by 1000 as an
explicit numerical scaling. No penalty energy is added and no force is replaced.
The constraints, written as nonnegative normalized slacks, are:

```
c_strain = (5 - (I(x) - I(original))) / 5
c_bond_lower = (0.15 + (distance(x) - distance(original))) / 0.15
c_bond_upper = (0.15 - (distance(x) - distance(original))) / 0.15
```

Every original bond has both bounds. The analytic strain derivative uses the
negative native internal force, separately recovered from `ExtendedEvaluator`.
The plan declares 128 SLSQP iterations, 192 distinct objective-point attempts
including failures, `ftol=1e-10`, no artificial coordinate box and no inherited
0.05 Å L-BFGS step cap. This is a different step policy and budget allocation,
not a matched algorithm performance comparison.

All completed native trials receive full product and research geometry checks.
Infeasible trials retain the true objective and remain in the ledger; they are
not replaced with fabricated penalty forces. Exact-coordinate cache hits reuse
their observations only within the guarded, fixed source/input/runtime context.
The retained result is the last fully feasible callback-observed or independently
validated terminal state whose objective does not exceed the original value.
All admission inequalities are exact, without a tolerance cushion.

SciPy's callback can occur before line-search acceptance. Consequently the
ledger calls it a **major-iteration observation**, not an accepted step. The
SciPy success flag is not sufficient for candidate eligibility or force
convergence. This distinction follows the
[SciPy 1.12 implementation](https://raw.githubusercontent.com/scipy/scipy/v1.12.0/scipy/optimize/_slsqp_py.py);
its [`ftol` option](https://docs.scipy.org/doc/scipy-1.12.0/reference/optimize.minimize-slsqp.html)
is an optimizer stopping parameter, not the product's atom-force criterion.

## Independent stationarity and arithmetic checks

The KKT diagnostic uses the unscaled total gradient. Constraint rows with
normalized slack at most 1e-6 define the active set. A nonnegative least-squares
fit obtains multipliers for `gradient - J.T @ multiplier`. The declared tests
are exact primal feasibility, nonnegative multipliers, maximum atom norm of
that residual at most 0.001 kcal/mol/Å, and maximum complementarity product at
most 1e-6 kcal/mol. The
[nonnegative least-squares problem](https://docs.scipy.org/doc/scipy-1.12.0/reference/generated/scipy.optimize.nnls.html)
and residual are recorded explicitly; a failed fit is not stationarity.

This KKT scope contains the strain and original-bond constraints only. Product
geometry is an independent eligibility filter and contributes no hidden
constraint normals. Raw maximum atom force at most 0.001 remains a separate
original requirement. Passing KKT with a larger raw force can only establish
`CONSTRAINED_STATIONARY_ONLY`, while product admission remains unresolved.
Such a local observation cannot prove that every feasible starting pose lacks
an unconstrained stationary solution.

Source-driven OpenMM Reference audits cover original, first retained incumbent
if any, and final retained coordinates. Both total and internal energies and
gradients are checked directly against the native and independent reference
states at absolute 1e-8. This also validates the derivative used for the strain
constraint. Inputs, runner, core, adapter, helpers, oracle, runtime and plan are
guarded; a recorded integrity failure remains fatal even if bytes are restored.

## Executed result

The experiment used the same 39 ligand and 4,376 receptor atoms. The product
source manifest still contains 224 files with digest
`7e9ac15910499ea5d92ba29debd66acd179e3e270010fc78578720963bde06c0`.
Its original, retained and rejected terminal states must remain distinct:

| Observation | Original and retained result | Last native trial, rejected |
|---|---:|---:|
| Total energy, kcal/mol | 399.913181390 | −180.739883714 |
| Internal increase from original, kcal/mol | 0 | 5.000032510069104 |
| Maximum original-bond change, Å | 0 | 0.105612135 |
| Maximum atom force, kcal/mol/Å | 745.982632473 | 47.337095201 |
| Product geometry / research placement | 8/8 and 6/6 | 8/8 and 6/6 |
| Exact strain bound ≤5 | Pass | Fail |
| Original raw-force bound ≤0.001 | Fail | Fail |

All 148 objective-point attempts completed, with no native or geometry-call
failures. Full geometry passed at 135/148 points, but only the original point
met the exact strain and all normalized primal constraints. There were 536
coordinate-cache reuses, 128 major-iteration observations and zero incumbent
updates. The terminal point was independently assessed and rejected. SciPy
returned status 9, `Iteration limit reached`, with `success=false`.

The retained original pose has no active strain/bond constraints and a KKT
maximum atom residual of 745.982632473 kcal/mol/Å. It is `NOT_STATIONARY`.
Neither constrained stationarity nor product force convergence was obtained.
The low energy of the rejected trial is not an admitted product improvement.

The frozen run's original/final numerical audit passed 2/2 evaluations at
1e-8, but those evaluations cover **one unique state**, because the original
was retained. A separately planned postexecution diagnostic therefore audited
the original and deterministic last completed trial. That diagnostic passed
2/2 evaluations across two unique states, directly binding the optimizer's
total/internal energies and gradients to OpenMM Reference. The largest of
those direct absolute errors was 5.213e-11. Across both audits there are four
evaluations but only two unique states; intermediate trial energies/forces
were not all independently recomputed. The supplemental diagnostic adds no
optimizer steps and changes no admission decision.

An independent NumPy/standard-library audit, without importing the product
geometry or constrained optimizer, checks all recorded trial geometry,
constraint values/Jacobians, retained-state lineage, counters and KKT receipt.
Its source, declared audit plan, outcome and source snapshots are indexed with
the immutable raw run in
[the evidence manifest](../evidence/pr49_constrained_refinement_development_v1.json).
It passed with zero additional force calls and verifies 239 frozen copies
(224 native files and 15 input/source references). Intermediate constraint
reconstruction uses the recorded internal gradients; independent force arithmetic
coverage remains limited to the original and point 148.

The enclosing main process took 1,443.379 s, including the frozen run's oracle
audit. Its 148 combined native calls took 280.351 s; the 148 extra internal-force
calls took 17.575 s. The core's 1,795 integrity checks accumulated 1,102.820 s
inside several enclosing scopes. These timers overlap and **must not be summed**.
The separate last-trial diagnostic took 10.898 s, with two additional native
snapshots. This exposes source-integrity overhead as a substantial cost in this
guard-heavy research harness, not evidence of a product CPU/GPU speedup.

## Next completion criteria

The next research step should retain exact feasibility during trial selection,
with a bounded feasible-step/backtracking strategy on the unchanged objective.
Freeze its algorithm, budget and strict inequalities before a new run; first
exercise a synthetic nonlinear constraint where an infeasible full step must
be shortened or rejected. A useful result must actually retain a lower-energy
pose that passes the same full geometry and strain checks. Keep rejected steps,
all feasibility evaluations and their cost in the denominator. This is a new
research protocol, not a repair of this completed negative result.

The proposed first milestone is deliberately one step: normalized negative total
gradient, maximum per-atom direction norm 1, fixed Armijo backtracking with
alpha = 0.05 × 2^-j Å for j = 0 through 15, and first exact-feasible sufficient
decrease retained. All trial costs and a 16-trial exhaustion must be explicit;
the final Armijo constant and complete protocol still need freezing before use.
This proposal is **unexecuted**. It does not claim a feasible result or convergence.

Product adoption additionally needs the original force-convergence condition;
a feasible or constrained-stationary research pose cannot substitute for it.
This single starting pose and finite budget do not prove that no feasible
unconstrained stationary point exists. Reducing repeated source-hash overhead
also needs its own mutation-detection tests and scoped before/after measurement;
do not remove those checks merely to accelerate the next experiment.

## Validation and operational scope

The new constrained core passes 58 synthetic tests, including analytic boundary
optima, nonzero raw force at a KKT stationary point, finite-difference Jacobians,
tiny negative-slack rejection, callback/terminal retention, failed evaluations,
the 192-attempt budget, cache behavior and source mutation. The product geometry
adapter passes 18 tests; ten runner tests reject independent energy/gradient or
coordinate mismatches. These **86** tests are distinct from the previous CPU
CI selection of 806; the latter was not rerun or relabelled as a new full-suite
result. An actual-input setup check deliberately stopped after plan publication
and before any force call, preserving its intentional-stop record.

The external supplemental receipt verifier first failed on a 5.684e-14
floating-point summation-order discrepancy in its receipt-identity comparison.
The corrected verifier retains the independent 1e-8 derivative check and
separately reproduces the report summation order with exact comparison. Both
verifier versions and the failed receipt remain in the audit bundle; the main
and supplemental numerical files and all scientific thresholds are unchanged.

Each completed native point uses one combined evaluator call and one additional
internal evaluator call to recover the constraint derivative. The combined call
already contains an internal and a receptor-cross evaluation; these nested calls
must not be double-counted as separate enclosing cost. The extra internal calls,
source guards, geometry checks, cache requests, trial publication and oracle work
are measured separately. Oracle evaluations are outside the optimizer's point
budget. The enclosing measurement excludes upstream preparation and human work;
CPU contention is not controlled.

The implementation is research-only. It does not admit training data, touch
Fresh-128 outcomes, replace the product minimizer, establish an observed PR49
pose, validate affinity or qualify service/HIP performance. The final packet and
independent postexecution audit are indexed in the accompanying evidence file.
