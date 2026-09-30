# PR49 bounded repeated feasible descent

The frozen development run retained **8 steps from 78 native points** and
stopped because the next step had no eligible trial in the declared backtracking
range. It preserved the original strain and bond references, but **did not meet
the raw-force criterion**. The result remains `NOT_ADMITTED`.

| Observation | Original | Retained attempt 62 | Requirement |
|---|---:|---:|---|
| Total energy, kcal/mol | 399.913181390 | 255.967225980 | Strict current-incumbent decrease and Armijo |
| Internal increase from original, kcal/mol | 0 | 4.999753054 | At most 5, without tolerance relaxation |
| Maximum original bond-length change, Å | 0 | 0.065451138 | At most 0.15 |
| Maximum atom force, kcal/mol/Å | 745.982632473 | 340.269183195 | At most 0.001; **not met** |

All 78 normally returned native points received the unchanged eight product and
six placement geometry checks and passed them. All 69 rejected points failed the
strain limit. There were zero failed objective calls, invalid objective results,
failed geometry calls, or observed source-integrity failures. The retained
coordinates are the last successfully published accepted state, not the final
rejected attempt 78.

## Protocol and implementation

The protocol was declared before molecular evaluation in
[predeclaration.json](/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-pr49-feasible-trajectory-20260929-jsrr7nfb/predeclaration.json).
It allows at most 32 accepted steps, 16 backtracking trials per step, and 129
native point attempts including the original, failures and rejections.
Each step uses the current accepted negative total gradient normalized by the
maximum atom norm, with alpha = 0.05 × 0.5^j Å for j = 0…15 and Armijo c1 = 1e−4.
The first eligible trial is selected. The strain and bond references always
remain the initial original; only the Armijo energy reference moves.

The shared single-point pipeline gained an optional current Armijo base, retaining
its former default. The new trajectory commits an incumbent only after its
selection publication succeeds. Ordinary callback failure keeps the last such
incumbent; a source-integrity failure revokes trusted selection to the original.
Small changes, a tiny step or blocked backtracking cannot count as convergence.
The product optimizer and admission rules were not changed.

The runner records every native callback in attempt order, including repeated
coordinates and failures. A malformed normally returned numerical result is
preserved as an explicitly tagged diagnostic while the full geometry callback
still executes. Published JSON is immediately bound to its intended bytes.
Invalid or incomplete final geometry prevents a normal result report.

## Independent checks and coverage

An offline auditor, which imports neither the optimizer nor molecular evaluators,
reconstructed all 78 decisions, the current gradient rays/Armijo bounds,
immutable original references, first-eligible selections, publication chain,
budgets and retained state. External JSONL and chronological native observations
were bound. Objective, geometry, publication and accepted-step denominators are
checked exactly; integrity counts are checked as lower bounds. Geometry verdicts
are bound from the execution, not independently recomputed by this ledger audit.

The independent OpenMM Reference same-math comparisons cover **10 unique states**:
the original, all 8 committed endpoints, and the last completed native point.
Nine original/endpoint pairs give **18/18 passing snapshots**, including repeated
original evaluations. Maximum checked energy error was 1.478e−11 kcal/mol and
gradient-component error was 5.213e−11 kcal/mol/Å, below the unchanged 1e−8
numerical thresholds. These checks compare the declared mathematical model;
they do not establish its physical accuracy.

The other **68 rejected intermediate points were not independently numerically
reevaluated**. They remain in the native and geometry denominators and decision
audit. They must not be described as 78 OpenMM-validated states.

One combined focused test invocation passed **231 tests** on Python 3.10,
including the existing single-step contracts, repeated-step invariants,
manual-ledger tampering, failure/retention paths, final geometry failure,
NaN/Inf recording, publication mutation and workflow trust boundaries. These
counts overlap earlier reports and are not additive. The analytical suite is
now included in the local-research CI workflow; hosted completion is separate
from this local result.

## Measured cost and preservation

The completed child process took **628.979 s** including its report output.
The trajectory occupied 521.864 s; its source-integrity callbacks accounted for
351.235 s. Combined force evaluation occupied 149.971 s over 78 calls, and the
additional internal evaluations 9.237 s over 78 calls. Nine independent paired
audits occupied 83.807 s. These scopes are nested and must not be summed.
CPU contention was uncontrolled. Upstream preparation, human effort, clean
installation, and post-run review are excluded; this is not a service-wide cost
or matched-budget speedup result.

Native product source remains 224 files with manifest
`7e9ac15910499ea5d92ba29debd66acd179e3e270010fc78578720963bde06c0`.
The packet contains 255 selected code/test/workflow files totaling 7.118 MiB,
instead of another whole-repository copy. Original requests, parameters and XML
are retained at their source-bound paths. Prior packets and protected evaluation
data were not modified. This research trajectory is not a new installed product
entrypoint or a proof of interrupted trajectory resume.

## Development consequence

This run answers whether repeated exact-feasible improvements can be retained:
yes, within this case and frozen protocol. It also shows that repeatedly shrinking
the current negative-gradient ray reaches the strain boundary while force remains
large. It does not prove that other feasible directions or starting poses cannot
improve, nor does it establish constrained stationarity.

The next refinement experiment needs a separately frozen strategy for feasible
directions near a constraint boundary, with independent arithmetic checks and
the original force/strain rules preserved. Increasing the same iteration budget
alone is not supported by this blocked-step result.

In parallel, prioritize the source-linked
[7XTB observed serotonin pose](7xtb_observed_pose_readiness_20260929.md) as a
separate development case after its microstate and preparation are explicit.
It supplies an observed heavy-atom reference that PR49 lacks. Neither case
clears experimental source roles, demonstrates affinity prediction, proves
AI prioritization benefit, or qualifies HIP or customer service.

Evidence: [summary](/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-pr49-feasible-trajectory-20260929-jsrr7nfb/summary.json),
[execution report](/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-pr49-feasible-trajectory-20260929-jsrr7nfb/run/report.json),
[trajectory plot](/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-pr49-feasible-trajectory-20260929-jsrr7nfb/trajectory.png),
and [repository evidence index](../evidence/pr49_feasible_trajectory_development_v1.json).
