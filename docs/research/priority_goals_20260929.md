# Current molecular development goals

These are the next work packages within the unfinished Engine V2 goal. The app
goal remains `usageLimited`; creating a replacement was refused because that
goal is unfinished. No goal was falsely marked complete. This document records
the requested priorities and observable completion criteria.

| Priority | Objective | Completion evidence | Current status |
|---|---|---|---|
| 1 | Transfer a complete, source-bound receptor chemical graph | Bond orders, aromaticity, formal charge, HIE/CYX/termini and atom mapping verified; coordinates, partial charges, masses and adjacency unchanged; unsupported states rejected | Implemented and verified on all 4,376 receptor atoms |
| 2 | Preserve the prepared input and complete the CPU comparison | Explicit registered-pose request/plan, exact initial coordinates, normal and installed pause/resume agreement, failure denominator and verification | Implemented; actual one-pose/two-row execution and exact installed replay passed; valid baseline retained |
| 3 | Improve useful D3 refinement without weakening acceptance | Fixed development protocol; independent energy-force checks; strain and convergence limits unchanged; rejection retained if limits fail | Rigid and bounded L-BFGS experiments completed; both NOT_ADMITTED; useful refinement remains unresolved |
| 4 | Remove measured redundant work and integrate | Mutation checks preserved, numerical identity demonstrated, measured cost scope stated, focused tests and exact-head draft PR updated | CPU CI selection 806 passed; separate research selection 66 passed; installed actual-case restart passed with shared dependencies; hosted CI separately pending |

Preparation, arithmetic agreement, pose recovery, candidate prioritization and
affinity are separate questions. PR49 has no observed reference pose here. The
existing geometry search is development data. Ki calibration, new training,
Fresh-128, HIP parity and service qualification are not inferred from these runs.
Old packets, failures, checkpoints and model weights remain unchanged.

Historical source baseline: `67b67b29d6adb8b6b45e0bdbb4773ab06457402e`. That prior case had
five-state numerical agreement and exact restart, but its direct D3 result is
unconverged with +40.0785 kcal/mol internal strain, and whole comparison is
blocked by incomplete receptor chemistry. See
[the executed report](pr49_7xtb_d3_execution_20260929.md).

The [explicit-chemistry report](pr49_explicit_chemistry_execution_20260929.md)
identified the placement defect. The
[registered-pose execution](pr49_registered_pose_execution_20260929.md) and
[hashed receipts](../evidence/pr49_registered_pose_development_v1.json) record
the implemented fix and narrow the remaining priorities:

1. **Preserve the registered input pose explicitly.** The existing generator
   recenters/rotates it and reintroduces severe overlaps. The exact registered
   pose separately passes the declared software validity checks. Completion
   required coordinate identity, request/plan policy binding, interrupted replay,
   and a new failure-inclusive comparison. **Completed for the explicit one-pose
   support boundary**, including exact installed-package restart. Existing
   generated-search policies retain their behavior.
2. **Meet D3 strain and convergence criteria on that fixed input.** Rigid warm-up
   alone failed: +43.561586 kcal/mol internal increase and 67.125677 kcal/mol/Å
   force. Freeze algorithm and budget before each comparison, retain all attempts,
   and do not weaken the 5 kcal/mol or 0.001 force criteria to obtain admission.
   L-BFGS on the original pose completed 128 accepted steps and 131 force calls,
   ending with +19.022436 kcal/mol strain and 0.679586 kcal/mol/Å force: still
   **NOT_ADMITTED**. Next freeze an admissibility-aware experiment including
   product bond/chirality/self-clash checks and an explicit stationarity definition.
   Algorithm and budget changed together here; a matched-budget benefit remains
   unproven. Do not substitute this research optimizer into the product yet.
3. **Add an independent allowed observed-pose case and enclosing cost evidence.**
   The current PR49 pose is computational. New enclosing execution/restart/audit
   measurements exist, but exclude upstream structure preparation and human work;
   a complete preparation-through-storage service measurement remains absent.
   These remain prerequisites to stronger product claims and a justified HIP
   performance decision.
