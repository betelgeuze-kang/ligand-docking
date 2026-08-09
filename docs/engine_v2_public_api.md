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
betelgeuze_engine_v2.benchmark
betelgeuze_engine_v2.physics.registry
betelgeuze_engine_v2.physics.reference_parameter_applicability
betelgeuze_engine_v2.physics.reference_diagnostics
betelgeuze_engine_v2.physics.reference_constrained_minimization
betelgeuze_engine_v2.physics.reference_forcefield_v2
betelgeuze_engine_v2.physics.reference_minimization
betelgeuze_engine_v2.physics.reference_minimization_independent_oracle
betelgeuze_engine_v2.physics.reference_minimization_validation_artifact_binding
betelgeuze_engine_v2.physics.reference_minimization_validation_materializer
betelgeuze_engine_v2.physics.reference_minimization_validation_protocol
betelgeuze_engine_v2.physics.reference_minimization_validation_review
betelgeuze_engine_v2.physics.reference_minimization_validation_receipts
betelgeuze_engine_v2.physics.reference_minimization_validation_authorization
betelgeuze_engine_v2.physics.reference_minimization_validation_nonce_reservation
betelgeuze_engine_v2.physics.reference_minimization_validation_run_start
betelgeuze_engine_v2.physics.reference_minimization_validation_runner
betelgeuze_engine_v2.physics.reference_minimization_validation_result_writer
betelgeuze_engine_v2.physics.reference_solvation
betelgeuze_engine_v2.physics.reference_validation_protocol
betelgeuze_engine_v2.physics.reference_validation_materializer
betelgeuze_engine_v2.physics.reference_validation_oracle
betelgeuze_engine_v2.physics.reference_validation_artifact_binding
betelgeuze_engine_v2.physics.reference_validation_review
betelgeuze_engine_v2.physics.reference_validation_authorization
betelgeuze_engine_v2.physics.reference_validation_nonce_reservation
betelgeuze_engine_v2.physics.reference_validation_run_start
betelgeuze_engine_v2.physics.reference_validation_runner
betelgeuze_engine_v2.physics.reference_validation_receipts
betelgeuze_engine_v2.physics.reference_validation_result_writer
betelgeuze_engine_v2.runtime
```

The frozen public-benchmark protocol symbols under
`betelgeuze_engine_v2.benchmark` define input identities, endpoint rules, and a
failure-inclusive reporting contract only. They do not authorize data fetch,
benchmark execution, result publication, or scientific promotion.

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
bounds; a failure-inclusive observation ledger; and canonical binary64
checkpoints that bind source-system, topology, parameter, and configuration
identities. Restart re-evaluates the stored state before continuation. These
provisional symbols do not ship or assign parameters, establish chemical
applicability, validate minimization accuracy, satisfy the frozen independent
validation protocol, or enable a scientific/product/customer route.

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
topology, v2 parameters, configuration, observations, and binary64 coordinates
into exact checkpoints. The constraint path does not use atomic masses.
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
arguments. The library does not create a network namespace or establish
same-UID replacement resistance. No trusted key, attestation, root, or
production receipt is bundled, and a verified receipt authorizes neither a
production run nor validation, fitting, or a scientific claim.

The minimization bounded-runner symbols re-read and live-reverify that receipt,
bind the stdlib-only bootstrap and runner sources, require the signed clean Git
checkout and exact dependency identities, validate the frozen materialization
manifest before consuming a nonce-bound mode-0600 start marker, and retain all
fourteen ordered pass and fail-closed case observations in memory. The runner
records predefined metric values, independent-oracle comparisons, and exact
checkpoint/restart equality under a 120-second budget. It writes no validation
result receipt itself. The separate result-writer symbols re-verify the signed
chain, persisted/live environment, durable runner-start marker, and canonical
observation before private atomic persistence. The receipt is unsigned and
pending independent result review, and the direct process entrypoint remains
fail-closed until bootstrap integration exists.

The bounded-runner symbols re-read and live-reverify the environment receipt,
require exact code, runner-source, dependency, and frozen-artifact identities,
require a source-only stdlib bootstrap launched with `-I -S -B -X
pycache_prefix=/dev/null` before any validation dependency import, reject Git
replacement refs, and atomically consume one nonce-bound mode-0600 runner-start
marker. The bootstrap ignores `PYTHONPATH` and user-site overrides, skips
`sitecustomize`/`.pth` execution, admits only root-owned read-only dependency
roots, and binds both bootstrap and runner sources into the signed runner-source
identity. Before importing the package initializer it bounds and canonicalizes
stdin, verifies the authorization operator HMAC against the external root-owned
trust store, requires reservation and artifact roots outside the checkout, and
uses root-owned Git to prove the exact signed commit, execution-source identity,
and clean worktree. Frozen manifest construction and
the exact 27-case/59-variant CPU float64 evaluation run in fixed supervised child
processes with automatic site initialization disabled and only the verified
runtime's dependency roots supplied. Remaining budget is rechecked before the
start marker is consumed, and a parent hard deadline can terminate
blocked native code. The result
is a canonical in-memory observation that retains
successes, expected failures, unexpected failures, missing metrics, and failed
thresholds. The exact process entrypoint is the absolute checked-out
`reference_validation_bootstrap.py` path under those frozen Python flags; it
accepts one bounded canonical stdin request, loads trust anchors only from the
fixed external root-owned store, and never sends trust material to either
worker. It exposes no marker release/delete
API. Test-only artifacts can exercise this implementation; no production key,
receipt, start, result, validation
acceptance, fitting, or claim promotion is bundled.

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
durable runner-start marker, and exact code/source/dependency identities. They
atomically persist one canonical mode-0600 nonce-bound receipt while retaining
every failed case, variant, and metric. Reading verifies canonical JSON and the
embedded digest; acceptance additionally requires an out-of-band expected
receipt SHA-256 and current external revocation/supersession inputs. The receipt
is unsigned, private POSIX storage is not external authenticity, same-UID
replacement resistance is not established, and result review remains
`pending_independent_review`. No production receipt or scientific promotion is
bundled.

Their schema IDs and serialized receipts are versioned, but Python convenience
signatures may change before the distribution reaches `1.0.0`. Callers should
pin the distribution version and validate schema IDs.

The provisional docking authority supports ordinary ring-containing ligands
only as rigid ring systems. Its derivation receipt records ring bonds, rigid
ring-system atom sets, the largest ring-system atom count, and the largest
detected shortest cycle. A connected ring system with 12 or more atoms fails
closed conservatively, including ambiguous fused or bridged systems whose
shorter cycles could hide an unsupported macrocycle. This is not yet
chemistry-complete rotor perception, ring-closure sampling, or ring-conformer
sampling.

The `3.0.0` torsion derivation receipt records one canonical disposition for
every ligand bond. Its bounded chemistry-aware rotor rules explicitly exclude
amide, urea, carbamate, sulfonamide, conjugated, ring, aromatic, non-single,
hydrogen, terminal-heavy-atom, and stereo-constrained bonds. This deterministic
graph profile records the full torsion-tree parent array and checks every
rotatable child against its exact parent bond. Both double-bonded and
charge-separated sulfonamide resonance forms are recognized. The profile is
auditable from the receipt but is not a claim of equivalence to a complete
external cheminformatics toolkit or scientific validation.

`prepare_deterministic_conformer_ensemble(...)` is a capability-gated
preparation API. When RDKit is available, it uses one-thread ETKDGv3 with an
explicit seed, MMFF94 or UFF energy optimization, an energy window, and greedy
heavy-atom Kabsch-RMSD diversity selection. The returned multi-model
`AllAtomSystem` is cross-wired to stable conformer IDs and an immutable
prepared-state receipt containing the exact configuration, RDKit version,
candidate denominators, optimization rows, energy model, and output hashes.
Missing RDKit, invalid SMILES, unsupported large ring systems, embedding
failure, unavailable energy parameters, multiple components, oversized
topologies, or potential unassigned atom/bond stereochemistry fail closed. The
canonical isomeric SMILES is reparsed before atom indexing. Complete conformer
record projections are receipt-bound and cross-checked against each selected
coordinate model, energy row, identity, and RMSD value. A dedicated pinned
RDKit CI job executes this capability. The diversity metric is not
symmetry-aware and the ensemble is not scientifically validated.

`build_guided_placement_context(...)`,
`generate_guided_docking_proposals(...)`, and
`run_authenticated_guided_placement_search(...)` provide a provisional,
deterministic known-pocket proposal layer. The context derives bounded
donor/acceptor, formal-charge, connected hydrophobic-patch, aromatic-plane, and
principal-shape features only from the authenticated receptor subset and ligand
graph. A fixed fraction of the existing pocket-centered uniform batch is
replaced by guided
proposals; every multi-candidate guided batch retains at least one byte-identical
uniform fallback proposal, and unavailable guidance leaves the entire baseline
batch unchanged. Immutable receipts bind the input authority, system hashes,
receptor subset, feature context, policy, budget, per-proposal modes, feature
counts, and proposal fingerprints to the failure-complete authenticated search.
Proposal generation and search require the bound receptor and ligand systems
and rederive the context before accepting a caller-provided context, so a
self-consistent but fabricated feature projection fails closed. Receptor
feature perception keeps only a pocket-local two-hop adjacency and fails closed
before scanning more than the exported receptor-bond hard bound. A guided mode
whose sampled conformer geometry is degenerate falls back for that candidate
without discarding the rest of the batch.
These features and placements are auditable heuristics, not validated
pharmacophore perception, docking accuracy, ranking evidence, or a product
claim.

`ChemistryPoseScorerV1(...)` (also exported as `PoseScorerV1`) requires the
element-aware authority plus the exact bound receptor and ligand systems. It
fails closed unless every explicit atom has a finite partial charge and each
system's partial charges reproduce its formal total charge. `score_terms(...)`
returns an immutable `ScorerV1Terms` receipt containing separate typed-vdW,
electrostatic, directional hydrogen-bond, hydrophobic-contact,
desolvation-proxy, torsion-energy, ligand-strain, and weak-pocket-prior terms.
The periodic torsion term is derived from the final pose coordinates relative
to the authenticated prepared ligand, so coordinate refinement cannot leave it
bound to stale sampled-angle metadata. Configured pair cutoffs must cover the
enabled hydrogen-bond and polar-burial ranges.
`run_authenticated_scorer_v1_guided_search(...)` combines this scorer with the
guided proposal layer and binds every successful term receipt to its exact
generic search row, revalidates the decomposition against the active scorer,
and retains failed candidates in the denominator.
Scorer v1 is deterministic and uncalibrated; it is not validated for docking
ranking and does not report physical energy, binding affinity, or free energy.

`EnergyBasedLocalRefiner(...)` binds an authenticated docking problem, its exact
ligand system, a topology-matched `ReferenceForceFieldParameters` packet, and an
immutable `EnergyLocalRefinementConfig`. Its `refine(..., max_steps=...)` method
requires CPU float64 coordinates, uses the existing bounded CPU reference
minimizer, and returns a proposal whose
lineage names the exact `EnergyRefinementAttempt` receipt. The receipt retains
binary64 pre/post coordinates, initial/final/delta kcal/mol energy, maximum
atom displacement, convergence and evaluation counters, checkpoint identity,
the implementation source, immutable parameter fingerprint, effective
step/config identity, or a failure row without fabricated post state.
Contradictory minimizer status, convergence, and failure-code combinations fail
closed. It can be passed as the `refiner` in authenticated docking search.
`run_authenticated_energy_refined_scorer_v1_guided_search(...)` requires a
positive refinement-step budget and returns an
`EnergyRefinedGuidedSearchResult` that binds every generic and Scorer v1 search
row to its exact attempt. The full success/failure denominator is retained, and
proposal lineage, authority, configuration, parameter, and receipt cross-wires
fail closed.

This adapter relaxes ligand-internal coordinates only. It does not include
receptor--ligand interaction energy, prove pose improvement, provide an
affinity/free-energy estimate, or establish scientific/product readiness.

`DockingPipeline()` is the provisional standalone CPU composition boundary for
canonical, already-prepared receptor and ligand inputs plus an explicit typed
pocket. Every `DockingPipelineRequestV1` must carry both the exact exported
`SYNTHETIC_ONLY_ACKNOWLEDGMENT` and the package-owned
`SyntheticD0FixtureAdmissionV1`. The loader authenticates the canonical
manifest bytes and fixes the receptor/ligand canonical SHA-256 values, pocket
fingerprint, seed, profile ID and receipt, request SHA-256, fixed-64 denominator,
and Top-5. Construction and `run()` independently recheck that admission before
any component or scorer call. Arbitrary coordinates, pockets, seeds, and
profiles therefore fail before computation. This repository-fixture identity
check is not external execution authority, scientific admission, or a molecular
experiment authorization. The admitted profile binds the current V7,
Scorer-v1, full fixed-64/Top-5 budget and proposal-plan receipts.

The no-argument pipeline seals the exact canonical component types and IDs.
The public constructor rejects supplied dependencies before execution. The
underscore-prefixed internal test factory is the only dependency-injected path;
its result records `internal_test_only_unverified_components`,
`arbitrary_dependency_injection_unverified`, and
`unverified_component_side_effects_unknown`. Network, reservation, chemistry,
and pocket-prediction observations are `null`, rather than falsely asserted
absent, for that path. Its component IDs are fixed to `UNVERIFIED`, and its
scorer/refiner implementation source identities are `null`; caller component
labels cannot become receipt evidence.

The evidence recorder is private, non-exported, and not dependency-injectable.
Each `run()` rederives package source hashes, evidence-safe component IDs, and
the sealed-or-unverified binding internally. It then issues one opaque,
process-local capability bound to the exact request, budget, proposal plan,
Scorer-v1 result object and receipt, refiner receipts, admission statuses, and
Top-K. The private recorder consumes that capability before validation and
cannot reuse it after success or failure. Its record method accepts no caller
source hashes, component IDs, or binding mode. Direct calls, replay, and
cross-run result substitution therefore fail closed without minting a result.

Candidate receipts
deep-canonicalize nested evidence and enforce disjoint success/failure states;
result receipts independently rederive the exact stable MINIMIZE Top-K and
reject missing, reordered, duplicate, out-of-range, failed, or ineligible
references. Candidate and result objects also carry a process-local HMAC
construction proof that only the canonical recorder creates. The proof is
rechecked whenever a receipt is read, so a format-valid `dataclasses.replace`
cannot substitute lineage, component binding, or nested receipt content. The
proof and key are never serialized; the serialized `receipt_sha256` remains a
deterministic structural self-hash, not a signature, cryptographic attestation,
or cross-process trust proof. These process-local controls protect the supported
API against accidental minting, replay, and ordinary cross-wiring; they are not
a security boundary against hostile same-process reflection, private-name
access, memory inspection, monkeypatching, or arbitrary code execution.
`DockingPipelineResultV1` retains all candidate
failures, complete
successful score-term/validity/refinement evidence, all required claim blockers,
and false Historical, Fresh, Stage 0, product, customer-pose, and
public/scientific authorities. The pass-through geometric-admission component
records that the future surface-aware gate is not enabled and never removes a
candidate.

The component boundary performs no file parsing, protonation, tautomer
selection, charge generation, pocket prediction, external reservation,
benchmark evaluation, or product action. It does not authorize or independently
admit real molecular execution. Only the exact repository-owned synthetic D0
fixture can reach the current scorer, and that admission keeps reservation,
Historical A/B, Fresh-128, public benchmark, product mutation, and all external
claim authorities false.

The provisional `betelgeuze-dock` console entry point exposes the same core as
six file-oriented commands:

```text
betelgeuze-dock prepare-receptor --input SYSTEM --output SYSTEM
betelgeuze-dock prepare-ligands --input SYSTEM [--input SYSTEM ...] --output-dir BUNDLE
betelgeuze-dock define-pocket ... --output POCKET
betelgeuze-dock dock --receptor SYSTEM --ligand SYSTEM --pocket POCKET --seed INTEGER --output RESULT
betelgeuze-dock verify --result RESULT --output VERIFICATION
betelgeuze-dock report --result RESULT --output REPORT
```

`prepare-ligands` publishes an absent-only directory containing fixed
`manifest.json` plus content-addressed canonical ligand files. It builds and
synchronizes a private sibling staging directory, atomically renames the whole
bundle without clobbering, and synchronizes the parent directory. It has no
manifest-path or overwrite option. All standalone output writers reject parent
symlink traversal, special files, multiple hard links, input/output aliases,
and detected replacement races. The hardened publication path is Linux-specific
and fails closed when no-follow directory descriptors, `/proc/self/fd`, or
`renameat2` semantics are unavailable. It pins and rechecks source and
destination inode identities. A detected overwrite race aborts, and rollback is
attempted only while an exact operation-owned inode remains at one exchange
endpoint; arbitrary same-UID mutation can still prevent confirmed restoration.
The writer is therefore not a security boundary against another process running
as the same UID with access to the writable parent or this process's descriptors;
deployment still requires process/account isolation.
Argument-admission failures use the same single canonical failure JSON as
runtime failures.

`verify` checks exact serialized keys, embedded self-hashes, available receipt
cross-bindings, denominator preservation, score-term decomposition, stable
Top-K semantics, and false authority fields. Its normalized output is explicitly
`verified_structural_consistency_only`: it verifies neither a cryptographic
signature nor content authenticity, pre-import source attestation, external
authority, or execution authorization. The receipt deliberately exposes
`structural_consistency_valid`, not a generic `valid` field, so consumers cannot
mistake this narrow result for content or scientific validity. `report` consumes
that normalized verification and remains claim-blocked. Synthetic denominators require the
paired `--synthetic-test-candidates` and `--test-only-synthetic` acknowledgment;
orphan synthetic flags fail closed.

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
