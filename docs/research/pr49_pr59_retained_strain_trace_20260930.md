# Retained PR49/PR59 strain: early crossing, no admissible stored alternative

Both completed trajectories cross the unchanged 5 kcal/mol internal-energy-increase cap at objective attempt 3, the second accepted step after the initial observation. Neither accepted trajectory subsequently returns within that cap. No retained accepted state satisfies both the 5 kcal/mol strain cap and 0.001 kcal/mol/Å raw-force criterion. This is a post-hoc diagnostic from the existing 733 objective observations and two restart receipts, with zero new force, score, graph, optimizer or OpenMM calls.

| Recorded trace | PR49 | PR59 |
|---|---:|---:|
| Objective observations / rejected Armijo trials | 385 / 8 | 348 / 7 |
| Initial plus accepted states | 377 | 341 |
| First accepted crossing: objective attempt | 3 | 3 |
| Internal increase at that crossing, kcal/mol | 6.133424699 | 5.722731530 |
| Accepted states within the strain cap, including start | 2 | 2 |
| Smallest raw force among those states, kcal/mol/Å | 484.650668593 | 341.988729658 |
| Accepted states meeting both force and strain | 0 | 0 |
| Final internal increase, kcal/mol | 20.525871055 | 28.855716129 |

The [retained figure](/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-pair-retained-strain-20260930-j4qo79au/strain-force-trace.png) shows internal increase and raw-force magnitude against actual objective attempt. The accepted-state line includes the initial state; rejected trials are marked separately. The CSVs keep all completed objective observations, including all 15 rejected trials. Restart work is counted separately, not plotted as another optimizer step. Final decisions and acceptance limits remain unchanged.

Every input is checked against the sealed campaign manifest, result/meta/event seals and full event-chain/call inventory. Stored component sums and initial/final energies agree with the final result. The [new receipt](../evidence/pr49_pr59_retained_strain_trace_v1.json) pins the separate archive, source, CSVs and figure. This analysis does not recompute forces or evaluate all eight geometry checks at each trial; the separately completed final numerical and domain audits retain their original scopes.

The retained path therefore offers no acceptable earlier-step replacement. Earlier stopping at a lower-strain state would fail the unchanged force criterion; more budget is not justified by these already converged terminal states. Different prepared states, generated hydrogen positions, initial placements or pose-search policies need separate prospective inputs and budgets. The rapid cross-energy relief accompanied by internal deformation is a recorded model tradeoff, not proof of the physical cause or of failure for every other initial pose. Any flexible-receptor, solvent or restricted-coordinate objective is also a different declared model.

The next development experiment is a separately frozen nonzero-perturbation SRO pose-recovery case with observed heavy coordinates reserved for generation/evaluation only. Its known-start stability control remains separate, and it cannot establish independent general recovery, affinity, AI benefit, HIP or service qualification. These two PR traces retain their negative results and unassigned experimental roles.
