# SRO source preparation through native/OpenMM arithmetic verification

The retained 7XTB serotonin observation now connects to a separately declared
computational microstate, prepared input, full unconstrained force-field
translation, registered single-pose request and independent numerical comparison.
**All four predeclared states pass the same-math energy/force checks.** This is
numerical development on an already known reserved source; no new training,
calibration, independent evaluation or pose-recovery role is admitted.

## What was prepared and executed

The [preparation record](human_5ht6_sro_numerical_preparation/README.md) preserves
all 13 deposited heavy-atom coordinates and adds 13 computational hydrogens.
NZ +1, C10H13N2O+ is a single declared assumption; the deposited EM buffer pH 7.4
is metadata, not a measurement of ligand protonation. Predicted NAGL charges are
kept distinct from measured charges and experimental binding endpoints.

The independent verifier imports neither the builder nor product molecular
loaders/evaluators. It checks source atoms/bonds, exact coordinate round trips,
three atom-name domains, formal/partial charge and mass, supported XML records,
and the 2,124 source-heavy/4,376 prepared receptor coordinate correspondence.
Its receipt binds 33 inspected files. It binds the declared charge-model digest
without reopening the weights or independently repeating model inference.

The full XML contains 27 bonds, 46 angles, 95 periodic torsion terms and 131
exceptions, with zero constraints. Standard native translation preserves all
supported terms. One negative proper Fourier amplitude is normalized with the
required constant energy offset **−0.917914800262 kcal/mol**; the absolute-energy
comparison includes this offset. The ITP remains an adjacency/nonbonded reader
projection, not a full dynamics topology.

The source-frame initial request uses the registered single-pose policy, explicit
receptor chemistry, and unchanged product limits. No scorer, optimizer or pose
search was executed. The fixed-receptor model remains dry and fragmented, with
ligand internal terms and switched cross LJ/Coulomb, cross dielectric 4 and no
receptor internal-energy contribution. Arithmetic correspondence does not
validate these physical-model choices.

## Actual numerical observations

Before calculation the protocol fixed the initial state plus three independent
uniform coordinate perturbations, seed 20260929, maximum component magnitude
0.001 Å. The unchanged absolute tolerances are 1e−8 kcal/mol and 1e−8 kcal/mol/Å.
The OpenMM oracle received these values explicitly; its smaller default
perturbation magnitude was not used.

| Observation | Result |
|---|---:|
| Requested / evaluated / passing / failed states | 4 / 4 / 4 / 0 |
| Maximum checked energy error, including components | 2.018e−12 kcal/mol |
| Maximum force-component error | 2.218e−11 kcal/mol/Å |
| Initial total model energy | 14.798201989 kcal/mol |
| Initial maximum atom force | 128.436473563 kcal/mol/Å |
| Initial product geometry checks | 8/8 within their declared scope |

The initial force is not converged at the unchanged 0.001 criterion; minimization
was not attempted. The initial geometry checks use a 974-atom pocket subset and
include a limited reference signed-volume check, not comprehensive stereochemical
validation. The numerical cross model uses all 4,376 receptor atoms. Geometry was
not separately reevaluated for the three perturbations; their evidence is the
same-math comparison only. No redocking, affinity or candidate-ordering claim
follows from these four states.

## Failure, runtime and cost accounting

The first launch passed **293 tests**, then stopped during binding because the
OpenFF preparation environment lacked Biopython. It made no force calls. Its
logs, frozen sources and failure receipt remain intact. The continuation uses
existing `/usr/bin/python3` (Python 3.10.12, Biopython 1.81, OpenMM
8.4.0.dev-4768436, torch distribution 2.6.0+rocm6.1) with native tensors on CPU
and OpenMM Reference. The preparation had used Python 3.11/OpenMM 8.6.1; this
runtime boundary is recorded rather than represented as one identical environment.
No source, input, scientific threshold or perturbation protocol was changed to
resume. The ROCm build label does not demonstrate HIP execution or parity.

The successful wrapper took **25.239 s**: binding and preparation verification
process 10.693 s, numerical-audit process 13.634 s. The audit's internal scope
11.720 s is inside those costs and must not be added again. The earlier 9.30 s
preparation, failed first launch, tests and human work remain separately scoped;
this is not a complete service latency or speedup measurement.

The 293-test invocation includes 12 preparer boundary cases, 31 independent
verifier cases and 19 request/audit cases, alongside the earlier research and
workflow checks. Post-verifier manifest/ligand/XML mutation, wrong perturbation
protocol and dropped/failed numerical states are rejected. All frozen 265 source
files were rechecked after actual execution. The successful packet references
the first launch's source snapshot instead of copying it again.

## Consequence for the five goals

This closes a second, observed-coordinate **numerical-development** preparation
path and adds a real signed-torsion/charge-state test of the existing converter.
It does not close independent experimental source admission or production
qualification. The [CPU profile](pr49_integrity_profile_20260929.md) identifies
fixed-receptor integrity checks as the main measured guard cost; a semantics-
preserving optimization and matched-output cost comparison are still required.
Allowed active/inactive endpoints, matched similarity/native/AI comparisons,
converged useful refinement and full installed-service validation remain open.

Evidence: [result summary](/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-sro-numerical-validation-20260929-cpu-2zyhi89d/result-summary.json),
[independent preparation verification](/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-sro-numerical-validation-20260929-cpu-2zyhi89d/request/preparation-verification.json),
[complete numerical report](/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-sro-numerical-validation-20260929-cpu-2zyhi89d/audit/numerical-four-states.json),
[execution completion](/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-sro-numerical-validation-20260929-cpu-2zyhi89d/completion.json), and
[repository evidence index](../evidence/sro_numerical_validation_v1.json).
