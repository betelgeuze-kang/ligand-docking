# Changelog

This changelog tracks the independent `betelgeuze-engine-v2` distribution. The
legacy/product monorepo has separate operational evidence and does not inherit a
scientific claim from a package version.

## Unreleased

### Changed

- Added an authenticated, deterministic Scorer v1 pose-ordering contract with
  separate typed-vdW, electrostatic, directional hydrogen-bond, hydrophobic,
  desolvation-proxy, torsion-energy, ligand-strain, and weak-pocket-prior terms.
  It requires complete charge-conserving explicit partial charges, binds the
  exact receptor subset and source systems, preserves a per-candidate term
  receipt, derives periodic torsion terms from final coordinates, revalidates
  retained decompositions against the active scorer, and retains the full
  success/failure denominator when used with guided placement.
- Authenticated known-pocket docking now has a deterministic interaction-guided
  proposal layer. Bounded graph features drive donor/acceptor, opposite-charge,
  connected hydrophobic-patch, aromatic-plane, and principal-shape placements
  while the existing Haar/spherical uniform generator remains an exact
  fallback. Context, policy,
  per-proposal mode, selected atom anchors, requested and observed anchor
  distances, feature counts, proposal fingerprints, budget, and search authority
  are cross-wired through immutable receipts. Proposal generation rederives the
  feature context from the required bound receptor and ligand systems before
  accepting it. Receptor topology work uses a bounded pocket-local two-hop
  adjacency, and sampled degenerate guidance falls back per candidate.
- A capability-gated deterministic ETKDGv3 conformer-preparation contract now
  generates an energy-ranked, heavy-atom Kabsch-RMSD-diverse ensemble with
  stable conformer IDs and an exact prepared-state receipt. It rejects
  oversized, disconnected, ambiguously stereochemical, and macrocyclic inputs;
  binds complete conformer records to their coordinate models; and has a pinned
  RDKit CI lane. RDKit remains an explicit lane dependency rather than a default
  Engine V2 dependency.
- The authenticated torsion derivation schema and policy advance to `3.0.0`.
  Every ligand bond now receives a canonical rotor disposition. Bounded graph
  rules exclude amide, urea, carbamate, sulfonamide, conjugated, ring, aromatic,
  non-single, hydrogen, terminal-heavy-atom, and stereo-constrained bonds while
  retaining eligible non-terminal aliphatic single bonds. The receipt binds the
  complete parent array so each rotatable child is checked against its exact
  parent bond, and charge-separated sulfonamide resonance forms are recognized.
- The provisional authenticated torsion derivation schema and policy advance to
  `2.0.0`. Ordinary ring systems are now retained as rigid components,
  ring-external eligible single bonds remain rotor candidates, and detected
  ring systems of 12 or more atoms conservatively fail closed so shorter
  alternate paths cannot hide an unsupported macrocycle. Receipts now include
  canonical ring bonds, disjoint rigid-ring atom sets, the maximum ring-system
  atom count, and the maximum detected shortest cycle size.

### Scientific boundary

This stage does not add ring-conformer or macrocycle sampling, scientific
conformer-quality, guided-placement, or docking-score validation, or benchmark
evidence. Guided chemical features and Scorer v1 terms are bounded auditable
heuristics; Scorer v1 is not a calibrated energy, affinity, or free-energy
estimate.

## 0.2.0rc2 — Runtime identity release candidate

### Added

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

### Changed

- The distribution version is `0.2.0rc2`, separating the runtime-byte-identity
  and Ed25519 trust boundary from the accumulated `0.2.0rc1` surface.

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
  endpoint comparisons are implementation checks, not validation results or
  scientific promotion.
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
  variants. The direct CLI remains closed and no production key, receipt, start,
  durable production result receipt, fitting authorization, or scientific
  promotion is bundled.
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
