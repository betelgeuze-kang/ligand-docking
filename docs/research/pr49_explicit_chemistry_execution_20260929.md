# PR49: explicit receptor chemistry and executed CPU comparison

The incomplete receptor chemical graph no longer blocks the authenticated CPU
scorer. The actual comparison now completes, resumes and passes structural
verification. It still selects **zero of two requested candidates**. The main
new finding is that the existing proposal generator recenters and rotates the
prepared ligand; it does not preserve its registered pose. The registered pose
itself passes the declared software validity checks when scored separately.

The [machine-readable evidence](../evidence/pr49_explicit_chemistry_development_v1.json)
pins every external receipt by bytes and SHA-256. Executed product source digest:
`1ace8ae29a95bad25ee58c83926f10d8f027ab622bbe9b5f168f273702f63019`.
The preceding source baseline was commit `67b67b29d6adb8b6b45e0bdbb4773ab06457402e`.
This is a development observation of one computational preparation, not a
reference-pose, activity-ranking, affinity or service qualification result.

## Chemistry and scorer changes

The source 7XTB CIF component bond tables and explicitly mapped AMBER preparation
states now supply receptor bond orders, aromaticity and formal charges. The
derived graph retains all 4,376 atoms, 4,431 bonds and the exact coordinates,
atom order, masses, partial charges and adjacency. It contains 413 double bonds,
211 aromatic atoms and 218 aromatic bonds. Formal charge +11 now agrees with the
prepared partial-charge total. HIE, the declared CYX disulfide and charged
termini are explicit; unsupported states fail rather than being guessed.

The separate `explicit_graph_hbond_features/1.0.0` model and scorer identity
classify the complete graph before filtering the pocket. The receptor has 431
donor pairs, 368 acceptors and 938 hydrophobic atoms under this declared model.
Backbone N, arginine side-chain N, Trp NE1 and protonated HIE NE2 are excluded
from acceptors. The previous model and its receipts remain separately identified.
No score weights or native force equations changed.

Review exposed and fixed three integrity defects: flattened all-single aromatic
graphs were insufficiently checked; regular explicit reports lacked a common
scorer identity against which to check every candidate; and the research
experiment did not pin its independent oracle module and returned tolerances.
The request binder also now verifies the original receptor/cross association
before deriving the new receptor identity. Negative tests retain these cases.

## Actual product comparison and restart

The frozen request was executed through `run-resumable`, stopped after the first
committed baseline candidate, resumed, exported and checked by
`verify-resumable`. The resumed run reused exactly one baseline result. There
were four successful score evaluations, two completed 32-step refinements and
66 native force calls. There were no unknown interrupted-attempt costs.

| Arm and candidate | Score | Minimum receptor distance, Å | Internal increase, kcal/mol | Eligible |
|---|---:|---:|---:|---|
| Baseline 0 | 5730.250 | 0.561 | — | No: overlap |
| Baseline 1 | 5792.594 | 0.613 | — | No: overlap |
| Refined 0 | 1475.290 | 1.314 | 1777.002 | No: overlap and bond distortion |
| Refined 1 | 1114.327 | 1.092 | 1301.509 | No: overlap and bond distortion |

Both refinements remain unconverged. Maximum bond-length changes were 1.492 and
0.862 Å. A lower score or energy did not override invalid geometry, strain or
convergence criteria. The final selection is empty; the success denominator is
four score evaluations, not four valid poses. The comparison and its rejection
records are preserved unchanged.

The product records candidate-level costs and reuse. A single enclosing wall
time including all preparation, verification and storage was not measured for
this interrupted execution and remains unknown; nested scopes are not summed
to manufacture it.

## Why the prepared pose was lost

An independent diagnostic regenerated both baseline proposals and matched their
coordinates and fingerprints exactly. Candidate 0 translates the ligand centroid
by 2.412834 Å to the pocket center. Candidate 1 also rotates it, producing a
6.087274 Å direct all-atom displacement RMSD from the registered pose. These
RMSDs measure a change from the computational input, not error against an
experimental binding pose. `max_torsions=0` only disables torsion changes; a
translation radius of 0.25 Å is centered on the pocket rather than the registered
input centroid.

The exact registered coordinates were separately scored as a distinct proposal
under the same authenticated scorer context. Its score is 75.794460, the validity
report is complete with no blockers, and its minimum receptor distance is
1.529046 Å. This was one additional diagnostic score, with no refinement; it was
not inserted into or used to relabel the completed comparison. Passing the
declared validity checks does not establish a physically correct binding pose.

The next implementation should therefore add an explicit policy for preserving
a registered input pose. Its policy, original coordinate identity, candidate
denominator and restart state must be bound into the request and plan. Existing
pocket-centered search semantics should remain independently selectable.

## Bounded rigid preparation did not solve D3 admission

A separately frozen experiment used at most 32 rigid steps, then the unchanged
32-step native D3 solver. It preserved the 0.60 all-atom overlap ratio, 0.001
kcal/mol/Å force tolerance and 5 kcal/mol internal-increase limit. It was a new
candidate preparation, not the same-candidate product comparison above.

Rigid preparation accepted seven steps and rejected 55 trials on geometry. It
reduced cross energy from 683.052832 to 632.477803 kcal/mol, while maximum
internal pair-distance drift was `2.13e-14 Å` and internal energy changed by
`8.53e-13 kcal/mol`. It stopped at the unchanged geometry boundary.

The subsequent native run completed 32 iterations and 35 force calls. Final
total energy was −97.796665 kcal/mol, internal increase was **43.561586 kcal/mol**,
and maximum force was **67.125677 kcal/mol/Å**. Geometry remained within the
declared thresholds, but strain and convergence failed: **NOT_ADMITTED**.
The archived direct D3 run had internal increase 40.078517 and force 37.951442;
this descriptive comparison supplies no evidence for adopting the rigid warm
start. No post-result budget or tolerance adjustment was made.

Two source-driven OpenMM Reference audits evaluated original/rigid and
rigid/final states: four evaluations, three unique coordinate states, all passing
the fixed absolute `1e-8` energy and force tolerance. Maximum total energy and
force-component differences were `2.08e-11` kcal/mol and `5.21e-11` kcal/mol/Å.
This verifies the declared mathematics at these coordinates. It does not audit
every product candidate above or establish binding accuracy.

The experiment took 105.889 s before report publication, including rigid
preparation 9.926 s, native D3 69.439 s and two oracle scopes of 9.257/9.253 s.
These are nested phase observations from a machine running other CPU work,
not a controlled performance comparison or cumulative engineering cost.

## Cost, packaging and regression evidence

Profiling showed repeated receptor integrity serialization dominated one force
evaluation. Reusing the already computed identity within that evaluation reduces
full integrity checks from four to three while retaining the public validation
boundaries. Mutation tests cover changes during calls. A fixed-state, three-call
per-method observation retained exactly equal energy, all 117 force components,
components and provenance. Median time changed from 2.532 to 1.908 s. This local
microbenchmark does not establish whole-workflow speedup or a GPU bottleneck.

The final focused regression run passed **554 tests** in 60.82 s. It is not the
entire repository suite. A product wheel was built and installed into an external
target directory; 511 non-metadata members matched the checkout and all 222
source-manifest entries matched the executed digest. All 179 loaded owned
modules came from the installed wheel. Synthetic legacy and explicit workflows,
including explicit interruption/restart, passed. Existing dependencies were
shared, so a clean dependency installation and external-user operation remain
unverified. An initial ownership audit mistakenly included a separate native
distribution; its log was retained and the corrected ownership audit passed
without rerunning scoring.

The earlier paused run before report-binding hardening is also retained under
`engine-v2-pr49-explicit-chemistry-execution-20260929`; final evidence uses the
separate `-final` directory. Neither historical receipts nor old failures were
resealed with a later source identity.

## Development decision

1. Preserve the registered pose through an explicit, replay-bound candidate
   policy and verify that the same coordinates reach scoring and refinement.
2. Improve D3 convergence and internal-geometry control on that fixed input;
   compare declared algorithms and budgets while retaining the present criteria.
3. Obtain a separately permitted observed-pose case and measure preparation,
   computation, verification, recovery and export as an enclosing product cost.

No new training rows were admitted, protected evaluation outcomes were not read,
and Fresh-128 remains untouched. HIP parity, affinity prediction and service
readiness remain unqualified. [Current goals](priority_goals_20260929.md) distinguish
completed implementation work from these remaining acceptance conditions.
