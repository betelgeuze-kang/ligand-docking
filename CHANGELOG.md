# Changelog

This changelog tracks the independent `betelgeuze-engine-v2` distribution. The
legacy/product monorepo has separate operational evidence and does not inherit a
scientific claim from a package version.

## 0.2.0rc2 — Runtime identity release candidate

### Added

- A bounded deterministic CPU `float64` explicit-solvent preparation bound to
  an exact OpenMM Force Fields Amber TIP3P/Joung--Cheatham Na+/Cl- source
  snapshot. It materializes water/ion atoms and residues, water bonds and
  angles, nonbonded parameters, intrawater exclusions, rigid-water
  SHAKE/RATTLE constraints, full orthorhombic PBC, exact neutralization,
  species molarity, clearance diagnostics, and a canonical placement trace.
  Neutral and counterion cases execute through direct Ewald, constrained NVE,
  and bit-exact checkpoint/restart. The deterministic lattice is not minimized
  or equilibrated, and source transcription, energy/force parity, liquid/ion
  observables, two-host reproduction, and every scientific/product claim
  remain unvalidated.
- A bounded deterministic CPU `float64` velocity-Verlet NVE reference path
  using explicit atom masses and caller-bound parameters. It rebuilds compact
  neighbors at every force evaluation, supports non-periodic or full 3D
  orthorhombic PBC with per-step wrapping, and optionally applies canonical-pair
  inverse-mass SHAKE position corrections plus RATTLE radial-velocity
  projection. Binary64 frames and canonical checkpoints bind constraint
  configuration, residual maxima, cumulative iterations, and bit-exact
  same-runtime restart. An optional neutral orthorhombic direct-Ewald mode now
  exactly replaces the frozen v1 screened-Coulomb energy/force with bounded
  shifted-real, reciprocal, self, and exclusion/1-4 correction components and
  binds its canonical config into restart identity. Constraint/mass assignment,
  scientific drift or Ewald-convergence acceptance, independent
  SHAKE/RATTLE/Ewald and cross-host reproduction, PME, net-charge background,
  thermostat/barostat, triclinic-cell,
  NVT/NPT-statistics, GPU-parity, and product claims remain blocked.
- A bounded all-step NVE drift analyzer requiring a fresh `trajectory_stride=1`
  run and a genuine pause/resume execution. It retains energy, raw kinetic
  temperature, linear momentum, current constraint residuals, and exact
  frame/coordinate/velocity identities; reports max/RMS energy and momentum
  drift plus energy-drift slope; and preserves all nine caller-predeclared
  metric rows including exact-restart and failure rows. A local numerical pass
  is not independently reviewed drift evidence or scientific promotion.
- A fit-only pose-ranking calibration contract with canonical success/failure
  rows, exact receptor/ligand/scaffold/pose identities, configurable target and
  family overlap rejection, deterministic CPU `float64` pairwise-logistic term
  fitting, and a non-promoted scorer wrapper. Held-out evaluation preserves
  failed poses and reports Top-1, Top-5, and scored-case coverage against the
  all-case denominator, both overall and per target family, with deterministic
  bootstrap intervals. No public dataset, fitted model, result, independent
  rerun, or scientific/product claim is bundled.
- Candidate-level docking score decomposition with canonical term IDs, raw
  values, weights, contributions, units, parameter-source digests, and
  failure-row preservation. A new explicitly uncalibrated CPU `float64`
  reference scorer consumes caller-bound force-field parameters and separates
  receptor--ligand Lennard-Jones, screened Coulomb, signed ligand internal
  strain delta, and VDW-overlap penalty terms. Its frozen chemistry admission
  profile supports H/C/N/O/F/P/S/Cl/Br/I with exact partial-charge binding,
  abstains on metals and receptor cofactors, and leaves pose-ranking
  calibration, public evidence, aromatic-specific physics, stereo validity,
  and all product/scientific claims blocked.
- A verifier-only adjacent registry-epoch transition contract that freshly
  re-verifies the previous fixed-policy witness-quorum proof, requires exact
  epoch-ordinal adjacency and unchanged terminal-root carry-forward into a
  derived sequence-zero genesis checkpoint, and verifies disjoint previous and
  next Ed25519 quorums over one exact transition statement. It deliberately
  leaves successor uniqueness, external witness locking, independent journal
  agreement, realm-wide non-equivocation, and all production/scientific claims
  false; no transition proof, policy, or key is bundled.
- A standard-library-only runtime byte-identity materializer for the active
  Python executable and standard library, the root-owned OpenSSL executable,
  and every `RECORD`-declared cryptography, NumPy, and Torch distribution
  payload. The isolated bootstrap measures these bytes before package or
  third-party imports; run-start and the bounded runner remeasure the exact six
  signed rows before evaluation.
- Explicit result-receipt semantics that distinguish content-mutation detection
  through a required out-of-band SHA-256 from same-UID pathname/inode
  replacement resistance, which remains unestablished without privileged or
  immutable storage.
- Sensitive-path CODEOWNERS coverage and a documented branch-protection review
  policy for independent human approval and unresolved-thread closure.
- Authorization builders now round-trip their newly signed receipt through the
  public verifier before returning it, rejecting invalid lifetime, identity,
  dependency, or signature combinations at construction time.
- The exact fourteen-case minimization process entrypoint now binds signed
  nonce, implementation-author, source, and dependency identities before
  package import; reloads Ed25519 reviewer/operator anchors only from a fixed
  external root-owned mode-0600 trust store; rechecks source, dependencies, and
  deterministic single-thread Torch state inside the spawned evaluator; and
  finalizes the failure-inclusive result receipt before returning a hash-only,
  closed-claim response. No production trust store or signed run is bundled.
- Both synthetic entrypoints now use a root-owned isolated outer launcher only
  to validate and sanitize startup, then re-exec the same interpreter as a
  source-bound, no-site controlled inner process so canonical uint32
  `PYTHONHASHSEED` is applied during interpreter initialization. The 27/59 and
  14-case workers receive environment and application/hash seeds only from the
  verified execution receipt, recheck exact argv, cwd, flags, environment, and
  a parent/child hash probe, and no longer copy mutable live supervisor state.
- Complete ordered CPU `float64` minimization coordinate traces now flow from
  operational checkpoints and the independent oracle through the bounded runner
  into the result-writer receipt. Every evaluation retains canonical binary64
  raw/evaluated coordinates, source/case/evaluation identity, coordinate and
  step digests, a whole-trace digest, exact accepted/rejected/evaluation counts,
  and accepted-energy-ledger consistency. Expected pre-evaluation failures use
  an explicit canonical empty trace.
- A frozen minimization trajectory-comparison contract now aligns operational
  and independent evaluations by exact index, iteration, trial, and outcome;
  applies the predefined `1e-8 Å` coordinate and `1e-10 kcal/mol` energy max/RMS
  limits; retains branch, rejection, count, and fail-closed non-comparability
  dispositions; and binds uninterrupted/paused/resumed digests for three
  checkpoint cases. Runner, writer, and independent result review recompute the
  canonical evidence and reject omission, reorder, cross-wire, non-finite
  values, and digest tamper. The refrozen v2.1 protocol uses half of the declared
  constraint tolerance as internal projection convergence headroom without
  changing the external acceptance threshold. The non-production implementation
  check passes all 14/14 comparison rows and all three restart-equality rows,
  including both fixed-Born rows, with no production or scientific promotion.
- A fail-closed Ed25519 minimization result-review contract that fully
  revalidates one exact result-writer receipt, derives accepted or rejected
  dispositions for all fourteen cases, every retained or missing metric, every
  ordered coordinate trace and step, and exact status, runtime/oracle/result
  identity, per-case count budgets, finite metric-consistent energy-ledger
  evidence, and recomputed coordinate/step/trace digests. It cryptographically
  reverifies the raw pre-execution review and authorization role chain, requires
  canonical byte transport and explicit current revocation/supersession inputs,
  and enforces an out-of-band public key plus four-way governance-role
  separation. No result-review attestation, production receipt, or scientific
  acceptance is bundled.
- A fail-closed Ed25519 energy-force result-review leaf that independently
  recomputes all required metric occurrences from retained raw energy/force
  arrays, records complete case/variant/metric/failure/worker dispositions, and
  enforces four-role separation without bundling a production receipt,
  attestation, independent approval, or scientific claim.
- A Linux process-launch identity measurement contract plus a frozen Ed25519
  production-evidence base for permit and status custody. An additive companion
  internally re-verifies that raw two-event prefix and implements claim-closed
  production-only review and authorization carriers as custody sequences three
  and four. No key, carrier/event, external chain, atomic permit consumption,
  successor uniqueness, execution authorization, or production result is
  provisioned.
- An additive sequence-5 reservation-custody companion that re-verifies the
  complete exact raw sequence-1-through-4 ancestry and lane-local reservation
  record, binds a custodian-signed intent to realm-global uniqueness slots and
  exact registry/witness authority material, and verifies dual signatures over
  a claimed commit plus a strictly newer post-commit status snapshot. The
  signatures are attestation evidence only: external serializable CAS, one-use
  slot consumption, non-equivocation, epoch continuity, and unique successor
  enforcement remain explicitly false. Exact-raw nonce-record verification is
  also public for both lanes without claiming independent proof of local
  exclusive-create or fsync history.
- A verifier-only external same-epoch reservation-registry proof contract. It
  freshly re-verifies sequence 5, validates 256-level sparse-Merkle
  transaction-tagged leaf updates for the permit, authorization nonce, and
  predecessor as one fixed-order adjacent-root chain, binds exact backend runtime
  identities, verifies separate backend and head-observer Ed25519 signatures and
  supplied freshly reverified status-lineage-tail denials, and requires the
  native checkpoint to equal a caller-supplied expectation. This verifies scoped
  backend-attestation, exact-transition, observer-signature, and caller-match
  facts only; it does not authenticate that expectation or a globally latest
  status head. Actual external CAS, global one-use consumption,
  non-equivocation, epoch continuity, status-head CAS, successor uniqueness,
  execution, and promotion remain false; no backend, proof, keys, or head is
  bundled, and no authenticated head receipt is present.
- A verifier-only authenticated external registry-head/status-tail receipt
  contract. It snapshots both nested reverification inputs, reproduces the same
  raw proof against the receipt-bound and strict post-receipt status lineages,
  verifies a role-separated Ed25519 authority signature over exact
  proof/sequence-5/head/status/service/time/challenge identities, and applies
  the later tail's revocation and supersession rows to the receipt itself and
  its trust/runtime dependencies. It verifies bounded authenticity, exact
  binding, and caller challenge equality only. Challenge freshness/one-use,
  global latest, CAS, global slot consumption, non-equivocation, later-head
  consistency, epoch continuity, execution, and promotion stay false; no
  receipt, authority key, challenge, or current-status descendant is bundled.
- A verifier-only same-epoch later-head consistency contract. It freshly
  re-verifies the authenticated anchor receipt, requires a bounded ordered path
  of adjacent backend-signed checkpoint/state-root transitions, verifies the
  existing independent head observer over the complete path, and reconstructs
  sparse-Merkle inclusion of the original permit, authorization-nonce, and
  predecessor-successor transaction-tagged consumed-leaf encodings in the
  caller-pinned later root. Proof issue cannot predate the anchor receipt, the
  signed later-head observation is observer countersign completion, and a status
  descendant issued after the proof supplies revocation and supersession denial.
  The DTO preserves false caller-challenge freshness/one-use and actual slot-
  consumption fields. This is one supplied fork only: sibling pins can each verify, so
  global latest, external non-equivocation, epoch continuity, CAS, execution,
  and promotion remain false; no proof, keys, or post-proof status is bundled.
- A verifier-only fixed-policy witness-quorum contract for one same-epoch exact
  anchor. It binds N/F/Q, an ordered full roster with distinct caller-pinned
  witness/operator/fault-domain identifiers, `2Q-N>F` and `2Q-N-F`
  intersection facts, a target-independent anchor fork
  scope, and Q Ed25519 votes over one exact descendant lineage. The complete N
  roster is validity- and denial-fenced. The resulting fact is conditional and
  anchor-scoped: the verifier does not observe the fault assumption, enforce
  exclusive voting, reconcile independent journals, or exclude hidden sibling
  certificates. Realm-wide non-equivocation, global latest, epoch continuity,
  execution, and promotion remain false; no external policy, keys, proof,
  journal, or post-quorum status is bundled.

### Changed

- The distribution version is `0.2.0rc2`, separating the runtime-byte-identity
  and Ed25519 trust boundary from the accumulated `0.2.0rc1` surface.
- Runtime-integrity contract v12 now additionally binds the refrozen minimization
  trajectory-comparison contract and the exact frozen custody-v1,
  review/authorization-extension, reservation-extension, external
  registry-proof-verifier, authenticated head/status-receipt verifier, and
  same-epoch later-head consistency verifier, fixed-policy anchor-scoped
  witness-quorum verifier, and process-launch-identity hashes
  while keeping
  provisioned external registry CAS,
  slot consumption, successor uniqueness, external process authenticity/custody,
  production execution/results, and every scientific/product promotion flag
  false. The v8 through v11 runtime documents are retained as read-only legacy
  identities; the dependent production custody/proof contracts are refrozen as
  v2 or v3 over the current minimization chain, and the legacy registry contains 63
  superseded documents.

### Scientific boundary

`0.2.0rc2` remains an internal CPU reference release candidate. Runtime byte
identity, signatures, packaging reproducibility, and governance policy do not
establish calibrated force-field accuracy, minimization validity, docking or
ranking validity, public benchmark performance, or customer readiness.

## 0.2.0rc1 — Release candidate

### Added

- Ed25519 public-key verification for minimization-validation review,
  authorization, and network-isolation attestations. Signing uses external raw
  32-byte private seeds while verifier trust anchors contain only raw public
  keys; the isolated stdlib bootstrap verifies the first authorization with a
  root-owned OpenSSL executable before importing package or third-party code.

- Failure-inclusive minimization-validation result writer and reader with raw
  signed-chain, live environment, runner-start, and canonical observation
  re-verification; atomic private nonce-bound persistence; exact external hash,
  revocation, and supersession checks; and no production result or claim
  promotion.

- Versioned all-atom contracts, canonical system/topology/coordinate identities,
  and provenance invalidation on coordinate changes.
- Bounded sparse neighbor geometry with periodic image-shift gradients.
- Scalar-energy AI reference primitives, matrix-free projection, torsion,
  temporal, and physics-gate contracts.
- Fail-closed CPU orchestration, strict runtime/checkpoint fingerprints, and an
  isolated wheel for Python 3.10–3.12.
- Bounded PDB and SDF V2000 ingest, canonical JSON round-trip, and strict writers.
- Docking problem/search-space/proposal identities, score semantics, pose
  metrics, pose-validity checks, and failure-complete bounded search ledgers.
- Typed benchmark metrics, stable case seeds, artifact verification, deterministic
  confidence intervals, and optional signed reports.
- Frozen four-case public redocking protocol identities, fixed-receptor-frame
  symmetry-aware RMSD/validity endpoints, scorer-source hashes, and
  failure-inclusive denominators without
  data bundling, benchmark execution, results, or scientific promotion.
- Explicit reference bond, angle, torsion, Lennard–Jones, and screened-Coulomb
  equations with autograd forces and fail-closed applicability contracts.
- Frozen H5 parameter-origin/runtime-envelope record with seven exact source
  hashes, caller-supplied value provenance, executable admission semantics, and
  explicit separation from the unparsed Sage candidate, scientific chemical
  applicability, parameter fitting, and force/energy validation.
- Frozen CPU reference energy/force contract-validation protocol with seven
  synthetic fixture profiles, twenty mutation contracts, twenty-seven
  failure-inclusive cases, nineteen predefined float64 metrics, exact H5
  dependency identity, independent-oracle/result-receipt requirements, and a
  closed validation-execution and parameter-fitting authorization gate.
- Exact CPU validation fixture materialization covering all seven fixtures,
  twenty mutations, twenty-seven cases, and fifty-nine deterministic runtime
  variants, plus a source-bound standard-library-only analytic oracle with
  forward-mode exact forces and an AST-enforced evaluator/protocol/third-party
  import boundary. No comparison result or scientific promotion is created.
- Frozen fourteen-case CPU minimization-validation inputs with an exact
  materializer and a separately source-bound standard-library reference for
  constraint/tangent-force projection, fixed-Born energy/forces, bounded
  backtracking, fail-closed identities, and checkpoint/restart. Test-only
  endpoint comparisons and complete coordinate-trace integrity checks are
  implementation evidence, not trajectory-level validation results or scientific
  promotion.
- Frozen independent-review attestation contract for the minimization artifacts,
  with exact source-binding identity, ordered technical checks and limitations,
  author/reviewer separation, out-of-band Ed25519 public-key trust, and a
  30-day maximum validity. No key, attestation, authorization, result, or claim
  promotion is bundled.
- Frozen CPU-only, network-disabled execution-environment and failure-inclusive
  result-receipt contracts for the exact fourteen-case minimization matrix and
  ten predefined metrics. Both implementation input identities, all failure
  rows, iteration/evaluation ledgers, and future review/authorization bindings
  are required; no authorization contract or receipt, environment/result
  receipt, runner, observed value, or claim promotion is bundled.
- Frozen Ed25519 single-run minimization-validation authorization contract
  binding a verified nonexpired review, pairwise-distinct author/reviewer/
  operator identities, exact code/runner/dependency and receipt-contract
  identities, a 24-hour maximum lifetime, external revocation sets, and a
  one-time nonce. No operator key, signed receipt, nonce reservation, execution,
  result, fitting authorization, or claim promotion is bundled.
- Local POSIX atomic one-time nonce reservation for minimization validation that
  re-verifies raw signed review and authorization artifacts before writing one
  canonical mode-0600 record beneath a caller-provisioned effective-UID-owned
  mode-0700 root with `O_EXCL`, `O_NOFOLLOW`, file `fsync`, and directory
  `fsync`. Duplicate/external nonce consumption fails closed and no release or
  delete API, production root, key, signed artifact, reservation, or execution
  is bundled.
- Fail-closed minimization-validation run-start re-verification that binds the
  raw signed review and authorization, durable nonce record, exact CPU-only
  deterministic runtime, a maximum-five-minute operator-signed network-
  isolation attestation, and one canonical mode-0600 secret-free environment
  receipt persisted with exclusive no-follow creation and file/directory
  `fsync`. No key, attestation, production root/receipt, bootstrap runner,
  execution, result, fitting authorization, or claim promotion is bundled.
- Frozen independent-review attestation contract binding the exact validation
  artifacts, ordered review checks and limitations, implementation-author and
  reviewer identity separation, out-of-band reviewer trust, HMAC-SHA256
  integrity, and a 30-day maximum validity window. No trusted key, attestation,
  execution authorization, validation result, or scientific promotion is
  bundled.
- Frozen single-run execution-authorization receipt contract binding a verified
  review to a pairwise-distinct operator identity, exact code/runner/environment/
  result/dependency hashes, HMAC-SHA256 integrity, a 24-hour maximum lifetime,
  external receipt/review revocation sets, and an unused one-time nonce. No
  operator key, receipt, reservation root, or production reservation is bundled,
  and execution remains disabled.
- Frozen CPU execution-environment and failure-inclusive result-receipt
  contracts binding the exact protocol, authorization, materialization, 27-case,
  59-variant, and 19-metric identities. No production receipt, durable production
  observed value, execution, or claim promotion is provided.
- Atomic local POSIX one-time authorization-nonce reservation with raw signed
  review and authorization re-verification, `O_EXCL` creation, file and
  directory `fsync`, private owner/mode checks, canonical tamper-evident records,
  concurrent duplicate rejection, and no release API. No key, receipt,
  reservation root, production reservation, execution, result, or claim
  promotion is bundled.
- Fail-closed run-start dependency and live execution-environment re-verification
  with exact review/authorization/reservation cross-checks, CPU-only deterministic
  runtime observation, a short-lived operator-signed network-isolation
  attestation, secret-free logical argv/path identities, and atomic mode-0600
  environment-receipt persistence. No key, attestation, root, production
  receipt, kernel isolation, production runner start, execution, result, or
  claim promotion is bundled.
- Bounded CPU float64 validation runner with persisted environment-receipt and
  live-process re-verification, exact code/source/dependency/artifact binding,
  an atomic one-time runner-start marker, a 120-second evaluation budget, and a
  canonical in-memory observation retaining every success, expected failure,
  unexpected failure, and failed metric across the exact 27 cases and 59
  variants. Its exact CLI requires the fixed external root-owned trust store and
  remains fail-closed without production trust and signed artifacts; no key,
  receipt, start, durable production result receipt, fitting authorization, or
  scientific promotion is bundled.
- Failure-inclusive result-receipt writer and verifier that re-verify the raw
  signed chain, live/persisted environment, durable runner-start marker, and
  exact bounded observation before one `O_EXCL`/`O_NOFOLLOW` mode-0600 canonical
  receipt is synchronized to a private caller root. Every failed case, variant,
  and metric remains present. Acceptance requires an out-of-band exact receipt
  hash and external revocation/supersession state; the receipt is unsigned,
  same-UID replacement resistance and independent result review remain external,
  and no production receipt or claim promotion is bundled.
- Exact-graph bounded PubChem CID 177/11199 reference-canonical tautomer
  selection, generated-hydrogen-only transfer, and a frozen failure-inclusive
  identity corpus without thermodynamic or scientific promotion.
- PEP 561 `py.typed`, focused Ruff/Pyright gates, reproducible-wheel checks, and
  SPDX 2.3 SBOM generation.

### Changed

- Repository-wide `O(N)` language was narrowed to the conditional bounded-degree
  short-range contract.
- Capability policy now separates implementation, internal execution,
  scientific validation, benchmark validation, customer enablement, and claim
  safety.
- Docking, physics, and benchmark public errors no longer expose raw exception
  text; private diagnostic content is represented by SHA-256 fingerprints.

### Scientific boundary

`0.2.0rc1` is an internal CPU reference release candidate. It does not establish
calibrated force-field accuracy, docking/ranking validity, MD ensemble validity,
free-energy accuracy, GPU parity, public benchmark performance, wetlab proof, or
customer product readiness.

## 0.1.0

Initial isolated Engine v2 wheel containing contract, sparse geometry, AI/math,
and fail-closed CPU reference surfaces.
