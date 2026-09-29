# Current molecular development goals

These are work packages within the five unfinished Engine V2 goals. The live
app goal was rechecked as `active` on 2026-09-29; the earlier `usageLimited`
observation is historical. No replacement goal or smaller completion definition
is used. The five requirements remain:

| Goal | Evidence still required for completion | Current boundary |
|---|---|---|
| 1. Source-linked human-target inputs and experimental endpoints | Prepared chemistry and comparable active/inactive endpoints with explicit, independently cleared train/calibration/evaluation roles | Human 5-HT6 computational preparation and a typed 205-occurrence source audit exist; 78 printed IDs and six repeated reports do not establish independent measurements. Source-family/identity/intake clearance remains incomplete; no newly admitted fit/calibration/evaluation rows |
| 2. Preparation quality and numerical validity | Contact, completeness, stereochemistry, charge and same-math checks; execution separated from eligibility | The new fixed-budget SRO comparison completes: external L-BFGS converges at 253 objective calls with force 0.00095027, all 8 scoped geometry and 2 initial/final same-math checks passing; SD remains unconverged after 417 calls. This is one declared-state development result, not pose recovery, affinity validation or product optimizer integration |
| 3. Similarity/native/native+AI comparison | Same eligible candidates, declared compute budget, all requested/failing candidates, independently interpreted outcomes | Source-bound registered-pose v3 now passes a two-candidate synthetic four-arm installed run and guarded reuse; independently cleared real candidates and scientific matched comparison are incomplete |
| 4. Integrity-preserving CPU efficiency | Equivalent results and mutation detection with enclosing measured cost | Deferred diagnostic formatting retains both fresh integrity passes; four-state SRO full outputs match with evaluation mean 6.18% lower, and the receptor integrity guard mean is 2.62% lower; full preparation-through-storage cost and broader throughput remain unproved |
| 5. Integrated reproducible baseline | Compatible implementation, installed execution/restart/report, exact-source verification and preserved historical work | The latest sulfonyl-compatible source passes 120 affected tests and a fresh 44-runtime dependency installation with exact source/wheel/installed ownership. Its synthetic public CLI comparison/verified reuse passes with zero new score/force calls on completed reuse. Product L-BFGS integration, mid-minimizer resume and all five real end-to-end requirements remain incomplete; earlier 529/255-test receipts belong to their historical source versions |

The work-package priorities below do not replace these five goals.

| Priority | Objective | Completion evidence | Current status |
|---|---|---|---|
| 1 | Transfer a complete, source-bound receptor chemical graph | Bond orders, aromaticity, formal charge, HIE/CYX/termini and atom mapping verified; coordinates, partial charges, masses and adjacency unchanged; unsupported states rejected | Implemented and verified on all 4,376 receptor atoms |
| 2 | Preserve the prepared input and complete the CPU comparison | Explicit registered-pose request/plan, exact initial coordinates, normal and installed pause/resume agreement, failure denominator and verification | Implemented; actual one-pose/two-row execution and exact installed replay passed; valid baseline retained |
| 3 | Improve useful D3 refinement without weakening acceptance | Fixed development protocol; independent energy-force checks; strain and convergence limits unchanged; rejection retained if limits fail | Historical PR49 and 32-step SRO remain NOT_ADMITTED. The new SRO comparison finds a development-eligible external L-BFGS state at 253 calls with force 0.00095027 and all original criteria passing; matched-cap SD fails after 417 calls. Versioned product integration with durable intra-candidate restart is the next implementation task |
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
The [bounded occurrence audit](human_5ht6_2024_occurrences_20260930.md)
now binds 205 typed occurrences and their endpoint distinctions to retained
source spans. Thirteen unresolved categories, null roles and unknown independent
measurement denominator remain explicit; the original ledgers are unchanged.
The [observed-pose readiness audit](7xtb_observed_pose_readiness_20260929.md)
identifies serotonin/SRO with 13 observed heavy atoms and verifies 2,124 shared
receptor coordinates. A separate [SRO preparation and numerical execution](sro_numerical_validation_20260929.md)
now preserves those heavy coordinates with a declared NZ+1 computational state,
13 generated hydrogens and complete unconstrained ligand parameters. All four
predeclared same-math states pass at unchanged 1e-8 tolerances. The initial eight
product geometry gates pass within their limited scope. A later
[installed registered-pose refinement](sro_registered_refinement_20260930.md)
now completes 32 accepted steps and 51 force calls, retaining 8/8 final scoped
geometry and 2/2 independent initial/final arithmetic checks. Final raw force
8.428 exceeds 0.001; the baseline is selected. Comprehensive stereochemistry,
perturbation geometry, pose recovery and useful converged refinement were not
proved by that 32-step run. The later fixed-budget comparison below separately
establishes an externally converged development state. Existing source
reservations and zero admission remain. This numerical case cannot substitute for independently
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

The [bounded existing-source metadata query](human_5ht6_reserved_metadata_20260930.md)
found one Ki record and one molecule accession in each exact assay and
document/target filter, with no missing pages and no additional identity. That
specific source-expansion route is exhausted; no role or numeric-outcome boundary
was changed. New primary correspondence and a candidate-to-prepared-state bridge
remain separate prerequisites to the matched-policy comparison.

The supplementary [five-row Ki correspondence](human_5ht6_2024_repeat_correspondence_20260930.md)
resolves the missing Table 5 means/SDs and their Table 6 repeats while preserving
the original occurrence inventory. This credits zero new independent measurements
and does not clear source-family roles or prepared-state correspondence.

The [non-outcome identity manifest](human_5ht6_2024_identity_manifest_20260930.md)
now links all 205 occurrences to 78 PR labels and 45 other literal names, with
78 source-bound synthesis headings and 22 entry-level prior-description citations.
PR29/PR39 print the same chemical name but cite different preparation methods;
a retained-source follow-up shows PR39's Table 4 ring atom `Y=N` conflicts with
its naphthalene synthesis name. Its corrected identity remains unresolved
alongside PR65/PR66. Source graph inclusion and roles remain unchanged. Official
access did not retrieve reference 31 or the supplement; targeted original-source
correspondence is still needed. Bibliography or synthesis citations alone do not
establish Ki reuse.

The [registered native-v3 integration](registered_native_v3_integration_20260930.md)
connects the source-record descriptor to explicit graph/coordinate stereo,
original XML charge tokens, a common receptor/method cohort and the installed
D3 four-arm comparator. Direct run and preflight share admission; invalid input
cannot bypass a preflight-only check. Its two synthetic molecules start at
model equilibrium, select their baselines and establish software connection and
reuse only. Their six successful initial force calls and twelve score calls do
not establish iterative refinement benefit. Existing real sources still have
zero newly admitted rows. SRO's separate 32-step rejection remains unchanged.

The [registered Kekule compatibility fix](registered_kekule_compatibility_20260930.md)
resolves a real SRO prepared-graph rejection caused by aromatic representation
normalization. All four unchanged-input component checks now pass in the exact
installed wheel, along with 89 affected regressions and synthetic installed
comparison/reuse. This adds no real force/score calls or assay admission and
does not change the earlier unconverged SRO result.

The [same-budget SRO SD/L-BFGS comparison](sro_same_budget_comparison_20260930.md)
now completes both arms under the separately reviewed 417-objective-attempt cap
and 7200-second operational watchdog. SD's 51-observation historical prefix
matches exactly. SD uses all 417 calls and retains the baseline because force
5.864118662 exceeds 0.001. L-BFGS converges after 253 calls at 0.000950270044,
with all original strain, geometry, score and independent numerical requirements
passing. Its refined selection is the external research protocol decision;
the installed product solver has not been replaced. All 670 attempted states
and returned forces are retained, with no extrapolation after early termination.
This justifies a versioned product L-BFGS integration, not new assay admission,
general algorithm ranking, affinity claims or a HIP transition.

The [sulfonyl compatibility and fresh installation](registered_sulfonyl_fresh_install_20260930.md)
resolves the pinned RDKit false-positive potential stereo rejection while
retaining true unsupported stereo boundaries and the original raw identity.
Its 120 affected regressions pass. A new independent runtime environment now
passes exact wheel installation, dependency resolution, the synthetic four-arm
public CLI and completed reuse. This closes the previously missing fresh
dependency installation observation; meaningful real candidate comparisons and
mid-minimizer restart remain separate requirements.

The [source-mapped PR49 aromatic annotation](pr49_aromatic_annotation_20260930.md)
now produces a separately referenced canonical preparation with correct aromatic
flags, exact original coordinates/charges/integer bonds and consistent parameter
hashes. All four component gates and five reproduction/mutation checks pass;
the old artifact remains rejected and unchanged. This clears a preparation
representation blocker without creating a source row, role, fit or admission.

The next implementation is the
[versioned Cartesian refinement and durable-restart path](cartesian_refinement_integration_20260930.md).
The source review identifies why changing an optimizer flag alone is insufficient:
the old projected schema, 256-step pose budget, projection work counters and
candidate-only retry semantics do not represent the demonstrated 417-attempt
Cartesian comparison. New solver/history/journal identities and explicit
restart-verification accounting are required. This design is not yet implemented.
