# PR49 integrity guard CPU profile — 2026-09-29

The unchanged fixed-receptor integrity stage accounts for **95.74% of measured
guard wall time** in this small profile. A full guard took 0.600393 s median and
0.614014 s mean across nine measured calls. No fast path was implemented and no
speedup was measured or claimed.

The measurement packet is
[`engine-v2-pr49-integrity-profile-20260929-pk4t7m2c`](/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-pr49-integrity-profile-20260929-pk4t7m2c/profile.json).
Its [protocol](/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-pr49-integrity-profile-20260929-pk4t7m2c/protocol.json)
was published before reconstruction and measurement, fixing **one warm-up plus
nine measured calls**. The helper is
[`profile_trajectory_integrity.py`](human_5ht6_d3_complex/profile_trajectory_integrity.py).

## What was measured

The helper rebuilt the original ligand, receptor, parameters and fixed receptor
environment using the same bound completed-run plan/request. The 39-atom ligand
and 4,376-atom receptor canonical hashes, original ligand coordinate values,
native source manifest, all 18 input/source references, product solver settings,
research protocol and runtime matched the completed run. It called the existing
`feasible_step_core._Run.guard()` with the same integrity operations and order as
the runner. Objective, validity and record callbacks were prohibited sentinels
and their actual `_Run` counters remained zero.

During the original trajectory phase, the published result reference set
contained only `plan.json`. The profile reproduces its verification through
`result_refs` and its second explicit verification. It does not include the
larger result reference set accumulated later during independent numerical audits.
Every guard still freshly enumerates and hashes native source files and fully
reads and hashes the bound references; there is no stat-based digest cache.

| Disjoint stage | Median wall ms | Mean wall ms | Mean CPU ms |
|---|---:|---:|---:|
| Native source enumeration and SHA-256 | 9.427 | 10.370 | 9.772 |
| Runtime identity and protocol | 2.202 | 2.222 | 2.221 |
| 18 bound input/source references | 8.519 | 8.560 | 8.552 |
| Published result references: plan | 0.080 | 0.080 | 0.079 |
| Explicit plan reference | 0.071 | 0.075 | 0.074 |
| Original ligand canonical SHA-256 | 4.678 | 4.746 | 4.744 |
| `fixed.assert_intact()` | **575.260** | **587.862** | **587.299** |
| Wrapper remainder | 0.101 | 0.099 | 0.107 |
| **Enclosing full guard** | **600.393** | **614.014** | **612.847** |

The nine enclosing guard measurements sum to 5.526122 wall seconds. Their
disjoint stages sum to 5.525234 seconds; the remaining 0.000888 seconds includes
timer/bookkeeping overhead and the outer original-coordinate checks. Per-stage
medians need not sum to the median full guard. The enclosing guard and its nested
stages must not be added as independent work.

`fixed.assert_intact()` includes `require_system`, receptor canonical
serialization/hash, receptor parameter coverage and declared-charge checks. This
profile does **not** separately identify the cost of those internal operations.
It establishes that the combined receptor integrity stage is the first place to
investigate, not that all its time is necessarily JSON serialization. File-hash
caching is not justified by this evidence and would require a separate integrity
contract review.

## Scope and memory

Object reconstruction and baseline checks took 5.772173 wall seconds / 5.765399
CPU seconds, separately from the measured guards. Post-profile source/input
verification took 0.028957 wall seconds. All ten guards, including warm-up,
passed with zero failed integrity checks. No objective point, molecular force,
pose validity evaluation, optimizer loop, solvation evaluation or OpenMM audit
was executed. Prepared authority/configuration reconstruction is setup work, not
a new molecular result.

Sampled RSS remained 670,183,424 bytes at the guard boundaries. Linux `ru_maxrss`
reported 7,582,433,280 bytes already before object reconstruction and did not rise.
That lifetime high-water value cannot be attributed to these guard calls or used
as their incremental memory cost; between-sample allocations were not measured.
Only source/input references and small profiling records are stored in the packet.
No repository, receptor, database, weight or protected outcome payload was copied.

## Relation to the completed trajectory

The original completed trajectory recorded **575 integrity checks / 351.234835 s**
inside an enclosing 521.863784 s trajectory. The count follows from 78 points × 7
guards, eight accepted-step publications × 2, nine step-loop guards and four final
guards/publication checks. Static file sizes imply approximately 11.001 GiB of
logical content reads across those guards; that is not a physical disk-I/O
measurement because the operating-system cache was uncontrolled.

The present nine-call profile is a new guard-only measurement. Its stage
proportions are not retroactive measurements of the original 351.234835 s. The
same canonical objects and runtime do not establish equal allocator, cache,
contention or scheduler state. There is no cold-cache, end-to-end speedup,
optimization-quality, scientific or product qualification claim.

Executed once from the authoritative worktree:

```sh
PYTHONPATH=. python3.10 -B docs/research/human_5ht6_d3_complex/profile_trajectory_integrity.py \
  --plan /mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-pr49-feasible-trajectory-20260929-jsrr7nfb/run/plan.json \
  --output /mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-pr49-integrity-profile-20260929-pk4t7m2c
```

The command exited 0; the bound protocol and source/input identity checks passed.
The helper underwent a syntax compile check before this single profile run.
Existing runtime, product, core, runner, thresholds and completed-run files were
not edited.
