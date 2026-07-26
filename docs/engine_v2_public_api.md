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
betelgeuze_engine_v2.docking.parameterized_validity
betelgeuze_engine_v2.docking.reference_applicability
betelgeuze_engine_v2.docking.steric_field
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
betelgeuze_engine_v2.offline.openmm_reference_native_minimization
betelgeuze_engine_v2.offline.openmm_reference_fixed_born_disposition
betelgeuze_engine_v2.offline.openmm_reference_result_review
betelgeuze_engine_v2.offline.s0_production_evidence_bundle
betelgeuze_engine_v2.runtime
```

The `betelgeuze_engine_v2.offline` modules are optional external-evidence
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
The separate installed
`betelgeuze-engine-v2-openmm-native-minimization` command consumes an exact
caller-pinned materialization, runs the OpenMM L-BFGS endpoint for the eight
supported cases, retains six N/A fail-closed rows, and recomputes Engine v2
energy and force at every endpoint coordinate. It applies only the previously
frozen same-coordinate mapping, per-case tangent-force, constraint-residual,
and energy-nonincrease checks; cross-algorithm coordinate and energy deltas are
recorded but ungated. Current `1.3.0` configuration SHA-256 is
`9189afe3a01a7eb8ee2c26e8b233db6c2250a14317f8498e34303c1c2b4fdf51`.
The 2026-07-24 local receipt under superseded `1.0.0` configuration
`6465f726c408e6df2dd15d318a4cdfc57a8b2edd271ddaa578edcc336110017e`,
`7e5b3454afc41f9954f71dfc3b0b274906323f15fd8ea6630bfcc1e95ce95b7c`
passed all eight same-coordinate mappings and energy-nonincrease checks but
failed the two fixed-Born constrained endpoint-health rows after final
constraint projection, so its status is rejected. Exact verification and
reexecution preserve that rejection; endpoint/trajectory equivalence and every
production or promotion flag remain false.
The installed
`betelgeuze-engine-v2-openmm-fixed-born-disposition` command requires that
exact materialization and native receipt plus caller-pinned hashes. Its current
v5 configuration is
`6182cecaa21d5d191baacda1bc9cf7ae7d3cb9eb8b2ca0217757cb23af37c281`;
the historical receipt binds v2 configuration
`ac601f3cfedd68e24b6507778ea36c1676fb24cacf89c7c2fa73848bf3c68045`
retains the rejected reporter-observer v1 identity
`67f1a6025155d8f62cd3d1aa7da2803e229a4dce7871050db6c323f531f0b8c1`,
keeps the same eight probes and original health thresholds, and adds a
no-reporter exact control. Receipt
`870f1ea247da4b0232f22804298e75d554af511da18924a7ba49c1c703f003f2`
records all 16 reporter traces and exact cross-alias physics equality. It
classifies a final constraint-projection tradeoff because the pre-projection
endpoint passes tangent force but misses the constraint residual, while the
post-projection endpoint passes the constraint residual but misses tangent
force. Diagnostic acceptance means only that this failure disposition is
complete; `frozen_native_endpoint_health_failure_resolved`, causal-root-cause,
S0/S1, validation, and product flags remain false.
The separate `reference_constraint_stationarity` API exposes
`ReferenceConstraintStationarityConfig`,
`minimize_reference_constraint_stationarity`, canonical checkpoint parsing,
and a result with complete energy/coordinate/acceptance/failure traces. Its
default contract uses strict `1e-14 Å` projection, retains the public
`1e-10 Å` constraint and `1e-8 kcal/mol/Å` tangent-force bounds, and permits
stationarity polish only under strict tangent decrease plus a
`1e-10 kcal/mol` best-energy band. Default configuration SHA-256 is
`5642654a25a2d024f7cb8c1de024815f6bf6032b06f6c57509d7b784b708f708`.
The offline `openmm_reference_constraint_stationarity` API and installed
`betelgeuze-engine-v2-openmm-constraint-stationarity` command build or verify a
mode-0600 no-overwrite same-coordinate receipt. Current comparison
configuration SHA-256 is
`69f5168dbf7bcaa9f4ff85f9e2e9f7800b8b21685110000a90c909d552eab6db`;
the retained local receipt binds superseded configuration
`722d319c865eb15dd12296dee998b26332e2c1ad8edf3e5e6611914b960529d1`.
These APIs cover only four constrained aliases, invoke no OpenMM minimizer,
leave ten frozen rows outside their denominator, and cannot report validation
or S0 completion.
The offline `reference_minimization_stationarity_successor` API and installed
`betelgeuze-engine-v2-minimization-stationarity-successor` command execute or
verify a separate all-14-case candidate observation. It preserves the frozen
v1 and fail-closed paths, uses the constraint-stationarity candidate plus a
standard-library tuple oracle for the four constrained aliases, records full
energy/coordinate/failure traces and exact operational/oracle restart evidence,
and binds the same-coordinate OpenMM candidate receipt. Current `1.3.0`
configuration SHA-256 is
`edae2c0ff83761426185e5eb269b1e30ea5dd5446c93121eef94163af284c237`;
the retained local observation binds superseded configuration
`5c39aa346531d8f3cff378361367f7ff236f2c94c0c4bb3db66a28ec8e27d4f5`.
Its mode-0600 no-overwrite output remains a single-host candidate observation,
not a production validation receipt or S0 admission.
The v7 Ed25519 result-review contract freshly reverifies both Engine
result-review chains, the exact OpenMM materialization, both complete
component/trace receipts, and the failure-inclusive native endpoint receipt.
It crosschecks the exact 27/59 Engine outputs and all fourteen operational
traces, binds a host-comparable native physics projection, and derives accepted
or rejected outcome from the predefined endpoint-health metrics. A rejection
also requires the exact fixed-Born disposition receipt and binds its
configuration, physics projection, completeness, and classification; an
accepted endpoint forbids that failure-specific input. The observed 6/8
receipt yields a signed rejection retaining both fixed-Born case IDs despite
its completed disposition. Contract SHA-256 is
`f7b57f08afd44e0ab7848c8ce75b08560d00cf381895aaeaf251e23cd3b81c7a`.
No key, attestation, production receipt, or populated two-host evidence bundle
is included.
The final v6 S0 bundle module freshly invokes that verifier for exactly two raw
host evidence sets. It first rejects a host unless the result review and native
endpoint health are accepted with 8/8 cases and no failed IDs. It rejects reused host/CPU/session/custody, artifact,
environment, authorization-nonce, and review-nonce identities while requiring
exact equality of commit, source, dependency, OpenMM runtime/source, seed, and
all three physics projections. Accepted hosts must report the failure-specific
disposition path as not applicable. Contract SHA-256 is
`5eb28543fa9b11ac3559c20c72955c6c9c9adec757869975c71ef0207beee3a4`.
Its final Ed25519 approval is canonical, time-bounded,
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
validity, fitted ranking weights, uncertainty, or a customer route.
`admit_reference_docking_scorer` evaluates that boundary without discarding
later failures at the first exception. Its
`ReferenceDockingApplicabilityAssessment` exact-binds the problem, config,
canonical system/topology, and optional parameter fingerprints; inventories
unsupported and metal atoms, nonpolymer receptor residues, formal/partial-
charge failures, missing/extra/mismatched parameters, model/dtype/cell/capacity
failures, aromaticity, and declared stereo; and emits one of
`admitted_diagnostic`, `invalid_input`, `abstain_chemistry_scope`,
`abstain_parameter_scope`, or `abstain_execution_scope`. The admission helper
returns the assessment plus a scorer only for the first disposition.
`assess_reference_docking_applicability` returns the same assessment without
exposing the scorer. Aromatic or declared-stereo inputs can remain executable
diagnostics but set `interaction_coverage_complete=false` and
`ood_detected=true`; they are not validated refinement inputs. Every assessment
keeps `scientifically_validated=false`, `validated_refinement_allowed=false`,
and `claim_safe=false`.
`UncalibratedReferenceDockingScorer.score_with_diagnostics` returns the same
four-term breakdown together with an exact proposal/problem/parameter-bound
interaction receipt. It evaluates pair-specific LJ-minimum contact ratios and
worst overlaps over every receptor--ligand pair and every ligand pair not
listed in the bound force field's `excluded_pairs`; it separately reports
like/opposite/neutral partial-charge pair counts and attractive versus
repulsive screened-Coulomb sums.
`evaluate_chemistry_aware_pose_validity` consumes that atomic result and
requires a `ChemistryAwarePoseValidityConfig` containing explicit maximum
signed strain delta and aggregate repulsive-Coulomb thresholds. No default
scientific thresholds are fabricated. An admitted nonaromatic, stereo-
unspecified pose can be valid only within that caller-declared diagnostic
scope; aromatic or declared-stereo inputs remain incomplete, unsupported
metals and receptor cofactors fail before evaluation, all thresholds remain
uncalibrated, and every result keeps `scientifically_validated=false` and
`claim_safe=false`.

`UncalibratedPdbqtUffDiagnosticScorer` is a separate test-diagnostic scorer; it
does not substitute for `UncalibratedReferenceDockingScorer`. It consumes
explicit PDBQT-derived element, charge, coordinate, and UFF nonbonded parameter
arrays plus a caller-bound ligand strain evaluator. Its fixed four-term
breakdown is UFF receptor–ligand van der Waals, PDBQT-charge Coulomb, ligand
source-atom strain delta, and UFF overlap penalty. The scorer binds coordinate,
parameter, configuration, and strain-reference identities and exposes
pair/contact diagnostics. Its UFF atom typing, PDBQT charges, implicit/merged
hydrogen omission, and macrocycle-closure pseudoatom policy are unvalidated;
metal/cofactor/covalent, directional hydrogen-bond, aromatic/stereo,
desolvation, receptor-flexibility, and uncertainty science are outside scope.

The fit-only ranking-calibration symbols separately require an exact term schema
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

`betelgeuze_engine_v2.molecular.rdkit_openff_preparation` provides the
installable ligand-preparation boundary. The
`betelgeuze-engine-v2-prepare-ligand` command accepts exactly one SMILES token
or one SDF V2000 record. It no-follow reads bounded file input, rejects
multiple fragments, radicals, isotopes, unsupported elements and unsupported
formal-charge ranges, and requires defined tetrahedral and double-bond
stereochemistry unless the caller explicitly requests a diagnostic-only
undefined-stereo artifact. RDKit supplies sanitization, aromaticity/ring
perception, bounded protomer and tautomer diagnostics, explicit hydrogens, and
either preserved input coordinates or a fixed-seed, single-thread ETKDGv3
conformer followed by bounded UFF optimization.

The optional `chemistry` package extra pins RDKit 2025.9.6. The adapter also
recognizes the frozen RDKit 2022.09.5/`rdkit-pypi` identity used by existing
evidence. OpenFF Toolkit is not a mandatory runtime dependency: when present,
its RDKit wrapper must round-trip the same explicit-hydrogen atom count, bond
count, and canonical molecular graph; when absent or failed, the exact status
is retained and `--require-openff` fails closed. This is molecule admission,
not OFFXML parameter assignment.

The output is an ordinary strict Engine v2 canonical system JSON and can be
passed directly as `--ligand-canonical-json` to the redocking command. Its
metadata contains a self-verifying preparation receipt that binds source
digest, configuration, RDKit/OpenFF identities, selected state, complete
bounded state rows, stereo/aromatic/ring counts, coordinate method, claim
flags, and blockers. The file is mode 0600 and never replaces an existing
path. Calibrated pKa selection, partial charges, force-field parameters,
chemical applicability evidence, and scientific/product promotion remain
absent.

`betelgeuze_engine_v2.benchmark.redocking_cli` provides the installable
prepared-input vertical boundary. The
`betelgeuze-engine-v2-redock-diagnostic` command takes strict canonical receptor
and ligand system JSON plus an explicit pocket center/radius, bounded candidate
count, Top-K, global torsion budget, translation radius, diversity threshold,
local-refinement-step budget, seed, and output path.
It no-follow reads and hashes both inputs, requires one nonperiodic Angstrom
model, binds pocket and search-space derivation receipts into a concrete
`DockingProblemInput`, and records numeric/RNG/search identity. Output is
canonical mode-0600 JSON, never replaces an existing path, retains all
candidate failure rows, and includes exact hexadecimal receptor-frame
coordinates for selected poses. An invalid input or execution produces a
sanitized failure receipt when the requested output is still available.

This CLI starts after chemistry preparation. A verified RDKit/OpenFF ligand
receipt and positive torsion budget materialize the bridge-only molecular
torsion tree and bind it through `bind_molecular_torsion_search_space` to the
transformed ligand. Candidate zero is the exact zero-torsion/identity/zero-
translation baseline. Later candidates sample every admitted torsion uniformly
on `[-pi, pi)`, use a Shoemake three-uniform unit quaternion for Haar-uniform
SO(3), and choose translation from a deterministic receptor-steric-field grid.
The bounded plan binds the exact authenticated problem/search space, receptor
shell, ligand atom radii, pocket, fixed unvalidated radius profile, lattice,
site ordering, and capacity limits. It first ranks sites by anchor overlap, then
for each oriented/torsioned ligand orders retained sites by deep-overlap count,
overlap count and squared penetration, pocket-boundary damage, and canonical
site index. Candidate zero forcibly retains the zero-translation site; later
candidates cycle over the best nonzero sites for placement diversity. Numeric
policy v3 distinguishes this deterministic field path from the receptor-free
uniform-volume ball and freezes the corresponding RNG draw order. Every success
or failure row embeds torsion angles, rotation matrix, translation, RNG states,
the selected site and steric metrics, complete placement receipt/plan digest,
and source proposal fingerprint. Generic input keeps the uniform-volume
translation fallback. `--max-torsions 0` uses the authenticated rigid search
space but still uses the steric field when ligand preparation verifies.

The verified preparation receipt also enables `interpretable-pose-scorer-v0`, which emits four fixed-radius
geometry terms, reference-relative bond/angle/rotatable-dihedral displacement,
an explicit-H directional D-H-A reward, and a neutral-element hydrophobic
contact reward. Feature rules, weights, and radii are deterministic heuristics;
they do not use partial charges, solvation, lone-pair direction, pi/halogen or
metal interactions, and they are not fitted or independently validated. The
For a verified prepared ligand, the command then runs
`interpretable-local-pose-coordinate-descent-v0` for up to six
steps by default. Each step enumerates signed Cartesian translation and
rotation moves plus signed rotations about every bridge-only rotatable bond,
uses score then canonical move order as the deterministic tie break, accepts a
strict score decrease, and reduces all move sizes after a rejection. Search
rows retain the complete refinement receipt even if later scoring or validity
fails: parent/problem/scorer/refiner/torsion-plan fingerprints, all iteration
outcomes, evaluated/rejected move counts, nine-term deltas, score trace,
coordinate-hash trace, and maximum bond/angle residuals. A generic canonical
ligand remains on the original five-term element-geometry diagnostic with an
effective zero-step budget and explicit missing-preparation/scorer/refiner
blockers. The verifier rejects cross-wired scorer, term, torsion-plan, or
refinement receipts. The CLI also rejects a prepared run before search when
candidate count × effective step budget × per-step move count exceeds 250,000
objective evaluations.

The same verified-preparation gate enables chemistry-aware validity v2. Its
context cross-binds the original preparation receipt, transformed ligand
topology, receptor shell, pocket, and docking problem. Each successful row
records element-radius-scaled receptor penetration and ligand self-clash with
1-2/1-3 exclusions, reference-relative bond/angle deltas, and preservation of
declared tetrahedral and double-bond stereo geometry. Thresholds and radii are
hand-fixed and uncalibrated. The contract does not assign partial charges,
independently validate protonation/tautomers, recompute absolute CIP/E/Z labels,
or validate aromatic planarity. Generic canonical ligands remain on geometric
validity with an explicit missing-v2 blocker.

The redocking command itself does not accept arbitrary PDB/SDF, perceive
protonation/tautomers, construct chemistry, use ring/macrocycle closure or a
calibrated interaction-energy field, run force/gradient or force-field
minimization, provide validated chemical applicability, or establish
benchmark/calibration/OOD evidence. Its steric field is a fixed-radius overlap
heuristic without electrostatics, directional hydrogen bonding, desolvation,
water/cofactor response, or receptor flexibility. Its local refiner optimizes the
uncalibrated diagnostic score, not a physical energy; analytic forces and
tangent-force residuals are unavailable. Receipts therefore freeze all
scientific, benchmark, customer, and claim flags to false.

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

`betelgeuze_engine_v2.benchmark.public_pose_ranking_corpus_intake` provides the
installable three-way file boundary. The
`betelgeuze-engine-v2-public-ranking-corpus-intake` command exposes
`materialize` and `verify` modes and requires caller-pinned file and payload
SHA-256 values for six canonical inputs: PDBbind-v2020 fit, CASF-2016
validation, and PoseBusters-308 test manifests plus fit↔validation, fit↔test,
and validation↔test all-chain sequence-identity receipts. No symlink,
non-canonical JSON, duplicate key, unknown field, derived-field mismatch, or
overwrite is accepted; output mode is exactly 0600.

The frozen policy requires roles `fit`/`validation`/`test`, scopes
`calibration_fit`/`full_benchmark`/`full_benchmark`, complete official CASF 285
and PoseBusters 308 case sets, the same scoring and preparation identities,
disjoint case/PDB/target/receptor/ligand/scaffold/target-sequence identities,
maximum all-chain sequence identity no greater than 0.90 on every pairwise
split comparison, and both fit→test and validation→test temporal ordering.
Target-family overlap remains allowed so family-stratified metrics are
possible. Configuration SHA-256 is
`4972e41765076e09b7bbec43b7e506dede6ab48b01b173f62cd73a749f694681`.
`ready_for_partition_materialization` means only that provenance inputs passed;
every receipt still fixes all score/partition/label/fit/model/result/review and
claim flags to false. No production receipt exists until genuine licensed
manifests and executed sequence evidence are supplied.

`betelgeuze_engine_v2.benchmark.public_pose_ranking_calibration_partition_intake`
provides the next file boundary. The installed
`betelgeuze-engine-v2-public-ranking-calibration-partition-intake` command
exposes `materialize` and `verify` modes. It first exactly reconstructs a
mode-0600, passing three-way corpus receipt, then accepts only canonical
PDBbind-v2020 `split_role=fit` and CASF-2016
`split_role=validation` `PoseRankingCalibrationPartition` files. A test
partition is not an accepted argument.

Every partition row is strictly reconstructed and bound to the corresponding
public case manifest. The receipt recomputes the generic pose-level leakage
audit, requires identical term schemas, records every case/row,
success/failure, positive/negative, and pairwise-uninformative denominator, and
distinguishes an admitted failure-inclusive intake from direct-fit readiness.
Fit failure rows remain present and require a separately bound success-only
training view; they are never silently dropped. Validation labels are
evaluation-only and `validation_labels_used_for_fit=false`.

Configuration SHA-256 is
`c4b423063a36f38d7f6f098a38c7ea54b078c25f3cc04d060ae88638902ff8be`.
Outputs are canonical mode-0600/no-overwrite receipts. This API performs no
fit, validation-based selection, test access, benchmark, external rerun, or
claim promotion. Because no genuine passing PDBbind/CASF corpus receipt exists,
there is currently no production partition-intake receipt.

`betelgeuze_engine_v2.benchmark.public_pose_ranking_calibration_training_view`
provides the explicit fit bridge above that passing intake. The installed
`betelgeuze-engine-v2-public-ranking-calibration-training-view` command exposes
`materialize` and `verify` modes. Selection is status-only: every successful
fit row is copied unchanged into an embedded success-only
`PoseRankingCalibrationPartition`, while every failed row is omitted only from
executable fitting and retained as a hash-bound disposition. The receipt
accounts for every source row and case, requires positive/negative trainability,
and recomputes leakage between the training view and CASF validation.

The guarded Python fit bridge calls the existing deterministic calibration API
only after verifying all scorer, preparation, schema, partition, and leakage
bindings. Validation labels are not used for view construction or fitting, and
no test-partition argument exists. Configuration SHA-256 is
`e5e202d10420b5a557b1227aa0f7735433ebaeadc1656f6b981c14453aeb25b8`.
This API performs no validation-based selection, test evaluation, external
rerun, or claim promotion. Genuine upstream corpus inputs remain absent, so no
production training-view receipt, fit, selected model, metric, review, or claim
exists.

`betelgeuze_engine_v2.benchmark.public_pose_ranking_fit_validation_selection`
provides the next claim-closed file boundary. The installed
`betelgeuze-engine-v2-public-ranking-fit-validation` command exposes
`materialize` and `verify` modes. A canonical
`PublicPoseRankingFitValidationManifest` workflow-locally preregisters one to
32 unique, canonically ordered candidate IDs and exact
`PoseRankingCalibrationConfig` objects, one `PoseRankingEvaluationConfig`, and
the frozen selection policy.
Its policy SHA-256 is
`1905b14e37da44293483b9b31a06b2653849b2e986dc75b9e4ad53aa0bc4b9d9`.

Materialization first reexecutes the corpus, partition-intake, and training-view
ancestry. Every candidate then fits only the embedded PDBbind success rows.
The bound CASF partition is evaluated only after fitting; every report retains
all-case/all-pose denominators, failure rows, target-family metrics, and
case-bootstrap confidence intervals. Selection maximizes pose-level
average-precision PR-AUC, then Top-1 and Top-5 native-like rates, with canonical
candidate ID as the final tie break. If any preregistered fit/evaluation fails
or any primary PR-AUC is unavailable, every candidate row and disposition is
retained and `selection_complete=false`.

The receipt binds the training-view file/payload, validation partition and
leakage audit, candidate manifest, source files, Python/Torch binary runtime,
each model/report, selection summary, and its own digest. Writes are canonical,
mode 0600, and no-overwrite; verification reexecutes every fit and validation
and exact-compares the full receipt. An ancestry-argument tree containing a
PoseBusters test score partition is rejected, and the CLI has no such argument.
Two builds were byte-identical at wheel SHA-256
`d338d81d14d08ca7c07f74629ac2b98f94d389f651e44e2b143fb487bfcf4bd3`
(1,708,814 bytes), and the installed entry point/import was verified outside
the checkout. This boundary is fit/validation model selection only. Genuine
licensed PDBbind/CASF inputs are not present, so no production receipt exists;
the receipt does not establish independent timestamp/signature custody for the
candidate manifest. It does not execute the PoseBusters test, fit confidence
calibration, establish independent reproduction/review, validate supported
chemistry, or authorize a scientific or product docking claim.

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

`betelgeuze_engine_v2.benchmark.public_posebusters_internal_preparation`
provides the canonical internal-input gate. The installed
`betelgeuze-engine-v2-posebusters-internal-prepare` command exactly reexecutes
the archive intake and corpus audit before touching a case. Rows at the
provisional supported-element/formal-charge/cofactor boundary are attempted;
all other chemistry rows abstain, and every intake/audit/preparation failure is
retained. The receptor uses strict PDB parsing with `CRYST1` recorded but not
materialized as periodicity. The start conformer is passed through the
self-verifying RDKit/OpenFF diagnostic adapter. The native ligand contributes
only its heavy-atom centroid for the explicit spherical pocket. Successful rows
write canonical receptor and ligand system JSON in a mode-0700/0600,
no-overwrite tree, cross-bound to source, system, configuration, runtime, and
ligand-preparation receipt identities. Verification reexecutes every case and
requires exact receipt and artifact bytes.

`betelgeuze_engine_v2.benchmark.public_posebusters_internal_execution` adds the
failure-inclusive internal batch boundary. The installed
`betelgeuze-engine-v2-posebusters-internal-execute` command first re-verifies
the complete preparation receipt and tree, derives each case seed from the
frozen base-seed/case-ID policy, and calls the prepared redocking diagnostic
with one frozen bounded configuration. Completed cases retain candidate
success/failure, selection-eligible, valid-pose, and selected-pose counts plus
the full authenticated diagnostic report. Preparation failures, upstream
failures, chemistry abstentions, and execution failures remain distinct rows;
all summary rates use the complete case denominator and Wilson 95% intervals.
The execution receipt binds the preparation projection, both runtime
identities, relevant source files, configuration, and exact output tree, and
its verifier reexecutes preparation and docking byte-for-byte.

This is an execution/evidence carrier, not the final public redocking result.
It does not yet compute native symmetry-aware Top-1/Top-5 RMSD, run the pinned
PoseBusters validity oracle over internal poses, stratify by target family or
chemistry, measure wall-clock/peak-memory runtime, or prove second-host and
independent-review reproduction. Therefore `benchmark_executed=false`,
`scientifically_validated=false`, and `claim_safe=false` remain fixed.

`betelgeuze_engine_v2.benchmark.public_posebusters_internal_rmsd_evaluation`
provides the next diagnostic gate. The installed
`betelgeuze-engine-v2-posebusters-internal-rmsd` command exactly reexecutes the
internal batch and intake, maps each prepared heavy atom through its retained
source-start atom index, enumerates all bounded native-to-start heavy-
connectivity isomorphisms, and computes minimum direct receptor-frame RMSD for
every selected pose without alignment. Case rows retain the selected mapping,
mapping-set identity, input/report/system hashes, internal validity, Top-1 and
Top-K best RMSD, threshold hits, and every blocked/evaluation-failure
disposition. Summary rates use the complete cohort denominator and Wilson 95%
intervals.

This diagnostic deliberately uses connectivity symmetry only. It does not
fully interpret atom stereochemistry and is not equivalent to PoseBusters
robust RMSD or its external physical-validity tests. The separate carrier below
supplies the pinned external-oracle execution boundary; production cohort
results, a production target/chemistry companion receipt, runtime evidence,
second-host rerun, and independent review remain required before any public
benchmark claim.

`betelgeuze_engine_v2.benchmark.public_posebusters_internal_oracle_evaluation`
provides the pinned external-oracle carrier for those selected internal poses.
The installed `betelgeuze-engine-v2-posebusters-internal-oracle` command first
exactly reexecutes the internal direct-RMSD chain and archive intake. For every
evaluated row it reopens the exact raw start ligand, receptor, native ligands,
prepared canonical ligand, and authenticated redocking report; requires a
complete bijective source-start-to-prepared atom mapping; reconstructs each
RDKit conformer at binary64 input precision; and applies the pinned
PoseBusters 0.6.5 `redock` full-report runtime. Batch failure falls back to
bounded per-pose evaluation. Added or missing prepared atoms fail closed rather
than being silently omitted from the oracle topology. Every report value,
grouped physical-validity
flag, oracle RMSD, internal/oracle direct-RMSD delta, per-pose failure, adapter
failure, and blocked upstream row is retained. All-case, selected-case, and
selected-pose rates include Wilson 95% intervals, and verification requires
byte-exact upstream and oracle reexecution.

This boundary does not regenerate poses and does not make the internal scorer
or refiner scientifically valid. No official 308-case production result is
bundled. Target-family/chemistry strata and runtime measurements are separate
claim-closed companions; official-cohort execution, same-input
Vina/GNINA/Smina comparison, second-host independent rerun, public
result-bundle validation, and scientific review remain explicit blockers.
Accordingly `benchmark_executed=false`,
`scientifically_validated=false`, and `claim_safe=false` are fixed.

`betelgeuze_engine_v2.benchmark.public_posebusters_internal_oracle_runtime_observation`
adds a non-deterministic measurement companion without changing the oracle
payload. The installed
`betelgeuze-engine-v2-posebusters-internal-oracle-runtime` command requires an
out-of-band expected Engine v2 wheel hash and expected oracle hash, verifies
that the wheel contains the exact executing observer/oracle/runtime source
bytes, and performs one byte-exact oracle reexecution through a private case
observer. It records batch and per-case `perf_counter_ns` wall duration,
synchronous boundary RSS samples, and 5 ms background RSS samples from bounded
Linux `/proc/self/statm`. Batch measurements cover the complete exact
upstream+oracle chain; per-case measurements cover only the downstream
PoseBusters oracle loop and are not a full redocking-pipeline stage breakdown.
Every oracle status, including upstream failure and abstention, remains in the
original case projection. The receipt also binds the
Python executable, CPU/platform projection, distribution versions, page size,
and a fixed safe environment-variable allowlist.

The verifier reexecutes the deterministic oracle and validates the measurement
receipt's canonical identity, wheel, source, case, result, and environment
bindings; it does not pretend timing or memory values can be reproduced exactly.
The sampled peak may miss a sub-sampling-interval transient and is not a
kernel-enforced isolated-case maximum. Sampling overhead is included. The
receipt is unsigned and does not prove physical host identity, an independent
second-host observation, full-pipeline per-case runtime, statistical benchmark
completion, or scientific review. Consequently `benchmark_executed=false`,
`scientifically_validated=false`, and `claim_safe=false` remain fixed.

`betelgeuze_engine_v2.benchmark.public_posebusters_internal_oracle_stratification`
adds a deterministic all-case join over the oracle result, runtime observation,
corpus audit, canonical preparation tree, conservative observed-target
clusters, and frozen RCSB/Pfam target-family receipt. The installed
`betelgeuze-engine-v2-posebusters-internal-oracle-strata` command provides
`materialize` and `verify` modes and requires caller-pinned identities for the
oracle, runtime observation, target clusters, annotation snapshot, and each
external evaluation receipt used to reconstruct the cluster binding.

Every case receives exactly one primary target stratum and one primary
chemistry stratum. Exact Pfam sets take precedence; cases without Pfam or with
failed RCSB mapping retain their annotation/mapping disposition plus observed
sequence-cluster ID. Prepared-case charge, heavy-atom count, elements,
aromaticity, ring, and stereo are projected from a canonical prepared ligand
whose artifact and system hashes have been exactly reverified. Cases without a
prepared ligand use the corpus-audited native ligand for charge, size, and
elements as an explicit fallback; receptor metal/cofactor context always comes
from the corpus audit. Unavailable preparation remains an explicit
chemistry/OOD stratum. Each stratum retains all failure, blocked,
abstention, and no-pose cases, Wilson 95% intervals for validity/RMSD outcomes,
wall-duration total/min/max, RSS sample counts, and the maximum sampled case
peak.

The per-case timing scope is only the downstream PoseBusters oracle loop, not
the full preparation/redocking pipeline. Sampled RSS is not additive or a
kernel-enforced isolated maximum, measurement values are not byte-reproducible,
and target OOD cannot be evaluated without an internal fit/training manifest.
The receipt is unsigned and does not establish an official 308-case production
result, second-host reproduction, public bundle validation, or independent
scientific review. Consequently `benchmark_executed=false`,
`scientifically_validated=false`, and `claim_safe=false` remain fixed.

`betelgeuze_engine_v2.benchmark.public_posebusters_internal_oracle_reproduction`
adds a claim-closed second-host work-order and comparison boundary above the
oracle, runtime-observation, and stratification receipts. The installed
`betelgeuze-engine-v2-posebusters-internal-oracle-reproduce` command provides
`materialize-work-order`, `verify-work-order`, `materialize-result`, and
`verify-result` modes. The work order binds caller-pinned baseline receipt
roots and files, the exact active source-bearing Engine v2 wheel, distinct
baseline/external host identity digests, role-separated work-order/execution
operator digests, a single-use nonce digest, and canonical registration time.
It writes a canonical mode-0600 no-overwrite receipt.

The result accepts a separately pinned external chain only when its runtime
and stratification receipt roots differ from the baseline, its runtime names
the preregistered wheel, its asserted host and executor identities match the
work order, and its asserted observation time follows registration. It then
requires exact oracle receipt identity and compares every runtime-free
target/chemistry case, stratum, fixed binding, and Wilson-metric field,
including failure, blocked, no-pose, and abstention rows. Wall duration and
sampled RSS remain distinct observations; batch ratios are reported, but exact
measurement equality is not required and no performance-equivalence threshold
is defined.

The external runtime observation must also payload-bind a canonical execution
attestation. `PoseBustersInternalOracleRuntimeAttestation` carries the
executing host identity, execution operator identity, single-use nonce, and
observed UTC, and the measured receipt publishes both the record and its
digest. The comparison recomputes that digest and requires each attested value
to equal the preregistered work-order value exactly, so an unattested
observation or a replayed nonce fails closed instead of passing as a second
host. Attestation remains optional for ordinary unattested local measurements.

Each receipt chain may additionally carry a detached Ed25519 custody signature.
`posebusters_internal_oracle_chain_signing_payload` fixes the exact canonical
bytes an external custodian signs: the oracle, runtime-observation, and
stratification receipt digests plus the signer identity and signing time.
`verify_posebusters_internal_oracle_chain_signature` re-derives those bytes,
requires the stored payload to match, and verifies the signature against a
`PoseBustersInternalOracleChainTrustAnchor` provisioned out of band. No signing
material is ever accepted by the verifier. Supplying both chain signatures and
the anchor sets `upstream_receipt_signatures_verified=true` and drops the
unsigned-upstream blocker; supplying only part of that triple fails closed, and
two chains signing the same payload are rejected. Signer custody itself remains
unreviewed.

This comparison is not itself proof of an independent physical-host run.
The attested host identity and nonce remain self-declared, and an unsigned
chain stays a bare canonical self-hash: neither form proves physical-host
identity nor proves that the nonce was used only once. Consequently a
deterministic comparison may say
`comparison_passed` while still fixing
`physical_host_independence_reviewed=false`,
`independent_external_rerun_present=false`,
`independent_reviewer_receipt_approved=false`, `benchmark_executed=false`,
`scientifically_validated=false`, and `claim_safe=false`. Independent custody,
host/nonce registry review, upstream receipt authorization, and scientific
result review remain mandatory promotion gates.

`betelgeuze_engine_v2.benchmark.public_posebusters_same_input_engine_comparison`
adds the same-input engine comparison the oracle receipts have been naming as a
blocker. The installed
`betelgeuze-engine-v2-posebusters-same-input-compare` command provides
`materialize` and `verify` modes and binds four caller-pinned receipts: the
internal PoseBusters oracle evaluation and the Vina, GNINA, and Smina
generated-pose evaluations. Every receipt is read as bounded mode-0600 canonical
ASCII JSON, must self-authenticate against its pinned digest, must keep
`benchmark_executed`, `scientifically_validated`, and `claim_safe` false, and
must name the same `archive_intake_receipt_sha256`. Four distinct receipt
digests are required, and each external receipt must declare its own engine id.

The denominator is the union of every case appearing in any bound receipt, so a
case the external engines never reached is retained as an explicit
`absent_from_receipt` row rather than dropped. Each case row records, per
engine, evaluated status, any-physically-valid-pose, Top-1 validity, Top-1 and
Top-5 symmetry-aware RMSD threshold hits, and Top-1 valid-and-hit, all read
from outcomes the upstream receipts already recorded. Six per-engine rates carry
Wilson 95% intervals over that single all-case denominator, and pairwise
internal-versus-external Top-1 agreement partitions every case into both,
internal-only, external-only, and neither.

This module regenerates no pose, executes no engine, and recalibrates no score;
the external engines remain offline reference receipts. The external evaluations
cover only the strictly prepared chemistry subset, so subset selection bias is
unresolved, the internal engine remains uncalibrated, and target-family and
chemistry stratification, an independent rerun, a public bundle validator, and
scientific review are all still absent. Every comparison therefore keeps
`benchmark_executed=false`, `scientifically_validated=false`, and
`claim_safe=false`.

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

`betelgeuze_engine_v2.benchmark.public_posebusters_prepared_ligand_diagnostic`
adds failure-inclusive observation and cross-version comparison contracts over
that exact preparation receipt. The installed
`betelgeuze-engine-v2-posebusters-prepared-ligand-diagnostic` command exposes
`observe`, `verify-observation`, `compare`, and `verify-comparison`. Observation
requires the expected preparation payload SHA-256 and exact mode-0600 receipt
plus private artifact tree. It fingerprints the resolved Python executable,
platform/ABI fields, RDKit core/build/Boost identity, and the owning RDKit
distribution's path-independent regular-file payload.

The PDBQT parser requires one embedded SMILES, complete unique `SMILES IDX`
coverage, bounded `H PARENT` mappings, contiguous atom serials, and only
unmapped zero-charge `G0` macrocycle pseudoatoms. It recomputes RDKit
`ComputeGasteigerCharges` with 12 iterations and `throwOnParamFailure=false`,
then merges charges of omitted H atoms into their source parent as Meeko does.
The 0.0005 e threshold covers only three-decimal PDBQT serialization. Type
checks cover element compatibility and aromatic-carbon `A` consistency; they
do not independently reproduce the AD4 typer.

The production RDKit 2022.09.5 and 2025.09.6 observations each retain all 308
rows, with 18 evaluated cases, zero diagnostic failures, 481 real atoms, and
two separate `G0` pseudoatoms. Every evaluated case passed the serialization,
element/type, aromatic-carbon, and pseudoatom checks; maximum charge delta was
0.0004979832249129013 e. The comparison requires the exact same preparation
identity and atom-mapping projection, then compares canonical binary64 expected
charges. All 481/481 values were bitwise equal and maximum cross-version delta
was zero. Configuration/source aggregate SHA-256 values are
`9e2a86f65b5168595f1c41cce9851d0e8d76bfcdcee838b8687cd06ce589518c`
and `9c31c749782a7c7810f616690fec3378646c72b5ee78a65507bfeceb049d35a3`.
RDKit 2022 observation payload/file values are
`df57b0d48ba905e0f132b66a3b4d4fc344fffc4a40f1d78de181c0264bedba8f`
and `b7e8b3ee7a235f63c79454af8b008230a4ed34e195dc2b85133eae21526962dd`;
RDKit 2025 values are
`6d3389ed55e7d47c8e0b0076c485b3f4ee7590cb3f9ddcd12db89030e92b6b50`
and `f1a78abba41e9783a57616a71930e7bf11f6377a28592d18f2bd66128d26b5f5`;
comparison values are
`ab9cf4b72d3af848dd48484fcbb203268fe8d7336ec552ffe52c360dca972b5f`
and `121bc96482cf2f73622c650dbce5da1fddc8c32f4421c185c2d4c926fadc978f`.
Byte-exact source-tree and isolated installed-wheel verification passed; two
wheels matched at
`9d1c96336c1fa55051ab3e0fc2192d990860c644dc5f39a0685f07c39613124e`.
Both observations use the same Gasteiger implementation family. Independent
charge/type assignment, source-SDF chemistry equivalence, receptor auditing,
unsupported chemistry, second-host reproduction, and reviewer acceptance are
still absent; `independent_charge_oracle_executed=false`,
`scientifically_validated=false`, and `claim_safe=false` are mandatory.

`betelgeuze_engine_v2.benchmark.public_posebusters_openbabel_charge_type_comparison`
adds a failure-inclusive comparison against the separately distributed Open
Babel 3.2.1 implementation. The installed
`betelgeuze-engine-v2-posebusters-openbabel-compare` command exposes `observe`
and `verify`. Both require the exact preparation receipt and private artifact
tree, its expected payload SHA-256, the official CPython 3.10 manylinux x86-64
Open Babel wheel, and expected wheel SHA-256
`ca6345ca6cc66522208c45355a90472d657be78dec7706757d477bfb0c105413`.
Observation also requires an explicit UTC timestamp and private no-overwrite
output. Verification reconstructs the complete canonical receipt and compares
the caller-provided expected receipt payload SHA-256.

The runtime identity binds Python/platform/ABI fields, Open Babel version
3.2.1, source commit `0e94434fa75c9f61095023e3c12e0d5f2ac035ff`, the
path-independent installed distribution payload, the official wheel bytes,
configuration, and implementation sources. The PyPI registry's Trusted
Publishing provenance claim is recorded but was not independently
cryptographically reverified by the local run. Runtime comparison is
network-free. The command reconstructs molecules only from the exact embedded
Meeko SMILES mapping, obtains full-precision charges from
`OBChargeModel("gasteiger")`, and obtains independently assigned AD4 types from
the Open Babel PDBQT writer with `c`, `p`, and `r` options. It reconciles
nonpolar-H charge merging and retained polar H atoms by parent/order; Meeko
`G0` macrocycle closure pseudoatoms remain in each case record but are excluded
from real-atom comparison statistics.

The 2026-07-23 local receipt retained all 308 rows: 18 evaluated, zero
comparison failures, 16 preparation blocks, and 274 chemistry abstentions. It
compared 481 real atoms and retained two excluded `G0` pseudoatoms. Charge
MAE/RMSE/max absolute delta (Open Babel full precision minus the three-decimal
Meeko PDBQT field) was 0.0038510594375734796 / 0.012204476318346003 /
0.18097866788513423 e; signed mean delta was -0.000010395010395007381 e.
Exact AD4 types agreed for 476/481 atoms (Wilson 95% CI
0.9758996496765601–0.9955519278053627). The five explicit mismatches were
three `SA` to `S` assignments in `7CIJ_G0C`, `7LT0_ONJ`, and `7NLV_UJE`, plus
two Meeko macrocycle `CG0` to Open Babel `C` assignments in `7UAW_MF6`. The
largest charge delta was the sulfur at source index 17/PDBQT serial 20 in
`7F5D_EUO`.

Configuration, implementation-source, runtime-identity, receipt-payload, and
receipt-file SHA-256 values are respectively
`a8915ed1625f8522e3315ca1d89f7f2bc2f575f6176a0b737d3317f5f30ac445`,
`f2e614c6708557443c0aced573b1c89e404fc419a2c70df4964ff072367ad62a`,
`d06dace825ee62a9d983c21a95d13beca65f94c8fe97079bb3a400e615cd01e9`,
`7754c4b56e10d4543b064c23daaf69ab99e098fda81bfd9fbaecc8694439d943`,
and `98a5b1c654bbf388f1782519ec9e0a8de54113bcdbb16c08f541d02607342cb5`.
Byte-exact source-tree and isolated installed-wheel verification passed; two
package builds matched at wheel SHA-256
`d0fc6a2acce76f2e3d23915b533528263d10e8277c0cf6feafd09e318c6d9529`.
This establishes execution of an independent charge/type implementation only.
No charge-accuracy threshold was preregistered, neither implementation is a
quantum charge oracle, and the comparison receipt itself does not adjudicate
the five type differences. The source-provenance follow-up below explains
their implementation mechanics without deciding chemical correctness.
Source-SDF chemistry equivalence, receptor
charge/type auditing, representative unsupported chemistry, native-library
identity, second-host reproduction, and independent review remain absent;
`charge_accuracy_pass=null`, `independent_charge_oracle_executed=false`,
`scientifically_validated=false`, and `claim_safe=false` are mandatory.

An exact-tag source-provenance follow-up explains the implementation mechanics
without adjudicating scientific correctness. Meeko 0.7.1 first assigns generic
`[#16]` sulfur type `S`, then its later `[SX2]` rule overrides neutral divalent
sulfur to acceptor type `SA`; its atom typer explicitly permits later matches
to override earlier ones. Open Babel 3.2.1's PDBQT writer emits `SA` only when
`IsHbondAcceptor()` is true, while that implementation returns true for sulfur
only at formal charge -1. The three neutral thioethers therefore represent a
real acceptor-semantics disagreement, not an atom-mapping defect. The relevant
Meeko source files at tag commit
`f4a8c1e7c86da3652f5a46e1d3574fed26aa58a1` are
[`ad4_types.json`](https://github.com/forlilab/Meeko/blob/v0.7.1/meeko/data/params/ad4_types.json),
[`atomtyper.py`](https://github.com/forlilab/Meeko/blob/v0.7.1/meeko/atomtyper.py),
and
[`flexibility.py`](https://github.com/forlilab/Meeko/blob/v0.7.1/meeko/flexibility.py),
with SHA-256 values
`d7e890ec95cf1da9b3f3c92d01ca044b9478bd8b36d6cefad068c3a540257d43`,
`e582309e1be6bb8708d0a42e9d26fea51125e3f4cc44d0ac4cb0e1281680443a`,
and `68b6546d8ea0d8d165bc58c35f783a5d76588555f6a97c022b874ffcf184c741`.
The exact Open Babel source files are
[`pdbqtformat.cpp`](https://github.com/openbabel/openbabel/blob/openbabel-3-2-1/src/formats/pdbqtformat.cpp)
and
[`atom.cpp`](https://github.com/openbabel/openbabel/blob/openbabel-3-2-1/src/atom.cpp),
with SHA-256 values
`ceb9469ca6aa5dec433f5561282237df59b08f84c9498244e29b83506947cc65`
and `e15d64ce7ec6494e41b098224ed6b0f8772ae8e25848ffdebd19620a80e378ed`.

The two `CG0`/`C` rows are an expected vocabulary extension rather than an
unexplained chemical perception difference: after selecting a macrocycle bond,
Meeko adds paired `G0` pseudoatoms and overwrites both closure carbons with
`CG0`. Open Babel's general PDBQT writer has no corresponding ring-closure
extension and emits ordinary aliphatic `C`. The Vina 1.2 methods paper also
describes `Gx`/`CGx` as added macrocycle pseudoatom types. This disposition
does not make `CG0` portable to GNINA or Smina and does not validate the chosen
ring break; it only explains why raw vocabulary equality is inappropriate for
those two rows.

The `7F5D_EUO` methylsulfone outlier is likewise implementation-explained but
not accuracy-adjudicated. Open Babel's six-iteration implementation selects a
special branch when sulfur has more than one free oxygen; RDKit sees the same
sulfur as `SP3` and selects its `S/sp3` parameter row. A controlled rerun in
both frozen RDKit 2022.09.5 and 2025.09.6 produced identical sulfur charges:
0.21119588924581498 e at six iterations, 0.21034893344174249 e at 12, and
0.21033550574606594 e at 24. The six-to-12 iteration change is only
0.0008469558040724856 e, whereas Open Babel reports 0.029021332114865777 e;
iteration count alone therefore cannot explain the cross-implementation
difference. RDKit's exact
[`GasteigerCharges.cpp`](https://github.com/rdkit/rdkit/blob/Release_2025_09_6/Code/GraphMol/PartialCharges/GasteigerCharges.cpp)
and
[`GasteigerParams.cpp`](https://github.com/rdkit/rdkit/blob/Release_2025_09_6/Code/GraphMol/PartialCharges/GasteigerParams.cpp)
are bound by release tag `0ece02e9254ef2d5eeade2bd40eb13546522dbd3`;
Open Babel's exact
[`molchrg.cpp`](https://github.com/openbabel/openbabel/blob/openbabel-3-2-1/src/molchrg.cpp)
and
[`molchrg.h`](https://github.com/openbabel/openbabel/blob/openbabel-3-2-1/include/openbabel/molchrg.h)
have SHA-256 values
`92a77b0ea1357185c02bead3cf5cf2d21fc9b907634ae01fcee167e9bbd87e68`
and `24911cb8ea5e7b235b6213e811d5e255988b8d3705dea2662194e0f325cbacdd`.
These source and control observations are not yet a canonical receipt and do
not supply a quantum electrostatic-potential reference or preregistered error
threshold; scientific charge accuracy remains open.

`betelgeuze_engine_v2.benchmark.public_posebusters_sulfur_qm_esp` adds a
preregistration-first fixed-geometry molecular electrostatic-potential
diagnostic. The installed
`betelgeuze-engine-v2-posebusters-sulfur-qm-esp` command exposes `register`,
`verify-protocol`, `observe`, and `verify-observation`. Registration consumes
the exact archive intake, preparation, and Open Babel comparison identities,
the official PySCF 2.14.0 wheel, and an explicit UTC timestamp, then writes a
private no-overwrite protocol receipt without running QM. Observation requires
that exact protocol and all bound inputs; verification reconstructs the
canonical protocol or observation and requires the caller-provided expected
payload SHA-256.

The 1.0.0 protocol scope is exactly `7CIJ_G0C`, `7F5D_EUO`, `7LT0_ONJ`, and
`7NLV_UJE`, while every other PoseBusters row remains an explicit scope
abstention in the 308-case denominator. It freezes the source start-conformer
SDF coordinates, explicit hydrogens, neutral singlet RHF/6-31G* calculation
with spherical basis functions and no geometry optimization, `minao` initial
guess, SCF and gradient tolerances, one native thread, and bounded memory and
iteration counts. The ESP grid uses PySCF's Lebedev-110 angular grid on 1.4,
1.6, 1.8, and 2.0 times fixed element radii, removes buried points, and gives
each shell equal aggregate weight. Meeko's actual three-decimal PDBQT charges
and Open Babel's full-precision charges are projected onto the exact same
prepared sites after a 0.001 A coordinate-bound check. Global and per-shell
weighted MAE, RMSE, signed error, maximum error, relative RMSE, Pearson
correlation, and the same-site model delta are retained with exact hashes for
coordinates, charges, angular grids, surfaces, density matrices, and ESP
vectors.

The runtime identity requires the official PySCF wheel
`pyscf-2.14.0-py3-none-manylinux_2_17_x86_64.manylinux2014_x86_64.whl`
at SHA-256
`37b0bccc55450311a55318cd643e851353331ddeab4fc0c0065e83c905e41502`,
source commit `c63a953ba603a5ad8c1d65d88da72aaf05ede4d8`, PySCF 2.14.0,
NumPy 1.26.4, SciPy 1.12.0, h5py 3.11.0, RDKit 2025.9.6, and
threadpoolctl 3.6.0. It verifies that installed PySCF content matches the
official wheel and that PySCF plus every discovered native thread pool uses
exactly one thread.

The preregistered protocol payload SHA-256 is
`0927260a16f1e09211fb601fade1725e21d35d221d04e69cfd2c624da7c06137`.
The 2026-07-23 observation retained 308 rows, evaluated all four scoped cases,
recorded zero QM failures and 304 scope abstentions, and labeled Meeko as the
lower global weighted ESP-RMSE model in 4/4 cases. The four Meeko/Open Babel
RMSE pairs in Hartree/e were respectively
0.01296866293778705/0.013041094573092262,
0.017459540473039038/0.017512572512645257,
0.010743378216444197/0.010776571832085028, and
0.011221393498522648/0.011295205716778691. These differences are small and
descriptive only. Exact source-tree and isolated installed-wheel reexecution
reproduced observation payload SHA-256
`402d1795f18b7eb0c87d8537f3b427fe116c0845bf1337b21e24752cef7e52e6`;
two deterministic builds matched at wheel SHA-256
`b4564648dbf3fcb681e0b73d1dcbcc2fd96ed10a0fe4a321149fe38545d0d73d`.

No accuracy threshold was preregistered, so
`charge_accuracy_threshold_preregistered=false` and
`charge_accuracy_pass=null`. HF/6-31G* is a defined reference, not an absolute
oracle; atom-centered charges are not observables; this four-case fixed-
geometry result is not representative chemistry coverage; and ESP does not
adjudicate neutral-thioether `SA` versus `S` hydrogen-bond semantics.
Accordingly `sa_vs_s_hydrogen_bond_type_adjudicated=false`,
`scientifically_validated=false`, `benchmark_executed=false`, and
`claim_safe=false` are mandatory. The bounded interaction-energy gate is
reported below, but a second CPU host and independent reviewer receipt remain.

`betelgeuze_engine_v2.benchmark.public_posebusters_vina_sulfur_type_invariance`
separates the active product-scoring consequence from that remaining chemical
question. The installed
`betelgeuze-engine-v2-posebusters-vina-sulfur-invariance` command exposes
`register`, `verify-protocol`, `observe`, and `verify-observation`.
Registration consumes the exact preparation, Open Babel comparison, and Vina
execution receipts plus their complete private artifact trees and a caller-
provided AutoDock Vina 1.2.7 source checkout. It performs no rescoring and
writes a private no-overwrite protocol receipt.

The source boundary is tag commit
`8eb40404f4f45608acb3b01427587ac049f27c1f`. It verifies exact SHA-256 for
`src/lib/atom_constants.h`, `model.cpp`, `potentials.h`,
`scoring_function.h`, and `vina.h`. The semantic projection is fail-closed:
both `AD_TYPE_S` and `AD_TYPE_SA` map to `EL_TYPE_S`; all element sulfur maps
to `XS_TYPE_S_P`; default Vina scoring selects XS atom typing; the Vina
hydrogen-bond potential dispatches through `xs_h_bond_possible`; and the exact
XS acceptor set contains nitrogen and oxygen acceptor types but not
`XS_TYPE_S_P`.

The protocol scope is exactly `7CIJ_G0C`, `7LT0_ONJ`, and `7NLV_UJE`.
Every other case remains an explicit abstention in the 308-row denominator.
For every model in each exact Vina pose artifact, the counterfactual changes
only PDBQT columns 78–79 for the target serial from `SA` to `S`. Length,
coordinates, charges, topology, all other bytes, model identities, receptor,
maps, pocket center, scoring configuration, runtime distribution, and source
identities remain fixed. Observation separately initializes original and
counterfactual map engines, then calls the public `Vina.score()` API for every
model and retains all eight canonical binary64 score components, exact-equality
flags, non-type projections, model hashes, bounded diagnostics, and all failure
rows.

The preregistered protocol payload SHA-256 is
`81f52bbf68518e1d09e0462f8124ac1a810c7cc502ff8923175703e62b28b57f`.
The production observation evaluated 3/3 cases and 60/60 pose pairs, recorded
zero score failures and 305 scope abstentions, and found exact equality for all
eight components in every pair. Source-tree and isolated installed-wheel exact
reexecution reproduced observation payload SHA-256
`a08ced8bbe0dbecc503f8e5eedf96d239130d0dbced897427694afe61742d406`;
two deterministic wheels matched at SHA-256
`fcbdc2df96c3b7df53f90e50e90688898147bf4665f2a816eb7d82382f547535`.

The exact gate therefore sets
`default_vina_fixed_pose_score_invariance_pass=true` and
`bounded_default_vina_invariance_claim_safe=true`. This narrow result does not
reexecute docking search, cover complete AD4 scoring, adjudicate whether neutral
thioethers are chemical hydrogen-bond acceptors, validate representative
chemistry, or promote docking performance. Consequently
`chemical_acceptor_semantics_adjudicated=false`,
`ad4_scoring_evaluated=false`, `docking_search_reexecuted=false`,
`scientifically_validated=false`, `benchmark_executed=false`, and
`claim_safe=false` remain mandatory. The donor-acceptor interaction-energy
protocol is now explicitly an AD4/chemical-semantics gate, not a blocker for
the observed default-Vina fixed-pose score path.

`betelgeuze_engine_v2.benchmark.public_posebusters_sulfur_interaction_energy`
implements that bounded interaction-energy gate. The installed
`betelgeuze-engine-v2-posebusters-sulfur-interaction` command exposes
`register`, `verify-protocol`, `observe`, and `verify-observation`.
Registration requires the exact prior QM-ESP and default-Vina invariance
protocol/observation receipts, a caller-pinned Vina 1.2.7 source checkout, the
official PySCF 2.14.0 wheel, the pinned PySCF-dispersion 1.5.0 wheel, and an
explicit UTC time. It writes a canonical mode-0600 no-overwrite protocol and
performs no QM calculation. Observation requires that exact protocol and
reconstructs all bound inputs; verification reruns and compares the complete
canonical receipt exactly. PySCF and PySCF-dispersion remain caller-supplied
offline evidence dependencies; neither is added to the normal product runtime.

`betelgeuze_engine_v2.benchmark.public_posebusters_sulfur_interaction_external_reproduction`
adds the external custody surface. The installed
`betelgeuze-engine-v2-posebusters-sulfur-reproduce` command exposes
`register`, `verify-work-order`, `execute`, `verify-result`,
`build-review-request`, `review-signing-bytes`, `attach-review-signature`, and
`verify-review`. Registration performs no QM calculation. Execution must match
the preregistered external host and executor and retains bounded initialization,
runtime-projection, execution, QM, and comparison failures. Result verification
reconstructs the work order and wheel source members, verifies canonical
runtime and embedded-observation digests, and rederives every 308-row,
21-point, 63-SCF comparison.

The review request is canonical and recursively rejects private signing
material. A detached signature is accepted only against a caller-supplied
public verification key; final verification additionally requires an
out-of-band reviewer identity/key binding plus explicit revocation and
supersession inputs. An accepted receipt can set only
`second_cpu_host_reproduced=true` and
`independent_reviewer_receipt_approved=true` for this bounded result.
Directionality, representative chemistry, receptor/solvent context, complete
AD4 scoring, docking accuracy, and product promotion remain false. No actual
external-host or reviewer receipt is bundled with rc2.

The scope is exactly the aliphatic `7CIJ_G0C`, diaryl `7LT0_ONJ`, and cyclic
`7NLV_UJE` neutral-thioether environments. The frozen acceptor models are
dimethyl sulfide, diphenyl sulfide, and tetrahydrothiophene with binary64
ETKDGv3/MMFF94s coordinates. The donor is fixed methanol with its O-H vector
aimed at sulfur. For each acceptor, registration freezes primary S-H distances
2.0, 2.25, 2.5, 2.75, 3.0, and 5.0 A on the least-occluded of two idealized
tetrahedral lone-pair axes, plus a 2.5 A positive C-S-C plane-normal control.
The primary axis is selected by steric clearance without evaluating energy.
Every complex, acceptor-with-probe-ghost, and probe-with-acceptor-ghost
geometry is hashed before execution.

QM is fixed-geometry, neutral-singlet B3LYP-D3(BJ)/def2-SVP with spherical
functions, density fitting through `def2-universal-jkfit`, explicit PySCF level
2 integration-grid machinery, `minao` initialization, SCF tolerance `1e-9`,
and one native thread. Boys-Bernardi counterpoise is computed from a complex
SCF plus both ghost-basis fragment SCFs. Each point retains total and dispersion
energies, electron and orbital counts, SCF cycles, integration-grid size,
geometry hashes, and either the result or a bounded failure row.

The same receipt projects the exact AutoDock4 source equations and weights for
the `S-HD` van der Waals pair and `SA-HD` hydrogen-bond pair from the pinned
Vina source. It compares only far-referenced normalized profiles and minimum
locations; absolute QM and isolated AD4 pair magnitudes are explicitly not
claimed comparable. Before QM, the protocol requires each model to have a
minimum at or below -1.0 kcal/mol, a well depth relative to 5 A at or below
-0.5 kcal/mol, and a minimum between 2.0 and 3.0 A. The local acceptor gate
requires 3/3 models. The `SA` profile gate requires a normalized-RMSE
improvement margin of at least 0.02 without worse minimum-distance alignment,
again for 3/3 models.

Protocol payload SHA-256 is
`f0b0d84551e63272509acaf967996496cc7100cd2a58b71392fe38bce7d8194c`.
The production observation completed all 21 geometries and 63 SCFs with zero
failures, retained 305 scope abstentions, and has payload SHA-256
`30d9ceb83aed88fa45b7bc8c8282e6a50ce0299c9f54b21ce0c8885775c35fce`.
Exact source-tree and fresh installed-wheel observation reexecution reproduced
that payload. The three counterpoise minima were all at 2.5 A and were -4.904978,
-4.757719, and -5.257573 kcal/mol. Their 5 A-referenced well depths were
-4.399215, -4.273605, and -4.699997 kcal/mol. Both preregistered local gates
passed 3/3. The AD4 `SA` minimum-distance error was 0 A versus 0.25 A for `S`,
and its normalized profile RMSE was lower in all three models.

That positive bounded result is not a general directionality result. At 2.5 A,
the plane-normal controls were respectively 0.551487, 0.632256, and 0.784138
kcal/mol more favorable than the selected idealized lone-pair direction. The
receipt therefore keeps `chemical_acceptor_semantics_adjudicated=false`.
It also covers only one O-H donor, three fixed gas-phase models, no receptor or
solvent, and isolated pair terms rather than a complete AD4 score. Two
pinned-tool wheel builds were byte-identical at SHA-256
`bb47ad0c5dcb0a5b9d298d2ba7f423910c11bf03c13f1691c0ecbec9c6db6f56`.
Second-host reproduction and independent review are still absent, so
`scientifically_validated=false`, `benchmark_executed=false`,
`product_promotion_allowed=false`, and `claim_safe=false` remain mandatory.

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

`betelgeuze_engine_v2.benchmark.public_posebusters_generated_pose_evaluation`
adds the failure-inclusive generated-pose evaluation layer. The installed
`betelgeuze-engine-v2-posebusters-evaluate-generated` command has `materialize`
and `verify` modes. It requires the exact archive/intake/corpus chain, strict
preparation receipt payload SHA-256
`3856706f5b470386e9151bc272f158192839683deaf08a2bc8f1d377b22082ba`,
Vina receipt payload SHA-256
`37b3df7c4c14d739d9fca3970dc73293a48909372314a8dfe1da5bcd956694ae`,
both complete private artifact trees, and the exact PoseBusters 0.6.5 wheel
(SHA-256
`3e0cbca6481079d5ab7d1989a8a8f184dbba27366613c4b515658ea52fb95ea3`).

Each Vina PDBQT artifact is reconstructed through pinned Meeko. Because Meeko
returns one RDKit molecule containing multiple conformers, the evaluator copies
each conformer into a one-conformer molecule and assigns conformer ID zero
before one case-level PoseBusters batch call. It uses the official `redock`
configuration (SHA-256
`4d551d898ff29a404f16e02ad5a7a2d4235e6b7b14e9a3e27f7c66b4d16b2da9`),
retains all 133 typed full-report values for every pose, and separately records:

- the conjunction of the 27 selected non-RMSD binary tests;
- identity, intramolecular geometry, internal-energy, and intermolecular groups;
- PoseBusters robust direct heavy-atom RMSD in the receptor frame, plus its
  Kabsch and centroid diagnostics;
- every Vina rank and energy component, failure row, and bounded diagnostic.

The 2026-07-23 local ignored-state receipt retained all 308 cases: 18 evaluated
Vina-success rows, 16 preparation blocks, and 274 chemistry abstentions. It
evaluated 355/355 poses (95% Wilson CI 0.989295–1.0); 325/355 passed every
non-RMSD binary test (0.915493, 95% CI 0.881925–0.940165). On the conditional
18-case Vina-success subset, Top-1 direct RMSD <= 2 A was 10/18 (0.555556, 95%
CI 0.337164–0.754405), and Top-5 was 16/18 (0.888889, 95% CI
0.672002–0.968980). `7LT0_ONJ` and `7XFA_D9J` were the two Top-5 misses.

Receipt payload SHA-256 is
`9c680e1edd08bfa07c1c71164b696ae050f180c3a2bb04bc91fd5d163a965b86`;
receipt-file SHA-256 is
`4903b3c5a34dc18fd38f9ba031099f0f2db688e4de66d2d42159163926a8975f`.
Configuration, implementation, and runtime identity SHA-256 values are,
respectively,
`3c02c32628e5974f23490652467517f26bd60242b680215dcdbae5d4d852ad74`,
`ac807c0688983a92f23b5cbed0e1e922349a07ca6f770401f817a1c4800eedd8`,
and `7834c35fe4052355a1dcc5b67f0b75583f922689a55f12181d4c2bd73e792ca9`.
The installed-wheel console script reproduced the canonical receipt byte for
byte. Two builds under pinned setuptools 75.8.2 and wheel 0.45.1 were also
byte-identical at wheel SHA-256
`b0248a218aaea0ef3f00e65d6f77e077cdd81a4c7ac37a128edd7833e3ce49a8`.

This result is conditional on the 18 strictly prepared cases, not a
representative 308-case docking benchmark. Default AD4 types and Gasteiger
charges remain independently unvalidated beyond the bounded same-algorithm
diagnostic, and no target-family, leakage, calibration,
independent-host, or reviewer receipt is present. Therefore
`benchmark_executed=false`, `scientifically_validated=false`, and
`claim_safe=false` remain mandatory.

`betelgeuze_engine_v2.benchmark.public_posebusters_external_binary_execution`
adds failure-inclusive GNINA 1.3.3 and Smina 2019-10-15 execution lanes. The
installed `betelgeuze-engine-v2-posebusters-external-execute` command has
`materialize` and `verify` modes and accepts only the exact strict-preparation
receipt and complete private artifact tree. The official executable bytes,
GNINA dynamic-library closure, runtime/platform identity, configuration, source
members, diagnostics, generated PDBQT bytes, and score components are bound by
the receipt.

The common configuration uses one CPU, seed 20260723, a native-centroid 22.5 A
cube, exhaustiveness 32, at most 20 modes, 1 A minimum separation, explicit
Vina scoring, and no added ligand hydrogens. GNINA uses CPU-only CNN rescoring,
sorts by CNNscore, and records minimized affinity, CNNscore, and CNNaffinity;
its binary does not support the configured energy-range option. Smina sorts by
minimized affinity and uses a 20 kcal/mol range. Both receipts retain all 308
rows and every engine/preparation/chemistry failure.

The production runs each attempted 18 prepared cases and succeeded on 17. Both
classified `7UAW_MF6` as an engine-input-validation failure because prepared
AutoDock type `CG0` is unsupported. GNINA retained 340 poses at receipt SHA-256
`60d0e6a67c86075905cd54497ab12a678f0f54a15a11d7e9345122369d390847`,
receipt-file SHA-256
`ee90b782166f1126fbe6db28ddeaab977cf3aaf830e49938ee37b2cd2d521138`,
and artifact-set SHA-256
`efe518828d5c27b9a6820852091d25e84edf06618baf54e9654599febe295fa2`.
Smina retained 336 poses at receipt SHA-256
`912b7081ba35d11e0accdf1af9c5ebb55c09641390f17242fb8b210d67d27733`,
receipt-file SHA-256
`5855dc2e6a6ee92602eb34b86eb165236cf744bea8dea112185559396df1e4c8`,
and artifact-set SHA-256
`94c15eae0c330814fe0ddb25eb3ce732e6f317bf6fdc3fac523a932295ed5926`.
Source-tree and installed-wheel exact reexecution reproduced both receipts.

`betelgeuze_engine_v2.benchmark.public_posebusters_external_generated_pose_evaluation`
adds the matching PoseBusters evaluation layer. The installed
`betelgeuze-engine-v2-posebusters-external-evaluate-generated` command also has
`materialize` and `verify` modes. It requires one of the exact GNINA/Smina
execution receipts, its complete private artifact tree, the source chain, and
the pinned PoseBusters wheel. It preserves every engine score component and all
133 typed `redock` report values for every evaluated pose, while keeping
physical validity and direct receptor-frame RMSD as separate endpoints. Its
metrics include both all-308 and engine-success denominators.

GNINA evaluated 340/340 poses (95% Wilson CI 0.988828–1.0); 304/340 were
physically valid (0.894118, 95% CI 0.856896–0.922533). On the conditional
17-case execution-success subset, Top-1 RMSD <= 2 A was 15/17 (0.882353, 95%
CI 0.656636–0.967120), and Top-5 was 16/17 (0.941176, 95% CI
0.730180–0.989540). `7XFA_D9J` was the Top-5 miss. Receipt payload and file
SHA-256 values are
`0959201d6165d82041447be820977de7ac8ba64b13d1f237ad5b8c914a290259`
and `6f6920af91c5761c8ce4c3cbed6d7e596042b2c0a1ebb4043ccee200ce84ffd1`.

Smina evaluated 336/336 poses (95% Wilson CI 0.988696–1.0); 312/336 were
physically valid (0.928571, 95% CI 0.895920–0.951534). On its conditional
17-case subset, Top-1 was 10/17 (0.588235, 95% CI 0.360054–0.783889), and
Top-5 was 15/17 (0.882353, 95% CI 0.656636–0.967120). `7LT0_ONJ` and
`7XFA_D9J` were the Top-5 misses. Receipt payload and file SHA-256 values are
`0590067f9c1731f6ebcbff36f54ba08d9265f32454b54fa03b7df0dbc328b930`
and `4f8231d98103d1dffa19f54f085b365886a34932e04802e26fe13573d32fb6ae`.

Both evaluation receipts bind implementation SHA-256
`6d7de40b994d71f2d320607fbbb6789235d681bf3e108f3729de807ce7cfb66f`,
PoseBusters runtime identity
`7834c35fe4052355a1dcc5b67f0b75583f922689a55f12181d4c2bd73e792ca9`,
and evaluation configuration
`3c02c32628e5974f23490652467517f26bd60242b680215dcdbae5d4d852ad74`.
Installed-wheel exact reexecution reproduced both canonical receipts. Two
correctly staged builds under setuptools 75.8.2 and wheel 0.45.1 were
byte-identical at wheel SHA-256
`02356f803a448fdb3f77f5594ef4927eacc1221d319069fa4b81ace25dc4a8f0`.

These numbers are conditional on 17 execution-success cases per engine and do
not constitute a representative 308-case docking benchmark. The all-case rows
still contain one engine failure, 16 strict-preparation failures, and 274
chemistry abstentions. Independent charge/type validation, complete target-family coverage,
external-fit leakage control, calibration, independent-host execution/
evaluation, and reviewer acceptance remain open;
`benchmark_executed=false`, `scientifically_validated=false`, and
`claim_safe=false` remain mandatory.

`betelgeuze_engine_v2.benchmark.public_posebusters_target_cluster_binding`
adds a conservative observed-target clustering and result-projection layer. The
installed `betelgeuze-engine-v2-posebusters-target-clusters` command has
`materialize` and `verify` modes. It exactly reverifies the published archive
intake and requires caller-pinned canonical Vina, GNINA, and Smina generated-
pose evaluation receipts. The three receipts must share the same archive,
corpus-audit, preparation, and ordered 308-case identities.

For each exact receptor PDB, the implementation reads only `ATOM` rows from the
first coordinate model, preserves the first-observed chain and residue order,
and hashes exact three-character residue-label sequences. Chains shorter than
20 residues remain in case identity but cannot create links. A case pair links
only when at least one eligible chain pair satisfies
`1 - Levenshtein_distance / max(chain_lengths) >= 0.90`; one maximum-similarity
chain pair is retained with deterministic ties. Connected components define
the observed-target clusters. Engine case rows, cluster membership, coverage,
complete coverage, any-member outcome counts, all-cluster and covered-cluster
Wilson intervals, and every failure/abstention disposition remain explicit.

The exact local run projected 308 cases onto 296 clusters: 11 clusters contained
multiple cases, the maximum size was 3, and 13 case-pair links were retained.
Vina covered 18/296 clusters (95% Wilson CI 0.038808–0.094067) and completely
covered 17/296 (0.036164–0.090041). GNINA and Smina each covered 17/296 and
completely covered 16/296 (0.033543–0.085992 for complete coverage). On the
covered-cluster denominator, explicit any-member Top-1/Top-5 RMSD-hit counts
were 10/18 and 16/18 for Vina, 15/17 and 16/17 for GNINA, and 10/17 and 15/17
for Smina. The matching Wilson intervals are retained in the receipt.

Configuration, implementation-source aggregate, receipt payload, and receipt-
file SHA-256 values are, respectively,
`5b713f0680f796457da8f48261d78dee5e5c2caf36677f5f9777276083dc3c94`,
`a030066e19f38086e7c63c27295c0e657bb9ea93f08d1d1199ad9f3fc1d7bd23`,
`34d782567e816206dcaf2be5207e424b8611a081c9ca6d51bc9500e42ec81e5e`,
and `fc69398c600c032f7f5c18ca1fc8baedd51c93db0f933c2320d1f597265750aa`.
Byte-exact reconstruction verified the mode-0600 receipt. Two pinned-tool
builds were byte-identical at wheel SHA-256
`050d06e9fc49ef3c79bcaefbd8854de85fce0ce7fe4a56cc83418a460280a597`;
an isolated installed-wheel console script reproduced the same receipt.

This method is deliberately an observed near-identity proxy, not a biological
target-family annotation or homology analysis. It does not provide a model-fit
split or compare the evaluation set with any training corpus. Vina, GNINA, and
Smina fit/training manifests are recorded as missing; target-sequence and
ligand/scaffold training leakage remain unevaluated. Consequently
`external_fit_training_leakage_audit_present=false`,
`leakage_control_passed=false`, `benchmark_executed=false`,
`scientifically_validated=false`, and `claim_safe=false` are mandatory.

`betelgeuze_engine_v2.benchmark.public_posebusters_rcsb_target_family_binding`
adds a normalized official-source annotation and result-projection contract.
The installed
`betelgeuze-engine-v2-posebusters-rcsb-target-families` command exposes
`verify-snapshot`, `materialize`, and `verify` modes. It never performs a
network request. The immutable snapshot records the official RCSB GraphQL and
holdings endpoints, exact query SHA-256, observation UTC, retrieval-tool byte
identity, ordered request batches, and canonical normalized response hashes;
raw API responses are not persisted and RCSB does not independently sign the
snapshot.

For each exact archive case, strict PDB and SDF parsers recompute native-ligand
pocket association from non-hydrogen protein and ligand atoms at an inclusive
6 A cutoff. A one-character archive chain maps first to an exact RCSB
`asym_id`; only if none exists may an exact `auth_asym_id` match be used. Chain
truncation, aliases, fuzzy matching, and removed-entry replacement remapping
are prohibited. The production observation contains 307 active entries and the
explicit removed `7D6O` disposition. The binding has 306 complete case
mappings, 299 UniProt-annotated cases, 225 Pfam-annotated cases, one exact
mapping failure (`6Z14_Q4Z`), and one removed-entry case (`7D6O_MTE`).

Pfam rows are deliberately multi-label: 199 distinct Pfam IDs occur, 46 span
more than one case, and the largest spans 15. A companion exact Pfam-set
partition prevents double counting: 149 sets occur, 31 repeat, and the largest
also spans 15 cases. For Vina, GNINA, and Smina, every family and set row keeps
the all-member denominator, execution-success count, Top-1/Top-5 RMSD-hit
counts, Top-1/Top-5 valid-RMSD-hit counts, and Wilson intervals. Source engine
failures and abstentions remain in those denominators.

GraphQL query, configuration, implementation-source aggregate, snapshot
payload/file, and target-family receipt payload/file SHA-256 values are,
respectively,
`ae19930d182dfd20570bea726cdcfcfee8788555cbec9f62ab6e071c8728fe83`,
`be8966a25136e3cd74456cc0a4b228a012dec4995933489fbaeb6039aa5bbad8`,
`060ae95a5156b74701c7d6eeef22ab0087155c35d170065b1f79fe524824b23f`,
`4d05e0127bb4c4dfedb5fa0a5f2e11d7de22aae481d34d3840676d04d367b51a`,
`2287ffc895b28828ff39568f3ee0b98707b8160f04fa10196b469fe9ba722358`,
`ce7d0f32054f05a328554fa04e38964768d2e734157aa9eca4ceb431c2a87076`,
and `164ef81d7e49dbf32aab6eef56325dfd2ee57e889304e7f3ac0dff7f11a36761`.
Byte-exact local reexecution verifies the canonical mode-0600 receipt. Two
pinned-tool builds were byte-identical at wheel SHA-256
`02d837ed5f624505a5a02bf1a5489f8aec1dcf0bacd15ef39b0fa6abf8526deb`;
the isolated installed-wheel command reproduced both snapshot and result.

This surface adds pocket-associated RCSB/Pfam provenance, not complete
biological-family coverage or a leakage audit. The external engines still have
no fit/training manifests, so target-sequence and ligand/scaffold overlap are
not evaluated. `external_fit_training_leakage_audit_present=false`,
`leakage_control_passed=false`, `public_benchmark_claim_authorized=false`,
`scientifically_validated=false`, and `claim_safe=false` remain mandatory.

`betelgeuze_engine_v2.benchmark.public_posebusters_pose_ranking_intake`
provides the receipt-to-calibration boundary for those exact production
artifacts. The installed
`betelgeuze-engine-v2-posebusters-ranking-intake` command exposes
`materialize` and `verify` modes. The caller must pin the Vina, GNINA, and
Smina evaluation receipt SHA-256 values and the RCSB/Pfam target-family receipt
SHA-256. The command then verifies every linked archive, preparation,
execution, and evaluation payload/file identity and requires canonical private
mode-0600 inputs.

The result is always `split_role=test`. Every evaluated pose retains its exact
engine-namespaced component order and canonical binary64 values, direct-RMSD
native-like label, and separate physical-validity label. A case with no
evaluated pose contributes one term-free failure row, preserving the all-308
denominator per engine. The current exact receipt reconstructs 924 engine/case
rows, 1,031 successful pose rows, and 872 failure rows, with 225/308 exact
Pfam-set assignments. Its Top-1/Top-5 all-case counts are 10/16 for Vina,
15/16 for GNINA, and 10/15 for Smina. Payload/file SHA-256 values are
`b6526c7407602721f2ec74f09c8b99d4ecdc7336e69417ed6321840663de9ea0`
and `88b756cd3e7d460edefe8330dbae6141e72492953a1af4e71bb60b1146574813`.
Two deterministic wheels matched at
`c8019fa070e8ca2fc598e26cbdf3c78394fcf9e0963ec656d736b3864681ac51`;
the installed-wheel receipt was byte-identical to the source-tree receipt.

This object is intentionally not a `PoseRankingCalibrationPartition`.
Its base `pose_coordinate_sha256` and `scaffold_sha256` fields remain null,
incomplete Pfam assignment remains explicit, and fit/training plus
target-sequence and ligand/scaffold leakage receipts are missing. The command
never calls `fit_pose_ranking_calibration`;
`test_labels_used_for_fit=false`, `calibration_partition_materialized=false`,
`leakage_control_passed=false`, and `claim_safe=false` are invariant.

`betelgeuze_engine_v2.benchmark.public_posebusters_pose_scaffold_identity`
provides an exact identity overlay for that immutable intake. The installed
`betelgeuze-engine-v2-posebusters-pose-scaffold-identity` command exposes
`materialize` and `verify` modes. Callers pin the archive, preparation,
Vina/GNINA/Smina execution, and ranking-intake receipt roots plus the three
private mode-0700 artifact roots. The command requires mode-0600 artifacts,
strict contiguous PDBQT models and atom mappings, exact three-decimal
coordinates, and the RDKit 2025.09.6 distribution/host identity already bound
by the preparation receipt.

Each generated pose receives a SHA-256 over the canonical source-chemistry
topology projection and all ordered PDBQT coordinate tokens; score remarks are
excluded. Each failed ranking row remains present with its source error and
disposition evidence. Per-case scaffold grouping uses canonical non-isomeric
RDKit Bemis-Murcko SMILES. When the Murcko graph is empty, the explicitly named
`acyclic_full_heavy_graph` policy hashes the complete non-isomeric heavy graph;
the API does not represent that fallback as a standard Bemis-Murcko scaffold.

The production overlay binds all 1,903 ranking rows: 1,031 coordinate
identities and 872 upstream failures. All coordinate identities are unique;
generated/start chemistry and cross-engine topology mismatch counts are zero.
All 308 start/reference scaffold pairs agree, producing 229 groups, 15 repeated
groups, maximum size 21, 275 Bemis-Murcko cases, and 33 acyclic fallbacks.
Start/reference full chemistry agrees for 305/308 cases; the three differences
remain explicitly pending independent disposition. Receipt payload/file
SHA-256 values are
`e7b92d0fc74b44f652c5196429812fe61165771906d9d487a13ec8719ac52995`
and `fbf3fa34f974dc8bd35b6564a1c004931a9ea0177f25fd551769b91f4db089d8`.
The overlay closes only the coordinate and scaffold identity omissions.
Complete target-family assignment, a disjoint fit manifest, target/ligand/
scaffold leakage audits, external rerun, and independent review remain absent;
the overlay's fit, partition, scientific, and product-claim flags remain false.

`betelgeuze_engine_v2.benchmark.public_posebusters_pose_ranking_test_partition`
provides the next exact, test-only boundary. The installed
`betelgeuze-engine-v2-posebusters-ranking-test-partitions` command exposes
`materialize` and `verify` modes and requires caller-pinned roots for the
ranking intake, pose/scaffold identity, observed-sequence cluster, and
RCSB/Pfam receipts.

It materializes one failure-inclusive
`PoseRankingCalibrationPartition(split_role="test")` per engine. The Vina,
GNINA, and Smina partitions retain 645, 631, and 627 rows respectively and all
308 cases each. The 1,031 successful rows use exact pose-coordinate SHA-256
values. The 872 failure rows have no coordinates or labels; because the generic
row contract requires `pose_sha256`, they use unique hashes over the
domain-separated failed-observation schema, exact source ranking-row identity,
engine, case, and failure code. Those values must not be interpreted as
coordinate hashes.

The generic row's `target_family` field is populated with the complete
observed-receptor sequence proxy ID. Receipt metadata and per-case rows state
that the 296 strata are not biological target families. RCSB/Pfam remains a
separate annotation surface with 225/308 annotated cases. The builder
revalidates all 21 ranking, 36 proxy-cluster, and 5,226 Pfam-family metric rows,
including numerator, denominator, estimate, and 95% Wilson interval, and
retains their canonical roots.

Production receipt payload/file SHA-256 values are
`509a7f7c8fcae221be53d5d7e525e05c37a1314f6d17060c8ed6b68e8e4fc89e`
and `581235213b161caeb41db441ca73428d669a7fa0c9a3ead3bba7632dfa63b1dc`.
Two deterministic wheels and isolated installed-wheel verification matched at
`5378c25f700a3f775aca232e379ea9e56b93a75310daead5d7dfdae082d9800e`.
The module never constructs a fit partition or calls a fitting API.
`calibration_fit_performed=false`, `test_labels_used_for_fit=false`,
`leakage_audit_present=false`, `leakage_control_passed=false`, and
`claim_safe=false` remain invariant.

`betelgeuze_engine_v2.benchmark.public_posebusters_external_ranking_evaluation`
provides the actual descriptive external-reference evaluation layer. The
installed
`betelgeuze-engine-v2-posebusters-external-ranking-evaluate` command exposes
`materialize` and `verify` modes and accepts only the exact caller-pinned
test-partition receipt. It never accepts a fit partition.

The evaluator freezes source execution sort policies before reading labels:
`vina.total` is minimized, `gnina.cnn_pose_score` is maximized, and
`smina.minimized_affinity_kcal_per_mol` is minimized. Every scored case must be
monotonic in that policy's ordering score. Top-K is tie-inclusive. Ratio
metrics use 95% Wilson intervals; pose-level average precision treats equal
scores as one threshold and uses 2,000 deterministic case-cluster bootstrap
replicates. Point average precision is conditional on successful labeled poses,
so the receipt always binds it to all-case coverage and failure counts.

The production result retains all 308 cases per engine and all 872 failure
observations. Vina/GNINA/Smina score 18/17/17 cases and 355/340/336 poses.
Their all-case Top-1/Top-5 counts are 10/16, 15/16, and 10/15. Average
precision is 0.287330 (95% bootstrap CI 0.174209–0.512214), 0.668157
(0.534293–0.886705), and 0.304352 (0.183486–0.541608). Source-bound
physical-validity counts are 325/355, 304/340, and 312/336. The receipt also
records 296 complete observed-sequence proxy strata, 150 exact-Pfam-set or
missing groups, and 200 overlapping Pfam or missing groups. The sequence
projection is not a biological family, Pfam is missing for 83/308 cases, and
multi-label Pfam memberships are not disjoint.

Production receipt payload/file SHA-256 values are
`509556b0bcd9ec35f9ff4b1860613f267b2a96d73b18de44b61288498a838137`
and `3f4965ba07be36c6233514d2545c1db0f604bc4245552be2180bcdb780a43dc1`.
The deterministic installed wheel identified above reconstructed the
test-partition and evaluation receipts exactly outside the checkout.
`score_policy_fit_performed=false`,
`test_labels_used_to_select_score_policy=false`,
`external_model_training_leakage_audit_present=false`,
`independent_external_rerun_present=false`,
`scientifically_validated=false`, `public_docking_claim_authorized=false`, and
`claim_safe=false` are invariant. This external result is not an evaluation of
the internal scorer and is not complete public docking evidence.

`betelgeuze_engine_v2.benchmark.public_posebusters_internal_diagnostic_ranking_evaluation`
provides the corresponding internal test-diagnostic layer. The installed
`betelgeuze-engine-v2-posebusters-internal-diagnostic-ranking` command exposes
`materialize` and `verify` modes. It caller-pins the test-partition,
pose/scaffold, preparation, and three execution receipt chains; requires the
preparation-matched RDKit 2025.09.6 distribution and NumPy 1.26.4; and computes
every pose score before joining any test label. The frozen unit-weight minimize
policy retains `uff_receptor_ligand_vdw`,
`pdbqt_receptor_ligand_coulomb`,
`rdkit_uff_source_atom_strain_delta`, and `uff_vdw_overlap_penalty`.

The production result scored every source-success pose—355 Vina, 340 GNINA,
and 336 Smina—with zero scorer failures, while preserving the 290/291/291
upstream failures and all 308 cases per engine. All-case Top-1/Top-5 counts are
2/5, 3/5, and 3/3. Successful-pose average precision is 0.113931
(95% case-cluster bootstrap CI 0.056090–0.270781), 0.169927
(0.100789–0.262457), and 0.106265 (0.064622–0.224549). Production receipt
payload/file SHA-256 values are
`63a2f62cd465438f83e177b11ffd50483a2ff3f94c9399c308da2e8baee45b57`
and `4e4acd968e2a32f4f6ff47b8412b9209b5afe6918bda2019fdc4e9e492a4f3b1`.
The deterministic installed wheel identified above reconstructed this receipt
exactly outside the checkout.
`score_policy_fit_performed=false`,
`test_labels_used_for_score_computation=false`,
`test_labels_used_for_fit=false`, `scientifically_validated=false`, and
`claim_safe=false` are invariant. The lower average precision than the external
source policies is evidence against promotion, not permission to tune on this
test set. A disjoint fit/validation corpus and target/ligand/scaffold leakage
audit are required first.

`betelgeuze_engine_v2.benchmark.public_posebusters_external_ranking_reproduction`
provides the preregistered external-host rerun boundary. The installed
`betelgeuze-engine-v2-posebusters-external-ranking-reproduce` command exposes
`materialize-work-order`, `verify-work-order`, `materialize-result`, and
`verify-result`. Every mode requires caller-pinned baseline evaluation,
test-partition, ranking-intake, and exact Engine v2 wheel roots.

The work order is non-executing. It binds the exact baseline chain, the wheel
bytes and four source members, distinct baseline/external host identities,
role-separated work-order/execution operator identities, a single-use nonce,
and a canonical registration time. The result additionally requires a
post-registration observation time and an external chain reconstructed with
the same archive-intake, strict external-preparation, and RCSB/Pfam roots. Its
ranking-intake, test-partition, evaluation, and all six engine
execution/evaluation receipt and file roots must differ from baseline.

The comparison retains all 924 engine/case rows and checks failed dispositions,
pose counts, source-rank and native-like-label sequences, tie-inclusive Top-K
outcomes, fixed-policy score tolerances, ratio-metric counts, average precision
and confidence intervals, sequence-proxy/Pfam family scopes, and source-bound
physical-validity counts. A copied baseline chain, changed fixed input, or
score drift fails closed. Runtime fields are evidence projections rather than
proof of a unique physical machine. Consequently even a numerically passing
unreviewed result retains `physical_host_independence_reviewed=false`,
`independent_external_rerun_present=false`,
`independent_reviewer_receipt_approved=false`, and `claim_safe=false`. No
production work order/result currently exists because real external
host/operator identities and custody evidence have not been supplied.

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
and bit-exact restart. The offline
`openmm_reference_nve_trajectory` API and installed
`betelgeuze-engine-v2-openmm-nve-trajectory` command freeze and execute a
two-case, 16-step same-input OpenMM Reference comparison. It independently maps
the shifted real, pair-correction, half-lattice reciprocal, self, bonded, and LJ
terms; uses OpenMM's documented velocity-Verlet/RATTLE `CustomIntegrator`;
retains every state, same-coordinate energy/force error, constraint residual,
drift, Engine exact restart, OpenMM native-checkpoint restart, and all three
failure dispositions; and re-executes the complete observation during
verification. Configuration SHA-256 is
`2beca32683c0393666cc1c3b5a136bed3416f774b0db631133a04bb43928871e`.
This is a single-host claim-closed implementation comparison only. General
solute constraint/mass assignment, accepted long-time drift or
Ewald-convergence evidence, broad chemistry/explicit-solvent comparison,
cross-host reproduction, PME, net-charge background, independently accepted
thermostat/barostat and NVT/NPT statistics, triclinic cells, GPU parity, and all
scientific/product/customer promotion remain unavailable.

The separate
`openmm_reference_explicit_solvent_trajectory` API and installed
`betelgeuze-engine-v2-openmm-explicit-solvent-trajectory` command bind the
deterministic TIP3P/Na+/Cl- materializer to three exact 12 Å systems: a neutral
solute with two waters, the same system with NaCl, and a +1 solute with a Cl
counterion. It retains all four nominal constrained-NVE steps, both restart
paths, complete same-coordinate energy/force and constraint metrics, an
equal-horizon three-timestep ladder on the salted case, direct-Ewald reciprocal
bounds 2/3/4 at identical coordinates, and four materialization/oracle failure
rows. Configuration SHA-256 is
`e40902895938a4d7848e5207d0fe29de1ecaa43ae600c9c9ed8f7b7d0ac6c1b5`.
The single-host candidate observation
`d510c9c65625c00f7bd14c134c72e1ed5dab004764efc60c7fd96a9dae223157`
(file SHA-256
`d1425d77a1457e05b596597139e4c7c76bfb6357f066e0f7c37cf5f919c96810`)
does not pass the physical protocol: all three rows retain an OpenMM Reference
SETTLE position residual near `4.67e-8 Å` against the frozen `1e-9 Å`
threshold; two rows also retain exact charged-pair cutoff-equality force and
velocity failures. Both implementations pass the bound-3 versus bound-4 Ewald
absolute and monotonic checks, while the Engine timestep coordinate monotonic
row remains failed at a `1.44e-11 Å` roundoff-scale error. The receipt records
all dispositions but never reclassifies them as passes. It is rejected
diagnostic evidence, not accepted explicit-solvent, liquid-property,
long-time-drift, Ewald/PME, scientific, product, customer, or P2 evidence.

The separate `openmm_force_double_rattle_oracle` module deliberately imports
only the standard library. The installed
`betelgeuze-engine-v2-openmm-force-double-rattle-trajectory` adapter supplies
static forces from the pinned OpenMM Reference mapping while the oracle applies
sequential binary64 previous-constrained-vector SHAKE and projected-current-
vector RATTLE. The frozen development configuration
`ba2c1e99183cc124bb664745dfd1b4cbabbd2d4328cc35754e9e4da044606007`
binds three fresh 13.5 Å four-water/ion systems, nonzero deterministic
velocities, a `0.25 Å` minimum cutoff margin at every retained frame, 16 steps,
both restart paths, and six failure rows. Candidate observation
`cd0b849e206124e11996581c81dcc13da9d11ee3caa1c8176b5525dfead271a6`
(file SHA-256
`733af591c5366670a1aba79581648f064b8dccbd50d87b2080d139eb018329f0`)
passes 3/3 physical and 6/6 failure rows. Its metrics were selected after
exploratory implementation work. Two builds were byte-identical at wheel
SHA-256
`32e5784ed210f9a62de015a71c18c3fe302f897761b4d740563afb04e9352cab`,
and installed-wheel verification reproduced the receipt. Its lattice is
unequilibrated, and its oracle is internally maintained rather than an
independent external integrator. It is therefore claim-closed development
evidence. A fresh holdout, two-host
reproduction, independent review, long-time drift, liquid/ion observables,
PME, CPU/GPU parity, and scientific/product/P2 gates remain open; the rejected
SETTLE receipt is preserved and not superseded.

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
The current source/dependency lineage is applicability record `1.2.0`
`cfc9d2a5f9ff4ee2539c3e15a8c0519788e26c447a71de4e994c53d4f78760a6`,
energy/force protocol `1.2.0`
`0e34905c635b33b47a26cb459a93840166fc222c663d73af43d40d36814d7ee2`,
and artifact binding `1.2.0`
`b3341f3b98e29594cfcd727353553efa466116f275f5250c4ae944d624ef62b0`.
Those identities are not production evidence.

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
