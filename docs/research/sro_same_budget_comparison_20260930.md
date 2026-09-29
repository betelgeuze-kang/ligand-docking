# SRO same-budget SD/L-BFGS comparison: launch observation

A separately reviewed v2 research comparison was launched once on the retained
SRO input. The [launch evidence](../evidence/sro_same_budget_comparison_launch_v2.json)
records the observed live wrapper/SD processes and immutable protocol/review
references. This document records launch, not final results; current progress
and termination belong to the retained run packet.

The SD first-51-observation reproduction gate has subsequently passed exactly,
including the earlier 32-step endpoint. Its immutable receipt is linked by the
launch evidence. The extended comparison still has no final result at this
publication; successful prefix reproduction does not establish convergence.

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
