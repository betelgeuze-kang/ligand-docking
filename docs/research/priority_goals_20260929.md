# Current molecular development goals

These are work packages within the five unfinished Engine V2 goals. The live
app goal was rechecked as `active` on 2026-09-29; the earlier `usageLimited`
observation is historical. No replacement goal or smaller completion definition
is used. The five requirements remain:

| Goal | Evidence still required for completion | Current boundary |
|---|---|---|
| 1. Source-linked human-target inputs and experimental endpoints | Prepared chemistry and comparable active/inactive endpoints with explicit, independently cleared train/calibration/evaluation roles | Human 5-HT6 source review and computational PR49 preparation exist; no newly admitted fit/calibration/evaluation rows |
| 2. Preparation quality and numerical validity | Contact, completeness, stereochemistry, charge and same-math checks; execution separated from eligibility | PR49 and a separately prepared observed-coordinate SRO development case have explicit chemistry and numerical observations; SRO passes four fixed same-math states and initial scoped geometry checks, without raw-force or pose-recovery qualification |
| 3. Similarity/native/native+AI comparison | Same eligible candidates, declared compute budget, all requested/failing candidates, independently interpreted outcomes | Registered-pose software execution/restart is verified within a narrow support boundary; scientific matched comparison is incomplete |
| 4. Integrity-preserving CPU efficiency | Equivalent results and mutation detection with enclosing measured cost | Deferred diagnostic formatting retains both fresh integrity passes; four-state SRO full outputs match with evaluation mean 6.18% lower, and the receptor integrity guard mean is 2.62% lower; full preparation-through-storage cost and broader throughput remain unproved |
| 5. Integrated reproducible baseline | Compatible implementation, installed execution/restart/report, exact-source verification and preserved historical work | Integrated local baseline and narrow installed replay exist; all five end-to-end requirements are not complete |

The work-package priorities below do not replace these five goals.

| Priority | Objective | Completion evidence | Current status |
|---|---|---|---|
| 1 | Transfer a complete, source-bound receptor chemical graph | Bond orders, aromaticity, formal charge, HIE/CYX/termini and atom mapping verified; coordinates, partial charges, masses and adjacency unchanged; unsupported states rejected | Implemented and verified on all 4,376 receptor atoms |
| 2 | Preserve the prepared input and complete the CPU comparison | Explicit registered-pose request/plan, exact initial coordinates, normal and installed pause/resume agreement, failure denominator and verification | Implemented; actual one-pose/two-row execution and exact installed replay passed; valid baseline retained |
| 3 | Improve useful D3 refinement without weakening acceptance | Fixed development protocol; independent energy-force checks; strain and convergence limits unchanged; rejection retained if limits fail | Repeated run retained 8 steps / 78 points, strain +4.999753 and bond change 0.0654511 Å; blocked at the strain boundary with force 340.269; NOT_ADMITTED |
| 4 | Remove measured redundant work and integrate | Mutation checks preserved, numerical identity demonstrated, measured cost scope stated, focused tests and exact-head draft PR updated | Canonical normalization now defers diagnostic-path construction while retaining fresh traversal and both digests; controlled fixed-state SRO evaluation has 18/18 completed attempts and exact full outputs. Current-source regression and installed replay evidence is tracked in the CPU normalization report; hosted completion is separate |

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
   **NOT_ADMITTED**. A retrospective audit now confirms all eight product geometry
   checks pass for that L-BFGS state; the strain and force failures remain.
   The subsequent [strain/bond-constrained experiment](pr49_constrained_refinement_20260929.md)
   includes all eight product and six research geometry gates plus an explicit
   independent KKT diagnostic. Its 128-iteration/148-point run produces no eligible
   update: terminal strain is 5.000032510069104 and force is 47.337095201. The
   original pose remains retained, with neither raw-force nor KKT convergence.
   The subsequent [single feasible-step experiment](pr49_feasible_step_20260929.md)
   completed that narrow transition: its first 0.05 Å trial reduced total energy
   from 399.913181390 to 316.053330633 while meeting exact strain/bond and all
   8+6 geometry gates. Both native states passed independent arithmetic checks.
   Its force remains 484.650668593, so no product refinement is admitted.
   The [bounded repeated-step execution](pr49_feasible_trajectory_20260929.md)
   retained eight steps from 78 points and stopped on blocked backtracking. All
   69 rejected points exceeded the original strain limit. Ten unique states
   passed independent same-math checks; final force 340.269 still fails admission.
   The next protocol must address feasible directions at a constraint boundary;
   this finite negative-gradient-ray search does not prove constrained stationarity.
   Algorithm and budget changed together; a
   matched-budget benefit remains unproven. Do not substitute research optimizers
   into the product. Repeated integrity checks are a measured research-harness
   cost; optimize them only with mutation detection preserved.
3. **Add an independent allowed observed-pose case and enclosing cost evidence.**
   The current PR49 pose is computational. New enclosing execution/restart/audit
   measurements exist, but exclude upstream structure preparation and human work;
   a complete preparation-through-storage service measurement remains absent.
   These remain prerequisites to stronger product claims and a justified HIP
   performance decision.

The [2024 source-lineage review](human_5ht6_2024_source_lineage_20260929.md)
now separates binding Ki references from functional KB/EC50 and records 78
printed test IDs. It is a blocked review, not a new full preflight or admission.
The [observed-pose readiness audit](7xtb_observed_pose_readiness_20260929.md)
identifies serotonin/SRO with 13 observed heavy atoms and verifies 2,124 shared
receptor coordinates. A separate [SRO preparation and numerical execution](sro_numerical_validation_20260929.md)
now preserves those heavy coordinates with a declared NZ+1 computational state,
13 generated hydrogens and complete unconstrained ligand parameters. All four
predeclared same-math states pass at unchanged 1e-8 tolerances. The initial eight
product geometry gates pass within their limited scope; comprehensive stereo,
perturbation geometry, minimization and pose recovery are not established.
The initial force is 128.436, not converged. Existing source reservations and
zero admission remain. This numerical case cannot substitute for independently
allowed active/inactive experimental endpoints.

The earlier [guard profile](pr49_integrity_profile_20260929.md) retained all
integrity operations and identified the fixed-receptor stage as 95.74% of its
measured guard wall time. The subsequent
[canonical-normalization change](cpu_canonical_normalization_20260929.md)
retains fresh raw and canonical digests while deferring diagnostic-path strings.
Separately replayed normalization measurements are 22.40% lower; the full
receptor integrity guard is 2.62% lower. Those separate timings are not additive
subspans. The controlled four-state SRO evaluator has identical complete outputs
with mean wall time 1.826910 to 1.714064 seconds (6.18% lower). Small warm
single-host measurements do not establish full-workflow speedup or justify a HIP
transition. Remaining work includes eligible experimental contrasts, useful
converged refinement and complete preparation-through-storage cost.
