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
betelgeuze_engine_v2.physics.reference_minimization_validation_materializer
betelgeuze_engine_v2.physics.reference_minimization_validation_protocol
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
