# Engine v2 Public API Stability Policy

The independent distribution is named `betelgeuze-engine-v2`. Distribution,
engine API, molecular schema, runtime-input, checkpoint, and result versions are
separate contracts; see `betelgeuze_engine_v2.contracts.schema.VERSION_TAXONOMY`.

## Stability tiers

### Stable within an Engine API major version

Symbols explicitly exported from `betelgeuze_engine_v2.__all__` are the stable
root API. Compatible additions may occur in a minor release. Removal or an
incompatible signature/semantic change requires an Engine API major-version
change.

Stable root surfaces currently cover:

- all-atom state and validation contracts;
- canonical system/topology/coordinate hashes;
- bounded sparse-neighbor contracts;
- deterministic atom features;
- scalar-energy/force reference primitives;
- projection and energy-composition contracts;
- the fail-closed CPU reference orchestrator;
- version and quantity descriptors.

### Provisional submodule APIs

The following V2-M modules are intentionally importable but provisional:

```text
betelgeuze_engine_v2.io
betelgeuze_engine_v2.molecular.mmcif_*
betelgeuze_engine_v2.docking
betelgeuze_engine_v2.docking.flexible_geometric_scoring
betelgeuze_engine_v2.docking.geometric_refinement
betelgeuze_engine_v2.docking.molecular_torsion
betelgeuze_engine_v2.benchmark
betelgeuze_engine_v2.benchmark.public_flexible_diagnostic
betelgeuze_engine_v2.benchmark.public_materialization
betelgeuze_engine_v2.benchmark.public_protocol
betelgeuze_engine_v2.benchmark.public_rigid_diagnostic
betelgeuze_engine_v2.benchmark.public_suite_materialization
betelgeuze_engine_v2.physics.registry
betelgeuze_engine_v2.physics.reference_parameter_applicability
betelgeuze_engine_v2.physics.reference_diagnostics
betelgeuze_engine_v2.physics.reference_constrained_minimization
betelgeuze_engine_v2.physics.reference_forcefield_v2
betelgeuze_engine_v2.physics.reference_minimization
betelgeuze_engine_v2.physics.reference_ewald
betelgeuze_engine_v2.physics.reference_explicit_solvent
betelgeuze_engine_v2.physics.reference_canonical_ensemble
betelgeuze_engine_v2.physics.reference_ensemble_statistics
betelgeuze_engine_v2.physics.reference_nve
betelgeuze_engine_v2.physics.reference_nve_drift
betelgeuze_engine_v2.physics.reference_shake_rattle
betelgeuze_engine_v2.physics.reference_minimization_independent_oracle
betelgeuze_engine_v2.physics.reference_minimization_validation_artifact_binding
betelgeuze_engine_v2.physics.reference_minimization_validation_materializer
betelgeuze_engine_v2.physics.reference_minimization_validation_protocol
betelgeuze_engine_v2.physics.reference_minimization_validation_review
betelgeuze_engine_v2.physics.reference_minimization_validation_receipts
betelgeuze_engine_v2.physics.reference_minimization_validation_authorization
betelgeuze_engine_v2.physics.reference_minimization_validation_dependency_identity
betelgeuze_engine_v2.physics.reference_minimization_validation_nonce_reservation
betelgeuze_engine_v2.physics.reference_minimization_validation_run_start
betelgeuze_engine_v2.physics.reference_minimization_validation_runner
betelgeuze_engine_v2.physics.reference_minimization_validation_result_writer
betelgeuze_engine_v2.physics.reference_minimization_validation_result_review
betelgeuze_engine_v2.physics.reference_minimization_validation_trajectory_comparison
betelgeuze_engine_v2.physics.reference_solvation
betelgeuze_engine_v2.physics.reference_validation_protocol
betelgeuze_engine_v2.physics.reference_validation_materializer
betelgeuze_engine_v2.physics.reference_validation_oracle
betelgeuze_engine_v2.physics.reference_validation_artifact_binding
betelgeuze_engine_v2.physics.reference_validation_review
betelgeuze_engine_v2.physics.reference_validation_authorization
betelgeuze_engine_v2.physics.reference_validation_dependency_identity
betelgeuze_engine_v2.physics.reference_validation_nonce_reservation
betelgeuze_engine_v2.physics.reference_validation_run_start
betelgeuze_engine_v2.physics.reference_validation_runner
betelgeuze_engine_v2.physics.reference_validation_receipts
betelgeuze_engine_v2.physics.reference_validation_result_writer
betelgeuze_engine_v2.physics.reference_validation_result_review
betelgeuze_engine_v2.physics.validation_legacy_contracts
betelgeuze_engine_v2.physics.validation_native_runtime_identity
betelgeuze_engine_v2.physics.validation_process_launch_identity
betelgeuze_engine_v2.physics.validation_production_evidence_custody
betelgeuze_engine_v2.physics.validation_production_review_authorization_custody_extension
betelgeuze_engine_v2.physics.validation_production_reservation_custody_extension
betelgeuze_engine_v2.physics.validation_production_reservation_registry_proof
betelgeuze_engine_v2.physics.validation_production_reservation_authenticated_head_receipt
betelgeuze_engine_v2.physics.validation_production_reservation_later_head_consistency
betelgeuze_engine_v2.physics.validation_production_reservation_witness_quorum_non_equivocation
betelgeuze_engine_v2.physics.validation_production_reservation_epoch_transition_continuity
betelgeuze_engine_v2.physics.validation_runtime_integrity_contract
betelgeuze_engine_v2.physics.validation_source_identity
betelgeuze_engine_v2.offline.openmm_reference_oracle
betelgeuze_engine_v2.offline.openmm_reference_receipts
betelgeuze_engine_v2.offline.openmm_reference_materialization
betelgeuze_engine_v2.offline.openmm_reference_result_review
betelgeuze_engine_v2.offline.s0_production_evidence_bundle
betelgeuze_engine_v2.runtime
```

The five `betelgeuze_engine_v2.offline` modules are optional external-evidence
adapters, not product runtime APIs. Importing them does not import OpenMM. An
explicit observation requires the exact pinned `OpenMM==8.4.0.post2` native
build and selects only the `Reference` platform. The mapping contract covers
all 47 supported 27/59 variants, preserves 12 fail-closed rows as N/A, and also
binds the eight supported plus six N/A minimization cases. Receipt builders
record exact inputs, component/total energies, forces, fixed-Born self/pair
terms, runtime/binary/environment identities, and predefined max/RMS errors.
Builders reobserve runtime and adapter-source identity before and after the
calculation; readers independently recompute nested output, comparison, and
summary digests. This is not immutable external custody.
The installed `betelgeuze-engine-v2-openmm-materialize` command executes both
complete matrices into one canonical mode-0600 artifact, refuses replacement,
retains every failure row plus Engine iteration/rejection counts,
constraint/tangent-force metrics, energy/coordinate traces, and checkpoint
equality, and supports structural verification or exact local re-execution. It
accepts no private key and permanently records the run as an
offline observation with production execution, signed result, independent
review, two-host reproduction, scientific validation, and claim safety false.
The separate Ed25519 result-review contract freshly reverifies both Engine
result-review chains and both complete OpenMM receipts, then crosschecks the
exact 27/59 Engine component/total/force outputs and all fourteen retained
operational traces before signing a host/CPU/session/custody-scoped canonical
projection. It requires an out-of-band reviewer key, role separation, bounded
freshness, and explicit revocation/supersession inputs. No key, attestation,
production receipt, or populated two-host evidence bundle is included.
The final S0 bundle module freshly invokes that verifier for exactly two raw
host evidence sets. It rejects reused host/CPU/session/custody, artifact,
environment, authorization-nonce, and review-nonce identities while requiring
exact equality of commit, source, dependency, OpenMM runtime/source, seed, and
both physics projections. Its final Ed25519 approval is canonical, time-bounded,
revocable/supersedable, cannot outlive either host review, and requires a human
reviewer distinct from every nested role. Successful runtime verification
authorizes only frozen synthetic S0 acceptance and entry into S1; it explicitly
does not authorize a real-chemistry, validated-refinement, fitting, benchmark,
product, customer, or broad scientific claim. Its detached-signing API produces
a canonical secret-free request only after both host inputs verify, exposes the
exact approval bytes for an external or hardware Ed25519 signer, and verifies a
returned signature with a public key before attachment. The installed
`betelgeuze-engine-v2-s0-review` command supports `contract`, `signing-bytes`,
and `attach-signature`; it deliberately has no private-key option, rejects
symlinked or changing inputs, and creates mode-0600 outputs without overwrite.
Signature attachment never replaces full raw-evidence re-verification. No host
evidence, key, external custody assertion, or final approval is included, so
the static decision is closed.
OpenMM L-BFGS is exposed only as a separate endpoint result and is never
interpreted as Engine Armijo/Jacobi trace or checkpoint equivalence. These APIs
do not authorize production protocol execution, install OpenMM for customers,
or validate parameters, chemistry, or a product claim.

The frozen public-benchmark protocol symbols under
`betelgeuze_engine_v2.benchmark` define input identities, endpoint rules, and a
failure-inclusive reporting contract. The companion offline materializer
verifies caller-supplied frozen SDF bytes, parses bounded multi-record
references with a row for every match, mismatch, or failure, ignores identity-
seed coordinates, and uses atom/bond labels including directional V2000 stereo
to generate bounded graph matches and symmetry permutations. Its RMSD helper
does no ligand-only alignment and minimizes direct receptor-frame heavy-atom
RMSD across all matched reference records and admitted symmetries. Canonical
receipts bind the v1.1 protocol, artifacts, limits, rows, mappings, and binary64
coordinates. The separate suite materializer consumes either an offline mapping
or a non-symlink local root, verifies all twelve receptor/seed/reference
artifacts, and retains exactly four case rows with an embedded per-case receipt
or an explicit failure. Its installable command writes mode-0600 canonical
output and refuses overwrite. These APIs do not fetch or bundle data, interpret atom stereo
beyond directional V2000 bond marks, standardize chemistry independently,
generate docking poses, evaluate receptor-ligand validity, score/rank poses,
authorize benchmark execution or publication, or promote a scientific claim.

The provisional docking symbols include an atomic score-breakdown contract and
an explicitly uncalibrated CPU `float64` reference scorer. The scorer requires
caller-bound canonical receptor/ligand systems plus explicit nonbonded and
ligand bonded parameters; it reports cross Lennard-Jones, screened Coulomb,
signed ligand internal-energy delta, and VDW-overlap contributions separately.
Its first scope admits only H/C/N/O/F/P/S/Cl/Br/I with exact partial-charge
agreement, rejects receptor nonpolymer cofactors and unsupported elements, and
does not implement metal coordination, aromatic-specific interactions, stereo
validity, fitted ranking weights, uncertainty, or a customer route. The
fit-only ranking-calibration symbols separately require an exact term schema
and a passing identity-overlap audit, fit pairwise logistic weights from the
`fit` partition only, and retain failed evaluation poses in all-case and
target-family Top-1/Top-5/coverage bootstrap denominators. Evaluation schema v2
also retains every ranked score/label and failure code, reports tie-invariant
pose-level average-precision PR-AUC over the successfully scored, labeled poses,
with explicit successful/failed/all-pose counts and coverage so scoring failures
cannot disappear from the receipt. It bootstraps by case rather than treating
poses as independent. A family with no positive and negative successful pose
labels emits an unavailable metric with explicit blockers instead of a
fabricated value. A separate claim-closed confidence evaluator binds this v2
ranking report and transforms the top-1/runner-up minimize-score margin with a
logistic function. It reports case-level decisions, Brier score, fixed-bin ECE,
threshold coverage/risk, tie-inclusive selective-risk curves, reliability bins,
case-cluster intervals, and the same outputs per target family. Cases with fewer
than two successful poses abstain and remain in the all-case/all-pose
denominators. The margin signal is explicitly a diagnostic proxy: it has no
disjoint probability-calibration fit, its threshold is not independently
reviewed, and every confidence report remains `probability_calibrated=false` and
`claim_safe=false`. These APIs do not
bundle a public partition, fitted model, holdout result, independent rerun, or
promotion.

The public rigid-diagnostic symbols reverify the full input suite, derive a
single redocking pocket from the lowest-index graph-matched native record,
rigidly de-leak the seed orientation with a fixed rotation, generate bounded
rigid poses, and retain every candidate's element-radius score decomposition,
apply receipt-bearing deterministic rigid coordinate descent to the initial
diverse score Top-K, re-rank, and retain geometric validity plus direct
receptor-frame symmetry-aware RMSD. Case rows include complete accept/reject
refinement traces, Top-1/Top-5, and oracle-best generation diagnostics so
proposal coverage is distinguishable from ranking failure. The report always
records that native coordinates defined the pocket, the cohort is not a
scientific holdout, and torsions, supported-force-field refinement, charge-aware
force-field scoring, external baselines, probability calibration, independent
rerun, and claim promotion are absent.

The separate public flexible-diagnostic symbols materialize the bounded
bridge-only molecular torsion tree for each seed, generate candidate zero at
zero torsion followed by deterministic independent uniform torsion samples,
then use the same failure-complete scoring, validity, receptor-frame RMSD, and
Top-K rigid geometry refinement path. Every case embeds its all-bond torsion
receipt. Its flexible scorer adds a fixed element-radius nonbonded self-overlap
term while excluding covalent 1-2 and angular 1-3 pairs. This is not a
torsion-energy or bonded-force-field model or validated conformer generation;
final Top-K selection excludes invalid poses before score-order diversity, but
torsions are not refined and all rigid diagnostic nonclaims continue to apply.

`betelgeuze_engine_v2.benchmark.public_external_baseline` provides the separate
same-input external-baseline preparation boundary. Callers must provide exact
prepared receptor and ligand PDBQT files plus source hashes and exact
preparation tool/version, configuration, executable, and optional container
identities. The builder reverifies all four files without following symlinks,
derives each receptor-frame pocket center from the lowest-index matched native
record, freezes a 22.5-A cube and deterministic search parameters, and emits
exactly one non-executing work order for each of Vina, GNINA, and Smina. Bundle
construction rechecks that all three orders carry identical prepared input
hashes and exact engine-specific command and score semantics. Native coordinates
are admitted only for box definition and are explicitly forbidden as ligand
preparation coordinates. The API bundles no PDBQT data or external executable,
launches nothing, and records `results_present=false`,
`scientifically_validated=false`, and `claim_safe=false`; the development
four-case cohort is not a statistical holdout or public benchmark result.

`betelgeuze_engine_v2.benchmark.public_split_provenance` is the public-data
lineage boundary above the generic pose-ranking calibration API. Its frozen
catalog distinguishes PDBbind v2020 fit inputs, the 285-case/four-endpoint
CASF-2016 evaluation, and the published 308-case PoseBusters Benchmark. It does
not download data or accept access terms. Sources must carry exact archive,
selection, license-text, and—where access is not open—external authorization-
receipt identities. The official PoseBusters 308-ID attachment is pinned as raw
SHA-256 `a69a7b6b9a5a52531933078ef983e6c069e3a987a1d7a733bd7d72cbe1793de6`
and canonical sorted case-ID projection SHA-256
`fb3d12a98fb61d95f306ecf36188d66dddf64303389915a72b2a9b96cc97f3f6`.

Each split case binds exact receptor, ligand, scaffold, and canonical protein-
chain-set hashes plus release date, target family, cofactor category, and
supported/unsupported chemistry disposition. The sequence receipt binds exact
Smith-Waterman/BLOSUM62 implementation/configuration identity and the maximum
query-fraction identity over all evaluation/fit protein-chain pairs, retaining
the paper-compatible low/medium/high strata. The leakage audit records exact
case/PDB/target/receptor/ligand/scaffold/sequence overlaps, optional temporal
ordering, and a caller-frozen maximum sequence-identity policy. Public partition
bindings then match every generic calibration row to this manifest. A final
result binding verifies the evaluation report's all-case and target-family
denominators. Every artifact remains `claim_safe=false`; no full source manifest,
similarity execution, fitted model, benchmark result, or independent rerun is
bundled.

`betelgeuze_engine_v2.benchmark.public_posebusters_intake` is the bounded local
archive boundary for the published PoseBusters set. The installed
`betelgeuze-engine-v2-posebusters-intake` command requires the exact frozen
53,660,397-byte Zenodo ZIP and exact 2,772-byte journal 308-ID selection as
caller-provided, non-symlink regular files. It checks both identities before
auditing the ZIP central directory without extraction. Duplicate or unsafe
names, encryption, unsupported compression, symlinks, unexpected entry,
uncompressed-byte or case counts, oversize members, and metadata identity
mismatches fail closed. It then CRC-streams and SHA-256 binds the receptor,
single reference ligand, reference-ligand collection, and ligand start
conformer for every selected case. Every selected case remains present as a
success or failure row.

The canonical receipt is written mode 0600 without replacement and can be
verified by exact local reexecution. The command performs no network access,
license acceptance, archive extraction, preparation, pose generation, scoring,
or benchmark execution. `input_identity_ready=true` means only that the exact
published input carriers and 1,232 selected members passed intake; scientific
validation and claim safety remain false. A 2026-07-23 local, unbundled
observation produced 308/308 ready rows with receipt payload SHA-256
`e76c31517be668eb2073cd78a83dd0e2327a041fefe98e9dfed9bab3635b66c6`
and exact reexecution equality. The data files and receipt are ignored runtime
state, not package evidence.

`betelgeuze_engine_v2.benchmark.public_posebusters_corpus_audit` adds a second,
installable extraction-free gate after that intake. The
`betelgeuze-engine-v2-posebusters-corpus-audit` command reexecutes the exact
archive-intake receipt, parses the receptor, native ligand, and start conformer
for every selected case, and retains parser failures, receptor/ligand element
and formal-charge inventories, operational metals, non-water nonpolymer residue
names, ligand atom capacity, heavy-atom labeled-graph identity, raw V2000 bond-
type-4 counts, and raw directional V2000 bond-stereo identity. Every rate uses
all 308 cases and a Wilson 95% interval. Nonorthogonal `CRYST1` observations are
validated and retained but not materialized as a periodic docking cell; fixed-
column `CONECT` parsing supports contiguous five-digit serials.
The receipt also binds exact source SHA-256 values for the audit, heavy-graph
comparison, both PDB parser layers, SDF parser, archive intake, frozen graph
search, and provisional scorer-scope implementation.

The 2026-07-23 local ignored-state receipt audited 308/308 cases with exact
reexecution equality (receipt payload SHA-256
`a239aae11a46be01c5f6f11082e6aa51cd57f256e228082c80abae3a6a3b4507`).
Heavy labeled connectivity matched 308/308, while raw directional bond marks
matched 128/308 (Wilson 95% CI 0.361916–0.471332). All ligand elements, parsed
formal charges, and ligand atom counts were inside the provisional scorer
limits, but only 159/308 receptors were inside its element list, 161/308 cases
were metal-free, and 34/308 were free of non-water cofactors. Consequently only
34/308 reached the chemistry-only scope boundary (95% CI 0.080078–0.150300),
and 0/308 were admitted because no partial-charge or parameter assignment was
performed. Both ligand files used Kekulized bonds: zero cases contained raw
V2000 aromatic bond type 4. That is not evidence that the molecules are
nonaromatic. Likewise, raw directional-bond equality is not atom-stereo
validation. The receipt runs no aromaticity/stereo oracle, preparation, pose
generation, validity, scoring, external engine, target-family analysis, or
benchmark, and remains `claim_safe=false`.

`betelgeuze_engine_v2.benchmark.public_posebusters_native_geometry` adds an
installable, extraction-free positive-control preflight. The
`betelgeuze-engine-v2-posebusters-native-geometry` command exactly reexecutes
both prerequisite receipts, securely reopens and rehashes the frozen archive,
and evaluates the native crystal pose in the receptor frame. It records the
minimum receptor/ligand fixed-radius ratio at overlap scales 0.82 and 0.58,
topology-excluded ligand self-overlap at scale 0.75, and the maximum native/start
heavy-bond length delta against 0.15 Å. The start SDF is explicitly treated as
an RDKit ETKDGv3 then UFF-minimized conformer, not a pose. Each row retains exact
binary64 values, atom indices, unsupported elements, metals/cofactors, and an
exact case-CCD residue-name-presence observation without inferring covalency.
All rates use the full 308-case denominator and Wilson 95% intervals; runtime,
source, threshold, radius-profile, and coordinate-role identities are bound.

The 2026-07-23 local ignored-state receipt processed 308/308 with zero failures
and exact reexecution equality (receipt payload SHA-256
`118c1c0db0424504ad7727e1b7bbbc355138f2693805439061395421da109a12`;
receipt-file SHA-256
`f01f9a6e00eab649e73e24a3f2b8871f7cdc936321a86a07fc838fc4951996cd`).
Element geometry was evaluable for 159/308; 156/308 were free of the deeper
fixed-radius threshold, 127/308 were free of the overlap threshold, 308/308
passed the self-overlap heuristic, and 195/308 met the heavy-bond-delta
tolerance. The bounded geometry conjunction was 89/308 (95% CI
0.241184–0.341937). Six receptors retained a residue name equal to the case CCD;
this is an observation, not a covalent-assignment claim. The existing reference-
scorer chemistry boundary contained 34/308, and its intersection with bounded
geometry was 15/308 (95% CI 0.029733–0.078789). Complete pose validity remains
0/308 (95% CI 0–0.012319) by construction. These are unvalidated native-pose
heuristics, not force-field strain, generated-pose validity, PoseBusters oracle
results, redocking, scoring/ranking, target-family performance, or benchmark
evidence; `benchmark_executed=false` and `claim_safe=false`.

`betelgeuze_engine_v2.benchmark.public_posebusters_external_preparation` adds a
strict, optional-runtime preparation gate after the exact intake and corpus
audit. The installed `betelgeuze-engine-v2-posebusters-external-prepare`
command attempts only rows whose provisional scorer scope is blocked solely by
missing parameters and partial charges. Ligands are read from the explicit-H
start conformer and prepared with the frozen Meeko 0.7.1 AD4/Gasteiger defaults;
receptors use default residue templates with no residue deletion, alternate-
location override, flexible residue, or `allow_bad_res`. The native crystal
ligand is passed only to the source-bound heavy-atom-centroid box definition.

The receipt binds the resolved Python executable, platform/ABI fields, Torch
version, and path-independent regular-file payload aggregates for Meeko 0.7.1,
RDKit 2025.9.6, NumPy 1.26.4, SciPy 1.12.0, Gemmi 0.7.5, and tqdm 4.67.1. It also
binds the complete configuration SHA-256, every source role/hash, exact PDBQT
size/hash/path, bounded error-message and diagnostic hashes, failing receptor
residue keys, and all-case Wilson 95% intervals. Artifact materialization is
mode 0700/0600 and no-overwrite; verification regenerates every attempted case
and rejects missing, extra, symlinked, permission-changed, or byte-changed
artifacts.

The 2026-07-23 local ignored-state receipt attempted 34/308 cases. Ligand
preparation succeeded for 34/308 (95% CI 0.080078–0.150300), while strict
receptor preparation and complete input-pair materialization succeeded for
18/308 (95% CI 0.037283–0.090479). It retained 15 template-matching failures,
one other receptor-construction failure, and 274 chemistry abstentions. Exact
reexecution matched receipt payload SHA-256
`3856706f5b470386e9151bc272f158192839683deaf08a2bc8f1d377b22082ba`,
receipt-file SHA-256
`11f76f2571e68232095877e4dd215e51de3d02e4d860267f7b533a56bf9212d4`,
and artifact-set SHA-256
`5ff0ae2a54ec1c70f61011b76a24242a0eccbffbd23f523ff035f9e18e040e19`.
These outputs are ignored local state, not bundled package evidence. Default
atom types and charges are not independently validated; no Vina, GNINA, or
Smina engine, generated pose, PoseBusters oracle, RMSD, score, family metric,
leakage audit, or independent rerun is present. `external_engine_executed=false`,
`benchmark_executed=false`, and `claim_safe=false` remain mandatory.

`betelgeuze_engine_v2.benchmark.public_posebusters_vina_execution` adds a
failure-inclusive Vina execution layer after strict preparation. The installed
`betelgeuze-engine-v2-posebusters-vina-execute` command has `materialize` and
`verify` modes. Both require the exact expected preparation-receipt payload
SHA-256, its canonical mode-0600 bytes, and its complete private artifact tree.
The preparation, output, and scratch roots must be disjoint real paths; output
materialization is private and no-overwrite.

The runtime is fixed to the Vina 1.2.7 Python distribution and must have the
same pinned preparation-runtime identity. Its identity covers the Python API
source, wrapper/native/shared-library payload, Python/platform/ABI, Torch, and
the Meeko/RDKit dependency closure used for preparation. The frozen search uses
the Vina scoring function, CPU count 1, seed 20260723, a native-centroid 22.5 Å
cube, 0.375 Å spacing, exhaustiveness 32, up to 20 modes, 1 Å minimum mode
separation, and a 20 kcal/mol output range. The receipt records every one of the
308 dispositions, exact generated PDBQT bytes, pose count, total/inter/intra/
torsion/intra-best energy components as canonical binary64 hexadecimal values,
bounded diagnostics, all-case Wilson 95% intervals, configuration and source
hashes, and exact input/output artifact identities.

The 2026-07-23 local ignored-state production receipt attempted 18/308 and
succeeded on 18/308 (95% CI 0.037283–0.090479), with zero engine failures (95%
CI 0–0.012319). It retained 16 strict-preparation blocks and 274 chemistry
abstentions and stored 355 poses across 18 private artifacts. Exact source-tree
and installed-wheel reexecution matched receipt payload SHA-256
`37b3df7c4c14d739d9fca3970dc73293a48909372314a8dfe1da5bcd956694ae`,
receipt-file SHA-256
`97cedf1d1f082d60decdf86184b5cf8b7358df1da36f31ddc33ae0ff04902c63`,
and artifact-set SHA-256
`706d9beef07d6065a914b0bd03367282a42833ffe1dae3e72adc57fd69dc4f7e`.
The configuration, implementation, and engine identity SHA-256 values are,
respectively,
`bbe44bef15f8620ae33e6358a7206382505c9faa338f36c4b662708cd0abacfb`,
`1efaf429becda5c7e343328c9157a431d7faa01b1dfb5eda495293baaf2761b8`,
and `5b620a109866a28293a82ddeb37efe4750ab053cfa1e016b3d72fcc47630e6b2`.
Two builds under the pinned setuptools 75.8.2 and wheel 0.45.1 toolchain were
byte-identical at wheel SHA-256
`68380b90af9ac286a70e264cb2603288ae5a2d639f32f27b1ae376bdaebc6228`;
the installed-wheel verification imported the package from that isolated wheel
tree rather than the repository checkout.

These generated poses have not passed the PoseBusters redock oracle or a
symmetry-aware native RMSD evaluation. Default AD4 types and Gasteiger charges
remain unvalidated, GNINA/Smina same-input receipts are missing, and no
target-family, leakage, calibration, independent-host, or reviewer receipt is
present. Therefore `benchmark_executed=false`, `scientifically_validated=false`,
and `claim_safe=false` remain mandatory.

The frozen H5 reference-parameter applicability symbols under
`betelgeuze_engine_v2.physics` record caller-supplied parameter origin, exact
implemented equations, code-enforced execution admission, capacity defaults,
and bound source hashes. They do not ship or assign a parameter set, parse the
reviewed Sage artifact, establish chemical applicability, authorize fitting or
validation, or enable a customer/runtime physics route.

The frozen CPU reference validation-protocol symbols under
`betelgeuze_engine_v2.physics` define exact synthetic fixture/mutation/case
identities, float64 energy/force tolerances, failure-inclusive aggregation,
independent-oracle requirements, future result-receipt fields, and an executable
closed authorization decision. They do not materialize fixtures, implement an
oracle, run validation, approve caller-supplied parameter values, establish a
scientific applicability domain, authorize parameter fitting, or promote a
scientific or product claim.

The bounded reference-minimization symbols accept only a single CPU `float64`
model and caller-supplied explicit reference parameters. They expose fixed
steepest-descent, Armijo-backtracking, capacity, displacement, and evaluation
bounds; a failure-inclusive observation ledger with complete canonical binary64
coordinates for every evaluation; and canonical binary64 checkpoints that bind
source-system, topology, parameter, configuration, and ordered coordinate-trace
identities. Restart first reproduces the complete checkpoint from the trusted
source input and requires exact history equality, then re-evaluates the stored
state before continuation. Standalone checkpoint parsing verifies canonical
form and internal self-hash consistency; source authenticity is established by
that trusted-input replay boundary. These provisional symbols do not ship or
assign parameters, establish chemical
applicability, validate minimization accuracy, satisfy the frozen independent
validation protocol, or enable a scientific/product/customer route.

The bounded direct-Ewald symbols expose an immutable canonical config and a
force-field evaluator for one neutral CPU `float64` coordinate model in a full
3D orthorhombic cell. The fixed convention is conducting/tin-foil boundary,
potential-shifted `erfc` real space at the v1 parameter cutoff, a full symmetric
rectangular reciprocal lattice, analytic self energy, and same-cell exclusion
or 1-4 `erf` correction. The evaluator reconstructs and checks the frozen v1
screened-Coulomb energy before replacing both its energy and force, preventing
silent double counting. Alpha, reciprocal bounds, neutrality tolerance, system,
topology, parameters, and neighbor identity are fingerprinted. This is direct
Ewald, not PME; non-neutral/background, partial-periodic, triclinic, non-CPU,
non-float64, oversized, or screened-kappa inputs fail closed. Formula and
finite-difference unit comparisons are implementation tests, not independent
scientific validation or convergence acceptance.

The bounded explicit-solvent symbols compose a complete, unboxed, single-model
CPU `float64` solute and its exact caller-bound reference parameters with a
frozen source-identified Amber TIP3P/Joung--Cheatham Na+/Cl- profile. The
result is not a label-only carrier: it materializes explicit water and ion
atoms/residues, water bonds and angles, Lennard-Jones and charge values,
intrawater exclusions, three rigid-water distance constraints, a full 3D
orthorhombic cell, and canonical source/system/topology/parameter/constraint/
placement identities. The deterministic lattice enforces box, clearance,
capacity, exact partial-charge binding, and neutral-direct-Ewald admission and
reports water/ion counts and molarity. A trusted-input replay helper re-runs the
complete preparation and requires exact artifact and coordinate identity. It is an unequilibrated implementation
fixture. It does not establish that the frozen source was transcribed by an
independent reviewer, reproduce liquid or ion observables, compare energy or
forces with an external implementation, authorize broad chemistry, or enable
scientific/product/customer use.

The bounded canonical-ensemble symbols expose immutable NVT/NPT integration
configs, constrained BAOAB Langevin dynamics, a domain-separated counter random
stream, optional molecular-centre isotropic Monte Carlo volume moves, complete
barostat attempt rows, mutable-cell trajectory frames, and canonical
checkpoint/restart. The checkpoint binds the exact RNG word index as well as
source, parameter, thermostat, barostat, Ewald, constraint, coordinate,
velocity, cell, energy, pressure-observation, and trace-head identities. The
separate ensemble-statistics symbols require an all-step fresh trajectory and a
genuine pause/resume endpoint; they report energy, temperature, and for NPT
volume and finite-difference molecular-pressure series with autocorrelation,
effective sample size, confidence intervals, threshold rows, and all failures.
These provisional APIs neither establish equilibration nor validate the
thermostat, barostat, pressure estimator, random stream, ensemble distribution,
liquid observables, cross-host/GPU parity, or any scientific/product claim.

The bounded reference-NVE symbols implement CPU `float64` velocity-Verlet for
one canonical model with explicit atom masses and caller-bound reference
parameters. Every force evaluation rebuilds the compact neighbor list;
non-periodic and full 3D orthorhombic PBC inputs are admitted, with periodic
coordinates wrapped each step. An optional constraint config applies bounded
canonical-pair-order inverse-mass SHAKE corrections based on the previous
constrained pair vectors, transfers each position correction into the half-step
velocity, and applies RATTLE radial-velocity projection after the second force
kick. Fresh constrained runs require the source coordinates to satisfy the
internal position tolerance before the initial velocities are RATTLE-projected.
Periodic constraints use minimum-image vectors and reject ambiguous target
distances. Canonical binary64 frames form a trajectory hash chain; the
checkpoint binds source, topology, parameter, integration and complete
constraint configurations, residual maxima, cumulative SHAKE/RATTLE iterations,
runtime, state, energy drift, and chain identities for bit-exact continuation.
Its integration config can optionally bind the neutral direct-Ewald reference;
that selection and the entire Ewald config survive canonical checkpoint parsing
and bit-exact restart. This is an implementation contract only:
general solute constraint/mass assignment, accepted drift or Ewald-convergence evidence,
independent SHAKE/RATTLE/Ewald or cross-host reproduction, PME, net-charge
background, independently accepted thermostat/barostat and NVT/NPT statistics,
triclinic cells, GPU parity, and all scientific/product/customer promotion
remain unavailable.

The bounded reference-NVE-drift symbols require a fresh all-step NVE result and
a separately executed pause/resume result. They reconstruct every step's
energy drift, raw kinetic temperature using the explicit
`3N - declared distance constraints` convention without center-of-mass removal,
linear momentum and momentum drift, and current position/velocity constraint
residuals. Frame, coordinate and velocity byte digests retain trajectory
identity. Maximum/RMS energy and momentum drift, least-squares energy-drift
slope, and exact final checkpoint/trajectory equality are evaluated against a
fixed nine-row caller-bound acceptance config; failed rows remain in the same
denominator. Subsampled or over-capacity traces fail closed. A numerical pass
does not establish accepted thresholds, independent or two-host reproduction,
force-field validity, NVT/NPT ensemble behavior, or a scientific/product claim.

The bounded reference-diagnostics symbols leave the frozen evaluator source
unchanged and numerically differentiate its five component energies over every
coordinate of a single CPU `float64` model. They retain all expected plus/minus
perturbation rows, suppress partial tensor outputs after any failed evaluation,
check component-force sums against the analytic total force, and expose
centered-coordinate configurational virials only for non-periodic systems.
Periodic virial fails closed because a cell-strain derivative is not yet
implemented. The outputs are provisional implementation diagnostics, not an
independent scientific reference, pressure/stress, parameter validation, or a
scientific/product/customer claim.

The versioned reference-forcefield-v2 symbols wrap, rather than modify, the
frozen v1 evaluator and explicit parameter object. They expose an ordered-star
harmonic out-of-plane improper parameter/evaluator and a bounded deterministic
simultaneous degree-relaxed equal-weight distance-constraint projector with per-
iteration residual rows and minimum-image distances for supported orthorhombic
PBC. The separate constrained-minimization symbols project every trial, use a
bounded iterative tangent-force projection, apply Armijo decrease to actual
projected displacement, retain nested projection failures, and bind source,
topology, v2 parameters, configuration, observations, and complete raw/projected
binary64 coordinate traces into exact checkpoints. Constrained restart applies
the same trusted-source full-history replay before continuing. The constraint
path does not use atomic masses.
Parameters remain caller supplied; general assignment, independent validation,
long-range physics, solvation, scientific promotion, and product/customer
execution remain blocked.

The fixed-Born solvation symbols expose a bounded non-periodic CPU `float64`
polar dielectric-transfer term using the Still generalized-Born pair function.
They require one caller-supplied fixed effective Born radius per atom, exact
topology identity, a radius-source SHA-256, and the exact v2 charge-parameter
fingerprint. A combined evaluator adds the polar term to the versioned v2 energy
and force while remaining composition-disabled. The constrained minimizer may
optionally include that combined energy/force and binds the solvation-parameter
fingerprint into exact checkpoint/restart identity. The API does not estimate
Born radii or implement nonpolar solvation, salt/ions, periodic solvent, or MD,
and it carries no independent solvation/minimization or product validation.

The minimization-validation-protocol symbols freeze fourteen ordered cases and
ten predefined acceptance metrics across the unsolvated, constrained, fixed-
Born constrained, checkpoint/restart, and fail-closed identity/applicability
lanes. The document binds exact implementation-source identities, retains every
case in the denominator, requires an independently implemented reference before
execution, and exposes an authorization function that always fails closed. It
does not materialize cases, implement the independent reference, authorize or
run validation, collect results, validate parameters or minimization, or enable
scientific/product/customer claims.

The separate minimization-validation-materializer symbols resolve all eleven
frozen fixture payloads and project all fourteen cases into deterministic CPU
`float64` `AllAtomSystem`, v1/v2 parameter, fixed-Born parameter, bounded
minimization configuration, checkpoint-pause-plan, and fail-closed identity
injection objects. Its canonical manifest binds every runtime input identity
and retains every failure case. The module imports configuration and parameter
contracts but no evaluator or minimizer entrypoint; it neither evaluates
physics nor creates checkpoints, metrics, validation results, or promotion
evidence. The original frozen protocol document remains byte-identical and
therefore still records its historical materializer-missing blocker; the
separate manifest does not mutate or open that protocol's authorization gate.

The independent-minimization-oracle symbols consume only primitive materialized
inputs and the already audited standard-library analytic oracle. They separately
implement constraint and tangent-force projection, fixed-Born energy/forces,
bounded backtracking, fail-closed identity/applicability outcomes, and canonical
checkpoint/restart. The artifact-binding symbols freeze the exact materializer,
analytic-oracle, and minimization-oracle source identities and AST-audit the
import boundary. These source and test artifacts are not production validation
receipts, independent scientific review, execution authorization, parameter
applicability evidence, or scientific/product promotion.

The minimization-validation-review symbols freeze a signed independent-review
attestation schema over the exact source binding. Verification requires a
repository-external trusted reviewer key, a reviewer identity distinct from the
implementation author, complete ordered checks and limitation acknowledgements,
and a bounded validity interval. The repository bundles no key or attestation;
even a valid review verification cannot authorize execution or fitting.

The separate validation-artifact symbols materialize the exact frozen fixtures
and mutations into deterministic CPU float64 runtime inputs and provide a
standard-library-only scalar analytic oracle with exact forward-mode forces.
The binding record fixes both source SHA-256 identities, the materialization
manifest, and an AST-enforced import boundary. These artifacts do not compare
the oracle with the reference evaluator, execute the frozen validation study,
create result or metric receipts, independently review parameter values or the
oracle, establish chemical applicability, authorize fitting, or open customer
execution. `require_reference_validation_execution_authorized()` always fails
closed for the current binding.

The separate review-contract symbols define and verify a future signed
independent-review attestation. Verification requires an out-of-band trusted
reviewer key, exact artifact dependencies, an implementation-author identity
distinct from the reviewer, complete ordered review checks and limitations, and
a non-expired validity window. The package bundles no reviewer key or
attestation. A verified review remains only an input to a future separately
signed execution authorization and cannot open execution or fitting by itself.

The authorization-contract symbols define and verify a separate future
operator-signed single-run receipt. They require a still-valid verified review,
pairwise-distinct implementation-author/reviewer/operator identities, an
out-of-band trusted operator key, exact code/runner/environment/result/dependency
identities, a maximum 24-hour lifetime, external revocation sets, and an unused
one-time nonce. No key or receipt is bundled. Successful verification is only
eligible for future atomic nonce reservation and still reports
`validation_execution_authorized=false`.

The nonce-reservation symbols re-verify the raw signed review and authorization
artifacts and durably consume a nonce in a caller-provisioned private local
POSIX directory using exclusive creation and file/directory synchronization.
Their exact-raw byte verifiers expose canonical record validation without a
pathname read, while deliberately making no independent claim that exclusive
creation or synchronization occurred.
They provide no release/delete API and produce an execution-disabled,
tamper-evident record only. No trusted key, receipt, reservation root, or
production reservation is bundled. Filesystem locality and resistance to a
same-UID attacker are not established; the primitive cannot create an
environment receipt, authorize a run, collect results, or authorize fitting.

The run-start symbols re-verify the raw review and authorization plus the
durable nonce record, require exact downstream artifact identities, inspect the
live CPU-only deterministic process, verify a short-lived operator-signed
network-isolation attestation, and atomically persist a canonical mode-0600
environment receipt in a private caller-provisioned artifact root. Only path
hashes and a fixed logical runner argv are recorded, not secret-bearing command
arguments. The library does not create a network namespace or provision the
required root-owned source/dependency runtime. The stdlib-only bootstrap now
rejects a mutable Engine v2 source tree before package import. It independently
rehashes the signed raw Git commit and recursive tree objects with Git SHA-1
object framing and compares the exact tracked `betelgeuze_engine_v2` path set
and each file's mode, blob OID, SHA-256, and size with the live root-owned
read-only tree. The canonical source manifest is carried as the sixth bootstrap
state element. Run-start persists canonical mode-0600 per-file source and
dependency manifests as `<nonce>.source-tree.json` and
`<nonce>.dependencies.json` with `O_EXCL`, `O_NOFOLLOW`, and file/directory
fsync. Their signed commit and six aggregate dependency digests are rechecked
against exact persisted/live bytes by runner and writer finalization, and the
source-manifest digest is bound through environment, runner-start, observation,
and result identities. Workers retain exact pre/payload/post lifecycle evidence,
and the supervisor binds both endpoint snapshots to the child PID. This is
endpoint evidence only: kernel vDSO content, an authorized native allowlist,
and load/execute/unload lifetime closure are not established.
No trusted key, attestation, root, or production receipt is bundled, and a
verified receipt authorizes neither a production run nor validation, fitting,
or a scientific claim.

The minimization bounded-runner symbols re-read and live-reverify that receipt,
bind the stdlib-only bootstrap, dependency-identity helper, and runner sources,
require the signed clean Git
checkout and exact signed aggregate identities for six selected dependency
artifacts, validate the frozen materialization
manifest before consuming a nonce-bound mode-0600 start marker, and retain all
fourteen ordered pass and fail-closed case observations in memory. The runner
records predefined metric values, independent-oracle comparisons, exact
checkpoint/restart equality, and complete ordered operational/independent
coordinate traces under a 120-second budget. Each trace binds every canonical
binary64 raw/evaluated coordinate row, source/case/evaluation identity,
raw/evaluated coordinate-payload and per-step digests, a whole-trace digest,
exact counts, and the accepted-energy ledger; expected pre-evaluation failures
use a canonical explicit empty trace. It writes no validation result receipt
itself. The separate result-writer symbols re-verify the signed chain,
persisted/live environment, durable runner-start marker, and canonical
observation before private atomic persistence. The receipt is unsigned and
pending independent result review. The exact process entrypoint wires the
stdlib-only bootstrap to the environment receipt, bounded runner, and result
writer. It accepts no caller trust keys, reloads reviewer/operator anchors only
from the fixed external root-owned mode-0600 trust store, revalidates the fixed
supervised worker subprocess source/dependency/deterministic runtime before evaluation, and returns
only artifact hashes plus closed claim flags. The production entrypoint rejects
a caller-owned mutable checkout and requires an externally provisioned
root-owned read-only package snapshot. The signed aggregate dependency digests
bind a durable canonical per-file manifest that runner and writer compare with
persisted and live bytes. The corresponding source-manifest digest is carried
through the environment, runner-start, observation, and result receipts. The
repository does not provision that external snapshot or dependency runtime;
kernel-backed source/Git-metadata immutability and custody, pre-bootstrap stdlib
closure, signed native-DSO allowlisting and lifetime closure, and kernel vDSO
identity remain production blockers. A PID/parent/start-tick/boot/namespace
measurement primitive exists, but worker binding, same-tick collision exclusion,
and externally authenticated launch custody remain absent. Exact
request/observation and successful canonical-transcript binding is implemented;
the common production evidence-class/permit/status/custody foundation exists,
but final stage-specific carrier propagation and a provisioned external chain are
still absent.
It fails closed when external
production trust, signed artifacts, private roots, or nonce reservation are
absent.

The minimization result-review symbols are a provisional, non-production
Ed25519 verification surface. They first apply the full result-writer receipt
validator, then bind the exact receipt and ordered fourteen-case evidence into
deterministic per-metric, result-evidence, fail-closed, coordinate-trace, and
coordinate-step dispositions. Result evidence includes exact materialized
runtime/oracle identities, operational and independent result hashes, allowed
status/error pairs, exact nonnegative integer counts bounded by each case's
frozen iteration/backtrack budgets, finite count-consistent accepted-energy
ledgers recomputed against retained energy metrics, and recomputed coordinate,
step-identity, and whole-trace digests. The builder and
verifier require the raw signed pre-execution review and authorization artifacts
and reverify their Ed25519 chains before deriving the three upstream role
identities. The signed outcome is explicitly `accepted` or `rejected`; signature
verification proves review artifact integrity and reviewer-key identity, not
result acceptance. Trust keys are caller-provided, all four governance roles
must be pairwise distinct, text/byte transport must be canonical JSON, and every
current external revocation/supersession input—including result-review
supersession—is required. No key, attestation, production receipt, reviewer
approval, or scientific claim is bundled.
The validated receipt and the Ed25519 result-review signature also bind the
canonical source-manifest digest; this is integrity binding, not reviewer
approval or scientific acceptance.

The energy-force result-review symbols provide a separate provisional Ed25519
leaf over the exact 27-case, 59-variant, 19-metric result receipt. They derive
deterministic case, variant, metric, expected-failure, and worker-execution
dispositions; independently recompute all 56 required metric occurrences from
retained raw energy/force arrays and require bitwise equality with retained
float values; validate successful input/component/total/force evidence; and
require pairwise separation of the implementation author, scientific reviewer,
authorization operator, and result reviewer. A verified signature proves only
the leaf review artifact and caller-provided result-reviewer key. Its upstream
scientific-review and authorization artifacts are also Ed25519 records verified
with exact caller- or trust-store-provided public keys; private or symmetric
verification material is rejected throughout the active chain. The leaf still
does not independently reverify the live dependency manifest or establish
external custody. No
production receipt, review attestation, trusted key, independent human approval,
or scientific claim is bundled.

The bounded-runner symbols re-read and live-reverify the environment receipt,
require exact code, runner-source, six selected aggregate dependency-artifact,
and frozen-artifact identities, and require a source-only stdlib outer bootstrap
launched by the root-owned Python executable with `-I -S -B
-X pycache_prefix=/dev/null` before any validation dependency import, reject Git
replacement refs, and atomically consume one nonce-bound mode-0600 runner-start
marker. The outer stage validates its exact executable, flags, argv, cwd, and
source without reading stdin, constructs an allowlisted environment from the
request, and re-execs the same interpreter as a fixed source-bound `-S -B -X
pycache_prefix=/dev/null` controlled inner loader. The inner stage verifies the
complete process identity before reading bounded canonical stdin, so the
canonical uint32 `PYTHONHASHSEED` is applied during interpreter initialization
instead of merely being recorded after startup. Both stages ignore `PYTHONPATH`
and user-site overrides, skip `sitecustomize`/`.pth` execution, admit only
root-owned read-only dependency roots, and bind the bootstrap,
dependency-identity helper, and runner sources into the signed runner-source
identity. Before importing the package
initializer the inner stage verifies the authorization operator Ed25519
signature against a public key in the external root-owned trust store, requires reservation and artifact roots
outside the checkout, and uses root-owned Git to prove the exact signed commit,
execution-source identity, and clean worktree. Before package import, it
independently verifies the signed raw commit/tree object bytes using Git SHA-1
framing and compares a canonical mode/blob-OID/SHA-256/size manifest for every
tracked Engine v2 package file with the live root-owned read-only source tree.
That canonical manifest is retained in the six-element bootstrap state. Frozen
manifest construction and
the exact 27-case/59-variant CPU float64 evaluation run in fixed supervised child
processes with automatic site initialization disabled. Worker argv, cwd,
flags, complete environment, uint32 hash seed, application seed, and a
parent/child hash probe are derived only from the verified receipt and checked
before evaluation; mutable live supervisor environment is not copied. Only the
verified runtime's dependency roots are supplied. The bootstrap requires a
non-root process and root-owned/read-only package snapshot, but the repository
does not provision an external production snapshot/dependency runtime or
kernel-backed source/Git-metadata immutability and custody. Run-start persists
the canonical source manifest as `<nonce>.source-tree.json`; runner and writer
require exact persisted/live equality and match its digest across environment,
start, observation, and result identities. The six signed aggregate dependency
digests likewise commit to a durable per-file dependency sidecar. Source and
dependency traversal use bounded `scandir`, direct streaming of wheel `RECORD`,
pre-read file caps, aggregate budgets, and carried monotonic deadlines. Each
worker emits canonical request-bound pre/payload/completion frames, native
endpoint snapshots, and payload aggregates. The parent accepts them only when
both snapshot PIDs equal the launched child PID and reads stdout with a hard
byte bound before buffering. It durably retains the exact canonical worker
request plus transcript digest/length/frame order, requires complete raw stdout
to equal reconstruction from the request, retained rows, and lifecycle, and
discards every partial child payload on incomplete execution. Writer validation
and minimization result review independently reconstruct and re-hash successful
transcripts. Pre-bootstrap stdlib closure, signed native-DSO allowlisting/lifetime
closure, kernel vDSO identity, PID start-time/boot-ID, and externally authenticated
worker launch custody remain production blockers. The energy-force lane has a
role-separated Ed25519 post-result-review leaf contract, but no actual production
receipt, attestation, trusted result-reviewer key, or independent result review;
its upstream review/authorization chain is implemented as public-key-only
Ed25519 but no production keys or signed artifacts are provisioned. Remaining cooperative budget is rechecked
before the start marker is consumed, and a parent hard deadline can terminate
blocked native code. The result
is a canonical in-memory observation that retains
successes, expected failures, unexpected failures, missing metrics, and failed
thresholds. The exact process entrypoint is the absolute checked-out
`reference_validation_bootstrap.py` path under those frozen Python flags; it
accepts one deadline-polled canonical stdin request, loads trust anchors only from the
fixed external root-owned store, and never sends trust material to either
worker. It exposes no marker release/delete
API. Test-only artifacts can exercise this implementation; no production key,
receipt, start, result, validation
acceptance, fitting, or claim promotion is bundled.

`validation_process_launch_identity` is a provisional Linux-only measurement
primitive for the fixed `/proc` view. It binds PID, nonnegative parent PID,
stat-field-22 start clock tick, boot ID/hash, and PID-namespace inode using bounded
no-follow reads and repeated observations. It does not authenticate the procfs
superblock or host, cannot exclude reuse of one PID within the same clock tick,
does not establish durable process uniqueness, and is not yet bound to either
worker carrier.

`validation_production_evidence_custody` is the frozen claim-closed Ed25519 base
foundation shared by both synthetic lanes. It freezes the exact
`synthetic_validation_production` class, a pre-execution permit, an adjacent and
append-only status-snapshot chain, and a deliberately narrow two-event custody
sequence: sequence 1 carries the exact canonical signed permit and sequence 2
carries its exact canonical signed status snapshot. This base-v1 projection and
its frozen SHA-256 remain unchanged. Signed carriers are capped at
4 MiB; raw custody evidence, argv, contract bundles, and status rows have separate
fixed bounds. The verifier rejects class downgrade, stale/revoked/superseded or
caller-reported consumed permit inputs, trust-key aliases, rewritten status history,
stale or retroactive handoff status, and raw-byte/run/lane/host transplant within
that two-event sequence. Permit verification is an inspection against bounded
external status inputs; it does not atomically consume a permit and therefore does
not enforce one-use. This foundation does not provision keys, permits, an external
log or one-use registry, enrolled hosts, immutable storage, an actual custody chain,
or stage-specific production artifacts. Without an external append-only
successor registry it also cannot make two sibling sequence-2 events mutually
exclusive; each valid fork remains independently verifiable.

`validation_production_review_authorization_custody_extension` is an additive
companion that internally re-verifies the exact raw base sequence and adds
production-only Ed25519 wrappers for sequence 3 `pre_execution_review` and
sequence 4 `authorization`. It binds the lane-specific upstream review and
authorization artifacts, the supplied process-launch-identity digest, exact
permit/status ancestry, causal time ordering, global role/key/material separation,
and logical plus raw revocation/supersession state. Both lanes' upstream
review/authorization chains use public-key-only Ed25519 verification. The
supplied process identity digest is not external process authenticity, and neither carriers, events, keys nor an
append-only successor registry are provisioned. Consequently these contracts
neither authorize execution nor record
production results and every scientific, fitting, benchmark, product, and claim
flag remains false.

`validation_production_reservation_custody_extension` is the additive sequence-5
companion. It re-verifies the complete exact raw sequence-1-through-4 prefix and
the lane-local canonical reservation record, then binds a short-lived
sequence-4-custodian-signed intent to realm-global permit, authorization-nonce,
and predecessor slots plus exact registry/witness identities, keys, epoch, and
prior checkpoint. A second artifact verifies registry and independent witness
Ed25519 signatures over a claimed commit, continuing custody identity, and a
strictly newer post-commit status descendant. These signatures verify an
attestation only: they do not independently prove serializable compare-and-set,
one-use slot consumption, append-only non-equivocation, epoch continuity, or a
unique custody successor. Same-prior-head sibling attestations therefore remain
possible and all corresponding actual-fact fields stay false. No registry,
keys, intent, commit proof, production chain, execution, or result is bundled.

`validation_production_reservation_registry_proof` adds a verifier-only external
same-epoch transaction-proof boundary. It freshly re-verifies sequence 5 and
uses one identical sibling path per step to verify a fixed-order chain of exactly
three adjacent sparse-Merkle leaf updates for the permit, authorization nonce,
and predecessor slots. It binds backend binary/schema/configuration/deployment
identity, requires distinct backend and head-observer Ed25519 signatures, applies
the supplied freshly reverified sequence-5 status-lineage tail denials, and
requires the backend-native checkpoint to equal a caller-supplied expected
sequence/checkpoint. A supplied proof verifies only that the backend attested a
serializable committed outcome, that the exact three transaction-tagged leaf
transitions are internally consistent, that the observer signed the native
checkpoint, and that it matches the caller expectation. The verifier does not
authenticate that expectation's provenance or prove that the supplied status
tail is the global latest head. Separate sibling expectations can therefore
validate different siblings. This does not prove actual external CAS, global
one-use consumption, status-head CAS, realm-wide non-equivocation, epoch
continuity, later-head consistency, or a unique custody successor. Those
actual-fact fields, execution, and every scientific/product claim remain false;
the package bundles no proof, keys, backend, or authenticated head receipt.

`validation_production_reservation_authenticated_head_receipt` adds a second
verifier-only boundary for an externally signed, challenge-bound exact registry
head/status receipt. It snapshots both nested reverification inputs before use,
freshly reproduces the same raw registry proof twice, binds the proof and
sequence-5 logical/raw identities, realm/epoch/sequence/native checkpoint/state
root, the receipt-time status tail, service identities, causal times, and caller
challenge, and requires a separately reverified strict status descendant issued
after the receipt. Revocation and supersession from that post-receipt tail apply
to the exact signed receipt, authority key/material, proof, checkpoints, and
service identities. This proves only the bounded authority signature, exact
binding, and caller-supplied challenge equality. It does not establish challenge
freshness/one-use, a globally latest head, CAS, global slot consumption,
non-equivocation, later-head consistency, epoch continuity, or successor
uniqueness. No receipt, authority key, caller challenge, or post-receipt status
descendant is provisioned, so all actual and promotion fields remain false.

`validation_production_reservation_later_head_consistency` adds a verifier-only
same-epoch path from that freshly reverified receipt to one caller-pinned later
registry head. Every adjacent checkpoint/state-root transition is signed by the
existing external backend trust domain, the existing head observer signs the
complete ordered path, and sparse-Merkle inclusion proofs require the original
permit, authorization-nonce, and predecessor-successor consumed leaves to remain
in the later state root. A strict status descendant issued after the proof
applies revocation and supersession to the proof, transitions, keys, checkpoints,
roots, and service identities. This proves consistency of the supplied fork
only: independently pinned siblings can each verify, so global latest,
realm-wide non-equivocation, epoch continuity, CAS, execution, and every
scientific/product claim remain false. No proof, keys, or post-proof status is
provisioned. `later_head_observed_at_utc` is the observer countersign-completion
time. The DTO explicitly preserves
`caller_challenge_freshness_verified=false` and
`caller_challenge_one_use_verified=false`. Also,
`original_consumed_slots_retained_verified=true` means only that the three
transaction-tagged consumed-leaf encodings attested by the anchor proof are
included in the selected later root; it does not independently establish actual
global slot consumption or one-use enforcement.

`validation_production_reservation_witness_quorum_non_equivocation` adds a
verifier-only N/F/Q witness certificate for one fixed policy, registry realm,
epoch, and exact authenticated anchor. The caller-pinned policy binds the
ordered full roster with distinct declared witness/operator/fault-domain
identifiers, public keys, service identities, validity windows, and the `2Q-N>F`
intersection rule. Every vote signs one stable anchor fork scope and one exact
descendant-lineage statement. All N roster members—not only the Q signers—must
remain valid for the policy window and survive the post-certificate status
denial fence. A successful result is only the conditional,
anchor-scoped certificate fact. The verifier does not observe the declared
fault bound, enforce exclusive voting, compare independent witness journals, or
exclude a hidden sibling certificate; realm-wide non-equivocation, global
latest, epoch continuity, execution, and promotion therefore remain false.
No policy, witness key, certificate, journal, or post-certificate status is
provisioned.

`validation_production_reservation_epoch_transition_continuity` adds a
verifier-only boundary for one caller-pinned adjacent registry-epoch
transition. It freshly re-verifies the previous same-epoch witness-quorum
proof, requires integer ordinals with `next = previous + 1`, carries the
previous terminal state root unchanged into sequence-zero genesis, derives the
genesis checkpoint from the full transition context, and verifies disjoint
previous/next fixed-roster Ed25519 quorums over the same exact statement. A
successful DTO proves continuity only for that supplied transition. It does not
enforce exclusive witness locking, compare independent journals, rule out a
separately quorum-signed sibling successor, prove global latest or realm-wide
non-equivocation, or commit external CAS. No transition proof, next policy,
keys, votes, or post-transition status descendant is provisioned.

`reference_minimization_validation_trajectory_comparison` freezes exact
evaluation-index/iteration/trial/outcome alignment, coordinate and energy
max/RMS thresholds, branch/rejection/count dispositions, expected-failure
non-comparability, and uninterrupted/paused/resumed digest equality for three
checkpoint cases. The runner, writer, and result-review verifier recompute the
canonical comparison and fail closed on omission, reorder, cross-wire,
non-finite values, or digest tamper. Its production, S0, scientific, and S1
flags remain false.

Runtime-integrity companion v14 binds the complete energy-force Ed25519 chain
and the exact frozen SHA-256 of the refrozen minimization trajectory-comparison contract, custody-v1,
the review/authorization extension, the sequence-5 reservation companion, the
external registry-proof verifier, the authenticated head/status receipt
verifier, the same-epoch later-head consistency verifier, the fixed-policy
anchor-scoped witness-quorum verifier, the adjacent epoch-transition continuity
verifier, and the process-launch-identity contract. Runtime v8 through v13 are retained only in
the read-only legacy-contract registry.

The receipt-contract symbols freeze the CPU-only execution-environment receipt
shape and the failure-inclusive result-receipt shape for the exact 27 cases, 59
materialized variants, and 19 predefined metrics. They bind the protocol,
artifact, authorization, environment, code, runner, dependency, lifecycle, and
review identities required by a future durable result. The package provides no
production receipt, trusted key, or durable production observed energy, force,
error, or metric values. `require_reference_validation_execution_ready()`
therefore always fails closed.

The result-writer symbols accept only a verified bounded-run observation and
re-verify the raw signed review and authorization, persisted/live environment,
durable runner-start marker, exact persisted/live source and dependency
manifests, and exact code/source/dependency identities. They
atomically persist one canonical mode-0600 nonce-bound receipt while retaining
every failed case, variant, and metric. Reading verifies canonical JSON and the
embedded digest; acceptance additionally requires an out-of-band expected
receipt SHA-256 and current external revocation/supersession inputs. The receipt
is unsigned, private POSIX storage is not external authenticity, same-UID
replacement resistance is not established, and result review remains
`pending_independent_review`. No production receipt or scientific promotion is
bundled.

The active energy-force base carrier chain uses v3 identities through run start,
a v5 runner/result writer, and a v2 result-review identity. The active minimization base chain uses v4 review and
execution-environment identities, v5 authorization, result-receipt,
nonce-reservation, and run-start identities, a v8 runner, and v7 result
writer/result review. Current hashes are frozen over the
complete upstream contract DAG. The production review/authorization and
reservation custody extensions are v4 and runtime-integrity is v14. The read-only legacy-contract verifier
recognizes 76 superseded contract documents by canonical projection hash and
fixed identity metadata. It does not verify or claim compatibility with
superseded signed attestations, receipts, run records, or observations.

Their schema IDs and serialized receipts are versioned, but Python convenience
signatures may change before the distribution reaches `1.0.0`. Callers should
pin the distribution version and validate schema IDs.

### Internal APIs

Names beginning with `_`, implementation files not re-exported from a package
`__init__`, and test helpers are internal. They carry no compatibility promise.

## Scientific semantics

API stability never upgrades scientific status. A stable API may still return
an uncalibrated internal scalar or a claim-blocked result. Consumers must inspect
quantity descriptors, capability rows, blockers, and provenance rather than
inferring scientific validity from import stability.

## Deprecation policy

Before `1.0.0`, a provisional submodule change should include:

- a changelog entry;
- a schema/version decision;
- a migration note when serialized data changes;
- focused compatibility tests.

Stable root API removal requires a major Engine API version change. A deprecated
alias should remain for at least one minor release when practical and must not
silently change scientific meaning.
