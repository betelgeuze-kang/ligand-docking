# Current molecular development goals

These are the next work packages within the unfinished Engine V2 goal. The app
goal remains `usageLimited`; creating a replacement was refused because that
goal is unfinished. No goal was falsely marked complete. This document records
the requested priorities and observable completion criteria.

| Priority | Objective | Completion evidence | Current status |
|---|---|---|---|
| 1 | Transfer a complete, source-bound receptor chemical graph | Bond orders, aromaticity, formal charge, HIE/CYX/termini and atom mapping verified; coordinates, partial charges, masses and adjacency unchanged; unsupported states rejected | Implemented and verified on all 4,376 receptor atoms |
| 2 | Run corrected chemical scoring and the whole CPU comparison | Explicit versioned feature/scorer identities; group-wise donor/acceptor tests; actual same-candidate comparison, failure denominator, publication and replay verified | Execution and replay completed; 4/4 score rows succeeded, 0/2 requested candidates admitted |
| 3 | Improve useful D3 refinement without weakening acceptance | Fixed development protocol; initial/final independent energy-force checks; strain and convergence limits unchanged; rejection retained if limits fail | Bounded rigid experiment completed; improvement not demonstrated, NOT_ADMITTED retained |
| 4 | Remove measured redundant work and integrate | Mutation checks preserved, numerical identity demonstrated, measured cost scope stated, focused tests and exact-head draft PR updated | Optimization and 554 tests passed; installed-wheel smoke passed with shared dependencies; hosted CI remains separately pending |

Preparation, arithmetic agreement, pose recovery, candidate prioritization and
affinity are separate questions. PR49 has no observed reference pose here. The
existing geometry search is development data. Ki calibration, new training,
Fresh-128, HIP parity and service qualification are not inferred from these runs.
Old packets, failures, checkpoints and model weights remain unchanged.

Source baseline: `67b67b29d6adb8b6b45e0bdbb4773ab06457402e`. The prior case has
five-state numerical agreement and exact restart, but its direct D3 result is
unconverged with +40.0785 kcal/mol internal strain, and whole comparison is
blocked by incomplete receptor chemistry. See
[the executed report](pr49_7xtb_d3_execution_20260929.md).

The [new executed report](pr49_explicit_chemistry_execution_20260929.md) and
[hashed receipts](../evidence/pr49_explicit_chemistry_development_v1.json) narrow
the next implementation priorities:

1. **Preserve the registered input pose explicitly.** The existing generator
   recenters/rotates it and reintroduces severe overlaps. The exact registered
   pose separately passes the declared software validity checks. Completion
   requires coordinate identity, request/plan policy binding, interrupted replay,
   and a new failure-inclusive comparison. This policy is not implemented yet.
2. **Meet D3 strain and convergence criteria on that fixed input.** Rigid warm-up
   alone failed: +43.561586 kcal/mol internal increase and 67.125677 kcal/mol/Å
   force. Freeze algorithm and budget before each comparison, retain all attempts,
   and do not weaken the 5 kcal/mol or 0.001 force criteria to obtain admission.
3. **Add an independent allowed observed-pose case and enclosing cost evidence.**
   The current PR49 pose is computational and the candidate workflow lacks one
   measured wall-time scope spanning all preparation, verification and storage.
   These remain prerequisites to stronger product claims and a justified HIP
   performance decision.
