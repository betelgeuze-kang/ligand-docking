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
betelgeuze_engine_v2.physics.validation_runtime_integrity_contract
betelgeuze_engine_v2.physics.validation_source_identity
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
the leaf review artifact and caller-provided result-reviewer key. The upstream
scientific-review and authorization artifacts remain symmetric-HMAC records, so
the leaf does not make that chain asymmetric. It also does not independently
reverify the live dependency manifest or establish external custody. No
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
initializer the inner stage verifies the authorization operator HMAC against
the external root-owned trust store, requires reservation and artifact roots
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
its upstream review/authorization chain remains symmetric HMAC. Remaining cooperative budget is rechecked
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
and logical plus raw revocation/supersession state. The energy-force upstream
review/authorization remains symmetric HMAC, the supplied process identity digest
is not external process authenticity, and neither carriers, events, keys nor an
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

`reference_minimization_validation_trajectory_comparison` freezes exact
evaluation-index/iteration/trial/outcome alignment, coordinate and energy
max/RMS thresholds, branch/rejection/count dispositions, expected-failure
non-comparability, and uninterrupted/paused/resumed digest equality for three
checkpoint cases. The runner, writer, and result-review verifier recompute the
canonical comparison and fail closed on omission, reorder, cross-wire,
non-finite values, or digest tamper. Its production, S0, scientific, and S1
flags remain false.

Runtime-integrity companion v12 binds the exact frozen SHA-256 of the refrozen
minimization trajectory-comparison contract, custody-v1,
the review/authorization extension, the sequence-5 reservation companion, the
external registry-proof verifier, the authenticated head/status receipt
verifier, the same-epoch later-head consistency verifier, the fixed-policy
anchor-scoped witness-quorum verifier, and the
process-launch-identity contract. Runtime v8 through v11 are retained only in
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

The active energy-force base carrier chain uses v2 identities with a v4 runner
and result writer. The active minimization base chain uses v4 review and
execution-environment identities, v5 authorization, result-receipt,
nonce-reservation, and run-start identities, a v8 runner, and v7 result
writer/result review. Current hashes are frozen over the
complete upstream contract DAG. The read-only legacy-contract verifier
recognizes 63 superseded contract documents by canonical projection hash and
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
