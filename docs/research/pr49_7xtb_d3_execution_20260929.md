# PR49 / 7XTB: native D3 numerical execution and remaining product boundary

The prepared components now reach native fixed-receptor D3, restart, coordinate
export and independent numerical verification in one development case. The
whole candidate-comparison workflow remains **BLOCKED** at chemical scoring
input validation. The minimized pose is **NOT_ADMITTED**. These are separate
results, not a commercial qualification or an affinity experiment.

Machine-readable observations and source/file SHA-256 bindings are in
[`pr49_7xtb_d3_development_v1.json`](../evidence/pr49_7xtb_d3_development_v1.json).
Large raw XML, coordinates, all geometry attempts, numerical force arrays,
checkpoints, timings and the failed CLI traceback remain on the external data
volume at the paths bound there. No experimental labels or training rows were
added; no protected evaluation outcomes were read.

## Preparation and complete term translation

The [preparation packet](human_5ht6_d3_complex/README.md) contains 4,376 receptor
atoms and 39 neutral PR49 atoms. A real rigid transform, all-pair collision
checks and an independent registration verifier replace the previous ~137 Å
separation. The public serotonin centroid supplies only a pocket anchor. There
is no observed PR49 pose or redocking reference. Geometric thresholds were not
relaxed; unsuccessful search protocols and all attempted placements are retained.
The successful protocol was developed iteratively, not an untouched benchmark.

The original constrained OpenFF XML is actually rejected with
`constrained_bond_terms_missing`. A separately declared unconstrained model
restores its 14 missing harmonic bonds by OpenFF reparameterization. The original
14-constraint model is preserved. The new model retains the original charges,
particle masses, angles, torsions and nonbonded parameters; it is not equivalent
to the original constrained dynamics.

The strict converter preserves 42 bonds, 70 angles, 122 proper Fourier terms,
57 periodic star improper terms, 112 excluded pairs and 92 scaled pairs. Seven
negative proper coefficients retain the required energy offset, totaling
−6.375138681673 kcal/mol. Unknown forces, virtual sites, offsets, unsupported
constraints and exception semantics are rejected. The versioned extension does
not change the legacy harmonic-improper schema.

The internal model is equivalent to unswitched NoCutoff arithmetic only while
every internal distance stays below 90 Å; every evaluation checks this domain.
The independently declared cross model is finite LJ plus Coulomb, dielectric 4,
quintic switching from 10 to 12 Å, with a fixed receptor and no solvent. Receptor
intramolecular energy is not part of this minimization objective. These are
computational model assumptions, not experimentally validated affinity physics.

## Independent numerical comparison

OpenMM 8.4 Reference evaluates source XML directly. A second independent
source-driven calculation makes the D3 Coulomb constant explicit, and separate
ligand×receptor interaction groups evaluate the declared cross formula. No
translated D3 parameter rows supply the reference energies or forces. Original
OpenMM constant differences remain separately visible.

Initial coordinates, three fixed-seed ±0.0001 Å coordinate perturbations, and
final D3 coordinates all pass: **5 requested, 5 evaluated, 5 passed, 0 rejected**.
The first four also appear in the earlier audit; these are five unique states,
not nine independent samples. Absolute energy and force-component tolerances
were fixed at `1e-8` kcal/mol and `1e-8` kcal/mol/Å, with no relative tolerance.

| Compared quantity | Maximum energy error (kcal/mol) | Maximum force-component error (kcal/mol/Å) |
|---|---:|---:|
| Internal | 6.82e-13 | 1.97e-11 |
| Cross | 2.10e-11 | 3.93e-11 |
| Total | 2.07e-11 | 5.21e-11 |

All mapped energy components also pass. This supports implementation agreement
at the tested coordinates within the declared model. It does not validate the
chemical state, solvent model, binding pose, ranking or affinity.

## Native execution, restart and admission

The pre-execution plan fixes 32 steps and the existing `0.001` kcal/mol/Å force
criterion. Native D3 performs 38 force evaluations with no failed force calls.

| Observation | Initial | Final |
|---|---:|---:|
| Total potential (kcal/mol) | 399.913181 | −96.762905 |
| Ligand internal potential (kcal/mol) | −283.139650 | −243.061133 |
| Cross LJ (kcal/mol) | 676.918208 | 145.681831 |
| Cross Coulomb (kcal/mol) | 6.134623 | 0.616397 |
| Maximum force norm (kcal/mol/Å) | 745.982632 | 37.951442 |

This is energy descent, not a converged or admitted candidate. The internal
increase is **40.078517 kcal/mol**, above the separately fixed **5 kcal/mol**
limit. The force criterion is also unmet. The direct minimizer exports raw
results; its `accepted_iterations=32` counts line-search steps, not pose
acceptance. The full selection workflow did not run, and applying these two
required admission conditions gives **NOT_ADMITTED**.

Pausing after three accepted steps, serializing the checkpoint and resuming
reproduces the full final checkpoint and coordinates exactly. Continuous work
uses 38 force calls; split execution uses 39, including one restart verification.
Measured continuous time is 97.111 s and split execution is 100.758 s. The
continuous force-evaluation scope is 93.933 s **inside** its total. These are
single local measurements, not speedup evidence or complete development costs.
Preparation, failed geometry searches, numerical audits and the failed product
workflow remain separate measured scopes. This was a source-checkout CPU run,
not clean-installed-wheel or HIP qualification.

## Why whole candidate comparison is blocked

The actual native `run-resumable` CLI fails during ScorerV1 construction; the
failure was reproduced and its full traceback retained. Zero candidates were
executed, despite two candidates per arm being planned. This is an input-stage
failure, not four failed docking results.

The receptor has AMBER partial charge +11 and formal annotations totaling zero:
all PDB charge columns are blank. Independent template matching confirms the
prepared residues and charges. All 4,431 canonical receptor bonds are represented
as order 1, with zero aromatic atoms or bonds. Merely forcing the formal total
to +11 would hide incomplete chemical typing. A direct feature audit classifies
all 278 backbone nitrogens, seven Trp NE1 and two HIE NE2 atoms as acceptors under
that incomplete graph. The existing charge rejection stays in place.

The [chemical audit](human_5ht6_d3_complex/chemical_typing_audit.py) records these
observations and the exact template/source hashes. Fixing this requires a
source-bound chemical graph covering bond order, aromaticity, formal charge,
protonation, disulfides, peptide bonds and terminal groups together, followed by
independent donor/acceptor checks. AMBER adjacency and partial-charge templates
alone do not provide that graph.

## Next work supported by these observations

1. Complete and verify receptor chemical-state transport before unrefined/D3
   candidate scoring. Preserve coordinates and force parameters as separate
   immutable inputs; do not bypass the charge check or invent an atom carrying +11.
2. Diagnose the poor initial pose and strain/convergence failure on development
   cases. Keep the fixed numerical oracle and admission criteria. A total-energy
   reduction alone must not promote a result; pose recovery needs a reviewed
   reference pose and its own frozen protocol.
3. Compare matched candidates through unrefined, native D3 and an external
   reference only after the chemical-scoring contract is valid. Assess AI order
   separately, and report preparation, failed requests, intervention, restart and
   publication costs separately from core work. Equal time caps do not prove
   equal executed work. Profile the measured force-evaluation scope before
   attributing its cost to GPU-suitable kernels.

Local verification: **205 tests and 3 subtests passed** across the new bridge,
OpenMM numerical oracle, fixed-receptor pipeline, publication, tampering,
restart and geometry suites. This is focused software evidence, not a full
repository CI, service-readiness or scientific qualification claim.
