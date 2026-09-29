# PR49 / 7XTB computational D3 development input

This preparation connects the previously separate 7XTB receptor and neutral
PR49 preparation through an **actual rigid coordinate transform**, a separately
declared unconstrained ligand force system, and the real prepared-component
reader. It supplies one numerical-development input. PR49 was selected for
implementation work, not as an unbiased activity contrast. It is not an observed
PR49 complex, redocking reference, admitted evaluation sample or affinity model.

The immutable external packet is:

```text
/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-pr49-d3-complex-20260929-final2
```

The subsequent [executed D3 report](../pr49_7xtb_d3_execution_20260929.md)
records strict conversion, five-state OpenMM energy/force comparisons, native
minimization and exact restart. It also records the nonconverged, excessive-strain
result and the separate whole-comparison chemical-typing blocker. Run the
independent registration verifier below before `build_d3_request.py`; the builder
checks manifest bytes but does not replace that geometric verification.

Its manifest SHA-256 is
`95128a77c3dd416371371966b9d7cbd2ca22dbfbff4499cce70bd14d6899af33`.
The packet includes the exact preparer source snapshot, original preparation
references, the geometry protocol and all 13,696 attempted placements, registered
SDF/GRO, an atom-order map, unconstrained XML, parameter differences, complete
reader input, canonical receptor/ligand JSON and the reader's parameter/evidence
output. All 4,376 prepared receptor atoms and 39 PR49 atoms are retained.

## Geometry and scope

The source receptor coordinates originally had a heavy-atom centroid near
(93.3585, 106.6640, 88.7626) Å; PR49's isolated conformer was centered near zero.
Their closest heavy-atom separation was 137.3565 Å. Matching a frame string would
not fix that geometry.

The new pocket anchor is the centroid of the 13 **public** serotonin heavy atoms
in 7XTB model 1, label asym F, CCD SRO, author residue 501:
(84.5650769231, 110.4963846154, 82.0223846154) Å. Serotonin supplies only this
spatial anchor. It does not supply a PR49 atom map or reference pose. The receptor
remains the previously declared active-state, truncated computational preparation,
with modelled hydrogens, terminal groups and three modelled heavy atoms. Assay
microstate, construct and antagonist-state equivalence remain unverified.

The protocol first enumerates 24 proper cube rotations and translations on the
fixed 2 Å grid within a 5 Å radius. After that finite grid fails, it searches rigid
rotations/translations with a fixed-seed differential-evolution procedure whose
objective is exclusively geometric threshold deficit. No energy, force, learned
score, Ki label or PR49 reference pose selects the initial placement. The first
accepted printed-coordinate candidate is retained. This is geometry fitting, not
a docking score or demonstrated binding-pose prediction.

The fixed severe-overlap criteria are minimum all-atom distance 1 Å, minimum
heavy-atom distance 2 Å, and distance/radius-sum ratios of 0.60 for all atoms and
0.72 for heavy atoms. Every ligand heavy atom must lie within 10 Å of the anchor.
The fixed element-radius table and search settings are explicit in
`geometry-protocol.json`, SHA-256
`01c1f5f2c0fa8e253a997565e64c4d319d2025a1f49a1221976bc9fde730af8b`.
Passing these thresholds excludes the specified severe overlaps; it does not
establish a physically valid complex or universally clash-free geometry.

The selected candidate, ordinal 13,695, has minimum heavy/all-atom distances
2.52937/1.52905 Å, minimum radius-sum ratios 0.74393/0.60652, and maximum heavy
radius 6.87319 Å. The proper rotation preserves orientation and all internal
distances before printing. Rounding to 0.0001 Å changes any intraligand distance
by at most 0.000103591 Å. Atom identity, element order, bonds, stereo and all
non-coordinate SDF bytes are retained. The selected geometry is checked against
every receptor atom by explicit all-pair distances after spatial-tree search.

The first coarse-grid run failed. A second run with 150 continuous iterations
also failed after 12,816 recorded attempts; its full failure log remains in
`engine-v2-pr49-d3-complex-20260929-v2/preparation-failure.json` on the same volume.
The third protocol enlarged only the search budget to 1,000 iterations and kept
every geometric threshold unchanged. The successful v3/final/final2 preparation
runs selected identical coordinates and XML. This is an openly iterated development
search, not a retrospectively labelled preregistered benchmark. The final2 run took
13.573 s in total; its nested geometry-search and reader scopes were 7.678 s and
2.057 s. Those scopes must not be added to the enclosing total, and this single
run is not the cumulative engineering or failed-attempt cost.

## Separate unconstrained ligand model

The original OpenFF 2.2.1 PR49 XML contains 14 constraints. It is preserved with
SHA-256 `edf02aab9acb609243040fe5af6f3a6a84419980e428bedd3da6235c138d782d`.
The D3 bridge must explicitly reject unsupported constraints. This preparer
records that required rejection but does not itself call the D3 bridge.

A separate force field is produced by removing OpenFF's Constraints handler
before **reparameterization**, retaining the exact original NAGL-predicted
AM1-BCC-like charges. The resulting XML has zero constraints and 42 harmonic
bonds instead of 28. Its 14 added bond pairs exactly equal the original constraint
pairs. Existing bond parameters, particle masses, and complete serialized
NonbondedForce, HarmonicAngleForce, PeriodicTorsionForce and CMMotionRemover
objects remain unchanged. This is an explicitly different unconstrained model;
no equivalence to constrained dynamics is claimed. The new XML SHA-256 is
`e09e5c0741c8c8784dfb45f63df20f22504aa68e051d720ea7466c2d8ebdaf80`.

The old ITPs remain cross-interaction/adjacency projections. They are not promoted
to complete intramolecular GROMACS topologies. D3 internal-term conversion must
use and verify the new full XML separately; this preparation alone does not prove
the converter, energy, force or minimizer.

## Reader and independent verification

`prepared-input.json` consumes the real transformed SDF/GRO together with the
unchanged receptor and reader parameter projections. The reader ingests data and
correctly retains `coordinate_registration_performed=false`; upstream transform
evidence is a separate `registration.json` claim that the independent verifier
checks. The coordinate-derivation exporter is not used because its contract
forbids a change of frame/registration.

`verify_registration.py` does not import the preparer. It pins the original 7XTB
source and frozen geometry protocol, rederives the source anchor, checks the
proper transform against actual printed coordinates, non-coordinate bytes,
complete atom mapping, all-pair distances, overlap/pocket bounds, canonical reader
roundtrips and false scientific authority. It verifies the recorded first accepted
attempt and selected geometry; it does not independently regenerate the entire
search trajectory or authenticate the historical timing. Tests reject reflections,
scaling, nonfinite matrices, collisions, out-of-pocket positions, frame relabelling
without actual movement, non-coordinate bond edits and rehashed protocol weakening.

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 \
  docs/research/human_5ht6_d3_complex/verify_registration.py \
  /mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-pr49-d3-complex-20260929-final2

PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider \
  docs/research/human_5ht6_d3_complex/test_prepare_complex.py
```

Regeneration requires the original hash-bound external preparations, source CIF
and pinned external OpenFF runtime. Supply a **new** output directory; existing
packets are never overwritten:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. OPENMM_CPU_THREADS=1 \
  /mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-openff-runtime-y2epeamt/env/bin/python \
  docs/research/human_5ht6_d3_complex/prepare_complex.py --output /absolute/new/output
```

Current source-component reservation policy also links serotonin metadata
transitively to reserved components. This numerical-development use does not
assign fit, calibration or independent evaluation roles. Protected outcome files
and Fresh-128 results are not inputs. Mathematical agreement, reference-pose
recovery, candidate activity ordering and affinity prediction remain distinct
validation questions.

## Explicit receptor chemistry and the next execution

`derive_receptor_chemistry.py` separately derives a complete chemical graph from
the source CIF component tables and the declared AMBER preparation states.
It preserves coordinates, atom order, masses, partial charges and bond adjacency.
Only the supported, explicitly mapped standard residues, HIE, CYX and terminal
states are accepted. A coordinate or force-field change is not a chemistry repair.

`bind_chemical_request.py` binds that new receptor identity into a new request.
The schema `cpu_explicit_chemistry_fixed_receptor_request/1.0.0` selects the
versioned `explicit_graph_hbond_features/1.0.0` feature model and a distinct,
uncalibrated scorer. Existing request schemas retain their existing scorer.
The new model checks complete explicit valence before pocket filtering and
classifies donors/acceptors using chemical groups, rather than atom names alone.
Unsupported or incomplete chemistry is rejected. Existing score weights and the
native D3 force model do not change. Old and new score receipts are not interchangeable.

Use a new output directory for each source version. The common product commands
are `run`, `run-resumable`, `verify` and `verify-resumable`; resumable execution
retains its original request and source identity. A source change requires a new
execution rather than relabelling or overwriting an old journal.

`d3_development_experiment.py` is a separate, bounded research experiment:
rigid-body cross-energy descent followed by the unchanged 32-step native D3
minimizer. It writes the protocol before evaluating energy, preserves internal
geometry during rigid preparation, records every trial and retains the existing
convergence and strain limits. Its changed starting candidate is explicitly
distinct from the product's same-candidate comparison. It cannot establish pose
recovery without an observed PR49 reference pose.

See [current goals](../priority_goals_20260929.md) for completion evidence and
remaining scientific and operational work.

## Registered-pose execution

`run_registered_policy.py` selects the opt-in
`cpu_registered_pose_fixed_receptor_request/1.0.0` schema for exactly one prepared
pose. It records its plan before execution, confirms binary64 coordinate identity
in both arms, verifies the product result and independently audits initial/final
energy and force. The installed-package interrupted replay reproduces the actual
case exactly when runtime settings match. The valid baseline is selected because
the unchanged D3 refinement fails geometry, strain and convergence criteria.

`lbfgs_development_experiment.py` separately freezes a 128-accepted-step /
192-force-attempt research protocol on the original pose. Its final result also
remains NOT_ADMITTED; it does not replace the product solver. See the
[executed report](../pr49_registered_pose_execution_20260929.md) for complete
denominators, numerical checks, runtime identity, retained harness failures and
the remaining acceptance conditions.

## Strain and bond constrained research

`constrained_development_experiment.py` adds a separately frozen SLSQP experiment
on the same registered input. `constrained_refinement_core.py` records exact
strain/bond feasibility, all evaluated points and independent KKT diagnostics;
`product_geometry_audit.py` applies the eight existing product geometry checks
to actual trial coordinates without scoring. The product solver is unchanged.

The actual 128-iteration/148-point run retained no improved incumbent. Its
terminal trial still exceeds the strict strain limit and raw-force threshold,
so the original pose remains selected. Main and supplemental OpenMM audits
agree numerically but do not change that negative outcome. See the
[executed constrained-refinement report](../pr49_constrained_refinement_20260929.md)
and [hash-bound evidence](../../evidence/pr49_constrained_refinement_development_v1.json)
for denominators, complete geometry scope, source-integrity overhead and the next
feasibility-preserving research criteria.
