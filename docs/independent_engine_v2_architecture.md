# Independent Engine v2 Architecture

Status: implementation scaffold; not a scientific or product release claim
Scope: independent molecular representation, sparse equivariant AI, docking,
physics, molecular dynamics, and structure-analysis engine

## 1. Goal and independence boundary

Independent Engine v2 is the clean scientific core for an independently
operated protein-structure and ligand-analysis product. A customer execution
must not delegate pose search, force or energy evaluation, molecular dynamics,
free-energy estimation, or AI inference to Vina, GNINA, Smina, OpenMM, AMBER,
GROMACS, or another molecular solver.

Those programs may be used as **offline reference oracles** in development and
validation. Their results must be provenance-labelled and cannot be emitted as
v2 results. General Python infrastructure and hardware runtimes such as
PyTorch, Rust, and ROCm are implementation foundations, not scientific
backends.

The first v2 slice establishes contracts and mathematically safe primitives.
It does **not** establish docking accuracy, force-field validity, GPU parity,
benchmark parity, calibrated affinity, MD validity, or commercial readiness.

## 2. Package boundary

The new implementation lives under `betelgeuze_engine_v2/`. It may consume
legacy values only through explicit adapters. New v2 modules must not import
legacy proxy scoring, coarse topology, attention, or customer result emitters.

```text
betelgeuze_engine_v2/
├── engine.py        # fail-closed internal CPU reference orchestration
├── features.py      # deterministic all-atom feature construction
├── contracts/       # typed/frozen schema shells, versions and claim state
├── molecular/       # all-atom identities, bonds, stereo and validation
├── forcefield/      # non-runtime topology, parameter, assignment, fit, and numerical-diagnostic contracts
├── geometry/        # bounded sparse graphs; no dense N x N allocation
├── ai/
│   ├── sparse_graph.py
│   ├── energy.py    # invariant scalar residual energy
│   ├── torsion.py   # static torsion/topology propagation
│   ├── temporal.py  # recurrent state; fixed-window mode is explicit
│   └── physics_informed.py
└── physics/
    └── projection.py
```

The existing `forcefield/typing.py`, `term_inventory.py`,
`linear_alkane_parameters.py`, `linear_alkane_assignment.py`,
`linear_alkane_evaluation_method.py`, `linear_alkane_method_binding.py`,
`linear_alkane_energy_diagnostic.py`,
`parameters.py`, `fitting.py`, `spice_c1c4_quantum_reference.py`,
`spice_c1c4_force_matching_targets.py`,
`spice_c1c4_bonded_basis_observability.py`,
`harmonic_diagnostics.py`,
`harmonic_virial_diagnostics.py`, and `harmonic_minimization.py` modules are
topology-contract, nonphysical, or non-runtime scaffolds. Future modules add
production force terms, integrators, long-range electrostatics, docking search,
refinement, validation, and report adapters. Product APIs remain outside the
engine and may consume a v2 result only after the relevant scientific gate is
satisfied.

The initial `IndependentEngineV2` orchestrator is an **internal CPU reference**
that connects validated molecular state, bounded geometry, deterministic
features, and the uncalibrated AI reference modules. Its output is always
`claim_safe=false` and carries checkpoint, scientific, benchmark, GPU, and
product blockers. Availability of this internal entry point does not enable a
customer route or any solver claim.

The legacy training adapter changes feature semantics from global KNN and
padding-influenced PE to bounded local-radius neighbors and active-only PE.
Shape compatibility is not checkpoint compatibility. V2-0 checkpoints embed a
runtime-input schema plus cutoff/capacity settings. Schema 2.1 also records
`periodic=false`; its benchmark path deliberately rebuilds the same non-periodic
compact-radius graph and active-only PE instead of reusing the force-field's
periodic/grid neighbor payload. Known train, benchmark, and ONNX consumers
reject old raw checkpoints or mismatched settings and require retraining. This
compatibility guard is not evidence that the legacy AI model is scientifically
valid in a periodic simulation. The shared loader also requires every current
model state key to be present and shape-compatible. Non-strict mode may ignore
retired extra checkpoint keys, but it cannot silently leave random current
weights. Dtype mismatches and non-finite tensors are rejected before mutation;
intentional partial transfer is a separate explicit development-only decision
and is not enabled by train, benchmark, or ONNX consumers.
Training checkpoints unwrap `torch.compile` to a canonical model key space, so
compile mode cannot leak `_orig_mod.*` prefixes that an ordinary consumer would
otherwise reject.

## 3. Canonical data flow

```text
validated all-atom molecular state
            │
            ▼
bounded cell-list / Verlet graph ─── torsion topology graph
            │                              │
            ├──── local SE(3) energy GNN ──┤
            │                              │
            └──── temporal GNN (streamed TBPTT for fixed window)┘
                           │
                 invariant scalar energy
                           │ exact VJP
                           ▼
                    conservative force
                           │
              structured orthogonal projection
                           │
                optimizer / integrator / docking
```

The V2-0 reference result currently records source provenance, schema IDs,
initialization seed, parameter fingerprint, feature/neighbor schema, device,
dtype, and claim blockers. Canonical molecular snapshots now carry a
recomputed, schema-pinned ordered-topology digest, but that digest is identity
evidence rather than chemistry validity. Code commit, complete software
environment, calibrated checkpoint provenance, and signed execution manifests
remain future release requirements. Unsupported chemistry fails closed; it is
never silently replaced with carbon-only atoms, alanine residues, or
virtual-bead evidence. Frozen dataclasses do not imply deep immutability of
contained tensors or metadata dictionaries; serialization/hashing gates must
close that boundary before product use.

### V2-1 canonical-ingest applicability boundary

V2-1 separates broad graph inventory from an affirmative ingest decision.
`ChemistryCoverageReport` remains a non-promoting inventory; it does not turn
`graph_representable=true` into chemistry or parameter support. The separate
`betelgeuze.canonical_ingest_applicability/1.0.0` report may return
`canonical_ingest_status=supported` only for the fixed
`source_explicit_h_neutral_nonisotopic_stereo_unassigned_acyclic_saturated_hydrocarbon_ingest_v1`
profile. That profile requires a current valid canonical state, a recomputed
topology digest, a recognized version-pinned parser pedigree, a self-consistent
parser-observation digest, one connected H/C-only graph, known zero formal
charges, no isotope/aromatic/stereo state, single bonds, acyclicity, exact
H=1/C=4 valence closure, and source-observed rather than adapter-generated
hydrogens.

This is an **ingest-only** applicability statement. The report always keeps
source authentication unproven, preparation incomplete, electronic state
untyped, `parameterability_assessed=false`, `parameterizable=false`,
`simulation_ready=false`, and `claim_safe=false`. V2-2 must supply a versioned
parameter set, assignment digest, applicability domain, and validation before
any downstream gate can change. The V2-1 schema-1.4 corpus binds selected
affirmative explicit-H methane, ethane, propane, n-butane, and branched
isobutane SDF rows, plus exact cyclobutane-cycle and ethane-missing-hydrogen
profile boundaries, out-of-profile abstention rows, identity-preservation
rows, and intentional parser failures to exact source and report digests.
These selected rows are evidence for the existing canonical-ingest-only
profile, not exhaustive chemistry support or a C1--C4 size ceiling; they do
not promote preparation, parameterability, simulation, or claim authority.

For successful PDB and mmCIF parses, `StructureIngestCoverage.supported` and
its explicit alias `syntax_ingest_supported` have the fixed support scope
`syntax_and_canonical_projection_only`. They assert only that accepted source
syntax was projected into the current canonical identity contract. They do not
assert bond-topology completeness, preparation, chemistry support,
parameterability, simulation readiness, or claim safety.

In the unchanged base `parse_pdb` contract, `CONECT` fixed-column syntax and
serial references are validated, but no such record is projected into
canonical `Bond` state. Every otherwise valid base-parser `CONECT` input fails
with `unsupported_contextual_conect_semantics` because source declaration
occurrences are not bond-order evidence and record type plus residue spelling
are not sufficient proof of a standard covalent bond. The current schema
cannot distinguish covalent, coordination, cofactor, LINK, disulfide, or
modified-residue context. A separate opt-in source-declaration envelope is
described below; it preserves only ordered rows and ordered target slots while
keeping the carrier bondless. Canonical bond projection remains blocked until
versioned residue/atom templates and explicit bond-kind/source-context
contracts exist.

In the unchanged base `parse_mmcif` contract, mmCIF categories whose
chemistry-significant values are not yet preserved or interpreted also fail
closed. Explicit topology categories fail with
`unsupported_topology_category`; ion, non-polymer component, chemical-component,
branched-component, polymer-sequence, functional-binding, modification, and
modified-residue context categories fail with `unsupported_context_category`.
They are not accepted as generic metadata because dropping their values would
erase information needed to distinguish covalent connectivity, coordination,
ion identity, cofactor/component identity, or polymer modification context.
Any other category that would otherwise be classified as
`uninterpreted_metadata` fails with `unsupported_uninterpreted_category` unless
it is on the narrow reviewed non-chemical metadata allowlist. This default-deny
rule keeps future dictionary additions fail-closed instead of depending on an
ever-growing chemistry denylist.
The separate opt-in nonpoly identity envelope below handles only its exact two
additional source-identity categories without changing that base admission
policy.
The separate opt-in nonpoly component-topology envelope below composes that
unchanged identity carrier with one exact `_chem_comp`, `_chem_comp_atom`, and
`_chem_comp_bond` profile. It is the only selected mmCIF path that materializes
those source-reported intracomponent declarations as canonical bonds. A still
narrower opt-in covalent-`_struct_conn` envelope composes that exact carrier
with one exact 23-field loop and materializes only explicit identity-symmetry
`covale` inter-residue bonds. Direct `parse_mmcif` admission and every
unselected topology category remain unchanged and fail closed.
The separate opt-in polymer-sequence envelope likewise handles only one exact
`_entity_poly_seq` membership loop; direct `parse_mmcif` admission remains
unchanged and fail-closed.
The separate strict nine-category polymer-sequence plus nonpoly
component-topology composition envelope splits its source into the exact
eight-category component child and exact six-category polymer/nonpoly child,
requires both children to accept independently, and cross-binds only their
shared carrier state and byte-exact canonical shared loops. The component child
continues to own the detached molecular system and its pedigree; polymer
membership remains source evidence only. Direct `parse_mmcif` admission and
both child contracts remain unchanged and fail-closed outside their exact
surfaces.
The third opt-in envelope below composes that carrier with one exact
residue-level `_pdbx_unobs_or_zero_occ_residues` loop. It does not broaden the
base parser/writer or either lower envelope.

Stereo and isotope corpus rows pin source bytes, canonical labels, ordered
topology hashes, full snapshot hashes, and all non-promotion reports for SDF
`M  ISO`, SMILES deuterium/tritium, opposite tetrahedral R/S assignments, and
opposite alkene E/Z assignments. Paired labels must produce distinct topology
and snapshot hashes. SDF atom parity, SDF bond stereo, V2000 mass-difference,
unsupported non-tetrahedral SMILES stereo, unretained stereo markers, and
out-of-contract isotope mass numbers are intentional failures. This is ingest
identity evidence only: independent CIP recomputation, coordinate stereo
verification, substituent equivalence, physical nuclide validity, parameter
coverage, and preparation remain blocked.

### V2-1 strict SDF V2000 canonical-writer boundary

`betelgeuze_engine_v2.molecular.sdf_v2000_writer` is a deterministic writer for
the exactly representable state created by the current strict SDF V2000 parser.
It is not a general `AllAtomSystem` exporter. The accepted state has 1--999
atoms, 0--999 bonds, no unit cell, and exactly one CPU `float64` coordinate
model in Angstrom with `requires_grad=false`. Every coordinate must survive an
`F10.4` emit/parse cycle with the identical IEEE-754 binary64 value; values that
would round or overflow the fixed-width field are rejected.

The writer preserves printable three-line header text, source atom order,
element, known formal-charge value and atom-block-versus-`M  CHG` encoding
class, `M  ISO`, atom map, supported bond types 1--4, aromatic markers, and the
parser-recorded bond row order and endpoint orientation. It accepts only the
exact synthesized single `LIG` residue and `L` chain, exact parser atom/bond
markers, current parser pedigree, current topology and parser-observation
digests, and false preparation/claim authority. Atom or bond stereo, partial
charge, free-form mass, altloc/occupancy/B-factor, arbitrary residue/chain
context, cell state, extra metadata, SDF data fields, unsupported provenance
operations or authority, and stale parser markers fail with a typed
`SdfV2000WriteError`; none is silently dropped. Safe header text and exactly
representable coordinates may be edited while retaining parser-shaped state.
In that case the receipt binds the edited current snapshot, while
`parent_source_sha256` records lineage only and does not assert that the parent
raw source contained the edited values.

The versioned representable-state projection includes the supported topology,
coordinates as binary64 hex, parser-owned markers, header text, and synthesized
context. `round_trip_sdf_v2000_source` alone executes
`source -> canonical -> emitted SDF -> canonical`, requires identical projection
and topology hashes, and then requires a second emission to be byte-identical.
Its success receipt, report, and aggregate result are factory-only; aggregate
construction recomputes and cross-checks the source, coverage, payload, receipt,
reparse, projection, and re-emission links. The aggregate stores both canonical
systems as immutable snapshot bytes and returns a freshly deserialized copy on
each accessor, so caller tensor mutation cannot stale the retained report. The
write receipt separately binds the
original source SHA-256, input full snapshot and topology hashes, projection
hash, and emitted-source SHA-256. Projection-digest equality directly covers
the binary64 coordinate and declared parser-marker entries; it is not a full
snapshot comparison. A reparse correctly creates a new raw-source SHA and
parser-observation digest, so full snapshot, `system_id`, `source_id`, and
dynamic provenance equality are explicitly outside the round-trip claim. These
hashes are tamper evidence, not source authentication. General PDB, general
mmCIF, general SMILES beyond the strict forest/simple-ring subset below, and general SDF
round-trip remain blocked. The writer and report
keep preparation, parameterability, simulation, runtime, scientific-validity,
and claim authority false.

### V2-1 opt-in SDF V2000 simple data-field envelope boundary

`betelgeuze_engine_v2.molecular.sdf_v2000_data_fields` is an additive,
record-level envelope around the unchanged SDF V2000 parser 1.5 and writer
1.0. It does not add SD data items to `AllAtomSystem.metadata`, change the
base parser pedigree, or alter any existing profile, snapshot, receipt, or
golden hash. Instead, it binds the normalized delimiter-terminated base-parser
input and the canonical mol block emitted by the base writer to a separate
`betelgeuze.sdf_v2000_data_field_projection/1.0.0`.

The accepted projection starts after `M  END` and contains only canonical
simple named headers of the form `>  <FIELD_NAME>`. Field names use the
bounded `[A-Za-z0-9_][A-Za-z0-9_.-]*` subset. Items remain in source order;
duplicate names, empty values, multiline values, and leading or trailing
spaces in value lines are retained. Values are printable ASCII source text,
not SMILES, charge, role, preparation, path, command, URL, authorization, or
scientific-claim input. Canonical emission normalizes newline and header
layout, so raw CRLF spelling and arbitrary header spacing are outside the
projection.

The envelope admits at most 256 fields, 128 field-name characters, 64 value
lines per field, 2,048 value lines in total, 200 characters per value line,
and 384 KiB of data-field payload, all within the inherited full-record 2 MiB,
4,096-line, and 256-character line limits. A blank value terminator and final `$$$$` are
required whenever a field is present. Registry-number headers, header
suffixes, malformed or nested headers, missing terminators, a second record,
control or non-ASCII text, and every limit overflow fail closed before an
artifact is created.

The versioned corpus fixes five round-trip rows (including no-field legacy
parity, empty data, ordered duplicates, authority-like names, and concurrent
`M  CHG`/`M  ISO`) plus eight malformed-header, terminator, delimiter,
second-record, and non-ASCII failures. Its manifest binds every fixture,
projection, combined record state, base snapshot and topology, writer output,
receipt, and round-trip report digest. Resource-limit and stale/crosswire
boundaries remain in the focused generated tests so the tracked corpus stays
small and readable.

The factory-only ingest envelope stores the raw full-record SHA-256, the
normalized base-parser-input SHA-256, the canonical base-writer-output SHA-256,
a hidden canonical-system snapshot, base coverage, the
ordered field table, and its projection digest. Its writer receipt and
round-trip report additionally bind the base representable-state and topology
digests, emitted bytes, reparse, and stable second emission. Reordering two
fields or changing a value therefore changes the data-field and combined
record projections even when molecular topology is identical. These hashes
are tamper and crosswire evidence only. Source authentication, chemistry
interpretation, molecular preparation, parameterability, physics, runtime,
simulation, and claim authority remain false. General SDF stereochemistry,
arbitrary `M` property records, registry or other rich data headers, multiple
records, V3000, and arbitrary molecular context remain blocked, so neither
general SDF nor the all-format V2-1 exit condition is satisfied.

### V2-1 strict PDB canonical-writer boundary

`betelgeuze_engine_v2.molecular.pdb_writer` is a separate deterministic writer
for the exactly representable, parser-owned PDB subset. It is not a general PDB
or `AllAtomSystem` exporter. The v1.2 input must retain the current strict PDB
parser pedigree and self-consistent topology, observation, coverage, and
missingness receipts. Canonical bonds must be empty and alternate locations
must be absent. The unchanged base profile admits no source-reported
missingness. Version 1.2 additionally admits source-reported `REMARK 465/470`
claims only for exactly one coordinate model with normalized model ID 1. At
least one typed claim is required; implicit-model and explicit `MODEL 1`
source syntax normalize to the same semantic scope. NMR ranges, other model
IDs, multiple models, header-only evidence, duplicate claims, stale raw/report/
coverage/resource bindings, coordinate conflicts, and fixed-column overflow
fail closed. The existing optional parser-owned `CRYST1` record remains
admissible only when its metadata and canonical
cell are both present, its lengths and angles are exactly representable as
PDB F9.3 and F7.2 fields, and the live CPU `float64` cell vectors exactly match
the parser's trigonometric reconstruction in every binary64 value. The cell
must retain `(False, False, False)` periodic flags. An arbitrary `UnitCell`
cannot be inferred into `CRYST1`. Direct use of this unchanged base writer on
`CONECT` source state, selected altloc state, missingness outside the exact
single-model profile, and nonrepresentable or inconsistent `CRYST1` state are
typed failures rather than silently narrowed source state.

Within that boundary the writer preserves source atom order, `ATOM` versus
`HETATM`, exact atom-name alignment, residue and chain identity, insertion code,
segment ID, element, occupancy, B-factor, blank-unknown versus explicit PDB
formal charge, model IDs and coordinates, and parser-owned `TER` placement. A
single model with ID 1 is emitted without `MODEL`; other model sets use explicit
`MODEL`/`ENDMDL`. `TER` source line numbers are audit-only and excluded from the
projection, while their preceding atom, serial, residue identity, per-model
placement, and common model layout are preserved. Coordinates must round-trip
through PDB `F8.3`, and occupancy and B-factor through `F6.2`, with identical
IEEE-754 binary64 values. Width overflow, decimal rounding, known neutral zero,
isotope, atom map, partial charge, free-form mass, aromatic or stereo state,
extra metadata, stale parser receipts, and preparation or claim authority fail
closed. When present, `CRYST1` is emitted once before model or atom records and
preserves canonical length, angle, space-group, optional Z, and reconstructed
cell-vector state rather than raw source spelling or source record position.
Coverage continues to mark it as a crystallographic cell rather than a
simulation box, and non-P1 or blank symmetry identifiers remain explicitly
unexpanded.

The missingness profile reconstructs and validates the attached
`SourceReportedMissingnessReport`, every parser-owned raw REMARK record, typed
claim ordinal/category/model scope, fixed-column identity, and coordinate
absence relationship. Its source-independent semantic projection contains the
ordered residue and atom claim identities, normalized model `[1]`, exact
counts, preserve-only policy, and false completion/preparation/claim states. It
excludes source SHA, topology SHA, raw text, source line numbers, model-field
blank-versus-`1` spelling, REMARK 470 row grouping, and atom position within a
grouped source row. Canonical output is optional `CRYST1`, one REMARK 465
boilerplate/header plus ordered I5 residue rows, one REMARK 470
boilerplate/header plus one I4 atom claim per row, then coordinate/TER records
and `END`. Every physical record is printable 80-column ASCII, and canonical
missingness output is capped at 20,000 lines without truncation.

`round_trip_pdb_source` alone executes
`source -> canonical -> emitted PDB -> canonical`, compares a versioned
PDB-representable-state projection and canonical topology, and requires a
second emission to be byte-identical. Factory-only receipt, report, and
aggregate objects bind the hidden input snapshot, topology, projection, emitted
source, reparse, and re-emission. Missingness receipts additionally bind the
input raw report SHA, semantic schema/profile and SHA, evidence presence,
input/emitted REMARK line counts, and residue/atom claim counts. Round-trip
reports record source and reparsed raw report SHA values separately and claim
equality only for the semantic SHA. The aggregate stores canonical systems as immutable
snapshot bytes and returns fresh copies so caller tensor mutation cannot stale
the retained evidence. Raw whitespace and line endings, implicit-versus-explicit
single-model source syntax, resource counters, source and parser-observation
hashes, full snapshot, `system_id`, `source_id`, and dynamic provenance equality
are outside the projection. The hashes are tamper evidence, not source
authentication.

This closes only a bondless, no-altloc source-format projection with optional
exactly representable parser-owned `CRYST1` and the narrow single-model-ID1
source-reported missingness profile. The profile preserves only what the source
reported; it does not assess actual completeness, SEQRES/reference membership,
model or complete missing residues/atoms, or support altloc/assembly/multimodel
missingness. General PDB round-trip, including `CONECT` forms outside the exact
declaration-only envelope below and every covalent, coordination, bond-kind,
bond-order, or chemistry interpretation of `CONECT`, altloc, general
missingness, nonrepresentable `CRYST1`,
symmetry expansion, and periodic simulation semantics, plus general mmCIF and
general SMILES round-trip, remain blocked. PDB syntax support and round-trip
evidence do not establish bond-topology completeness, preparation, chemistry
support, parameterability, simulation readiness, scientific validity, runtime
eligibility, or claim authority.

#### Opt-in PDB `CONECT` source-declaration envelope

`betelgeuze_engine_v2.molecular.pdb_conect_declaration` is an additive opt-in
envelope around the unchanged PDB parser 1.8.0 and writer 1.2.0. It accepts
exactly one coordinate model normalized to model ID 1, implicit or explicit
`MODEL 1`, blank altloc state, no `CRYST1`, no source-reported missingness, and
at least one contiguous uppercase fixed-column `CONECT` suffix outside the
model and immediately before `END`. Each row retains one live source atom
serial and one through four contiguous live target-serial slots. Self
references, unknown or nonpositive serials, reserved-column content,
declarations inside a model, noncontiguous placement, multiple models, and
other model IDs fail closed. Explicit `MODEL 1` input normalizes to the base
writer's implicit single-model form; the base parser and writer entry points
and their direct behavior remain unchanged.

The declaration projection preserves directed row order, source serials,
target-slot order, duplicate target slots, row grouping, and directional
asymmetry. It neither collapses reciprocal rows nor interprets repeated target
occurrences as multiplicity or bond order. The carrier `AllAtomSystem` always
has `bonds == ()`, and coverage reports `bond_count == 0`. No canonical bond,
bond kind or order, covalence, coordination, disulfide, modified-residue,
chemistry, preparation, parameterability, physics, runtime, execution,
simulation, or claim authority is inferred. The declaration exists in the
envelope evidence rather than `AllAtomSystem`; extracting or serializing only
the bare `.system` intentionally loses it and the unchanged base writer emits
no `CONECT` rows.

Factory-only ingest, row, receipt, write-result, and round-trip artifacts bind
the normalized full source, declaration projection, source identifier, base
carrier source and canonical emission, detached canonical snapshot, topology,
base representable state, record state, output, reparse, and second emission.
Canonical output places printable 80-column declaration records immediately
before the 80-column `END` record and must be byte-stable on re-emission. Fixed
input/output byte and line, declaration-row, target-occurrence, projection,
and source-ID limits fail closed. A fixed five-round-trip/ten-failure corpus
binds manifest payload SHA-256
`c6346f7b046d157a70fb1629dfe3e7f3c13a4b9b079474961a613ec436c38a75`.
These SHA-256 bindings are tamper and crosswire evidence, not source
authentication. This envelope narrows one
source-layout loss only and does not make general PDB round-trip ready.

### V2-1 strict mmCIF selected-profile canonical-writer boundary

`betelgeuze_engine_v2.molecular.mmcif_writer` is a third deterministic writer
for narrow parser-owned source-format projections. Version 1.5 accepts only a
single coordinate model with model ID 1. The six unchanged legacy profiles
consist solely of one `_atom_site` loop and begin with the reviewed core 11
fields:
`_atom_site.group_pdb`, `_atom_site.id`, `_atom_site.type_symbol`,
`_atom_site.label_atom_id`, `_atom_site.label_comp_id`,
`_atom_site.label_asym_id`, `_atom_site.label_seq_id`, `_atom_site.cartn_x`,
`_atom_site.cartn_y`, `_atom_site.cartn_z`, and
`_atom_site.pdbx_pdb_model_num`. Exactly six ordered profiles are admitted:
core 11 alone; core 11 followed by `_atom_site.pdbx_formal_charge`; core 11
followed by `_atom_site.pdbx_pdb_ins_code`; core 11 followed by formal charge
and then insertion code; core 11 followed only by `_atom_site.occupancy`; or
core 11 followed by occupancy and then `_atom_site.b_iso_or_equiv`. Occupancy
is not combined with charge or insertion code, and B-factor is admitted only
as the second column of that exact occupancy/B-factor pair. Other orders,
middle insertion, unlisted combinations, and other optional fields fail
closed. The profile is selected from the source header
inventory, never inferred from row values. A present optional column containing
only `.` or `?` therefore remains in its 12- or 13-field profile. It is not a
general mmCIF or `AllAtomSystem` exporter.

One additional profile,
`pdbx_common_core21_complete_label_auth_entity_identity/1.0.0`, admits exactly
three loops and no other category: `_entity.id,_entity.type`,
`_struct_asym.id,_struct_asym.entity_id`, and the official-order common
21-column `_atom_site` surface. The latter includes blank-marker
`label_alt_id`, `label_entity_id`, insertion code, occupancy, B-factor, formal
charge, and a complete `auth_seq_id,auth_comp_id,auth_asym_id,auth_atom_id`
quartet. `_entity.type` is restricted to exact bare `polymer`, `non-polymer`,
or `water`. The writer canonicalizes category order to `_entity`,
`_struct_asym`, `_atom_site`, while preserving selected category row order and
raw bare token spelling. Category source-loop position remains layout and is
not part of the semantic projection.

The current parser pedigree, topology, observation, coverage, category
inventory, selection ledger, and empty missingness evidence must remain
self-consistent, and canonical bonds and cell state must be absent.
The versioned evidence surfaces are
`betelgeuze.mmcif_representable_state/1.5.0`,
`betelgeuze.mmcif_write_receipt/1.5.0`,
`betelgeuze.mmcif_round_trip_report/1.5.0`, and
`betelgeuze.mmcif_label_auth_entity_identity_projection/1.0.0`.

Within that boundary the declared representable-state projection preserves
atom, residue, and chain order and identity, parser-owned bare non-coordinate
token spelling, source atom-site ID and label identity, and every coordinate as
its exact IEEE-754 binary64 value. Coordinate token spelling is normalized with
deterministic representation rather than claimed as source text. Emission uses
deterministic CIF 1.1 syntax, and a reparse must recover the same declared
projection and topology before a second byte-identical emission is accepted.
For a formal-charge profile, bare single-line `.` and `?` missing markers and
bare integer spellings in the parser-owned `[-32767,32767]` range are preserved
exactly, including `+01`, `+0`, and `-0`. Canonical charge value, knownness, and
the duplicate source/interpretation markers must agree with that token. An
insertion-code profile likewise preserves each parser-owned bare printable-ASCII
token. Raw `.` and `?` both map to canonical blank insertion state but remain
distinct per-atom projection values, including when both spellings occur in one
canonical residue. Any other token must exactly equal the canonical
`Residue.insertion_code`. Header absence requires blank canonical insertion
state. Atom and first-model token payloads must match exactly. Receipt profile
and header count are live-checked, including charge-only, insertion-only, and
occupancy-only profiles with the same header count, plus the two distinct
13-header charge/insertion and occupancy/B-factor profiles. Token accounting
uses `2 + H * (N + 1)` for `H` selected headers and `N` rows.

The occupancy-only profile accepts bare `.` and `?`, or a bare, single-line,
uncertainty-free finite CIF number whose binary64 value is in `[0,1]`. Numeric
spellings such as `+0`, `-0`, `01.000`, `1.`, `.25`, and `1e0` are preserved
exactly. Numeric tokens are bound to canonical `Atom.occupancy` and an explicit
IEEE-754 binary64 hex value, so positive and negative zero remain distinct.
Raw `.` and `?` both map to canonical `None` but remain projection-distinct.
The value profile is
`bare_dot_question_or_uncertainty_free_finite_binary64_zero_to_one/1.0.0`.
The occupancy/B-factor pair uses the same occupancy contract. Its
`_atom_site.b_iso_or_equiv` value profile is
`bare_dot_question_or_uncertainty_free_finite_binary64/1.0.0`: bare `.` and `?`
both map to canonical `None` while remaining raw-distinct, and every other
token must be a bare, single-line, uncertainty-free finite CIF number. B-factor
has no numeric range restriction, so negative finite values are representable.
Its raw spelling, canonical `Atom.b_factor`, and exact IEEE-754 binary64 hex
must agree; `+0` and `-0` therefore remain bit-distinct. Standard uncertainty,
quoting, multiline or nonfinite values, occupancy or B-factor ESD, headerless
live occupancy or B-factor state, B-factor-only or reversed/middle placement,
charge/insertion/B-factor combinations, raw/canonical drift, and
atom/first-model payload drift fail closed.

For common-core21, label remains the only canonical identity namespace.
Every atom's `label_asym_id` must resolve through `_struct_asym` to an existing
`_entity`, and its `label_entity_id`, atom/residue/chain entity metadata, and
normalized source entity type must agree with that join. Complete auth fields
are preserved as source aliases and need not equal label atom, component,
chain, or sequence values. Auth component, asym, and sequence aliases must be
consistent within one label residue, while different label chains may share
one auth asym ID. A polymer requires a positive label sequence ID. A
non-polymer or water requires a raw `.` or `?` label sequence marker and a
nonmissing auth sequence alias; the writer independently recomputes the
parser's stable negative canonical residue-number carrier. Mixed `.` and `?`
markers within that same canonical residue remain row-distinct. `HETATM` is
preserved independently of entity type, so a source-declared polymer modified
residue remains polymer rather than being inferred as non-polymer.

The identity projection binds raw entity rows and normalized types, raw
struct-asym rows and joins, every atom's selected label/auth/entity and
measurement marker, residue sequence source and canonical number, chain
label/entity/auth-asym mapping, row order, and live category counts. Receipt,
report, and snapshot-backed aggregate bind its SHA separately from the full
representable-state SHA. Common-core21 token accounting is
`8 + 2E + 2S + 21(N + 1)` for `E` entity rows, `S` struct-asym rows, and `N`
atom rows. Writer caps are 4,096 entity rows, 16,384 struct-asym rows, 80,000
atom rows, two million tokens, 250,000 physical lines, 2,048 characters per
line, and 64 MiB output.

A separate opt-in
`betelgeuze_engine_v2.molecular.mmcif_assembly_envelope` envelope 1.0.0 closes
one exact biological-assembly round-trip surface without changing the base
parser 1.9.0 or writer 1.5.0. The source must contain the exact common-core21
`_entity`, `_struct_asym`, and `_atom_site` carrier plus one exact
`_pdbx_struct_assembly.id` loop, the three official generator fields
`assembly_id,oper_expression,asym_id_list`, and the operator ID, 3x3 matrix,
and three-vector fields in official order. Version 1 admits exactly one
assembly definition, at most 256 generator rows and 1,024 operator rows, one
model with ID 1, bare single-line tokens, and uncertainty-free finite operator
numbers. Input and canonical output are each capped at 64 MiB, source identity
at 4,096 UTF-8 bytes, each selected token at 2,048 characters, and each
canonical assembly row at 2,048 characters. Canonical-output size is
preflighted during parse so every admitted record remains writable. All
generator rows must target the
sole explicitly requested assembly. Scalar or mixed categories, extra headers,
altloc selection,
multimodel, cell/symmetry, missingness, topology categories, numeric standard
uncertainty, unknown operators/asym IDs, non-rigid transforms, or extra
category surfaces fail closed.

The envelope removes only the three assembly loops to obtain the unchanged
common-core21 carrier, runs the existing base writer on that deposited ASU,
then reinserts the canonical assembly loops before `_atom_site`. It reparses
the output with the same explicit `assembly_id`; it never serializes expanded
atoms as deposited rows and therefore cannot silently double-apply an
operator. The declaration projection binds exact headers and ordered source
tokens, the parser's right-to-left operation-expression semantics, parsed
generator sequences, and generator/operator/token limits. A separate
expanded-state projection binds canonical topology, atom and chain instance
order, source atom/asym pointers, assembly instance/copy-group IDs, the complete parser
assembly ledger, exact single model ID 1, angstrom coordinate units, an absent
periodic cell, and every transformed coordinate as exact IEEE-754 binary64
bytes. The carrier representable-state, declaration, expanded state,
source-ID hash, emitted bytes, receipt, reparse, and byte-identical second
emission are independently bound and cross-checked.

Admission independently rebuilds the expected plan from the raw generator and
operator rows. It checks exact generator sequences, composed binary64
rotation/translation values, deterministic `ASMnnnnnn` chain order, source
atom IDs and counts, and transformed coordinates against the live expanded
system. Every expanded atom's non-coordinate canonical state and source
metadata, every residue identity/sequence/insertion/entity field, and every
chain entity/source metadata field must be an exact carrier copy except for
the explicitly synthesized assembly indices and chain IDs.

Admission also pins envelope parser/writer 1.0.0, the base parser name/version and exact deposited-versus-
assembly operation ledgers, base writer version, carrier representable-state
schema, the provenance model-ID mirror, nonperiodic angstrom state, and
parser/coverage `preparation_ready=false` and `claim_safe=false` state. Nested declaration and expanded evidence is stored as immutable
canonical bytes. Receipt and report construction recomputes the exact expected
document; the aggregate requires the first receipt to bind the source ingest,
the first payload SHA to equal the reparsed full-source SHA, the second receipt
to bind that reparse, equal source identity and record state, and stable bytes.
Comment-only or source-ID crosswires and forged authority fields therefore fail
closed even when their semantic projections happen to match.

The fixed corpus contains identity, translated two-copy, and noncommuting
right-to-left composition positives plus an intentional numeric-uncertainty
failure. Its manifest payload SHA-256 is
`39a9d73e74ef71b7d740f4751edb35a78439eac059ec0f93f7b9eb5e40edffc5`.
Generated focused tests additionally hold exact surface, unknown-reference,
non-rigid transform, input/canonical-output/row/token resource caps, model/cell
semantic mirrors, stale evidence, and factory/crosswire
boundaries. This proves only deterministic preservation of one source-declared
rigid expansion. It does not authenticate the declaration, establish that the
assembly is biologically correct, expand crystallographic symmetry, interpret
PBC, or grant bond, chemistry, protonation, preparation, parameterability,
physics, runtime, simulation, execution, or claim authority. Other assembly
category/header/operator forms and general mmCIF remain blocked.

A separate opt-in
`betelgeuze_engine_v2.molecular.mmcif_nonpoly_identity` envelope 1.0 extends
only the source-reported non-polymer identity surface. It leaves the base
parser 1.9.0 and writer 1.5.0 contracts and versions unchanged; in particular,
calling the base parser directly with either added category still fails
closed. The envelope accepts exactly the common-core21 `_entity`,
`_struct_asym`, and `_atom_site` loops plus `_pdbx_entity_nonpoly` in one of
two exact header profiles, `entity_id,comp_id` or
`entity_id,name,comp_id`, and `_pdbx_nonpoly_scheme` in this official
10-field order: `asym_id,entity_id,mon_id,ndb_seq_num,pdb_seq_num`,
`auth_seq_num,pdb_mon_id,auth_mon_id,pdb_strand_id,pdb_ins_code`. Canonical
emission order is `_entity`, `_struct_asym`, `_pdbx_entity_nonpoly`,
`_pdbx_nonpoly_scheme`, `_atom_site`, followed by an exact reparse projection
check and byte-stable second emission.

The selected entity-nonpoly IDs must exactly cover source entities of type
`non-polymer` or `water`; their component IDs, struct-asym joins, and scheme
`asym_id,entity_id,mon_id` triples must agree with the selected entity and
atom-site label identity. Scheme keys `(asym_id,ndb_seq_num)` are unique, and
their per-triple row counts must match unique atom-site residue instances.
The remaining ndb, PDB, and auth values are preserved as source nomenclature
aliases: the envelope neither equates them with one another nor promotes one
to canonical identity. Optional entity-nonpoly `name` is likewise preserved
only as a source-reported name.

This envelope provides no water, solvent, ion, metal, ligand, cofactor, or
fragment-role authority and no chemical-component definition. It does not
interpret or validate chemistry, bond topology or order, coordination,
charge, protonation, preparation, parameterability, physics, runtime,
simulation, execution, or scientific claims. `_chem_comp`, `_struct_conn`,
chemical-component topology, ion or modified-residue categories, and every
other general mmCIF surface remain blocked in this identity-only envelope.
Only the separate exact component-topology envelope below admits its selected
three chemical-component loops.

A separate opt-in
`betelgeuze_engine_v2.molecular.mmcif_nonpoly_component_topology` envelope 1.0
adds source-reported non-polymer component topology without changing the base
parser 1.9.0, writer 1.5.0, or nonpoly-identity envelope 1.0. Its profile ID is
`strict_mmcif_nonpoly_component_topology_envelope/1.0.0`. It accepts exactly
the unchanged five-category nonpoly carrier plus the following three loops:

- `_chem_comp.id`, `.type`, `.pdbx_formal_charge`;
- `_chem_comp_atom.comp_id`, `.atom_id`, `.type_symbol`, `.charge`,
  `.pdbx_aromatic_flag`, `.pdbx_stereo_config`, `.pdbx_ordinal`;
- `_chem_comp_bond.comp_id`, `.atom_id_1`, `.atom_id_2`, `.value_order`,
  `.pdbx_aromatic_flag`, `.pdbx_stereo_config`, `.pdbx_ordinal`.

Canonical category order is `_entity`, `_struct_asym`, `_chem_comp`,
`_chem_comp_atom`, `_chem_comp_bond`, `_pdbx_entity_nonpoly`,
`_pdbx_nonpoly_scheme`, `_atom_site`. Scalar, mixed, additional-category, or
additional-header inputs fail closed rather than losing chemical state. The
selected source element domain is the organic subset
`H B C N O P S F Cl Br I`; atom and bond stereo configuration must be exact
`N`. Every selected nonpoly residue instance must contain exactly the template
atom-ID set for its
component, and each coordinate atom's source element must equal its template
element. Missing or extra instance atoms, duplicate component/atom/bond IDs or
ordinals, self-bonds, unknown endpoints, and template-to-instance join drift
are typed failures.

An already-known `_atom_site` formal charge must exactly equal
`_chem_comp_atom.charge`. A raw atom-site `.` or `?` charge instead resolves
from the explicit template charge and materializes as
`formal_charge_known=true`; the component's `_chem_comp.pdbx_formal_charge`
must equal the exact sum of all template atom charges. This is a deterministic
source-declaration fill and crosscheck, not independent charge assignment,
protonation, oxidation-state, or electronic-state inference.

Only exact `SING`, `DOUB`, `TRIP`, and `AROM` value-order tokens are mapped to
canonical bond orders `1.0`, `2.0`, `3.0`, and `1.5`, with aromatic flags
required to agree. The ordered template bond graph is expanded into every
complete matching residue instance and becomes real canonical `Bond` state,
not evidence stored beside a bondless carrier. Exact output reparse must
recover the same source projection, filled atom charges, materialized bond
rows, and canonical topology state; a second emission must be byte-identical.

Input, output, and projection are each capped at 64 MiB. The fixed row caps
are 4,096 `_chem_comp`, 80,000 `_chem_comp_atom`, and 120,000
`_chem_comp_bond` rows, and repeated component instances may materialize at
most 120,000 bonds; source IDs are capped at 4,096 UTF-8 bytes, and source
tokens and output lines at 2,048 characters. Factory-only projection,
topology-state, source-binding, write-receipt, round-trip-report, and aggregate
artifacts cross-bind full and normalized source, the unchanged carrier,
detached materialized snapshot, topology, source identity, output, reparse,
and stable second emission. Recomputed documents and external factory anchors
reject stale, tampered, crosswired, and coherent whole-artifact replacements.
Public carrier, receipt, report, and aggregate child accessors reconstruct fresh
detached artifacts, so caller-side mutation cannot poison the retained parent.
The public augmented system's `provenance.source_sha256` is always the exact raw
eight-category input digest; the distinct canonical-output digest is named in
provenance metadata and the source-binding artifact. The source-specific
source ID and detached carrier/base snapshot digests remain in source binding
and receipts, while the source-independent round-trip topology-state digest
compares only the normalized carrier, component projection, and materialized
canonical topology.
Their schemas are
`betelgeuze.mmcif_nonpoly_component_topology_projection/1.0.0`,
`betelgeuze.mmcif_nonpoly_component_topology_state/1.0.0`,
`betelgeuze.mmcif_nonpoly_component_topology_source_binding/1.0.0`,
`betelgeuze.mmcif_nonpoly_component_topology_write_receipt/1.0.0`, and
`betelgeuze.mmcif_nonpoly_component_topology_round_trip_report/1.0.0`.

The finalized augmented state has the exact parser pedigree
`betelgeuze.mmcif_nonpoly_component_topology_parser/1.0.0`. Materializing
template charges, aromatic flags, and bonds invalidates the identity carrier's
attached state digests, so the envelope refreshes both the canonical-topology
and parser-observation digests after all augmentation is complete. Generic
preparation recognizes this pedigree only when source format, exact parser
name, version `1.0.0`, raw-source digest, finalized canonical topology, and
refreshed observation digest agree. It does not accept a bare system that
merely copies the pedigree string.

The complete per-atom component marker mapping is an optional, format-local
field in the parser-observation document. Its component ID, template atom ID,
template ordinal, source-reported aromatic flag, and source-reported stereo
flag are therefore covered by the refreshed digest without changing hashes
for parsers that never emit this marker. A stale marker edit fails the digest;
even after a coherent rehash, each non-polymer or water instance must expose
the exact contiguous ordinal set `1..N` before any of its component-template
markers can count as preparation evidence.

The preparation marker check distinguishes a known atom-site charge that was
cross-checked against `_chem_comp_atom.charge` from a raw `.` or `?` marker
that was filled from that template. Both are reported under the bounded origin
`metadata_observed_mmcif_chem_comp_atom`, but each must satisfy its own raw
marker and template metadata rule. A hydrogen is source-observed only when its
original atom-site identity and the same finalized pedigree/observation chain
also agree. These observations are digest-bound source provenance, not source
authentication or independent charge, hydrogen, or valence assignment.

No new chemistry profile is introduced. The refreshed state can enter the
existing
`source_explicit_h_neutral_nonisotopic_stereo_unassigned_acyclic_saturated_`
`hydrocarbon_ingest_v1` applicability gate and the existing
`betelgeuze.profile_local_preparation_evidence/1.0.0` gate. The pinned positive
evidence is the exact single-methane component-topology fixture: it satisfies
the unchanged source-explicit-H, known-zero-charge, H/C-only, single-bond,
acyclic, H=1/C=4 graph rules and therefore has
`canonical_ingest_supported=true` and
`profile_local_evidence_satisfied=true`. The aromatic-benzene,
charged-ammonium, two-water, and mixed-polymer fixtures remain nonpositive
under those same rules. This one fixture is evidence for the existing profile,
not a new size ceiling or general mmCIF chemistry claim.

Even for the positive row, generic `ChemistryCoverageReport.chemistry_supported`
and generic `MolecularPreparationReport.preparation_ready` remain false.
Global molecular preparation, independent chemistry or valence validation,
protonation, parameterability, physics, runtime, execution, simulation, and
claim authority remain false or unassessed.

This profile establishes only the deterministic projection of one exact
source-reported organic-subset nonpoly component template into selected
canonical charge and intra-residue bonds. It does not authenticate the source
or independently validate chemistry, valence, aromaticity, stereo, component
role, protonation, generic or global preparation, parameterability, physics, runtime,
simulation, execution, or claims. `_struct_conn`, inter-residue and
cross-component links remain blocked in this eight-category envelope; only the
separate bounded profile below admits its exact selected covalent surface.
Coordination and metals, stereo other than `N`, other component bond orders,
polymer templates, composition with altloc, assembly, missingness, cell, or
multimodel state, and general mmCIF remain blocked. The envelope therefore does
not complete V2-1.

A separate opt-in
`betelgeuze_engine_v2.molecular.mmcif_nonpoly_covalent_struct_conn_topology`
envelope 1.0.0 composes the unchanged component-topology envelope 1.0.0 with
one exact `_struct_conn` loop. Its profile ID is
`strict_mmcif_nonpoly_covalent_struct_conn_topology_envelope/1.0.0`; its parser
and writer are both 1.0.0, and its finalized parser pedigree is
`betelgeuze.mmcif_nonpoly_covalent_struct_conn_topology_parser/1.0.0`.
Canonical category order is `_entity`, `_struct_asym`, `_chem_comp`,
`_chem_comp_atom`, `_chem_comp_bond`, `_pdbx_entity_nonpoly`,
`_pdbx_nonpoly_scheme`, `_struct_conn`, `_atom_site`.

The exact 23 `_struct_conn` fields are, in order, `id`, `conn_type_id`,
`ptnr1_label_asym_id`, `ptnr1_label_comp_id`, `ptnr1_label_seq_id`,
`ptnr1_label_atom_id`, `pdbx_ptnr1_label_alt_id`,
`pdbx_ptnr1_pdb_ins_code`, `ptnr1_symmetry`, `ptnr2_label_asym_id`,
`ptnr2_label_comp_id`, `ptnr2_label_seq_id`, `ptnr2_label_atom_id`,
`pdbx_ptnr2_label_alt_id`, `pdbx_ptnr2_pdb_ins_code`,
`ptnr1_auth_asym_id`, `ptnr1_auth_comp_id`, `ptnr1_auth_seq_id`,
`ptnr2_auth_asym_id`, `ptnr2_auth_comp_id`, `ptnr2_auth_seq_id`,
`ptnr2_symmetry`, and `pdbx_value_order`. No scalar, mixed, reordered,
additional-header, or additional-category surface is projected.

Each row must use exact bare `conn_type_id=covale`, explicit lowercase
`pdbx_value_order=sing`, `doub`, or `trip`, and exact identity symmetry `1_555`
for both partners. The selected nonpoly profile also requires label sequence
marker `.`, label-alt marker `.`, and PDB insertion marker `?` on both partners.
Each endpoint's complete label plus auth identity must join one unique atom in
the component-materialized carrier. Both endpoints must belong to
`non_polymer` or `water` residues, and the two endpoints must belong to
different residue instances. Missing, crosswired, ambiguous, same-residue,
self, duplicate/reversed, already materialized, polymer, or unsupported
endpoints fail closed.

Accepted `sing`, `doub`, and `trip` declarations become canonical inter-residue
`Bond` rows with orders `1.0`, `2.0`, and `3.0`, source
`mmcif_struct_conn_covale`, nonaromatic state, and a parser-observed row and
endpoint marker. This is bounded source-reported topology materialization, not
independent covalence, bond-order, valence, or chemistry validation. After the
inter-residue graph is complete, the envelope refreshes both the attached
canonical-topology digest and parser-observation digest under the exact new
pedigree; stale inherited component digests are never authority for the
augmented graph.

Factory-only projection, topology-state, source-binding, write-receipt,
round-trip-report, and aggregate artifacts bind the exact component carrier,
ordered 23-field rows, endpoint joins, materialized bonds, raw and canonical
source digests, detached system snapshot, refreshed topology and observation,
source ID, exact reparse, and byte-stable second emission. Input, output, and
projection are each capped at 64 MiB; `_struct_conn` rows and total materialized
bonds are each capped at 120,000; source IDs are capped at 4,096 UTF-8 bytes,
and source tokens and output lines at 2,048 characters. The fixed corpus
manifest at
`config/independent_engine_v2_v2_1_mmcif_nonpoly_covalent_struct_conn_topology_corpus.json`
binds three round trips, fifteen typed failures, strict-JSON and fixture-path
confinement, live-limit checks, and artifact crosswire evidence with payload
SHA-256 `2a8a2428ff39646f964af01773bc69b3f71cb03cfaba78b7ebb30ef2ba2d2704`.

The source-independent topology state contains the normalized component
carrier state, ordered `_struct_conn` projection, and final canonical topology;
the source ID and carrier/final detached snapshot digests are confined to the
source-binding and receipt chain. Public carrier, receipt, report, and aggregate
child accessors return fresh detached artifacts rather than internal aliases.

No new chemistry or preparation profile is introduced. The exact
`split_ethane_sing` fixture reconstructs the unchanged explicit-H, neutral,
nonisotopic, stereo-unassigned acyclic saturated H/C ethane graph across two
nonpoly residues. It therefore reaches only the existing
`source_explicit_h_neutral_nonisotopic_stereo_unassigned_acyclic_saturated_`
`hydrocarbon_ingest_v1` canonical-ingest gate and existing
`betelgeuze.profile_local_preparation_evidence/1.0.0` gate, with
`canonical_ingest_supported=true` and
`profile_local_evidence_satisfied=true`. Generic chemistry, generic and global
preparation, independent chemistry, valence or bond-order authority,
parameterability, physics, runtime, simulation, execution, and claim authority
remain false.

General `_struct_conn` remains blocked. In particular, `disulf`, `hydrog`,
`metalc`, salt/ionic interpretations, `quad`, omitted/default bond order,
nonidentity symmetry, coordination, polymer endpoints, and composition with
altloc, assembly, missingness, cell, or multimodel state are outside this
profile. General cross-component topology, general mmCIF, and V2-1 therefore
remain incomplete.

A separate opt-in
`betelgeuze_engine_v2.molecular.mmcif_polymer_sequence` envelope 1.0 preserves
only source-reported polymer entity sequence membership. It accepts either the
exact common-core21 carrier or that carrier composed with the unchanged
nonpoly-identity envelope, plus one exact loop in official field order:
`_entity_poly_seq.entity_id`, `.num`, `.mon_id`, `.hetero`. Canonical category
order is `_entity`, `_struct_asym`, `_entity_poly_seq`, `_atom_site` for the
base carrier and `_entity`, `_struct_asym`, `_entity_poly_seq`,
`_pdbx_entity_nonpoly`, `_pdbx_nonpoly_scheme`, `_atom_site` for the composed
carrier. The base parser 1.9.0, base writer 1.5.0, and nonpoly envelope 1.0
contracts and versions remain unchanged.

Every selected sequence row must join a source entity of exact type `polymer`;
every polymer entity is covered, sequence numbers are canonical positive
decimals contiguous from one, and every polymer `_atom_site` label
`(entity_id,label_seq_id,label_comp_id)` must join the declared membership.
Version 1 rejects duplicate positions and the general mmCIF
microheterogeneity surface; it accepts only bare `n` or `no` and emits
canonical `n`. Monomer codes remain opaque source tokens. A row with no
matching selected atom-site row is recorded only as an unobserved source
membership row, with any matching asym IDs derived as coordinate-presence
evidence. It is not an experimentally unobserved or missing-residue fact.

The ordered projection, canonical carrier state, optional existing nonpoly
record-state digest, detached molecular snapshot, full and normalized source,
receipt, reparse report, and byte-stable second emission are independently
bound and cross-checked. Standalone write artifacts rederive the canonical
payload fixed point and compare polymer, base-topology/representable, and
optional nonpoly state with their receipt; public evidence serialization also
revalidates fresh source, coverage, missingness, and composed-carrier bindings.
The bounded manifest pins seven round-trip and seven fail-closed cases with
payload SHA-256
`accee9d4f69cd85c069f2b58d515f0a5ea4b0bccce3d90b7422b54b295ced289`.
Limits are 64 MiB input/output, 100,000 sequence rows,
and 256 characters per selected identity token. `_entity_poly`,
`_pdbx_poly_seq_scheme`, reference-sequence, modified-residue, chemical-component,
and missingness categories remain blocked. Preservation establishes neither
reference-sequence equivalence nor sequence or coordinate completeness,
auth/label equivalence, modeled residue existence, modified-residue identity,
microheterogeneity chemistry, preparation, parameterability, physics, runtime,
simulation, execution, or claim authority.

A separate opt-in
`betelgeuze_engine_v2.molecular.mmcif_polymer_component_topology` envelope has
parser, writer, and envelope version 1.0.0. It accepts exactly seven
category-local loops with exact headers and emits them in canonical order:
`_entity`, `_struct_asym`, `_entity_poly_seq`, `_chem_comp`,
`_chem_comp_atom`, `_chem_comp_bond`, and `_atom_site`. Source category-order
variants normalize to that output. The unchanged four-category
`mmcif_polymer_sequence` child must independently accept and emit the carrier;
the wrapper does not broaden that child's grammar or membership semantics.

This is an exact fully observed, source-reported `L-peptide linking` polymer
component-topology profile. Every polymer entity is covered by sequence rows,
and every Cartesian product of an entity's selected asym IDs and sequence
positions must have exactly one coordinate residue instance. Each instance
must contain every atom in its selected component template exactly once and
no extra atom, with exact atom-name and element agreement. Component
definitions must exactly cover the unique sequence `mon_id` set, use the
quoted case-insensitive `L-peptide linking` type normalized to that canonical
spelling, close component formal charge against the sum of atom charges, and
use contiguous positive atom and bond ordinals. Selected elements are exactly
H, C, N, O, and S; atom stereo is the explicit source-reported N/R/S surface,
and bond stereo is exactly N. This source/template-relative coverage is not
CCD authentication, reference-sequence evidence, or general coordinate,
template, residue, atom, or chemistry completeness.

Known `_atom_site.pdbx_formal_charge` values are cross-checked against the
component atom charge, while `.` or `?` values are deterministically filled
from that template. Exact `SING`, `DOUB`, `TRIP`, and `AROM` declarations
materialize as canonical 1.0, 2.0, 3.0, and 1.5 bonds with matching aromatic
flags. Atom aromatic and N/R/S declarations are retained as source-reported
template metadata and parser-observation markers; N/R/S is not an independent
CIP assignment. Materialization is strictly intra-residue. The unchanged
carrier remains bondless, and no peptide, inter-residue, cross-component,
`_struct_conn`, coordination, or inferred bond is added.

The augmented detached system receives the exact new parser pedigree
`betelgeuze.mmcif_polymer_component_topology_parser/1.0.0`. After charge,
aromatic, stereo-marker, and bond materialization, the envelope refreshes both
the attached canonical-topology and parser-observation digests rather than
reusing the child's digests. Factory-only projection, topology-state,
source-binding, write-receipt, round-trip-report, and aggregate artifacts bind
the child carrier, ordered component rows, materialized topology, detached
snapshot, raw and canonical sources, source ID, exact emitted-source reparse,
and byte-stable second emission. Normalized carrier/component/topology
semantics remain source independent; raw-source, source-ID, canonical-output,
and detached-snapshot digests remain in the source-binding and receipt chain.

The preparation inventory recognizes that pedigree only when the complete
polymer-component contract remains self-consistent. It revalidates the exact
system profile and negative-authority fields, provenance marker and carrier
semantics, the exact 21-field `_atom_site` row shape and its label/auth,
source-record, element, sequence, altloc, insertion, and model identity against
the canonical atom/residue/chain state, the carrier category/resource/
missingness ledgers, every polymer atom's component/template ordinal, aromatic
and N/R/S marker, charge-fill or charge-crosscheck path, and every
intra-residue bond's component, endpoints, ordinal, order, aromaticity, stereo,
and source. The parser attaches and preparation recomputes
`betelgeuze.mmcif_polymer_component_topology_preparation_inventory_commitment/1.0.0`.
Stale observation state and topology/observation-only coherent rehashes with
that parser commitment left unchanged fail back to an unrecognized parser
pedigree. The commitment is unkeyed digest-bound tamper evidence, not source
authentication; an actor able to rewrite it together with every enclosing
digest is outside this check's threat model. A valid inventory classifies
explicit source hydrogen and `_chem_comp_atom` charge origins, but it does not
assess or promote preparation, parameterability, peptide-link chemistry,
physics, runtime, simulation, execution, or claim authority.

Input, output, and projection are each capped at 64 MiB; polymer sequence,
component, component-atom, component-bond, and expanded materialized-bond rows
are capped at 100,000, 4,096, 80,000, 120,000, and 120,000 respectively.
Source IDs are capped at 4,096 UTF-8 bytes, and selected tokens and canonical
output lines at 2,048 characters. The fixed three-round-trip/fifteen-failure
corpus is declared by
`config/independent_engine_v2_v2_1_mmcif_polymer_component_topology_corpus.json`
and binds canonical-manifest payload SHA-256
`6ae0e794e849b66f3d9f98717d3608e29e99852ed4853812692d6b54afea2808`.

This envelope establishes only exact source-reported, template-relative
topology for that selected fully observed surface. Modified residues and
terminal variants outside the exact selected templates, D-peptides, nucleic
acids, saccharides, CCD/reference authentication, general chemistry and
valence, peptide/inter-residue bonds, completion, preparation,
parameterability, physics, runtime, simulation, execution, claim authority,
general mmCIF, and V2-1 completion remain false or blocked.

A separate opt-in
`betelgeuze_engine_v2.molecular.mmcif_archive_standard_l_peptide_topology`
envelope has parser and writer version 1.0.0, parser pedigree
`betelgeuze.mmcif_archive_standard_l_peptide_topology_parser/1.0.0`, and
profile
`strict_mmcif_archive_standard_l_peptide_ALA_GLY_heavy_topology/1.0.0`.
It accepts exactly five categories and emits them in engine-selected canonical
order: `_entity`, `_entity_poly`, `_struct_asym`, `_entity_poly_seq`, and
`_atom_site`. The `_entity_poly` loop must have exactly `entity_id`, `type`,
`nstd_chirality`, `nstd_linkage`, and `nstd_monomer`; every row must contain
exact bare values `polypeptide(L)`, `no`, `no`, and `no` for the final four
fields. The unchanged exact polymer-sequence carrier must independently accept
the other four categories. No additional mmCIF category or explicit link
field is admitted.

This profile materializes only a sequence-implied, archive-standard ALA/GLY
heavy reference graph from a pinned engine-owned offline manifest. GLY uses
exact core roles N, CA, C, and O; ALA adds CB. A residue at its asym's final
sequence boundary, including a singleton, must additionally contain OXT,
whereas a residue with an outgoing sequence link must not contain OXT. The
manifest pins all intra-residue bonds. For each asym independently, consecutive
`_entity_poly_seq` positions add one exact single C(i)--N(i+1) reference bond,
so an n-residue asym has exactly n-1 such links. Links never cross asym IDs.
Atom identity is an exact rule-name join. Coordinate distance and auth aliases
do not select links, and coordinate or auth-value changes therefore cannot
change the materialized graph.

The immutable rule manifest schema is
`betelgeuze.standard_l_peptide_heavy_topology_rule_manifest/1.0.0`, with
SHA-256
`4d941815d26431a5de9bd74b4860f84ce39232e7123ee87b3b61a104457eb244`.
Its recorded official CCD provenance is ALA from
`https://files.rcsb.org/ligands/download/ALA.cif`, 6,071 bytes, SHA-256
`6d32b34d4f7b3ddf0cd3dff3f98ddaf7649bc5303ff9a8bd95ba62283f47a1ca`,
component type `L-PEPTIDE LINKING`; and GLY from
`https://files.rcsb.org/ligands/download/GLY.cif`, 5,615 bytes, SHA-256
`c49458946b0ebc057db6ad0a4e1557a1caaed4c80a203accd458efddccbf92ff`,
component type `PEPTIDE LINKING` rather than `L-PEPTIDE LINKING`. Both records
pin initial date 1999-07-08, modified date 2024-09-27, and release status REL.
Those downloaded-file hashes are tamper evidence, not source authentication;
runtime never fetches CCD data and instead recomputes the engine-owned manifest
hash before use.

The projection, state, source-binding, write-receipt, and round-trip-report
schemas are respectively
`betelgeuze.mmcif_archive_standard_l_peptide_topology_projection/1.0.0`,
`betelgeuze.mmcif_archive_standard_l_peptide_topology_state/1.0.0`,
`betelgeuze.mmcif_archive_standard_l_peptide_topology_source_binding/1.0.0`,
`betelgeuze.mmcif_archive_standard_l_peptide_topology_write_receipt/1.0.0`,
and
`betelgeuze.mmcif_archive_standard_l_peptide_topology_round_trip_report/1.0.0`.
Factory-only artifacts bind the ordered projection, rule manifest, final graph,
detached system, source identity, canonical emission, exact reparse, and stable
second emission across artifacts. After graph materialization, the parser
refreshes both canonical-topology and parser-observation digests.

The parser provenance marker also binds schema and SHA for
`betelgeuze.mmcif_archive_standard_l_peptide_topology_preparation_inventory_commitment/1.0.0`.
The preparation bridge recognizes this pedigree only after semantically
recomputing the exact rule manifest, carrier ledger, exact system/chain/residue/
atom/bond marker-key sets, graph, and commitment. Leaving the parser commitment
unchanged while coherently rehashing only topology and observation state fails
closed. All five fixed positive inputs have a recognized preparation parser
pedigree and self-consistent parser observation, but canonical applicability
remains `unsupported` and preparation remains `incomplete`; none is classified
`invalid`, and no preparation or execution promotion follows.

Input and output are capped at 64 MiB, source IDs at 4,096 UTF-8 bytes,
selected tokens at 2,048 characters, atom rows at 80,000, and materialized
bonds at 300,000. The fixed five-positive/twenty-four-failure corpus manifest
`config/independent_engine_v2_v2_1_mmcif_archive_standard_l_peptide_topology_corpus.json`
binds canonical payload SHA-256
`58377d1b60a493e62a53af8250c912b49b7475e76d41316ee8d2380ffaf967de`.

The three positive statements are narrowly limited to a matching engine rule
manifest, materialized sequence-implied ALA/GLY heavy reference topology, and
materialized same-asym sequence-adjacent peptide reference bonds. This does not
establish source authentication or observed covalence, validate peptide
geometry, detect or exclude coordinate or chemical chain breaks, assign formal
charge, hydrogens, protonation, or stereochemistry, support modified or
nonstandard monomers, establish generic chemistry, preparation, or
parameterability, support physics/runtime/simulation, authorize execution or
claims, complete general mmCIF topology or round-trip evidence, establish
all-format readiness, or complete V2-1.

A second opt-in wrapper,
`betelgeuze_engine_v2.molecular.mmcif_polymer_component_terminal_leaving_policy`,
has envelope, parser, and writer version 1.0.0 and profile
`strict_mmcif_polymer_component_terminal_leaving_annotation_envelope/1.0.0`.
It retains the same exact seven categories and canonical category order as the
polymer component-topology child, but requires this exact official-order
eleven-field `_chem_comp_atom` header: `comp_id`, `atom_id`, `type_symbol`,
`charge`, `pdbx_aromatic_flag`, `pdbx_leaving_atom_flag`,
`pdbx_stereo_config`, `pdbx_backbone_atom_flag`,
`pdbx_n_terminal_atom_flag`, `pdbx_c_terminal_atom_flag`, and `pdbx_ordinal`.
The wrapper projects zero-based columns 0, 1, 2, 3, 4, 6, and 10 while
preserving the selected token values and column order to reconstruct the
unchanged seven-field child input.
That child must independently parse and canonically emit before the wrapper is
accepted.
At each source and canonical-reparse stage, the wrapper performs a second exact
child parse. A private proof compares parser pedigree, component projection,
topology state, augmented topology, source binding, serialized system bytes,
snapshot, parser observation, preparation-inventory commitment, and canonical
child emission. The existing wrapper state binds the exact twelve-field
required/pass-and-comparison gate map; the source binding binds that same map,
the private proof SHA-256, and the state hash. The policy and round-trip reports
consume those computed gates. Any mismatch fails closed with a typed error.
Source-stage and canonical-reparse child proofs and
parser-observation values are not required to equal because canonical source
and provenance normalization legitimately change their source binding.

The four added fields admit only exact bare Y/N source annotations. They are
preserved in an ordered projection and are never inferred from atom names,
coordinates, distances, valence, component names, or sequence position. The
versioned rules schema
`betelgeuze.mmcif_polymer_terminal_leaving_rules/1.0.0` also derives only the
per-asym sequence-position roles `singleton`, `n_sequence_boundary`,
`internal`, and `c_sequence_boundary`. These roles are positional boundaries,
not chemical termini, retained or leaving atom decisions, reaction endpoints,
or peptide-link assignments. Reuse of one component template at both internal
and boundary positions does not synthesize or select a terminal variant.
The canonical rules payload binds SHA-256
`9235a365be1ee9f0189f94f37ed3317ff14903f0469d41f6fea2a6d2678f92b1`.

The wrapper mints no system parser pedigree. Its `AllAtomSystem` snapshot,
canonical topology, parser observation, exact
`betelgeuze.mmcif_polymer_component_topology_parser/1.0.0` pedigree, and
`betelgeuze.mmcif_polymer_component_topology_preparation_inventory_commitment/1.0.0`
schema and value are byte-identical to the independently projected child.
Annotation projection, rules and policy reports, child state and source
binding, wrapper source binding, receipt, reparse, and stable second emission
are bound only in factory artifacts. Serializing the bare child-owned system
therefore intentionally loses the wrapper annotations and grants no wrapper
authority.

The wrapper inherits the child limits of 100,000 polymer-sequence rows, 4,096
components, 80,000 component atoms, 120,000 component bonds, and 120,000
materialized child bonds. Input, output, and projection payloads are each
capped at 64 MiB; source IDs at 4,096 UTF-8 bytes; and tokens and canonical
output lines at 2,048 characters. The fixed three-round-trip/twenty-failure
corpus manifest
`config/independent_engine_v2_v2_1_mmcif_polymer_component_terminal_leaving_policy_corpus.json`
binds canonical-manifest payload SHA-256
`3cfc5731f9943479f7246baf17148ac52a52b3557b35a584a14a6e606a579a3d`.

This is source-reported annotation inventory only. It does not assess a
chemical terminal state, assign terminal chemistry, apply a leaving-atom
policy, remove H/H2/OXT or any other atom, infer a C--N endpoint from names or
geometry, or materialize a peptide, inter-residue, or cross-component bond.
Generic chemistry, generic or global preparation, parameterability, physics,
runtime, simulation, execution, claim authority, general mmCIF, and V2-1
completion remain false or blocked.

A distinct non-writer transform,
`betelgeuze_engine_v2.molecular.mmcif_standard_l_peptide_neutral_preparation`,
implements version 1.0.0 of profile
`strict_mmcif_ALA_GLY_source_explicit_CCD_neutral_linkage_preparation/1.0.0`
under the literal policy
`exact_ALA_GLY_source_explicit_CCD_neutral_linkage_policy/1.0.0`. It accepts
one exact eight-category source in this order: `_entity`, `_entity_poly`,
`_struct_asym`, `_entity_poly_seq`, `_chem_comp`, `_chem_comp_atom`,
`_chem_comp_bond`, and `_atom_site`. The same raw source is independently
reprojected into the exact seven-category terminal/leaving child and the exact
five-category archive-heavy child before any transform is accepted. This is a
profile-local preparation transform, not another mmCIF envelope, parser-owned
writer, write receipt, or canonical source round-trip contract.

The pinned preparation-rule manifest schema is
`betelgeuze.standard_l_peptide_neutral_linkage_preparation_rule_manifest/1.0.0`
with SHA-256
`daa2beb6648d2749204093bfd0db5dd316cb38557b29890054ddc54c73193d7f`.
The complete source templates contain 13 atoms and 12 bonds for ALA and 10
atoms and 9 bonds for GLY. Every source formal charge must be known zero; ALA
CA must carry source stereo `S`, while the other selected source stereo markers
are `N`. The outer source uses the child-normalized quoted component type
`L-peptide linking` for both components. The official GLY CCD provenance says
`PEPTIDE LINKING`, so this contract does not claim that the normalized outer
component-type token is byte-exact official GLY CCD text.

Sequence-position policy deletes no atoms from a `singleton`; deletes OXT and
HXT from an `n_sequence_boundary`; deletes H2, OXT, and HXT from an `internal`
residue; and deletes H2 from a `c_sequence_boundary`. All remaining atoms and
coordinates are retained from source without generated hydrogens or coordinate
construction. Only exact consecutive positions within one asym receive a
single C(i)--N(i+1) bond. For `L` links, the transform must delete exactly
`3L` source atoms and `3L` source bonds, add `L` peptide bonds, and finish with
the source bond count minus `2L`. The induced prepared heavy graph and exact
binary64 retained coordinates must match the independently projected
archive-heavy child.

Factory-only state, source-binding, report, atom-mapping, and exact-instance
parameter-requirement inventory artifacts bind the raw source, both child
projections, transformed snapshot, topology and observation digests, mapping,
and heavy crosscheck. `verify_replay()` recomputes those artifacts from the
retained raw source and requires byte-exact state equality; it is replay
evidence, not serialization round-trip evidence. The parameter inventory lists
atom, bond, angle, proper-torsion, nonbonded, and partial-charge requirements
only. It does not enumerate improper or CMAP terms, supplies no force-field
types or production parameters, and its
production parameter-set status remains missing.
The fixed four-positive/sixteen-failure corpus manifest
`config/independent_engine_v2_v2_1_mmcif_standard_l_peptide_neutral_preparation_corpus.json`
binds canonical payload SHA-256
`c5c0ab935305c8d15fb2868c8327d38622de85fe84b8426e32d14be88ff3c20d`.

Only the exact profile fields `profile_molecular_preparation_assessed` and
`profile_molecular_preparation_ready` are promoted. Generic or global
preparation, environmental pH or protonation correctness, generic hydrogen
completion, independent tautomer/aromaticity/CIP/electronic structure,
modified or nonstandard residues, water/ion/metal/cofactor roles,
parameterability, physics, energy, force, minimization, runtime, simulation,
execution, claims, general mmCIF/all-format round-trip readiness, and V2-1
completion all remain false or blocked.

A second non-writer transform,
`betelgeuze_engine_v2.molecular.mmcif_standard_l_peptide_heavy_completion`,
implements version 1.0.0 of profile
`strict_mmcif_ALA_GLY_heavy_complete_fixed_neutral_microstate_completion/1.0.0`
under policy
`exact_ALA_GLY_heavy_to_fixed_neutral_microstate_completion_policy/1.0.0`.
It accepts only the exact five-category archive-standard ALA/GLY heavy source
and requires that child to accept the same raw bytes independently. The
engine-owned completion-rule manifest schema
`betelgeuze.standard_l_peptide_heavy_to_fixed_neutral_all_atom_completion_rule_manifest/1.0.0`
is pinned at SHA-256
`eed2b432c6a4b916370e14d922830a5eeb9f531acc579c94b7e823b8949810c6`.
It contains the official ALA/GLY CCD ideal coordinate decimal tokens, atom
ordinals, hydrogen-parent rows, role inventories, and provenance pins used by
the transform; the pins are offline tamper evidence, not source authentication.

Admission preserves every source heavy coordinate bit-for-bit in binary64 and
requires each active heavy bond to be within 0.20 angstrom of its pinned ideal
length. Same-asym adjacent C--N links must be in the inclusive 1.15--1.55
angstrom interval. Each residue must have a nondegenerate N--CA--C frame with
normalized sine at least 0.05, and ALA must retain the positive N/C/CB-about-CA
orientation with normalized absolute triple product at least 0.05. These are
bounded profile admission checks, not scientific geometry validation: angles,
omega, clashes, conformational quality, and energetics are not assessed.

For each admitted role, the transform rotates the pinned parent-relative ideal
hydrogen vector from the ideal N--CA--C frame into the source frame and anchors
it at the retained source parent. Atom and bond order are deterministic.
Mapping rows partition every output atom into `source_retained` or
`profile_generated` and bind each generated H to its parent, rule atom ordinal,
and rule-manifest SHA. All output formal charges are profile-assigned known
zero, and ALA CA receives profile-owned `S`; this fixed neutral microstate is
not environmental pH or protonation correctness and is not independent CIP.

Factory-only state, source-binding, report, mapping, and exact-instance
parameter-requirement artifacts bind the raw source, archive child, completed
snapshot, topology and observation digests, and rule manifest. Raw-source
`verify_replay()` is supported, but there is no outer writer or serialization
round-trip claim. Atom, bond, angle, proper, nonbonded, and partial-charge
requirements are enumerated without duplicates; improper and CMAP terms are
not enumerated and production parameters remain missing. The fixed
four-positive/thirteen-failure corpus manifest
`config/independent_engine_v2_v2_1_mmcif_standard_l_peptide_heavy_completion_corpus.json`
binds canonical payload SHA-256
`7fed000628174709fb5cd30955239f65e9395e981d3a34422fdcdb3a932bfb1f`.
Only profile-local heavy-completion and molecular-preparation readiness are
true. Generic/global preparation, source authentication, generic hydrogen
completion, pH/protonation correctness, parameterability, physics, runtime,
energy, force, minimization, simulation, execution, claim authority, general
mmCIF/all-format readiness, and V2-1 completion remain false or blocked.

A separate opt-in
`betelgeuze_engine_v2.molecular.mmcif_polymer_sequence_nonpoly_component_topology`
composition envelope has parser, writer, and envelope version 1.0.0. Its
profile ID is
`strict_mmcif_polymer_sequence_nonpoly_component_topology_composition_envelope/1.0.0`,
and its state schema is
`betelgeuze.mmcif_polymer_sequence_nonpoly_component_topology_state/1.0.0`.
The wrapper does not mint a new system parser pedigree.
It accepts exactly this nine-category set and emits canonical order: `_entity`,
`_struct_asym`, `_entity_poly_seq`, `_chem_comp`, `_chem_comp_atom`,
`_chem_comp_bond`, `_pdbx_entity_nonpoly`, `_pdbx_nonpoly_scheme`, and
`_atom_site`. Input category-order variants normalize to the same child sources
and canonical output.

The parser splits that surface into two complete child inputs rather than
reimplementing either child: the exact eight-category nonpoly
component-topology child and the exact six-category polymer-sequence plus
nonpoly-identity child. Both children must independently accept and emit their
own canonical projection. The composition then cross-binds the shared nonpoly
identity projection and record state, base topology and representable state,
and data block in its source-independent semantic state. The `_entity`, `_struct_asym`,
`_pdbx_entity_nonpoly`, `_pdbx_nonpoly_scheme`, and `_atom_site` loops and the
shared nonpoly writer payload recovered from the two child writers must be
byte-exact. Child provenance differs, so this contract does not assert direct
equality of child snapshot digests.

The component child exclusively owns the detached `AllAtomSystem`; its exact
component-carrier system pedigree
`betelgeuze.mmcif_nonpoly_component_topology_parser/1.0.0` is retained. Polymer
sequence rows remain ordered source evidence only and do not materialize
polymer templates or chemistry into that system. Factory-only state,
source-binding, receipt, and round-trip artifacts bind the full source, source
ID, child source bindings, component snapshot, both child semantic states, the
shared carrier, and the canonical output. Public nested artifacts are fresh
detached reconstructions. Exact canonical reparse must recover both child
states and the composition state, the emitted payload must equal the reparsed
raw source byte-for-byte, and the second emission must be byte-identical. Input
and output are each capped at 64 MiB, polymer-sequence rows at 100,000,
component rows at 4,096, component-atom rows at 80,000, component-bond rows at
120,000, selected tokens at 2,048 characters, and source IDs at 4,096 UTF-8
bytes.
The fixed two-positive/six-deterministic-failure corpus is declared by
`config/independent_engine_v2_v2_1_mmcif_polymer_sequence_nonpoly_component_topology_composition_corpus.json`
with canonical-manifest payload SHA-256
`6ac10b99e058134bdcbf1739afd7d2d719dd15667890530e9c716beb14592e69`.

This profile closes only the selected composition gap. Polymer templates,
modified-residue chemistry, reference-sequence equivalence or completeness,
coordinate completeness and missingness, `_struct_conn`, altloc, assembly,
cell, multimodel composition, generic or global preparation, parameterability,
physics, runtime, simulation, execution, claim authority, general mmCIF, and
V2-1 completion all remain false or blocked.

A separate downstream opt-in module,
`betelgeuze_engine_v2.molecular.mmcif_unobserved_residues`, defines envelope
1.0 for one exact source-reported residue-level missingness surface. Its carrier
must already satisfy the polymer-sequence envelope, either alone or composed
with the existing nonpoly-identity envelope. The selected loop has the exact
official 11-field order `id,polymer_flag,occupancy_flag,pdb_model_num,`
`auth_asym_id,auth_comp_id,auth_seq_id,pdb_ins_code,label_asym_id,`
`label_comp_id,label_seq_id`. Version 1 accepts only bare ASCII rows with
`polymer_flag=Y`, `occupancy_flag=1`, and model `1`.

Every selected label identity must resolve through `_struct_asym` to a polymer
entity and join the exact `_entity_poly_seq(entity_id,num,mon_id)` member. A
claim is rejected if the same `(label_asym_id,label_seq_id,label_comp_id)` is
present in selected coordinates; source row IDs and semantic residue keys must
also be unique. Canonical order is `_entity`, `_struct_asym`,
`_entity_poly_seq`, `_pdbx_unobs_or_zero_occ_residues`, `_atom_site`, with the
two existing nonpoly categories inserted before the selected missingness loop
for the composed seven-category carrier.

The artifact graph binds the ordered claim projection, carrier and optional
nonpoly record state, topology, detached snapshot, source and source-ID
bindings, both write receipts, reparse state, and stable re-emission. Public
serialization recomputes canonical output and rejects coherent payload/receipt
replacement, noncanonical JSON evidence, same-payload/different-source-ID
crosswires, and nested aggregate type tamper. Raw source and reparsed
missingness-report SHA values are recorded separately: normalization changes
layout, so raw-report SHA equality is explicitly not claimed. Limits are 64
MiB input/output, 20,000 selected rows, 256 characters per selected identity
token, and 4,096 UTF-8 bytes for `source_id`. The six-round-trip/fourteen-failure
manifest payload SHA-256 is
`003b7f870a988fd39f83ca23302edeef2cd7d7123ea72a1c0508c8ee202b4750`.

This proves only that an ordered source-reported unobserved polymer-residue
claim survives this selected semantic projection. It does not authenticate the
source or establish an actual missing-residue fact, reference-sequence or
coordinate completeness, auth-label equivalence, modeled/modified-residue
identity, chemistry, preparation, parameterability, physics, runtime,
simulation, execution, or claim authority. Atom-level
`_pdbx_unobs_or_zero_occ_atoms`, `occupancy_flag=0` zero-occupancy semantics,
other models, general missingness, and raw-layout round-trip remain blocked.

A fourth opt-in module,
`betelgeuze_engine_v2.molecular.mmcif_unobserved_atoms`, defines envelope 1.0
for one exact source-reported atom-level missingness surface. It composes the
same polymer-sequence carrier, with or without the existing nonpoly-identity
carrier, and accepts one exact official-order 14-field loop:
`id,polymer_flag,occupancy_flag,pdb_model_num,auth_asym_id,auth_comp_id,`
`auth_seq_id,pdb_ins_code,auth_atom_id,label_alt_id,label_asym_id,`
`label_comp_id,label_seq_id,label_atom_id`. Version 1 requires bare ASCII,
`polymer_flag=Y`, `occupancy_flag=1`, model `1`, and a raw `.` or `?`
`label_alt_id`. Source row IDs are canonical positive decimals no greater than
`2^53-1`. Row IDs and fully qualified semantic atom keys are unique, and a
simultaneous residue-missingness loop fails closed.

Each label identity must resolve through `_struct_asym` to an exact polymer
entity and join `_entity_poly_seq(entity_id,num,mon_id)`. The selected model-1
coordinates must contain the exact parent residue under label asym, sequence,
component, and normalized insertion code, while the exact label atom under the
normalized altloc must be absent. Raw `.` and `?` insertion and altloc markers
remain projection-distinct but both normalize to blank for coordinate checks.
Auth values remain opaque aliases. The envelope neither consults a residue
template nor validates atom nomenclature. It also verifies the base
missingness claim row by row: category, ordinal, model, label residue and atom
identity, normalized insertion and altloc, raw token payload, controls, and
source row ID must agree, with zero residue claims and exactly one base atom
claim per selected row.

Canonical emission orders `_entity`, `_struct_asym`, `_entity_poly_seq`, the
optional two nonpoly categories, atom missingness, and `_atom_site`. The
artifact graph binds ordered projection, carrier and optional nonpoly state,
topology, detached snapshot, full and normalized source, source ID, source and
reparsed base missingness reports, both receipts, aggregate, and byte-stable
second emission. Raw source and canonical reparse missingness-report hashes are
recorded separately and equality is not claimed because layout is normalized.

Input and output are capped at 64 MiB, selected identity tokens at 256
characters, and `source_id` at 4,096 UTF-8 bytes. The unchanged base parser
preserves at most 40,000 missingness values; at 14 values per row the real v1
row cap is therefore `floor(40000/14)=2,857`, and row 2,858 fails closed.
Canonical rows longer than the CIF 1.1 2,048-character line cap are emitted one
token per line. The six-round-trip/ten-failure corpus manifest payload SHA-256
is `82081b2061386e90e2bf5e7ec94e5e6ab43d03c534d709dfbb76ffe7dbe33f7f`.
This proves only preservation of an ordered source-reported
unobserved-atom claim. It does not establish an actual missing-atom fact,
reference, sequence, or coordinate completeness, auth-label equivalence,
modeled atom presence, residue-template or atom-name validity, completion,
modified-residue identity, chemistry, preparation, parameterability, physics,
runtime, simulation, execution, or claim authority. Zero-occupancy rows,
nonpoly atom claims, nonblank altlocs, other models, general atom missingness,
and raw-layout round-trip remain blocked.

A fifth opt-in module,
`betelgeuze_engine_v2.molecular.mmcif_zero_occupancy_residues`, defines an
additive envelope 1.0 for the `occupancy_flag=0` branch of the exact official
11-field `_pdbx_unobs_or_zero_occ_residues` loop. It composes only the unchanged
polymer-sequence carrier, optionally already composed with the unchanged
nonpoly-identity carrier. The base mmCIF parser 1.9.0, base writer 1.5.0,
polymer-sequence envelope 1.0, nonpoly-identity envelope 1.0, and both existing
`occupancy_flag=1` unobserved envelopes keep their behavior and versions.
Version 1 accepts only bare ASCII `polymer_flag=Y`, `occupancy_flag=0`, model-1
polymer declarations whose label tuple joins `_struct_asym` and the exact
`_entity_poly_seq` member. Source row IDs and normalized-insertion-qualified
semantic residue identities are unique; the atom-level zero-occupancy category,
or residue and atom zero-occupancy categories together, fail closed.

Each selected residue declaration must have at least one matching model-1
common-core21 `_atom_site` row under label asym, positive label sequence,
component, and normalized insertion code. Every matching row, including every
matching atom or alternate row, must carry a bare, uncertainty-free, finite
numeric occupancy whose exact numeric value is zero; absence, a missing or
non-numeric value, or any nonzero match fails closed. This is a selected-source
consistency crosscheck, not an inference that zero occupancy means a missing
residue. The unchanged base parser must independently preserve exactly `N`
residue evidence rows and `N` zero-occupancy-residue rows, zero atom rows and
zero zero-occupancy-atom rows, zero extension items, and zero missing-residue
and missing-atom claims. That preserve-only metadata receives its own digest in
the record state, source binding, receipts, and round-trip report.

A sixth opt-in module,
`betelgeuze_engine_v2.molecular.mmcif_zero_occupancy_atoms`, applies the same
additive rule to the exact official 14-field
`_pdbx_unobs_or_zero_occ_atoms` loop. It accepts only bare
`polymer_flag=Y`, `occupancy_flag=0`, model-1 polymer declarations with raw
`.` or `?` `label_alt_id`. The parent residue must exist under the exact label
identity and normalized insertion marker, the exact label atom under the
normalized blank altloc must itself be present, and every matching atom-site
occupancy must be an exact finite numeric zero. Missing parent or atom rows,
unavailable occupancy, any nonzero match, nonblank altloc, duplicate semantic
identity, or a simultaneous residue zero-occupancy loop fails closed. The base
preserve-only metadata must contain exactly `N` atom and zero-occupancy-atom
rows, zero residue rows, zero extension items, and zero missing claims.

Both envelopes emit the declaration category immediately before `_atom_site`
in canonical five- or seven-category carrier order, bind ordered declaration,
polymer and optional nonpoly state, topology, detached snapshot, source and
source ID, base preserve-only metadata, receipts, exact output reparse, and a
byte-stable second emission. Input is capped at 64 MiB, selected identity
tokens at 256 characters, and `source_id` at 4,096 UTF-8 bytes. The unchanged
base parser's 40,000 preserved-value limit gives residue and atom row caps of
`floor(40000/11)=3,636` and `floor(40000/14)=2,857`. The shared six-round-trip,
nineteen-failure corpus is pinned by canonical manifest payload SHA-256
`96564c7b9d4d70eed7ac65188783a6de0acf33a01ac18b7e0559afb28f61ae40`.

These envelopes preserve only ordered source-reported zero-occupancy
declarations plus the exact selected-coordinate numeric-zero crosscheck. They
do not authenticate the source or establish actual missing-atom or
missing-residue facts, occupancy populations or weighting, alternate-location
populations, coordinate or sequence completeness, refinement validity,
reference/auth equivalence, chemistry, preparation, parameterability, physics,
runtime, simulation, execution, or claim authority. They do not make the base
parser/writer a general mmCIF implementation and do not satisfy the V2-1 or
commercial exit conditions.

Raw whitespace, comments, and the exact single- versus double-quote delimiter
are layout and are not projected. The optional name's quoted-versus-bare token
class is projection-bound because it distinguishes a quoted literal from a
bare missing marker. Full source/base bytes and detached serialized system
snapshots bind their own hashes, while source/system identifiers, dynamic
parser-observation hashes, and full-snapshot equality between the source and
reparse artifacts are not identity claims.

Within the unchanged base parser/writer contract, non-`_atom_site` categories
outside the exact common-core21 `_entity` and `_struct_asym` loops, any
`_atom_site` field set other than the six legacy profiles or common-core21,
partial auth state, unsupported entity types, canonical bonds,
alternate-location or assembly selection, source-reported unobserved or
zero-occupancy declarations outside the four selected residue- and atom-level
envelopes, cell state, and multiple models fail with
typed writer errors rather than being
omitted. The two nonpoly categories are admitted only by the separate opt-in
identity envelope; the exact three component-topology categories and
materialized canonical bonds are admitted only by their separate eight-category
opt-in envelope. The selected 23-field `_struct_conn` loop and its materialized
inter-residue bonds are admitted only by the separate nine-category covalent
opt-in envelope. `_entity_poly_seq` is admitted only by its separate opt-in
envelope. The exact eleven-field polymer terminal/leaving annotation inventory
is admitted only by its dedicated wrapper; its annotations remain outside the
child-owned `AllAtomSystem`. The exact nine-category polymer-sequence plus nonpoly
component-topology surface is admitted only by its separate composition
envelope, which preserves the two child contracts and grants no broader
category authority. The selected residue-level unobserved loop is admitted
only by its dedicated envelope, the selected atom-level unobserved loop only by its
dedicated envelope, and the two `occupancy_flag=0` branches only by their two
dedicated envelopes.
Factory-only receipt, report, and snapshot-backed aggregate objects
bind the input snapshot,
topology, projection, emitted source, reparse, and stable re-emission while
keeping authentication, preparation, parameterability, simulation, runtime,
scientific-validity, and claim authority false.

This is evidence only for the single-model-ID1 six legacy `_atom_site` profiles
and the exact three-category common-core21 profile, plus the separate exact
five-category nonpoly identity envelope, exact eight-category nonpoly component
topology envelope, exact nine-category nonpoly covalent-`_struct_conn` topology
envelope, four- or six-category polymer sequence membership envelope, exact
seven-category fully observed polymer component-topology envelope, its exact
eleven-field terminal/leaving annotation inventory wrapper, and exact
nine-category polymer-sequence plus nonpoly component-topology composition
envelope, together with the selected source-reported unobserved and
zero-occupancy residue- and atom-level envelopes when explicitly selected.
Formal-charge source notation is not charge assignment,
protonation, oxidation state, electronic-state assessment, or evidence of an
ion, metal, or cofactor role. In the selected component-topology profile, a
template-filled charge and materialized canonical bond remain source-reported
component declarations; they are not independent chemistry, valence,
aromaticity, stereo, protonation, or role evidence. Insertion-code preservation
is not auth numbering, polymer sequence alignment or completeness,
modified-residue interpretation,
missingness, altloc, assembly, or entity-role evidence.
Auth aliases are not equivalent to label identity, and source-declared entity
type is not polymer sequence completeness, modified-residue chemistry, or
water, ion, ligand, or cofactor role inference. Occupancy and B-factor spelling preservation is not alternate-location
population or occupancy-weighting interpretation, zero-occupancy missingness
or completeness evidence, refinement validity, mobility, temperature,
disorder, experimental-uncertainty assessment or propagation, or preparation
evidence. General mmCIF categories and auth/entity semantics outside
common-core21 or the selected nonpoly identity, nonpoly component topology,
nonpoly covalent-`_struct_conn` topology, polymer-sequence,
fully observed polymer component topology,
polymer terminal/leaving annotation inventory,
polymer-sequence plus nonpoly component-topology composition,
source-reported unobserved-residue and unobserved-atom, and source-reported
zero-occupancy-residue and zero-occupancy-atom envelopes,
other optional fields, `_struct_conn` outside the exact selected
identity-symmetry `covale` surface, general inter-residue or cross-component
links, coordination, metals, stereo other than `N`, other component bond orders,
altloc,
biological assemblies, missingness or zero-occupancy declarations outside the
selected envelopes, cells,
and multimodel round-trip remain
unfinished, as do general PDB and general SMILES round-trip and the all-format
V2-1 exit condition. Preparation, parameterability, simulation, scientific
validity, and claim authority remain false.

In particular, source-reported terminal/leaving flags and sequence-boundary
roles do not establish chemical termini, leaving-atom transformations, or
peptide-link materialization. The wrapper keeps the child snapshot, parser
pedigree, preparation-inventory commitment, and all readiness and claim gates
unchanged even when its fixed corpus passes.

In particular, the selected composition envelope does not promote polymer
templates, modified-residue chemistry, reference or coordinate completeness,
missingness, `_struct_conn`, altloc, assembly, cell, multimodel state, generic
or global preparation, parameterability, physics, runtime, or claim authority.
Those gates, general mmCIF support, and V2-1 completion remain false even when
the fixed composition corpus passes.

### V2-1 strict SMILES ordered-forest/simple-ring canonical-writer boundary

`betelgeuze_engine_v2.molecular.smiles_writer` is a deterministic writer for a
versioned projection of current strict-parser SMILES state. It is not a general
SMILES or `AllAtomSystem` exporter. Version 1.8 accepts one to 256 ordered
source components with global cyclomatic rank zero or one. In the rank-one
case exactly one component may be cyclic, and dependency-free iterative
degree peeling must leave one simple 2-core whose closure is the final source
bond. A non-aromatic ring has three through eight atoms, exact-single closure,
and either all-single edges or exactly one non-closure double edge. The new
selected aromatic profile instead requires a five- or six-atom ring in which
every and only ring atom is aromatic and every and only ring bond is exact
binary64 order 1.5, aromatic, and stereo-free. Tree and branch edges outside
either ring remain non-aromatic exact single, double, or triple. Components, roots, parent
edges, cycle rank, the ring atom/bond inventory, and both source and expanded
memberships are derived from the live graph rather than trusted metadata.
Source atoms are known-charge, non-isotopic members of
`B C N O P S F Cl Br I` with exact formal charge in `{-1, 0, +1}`. Atom maps
are either absent or positive and unique. Typed atom stereo is absent except
for the bounded parser-owned tetrahedral R/S plus exact RDKit CW/CCW state
described below. Source hydrogens and bracket-explicit generated hydrogens
outside the selected aromatic or tetrahedral states are rejected. A
charged source atom may not own an implicit hydrogen. Generated hydrogens are
known-neutral trailing parser-owned atoms with exact parent, origin, and
origin-local ordinal markers; generated bonds remain exact single,
non-aromatic, and stereo-free. `bracket_explicit` origin is admitted only for
the finite canonical aromatic tokens `[bH-]`, `[cH-]`, `[nH]`, `[nH+]`,
`[oH+]`, `[pH]`, `[pH+]`, and `[sH+]`. Each admitted tetrahedral center may
also retain zero or one exact bracket-explicit hydrogen as a ligand; all other
generated H remains `implicit`.

Source-bond stereo is limited to exact `none`, `E`, or `Z`. Parser-typed E/Z
must belong to a non-aromatic exact-double source-tree edge, or to the unique
non-closure double of the selected eight-member ring. Each double endpoint
must retain exactly one distinct parser-observed source-neighbor reference;
generated hydrogens cannot be references or direction carriers. Unknown bond
stereo remains outside the writer contract.

The system must retain the exact strict-SMILES parser pedigree and operations,
self-consistent topology, ordered-topology, coverage, normalized-isomeric-SMILES,
and parser-observation digests, one synthesized `Lk` residue and chain for each
graph-derived component, an empty CPU `float64` coordinate carrier of shape
`(0, N, 3)`, and no cell. Expanded component atom lists may be noncontiguous
because all source atoms precede all parser-generated hydrogens. The source
graph must satisfy `E_source = V_source - F + R`, and the expanded topology
must satisfy `E = V - F + R`, for `R in {0,1}`, without using the declared
fragment marker to establish either invariant. A source-order DSU pass exactly
partitions tree and non-tree edges. For `R=1`, the sole non-tree edge must be
the parser's final source bond; removing it produces the forest used by the
emitter.

Emission uses `ordered_acyclic_organic_forest_bounded_formal_charge/1.0.0` for
rank zero and
`ordered_forest_with_one_simple_unicyclic_component_bounded_formal_charge/1.0.0`
for rank one. Under the fixed cycle policy,
`at_most_one_simple_nonaromatic_3_8_member_all_single_bond_source_ring/1.0.0`
applies to no ring or an all-single ring, while
`at_most_one_simple_nonaromatic_3_8_member_source_ring_with_exactly_one_nonclosure_double_bond/1.0.0`
applies to the bounded cycloalkene profile. A no-ring state has no ring-bond
profile. The corresponding all-single and one-double ring-bond profiles are
`all_single_nonaromatic_stereo_none/1.0.0` and
`one_nonclosure_double_otherwise_single_nonaromatic_stereo_none/1.0.0`.
When the unique non-closure double of an eight-member ring is parser-typed E/Z,
the corresponding profiles are
`one_simple_nonaromatic_8_member_source_ring_with_exactly_one_nonclosure_parser_typed_ez_double_bond/1.0.0`
and
`one_nonclosure_parser_typed_ez_double_otherwise_single_nonaromatic/1.0.0`.
The selected aromatic alternatives are
`at_most_one_simple_fully_aromatic_5_6_member_b_c_n_o_p_s_source_ring/1.0.0`,
`all_order_1_5_aromatic_stereo_none/1.0.0`, and
`ordered_forest_with_one_simple_fully_aromatic_5_6_member_ring_selected_unit_charge_and_canonical_bracket_hydrogen_states/1.0.0`.
Validation derives one source-atom token table from typed parser state:
stereo-free unmapped neutral atoms use their bare element token, `+1` uses
`[Element+]`, and `-1` uses `[Element-]`; admitted atom maps and tetrahedral
markers use their exact bounded bracket-token forms. No charge, CIP label,
protonation, valence, or other chemistry is inferred during emission. Selected
aromatic atoms use the finite lowercase/bracket token table bound by
`selected_b_c_n_o_p_s_unit_charge_and_canonical_bracket_hydrogen_aromatic_atom_tokens/1.0.0`;
states such as `[cH]` whose bracket-H origin would be lost by canonicalization
fail closed. Iterative
depth-first traversal starts from each graph-derived root in source order.
Textual visitation across all roots must equal source atom order, roots are
separated by exactly one `.`, all but the final child are parenthesized, and a
one-pass O(V+E) parent-edge index supplies the empty, `=`, `#`, `/`, or `\\` token
immediately before each branch or continuation child. In the ring profile the
writer emits label `1` immediately after both closure-endpoint atom tokens,
before any branch or continuation; a directional closure uses `/1` or `\\1`
at the close endpoint. Raw labels such as `0`, `2`, `9`, `%10`, or
`%99` are spelling only and normalize to `1`; the writer never emits `%10`.
An aromatic ring edge also uses the empty spelling token, while its exact 1.5
order and aromatic flag remain projection-bound rather than being collapsed
into single-bond state.
The emitted one-line
ASCII SHA-256 must equal the parser-recorded normalized-isomeric-SMILES SHA-256.
Component sorting or atom reindexing is not performed: an input such as `CC.C`
whose normalized component order is `C.CC` fails the normalized hash gate.

For every typed E/Z double, the writer selects the lowest-source-index adjacent
exact-single, non-aromatic, stereo-free carrier at each endpoint. A tree
carrier is lexically oriented parent-to-child and the selected closure is
oriented close-to-open. The E/Z constraint XORs parser E/Z parity, whether
each carrier is emitted toward its stereo endpoint, and whether the selected
carrier differs from that endpoint's parser reference. Conjugated doubles that
share a carrier are solved in one constraint graph. A component containing the
closure uses the closure `/` token as its stable gauge anchor. The final
normalized spelling hash, exact reparse projection, and second-emission byte
stability remain mandatory fail-closed checks.

For every admitted parser-typed tetrahedral center, the writer retains exact
source R/S and RDKit CW/CCW metadata under profile
`source_order_dfs_parser_typed_tetrahedral_cw_ccw_lexical_parity_with_zero_or_one_bracket_hydrogen/1.0.0`.
The center must be non-aromatic, have exactly four source-or-bracket-H ligands,
zero implicit hydrogens, zero or one bracket-explicit hydrogen, and only exact-
single non-aromatic stereo-free incident bonds. A source graph may carry at
most 256 typed tetrahedral centers and, whenever any such center exists, at
most 514 source atoms. The source-order DFS emitter
first spells every typed center with a trial `@`, reparses that single trial
through the pinned parser, and independently changes a center to `@@` when its
local trial CW/CCW state differs. One final parse must then recover both the
exact source R/S label and exact CW/CCW tag at every center. Thus one trial and
one final parse are required whenever typed centers exist; the calibration
does not perform independent CIP assignment. Up to 256 admitted centers in a
source graph of at most 514 atoms, the existing selected ring profile, bounded
E/Z, positive unique atom maps, and zero-or-one bracket-H may coexist without
widening the graph profile. A typed-center graph above 514 source atoms fails
closed before calibration parsing, independently of the general 4,096-source-
atom parser ceiling.

The emitted line is reparsed through the same pinned RDKit contract and must
reproduce the exact declared representable-state and topology hashes; a second
emission must be byte-identical. This projection can normalize raw spelling,
for example `C-C` to `CC`, so raw source bytes, source/system identifiers, full
snapshot equality, and dynamic provenance equality are explicitly not claimed.
The factory-only write result keeps a hidden exact input snapshot so its parent
source, snapshot, topology, representable-state, and parser-observation receipt
bindings are live-recomputed rather than trusted. The writer state and receipt
also bind the exact formal-charge and cycle profiles, the canonical
`betelgeuze.smiles_component_cycle_projection/1.3.0` digest, per-component
cyclomatic numbers, ring atom/bond inventory,
source-index-sorted ring bond-order table, dynamic cycle/ring-bond profile,
double-edge count and index, closure index and endpoints, source ring-marker table, source/tree edge counts,
source atom tokens, charged-source-atom count, and net formal charge; unit-
charge count/total parity is validated. Version 1.6 additionally binds a
separate `betelgeuze.smiles_aromatic_ring_projection/1.0.0` digest, selected
aromatic atom and bond counts, exact atom element/charge/known-charge/aromatic/
implicit-H/bracket-H/token rows, exact bond endpoint/order/aromatic/stereo/
tree-or-closure rows, and generated bracket-H atom/bond parent-origin-ordinal
rows. The round-trip aggregate independently
recomputes and revalidates these cross-artifact bindings. These hashes remain
tamper evidence, not source authentication.

Version 1.7 introduced, and version 1.8 retains,
`betelgeuze.smiles_ez_stereo_projection/1.0.0`: typed source-double endpoints
and E/Z labels, endpoint references, chosen carriers and tokens, emitted
from/to orientation and tree/closure role, reference and orientation parity,
shared constraints, and exact counts/profile. The bounded scope includes only
lowest-index-carrier spellings that pass the attached normalized hash gate:
selected branched, conjugated, and multi-component source-tree E/Z, exocyclic E/Z whose
carrier lies on a selected three- through eight-member simple ring, and the
unique non-closure E/Z double at any source-tree position of a selected
eight-member ring. Receipt, report, and aggregate cross-bind the input and
reparsed E/Z projection digests. A structurally similar graph whose canonical
spelling directs a different carrier may therefore fail closed with a
normalized-spelling mismatch rather than widening this contract implicitly.
The separate `betelgeuze.v2_1_smiles_e_z_writer_corpus/1.1.0` fixes 17 positive
fixed points under manifest payload SHA-256
`a58207f72b9127b3adf1cde9499b765ec934f7162fe52ef720aae74ebff8b03f`.
It also recomputes and binds the frozen upstream ingest-corpus case-record
digests for `smiles_alkene_e` and `smiles_alkene_z`.

Version 1.8 additionally binds
`betelgeuze.smiles_tetrahedral_stereo_projection/1.0.0`. Each typed-center row
binds source atom index and optional map, target R/S and CW/CCW state, ordered
source neighbors and incident bonds, emitted parent/branch/continuation/closure
roles, ring marker, optional bracket-H atom and bond, and trial/final lexical
marker, token, and recovered stereo state. Receipt, report, and aggregate
cross-bind the input and reparsed projection digests. The separate
`betelgeuze.v2_1_smiles_r_s_writer_corpus/1.0.0`, corpus ID
`v2_1_strict_smiles_bounded_r_s_writer_v1`, fixes 14 inline-ASCII positive
cases covering bracket-H and no-H R/S, positive maps, multiple centers, a
selected ring, E/Z coexistence, multi-component input, charged N, S, B, and a
stereo-free baseline. Its final manifest payload SHA-256 is
`34a1cadfe0c3fa321bfb256c28d723c29465c85384ec2e99f1022aef71a636fc`
and is bound in capability and CI.

Only ordered organic-subset forest spelling, one bounded non-aromatic simple
ring with zero or one non-closure double edge or one selected fully aromatic
five/six-member simple ring, and bounded parser-observed formal-charge/H-origin
serialization are added. This
is not charge assignment, protonation,
tautomer, oxidation/electronic-state assessment, partial-charge support, or
evidence of ion, salt, mixture, or counterion roles. Fragment roles and
contextual chemistry remain unassessed; `[Na+].[Cl-]` still fails the selected
element policy even though selected organic-subset `-1` and `+1` tokens can be
serialized. Aromatic/Kekule input is normalized only when its sanitized source
index order is already canonical; the raw spelling is not preserved. A
nine-member non-aromatic ring, an aromatic ring outside five/six members, a
second cycle, fused/spiro/bridged systems, a non-aromatic multiple-bond closure, a ring triple edge,
and a second ring double edge fail closed, as do general charge states,
isotopes, nonpositive or duplicate maps, atom stereo outside bounded
tetrahedral R/S, unknown bond stereo, E/Z outside the bounded tree/simple-ring
carrier profile, source hydrogens, bracket hydrogens outside the selected
aromatic or tetrahedral states, coordinates, and cells. Bounded cycloalkene or selected
parser-observed aromatic serialization is not unsaturation
assessment, independent aromaticity/resonance/Kekulization verification,
electronic-structure evidence, ring-strain, conformation, valence, protonation,
tautomer, or other chemistry interpretation. Bounded parser-typed E/Z and R/S
serialization is not independent CIP assignment, global stereo-completeness,
substituent-equivalence, or stereo-geometry assessment, conformation evidence,
or chemistry interpretation. The E/Z projection itself deliberately does not
encode atom stereo; version 1.8 binds it separately in the tetrahedral
projection.
This selected forest/ring, bond-order, and formal-charge serialization is not
general fragment-role, salt, mixture, ring, multiple-bond, aromatic, charge,
or stereochemical chemistry support. The accepted topology-only projection does
not establish preparation, parameterability, simulation readiness, scientific
validity, runtime eligibility, or claim authority and does not make SMILES
input eligible for the source-observed-hydrogen reference-kernel lane. General
SMILES round-trip and the all-format V2-1 exit condition remain blocked.

### V2-1 contextual component inventory boundary

`betelgeuze.contextual_component_inventory/1.0.0` is a factory-only derived
report with claim scope `canonical_component_observation_only`. It recomputes
the topology digest, obtains a fresh preparation inventory, and records one
immutable row per canonical residue. Rows may state only canonical markers:
the exact residue name and entity-type string, hetero flag, atom indices,
element counts, formal-charge known/unknown counts, a canonical net charge when
all atom charges are marked known, an `entity_type=water` marker, a known
nonzero charged-monatomic marker, and a polymer-plus-hetero marker.

Those markers are not source authentication and are not contextual chemical
roles. A `HOH` name or water entity marker does not prove hydrogen completeness
or solvent role; a charged monatomic Na or Zn row does not prove ion role,
oxidation state, or metal coordination; `HEM` remains a generic component name;
and polymer `HETATM` `MSE` is not a verified modified residue. Connection
context, water/ion/metal/cofactor roles, modified-residue identity, chemistry
support, preparation, parameterability, simulation, and claim safety remain
machine-readably `unassessed` or false.

The schema-1.4 corpus pins a mixed mmCIF canonical-marker inventory containing
water, charged monatomic Na and Zn, generic HEM, and polymer-hetero MSE while
retaining all non-promotion gates. Separate intentional failures pin topology,
ion-context, non-polymer component mapping, and modified-residue context
categories that cannot yet be ingested losslessly.

The generic preparation inventory now applies a fixed pre-validation resource
profile: at most 100,000 atoms, 200,000 bonds, 100,000 residues, and 100,000
chains. Inputs above any bound raise a typed `PreparationCoverageLimitError`
before canonical validation, topology hashing, or audit allocation. Canonical
applicability, profile-local evidence, and contextual-component inventory
propagate the same error instead of repeating unbounded work. Equality at each
limit is accepted, and all in-profile report schemas, bytes, digests, and
non-promotion decisions remain unchanged. These are audit safety limits, not
supported system sizes, performance claims, preparation evidence, or execution
authority.

### V2-1 profile-local preparation evidence boundary

The separate `betelgeuze.profile_local_preparation_evidence/1.0.0` report is a
derived view produced by reanalyzing one canonical system into validated
chemistry, applicability, and generic preparation reports. It does not accept
independently supplied copies of profile constraints or diagnostic counts. Its
positive result is limited to
`canonical_graph_local_valence_evidence_only`: the declared canonical graph has
source-observed explicit hydrogens, H=1/C=4 local valence closure, known-zero
formal charges observed through a source-format-compatible parser marker, and
no profile-relevant need for aromatic or multiple-bond handling. The current
schema-1.4 corpus has five selected positive rows: explicit-H methane, ethane,
propane, n-butane, and branched isobutane. Cyclobutane pins the exact
`acyclic_graph` boundary, while explicit-H ethane with one hydrogen omitted
pins the exact `explicit_valence_closed` boundary. This table samples the
existing neutral, nonisotopic, stereo-unassigned, acyclic saturated H/C
canonical-ingest-only profile. It neither exhausts the profile nor declares a
C1--C4 size ceiling, and every global preparation, parameterability,
simulation, and claim gate remains false.

`require_profile_local_preparation_evidence` is the typed consumer gate for
that exact local decision. It always derives a fresh report, returns that report
only when `profile_local_evidence_satisfied=true`, and otherwise raises
`ProfileLocalPreparationEvidenceError` carrying the same report, status, and
bounded blocker tuple. Wrong input types and preparation resource-limit errors
remain unwrapped. This API does not create a second authority or mutate the
system, and a successful return does not change any global preparation,
parameterability, simulation, or claim field.

`profile_local_evidence_satisfied=true` is not a preparation attestation. Even
for that row, whole-molecule and generic hydrogen completeness, environmental
protonation, formal-charge assignment, tautomer choice, independent
aromaticity perception, stereo completeness, electronic state, geometry,
contextual water/ion/metal/cofactor roles, and parameterability remain
`unassessed`. Normalization and completion are not attempted, source digests
are not authentication, and preparation, simulation, and claim gates remain
false.

### V2-1 additive C3--C8 cycloalkane graph-profile boundary

`betelgeuze.cycloalkane_c3_c8_graph_profile/1.0.0` is a separate,
additive profile for parser-owned SDF V2000 state. It accepts only one
source-observed explicit-H, neutral, nonisotopic, unmapped, stereo-unassigned,
nonaromatic unsubstituted monocycle with three through eight carbon atoms,
formula CnH2n, one connected simple carbon cycle, exactly two carbon and two
source-hydrogen neighbors per carbon, one carbon neighbor per hydrogen, exact
single bonds, known-zero source formal charges, and no partial charges. It
recomputes generic chemistry and preparation reports, their versions and
digests, canonical topology, and the parser-observation schema and attached
versus recomputed digest from a hidden canonical-system snapshot. Its frozen
rule bytes, source-indexed exact graph projection, report, and snapshot have
separate SHA-256 bindings. Those digests are tamper evidence, not source
authentication.

The exact positive scope is
`source_observed_graph_local_identity_and_valence_only`. A positive row makes
only `profile_chemistry_supported` and
`profile_graph_preparation_ready` true. The typed require gate demands the
sole allowlisted consumer ID `cycloalkane_c3_c8_graph_profile_audit`; it rejects
other consumers before returning evidence. The graph-projection digest retains
source atom and bond indices and therefore is deliberately not an
order-independent graph-isomorphism identity. Admission is graph-structural,
while the snapshot and projection bind the exact source-indexed state.

The separate versioned corpus pins every C3--C8 positive plus bounded
size, branched, fused or spiro, unsaturated, hydrogen-count, heteroatom,
charge, isotope, and disconnected failures. A separate dependency-pinned
focused test fixes the SMILES adapter-generated-H and wrong-pedigree boundary
without placing RDKit-version-dependent snapshot digests in this SDF corpus.
The existing
acyclic canonical-ingest profile remains unchanged: its cyclobutane row still
fails exactly with `acyclic_graph`, while the same source is positive only in
this additive cycloalkane profile. C3--C8 is a versioned product-profile bound,
not a statement that C9 chemistry is invalid.

Even for a positive row, `global_molecular_preparation_ready`, environmental
pH and protonation correctness, ring strain, conformation and geometry
quality, parameterability, force-field typing, charges and parameters,
physics, runtime, execution, energy, force, minimization, simulation, and
claim authority remain false or unassessed. This evidence neither completes
V2-1 nor expands any V2-2 force-field applicability boundary.

### V2-1 additive terminal-monoalkene C2--C8 graph-profile boundary

`betelgeuze.terminal_monoalkene_c2_c8_graph_profile/1.0.0` is a separate,
additive profile whose exact profile ID is
`source_observed_explicit_h_neutral_unbranched_terminal_monoalkene_c2_c8/1.0.0`.
It accepts only parser-owned `betelgeuze.sdf_v2000_parser/1.5.0` state containing one
source-observed explicit-H, neutral, nonisotopic, unmapped, stereo-unassigned,
nonaromatic C/H component with formula CnH2n and two through eight carbon
atoms. Every atom must carry the exact source marker metadata and a
source-observed known-zero formal charge. Every bond must carry the exact
source atom, source bond, and SDF bond-type metadata. The carbon-induced graph
must be one connected simple path with exactly one terminal C=C bond; for C2,
both double-bond endpoints are path endpoints, while for C3--C8 exactly one is
a path endpoint. Every other C--C and C--H edge is an exact single bond, and
the integer source bond-order ledger must close at C=4 and H=1.

The exact positive scope is
`source_observed_graph_local_unbranched_terminal_monoalkene_identity_and_bond_order_valence_ledger_only`.
Here, “unbranched” means only that the carbon-induced graph is a simple path;
it makes no coordinate-linearity or geometry claim. The source bond-order
ledger closes the parser-observed annotation against the declared graph. It is
not independent bond-order, valence, unsaturation, E/Z or CIP, conjugation, or
electronic-structure validation. The source-indexed projection deliberately is
not an order-independent graph-isomorphism identity, and its digests are
tamper evidence rather than source authentication.

Only `profile_chemistry_supported` and
`profile_graph_preparation_ready` may become true. The typed require gate
allows only `terminal_monoalkene_c2_c8_graph_profile_audit`. Generic chemistry,
generic and global molecular preparation, E/Z and CIP assessment, conformation
and geometry, electronic structure, parameterability, force-field typing,
charges and parameters, physics, runtime, execution, energy, force,
minimization, simulation, and claim authority remain false or unassessed.
C2--C8 is a
versioned product-profile boundary: a valid terminal C9 row fails only the
`carbon_count_c2_c8` product constraint and is not classified as chemically
invalid.

The separate versioned corpus pins ethene through oct-1-ene positives and
bounded size, internal-double-bond, branching, cyclic, polyunsaturated,
triple-bond, saturated, hydrogen-ledger, heteroatom, charge, isotope/map,
aromatic, and disconnected failures. This SDF-derived graph profile does not
expand the strict SMILES writer's selected multiple-bond serialization subset,
does not establish general alkene chemistry support, and neither completes
V2-1 nor expands any V2-2 force-field applicability boundary.

### V2-1 additive exact-H2O graph-profile boundary

`betelgeuze.exact_h2o_graph_profile/1.0.0` is a separate additive profile
whose exact profile ID is
`source_observed_explicit_h_neutral_h2o_graph/1.0.0`. It accepts only one
parser-owned `betelgeuze.sdf_v2000_parser/1.5.0` component containing exactly
one oxygen and two source-observed explicit hydrogens. Every atom must carry
an SDF atom-block observed known-zero formal charge, exact source atom marker
metadata, no isotope or atom map, no partial charge, no typed stereo, and no
aromatic state. Exactly two source-indexed bonds must connect the oxygen to
the two hydrogens as nonaromatic stereo-free single bonds with exact source
bond index, endpoint, type, and source metadata. The oxygen must have degree
and integer source bond-order ledger value two; each hydrogen must have degree
and ledger value one. The parser-synthesized context is exactly one
`LIG/non_polymer` residue in one `L/ligand` chain, not a water entity marker.

The factory-only report stores a hidden canonical-system snapshot and
recomputes canonical topology, current generic chemistry and preparation
reports and their digests, the attached versus recomputed parser-observation
digest, a frozen rule document, a source-indexed exact graph projection, and
the final report digest. The projection is deliberately not an
order-independent graph-isomorphism identity. Coordinates remain bound by the
snapshot but are absent from the admission projection: bent and collinear
finite parser-owned coordinates do not change graph admission. These SHA-256
bindings are tamper evidence, not source authentication.

The exact positive scope is
`source_observed_graph_local_h2o_identity_and_bond_order_valence_ledger_only`.
Only `profile_chemistry_supported` and
`profile_graph_preparation_ready` may become true, and the typed require gate
allows only `exact_h2o_graph_profile_audit`. Source-ledger closure checks the
parser-observed bond-order annotations against this exact graph; it is not
independent bond-order, valence, protonation, autoionization, isotopic
speciation, or electronic-structure validation. It also establishes no bond
length, H--O--H angle, conformation, or geometry-quality result.

An admitted H2O graph is not an assignment of water, solvent, or hydration
role. In particular, its SDF-derived `LIG/non_polymer` context has no canonical
water entity marker. Existing mmCIF `HOH` or `entity_type=water` marker
preservation remains separate, and the contextual-component inventory keeps
water role unassessed even when such a marker exists. The versioned corpus
and focused fail-closed tests jointly pin positive source atom orders and
coordinate shapes plus hydrogen-count,
connectivity, peroxide, multiple-bond, heteroatom, charge including
net-zero redistribution, isotope/map, partial-charge, stereo, aromatic,
wrong-pedigree, exact-metadata, source-binding, and synthesized-context
failures.

Generic chemistry and generic/global molecular preparation remain false.
Environmental pH, protonation and autoionization, isotope speciation,
water/solvent/hydration roles, parameterability, atom typing, partial-charge
and parameter assignment, water-model and constraint assignment, box
preparation, PBC and periodicity, physics, runtime, execution, energy, force,
minimization, simulation, and claim authority all remain false or unassessed.
This bounded graph profile neither completes V2-1 nor expands the V2-4
solvent, constraint, PBC, long-range, or MD boundary.

### V2-2 exact-methane bond/angle identity bridge

`betelgeuze.exact_methane_bond_angle_inventory/1.0.0` is a contract-only,
factory-derived bridge into V2-2. It is available only when a fresh
profile-local report and direct graph checks agree on one source-bound SDF
V2000 molecule containing exactly one carbon, four source-observed hydrogens,
four single C-H edges, one connected component, and one non-polymer residue.
The broader acyclic saturated-hydrocarbon ingest profile is intentionally not
promoted: explicit-H ethane remains unsupported by this exact layer.

For the exact graph, the report deterministically enumerates four unordered
C-H bond identities and six undirected H-C-H angle identities, independent of
source bond-row order or the carbon atom's position. These are canonical graph
indices only. No atom types, force constants, equilibrium geometry, partial
charges, parameter values, energies, or forces are present. Proper torsion,
improper, and constraint identity policies remain `not_assessed` because those
choices require a versioned force-field convention.

Even when the inventory is `available`, preparation, parameterability,
physics, energy, force, minimization, simulation, and claim authority remain
false. The source digest supplies deterministic binding, not authentication;
`parameter_set_id` and the assignment digest remain null. This bridge does not
complete V2-1 and does not implement or enable a V2-2 force field; it only
fixes the smallest deterministic bonded-identity input on which a future
parameter contract can operate.

### V2-2 bounded C1--C4 linear-alkane topology boundary

Three separate factory-only contracts extend graph coverage without widening
the exact-methane parameter or numerical-diagnostic scope:

- `betelgeuze.linear_alkane_c1_c4_force_field_applicability/1.0.0`
  accepts only a source-bound SDF V2000 system with one connected non-polymer
  residue, one through four carbons, source-observed explicit hydrogens,
  `H=2*C+2`, a simple-path carbon subgraph, exact carbon/hydrogen degrees,
  known-zero formal charge, and no isotope, aromatic, stereo, generated-H, or
  source `partial_charge_e` state. Branches, cycles, missing hydrogens, charge,
  isotope, source partial charge, and wrong parser pedigree fail closed.
- `betelgeuze.linear_alkane_c1_c4_topological_environment_typing/1.0.0`
  derives coordinate-, atom-name-, and residue-label-independent graph
  environment match keys. These keys describe only carbon-neighbor and
  hydrogen-neighbor counts, and each hydrogen key refers to its attached
  carbon environment. They are explicitly **not force-field atom types**;
  every `force_field_type_id` and `assigned_partial_charge_e` remains null.
- `betelgeuze.linear_alkane_c1_c4_term_pair_inventory/1.0.0` enumerates exact
  bonds, angles, and proper torsions, and classifies every unordered atom pair
  by shortest covalent-graph distance. Distance one is `excluded_1_2`, distance
  two is `excluded_1_3`, distance three is `one_four_separate`, and distance
  four or greater is `full_nonbonded`. The selected-improper set and selected-
  constraint set are empty by explicit versioned policies, not because those
  concepts have been implemented generally. No interaction is evaluated.

The exact bounded inventory counts are:

| Molecule | Atoms | Bonds | Angles | Propers | 1--2 excluded | 1--3 excluded | 1--4 separate | Farther full | All pairs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| C1 methane | 5 | 4 | 6 | 0 | 4 | 6 | 0 | 0 | 10 |
| C2 ethane | 8 | 7 | 12 | 9 | 7 | 12 | 9 | 0 | 28 |
| C3 propane | 11 | 10 | 18 | 18 | 10 | 18 | 18 | 9 | 55 |
| C4 n-butane | 14 | 13 | 24 | 27 | 13 | 24 | 27 | 27 | 91 |

The C1--C4 manifest,
[`independent_engine_v2_v2_2_linear_alkane_corpus.json`](../config/independent_engine_v2_v2_2_linear_alkane_corpus.json),
remains separate from the V2-1 ingest corpus even where the two manifests
reuse digest-bound fixture bytes. In particular, branched isobutane is a
positive selected row for the broader V2-1 acyclic saturated H/C ingest-only
profile but remains a negative row for the V2-2 **linear**-alkane force-field
profile. The V2-2 manifest binds its bounded positive and intentional-failure
sources to applicability, environment, term, pair, and non-promotion
expectations. Its SHA-256 values are deterministic integrity bindings, not
source authentication, signatures, license review, or scientific evidence.

The topology reports themselves do not assign a charge model, partial charges,
force-field atom types, bonded or nonbonded parameters, or 1--4 LJ/Coulomb
scale factors. They do not implement LJ, Coulomb, energy, force, virial,
minimization, runtime physics, or scientific/product applicability. They are
the exact graph input to the separate nonphysical parameter-assignment
contract below, not completion of V2-2.

### V2-2 bounded C1--C4 full parameter and assignment contract

Three frozen, separate artifacts extend the bounded topology without
authorizing a force-field runtime:

- `betelgeuze.linear_alkane_c1_c4_parameter_protocol/1.0.0` fixes the exact
  union of six graph environments, six bond keys, nine angle keys, and seven
  proper keys. It specifies harmonic bond/angle and periodic-proper forms,
  LJ 12-6, the deferred-coefficient Coulomb base form, exact-pair override
  precedence, Lorentz--Berthelot fallback, and independent 1--4 LJ/Coulomb
  scales. Cutoff, switch, dielectric, Coulomb coefficient, PBC, long range,
  neighbor policy, dtype/device, and accumulation order remain deferred.
- `betelgeuze.linear_alkane_c1_c4_parameter_set/1.0.0` stores one-to-one
  environment-to-FF-type mappings, explicit charge-parameter lookups, LJ type
  rows and optional full pair overrides, the complete bonded-rule universe,
  and global 1--4 scales. Every float uses canonical IEEE-754 binary64
  big-endian hex, with separate protocol, payload, set, and artifact digests.
- `betelgeuze.linear_alkane_c1_c4_parameter_assignment/1.0.0` binds canonical
  system and parameter bytes, freshly recomputes applicability, typing, and
  inventory, and then maps atom, bond, angle, proper, and every unordered-pair
  identity. Excluded 1--2/1--3 pairs carry no pair parameters. Nonexcluded
  pairs preserve endpoint type/charge association and record override or
  Lorentz--Berthelot LJ mapping; only 1--4 pairs carry the two 1--4 scales.

The shipped numeric values are not scientific parameters. They exist only in
the test fixture and exercise explicit nonzero positive/negative dyadic charge
lookups; frozen environment-order `math.fsum` is exactly zero for each C1--C4
component. Source partial charge is never copied, known-neutral formal charge
is never converted to zero partial charges, and no renormalization is allowed.
The assignment serializer is canonical ASCII JSON, while no standalone
deserializer trusts assignment rows without the two original inputs. C1 and
C4 byte lengths and digests, hash-seed replay, snapshot tampering, and forged
cross-artifact rows are pinned.

`bounded_contract_fixture_*_complete` means only that this declared fixture
maps the bounded graph exactly. Production assignment, parameterability,
global coverage, preparation, physics, scientific validation, production
evaluation method, energy, force, virial, minimization, execution, simulation,
and claim gates remain false. The assignment contract does not evaluate LJ or
Coulomb and cannot establish electrostatic or force-field accuracy. Scientific
fitting, licensed data and provenance review, reference validation, production
method semantics, and an energy/force/virial kernel remain blockers.

### V2-2 bounded C1--C4 nonphysical evaluation-method binding

Two additional versioned contracts close only the method choices needed for a
tiny, nonphysical reference boundary:

- `betelgeuze.linear_alkane_c1_c4_evaluation_method_protocol/1.0.0` and its
  strict artifact bind the exact parameter-protocol digest, assignment schema
  and policy, pair classes, functional forms, and unit system. The method is
  limited to one cell-free, nonperiodic, CPU `torch.float64` coordinate model,
  no autograd input, `N<=14`, at most 91 unordered pairs, and at most 54
  selected nonexcluded pairs.
- `betelgeuze.linear_alkane_c1_c4_evaluation_method_binding/1.0.0` binds the
  canonical system, parameter, and method bytes plus a separately hashed live
  tensor-interface envelope. The envelope is observed before molecular
  serialization detaches, moves to CPU, and makes tensors contiguous, so an
  original non-CPU, float32, multi-model, cell-present, or `requires_grad`
  input cannot be silently promoted by snapshot normalization.

The binding factory accepts only strict canonical molecular state. A
non-angstrom unit, nonfinite coordinates, or another molecular-validation
failure raises its typed validation error before a report exists; valid
canonical chemistry with a method-interface mismatch is represented by
`method_incompatible` instead.

The reference pair method iterates only the canonical assignment pair rows.
It omits 1--2 and 1--3, applies the two stored scales only to 1--4, leaves full
nonbonded rows unscaled, and consumes the already-resolved exact override or
Lorentz--Berthelot LJ values without recombination. There is no cutoff,
switch, spatial neighbor search, dense `N x N` pair materialization, minimum
image, reciprocal-space method, long-range correction, or dispersion tail.
Direct electrostatics is frozen as the exact binary64 operation sequence
`(k_e/epsilon_r)`, multiply by `q_i`, multiply by `q_j`, then divide by `r`.
The test-only fixture uses `k_e=1.0` and `epsilon_r=1.0`; these are explicitly
not scientific Coulomb values.

The method artifact fixes prospective scalar accumulation as bond, angle,
proper, then selected-pair identities. Proper components and each pair's
LJ/Coulomb values use the declared `math.fsum` order. CPU binary64
round-to-nearest-ties-to-even is required; mixed precision, fast math, and FMA
contraction are prohibited. Cross-platform libm bit replay is not claimed. The
downstream diagnostic below realizes only that bounded scalar sequence;
v1 method-owned force and virial methods and their accumulation orders remain
undefined because that v1 method artifact's kernel is still missing. The later
overlay reference kernel is a separate protocol and does not alter this fact.

Every binding access strictly round-trips all snapshots and freshly recomputes
the C1--C4 assignment. It checks the exact full pair inventory before accepting
the empty C1 selected subset, then assesses bond distances, angle leg/sine
geometry, proper bond/normal geometry, and selected-pair distances against the
artifact thresholds. The binding itself still calculates no interaction value.
The shipped n-butane source fixture contains one exactly opposed H--C--H pair
and therefore correctly returns `method_incompatible`; separate C4 evidence on
the same source-identified topology uses a test-only derived coordinate state
with one hydrogen displaced by an exact 0.125 angstrom and passes the same contract.

Only the scoped nonphysical method-definition and method-assignment binding
flags may be true in this binding report. It emits no numeric energy, force,
virial, or per-term result. The direct all-pair boundary is tiny-reference
evidence, not scaling evidence, and it is not registered in engine dispatch.

### V2-2 snapshot-bound nonphysical C1--C4 scalar-energy diagnostic

`betelgeuze.linear_alkane_c1_c4_scalar_energy_diagnostic_protocol/1.0.0`
and `betelgeuze.linear_alkane_c1_c4_scalar_energy_diagnostic/1.0.0` add a
separate, schema-owned numerical diagnostic downstream of the non-evaluating
method binding. This does not change the bound method artifact's
`energy_kernel_status="missing"`: the diagnostic evaluator is not a method-owned
or production runtime kernel.

The only accepted input is one exact
`LinearAlkaneC1C4EvaluationMethodBindingReport`; a raw system, parameter set, or
method API is prohibited. Each public analysis replays exactly one immutable
capsule containing the binding's canonical system, parameter, method,
assignment, input-envelope, and binding-report snapshots. It rejects stale,
substituted, or tampered dependencies instead of rereading a caller's live
tensor.

Within the already bounded, direct-uncut CPU-binary64 domain, the diagnostic
freezes the literal arithmetic order:

- bond and angle energies use `(0.5*k*delta)*delta`; angles use normalized
  singularity checks followed by `atan2` of the literal raw cross norm and raw
  dot;
- signed proper angles use the literal cross/dot `atan2` convention, each
  periodic component uses `amplitude*(1+cos(n*phi-phase))`, and components are
  reduced with `math.fsum`;
- LJ uses `s=sigma/r`, then `s2`, `s4`, `s6`, `s12`, and
  `(4*epsilon)*(s12-s6)`; Coulomb uses `(k_e/epsilon_r)`, `*q_i`, `*q_j`, then
  `/r`;
- 1--4 LJ and Coulomb scales are applied exactly once after the base values;
  full-nonbonded values are not multiplied by a scale; each pair uses
  `math.fsum((LJ,Coulomb))`;
- the reported total is one `math.fsum` over the flat canonical sequence of
  bond, angle, proper, and selected-pair energies. Class and LJ/Coulomb
  subtotals are reporting-only and are never re-summed to form the total.

The test-only fixture pins the following evaluated counts and binary64 energy
goldens. The C4 row uses the same one-hydrogen exact-0.125-angstrom derived
coordinate state described above. Values are hexadecimal encodings of
kilojoules per mole and are contract evidence, not scientific reference data.

| Molecule | Evaluated B/A/P/pair | Bond | Angle | Proper | Selected pair | Applied LJ | Applied Coulomb | Flat total |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C1 methane | 4/6/0/0 | `3ff9b589b5b18f2f` | `3fe80c7fa29664b5` | `0000000000000000` | `0000000000000000` | `0000000000000000` | `0000000000000000` | `4002dde4c37e60c5` |
| C2 ethane | 7/12/9/9 | `402c83072057e042` | `401138567aa253d8` | `402b00000f407602` | `3ff1db3b331b547c` | `3ff1b25deaa00700` | `3f846ea43da6be1e` | `404096a674d33ab0` |
| C3 propane | 10/18/18/27 | `4038debb80e2523f` | `40417da3afe515f8` | `403f11f3df977c69` | `bfcddd79234d656d` | `bfcead966d48c5dd` | `3f7a03a93f6c0e02` | `4056ac0ef37f57f3` |
| C4 derived n-butane | 13/24/27/54 | `404208fc6f52f5ff` | `405a8bb2829a5632` | `40490af7220cdfe4` | `40a5e286778d609b` | `40a5e2818bd1267f` | `3f83aef0e8705d5a` | `40a76333d9e7b2a4` |

The protocol SHA-256 is
`d749376664b1624ba53257378ef1e7c052e7a784a4e36393fa5874a007ad8f11`.
The canonical C1 diagnostic is 5,590 bytes with serialized SHA-256
`3ba0b3dd03e41862512cf3843dcf023e6608aec4645d7b710cac970de88be825`;
its report, scalar-evaluation, and canonical-term-sequence digests are pinned
independently. Per-term rows are available only in the immutable analysis and
are bound by those digests; the compact serialized report omits them.

An upstream `invalid_system`, `unsupported_system`, or `method_incompatible`
status produces a non-evaluated diagnostic report with zero evaluated counts,
all energy fields null, and no term tuples. Snapshot inconsistency, tampering,
nonrepresentable coordinate arithmetic, or nonfinite arithmetic raises a typed
failure before any report is returned; partial results are prohibited. The C1
empty selected-pair subset is a successful positive-zero result only after the
full ten-pair inventory is verified.

The evaluator performs a binary64 tie-sensitive rounding-mode check before
and after every successful evaluation. Upward, downward, or toward-zero
ambient rounding therefore fails with a typed error instead of silently
changing the pinned totals.

Only the diagnostic-specific, bounded nonphysical scalar-evaluation flags may
be true on a successful report. Method-owned/runtime energy-kernel,
force, virial, gradient/autograd, minimization, dispatch, production assignment
and method, parameterability, global coverage, physics, scientific validation,
execution, simulation, and claim gates remain false. The next force-field step
is still licensed scientific fitting plus an independently validated
energy/force/virial kernel and production method.

### V2-2 bounded nonphysical C1--C4 method-kernel reference potential

`betelgeuze.linear_alkane_c1_c4_method_kernel_protocol/1.0.0` is a separate
method-kernel overlay on the frozen v1 binding. It records both sides of that
boundary explicitly: the bound v1 method's own `energy_kernel_status="missing"`
and undefined force/virial methods remain unchanged, while the overlay owns a
bounded nonphysical CPU energy/force/virial implementation. It therefore does
not rewrite the v1 method, binding, or scalar-diagnostic bytes and is not a
production evaluation-method promotion.

`compile_linear_alkane_c1_c4_reference_potential(binding)` accepts only an
exact, successful `LinearAlkaneC1C4EvaluationMethodBindingReport`. Compilation
performs one fresh immutable replay, verifies the canonical binding report and
its report/snapshot hashes, requires the exact assignment, parameter-protocol,
method-protocol, unit-system, bound-status, and geometry-status projections,
and freezes only resolved numeric interaction rows into a tuple-only plan. Raw
system/parameter/method overloads and incompatible bindings are rejected. The
resulting potential can evaluate multiple fresh coordinate snapshots without
rereading the original live tensor or rebuilding chemistry.

Every call requires an exact strided CPU `torch.float64` tensor of shape
`[N,3]`, `requires_grad=false`, with the compiled atom count. The input is
cloned contiguously before scalar reads, is hashed as row-major binary64, and is
checked for finite values and the compiled distance/angle/proper thresholds.
No dtype/device conversion, clamp, softcore, epsilon regularization, partial
result, cell, PBC, cutoff, switch, neighbor search, or long-range method is
allowed.

The energy forward pass independently reproduces the diagnostic's literal
bond, angle, signed proper, LJ, Coulomb, one--four, and flat `math.fsum`
operation sequence. Each term then applies a local reverse-mode VJP to those
same forward intermediates; total atom force is the canonical flat per-term
`math.fsum` and is defined as `F=-dE/dr`. Pair LJ and Coulomb derivatives are
scaled exactly once for 1--4 rows and never scaled for full-nonbonded rows.
The implementation does not import or call the scalar diagnostic evaluator.

Each public term carries its canonical identity, parameter identifier, energy,
local atom forces, and local virial. Class results cover bond, angle, proper,
Lennard-Jones, and Coulomb. The complete cell-free nonperiodic virial is

```text
W[a,b] = sum_terms sum_local_atoms F[a] * (r[b] - r_anchor[b])
       = -dE/d epsilon[a,b],  r' = r @ (I + epsilon).T
```

with canonical atom-j anchors for bond/proper/pair and the center atom for an
angle. The index order is force axis then coordinate axis. Flat term virials,
not class subtotals, form the total. This is a configurational nonperiodic
virial only; pressure, stress, volume, cell, and PBC virial semantics remain
undefined.

Class energy/force/virial values are reporting decompositions. Because selected
pairs are combined before the flat total while LJ and Coulomb are accumulated
separately for class reporting, re-summing class values is checked within the
declared binary64 tolerance and is not a bitwise-identity contract.

The immutable
`betelgeuze.linear_alkane_c1_c4_reference_kernel_result/1.0.0` binds the
protocol, binding-report bytes and report digest, system/parameter/method,
assignment, topology, source, compiled plan, coordinate snapshot, flat term
sequence, output sequence, evaluation, and report roots. Detached tensor-copy
accessors expose force `[1,N,3]` and virial `[3,3]` without mutable aliases.
For C1, the protocol is 5,519 bytes with SHA-256
`c402308fbec145137a69917102c8539c224e6393567dc30fcc64496724359cad`;
the compiled plan digest is
`e1107d0182ccc50e0bcc301d72d3f73cd143b06bc06fd7a47568ff26f7c55f62`,
and the 14,655-byte result has serialized SHA-256
`9d72ddf1b55b7f029a6cac5349576373e6f71621a201460d8fa80bfd80799d50`.

Tests pin C1--C4 binary64 energy equality with the independent scalar
diagnostic, every coordinate force against central finite differences, force
against an independent Torch autograd graph containing proper/LJ/Coulomb
terms, all nine affine virial derivatives, translation and proper-rotation
behavior, atom-reindexing equivariance, net force/torque, class decomposition,
repeated evaluation, exact
override/full/1--4 coverage, strict interface rejection, nonfinite input, and
singular geometry. These are algorithm-consistency tests on nonphysical
fixture parameters, not scientific reference agreement.

Only the bounded nonphysical method-owned reference-kernel flags are true.
Production runtime energy/force/virial, scientific parameters and validation,
physics support, engine dispatch, minimization, simulation, execution, and
claim authority remain false. Licensed fitting/provenance, force-energy
reference validation, a production method with cutoff/switch/PBC/long-range
semantics, complete pressure virial, minimizer evidence, and release
attestation remain blockers.

### V2-2 exact-methane bond/angle parameter contract

`betelgeuze.exact_methane_bond_angle_parameter_set/1.0.0`, its form-bound
`1.1.0` successor, and
`betelgeuze.exact_methane_bond_angle_parameter_assignment/1.0.0` define the
first parameter artifact and assignment boundary. Their scope is exactly
`exact_methane_bond_angle_parameter_assignment_only`: one harmonic C-H bond
parameter is mapped to all four canonical bond identities and one harmonic
H-C-H angle parameter is mapped to all six canonical angle identities. Exact
set equality, rather than matching counts, determines scoped assignment
completeness.

The unsuffixed public constants and constructor defaults retain the frozen
1.0 artifact. Its canonical bytes and digests are unchanged. The explicit
1.1 artifact adds the exact functional-form identifier
`harmonic_half_k_delta_squared_bond_angle/1.0.0` to the payload and full-set
hash graph. Each version has its own exact key set: 1.0 rejects an added form
field, while 1.1 rejects a missing, null, aliased, or different form. Schema
selection and the form field are keyword-only, and serialization and
assignment reconstruct a validated slotted snapshot so post-construction
mutation or instance-method injection cannot forge the designated bytes.

The unit system is fixed to angstrom, radian, and kilojoule per mole, including
dimension-specific bond and angle force-constant units. Numeric values are
encoded as canonical IEEE-754 binary64 big-endian hex. Non-finite values,
negative zero, mixed or aliased units, stale hashes, duplicate JSON keys, and
unknown fields fail closed. A parameter-payload digest covers the applicability
profile, policy, units, and values; a separate full parameter-set digest also
covers derivation and fit-evidence references. This separation avoids a hash
cycle when a later fit receipt references the parameter payload and the final
parameter-set manifest references that receipt.

Parameter sets built directly from caller-supplied fit digests can create only
`declared_fit_candidate_unverified`; they cannot claim that a fitter ran
successfully. Their execution status remains `unverified` and every runtime
gate remains closed. The typed synthetic receipt below is accepted only by
recomputing its bound nonphysical artifacts and does not promote that status.

The factory-only assignment report recomputes the molecular inventory and
binds the ordered topology digest, source-bound inventory report, complete
parameter-set content digest, resolved values, and exact canonical term maps.
The direct-constructor unit-test fixtures use deliberately nonphysical values
with `artifact_purpose=contract_fixture_only`; those fixtures are not fitted
results. The separate synthetic fitter can emit only a nonphysical,
unverified candidate under the same nonpromotion boundary. Neither path is a
force field, and both are excluded from package defaults and runtime selection.

Even when `bond_angle_assignment_complete=true`, atom typing, partial charge,
vdW, short-range electrostatics, proper torsion, improper, constraint, and
implicit-solvation parameter coverage remain `not_assessed`.
`global_parameter_coverage_complete`, parameterability, runtime eligibility,
execution, energy, force, minimization, simulation, and claim authority remain
false. Parameter and molecular digests provide deterministic binding, not
authentication or release approval.

### V2-2 nonphysical parameter-fit pipeline scaffold

The first fitting pipeline uses separate
`betelgeuze.parameter_fit_dataset_manifest/1.0.0` and
`betelgeuze.parameter_fit_split_manifest/1.0.0` artifacts, neutral row IDs,
and a factory-only `betelgeuze.parameter_fit_run_receipt/1.0.0`. The synthetic
rows live only under test fixtures. They are nonphysical arithmetic examples,
not scientific training data, and are excluded from the wheel and every
runtime registry.

The default fitting API remains pinned to the legacy 1.0 output parameter
artifact and its frozen 1.0 fit protocol. An explicit keyword-only 1.1 output
selection uses a distinct frozen form-bound protocol whose canonical document
binds the output parameter schema and the same functional-form identifier as
the parameter payload. A receipt therefore cannot be combined with a
parameter set from the other output schema; bundle reconstruction recomputes
the selected protocol and complete expected parameter set before acceptance.

For each of bond and angle, the fitter reads exactly three fit rows and solves
the quadratic coefficients with exact `Fraction` arithmetic. The protocol
requires `E(q)=0.5*k*(q-q0)^2`, positive curvature, and exactly zero additive
offset. It derives `q0=-b/(2a)` and `k=2a`; holdout rows are never used in the
fit and must have exact zero residual afterward. Canonical decimal inputs are
converted directly to rational values, never through floating point. Output is
accepted only when the exact rational result is exactly representable in the
declared binary64 parameter encoding. Angle observations and the fitted angle
equilibrium must also lie strictly between zero and pi radians.

The hash graph is acyclic: row bytes bind the dataset manifest; the split
manifest binds the dataset; the fit receipt binds dataset, split, protocol,
selected row digests, exact coefficients, and output parameter-payload SHA;
the final parameter-set manifest then binds the receipt SHA. The receipt does
not include the final full parameter-set SHA. Repeated runs and distinct
`PYTHONHASHSEED` values produce identical receipt and bundle hashes.
The receipt retains the three immutable input byte artifacts and re-runs their
loaders, manifest bindings, split selection, exact solve, holdout check, and
payload derivation before serialization or bundling. The bundle reconstructs
the entire expected parameter set from that recomputation. The frozen receipt
protocol and the parameter set use the same canonical protocol identifier;
mutating exported module labels after import cannot change the protocol bytes
or their SHA.

`fit_execution_status=succeeded` on this receipt means only that the synthetic
exact-arithmetic protocol ran and recomputed the bound payload. The resulting
ParameterSet remains `declared_fit_candidate_unverified`; scientific review,
physical validation, parameterability, runtime eligibility, energy, forces,
minimization, simulation, and claims all remain blocked. A licensed scientific
dataset, immutable split, reviewed provenance, independent validation, and a
trusted release attestation are still required.

### V2-2 SPICE C1--C4 quantum-reference observation evidence

The separate `spice_c1c4_quantum_reference.py` contract admits an exact,
non-runtime observation slice from SPICE 2.0.1 (DOI
`10.5281/zenodo.10975225`) and QCArchive singlepoint dataset 340,
`SPICE DES Monomers Single Points Dataset v1.1`, specification `spec_4`.
All 200 complete records are bound as four groups of 50 for methane through
n-butane, with Psi4 1.4.1 `wb97m-d3bj/def2-tzvppd` provenance. The admitted
release values preserve float32 coordinates in bohr, float64 total energies in
hartree, and float32 total energy gradients in hartree/bohr. The gradient is
`dE/dr`; it is not a force, and this contract performs no `force=-gradient`
transform.

The source generator contributes 25 related high/nearby-low conformation pairs
per graph. Partitioning is therefore pair-atomic: a domain-separated SHA-256
ordering over `(group_id, pair_id)` assigns 15/5/5 pairs per graph to
fit/selection/holdout, or 120/40/40 records globally. Exact record, geometry,
QCArchive molecule-ID, and source-pair overlap are zero, but all partitions
contain the same four molecular graphs and share release/time provenance. The
only valid split claim is
`within_same_four_graphs_unseen_conformations_only`; it is not graph-, family-,
time-, or release-disjoint validation.

This is observation-inventory evidence, not parameter evidence. Absolute
energies from different molecules cannot be fitted against one common offset;
a future protocol must use per-molecule relative energies or explicit nuisance
intercepts. Isolated monomer total energies and gradients do not identify a
transferable partial-charge, Lennard-Jones, or 1--4 model. The upstream source
declares CC0, while human license review and whole-file authentication remain
pending. No fit, candidate parameter set, parameterability, reference
validation, production parameter, physics, runtime, execution, or claim gate
is promoted.

### V2-2 SPICE C1--C4 source-authentication and license-review input packet

`spice_c1c4_source_review_packet.py` adds a factory-only, non-runtime review
input around the unchanged quantum-reference evidence. Its schema is
`betelgeuze.spice_c1_c4_source_authentication_license_review_packet/1.0.0`
and its exact claim scope is
`machine_prefilled_upstream_metadata_and_review_requirements_only`. The
canonical external packet binds the frozen evidence schema, byte count, core
and artifact SHA-256 before admitting any review fields.

The normalized metadata snapshot records the Zenodo version record, concept
DOI, revision, timestamps, dataset type and license identifier, and the one
HDF5 file's stable identifiers, exact byte count, official MD5, and content
URL. A separate GitHub snapshot binds release 2.0.1, its lightweight tag and
target commit, plus tag-pinned README and LICENSE blob IDs, byte counts, and
SHA-256 digests. GitHub reports the commit signature as verified, but the tag
itself is unsigned and the commit contains no HDF5 digest. Zenodo also has no
machine-typed GitHub relation. The packet therefore records observations and
tamper bindings, not a publisher signature or publisher-identity proof.

License contexts stay separate. Zenodo and the tagged README declare the
dataset data as CC0, while the repository LICENSE applies MIT terms to the
software and associated documentation. Neither declaration is converted into
a human scope decision, commercial-use clearance, or redistribution approval.
Reviewer decision, identity, timestamp, and attestation fields remain absent;
no reviewer PII or local absolute path is committed.

The packet also predeclares two missing receipts. The whole-file receipt must
stream all 37,479,271,148 bytes, match the official byte count and MD5, and
record a local SHA-256. A separate extraction receipt must bind that whole-file
receipt to exact HDF5 paths, selection/order protocol, shapes, dtypes, raw
array hashes, atomic numbers, mapped molecular identity, connectivity
derivation, record/index mapping, and the admitted evidence artifact/core
hashes. Those identity/mapping fields remain an explicit requirement for the
future receipt rather than a completed field in this prefilled packet. A locally
matched MD5 establishes only expected byte integrity, not collision-resistant
publisher authentication. Until those receipts and the independent human
review exist, whole-file integrity, subset extraction provenance, strong
publisher authentication, license review, legal clearance, fitting, science,
production, runtime, execution, and claim fields all remain false. CI and
runtime replay only the small committed packet and existing evidence; they do
not fetch or hash the HDF5 file.

### V2-2 SPICE C1--C4 source-bound force-matching target view

`spice_c1c4_force_matching_targets.py` is a separate, non-runtime transform
over the exact admitted source bytes. It replays the strict evidence loader and
derives 100 pair-relative energy targets as
`E(entry suffix p) - E(entry suffix p+25)`. Pair roles come only from the
numeric QCArchive entry suffix; the transform never energy-sorts the members,
takes an absolute difference, or uses a shared cross-molecule energy offset.
The `p+25` role preserves the source generator's nearby-lower provenance and
does not assert a QM minimum or a torsion-scan endpoint.

For all 200 source records, the raw force view is formed by flipping each
float32 gradient scalar's IEEE-754 sign bit, including signed zero, so its
meaning is explicitly `F=-dE/dr`. Coordinates, pair-energy differences, and
forces are converted to angstrom, kJ/mol, and kJ/mol/angstrom with a versioned
2022 CODATA central-value convention. The decimal central values are frozen as
protocol rationals and each output is rounded once to binary64; this is a
reproducibility convention, not a claim that measured constants are exact.
The resulting on-demand view contains 100 energy rows, 200 force rows, and
5,700 force scalars, partitioned 60/20/20 pairs and 120/40/40 records.

The canonical view is regenerated from the external evidence rather than
committed as a duplicate data artifact. It preserves source, topology, row,
protocol, value, and derived hashes and reports the raw net-force and
coordinate-centroid torque residuals. No rigid-body projection, centering,
clipping, or denoising is applied. The public holdout is pair-preserving but is
not blind to humans, and all partitions still share the same four graphs and
release/time provenance. This target transform defines no loss, fit, force-
field type, parameter, identifiability result, validation claim, production
physics, runtime dispatch, execution authority, or product claim.

### V2-2 SPICE C1--C4 fit-only bonded-basis observability

`spice_c1c4_bonded_basis_observability.py` is a downstream, non-runtime
preflight over the exact source-bound target view. It rebuilds the four C1--C4
graphs only from atomic numbers and connectivity and uses their 6 bond, 9
angle, and 7 proper graph-environment keys solely as diagnostic grouping
labels. Those labels are not force-field atom types, parameter identifiers,
chemistry perception, or a transferable typing claim.

The primary predeclared linear basis contains `0.5*r^2` and `-r` for every
bond key, `0.5*theta^2` and `-theta` for every angle key, and the parity-even
`cos(n*phi)` family for `n=1..3` for every proper key: 51 columns total.
Constants and intercepts are absent because same-topology pair differences
cancel them and their Cartesian derivatives are zero. Three additional,
non-selecting audit variants add sine terms and/or extend the declared
periodicity range through six. They are misspecification and allowed-family
stress checks, not candidate models, and no target residual is used to choose
among them.

Only the 60 fit pairs enter the audit. Canonical rows comprise one
`Phi(seed)-Phi(related)` energy row and both records' atom-major Cartesian
`-dPhi/dR` force rows per pair, for 60 energy and 3,420 force rows. A frozen
fit-only, graph-balanced and energy/force-class-balanced loss convention uses
RMS scales computed about zero from the fit targets; selection and holdout
values do not enter basis selection, scaling, rank, or conditioning. Pair
blocks remain the indivisible unit for any future resampling.

Each loss-weighted design column is normalized by its fit-only L2 norm before
a binary64 SVD. The report records matrix and metadata hashes, rank, nullity,
condition diagnostics, tolerance, backend metadata, and an explicit statement
that SVD values are not a cross-platform bitwise contract. All four
predeclared variants have full numerical column rank on the frozen fit slice,
but the only promoted statement is conditional design observability on these
coordinates and this weighting convention.

The protocol SHA-256 is
`063bbbea6d97ddc6f65242e70898442ae6514838c5acc02c9e2d57562089af93`.
The frozen fit-only RMS scales are 42.65680130781243 kJ/mol
(`4045541210b48320`) and 69.42751524726391 kJ/mol/angstrom
(`40515b5c68e9628d`). They are weighting receipts computed about zero, not
accuracy thresholds. With those weights, current local NumPy binary64 replay
gives rank/column counts and approximate condition numbers of `51/51, 181.87`,
`72/72, 198.23`, `72/72, 221.06`, and `114/114, 376.95` in protocol variant
order. Tests freeze exact shape, rank, nullity, and wide numerical gates rather
than singular-value bit patterns.

No coefficient, prediction, residual fit, candidate parameter, or committed
report artifact is produced. SPICE total energies and gradients also contain
intramolecular electrostatics, dispersion, 1--4, polarization, and coupled
effects that a bonded-only projection could absorb. Consequently bonded or
physical parameter identifiability, parameter-family sufficiency,
transferability, reference validation, parameterability, production physics,
runtime, execution, and claim gates all remain false.

### V2-2 prospective graph/family-disjoint population preflight

The metadata-decided `spice_graph_family_disjoint_population_preflight.py`
protocol keeps future scientific split claims separate before any expanded
population is admitted. Strict source-integrity replay decodes and validates the
already-frozen target payload, but population, family, and split decisions
consume topology and partition metadata only and never branch on target values.
Schema
`betelgeuze.spice_graph_family_disjoint_population_preflight/1.0.0` binds
protocol SHA-256
`57482f6a531b068c3589c7820025ed52e4af0cb3bde482180f8e9d08ba877415`.
Its hierarchy is `release -> chemistry family ->
parent/scaffold -> exact molecular graph -> related-conformer or geometry
cluster -> record`. A graph lane moves whole graphs; a family lane moves whole
families. Records, source pairs, and force scalars are never independent split
units. The outer uncertainty resampling unit is a graph or, when applicable, a
family; source-pair blocks may only be nested inside a graph, and force
components are not independent observations.

The current public C1--C4 partitions have four graph intersections and one
`linear_alkane` family intersection. They also share release and time
provenance and are not blind to humans, so every graph-, family-, time-,
release-disjoint and blind flag remains false. The v1 atom-order-independent
graph identity is exact only for bounded C/H trees whose isotope and stereo
states are both explicitly absent. It binds atomic numbers, bond orders,
molecular charge, and multiplicity. Any isotope- or stereo-present graph fails
closed until a new schema carries atom-level isotope labels and stereo
descriptors. The SHA-256 domain, rooted-tree encoding, canonical JSON recipe,
four C1--C4 graph digests, and topology receipt are all protocol-bound; current
local environment keys are prohibited as graph or family identities. Family
taxonomy, population inventory, split domains, metrics, thresholds, and
minimum graph counts must be derived without using energy or gradient values,
even though strict source-integrity replay decodes and validates those values.

Longer linear alkanes expose a coverage boundary. The C1--C4 union has 6 bond,
9 angle, and 7 proper keys. C5 adds one all-interior angle and two proper keys;
C6 adds a third new proper key, while C7+ adds no further local key under this
exact graph-only scheme. Therefore C5/C6 cannot validate the current C1--C4
parameter universe. A new version must put whole C1--C6 graphs into fit-only
coverage and establish the expanded basis and observability before unseen
C7+ graphs can be eligible for in-family graph-disjoint accuracy validation.
Branched, cyclic, or unsaturated families remain OOD/abstention evidence until
their own versioned applicability, coverage, and observability contracts exist.

The prescribed sequence is source/license receipts, target-independent
population and immutable split/threshold manifests, fit-only scaling and
candidate construction, selection, candidate/method freeze, one-shot public
graph holdout, family OOD or separately eligible-family evaluation, and then a
separate externally sealed blind set. Post-holdout changes require new dataset,
protocol, and candidate versions. This preflight contains no expanded rows,
targets, fit, coefficients, parameters, validation result, transferability,
production, runtime, execution, or claim promotion.

### V2-2 exact-methane harmonic numerical diagnostic

`betelgeuze.exact_methane_harmonic_diagnostic/1.0.0` is a deliberately
nonphysical, non-runtime numerical diagnostic over the exact-methane parameter
assignment. It accepts one cell-free CPU `float64` coordinate model in
angstroms, canonicalizes both the molecular system and parameter artifact,
recomputes a fresh exact four-bond/six-angle assignment, and retains only those
canonical bytes as the report's source of truth. Every property and serialized
report is derived again from those bytes; stale or malformed snapshots fail
closed.

The fixed diagnostic form is `E(q)=0.5*k*(q-q0)^2`. Bond distances and H-C-H
angles from `atan2(||u x v||, u dot v)` produce term-level energies and direct
analytic Cartesian forces. Bond lengths at or below `1e-8` angstrom and angle
sines at or below `1e-8` are rejected rather than regularized. Unit tests cover
all 15 Cartesian finite-difference coordinates, translation and proper
rotation behavior, atom permutation, net force and torque, equilibrium zeros,
and singularity failures. Results and force components use canonical binary64
big-endian hex, while hashes bind the full system snapshot, topology,
inventory, parameter payload/set bytes, assignment, and report.

This is only an implementation check for the scoped bonded formulas. A 1.1
parameter artifact binds the exact diagnostic form and records a matched
binding status; a legacy 1.0 artifact remains accepted only with the explicit
`parameter_functional_form_not_embedded_in_parameter_set_v1` blocker. Both
paths yield the same arithmetic for identical values but distinct bound
artifact and report hashes. This energy/force report itself omits nonbonded
terms, virial, global parameter coverage, minimization, and scientific
reference validation. Consequently
`physics_supported`, scientific validity, parameterability, runtime
eligibility, execution, energy/force authorization, minimization, simulation,
and claim authority all remain false. The module is not imported or dispatched
by the engine runtime.

### V2-2 form-bound nonperiodic bonded virial diagnostic

`betelgeuze.exact_methane_harmonic_virial_diagnostic/1.0.0` is a separate
contract-only follow-on to the energy/force diagnostic. It accepts only the
form-bound parameter schema 1.1 with
`harmonic_half_k_delta_squared_bond_angle/1.0.0`; legacy 1.0 and any other
form fail with typed errors. The report stores only canonical system and
parameter bytes and recomputes the exact assignment, analytic forces, every
term tensor, aggregate tensor, trace, statuses, and hashes on each access.

Its fixed nonperiodic convention is
`W[a,b] = sum_i F_i[a] * (r_i[b] - r_anchor[b]) = -dE/d epsilon[a,b]`.
Each bond uses canonical `atom_j` as its anchor and each angle uses its center,
so four bond and six angle tensors are translation invariant before they are
summed. Tests compare all nine affine-strain derivatives, isotropic dilation
against the negative trace derivative, term sums, proper-rotation covariance,
translation and atom-permutation behavior, torque/antisymmetry, equilibrium
zeros, canonical encoding, singularity and malformed-snapshot rejection.

Only `scoped_bonded_virial_assessed=true`; `complete_virial_assessed=false`.
The tensor does not define volume, pressure, stress, periodic virial, or any
nonbonded contribution. It is not a runtime force-field result and keeps
scientific validity, global parameter coverage, execution, energy, force,
virial, minimization, simulation, and claim authority false. The module is not
imported or dispatched by the engine runtime.

### V2-2 form-bound bounded-descent and restart diagnostic

`betelgeuze.exact_methane_harmonic_minimization_diagnostic/1.0.0` adds a
bounded numerical-descent contract over the same exact-methane harmonic form.
It accepts only parameter schema 1.1, one cell-free CPU `float64` model, and
the fixed form `harmonic_half_k_delta_squared_bond_angle/1.0.0`. The direction
is the raw analytic force. Every accepted step resets to the configured step
size and requires both strict energy decrease and the Armijo inequality;
the Armijo slope uses the sum of every Cartesian force-component square,
whereas termination uses the maximum per-atom force-vector norm. Both
definitions and their units are frozen in the protocol document. Singular or
nonfinite trial states are rejected and backtracked without
clipping, regularization, or a fallback algorithm. Accepted steps, trial and
rejection counters, energy/force values, harmonic and bonded-virial report
hashes, system snapshot hashes, and a rolling transcript hash use a frozen
canonical protocol. Configured work is capped at 256 accepted steps and 64
line-search trials per step. The force tolerance is positive and bounded above
by `1e-6` kilojoule per mole per angstrom, so an arbitrarily large threshold
cannot manufacture a stationarity observation.

Termination distinguishes scoped force-tolerance observation, accepted-step
limit, line-search exhaustion, a binary64 coordinate update that is not
representable, and failure to obtain a representable energy decrease after the
configured backtracking path actually reaches that coordinate floor. A trial
budget that merely stops after a same-energy candidate remains line-search
exhaustion and is not mislabelled as a representability result. Initial
coordinate negative zero is rejected, while exact-zero trial coordinates are
normalized to positive zero.
The force-tolerance result is explicitly first-order and is not a local- or
global-minimum attestation. The nonphysical fixture's simultaneous angle
targets are not a scientific equilibrium model.

The public pause path can stop at an accepted-step boundary and emit
`betelgeuze.exact_methane_harmonic_minimization_checkpoint/1.0.0`. The
checkpoint embeds canonical diagnostic-start and current system bytes,
parameter bytes, config, counters, state/report hashes, and the accepted-prefix
transcript. Deserialization fully replays the prefix and rejects canonical,
hash, counter, state, config, or authority tampering. Resume then continues the
remaining suffix from the verified current state and prefix counters; tests
require its final report to equal the uninterrupted report. Resume may pause
again after a bounded number of additional accepted steps, producing the same
canonical boundary checkpoint as a direct run. This exact replay claim is
limited to the same Python, PyTorch, CPU, and libm runtime. SHA-256 is binding
and tamper evidence, not authentication.

Diagnostic-created coordinate states start a bounded diagnostic provenance
ledger from the source-system snapshot digest, then append one versioned
operation and parent-state digest per accepted step. They always force
`preparation_ready=false` and `claim_safe=false`, even when the source system
arrives with affirmative provenance flags, and the parser-observation digest
is reattached after the provenance change. The implementation remains a
non-runtime steepest-descent diagnostic: nonbonded physics, scientific
parameters, minimum certification, cross-platform bitwise replay, production
minimizer behavior, and all execution, energy, force, virial, minimization,
simulation, and claim authority remain false. The engine does not dispatch it.

## 4. Linear-scaling contract

Let `N` be atom count, `E` the directed sparse-edge count, `K` the configured
maximum neighbors per atom, `L` network depth, `C` channel width, `r`
projection rank, and `W` temporal backpropagation window.

The short-range forward and reverse passes are `O(N)` only under all of these
conditions:

1. Fixed physical density and fixed cutoff permit `E <= K*N`.
2. `K` is finite and independent of `N`; overflow fails closed rather than
   falling back to all-pairs computation. Engine-owned geometry and sparse AI
   enforce a hard `K <= 256` cap; callers cannot raise it with `N`.
3. Cell-list construction and neighbor traversal use bounded occupancy or
   explicitly report overflow.
4. `L`, `C`, irreducible-representation order, radial basis count, candidate
   budget, refinement steps, and `W` do not grow with `N`. The reference local
   energy path additionally hard-caps layers at 16 and hidden width at 512.
5. Orthogonal projections use a hard rank cap of 16 or bounded local bases and
   never materialize an `N x N` projector.
6. No `torch.cdist`, dense adjacency, full attention, full Hessian, full
   Jacobian, global QR/SVD, or direct all-pairs electrostatics is used on the
   product path.

Under these assumptions, `E = O(N)` and a local layer costs `O(E)`. Reverse-mode
automatic differentiation traverses the same sparse operations, so its atom
count dependence is also `O(N)`. This is a conditional algorithmic contract,
not yet a measured performance claim. Constants may still be large.

### Periodic-boundary limitation in V2-0

The compact geometry builder tests orthorhombic minimum-image distances, but
the initial AI energy reference reconstructs edge displacement from raw
coordinates. That reconstruction does not yet carry the periodic image shift
through the energy/force autograd path. Consequently, the AI energy and CPU
reference orchestrator must fail closed when neighbor diagnostics declare a
periodic system.

Periodic execution remains blocked until the graph supplies differentiable
minimum-image displacement or image-shift data to the energy model and
finite-difference tests cross the unit-cell boundary. A passing neighbor-only
minimum-image test is not evidence of periodic energy or force correctness.

### Long-range physics

Short-range linearity does not make the whole physical solver unconditionally
linear:

| Method | Expected complexity | v2 policy |
| --- | ---: | --- |
| Direct Coulomb all-pairs | `O(N^2)` | prohibited outside tiny reference tests |
| PME | `O(N log N)` | acceptable truthful production option once validated |
| FMM | expected `O(N)` | claim requires fixed error tolerance, multipole order, bounded tree behavior, and scaling evidence |
| Fixed-cutoff screened electrostatics | `O(N)` | approximation must be named; not PME/FMM parity |

The public product must report the selected long-range method. It must not label
a PME execution as strict `O(N)` or an unvalidated FMM scaffold as production
linear scaling.

## 5. Equivariance and molecular chirality

The v2 energy model produces a scalar that is invariant to translation, proper
rotation, and permitted atom permutation. Forces are obtained as

`F_i = -dE_total / dr_i`

and therefore transform covariantly when the energy implementation is correct.

Molecular chirality prevents treating reflection as an interchangeable data
augmentation. The implementation uses SE(3)-equivariant coordinate behavior
with parity-aware features:

- R/S and E/Z stereo identifiers are canonical input features;
- signed triple products or equivalent pseudoscalar channels distinguish
  mirrored local environments;
- three local polar-vector branches form an explicit signed pseudoscalar; this
  is not yet a general irreducible-representation vector/pseudovector stack;
- reflection tests verify the declared parity behavior instead of requiring
  enantiomers to receive identical representations.

The term “E(3) GNN” in planning documents therefore means Euclidean geometric
message passing. The executable contract is more precise: proper-rotation
SE(3) equivariance plus explicit parity/chirality handling. A distance-only
model cannot be promoted as chirality-aware.

## 6. Non-attention AI components

### 6.1 Sparse energy GNN

The main AI contribution is an invariant residual energy,

`E_total = E_independent_physics + sum_i delta_e_i`,

not an unconstrained force vector. Exact differentiation supplies the residual
force. This preserves energy/force consistency and avoids a force-only model
being described as conservative without proof.

Messages are exchanged only across bounded sparse edges. There is no
Transformer, softmax attention, global pair tensor, `torch_geometric`, or
external equivariant-model dependency in the baseline implementation.

### 6.2 Torsion GNN and Temporal GNN are separate

`TorsionTopologyGNN` operates on a static bond/torsion tree. It propagates
rotatable-bond context and supports recursive forward kinematics plus a reverse
adjoint. It must not walk every torsion's descendant atoms independently,
which can become `O(N^2)`.

`TemporalStateGNN` operates across simulation or refinement steps using bounded
recurrent state. One-step cost is `O(N)`. A history-free rollout with truncated
backpropagation and final-state/chunk loss costs and retains `O(W*N)` state for
fixed window `W`. Returning every state intentionally retains `O(T*N)` memory,
and a loss over that history has `O(T*N)` backward work. Full-history rollout
is therefore outside the fixed-memory claim.

Combining these concerns behind a single ambiguous “T-GNN” name is prohibited
in code, evidence, and product reports.

### 6.3 PINN role

Physics-informed learning is a loss and release-gate layer, not the numerical
MD solver. It may combine:

- energy and force supervision;
- translation, proper-rotation, permutation, and declared-parity checks;
- net-force and net-torque residuals;
- force/energy finite-difference consistency;
- bond, angle, virial, pressure, and short-rollout residuals;
- uncertainty calibration and out-of-domain abstention.

PINN loss success cannot substitute for an independently implemented
integrator, force field, ensemble test, or public benchmark. Force-label
training may require higher-order differentiation; sparsity preserves the
conditional atom-count order but not a small runtime or memory constant.

## 7. Orthogonal projection and its adjoint

For a full-column-rank basis `B` with shape `(D, r)`, projection onto its span
is applied as

`P(v) = B @ solve(B.T @ B, B.T @ v)`

and projection onto the complement as

`Q(v) = v - P(v)`.

The dense `D x D` matrices `P` and `Q` are never materialized. With hard-capped
fixed `r`, application costs `O(D*r^2 + r^3)` and the vector adjoint uses the
same symmetric projector at that order. Rank-deficient or ill-conditioned
bases fail closed: a Moore-Penrose projector changes rank at that boundary and
does not provide the claimed exact basis gradient.

If `B` depends on coordinates, an exact gradient also includes derivatives of
the basis. Detaching `B` changes the mathematical operator and must be exposed
as an approximation. Exact v2 training leaves the basis in the autograd graph
and validates gradients against finite differences. Global QR/SVD over atom
axes and dense constraint pseudoinverses are excluded from the linear claim.

Approved initial projection uses include translation-mode removal, bounded
local frames, net-force/net-torque correction with a constant-size solve, and
fixed-rank separation of analytic and learned residual subspaces. Constraint
projection is linear only when graph degree and solver iteration count are
bounded.

## 8. Validation ladder and blocked claims

Implementation gates are intentionally independent:

1. **Contract gate:** schema validation, units, topology identity, no silent
   fallback.
2. **Mathematical gate:** sparse-bound checks, equivariance/parity tests,
   energy/force finite differences, projection-adjoint checks.
3. **Scientific gate:** all-atom force terms, energy conservation, ensemble
   properties, docking pose validity, calibrated uncertainty.
4. **Benchmark gate:** row-level public holdouts, dataset hashes, commands,
   seeds, baseline versions, confidence intervals, and failure rows.
5. **GPU gate:** CPU/ROCm energy, force, gradient, ranking, determinism,
   overflow, memory, and scaling parity on real hardware.
6. **Product gate:** versioned execution, reports, recovery, security, offline
   deployment, and accepted customer-shadow evidence.

Until the respective gate passes, all of the following remain blocked:

- GPU acceleration or CPU/ROCm parity claims;
- strict end-to-end `O(N)` claims;
- docking accuracy or external-tool parity claims;
- calibrated binding affinity, MM/GBSA, FEP, or wet-lab hit claims;
- validated all-atom MD or protein-structure prediction claims;
- periodic AI energy, force, docking-refinement, or MD claims;
- independent commercial-solver, broad-platform, or customer-ready claims.

Accounting, compilation, and unit-test success establish implementation
progress only. They do not promote scientific or product capability.
