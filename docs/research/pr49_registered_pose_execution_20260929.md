# PR49 registered-pose CPU execution

The new opt-in registered-pose policy preserves the prepared ligand coordinates
through baseline scoring and the start of native D3 refinement. The actual PR49
product run selected the original candidate because the refined candidate failed
the unchanged acceptance checks. This closes a candidate-generation defect for
the narrow registered-input use case; it does not demonstrate binding-pose
recovery, affinity prediction or service qualification.

The executed implementation contains 224 source-manifest files with digest
`7e9ac15910499ea5d92ba29debd66acd179e3e270010fc78578720963bde06c0`.
The source baseline before these changes was
`28de0191b7ecd74eb16994599055a0f13e0ae8bd`.
The [evidence index](../evidence/pr49_registered_pose_development_v1.json) binds
the external run packets, complete numerical audits, plans, validation logs and
research runners by file hashes. Historical packets retain their original source
identities and failures.

## Supported behavior and request

The request schema `cpu_registered_pose_fixed_receptor_request/1.0.0` selects
`registered_input_single_pose/1.0.0`. It uses the existing explicit-chemistry
fixed-receptor fields. The supported budget is exactly one candidate, Top-1,
zero torsions, zero translation radius and `same_candidates`. Other combinations
are rejected before output publication. This is one prepared pose, not a search
around that pose. Existing generated-placement schemas retain their behavior.

The proposal receipt binds the authority, ligand identity, binary64 initial
coordinates, candidate and proposal fingerprints, frame, seed and budget. The
request, comparison plan, both arms, refinement input and resumable journal all
verify this policy. The registered proposal is not labelled as a guided placement.
Both portable verifiers reject rehashed changes to the policy, coordinates,
source-ligand claim or request/plan relationship.

The regular `run`, `run-resumable`, `verify` and `verify-resumable` product
commands accept the new schema. For this executed case, the new request is
`engine-v2-pr49-registered-policy-20260929/request.json` under the external
`ligand_heavy_runs` directory. Its SHA-256 is
`7ab82c064944d59e701206a69a01538a85ffff58f3689038a9d4f60dc5f16c17`.
Use a fresh output directory for new source or input identities.

## Actual product result

The request retains the same 39 ligand atoms, 4,376 receptor atoms, chemical
states, native force parameters and registered starting coordinates as the prior
explicit-chemistry execution. Only the request schema and proposal budget select
the new one-pose policy. The native solver remains limited to 32 accepted steps,
with maximum force 0.001 kcal/mol/Å and internal-energy increase at most 5 kcal/mol
required for admission. No tolerance was relaxed.

| Observation | Executed result |
|---|---:|
| Requested candidates / scored rows | 1 / 2 |
| Successful score rows | 2 / 2 |
| Exact initial coordinates in baseline and refinement input | Yes |
| Baseline software validity / selected variant | Valid / baseline |
| Baseline uncalibrated ordering score | 75.7944595744211 |
| Native accepted iterations / force calls | 32 / 38 |
| Initial / final total energy, kcal/mol | 399.913181390 / −96.762905418 |
| Internal-energy increase, kcal/mol | 40.078517343 |
| Final maximum tangent force, kcal/mol/Å | 37.951442082 |
| Native convergence / refined software validity | False / false |

The refined result is not admitted. Its software-validity blocker is
`bond_length_preservation_failed`, with maximum bond-length change 0.155270319 Å.
Convergence and the separate strain criterion also fail. Selection preserves the original valid
candidate; it does not turn an invalid refinement into a success. The baseline
passes the declared software checks, which is not proof of an experimentally
observed complex. The old generated-placement run had zero admitted candidates
out of two after moving the input; these different proposal policies are not an
unbiased docking-success comparison.

Source-driven OpenMM Reference checks evaluated the exact initial and final
coordinates, two requested and two passed, with the fixed absolute 1e-8 energy
and force tolerances. Maximum total-energy difference was 8.87e-12 kcal/mol;
maximum total-force-component difference was 5.21e-11 kcal/mol/Å. These checks
validate the declared mathematics at those states, not the physical model or
pose accuracy. The complete `numerical-initial-final.json` is hash-bound in the
evidence index, not just summarized as a pass count.

The enclosing run took 100.539 seconds before report publication. Nested phases
were request preparation 0.187 s, continuous product execution 91.133 s,
portable verification 0.055 s and independent numerical audit 9.066 s. These
observations exclude upstream structure preparation and human work; they are
not full service cost or a controlled performance comparison. Nested timings
must not be added to the enclosing total.

## Installed package and actual restart

A newly built wheel contains 513 package files matching the checkout and five
distribution metadata files. Its 224-file execution source manifest matches the
continuous run. All 180/181/180 owned modules observed in pause/resume/verify
come from the installed target; the separate native dependency is inventoried.
Existing dependencies were shared. This is an installed-package check, not a
clean dependency installation or external-user qualification.

The actual PR49 request was paused after committing its baseline candidate,
then resumed and independently verified through the installed CLI. With the
same runtime settings, full baseline and refined rows, every attempt field
(including checkpoint and receipt hashes), scorer identity, proposal receipt,
budgets, solver, cross parameters, paired decisions and selections match the
continuous run exactly. Baseline journal bytes are unchanged. Resume reused
one baseline with zero new baseline score or force calls, then executed one
refinement with 38 force calls and one score call.

The matched pause/resume/verify measurement is 121.978 s enclosing phase times
19.273 / 100.699 / 1.965 s. The separate earlier build/install measurements are
0.990 / 0.544 s. They do not include upstream preparation or human work.

Two validation-harness issues are retained. The first expected `report.json`
during a pause, when only the journal should exist. After that harness correction,
all numerical results matched but checkpoint hashes differed: the installed
launcher set `torch_interop_threads=1`, while continuous execution used 12.
Checkpoint identity correctly includes that runtime setting. A fresh output with
identical runtime settings produced the exact match above, without any product
code change. The unmatched run, diagnosis, original failure, and its separately
measured 175.455 s validation scope remain in the artifact index. They are not
omitted from the development history or added as nested matched-run timings.

## Separate bounded L-BFGS diagnosis

The research runner uses the exact original pose and unchanged D3 energy/force
evaluator. Before physics, it publishes a plan allowing at most 128 accepted
steps and 192 optimizer force attempts, including initial, rejected and failed
calls. History is 10, initial inverse-Hessian scale 0.001, Armijo constant 1e-4,
backtracking factor 0.5, maximum backtracks 12 and maximum atom movement 0.05 Å.
The product minimizer is not replaced by this experiment.

The run ended **NOT_ADMITTED** after 128 accepted steps and 131 force calls.
There were 130 trial steps, two Armijo rejections, no force or graph failures,
no curvature skips and no restarts. Total energy changed from 399.913181390 to
−184.710520712 kcal/mol. Final maximum force was **0.679586068 kcal/mol/Å**,
still above 0.001; internal-energy increase was **19.022436025 kcal/mol**, still
above 5. All six declared receptor-distance/radius/pocket/centroid checks passed.
Those six checks do not replace the full product bond, chirality and self-clash
validity checks, and the experiment supplies no full-product-validity claim.

Two source-driven numerical audits cover original/first-accepted and
original/final states: four evaluations and three unique states, all passing
the unchanged 1e-8 tolerances. Maximum total-energy and force-component errors
were 1.18e-11 kcal/mol and 5.21e-11 kcal/mol/Å. Oracle work is recorded separately
from the optimizer's 192-attempt bound.

The enclosing run took 508.953 s before report publication; optimizer time was
480.522 s, including 244.524 s inside native force evaluation, and the two audit
scopes were 9.356 and 9.486 s. Source guards, trial publication and other work are
included in their enclosing scopes. CPU contention was not controlled. The
32-step product run and 128-step L-BFGS run differ in algorithm and budget, so
these observations do not establish a matched-budget improvement or speedup.

This result supports testing admissibility-aware refinement next. Merely lowering
the total objective, increasing iterations or substituting an optimizer has not
yet produced a candidate meeting the retained strain and convergence limits.
A next experiment must freeze its objective, constraints, budget and convergence
definition before execution and include product geometry checks. A constrained
optimizer must report constrained stationarity explicitly rather than treating
a blocked step as unconstrained force convergence.

## Regression scope

The CPU CI test selection passed **806 tests** in 88.07 s. The required CPU
Ruff scope passed. A subsequent eight-test rerun verifies the final lint-only
cleanup; it is a subset, not eight additional distinct tests. This is not the
entire repository suite or hosted CI closure.

The new registered-pose suites contribute 29 proposal-contract tests and 27
workflow tests within those 806, covering normal execution, actual nonconverged
refinement, interruption/replay, coordinate preservation, denominator enforcement,
and rehashed receipt/request/plan tampering. Separately, 40 L-BFGS and 26 existing
rigid-experiment tests passed; their 66-test total is independent of the CPU CI
selection. An independent agent reviewed the frozen experiment and product
contracts without identifying an execution blocker.

## Qualification boundary

PR49 has no observed reference pose in this development packet. Neither a
valid baseline nor same-math agreement establishes redocking, activity ranking
or affinity. No new training data, model weights or protected Fresh-128 outcomes
were used. CPU software evidence does not establish HIP parity or speedup.

The next decisions remain tied to measured refinement admissibility, a separately
allowed observed-pose case and complete operational cost. See
[the current goals](priority_goals_20260929.md).
