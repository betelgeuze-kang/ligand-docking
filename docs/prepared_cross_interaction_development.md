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

## Ordered molecule sources in prepared-input v2

The unchanged command envelope accepts the additive prepared input schema
`prepared_gromacs_components_v2`. Each `protein_chains` entry contains an exact
PDB `chain_id` (one non-whitespace character or the empty string for an original
blank field) and `molecule_itps`, an explicit ordered list of 1–32 independently
hash-bound original molecule files. Molecule atom indices may restart at one.
The reader offsets only canonical adjacency indices while retaining each original
source atom index, topology row and source-molecule label. PDB residue numbers,
chain fields, atom order and coordinates are not rewritten. All existing count,
residue, atom-name, element, charge, parameter and distance checks still apply.

`prepared_gromacs_components_v1` keeps its original one-file `molecule_itp` and
nonblank-chain contract. Existing v1 canonical hashes, parameters and complete
provenance were equal before/after in a separate invented input. Clients opt into
v2 explicitly; there is no checkpoint or score-unit migration. A synthetic
blank-element transfer found a source-label omission in the initial v2 draft;
the corrected ledger resolves the original molecule file, with the v1 label as
its unchanged fallback. The new controls also cover nonzero bond-index offsets.

## Third distinct public prepared input: thrombin/lig_5

The pinned OpenFF thrombin PDB retains a blank chain field, 4,688 atoms and
original residue numbers 1–295. Its declared protein molecule topology is split
into 4,527-atom and 161-atom files, with the second file restarting atom indices.
The original v1 consumer rejected this representation (`chain_id: nonblank string
required`, one requested/zero evaluated/one failed). V2 explicitly represents the
two original files under the blank chain; no chain name, atom, charge or hydrogen
position is fabricated. The successful repeat is the same distinct input, not a
new denominator member. The ligand has 52 supplied atoms and retains its +1 state.

The actual command on exact parent source plus this adapter change exited zero,
with one requested/one evaluated/zero failed/zero skipped. Independent NumPy
expressions, which import no engine or solver, compared all 243,776 cross pairs
and exactly matched the 13,977 pairs within the declared 10 Å cutoff. LJ is
-39.39911546111321 kcal/mol, Coulomb is -116.1653778597004 kcal/mol, and total
cross energy is -155.5644933208136 kcal/mol. Absolute total-energy difference is
2.27e-13 kcal/mol; maximum difference across all 14,220 force components is
2.91e-13 kcal/mol/Å. Both pass the predeclared 1e-8 tolerances. Unevaluated
internal energy, strain, solvation, residual and affinity remain null.

The whole fresh process, including output and source-origin audit, took 11.336 s
and peaked at 799,272 KiB RSS. The command-main scope excluding startup/output
reported 9.866 wall/9.856 CPU seconds; the inner adapter scope reported 5.776
wall/5.769 CPU seconds. These are one-state observations, not p50/p95, a speedup,
a CPU/GPU comparison or a fair comparison against the array-only reference.

Across distinct public inputs, coverage is now **2 numerically compared / 3
requested**, or **2 / 2 within the declared source-distance domain**. The earlier
CDK2 failure remains. This thrombin state and BACE use separate independently
written static references; neither establishes binding affinity or dynamics.
The separately sourced protein parameter table still does not establish identity
to the original OpenFF simulation Hamiltonian.

Local exact-parent regression passed 270 tests (257 existing plus 13 v2 controls),
with no skips. Four independent adapter controls passed separately, including
v1 output equality. The reference has six synthetic formula controls and one
actual-state comparison; those totals are separate. The evidence retains an
initial collection failure from an incomplete source snapshot, the initial
post-execution origin-check misclassification of the installed native dependency,
and an audit's incorrect blank-element assumption. These were harness errors;
the corrected run verifies all repository module hashes/origins, records the
installed dependency separately, and leaves source guards unchanged.

The source's 11 measured thrombin binding free energies were checked against the
original author table. One uncertainty annotation differs (lig_5: OpenFF -1
versus author-table 0.3 kJ/mol) and is unresolved. All 11 compounds share one
study/scaffold component, so they do not supply independent fit/calibration/test
groups. No thrombin model is fitted and no measured free energy is subtracted
from this cross potential energy. The original author thesis has separate
noncommercial rights; its full text is not redistributed with development data.

## Source-coordinate observations in the actual consumer

Every command row now carries `source_geometry_observation` under the additive
`prepared_source_geometry_observation_v1` contract. After successful preparation,
the consumer retains preparation provenance even if the physical evaluator later
rejects the input. The observer reuses canonical V2 components and the compact
radius graph, examining all supplied atoms in the single CPU float64 nonperiodic
frame. Coordinates, atom order, energy, forces, pocket selection and the physical
admission guards are unchanged. No checkpoint or score-unit migration is needed.
The request and existing result schemas remain v1; strict output consumers must
accept the additional row field and provenance on successfully parsed failures.

The fixed inclusive 1 Å radius is a descriptive search window, not a calibrated
clash threshold or a chemical validity test. Receptor, ligand and cross groups
report complete unique pair counts within that window and up to 16 nearest
pairs per list, with the exact undisplayed count. Atom indices, source serials,
chain/residue/insertion codes and canonical source hashes identify observations.
The supplied direct adjacency alone separates direct bonds from other pairs;
1–3/1–4 exclusions and a complete chemical nonbonded interpretation are not
claimed. A missing source molecule or `[ bonds ]` section leaves bond-filtered
counts null. An explicit empty section is retained as supplied information,
not evidence that the chemical topology is complete.

Missing preparation, nonfinite/unsupported geometry, invalid adjacency or the
bounded neighbor/cell capacity yields an unavailable observation with null
groups. A successful zero count remains distinct. Neighbor capacity can depend
on coordinate orientation and grid placement; overflow does not authorize a
zero or partial count. Observer failures are visible and do not replace the
independent physical evaluator's result. The observation records its own wall
and CPU cost; total consumer cost includes that work. This adds interpretive
evidence and may add cost; it is not an engine acceleration or affinity claim.

Fresh synthetic controls reproduce the former missing output field and cover
missing versus explicit empty bond sources, complete canonical chain/molecule
coverage, unchanged physical output, original numerical rejection, bounded
display and unavailable capacity. Independent synthetic checks additionally
exercise rotation, translation, atom permutation, remapped bond indices and
the inclusive radius boundary. No protected molecular outcome is used.


## Conservative mathematical projection compaction

Within each original 64+64 tile that survives the existing exact cutoff cull,
the adapter can omit a mathematical projection atom that lies outside every
opposite-side coordinatewise cutoff cube. A conservative rounding margin keeps
boundary atoms; the unchanged V2 radius graph decides the exact spherical pair
set. Original tile iteration and source order remain fixed. Complete source
states, source validation, all requested cross pairs and all source-indexed force
components remain in the report. This reduces repeated projection/graph work,
not the number of ligand candidates or the declared physical cutoff.

The optimization has explicit numerical eligibility bounds: absolute source
coordinates at most 1e6 Å, absolute charges/sigma/epsilon at most 100 in their
declared units, dielectric in [1e-3, 1e3], and inverse screening length at most
1e3 /Å. Inputs outside these bounds use the original full tile. These bounds do
not reject an input or expand its physical applicability. They preserve original
nonfinite-intermediate errors: the V2 kernel evaluates masked terms and forms a
zero from the coordinate sum. Initial drafts hid errors from excluded extreme
charges/LJ parameters and from very large finite coordinates. Fresh synthetic
controls reproduced those failures; both drafts and their failed logs are
retained, and the original path restores each error without weakening a guard.

The additive `pair_accounting.projection_compaction` object names the algorithm,
eligibility/fallback, original/projected atom slots and the omitted mathematical
slots. Existing result schema, units, checkpoints and source identities retain
their meaning. Strict validators must allow the added accounting object. This is
not a cache or a batch API and does not supply strain, solvent, affinity, a
learned residual, calibrated uncertainty or dynamics.

### Latest source-reservation and molecular-state audit

A newer complete metadata component graph contains 126,655 nodes. Under the
existing conservative source/scaffold/document reservation policy, all 42 MCL1
entries in the pinned OpenFF source now connect to a component containing 1,013
reserved/protected nodes. An explicit witness is lig_27 → scaffold →
ChEMBL activity 9585896 → document → ChEMBL activity 9582185 → scaffold →
BindingDB record 42649 (`protected=true`). The former unblocked receipt is stale.
These entries are not newly admitted for training, evaluation or benchmarking;
previous observations are retained as historical engineering evidence. No
protected molecular outcome is read by this metadata graph audit, and no
reservation edge or original role is removed to obtain a split.

The original paper's compound 60 links to PDB 4HW3 and CCD 19G, but the prepared
carboxylate and the CCD neutral acid are distinct chemical states. The common
4HW3 receptor does not make prepared lig_23/lig_26 poses their own experimental
cocrystals. A different 6O6F source has a different paper and construct. These
sources do not yet supply matched experimental pose/affinity labels for the
current calculation. Original author text was inspected for these mappings;
full text transmission and limited SAR-text exposure are disclosed in the audit.
The current cost comparison consequently uses newly invented numerical states.

### Matched synthetic cost measurements

The final comparison uses two fresh 308-source-file snapshots with zero Python
bytecode caches before and after every process. Bytecode writing is disabled.
It repeats the same fixtures, order, final adapter bytes and independent scalar
reference with unchanged 1e-8 energy/force tolerances. Installed dependency and
OS caches are shared/uncontrolled; this is not a physical cold-cache benchmark.

Sparse numerical fixtures have 64, 512 or 2,048 receptor atoms and 13 ligand
atoms, with four near and 60 far receptor atoms per original tile. A separate
dense 64×13 fixture keeps all 77 projection atom slots and all 832 cross pairs.
The dense follow-up was selected after sparse timings to investigate overhead,
not pooled into a more favorable average. None is a model of protein chemistry.

Each mode/fixture has three interleaved fresh processes and one first plus two
warm evaluations. In total, 24 processes retain 72 complete evaluation outputs,
with zero failures, skips or timeouts. Every source coordinate, parameter,
source-indexed force component, pair set and requested denominator is retained.
Parent and final candidate energy/force outputs are exactly equal here. Separate
scalar expressions agree within 3.56e-15 kcal/mol and 2.23e-15 kcal/mol/Å, below
the predeclared 1e-8 tolerances. All loaded first-party module hashes match the
snapshots. These are mathematical equivalence checks, not molecular validation.

CPU float64, one Torch/BLAS thread on a shared host. Cold readiness is process
launch through source verification, imports, construction, first evaluation and
writing its complete output. Warm evaluation reuses canonical objects but still
runs complete validation, integrity guards, graph construction and physics;
output serialization is separate. RSS is whole-child high-water memory. Cold
n=3 and warm n=6 are small, dependent-within-process samples; interpolated p95
is descriptive and does not establish production tail latency.

| Fixture | Cold p50/p95 s, parent → final | Warm p50/p95 s, parent → final | Warm CPU p50 s, parent → final | Whole-child RSS p50 KiB, parent → final |
| --- | --- | --- | --- | --- |
| sparse, 64×13 | 1.712596/1.714145 → 1.664254/1.665763 | 0.074823/0.075545 → 0.025153/0.026057 | 0.074601 → 0.025080 | 536,000 → 535,524 |
| sparse, 512×13 | 2.247224/2.272540 → 1.817365/1.823005 | 0.567968/0.572796 → 0.184907/0.207018 | 0.567944 → 0.184904 | 542,488 → 540,896 |
| sparse, 2,048×13 | 4.121041/4.198863 → 2.534599/2.535812 | 2.333361/2.364392 → 0.707141/0.717376 | 2.333222 → 0.706342 | 565,188 → 564,640 |
| dense, 64×13 | 1.697243/1.709706 → 1.714009/1.719456 | 0.096840/0.097996 → 0.097764/0.102324 | 0.096641 → 0.097353 | 535,916 → 536,672 |

Sparse warm costs fall at unchanged outputs, while dense times are close with
about 1% higher measured warm/cold medians. RSS changes are small. This does not
establish a universal speedup, real screening benefit, improved pose/hit recovery
or lower memory. No engine cache on/off, true batch API, GPU/VRAM, or admitted
real-molecule quality-at-equal-budget comparison is measured by this experiment.

Earlier sparse/dense observations are retained, not pooled or silently removed.
An independent audit found 176 valid loaded-module Python bytecode caches only
on the parent (179 total cache files), and none on the candidate. Disabling
bytecode writing had not disabled reading those existing caches. Their numerical
comparisons still pass, but their cold/process differences cannot be attributed
to this code change. The matched repeat above corrects the harness. The first
attempt to make fresh snapshots copied cached entries present in the old parent
manifest; its zero-cache assertion stopped before any measurement. That error
and the new manifest-only non-bytecode copy are documented without altering
source bytes, assertions, physical guards or earlier evidence.

An even earlier compaction draft hid extreme-coordinate errors. Its 54 outputs
remain historical rather than final guard validation. Final local regression
passes 305 tests with zero failures/errors/skips, including actual parser and
subprocess consumer integration. Independent final-source synthetic controls
pass 56 tests; two saved-output audits and six reference arithmetic controls are
reported separately. These are internal automated checks, not external human
review, scientific validation or customer approval. No new model is trained and
no checkpoint or physical-score migration occurs in this change.
