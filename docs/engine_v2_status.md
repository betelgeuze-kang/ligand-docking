# Independent Engine v2 Status

This document is the human-readable companion to
`config/independent_engine_v2_capabilities.yaml`. The YAML snapshot is validated
against `betelgeuze_engine_v2.capabilities.capability_snapshot()` and is the
machine-readable source of truth.

## Current implementation stage

```text
v2_ao_native_cpu_scorer_contract_rc5
```

The current `main` branch contains:

- versioned all-atom molecular contracts and canonical SHA-256 identities;
- bounded sparse radius geometry with fixed neighbor and cell capacities;
- a scalar-energy neural reference model with exact coordinate gradients;
- periodic image-shift geometry for the supported short-range path;
- matrix-free projection, torsion-tree, temporal, and physics-gate primitives;
- a fail-closed CPU reference orchestrator and strict checkpoint contracts;
- an independent `betelgeuze-engine-v2` wheel for Python 3.10–3.12;
- an ABI 1.21 C++/Rust complete fixed64 candidate pipeline and a frozen,
  exactly-once-consumed native CPU qualification-v7 profile. The pipeline applies the
  same full-Cartesian geometric admission to final post-refinement coordinates
  before ScorerV1, preserves every rejected or upstream-failed slot as typed
  inactive evidence, and exposes the complete score, validity, stable-rank,
  and clustering graph through one bounded versioned v3 bridge shared by CLI,
  benchmark, API, and product shadow. Two compiled synthetic fixtures preserve
  all 64 slots, compare independently implemented C++ reference and Rust CPU
  decisions plus all numeric scientific state, and reuse persistent contexts.
  The single account-scoped synthetic execution recorded `PASS` in persisted
  receipt `f653185c2bfc7642e2d9e73b918a2e0a9c14c0e107f5804799e140bb42c34b82`;
  it must not be rerun. CI may compile, unit-test, and statically verify the
  frozen profile and receipt but receives no live qualification authority. This
  is engineering-only evidence and grants no molecular, benchmark, Stage 0,
  product, HIP-device, or claim authority;
- a separately constructed Rust public preselected-fixed64 composition path that accepts the exact
  receipt-bound 512-to-64 funnel payload and invokes the existing ABI 1.21
  admission, rigid/V7 refinement, post-refinement admission, ScorerV1,
  validity, stable-rank, and clustering kernels without rerunning proposal
  generation. Its receipt rederives every component and row binding, synthetic
  C++/Rust CPU coverage preserves rank order, and all execution, reservation,
  benchmark, product, Stage 0, Fresh-128, and claim authority remains false;
- a source-bound Rust CPU producer for the exact 512-row preselection input. It
  executes 128 deterministic transforms in each uniform-SO3, pocket-surface,
  single-anchor, and multi-anchor lane, derives the orientation seed from the
  complete search and geometric-input identities, computes the existing exact
  geometric metrics for every generated coordinate set, and directly emits the
  receipt-bound funnel payload plus materialized 64 rows. Missing compatible
  dual-anchor geometry becomes 128 typed failures rather than a substituted
  lane. Aggregate pair work is bounded before coordinate generation, and every
  molecular, reservation, benchmark, Fresh-128, product, Stage 0, performance,
  and scientific-claim authority remains false;
- bounded single-model PDB and single-molecule SDF V2000 ingestion;
- bounded single-block CIF syntax plus mmCIF entity/asym/polymer identity,
  zero-occupancy, altloc, nonpoly instance, component atom/bond, and selected
  `_struct_conn` source-declaration contracts, plus a bounded selected nonpoly
  `_atom_site` observation-to-identity join and finite-binary64 coordinate-value
  binding that retains each raw token spelling and exact 64-bit pattern, plus
  bounded occupancy/B-factor/formal-charge marker and numeric semantics and a
  complete atom-site model-number classification that permits only model set
  `{1}` for bounded execution and explicitly blocks multi-model or singleton
  non-1 execution without automatic selection, plus a bounded biological-
  assembly declaration policy that binds exact selected
  `_pdbx_struct_assembly`, `_pdbx_struct_assembly_gen`, and
  `_pdbx_struct_oper_list` rows and blocks preparation without interpreting
  operation expressions, matrices, composition, or expanding coordinates, plus
  a bounded
  `_pdbx_unobs_or_zero_occ_residues`/`_pdbx_unobs_or_zero_occ_atoms`
  observation-gap admission policy that classifies source `occupancy_flag` 0/1
  and blocks preparation whenever a zero-occupancy or unobserved declaration is
  present without treating absent declaration categories as proof of structural
  completeness, plus a
  bounded source-water/monoatomic-metal/monoatomic-nonmetal-ion composition-role
  projection that does not infer general ligand, cofactor, or biological roles,
  plus source-declared modified polymer residue identity joined to the bounded
  polymer semantic projection without atom-site, parent-chemistry, or preparation
  inference, plus a
  fail-closed component-bond/identity-symmetry connection topology that keeps
  metal coordination edges separate from canonical bonds, plus bounded neutral
  acyclic C/O/H single/double-bond chemical-graph hydrogen completion with a
  failure-complete per-instance parameterability report, plus a graph-bound
  coordinate scaffold that preserves source Cartesian angstrom coordinates and
  assigns added hydrogens deterministic 1.0-angstrom fixed parent offsets while
  explicitly leaving neighbor geometry, stereo, clashes, calibration, and
  minimization uninterpreted, plus an instance-level canonical all-atom
  materializer that carries prepared atom/bond identity, source scalar states,
  exact coordinate bits, residue/chain source identity, and canonical hashes
  while retaining intercomponent coordination as metadata and blocking
  unmaterialized intercomponent covalence, plus an offline reviewed parameter-source
  provenance contract that freezes the OpenFF Sage 2.2.1 unconstrained release,
  commit, artifact SHA-256, CC-BY-4.0 license identity and license-text SHA-256
  while explicitly excluding OFFXML parsing, parameter or partial-charge
  assignment, coverage, applicability, calibration, and scientific validation,
  plus a separate source-to-system binding carrier that attaches that reviewed
  source identity, immutable artifact digest, license identity, and candidate
  scope to eligible canonical system hashes without assigning any values,
  plus an explicit partial-charge vector application contract that binds finite
  binary64 values, atom order, total-charge conservation, method provenance, and
  source system hashes while providing no charge generator or scientific method,
  plus canonical Engine v2 JSON identity round-trip receipts that re-execute
  encode/decode/re-encode and preserve topology, coordinates, lineage metadata,
  parameter-source binding, and charge bits without re-emitting original mmCIF,
  plus an exact-graph pH-dependent protonation contract for PubChem CID 176
  acetic acid that binds reviewed factual identity, pKa 4.76, caller pH, and a
  90% dominant-population threshold, abstains near the pKa, removes only the
  exact generated hydroxyl hydrogen for the deprotonated state, preserves a
  localized formal-charge representation without claiming resonance or tautomer
  interpretation, treats graph matching as a contract comparison rather than
  source-structure identity authentication, and verifies the selected system by byte-exact JSON
  round trip, plus a frozen 7-case PubChem-identity corpus with two selected
  states, one abstention, and four expected failures whose source URLs,
  retrieval dates, and source-specific license-review boundary are explicit
  while raw PubChem records, contributor text, and conformers are not bundled,
  plus an exact-graph reference-canonical tautomer-selection contract for
  PubChem CID 177 acetaldehyde and CID 11199 vinyl alcohol that moves only the
  generated hydroxyl hydrogen, rejects source-observed hydrogen movement, and
  explicitly makes no population, equilibrium, thermodynamic-preference, pH,
  geometry, parameter, or scientific claim, plus a frozen 6-case factual-
  identity supported/failure corpus that retains four expected failures,
  plus a frozen 30-case
  synthetic contract corpus that retains supported, explicitly unsupported, and
  2 invalid-source cases, plus a 52-axis executable coverage ledger classifying
  25 supported, 27 explicitly unsupported, and 0 not-implemented rows,
  including a nonpoly explicit-altloc preparation failure boundary and a known
  insertion-code exact identity join across scheme, atom-site, and connection rows,
  while unresolved nonpoly components are never guessed to be cofactors;
- an independent physics-term registry contract;
- deterministic bounded docking proposal/search scaffolds, including
  deterministic bridge analysis that retains ordinary ring systems as rigid
  components, exposes ring-system identity in the torsion derivation receipt,
  and admits rotor candidates only on ring-external single, non-aromatic,
  non-terminal heavy-atom bonds without declared stereo. Connected ring systems
  containing 12 or more atoms fail closed conservatively so a shorter cycle or
  chord cannot hide an unsupported macrocycle;
- bounded chemistry-aware rotor perception that records one disposition per
  bond and excludes amide, urea, carbamate, sulfonamide, conjugated, ring,
  aromatic, non-single, hydrogen, terminal-heavy-atom, and stereo-constrained
  bonds;
- capability-gated deterministic ETKDGv3 conformer preparation with exact
  seed/configuration and RDKit-version identity, MMFF94-or-UFF conformer
  energies, energy-window filtering, heavy-atom Kabsch-RMSD diversity, stable
  conformer identities, an immutable prepared-state receipt, bounded atom/bond
  counts, exact-one-component input, explicit potential stereochemistry, and a
  pinned RDKit CI lane;
- deterministic authenticated guided proposals for donor/acceptor hotspots,
  opposite formal-charge anchors, connected hydrophobic patches, aromatic-plane
  alignment, and principal-axis shape alignment. Exact context/policy/mode and
  proposal receipts are retained, multi-candidate batches keep a uniform
  Haar/spherical fallback, and unavailable guidance reproduces the uniform
  baseline exactly;
- an authenticated Scorer v1 baseline with complete explicit-partial-charge
  admission, sparse bounded contact work, eight separately receipted terms,
  source-system/config/proposal cross-wire rejection, and failure-complete
  guided-search term evidence;
- an authenticated ligand-internal energy-refinement adapter that connects
  docking proposal lineage to the bounded CPU reference minimizer and retains
  exact pre/post coordinates, energy delta, displacement, convergence,
  implementation source, immutable parameters/configuration, and
  failure-complete attempt evidence.
  Its Scorer v1 guided-search result binds every candidate row to the exact
  attempt while preserving the full denominator. Parameter identity contributes
  to the generic refiner/search contract, and final coordinates carry
  recomputed torsion metadata;
- a benchmark manifest and one-row-per-case success/failure ledger;
- a frozen four-case public redocking protocol definition bound to the
  PoseBusters packaged PDB examples at commit
  `1a5f26aa7270fafba21b7fec8b3633f4c4e45ead`, exact external receptor/reference
  SHA-256 values, MIT repository-license metadata, the RCSB CC0 usage-policy
  identity, an exact ligand-graph identity seed whose coordinates are ignored,
  predefined 2 Å symmetry-aware direct RMSD in the fixed receptor frame plus
  bounded-validity endpoints,
  all-case failure denominators, and exact scorer-source hashes. No raw data is
  bundled, no network fetch or benchmark execution is implemented or authorized,
  no result document exists, and the four fixtures do not establish statistical
  representativeness or PoseBusters Benchmark equivalence;
- a historical frozen 300-case public redocking evaluation contract selected
  by a result-independent SHA-256 rule from the published PoseBusters 308-case
  journal subset. A complete report existed before numeric Stage 0 freeze, so
  all 300 cases are contaminated development data and the former 298-case
  primary-holdout designation is invalid. The legacy scope is rejected for
  execution but retained for historical report-schema serialization only; it
  never identifies blind evidence. A disjoint fresh 128-case complement is the
  internal provisional blind holdout; it has not been executed. Its active
  refiner is V7, and Stage 0 admission, product promotion, and public claims
  remain false. The contract
  binds the external Zenodo archive and identifier-document
  bytes, requires one failure-complete five-pose row for each of Engine V2,
  Vina, and GNINA, and defines bootstrap-CI Top-1/3/5 RMSD and valid-pose
  success, top-pose geometric/chemical validity, runtime,
  ligand-size/rotor/ring subgroups, paired baseline deltas, and typed Engine V2
  preparation/charge/H-bond/proposal-oracle/scoring-regret decomposition. The
  fixed 64-candidate denominator, candidate pose/evaluator outcomes, scorer
  term receipts, and Top-5 consistency checks are sealed into each execution
  receipt. A local runner verifies the
  source archive and identifier list, materializes only the frozen inputs,
  serializes Engine V2 poses, invokes Vina/GNINA modes, and retains exact
  receipts. It binds timeout and the full Engine V2 Python source closure,
  enforces one CPU, stops engine runtime before shared evaluation, and records
  that Engine V2's ligand-derived spherical region is not geometrically equal
  to the external ligand-derived autobox. Engine V2 benchmark preparation uses
  explicit, claim-blocked standard-residue receptor charge proxies and
  conserved RDKit Gasteiger ligand charges; these are not calibrated
  force-field charges. Exact per-case commands, pose hashes, and all
  evaluator dependency versions are bound. Exact Torch build and row-level
  execution policies are also bound and revalidated against engine-mode
  commands and case-specific input path names. Unevaluated PoseBusters validity
  cells abort evidence construction before row reduction. Every case carries a
  materialization value for all four archive inputs that must match the frozen
  per-case receipt manifest, plus a frozen, report-validated base-plus-index
  seed that report construction cross-checks across all three commands. Private
  read-only inputs are opened once and consumed through pinned descriptors.
  PoseBusters decodes molecules from pinned bytes; GNINA uses suffix-bearing
  hard-link aliases to the same inodes under an inherited private-directory
  descriptor, with inotify mutation detection and path/inode/hash checks around
  every engine/evaluator window. Row receipts record boot-session/runtime identity including CPU affinity/model,
  selected runtime-variable hashes, the Python executable, and loaded
  shared-file identities. Evaluator identity includes installed-file hashes in
  addition to exact versions. Cache reads are disabled because a colocated
  self-hash is not a trust anchor; no bootless or same-boot timed row is reused.
  Public report construction accepts only exact fresh-run
  `VerifiedPublicRedockingCaseExecution` receipts, not caller-reconstructed raw
  rows. Each receipt binds the full success/failure result, runtime, evaluator
  outcomes, pose hashes, materialization, implementation, evaluator, and one
  common environment identity; mutation or identity drift is rejected before
  metric derivation. This is a local typed API boundary, not an independent
  process attestation.
  Engine V2 pose hashes and evaluator outcomes are derived from one
  `O_NOFOLLOW`-pinned serialized payload rather than separate pathname reads.
  Every invocation atomically quarantines any prior canonical full report
  before preflight, and every Engine V2 attempt quarantines a prior canonical
  pose before execution. Exact-case-selection digests distinguish partial
  summary filenames.
  The external binary is copied to a private
  SHA-256-named stage and executed through a pinned Linux file descriptor while
  its path, inode, mode, and hash are revalidated around every launch and before
  report creation. Incomplete Engine V2 ranked pose sets use a typed failure
  code, and typed input-parse failures use the frozen
  `engine_v2_input_unsupported` code accepted by report validation. Managed
  output paths reject symlink ancestors and cleanup deletes only
  the expected four inputs. Local row checksums are not signatures or
  independent provenance attestations. External fresh-process and Engine V2
  reused-process runtimes
  remain explicitly non-comparable. The
  external structures, engine outputs, and benchmark result remain absent from
  the repository;
- a frozen H5 reference-physics parameter-origin and runtime-envelope record.
  It binds seven exact implementation-source SHA-256 identities, records that
  every runtime value is supplied explicitly by the caller, and enumerates the
  implemented bond, angle, proper-periodic-torsion, Lennard-Jones, screened-
  Coulomb, switching, pair-scaling, orthorhombic-PBC, topology, and capacity
  checks. The existing reviewed Sage 2.2.1 artifact remains a pinned candidate
  identity only: it is not claimed to be the latest selection, is not parsed,
  and no value from it is bound to the runtime parameter object. The code-
  enforced runtime envelope is explicitly not a scientifically validated
  chemical applicability domain and authorizes neither fitting nor validation.
- a bounded deterministic CPU reference minimizer for one-model `float64`
  systems with caller-supplied explicit parameters. It uses force-directed
  steepest descent, Armijo backtracking, hard iteration/backtrack/displacement
  and neighbor-capacity bounds, and retains every accepted, applicability-
  rejected, non-finite, and insufficient-decrease evaluation. Canonical
  checkpoints bind the original system, topology, parameter and config hashes,
  exact little-endian binary64 coordinates, energies, maximum force, progress,
  and the complete observation ledger. Restart re-evaluates the checkpoint
  state and requires bit-exact stored energy and force before continuing. This
  is an unvalidated internal numerical contract: it ships no parameter set,
  performs no assignment, and establishes no scientific applicability,
  minimization accuracy, product qualification, or customer execution claim.
- bounded per-term numerical diagnostics layered around the unchanged frozen
  reference evaluator. For a single CPU `float64` model it retains all `6N`
  plus/minus coordinate perturbations, reconstructs each of the five component
  forces by central difference, and checks their sum against the evaluator's
  analytic total force plus each component's net-force residual. For
  non-periodic systems it reports the explicit configurational convention
  `sum((r-r_center) outer F)` and tests symmetry and uniform-strain energy
  derivatives. Periodic virial is unavailable until a cell-strain derivative
  is implemented and therefore fails closed rather than using wrapped Cartesian
  coordinates. These diagnostics preserve the frozen evaluator source hash and
  are implementation evidence only, not parameter, applicability, force,
  virial, scientific, or product validation.
- a separate versioned reference-forcefield extension that preserves the frozen
  v1 evaluator and parameter sources. It adds an explicit ordered-star
  out-of-plane `asin` improper definition with harmonic autograd energy/forces,
  plus simultaneous equal-weight degree-relaxed Jacobi projection for caller-
  supplied distance constraints under hard iteration, correction, and capacity
  bounds. Every projection iteration retains all constraint residuals, including
  degenerate and exhausted-budget failures. A separate constrained minimizer
  projects the initial state and every trial, iteratively removes constraint-
  normal force components, applies Armijo decrease to the actual projected
  displacement, retains nested projection failure rows, and binds exact binary64
  checkpoint/restart state. Rigid transforms and equivalent-outer-atom swaps are
  tested. Atomic masses are ignored; neither the improper/constraint surface nor
  constrained minimization has independent scientific validation, general
  assignment, or product approval.
- a bounded non-periodic CPU `float64` polar Generalized Born term using the
  Still pair function from DOI `10.1021/ja00172a038`. Every atom must have one
  caller-supplied fixed effective Born radius bound to a source digest, exact
  topology, and the v2 charge-parameter fingerprint. The evaluator includes all
  bounded self and pair contributions, derives exact coordinate forces by
  autograd, can be combined with the versioned v2 force field, and can optionally
  participate in constrained projected-Armijo minimization with its parameter
  fingerprint bound into exact checkpoint/restart state. Analytic,
  finite-difference, rigid-transform, atom-permutation, net-force, coverage,
  identity, minimum-distance, and fail-closed PBC tests are present. Effective-
  radius estimation, nonpolar solvation, salt/ions, periodic solvent,
  independent solvation/minimization validation, and product approval remain
  unavailable.
- a frozen CPU minimization contract-validation protocol. It binds fourteen
  ordered unsolvated-v1, constrained-v2, fixed-Born-constrained-v2, checkpoint,
  and fail-closed identity/applicability cases; ten predefined CPU float64
  metrics; exact implementation-source SHA-256 identities; all-case failure
  accounting; and an independent-reference import-separation policy. The
  protocol is not executed. A separate exact materializer now resolves all
  eleven fixture payloads and maps all fourteen cases to deterministic CPU
  `float64` systems, v1/v2/fixed-Born parameters, bounded configurations,
  checkpoint-pause plans, and fail-closed identity injections. It imports no
  evaluator or minimizer entrypoint and records no physics value, checkpoint,
  metric, or result. The original protocol document remains byte-identical and
  retains its historical materializer-missing authorization blocker; the
  separate manifest does not open that frozen gate. A separate source binding
  now fixes an import-separated standard-library minimization reference and its
  analytic-oracle dependency. The reference independently implements distance
  and tangent-force projection, fixed-Born energy/forces, bounded backtracking,
  fail-closed identity/applicability outcomes, and exact checkpoint/restart.
  Test-only endpoint comparisons are implementation checks, not validation
  result evidence. A frozen Ed25519 independent-review attestation contract
  now binds the exact artifact and requires author/reviewer identity separation,
  complete ordered algorithm/projection/fixed-Born/backtracking/checkpoint/
  negative-case/import-boundary review checks, explicit limitation
  acknowledgements, an out-of-band trusted reviewer key, and bounded freshness.
  Signing keys remain outside verifier trust stores; those stores hold only raw
  Ed25519 public keys. The stdlib-only bootstrap verifies the first
  authorization with trusted OpenSSL before importing Engine v2 or third-party
  packages. It also measures exact byte manifests for Python, the standard
  library, OpenSSL, cryptography, NumPy, and Torch before those imports;
  run-start and the bounded runner remeasure the same six signed identities.
  It bundles no attestation or trusted key and cannot authorize execution. No
  independent scientific review or authorization exists. Separate frozen
  CPU-only, network-disabled execution-environment and failure-inclusive result-
  receipt contracts bind all fourteen cases, both operational and independent
  input identities, all ten predefined metrics, and exact failure retention.
  They bundle no authorization receipt, environment/result receipt,
  runner, writer, or observed value. A separate Ed25519 single-run
  authorization contract now requires a verified nonexpired review, pairwise-
  distinct author/reviewer/operator identities, exact code/runner/dependency and
  receipt-contract identities, at most 24 hours of validity, external revocation
  inputs, and a one-time nonce. It bundles no operator key, signed receipt, or
  atomic nonce reservation and cannot open execution.
  A separate local POSIX nonce-reservation primitive now re-verifies both raw
  signed artifacts and their exact code/runner/dependency/receipt-contract
  identities before consuming the one-time nonce as a canonical mode-0600 record
  beneath a caller-provisioned effective-UID-owned mode-0700 root. It uses
  `O_EXCL`/`O_NOFOLLOW`, file and directory `fsync`, rejects duplicate or
  externally consumed nonces, and exposes no release/delete API. No production
  root, key, signed artifact, or reservation is bundled, and reservation alone
  cannot authorize run start, execution, fitting, or claims. A separate
  minimization run-start primitive now re-verifies the raw review and
  authorization artifacts plus the durable nonce record before observing the
  exact Linux x86_64 CPU process, Python/Torch/NumPy versions, GPU visibility,
  locale, seed, thread, deterministic-algorithm, logical-argv, and network-
  namespace identities. It verifies a maximum-five-minute operator-signed
  network-isolation attestation and atomically persists one canonical mode-0600
  secret-free environment receipt beneath a separate private caller root using
  `O_EXCL`, `O_NOFOLLOW`, and file/directory `fsync`. A separate stdlib-only
  bootstrap and bounded runner now bind their exact combined source identity,
  re-read the persisted receipt and live process, require the exact signed clean
  checkout, dependencies, protocol, and materialization manifest, then consume
  one durable mode-0600 nonce-bound runner-start marker. It evaluates the ordered
  fourteen-case CPU float64 matrix, retains all success and failure observations,
  compares operational endpoints with the import-separated independent oracle,
  and verifies exact checkpoint/restart equality under a 120-second budget.
  The primitive creates no network
  namespace, kernel isolation, production key, attestation, root, or receipt.
  A separate failure-inclusive writer now re-verifies the signed chain, live
  environment receipt, runner-start record, and canonical observation before
  atomically persisting one nonce-bound mode-0600 receipt. Its reader requires
  an out-of-band exact receipt hash and current revocation/supersession inputs.
  The exact process entrypoint remains fail-closed until this writer is wired
  into the externally provisioned bootstrap. No production result
  receipt, independent result review, scientific applicability, or parameter-
  fitting approval exists, so minimization and
  solvated minimization remain unvalidated.
- a frozen CPU reference energy/force contract-validation protocol. It binds
  seven exact synthetic fixture profiles, twenty exact mutation contracts,
  twenty-seven ordered cases (fifteen expected passes and twelve expected
  fail-closed rows), nineteen predefined float64 acceptance metrics, all-case
  denominators, independent-oracle separation, environment/result-receipt
  requirements, and the exact H5 dependency. A separate frozen artifact binding
  now materializes all seven fixtures, twenty mutations, and twenty-seven cases
  into fifty-nine deterministic CPU float64 runtime variants without energy,
  force, or metric values. It also binds a standard-library-only independent
  scalar analytic oracle whose forces use forward-mode exact derivatives and
  whose source is AST-audited to import neither the reference evaluator nor the
  protocol, Torch, NumPy, or an external molecular solver. Exact materializer,
  oracle, materialization-manifest, protocol, fixture-manifest, and H5 SHA-256
  identities are bound. No production result receipt, scientific holdout, independently
  reviewed runtime parameter values, independent scientific acceptance, or
  signed authorization receipt exists. A separate frozen review-attestation
  contract now fixes the required review checks, acknowledged limitations,
  author/reviewer identity separation, out-of-band trusted reviewer key,
  HMAC-SHA256 integrity, and a maximum 30-day validity window. No attestation or
  trusted key is bundled, and even a verified review cannot itself authorize
  execution or fitting. The current gate denies validation execution and parameter-fitting proposals.
  A separate authorization contract now binds a future verified review to a
  pairwise-distinct operator identity, out-of-band HMAC key, exact code/runner/
  environment/result/dependency identities, at most 24 hours of validity,
  external receipt/review revocation sets, and a one-time nonce. No operator key
  or receipt is bundled. Verification only makes a receipt eligible for a
  future atomic nonce reservation; it does not open execution or fitting.
  Separate frozen receipt contracts now define a CPU-only, network-disabled
  execution environment and the exact failure-inclusive result shape for all
  twenty-seven protocol cases, fifty-nine materialized variants, and nineteen
  predefined metrics. They require exact authorization, nonce, code, runner,
  dependency, environment, artifact-path, reviewer, supersession, and revocation
  identities. A separate result-writer contract and implementation now exist,
  but no production environment receipt, production nonce reservation, runner
  start, durable observed energy/force/error/metric value, or result receipt is
  bundled, so the production execution and fitting gates remain closed.
  A separate atomic reservation primitive now re-verifies the raw review and
  authorization artifacts against out-of-band trust anchors and exact downstream
  hashes, then consumes one nonce in a caller-provisioned private local POSIX
  directory using `O_EXCL`, `O_NOFOLLOW`, file `fsync`, and directory `fsync`.
  Its durable canonical record remains execution-disabled and has no release or
  delete API. The repository bundles no key, artifact, reservation root, or
  production reservation; filesystem locality and same-UID replacement
  resistance are not established. A separate run-start primitive now re-verifies
  the raw review, authorization, and durable nonce record; observes the live
  Linux/Python/NumPy/Torch/env/thread/determinism/argv state; verifies a
  short-lived operator-signed network-isolation attestation; and atomically
  persists one mode-0600 secret-free environment receipt beneath a private
  caller root. It provides neither kernel network isolation nor execution
  authorization, and the receipt never authorizes execution or fitting. A
  separate bounded runner now re-reads that persisted receipt, re-verifies the
  live process, a direct stdlib-only `-I -S -B -X pycache_prefix=/dev/null`
  bootstrap that ignores environment/user-site import paths before any
  validation dependency is imported, and workers with automatic site
  initialization disabled and only root-owned read-only bootstrap-verified
  dependency roots supplied. The signed runner-source identity binds both the
  bootstrap and runner files. The bootstrap bounds canonical stdin and verifies
  the external operator signature, signed commit/source, and clean checkout
  before the package initializer can run. Reservation and artifact roots must be private external directories
  with no ancestry overlap with the checkout. Root-owned absolute-Git clean-checkout proof with replacement refs
  disabled and rejected for the observed `HEAD`, signed runner source, frozen
  reference-evaluator/materializer/oracle sources, and dependency identities, atomically
  consumes one mode-0600 nonce-bound runner-start marker, and evaluates the exact
  twenty-seven cases and fifty-nine variants on CPU float64 under a 120-second
  deadline. Frozen manifest materialization runs in a supervised preflight child;
  remaining budget is rechecked before marker consumption, and evaluator/oracle
  work runs in a separate fixed child whose process is hard-killed at the deadline;
  POSIX timers remain an inner defense. It
  returns one canonical failure-inclusive observation in memory, including
  failed metrics and sanitized evaluator failures. The exact process command
  executes the absolute checked-out bootstrap path with the frozen isolated
  Python flags and accepts only a bounded canonical stdin request that cannot
  contain trust keys. Reviewer/operator anchors load only from the externally provisioned
  fixed `/etc/betelgeuze/engine-v2/reference-validation-trust-anchors.json`
  root-owned mode-0600 store; the repository does not bundle that store or keys.
  Trust material never enters stdin, argv, the worker requests, or the response;
  it remains in the verified supervisor that creates the environment receipt and
  finalizes the result. A missing or unsafe trust store, wheel-only invocation,
  or a checkout without exact clean Git metadata fails closed. No marker
  release API is exposed. A separate failure-inclusive
  result writer re-verifies the raw signed review/authorization chain, persisted
  environment receipt, live process, durable runner-start record, and exact
  observation identities before creating one canonical private mode-0600
  nonce-bound receipt with `O_EXCL`, `O_NOFOLLOW`, file `fsync`, and directory
  `fsync`. It retains every case, variant, metric, and failure, rejects a case
  status that contradicts its metrics, binds the embedded nonce to the selected
  filename, and opens special files nonblocking before rejecting them. Its verifier
  requires an out-of-band exact receipt SHA-256 and current external revocation/
  supersession inputs. The receipt is unsigned, private POSIX storage is not an
  external authenticity proof, and same-UID pathname/inode replacement
  resistance is not established. Changed content is detected when the required
  out-of-band SHA-256 is supplied. Test-only signed artifacts and receipts exercise these
  primitives; no production key, attestation, receipt, root, runner start,
  validation result, independent result review, or scientific acceptance is
  bundled.

## What the implementation does not establish

All customer and scientific promotion flags remain false. The repository does
not currently establish:

- a calibrated independent force field;
- independently validated minimization or a scientific minimization protocol;
  the bounded deterministic minimizer and its failure/checkpoint tests are
  implementation evidence only;
- an authorized, independently reviewed CPU reference validation study, an
  accepted analytic oracle, a production or independently accepted durable
  result receipt, or accepted energy/force evidence; test-only synthetic
  observations and receipts are implementation checks, not production
  validation results or parameter-fit data;
- a shipped production/reference parameter set, reviewed caller-supplied
  parameter values, a Sage-to-runtime value binding, or a scientifically
  validated molecule/element/charge applicability domain; the H5 runtime
  capacity envelope establishes execution admission only;
- general-chemistry real-world coverage, a legal determination for source-
  specific PubChem content, thermodynamic/population evidence for the bounded
  tautomer pair, or authorization to fit parameters from any contract corpus;
- general mmCIF coordinate geometry or symmetry-expanded topology, occupancy
  population or B-factor quality assessment, general charge chemistry, hydrogen
  model selection, ensemble/trajectory/averaging semantics, multi-model execution,
  validated hydrogen geometry, source-to-graph parameter assignment, parsed
  parameter values or assigned parameters, general ligand/cofactor or
  non-source-declared modified-residue role interpretation,
  metal/ion/modified-residue preparation, source-to-system parameter-value
  assignment, partial-charge generation/calibration/validation, original mmCIF
  text/token/category-order/comment/whitespace round trip, or a
  parameterable `AllAtomSystem`;
- a scientifically validated docking scorer or ranker;
- macrocycle docking, ring conformer sampling, or
  third-party-toolkit-equivalent rotor perception. Ordinary supported ring
  systems are rigid, and the bounded chemistry-aware rules remain
  scientifically unvalidated;
- scientific validation of ETKDG ensemble quality, symmetry-aware conformer
  diversity, or a default Engine V2 RDKit dependency;
- validated pharmacophore perception, calibrated guided-placement quality, or
  evidence that the current graph and principal-axis heuristics improve pose
  recovery;
- calibrated or scientifically validated Scorer v1 weights, physical-energy
  semantics, affinity/free-energy interpretation, or evidence that Scorer v1
  improves pose ranking;
- receptor--ligand interaction-energy minimization, evidence that ligand-only
  local refinement improves pose recovery, or a validated docking-refinement
  energy surface;
- public CASF/PDBBind/LIT-PCBA/PoseBusters holdout performance or a statistically
  representative public holdout; neither the frozen four-case fixture nor the
  300-case runner and its two-case engineering smoke are a benchmark result;
- free-energy, MM/GBSA, FEP, or equilibrium MD accuracy;
- CUDA, ROCm, or HIP numerical/performance parity;
- customer API integration for Engine v2;
- wetlab or commercial discovery claims.

## Complexity boundary

The bounded short-range geometry path has a conditional linear-complexity
contract when density, cutoff, maximum neighbors, maximum atoms per cell, model
width, and candidate budgets remain fixed. It fails closed on configured
capacity overflow. This is not evidence that the complete repository, all
long-range physics, or end-to-end product workflow has measured `O(N)` scaling.

## Capability interpretation

Each capability row separates four questions:

1. **implemented** — source and focused tests exist;
2. **internal reference execution enabled** — the CPU reference path may run;
3. **scientifically validated** — independent scientific evidence exists;
4. **customer execution enabled** — the capability is admitted to a product route.

Only the first two are true for selected V2-M surfaces. `claim_safe` remains
false for every current capability row.

## Verification

The canonical post-merge workflow is `.github/workflows/ci-engine-v2-main.yml`.
It runs on relevant pull requests and every push to `main` using Python 3.10,
3.11, and 3.12. It validates:

- the complete focused Engine v2 CPU test suite;
- capability YAML/code drift;
- source compilation and architecture guards;
- independent wheel construction and member inspection;
- clean virtual-environment installation without system site packages;
- `pip check` and import outside the repository checkout.

## Next evidence layers

Future implementations must preserve the current fail-closed separation:

```text
implemented scaffold
≠ calibrated physical quantity
≠ scientifically validated method
≠ public benchmark result
≠ product-qualified capability
```
