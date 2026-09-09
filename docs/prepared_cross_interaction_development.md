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

The same CLI also dispatches `prepared_input.schema_version =
compiled_gromacs_cross_particles_v1` to a compiled-source particle reader. This
profile reads one local hash-bound standalone `.top` and `.gro` pair. It requires
explicit receptor/ligand molecule names, exact counts of every excluded molecule,
and explicit trailing inert virtual-site omissions. Each selected molecule must
have one copy. It preserves the full topology text, source atom indices, residue
partition, connectivity, supplied coordinates/charges/parameters, original box,
and all selected/omitted site counts. A source molecule group is not asserted to
be a biological chain. Selected particle limits remain 10,000/256 and the full
GRO inventory is bounded to 99,999 unwrapped sequential serials.

Compiled input fields are `schema_version`, `topology`, `coordinates`,
`selected_molecules` (receptor/ligand names), `excluded_molecules` (name/count map),
`omitted_inert_sites` (receptor/ligand lists of source indices), the existing four
`source_declarations`, and `source_relationship`. File references retain the
existing absolute `path`, `sha256`, and `source_id` contract. For the published
waterNES 1LPG input, selections are system1/LIG, exclusions are MOL:1, HOH:16947,
NA:61, CL:62, and the only omitted selected-molecule site is receptor 4426.

This is a **particle cross-potential input**, not chemical preparation. Chemical
bond orders and formal-charge observations are unavailable; source adjacency is
retained separately, canonical chemical bonds remain empty, and canonical formal
charge default zero is explicitly marked as an unavailable observation rather
than an assigned atomic charge. Same-state experimental joins remain unverified
and ineligible. All hydrogens and partial charges used in the calculation come
from the source files. No missing coordinate or parameter is fabricated.

Selected/global preprocessing is rejected. Only inert `#ifndef FLEXIBLE` water
bond/constraint branches outside selected molecules can be retained without
evaluation; they cannot change the particle inventory. Omitted selected sites
must be explicitly declared, trailing, zero-mass/zero-charge/zero-epsilon dummy
particles with a supported two-parent virtual-site definition. Other selected
virtual sites or parameter overrides are unsupported. The source simulation's
periodic Hamiltonian, solvent and bonded terms are not reproduced.

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


## Deposited mmCIF ligand coordinate observations

`python -m tools.product.observe_mmcif_ligand_coordinates --request request.json --output report.json`
adds a separate offline, source-bound observation consumer. This does not replace
or weaken prepared-state admission in `score_prepared_cross_interactions`.
Request schema `mmcif_ligand_observation_request_v1` contains 1–32 cases with
`case_id`, an absolute local `source: {path, sha256}`, `selection`, and caller
`provenance`. Selection explicitly supplies `entry_id`, `label_asym_id`,
`component_id`, `auth_seq_id`, and string `model_number`. Provenance, including
original role/split/evaluation-only declarations, is retained as declared and
cannot grant training admission. Duplicate case IDs fail every duplicate.

The adapter reuses the V2 CIF lexer/block parser, canonical `Bond` carrier,
controlled bond-order vocabulary and compact radius graph. It checks source
entry, entity, asym and nonpolymer instance mappings; preserves source atom
order/IDs and coordinates; joins the entry's component atom/bond tables; and
records absent atom coordinates. Multiline descriptive names and unused extra
table fields remain bound by the original file hash, without becoming identity
keys. The older strict topology parser and its exact-header restrictions are
unchanged. Missing atom-site and component charges remain separately null; the
adapter deliberately does not instantiate an `Atom` with a default zero charge
or construct an unprepared `AllAtomSystem`.

The output reports source bond lengths and all unique selected-ligand pairs at
an inclusive 1 Å radius. This is a geometric observation, not a calibrated clash
criterion. Capacity overflow produces an unavailable geometry result with null
pairs/count. Missing hydrogens, heavy atoms and charges, measured zero occupancy,
and unknown occupancy have separate counts. Alternate locations, ambiguous or
duplicate identities, nonfinite coordinates and conflicting declarations fail
without repairing or choosing a last row. Coordinates describe the explicitly
selected asymmetric-unit instance; no assembly/symmetry transform, alternate
model choice, receptor preparation or intercomponent bond inference is applied.

Eight post-observation public Factor Xa development structures were exercised
through the actual module consumer. Their 273 supplied ligand heavy-atom
coordinates and 298 observed-coordinate bonds were compared with a separately
implemented Gemmi parser and scalar Euclidean-distance calculation. All eight
have complete heavy-atom coordinate coverage against their own component tables,
but lack ligand hydrogen coordinates and atom-level charge declarations. This
establishes source correspondence only. Potential energy, atomic forces and
partial charges remain null; all-atom readiness, assay-state equivalence,
training/scientific/customer admission remain false. These crystallographic
coordinates are not predocking cheap-selector features.

The observation report is a new v1 schema and requires no checkpoint, score-unit
or existing prepared-report migration. The dedicated prepared-cross workflow
includes fresh synthetic observation controls; actual public sources and their
local Gemmi cross-check are retained in the development evidence bundle and are
not downloaded by CI. No external solver or model fitting is added.

The additive `source_polymer_context` field carries entry-wide deposited entity,
polymer sequence, database alignment, sequence difference, modified-residue and
unobserved-residue declarations. Original category tags, token values and row
order are preserved; missing categories are null. Duplicate declaration rows are
retained without resolving them, and declaration consistency remains unverified.
This metadata does not assign a receptor chain to the selected ligand, prepare
missing coordinates, or establish assay-construct equivalence. An accession match
alone can conceal engineered mutations, deletions and unobserved phosphorylation.
For example, the public fit-associated 2P2H and 2P2I entries both declare C817A,
E990V and deletion 940–989, while only 2P2H also declares V916T. PTR1054/1059
are unobserved in their coordinate models. These declarations accompany the
observed ligand coordinates rather than being replaced by a wild-type assumption.
The nested context has its own `mmcif_source_polymer_context_v1` identifier; the
existing request, score/checkpoint and prepared-state admission are unchanged.


## Source metadata projection and actual fixed-pose comparison

The cross adapter keeps complete source metadata in the validated parent states
and returned canonical sources. Its temporary mathematical pair projections now
carry only source-side and source-atom maps. Copying each raw source atom record
into every tile previously repeated metadata hashing inside the unchanged V2
kernel. All full parent integrity guards and tile kernel guards remain active;
coordinates, parameters, element/charge fields, neighbor construction and physics
are unchanged. This is neither neighbor caching nor fewer evaluated candidates.

A fresh synthetic source-payload control fails on parent `71413af9`; its positive
scalar energy/force control passes after this change. A second control mutates a
nested source atom metadata tensor during evaluation and confirms that the
original integrity guard still rejects it. The complete dedicated local scope
passes 428 tests, zero failures/errors/skips. An earlier command labelled
`full-ci` omitted `--full` and ran only two tests; the retained `full-scope`
command and JUnit are the actual 428-test evidence. No earlier test is weakened.

The predeclared public-source comparison retains all three MIT-licensed
MobleyLab/waterNES prepared inputs from commit
`c7f6eed8e75520a181a028e914848f432aca7fd3`: 1LPG, 1EZQ and 1F0S.
For each, the fixed candidate roster contains the original pose and six rigid
translations of plus/minus 0.25 Angstrom along each Cartesian axis. There are
21 requested poses: 14 evaluated and seven preparation failures. The original
malformed 1EZQ GRO input remains a typed failure; it is neither repaired nor
removed from the denominator. No candidate is fitted or selected using scores.

The independently written scalar pair expressions and V2 evaluate the same
nonperiodic switched cross LJ/Coulomb model, states, charges, parameters and
coordinates. At the predeclared 1e-8 absolute tolerance, all 14 outputs match:
maximum energy error 9.38e-13 kcal/mol and maximum atom force component error
4.69e-13 kcal/mol/Angstrom. Ordered cross pairs and rankings agree. A saved-output
verification corrects an initial driver tuple-versus-list comparison error without
rerunning physics; both the failed driver log and corrected JUnit are retained.
Candidate adapter outputs also exactly preserve all 14 baseline quantities,
pair inventories, canonical source states and reported model/pocket declarations.

The original input poses rank second of seven for 1LPG and fourth for 1F0S.
Thus even this local probe does not establish original-pose recovery. It is not
symmetry-aware RMSD, chemical pose validity, affinity or a screening benchmark.
Same-model residual differences are numerical noise; this comparison supplies
zero eligible scientific residual-training rows. Strain, solvation and affinity
remain unevaluated, and no experimental Ki state join or new learning occurs.

For preloaded prepared states, five interleaved A/B repeats per source preserve
all 30 slots (20 evaluated, ten preparation failures). CPU float64 uses one
Torch/BLAS thread on a shared host. 1LPG evaluator wall p50/p95 decreases from
5.8132/6.9252 to 4.8742/4.9705 seconds; 1F0S decreases from 4.0467/4.0922 to
3.4533/3.5689 seconds. CPU p50 changes from 5.8122 to 4.8739 seconds and from
4.0465 to 3.4530 seconds respectively. Outputs and candidate count are unchanged.
The approximately 15-16 percent median reduction applies only to these two
prepared evaluations. Same-process cumulative RSS cannot attribute memory use
between variants. No GPU, true batch API, end-to-end screening, pose/hit recovery,
calibrated uncertainty, dynamics or customer qualification is established.

Report schemas and score units do not change. The adapter source fingerprint
changes; archived outputs keep their original fingerprint. No model checkpoint
is migrated, rehashed or trained by this optimization.


Fresh-process complete CLI comparison (three paired repeats, AB/BA/AB) includes
imports, all three input/hash checks, source geometry, evaluation and compact
JSON output. Both variants write to the same secondary disk; OS page caches are
not flushed, and neither source snapshot has Python bytecode caches. The 18
requested source slots retain 12 evaluations and six preparation failures; all
six commands return the expected partial-failure exit code 2. Complete outputs
agree except explicitly measured costs and the changed adapter source hash.

| Whole CLI metric | Parent A | Candidate B |
| --- | --- | --- |
| Wall p50 / p95, s | 18.3642 / 18.5081 | 16.9675 / 16.9882 |
| Child CPU p50 / p95, s | 18.3443 / 18.4669 | 16.9481 / 16.9664 |
| Whole-child peak RSS p50 / p95, KiB | 807,196 / 807,415.6 | 807,684 / 826,252.8 |

The whole-CLI wall median is 7.6 percent lower on these inputs. Memory does not
improve; three repeats are insufficient for deployment tail claims. This is the
fixed-input scoring CLI, not end-to-end docking, selection or active recovery.
GPU/VRAM and full cold-storage effects are unmeasured.

Two earlier CLI harness attempts are retained separately: the first comparator
forgot source-geometry timing fields; its replacement assumed failed observations
also had a cost field. Persisted outputs confirm only cost/source-hash differences.
The corrected comparator was exercised on saved complete outputs before the final
six-process run. Earlier timings are not pooled with the final matched output-disk
comparison. No physical guard or output field is weakened by these harness fixes.

## Optional experimental-assay selector co-execution

The same `tools.product.score_prepared_cross_interactions` module now accepts
`prepared_cross_interaction_with_assay_shadow_request_v1`. It executes the
existing registered public assay selector before the existing prepared V2
cross calculation. This closes the prepared CLI's model co-execution gap; it
is not a docking search, BioDiscovery end-to-end run, or physical-energy residual.
The default v1 request and all its physics remain unchanged.

The new request retains `cases` and adds `assay_selector` with `checkpoint` and
`checkpoint_sha256`. Each case may contain an `assay_metadata` object. For the
frozen ChEMBL37 Factor Xa Ki model it contains `smiles`, `endpoint=Ki`,
`endpoint_subtype=enzyme_inhibition_Ki`, and the model's exact
`target_annotation_sha256`. The annotation is a catalogue declaration, not
verification of the prepared receptor or assay construct. All additional source
metadata, original roles/splits and even conflicting historical declarations are
preserved verbatim under `input_metadata`; they are not training admissions.

The model adapter and its previous base/v2 tests are reused byte-for-byte from
PR513 head `2817f1785761118a7d3109704d898fae8c5a8c20`. No registry, checkpoint,
features, calibration or scores are changed. New module
`betelgeuze_engine/product/prepared_assay_shadow.py` invokes its existing loader
and batched `predict_rows`. Neither training code nor a new solver is introduced.
A separate source fingerprint identifies this integration.

Outputs use `prepared_cross_interaction_with_assay_shadow_report_v1`. Every case
retains its original request index, including duplicate IDs and physics failures.
`assay_selector_shadow` is a separate observation: AI pKi, heuristic fit mean,
uncertainty null, OOD not assessed, original metadata and reasons. No prepared
chemical-state verification or energy conversion is inferred from a SMILES or
matching ID. `combined_score` stays null; `residual_training_eligible` stays false.
The original cross result still exposes the actual evaluated coordinates, units,
atomic cross forces and unevaluated terms. Model failure cannot suppress a
physical evaluation, and physical failure cannot erase a completed prediction.
Separate denominators count all physical cases and shadow evaluated/unsupported/
not-requested cases. Explicitly requested but unsupported model rows make the
CLI exit2, as does a physical failure; absent optional metadata is not requested.

### Actual fixed-structure observation, 2026-09-09

The previous three native waterNES inputs and immutable ChEMBL Ki checkpoint
`c6e508e390df9d295ec53c9cc26f16a27c7ff5e31bf8f479e777f6c2e758049b`
were run through the real module without interception or external solvers.
Three fresh-process pairs used the predeclared order off/on, on/off, off/on.
Every process requested3 cases, computed2 and retained1 preparation failure
(1EZQ's original malformed GRO). No cases were skipped or repaired by guessing.
Every shadow process predicted2 supplied catalogue ligands; 1EZQ had no supplied
assay metadata and stayed not requested. All6 processes exited2 for the retained
physical failure. Coordinates, atomic parameters, cross energies/forces, source
geometry and failure records matched exactly across each pair after excluding
only their recorded timing fields and the new shadow observation.

- 1LPG catalogue ligand: predicted pKi5.598057095240747. Prepared H count/charge
  differs from the catalogue representation. The original historical fit role
  and failed expanded BindingDB identity-independence observation are retained.
- 1F0S/PR2 catalogue ligand: predicted pKi6.55686292361489. Heavy connectivity and
  relative handedness have previous source evidence, but prepared bond orders,
  formal charge and complete receptor/assay-state identity remain unverified.
  Original BindingDB calibration provenance remains visible and ineligible for fit.

These are AI predictions, not new experimental measurements. No evaluation label
was joined, no new model was fit and no same-state residual row was obtained.
The original ChEMBL model was trained on224 exact Ki observations; its earlier
3-row exact development evaluation worsened versus the mean baseline. Serving it
here does not reverse that negative result or establish out-of-distribution accuracy.

| Whole fresh CLI process, CPU | Shadow off p50 / p95 | Shadow on p50 / p95 |
|---|---:|---:|
| wall seconds, including output |15.6112 /15.7666|16.0585 /16.1144|
| user + system CPU seconds |15.58 /15.724|15.99 /16.062|
| peak RSS KiB |748880 /749085.2|727584 /727609.2|

Paired wall overheads were0.3367,0.1084,0.5665 seconds. Each mode has only3
observations on a shared host with OS caches unflushed; these descriptive tails
and RSS variation establish no speedup or memory improvement. No GPU, warm
process, candidate recovery, search/refinement, dynamics or calibrated uncertainty
was measured. Source and checkpoint bytes were fixed before execution.

Fresh synthetic controls failed7/passed1 on the parent consumer because the
optional request was unsupported. The completed focused and previous regression
suite passed516, with0 failures/errors/skips, and Ruff passed. Initial lint found
three statement-formatting errors, corrected without changing behavior. Actual
artifact checks additionally compare all paired outputs and independently compute
the two frozen Morgan/ridge dot products. The first comparison harness mistakenly
included nested timing fields; its failed log is retained, and only timing fields
were excluded in the corrected comparison. No physical tolerance was relaxed.

A relocated runtime/input copy reran the actual CLI while network connections,
child processes and training/solver imports were blocked. After a host-description
metadata-only setup, no original evidence reads were allowed. Physics and model
rows matched after excluding only recorded costs and file-location fields;
verification passed, with the expected CLI exit2 for1EZQ. The first harness attempt
blocked Python's `platform.platform()` call to system `uname`; its failure is kept.
The corrected harness caches only that host description before applying the same
restrictions. No model or physics call was mocked. This is offline replay with the
installed dependencies, not clean-wheel installation or customer qualification.


## Explicit pair LJ extension and actual AKT1 component observation

The independently versioned `betelgeuze_engine.product.reference_pair_lj` API wraps the unchanged
V1 evaluator. It accepts caller-assigned mixed pair sigma/epsilon values, retaining
V1 exclusions, LJ scaling, charge interactions, energy switching, topology and
neighbor checks. Overrides on excluded or unknown atoms, duplicates, nonfinite
values and periodic input are refused. The source digest and sorted overrides
bind a new parameter fingerprint; existing V1 fingerprints/checkpoints/scores
are unchanged. Its source digest is a caller declaration, not a verification of
the referenced file. The development source workflow separately checks bytes.
Forces differentiate the same corrected scalar. Scientific/composition approval
remains false. This API is exercised by an actual development consumer; the
prepared cross CLI does not yet accept CHARMM or automatically use these overrides.

The draft import previously lived at
`betelgeuze_engine_v2.physics.reference_pair_lj`. Development callers now import
`betelgeuze_engine.product.reference_pair_lj`; the numerical implementation,
parameter schema and fingerprints are unchanged. There is no compatibility module
in the frozen V2 namespace. This keeps the existing ScorerV1 transitive source
manifest exact while the separately tested adapter explicitly imports the V2
primitive. Frozen manifests, protocols and their rejection tests remain unchanged.
The reference-physics CI watches and hashes the new adapter path. This import
migration does not promote the adapter into the prepared cross CLI or establish
scientific or customer execution approval.

A licensed public AKT1 PSF/PDB (Zenodo17187387, CC BY4.0) supplies7761 atoms,
480 residues,7854 bonds and the original charges/hydrogen coordinates. The
July2024 CHARMM archive was pinned at mackerell-lab/charmm36-force-field commit
283160ad9682f23e92d442d35feba71b2e6baae1 with its MIT notice. Its archive bytes
also match the MacKerell laboratory's primary download exactly (SHA256
`a9382b5739c00092d626a074ba75db849e900080092c8560d46a3cf3a1fc85fc`).
The protein PRM SHA256 is `a1209a63aadbe00beb59566e533cdfa16956707ae6ef589bde0f1b8fca125984`.
All38 source atom types have parameters;10 types have distinct1-4 values and
NC2–OC has an NBFIX override. Standard mixing alone is a different parameterization,
not a numerical failure of the original V1 kernel.

The predeclared development model evaluates only nonperiodic intramolecular LJ
and Coulomb at10Å cutoff,8Å quintic energy-switch start, dielectric1 and no
screening. Source bond graph distances1/2 are excluded; distance3 uses source
1-4 LJ; the explicit NBFIX is retained. This is a newly declared component model,
not the native NAMD/CHARMM total Hamiltonian or trajectory. Bonded, CMAP,
solvation, strain, long-range contributions, total potential energy and affinity
are not evaluated and remain null. The apo/autoinhibited modeled receptor is
not established as the active construct of the frozen IC50 observations.

The initial1024-neighbor configuration was rejected before energy evaluation by
V2's fixed256 hard cap. The recorded execution amendment uses128-atom blocks,
at most256 atoms per off-diagonal projection and exact AABB cutoff pruning,
without changing caps, atoms or the physical model. The full-source minimum
separation check runs before tiling.986 tiles evaluated;905 were exactly outside
the declared cutoff. All7761 atoms and1,071,717 cutoff pairs are retained;
22,040 pairs are source1-2/1-3 exclusions,20,458 are1-4 pairs and353 use NBFIX.
The full all-pairs denominator is30,112,680.

An independently written NumPy Rmin energy/analytic-force implementation uses
separate OpenMM parameter/PSF readers and a SciPy neighbor search. No OpenMM
System/Context or solver runs. Its source bond exclusions and all cutoff pair
indices match the V2 consumer exactly. LJ/Coulomb differences are6.82e-13 and
5.46e-12 kcal/mol; maximum component force difference is3.66e-13 kcal/mol/Å
against the predefined1e-7 tolerances. Every atom's force vector and actual
coordinates are saved. Omitting source pair rules changes this component by
3570.44 kcal/mol and a force component by69.05 kcal/mol/Å; the original V1
arithmetic independently matches its own generic-mixing reference. These are
parameter-rule differences, not affinity or cross-score comparisons.

Cost is not competitive yet: one paired old/corrected V2 observation took569.29s
wall/569.21s CPU, peak1,045,364KiB. Within that paired run, neighbor construction
was111.30s, original V1 evaluation187.81s and corrected evaluation206.50s;
source binding, projection, identity and output work are also included in the
total. Imports are excluded from these inner times. The separate analytic
reference took5.43s/413,520KiB including its source parsing and comparison work.
This is n=1 on one CPU host, not a matched end-to-end timing benchmark, p50/p95,
GPU evidence, speedup or docking recovery result. Repeated neighbor/identity
work and tile construction need profiling and exact-result-preserving reuse.

Validation:43 local pair-extension/V1 tests and6 separate actual-artifact checks
passed with0 failures/errors/skips; the unchanged Engine V2 architecture guard
passes. Tests include independent pair energy/forces through the switch/cutoff,
zero epsilon versus missing values, charge/scaling preservation, multiple pairs,
rotation/translation/permutation, batches, finite differences and source failures.
CI adds the new tests while retaining all existing physics contracts, and uploads
exact source hashes and JUnit. No protected qualification or model refit occurred.

Local evidence root:
`/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-akt1-parameter-intake-4hpua2d5`.
It contains source files/notices, native metadata, plans/amendment, initial
failures, development consumer and separate reference source, atom/parameter/pair
ledgers, coordinates/forces, command/exit/environment logs and JUnit. This local
artifact layout is not a portable customer input format. Frozen experimental
model quality remains unchanged and NOT_PROMOTED; same-state bound ligand,
prepared cross/assay joins, total-model physics and candidate recovery/cost
remain incomplete. No external reviewer or scientific approval is asserted.

Sources: [MacKerell laboratory archive](https://mackerell.umaryland.edu/charmm_ff.shtml),
[parameter-file semantics](https://academiccharmm.org/documentation/version/c49b1/parmfile),
[AKT1 source](https://zenodo.org/records/17187387).


## Opt-in spatial projection through the prepared product consumer

The existing cross adapter can now partition original receptor and ligand atom
indices by recursive widest-axis median splits, bounded to64 atoms per component
block. It still calls the same V2 cross kernel. No atom, candidate, source state,
parameter, cutoff pair or physical term is removed by this option. The complete
source minimum-distance and mutation guards, conservative cube compaction,
source-index force scatter, exact pair accounting and finite accumulation checks
are retained. Outside the existing compaction numerical bounds it uses the
original source-order blocks, including their excluded-term failure behavior.

Existing `prepared_cross_interaction_request_v1` and assay-shadow v1 requests
retain their original default order and result fields. New opt-in requests use
`prepared_cross_interaction_request_v2` or
`prepared_cross_interaction_with_assay_shadow_request_v2`. Each v2 case requires
`"execution": {"projection_partition": "source_order_v1"}` or
`"execution": {"projection_partition": "spatial_median_v1"}` alongside the
unchanged explicit evaluation parameters. Invalid or missing execution options
remain failed cases in the full denominator. The corresponding report envelope
is v2; spatial results additionally record requested/effective partition, any
numeric fallback, block counts and the original-index block SHA-256. No model,
checkpoint, physical score, source coordinate or frozen protocol migration occurs.
AI predictions remain separate shadow observations with no combined score or
same-state residual claim. Customer execution and scientific validation remain false.

On exact parent56a789d373d927894aeb7a6d36dd2ea95be57497, new option/CLI/shadow
controls fail4 while the original actual-parser CLI positive control passes1.
The implemented focused consumer regression passes552 with0 failures/errors/skips;
Ruff passes. New controls include130-by70 synthetic particles, independent scalar
energy and analytic forces, rotation/translation/permutation, explicit zero
parameters, cutoff/switch boundaries, unchanged near-pair and extreme-value
failures, and actual multiblock PDB/ITP/GRO/SDF-to-module execution. These are
synthetic numerical and integration results, not experimental chemistry evidence.
The initial local run passed261 and failed1 because a new test expected the wrong
exception class for the existing kernel's correct near-pair rejection; the test
now expects that existing typed exception. No guard or tolerance was relaxed.

Renewed public thrombin execution was deferred: the current154607-node metadata
context plus the source-declared measurement, calculation-study and PDB citations
connects all11 queried candidates to a124923-node component with1320 reserved
nodes, independently checked by breadth-first traversal. This deliberately
conservative shared-literature dependency is not proof of experimental label
leakage or direct derivation from each cited calculation. No public coordinates,
labels or checkpoint were newly used in this audit, and no blocked case was
removed to report a favorable denominator:0 admitted /11 queried. Query nodes
and witness paths are retained separately from the unchanged role context.
Therefore this product option has no new real-structure speedup, recovery or
memory claim. The separate apo AKT1 intrareceptor benchmark is not a product
cross-interaction benchmark. Broader frozen scorer-source CI incompatibility
introduced before this change remains unresolved; no guard is weakened here.

Evidence snapshot:
`/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-product-spatial-partition-_38e3rae`.
It retains the source-bound commands, environment, initial failed logs, parent
reproduction and full-regression raw logs/JUnit, CLI request/source/output files,
and metadata-only admission audit. This change is an opt-in development path;
quality-cost superiority and customer qualification remain unmeasured.
