# SRO same-budget SD/L-BFGS comparison: completed development result

A separately reviewed v2 research comparison was launched once on the retained
SRO input. The [launch evidence](../evidence/sro_same_budget_comparison_launch_v2.json)
records the original live wrapper/SD processes and immutable protocol/review
references. That launch snapshot remains unchanged. Both arms subsequently
completed under the original protocol; the
[completed evidence](../evidence/sro_same_budget_comparison_completed_v2.json)
links their final records and independent review.

The SD first-51-observation reproduction gate has subsequently passed exactly,
including the earlier 32-step endpoint. Its immutable receipt is linked by the
launch evidence. Successful prefix reproduction establishes continuity with the
earlier run; the extended outcomes below establish the new development result.

| Recorded outcome | SD | L-BFGS |
|---|---:|---:|
| Objective attempts, common cap 417 | 417 | 253 |
| Accepted steps / rejected Armijo trials | 262 / 154 | 244 / 8 |
| Failed objective calls | 0 | 0 |
| Final model energy, kcal/mol | -31.250187383 | -37.411370307 |
| Final separate dimensionless ordering score | -19.814099982 | -18.857554318 |
| Final maximum atom force, kcal/mol/angstrom | 5.864118662 | 0.000950270044 |
| Internal energy change, kcal/mol | -14.143277885 | -15.070364673 |
| Maximum bond-length change, angstrom | 0.104102108 | 0.095908975 |
| Scoped geometry checks | 8/8 | 8/8 |
| Independent initial/final numerical states | 2/2 | 2/2 |
| Decision | NOT_ADMITTED; baseline | DEVELOPMENT_CRITERIA_MET; refined |
| Observed process wall seconds | 1640.892502 | 1006.377267 |

The initial model energy is 14.798201989 kcal/mol and maximum atom force is
128.436473563 kcal/mol/angstrom. L-BFGS meets every original acceptance condition
and stops on force convergence. SD exhausts its objective budget and fails only
the force-convergence condition. This gives one observed-pose development case
with useful converged refinement in this fixed model. It does not establish
general algorithm superiority or install L-BFGS into the product optimizer.
Both ordering scores improve from -16.649148980. SD has the lower final ordering
score but fails force convergence; L-BFGS has the lower model energy. These
quantities answer different questions and cannot be merged into an affinity or
pose-quality ranking.

All 670 objective calls (1,340 start/finish records) retain full 26-by-3 trial
coordinates and returned force arrays. Four endpoint states pass the same-math
OpenMM checks and direct stored-energy/component/full-force binding at 1e-8
tolerances. Four score calls, four native oracle snapshots and 38 OpenMM oracle
observations are accounted separately from the 670 optimizer calls. The
independent completed-pair review passes 41 checks with no result discrepancy.

The common upper bound does not imply equal work: L-BFGS uses 253 calls and SD
uses 417. Predeclared milestones after L-BFGS termination (256, 384 and 417) are
unobserved, not zero cost or extrapolated states. The descriptive
[trajectory figure](/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/sro-same-budget-analysis-20260930-pc7po8p4/sro-same-budget.png)
and retained CSV stop each arm where it actually terminates.

The enclosing wrapper takes 2647.819838 seconds, including preflight, both arms,
geometry/score, numerical checks, summary and postflight. Nested objective and
force timings are not added again. Historical preparation, installation, review
and human work are excluded. The wrapper's absolute child user-CPU reading is
0.001263 seconds larger than the two arm deltas; the original child baseline was
not recorded, so this small residual is preserved with unknown provenance.
SD runs first on a shared host, and dependency bootstrap overlaps L-BFGS at
18:11:15-18:11:33 UTC. These are observed costs, not causal speedup evidence.

The observed heavy-atom starting pose has zero initial reference RMSD. Final
direct receptor-frame heavy-atom displacement is 0.260658 angstrom for SD and
0.476749 angstrom for L-BFGS. These are drift measurements, not pose-recovery
successes. Energies are not affinity predictions. The original chemical state
and dry fixed-receptor model limit physical interpretation.

Both arms use the original 224-file installed CPU evaluator, original chemical
state, coordinates, parameters and initial pose. The current checkout's 225-file
implementation scope is separately pinned context; it is not imported as the
historical runtime. The new registered binding fix is independent of this run.

SD runs first, then L-BFGS in a fresh process. Each arm has at most 417 objective
attempts including rejected/failed attempts, with 416 accepted-step capacity.
The operational watchdog is 7200 seconds per arm. This was fixed before launch
using the historical 51-call cost: simple full-run scaling is about 4421 seconds;
a 3600-second watchdog had insufficient margin. This is a common time ceiling,
not a prediction or assertion of equal actual work.

SD's first 51 observations must exactly reproduce the old trajectory. Initial
and every attempted coordinate are durably journalled, with full returned force
arrays. Endpoints receive the original independent OpenMM checks; a new pure
array comparison also connects the optimizer's own endpoint energy/components/
forces to both oracle outputs without extra molecular evaluations. Oracle and
score work are recorded separately from the optimizer budget.

Force 0.001 kcal/mol/angstrom, internal-strain increase 5 kcal/mol, bond-change
0.15 angstrom and all eight geometry checks remain unchanged. A refined state
also requires successful numerical checks and improved dimensionless ordering
score. The last accepted state is evaluated; there is no retrospective best-state
selection. A fatal arm or watchdog stops the pair with no automatic retry and
records unstarted arms and unknown partial work. Source roles, protected data,
weights and assay admission remain unchanged. One input cannot qualify general
algorithm performance, pose recovery, affinity, HIP or service readiness.

[Retained protocol and run packet](/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-sro-sd-lbfgs-comparison-20260930-v2/README.md)
