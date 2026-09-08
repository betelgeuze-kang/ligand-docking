# Prepared cross-interaction development adapter

The product-side adapter consumes explicit, local, hash-bound prepared files and
invokes the existing Engine V2 canonical state, radius geometry, and reference
Lennard-Jones/Coulomb kernel. It does not alter the V2 source tree or its frozen
qualification manifest. No third engine, external solver, molecule preparation,
learned correction, docking search, refinement, or dynamics is introduced.

`python -m tools.product.score_prepared_cross_interactions --request REQUEST.json
--output NEW_REPORT.json` evaluates each requested case and retains failures by
request index. Existing output/source files are never overwritten. The public
request envelope is `prepared_cross_interaction_request_v1`, with 1–32 `cases`;
each has a `case_id`, `prepared_input` for `load_prepared_gromacs_components`, and
all six explicit `evaluation` parameters: pocket center/radius, cutoff, switching
start, dielectric, and inverse screening length. The command is a development
consumer; customer capability and qualification flags remain false.

## Supported computation

One nonperiodic CPU float64 prepared receptor (1–10,000 atoms) and ligand
(1–256 atoms), each with explicit coordinates and complete per-atom charge,
sigma, and epsilon. Elements are H/C/N/O/F/P/S/Cl/Br/I; this is a representational
limit, not evidence of chemical or force-field applicability to all those atoms.
The ligand must fit the explicit spherical pocket. No missing charge, hydrogen,
protonation, tautomer, bond order, or parameter is generated.

Energy and atomwise force cover **cross-component pairs only**: Lorentz–Berthelot
LJ plus screened Coulomb with the unchanged V2 constant and quintic switching of
both terms. Cross scaling is one. Cutoff is between the kernel minimum distance
0.35 Å and 20 Å; switch start is positive and below cutoff. All source atom pairs
must meet the existing minimum distance, independently of tile order. Internal
energy, strain, solvation, residual, affinity, and calibrated uncertainty are
unevaluated nulls. These kcal/mol values are not binding free energies or IC50.

Complete source canonical states, actual evaluated coordinates, ordered original
parameters, force vectors, cross-pair indices/hash and counts are retained.
Bounded 64+64 atom projections call the existing kernel. Exact out-of-cutoff tile
culling implements the declared physical cutoff; it does not skip candidates.
For an explicit source sigma=epsilon=0, source zeros remain in the report. V1's
positive-sigma contract uses a documented unused placeholder only in the kernel
projection: with epsilon zero, the LJ value and coordinate derivatives vanish
for every partner. Coulomb still uses the supplied charge. Missing is rejected.

## Prepared-file provenance

The narrow reader retains original topology sections and source atom mappings;
it does not interpret bonded tables as chemical bond orders or merge standalone
protein/ligand 1–4 defaults. Source partial charges are computed force-field
observations, not experimental atomic charges. The strict existing PDB and SDF
parsers are reused. Any explicitly enabled transfer of a blank PDB element from
an exactly matched topology atomic number records the raw blank, source value,
source and projected hashes; it does not infer an element from an atom name.

The initial public development candidate comes from OpenFF's pinned
protein-ligand-benchmark 0.2.1 CDK2/lig_1h1q prepared files. Its prepared ligand
state is retained even where the current CCD tautomer differs. The separately
published 2024 protein parameter lookup table is not proven byte-identical to
the original 2019 preparation. The selected cross model therefore does **not**
replay the original GROMACS simulation Hamiltonian, PME, solvent or bonded terms.
This CDK2/cyclin prepared-state computation is separate from the BACE1 IC50
cheap-selector experiment; the states and label meanings are not interchangeable.

## Evidence boundaries

Synthetic tests independently implement scalar cross energy/force equations,
finite differences, zero-LJ charged controls, rigid transforms, source atom
reordering, inference/autocast contexts, capacity/domain failures and JSON
serialization. Frozen V2 guards remain unchanged. Actual public-state parsing,
module execution, and a separately implemented offline OpenMM static cross
comparison are recorded separately with exact source/commands/environment,
raw logs, exit status and JUnit. Reference code never enters product runtime.

A single public prepared state is development evidence. It does not establish
pose recovery, screening enrichment, general force-field accuracy, performance
improvement, dynamics validity, or customer qualification. Initial per-call
wall/CPU/RSS observations are not p50/p95 latency or cache/batch acceleration
measurements. No protected holdout, Fresh-128 or one-use qualification is run.

Checkpoint migration: none. New request/report/adapter schemas are versioned
independently; existing scoring and model checkpoint semantics are unchanged.

## First public development observations (2026-09-08)

Two distinct public prepared states were requested. CDK2/lig_1h1q was rejected:
source receptor atoms 186/187 (PDB serials 187/188, 1HG1/2HG1) are only
0.11216505694734025 Å apart. This failed state and its cost remain in the full
requested denominator. No atom was removed or moved and no distance guard was
weakened. Its initial missing-element input-format failure is retained separately.

An additional BACE hunt/lig_13 state, from the same pinned OpenFF release, contains
6,229 receptor and 48 ligand atoms and retains its supplied +1 ligand state.
The reader preserves the inert SDF header `> <chiral flag> (1)` and its original
data tail without altering the mol block. All 298,992 receptor–ligand pairs remain
in scope; 13,908 are within the declared 10 Å cutoff. The independently computed
pair set is exactly equal to the adapter's set. On unchanged main V2 source plus
this product adapter, a separate offline OpenMM 8.4 Reference implementation
agrees under the predeclared tolerances:

| Quantity | Own result | Absolute difference from reference |
| --- | ---: | ---: |
| Cross LJ, kcal/mol | -33.489480578816845 | 1.35e-13 |
| Cross Coulomb, kcal/mol | -96.29391776083942 | 8.53e-13 |
| Cross total, kcal/mol | -129.78339833965626 | 7.11e-13 |
| Maximum difference across 18,831 force components, kcal/mol/Å | — | 1.74e-13 |

The fresh own-engine command process took 15.681 seconds including startup and
output; command-main wall/CPU were 13.901/13.896 seconds with peak RSS
748,688 KiB. The adapter's validation, source identity and tiled evaluation scope
was 9.143 wall/9.141 CPU seconds. The reference consumes already-exported arrays
and has a different scope, so these observations are not a fair speed benchmark.
A separate instrumented CDK2 parse indicates repeated canonical identity and
integrity serialization as a cost to investigate; cumulative profile entries
are overlapping and must not be summed.

Coverage is **1 numerically compared / 2 requested public states**, or
**1 / 1 state admitted by the declared source-distance domain**. Five numerical
comparison checks passed for BACE; the public CDK2 observation has one failure
in its own JUnit record. Synthetic/CI test passes are separate. A same-AI
development review and independently written reference expressions/finite
differences are not an external scientific reviewer, signature or approval.

Public sources: [pinned OpenFF data](https://github.com/openforcefield/protein-ligand-benchmark/tree/fe6f96916b2e28f9c14398d77c838d6515e931b0/data),
[separate published protein parameter table](https://zenodo.org/records/10495732).
The evidence bundle retains downloaded bytes, dataset/license identities, raw
requests/responses, identity-only protected-catalogue comparisons, command logs,
actual coordinates/parameters/force vectors, the unchanged reference script,
premeasurement tolerances, source hashes and JUnit. No molecular outcome from a
protected catalogue was read or executed.
