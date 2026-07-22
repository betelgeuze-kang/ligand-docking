# Independent Engine v2 Status

This document is the human-readable companion to
`config/independent_engine_v2_capabilities.yaml`. The YAML snapshot is validated
against `betelgeuze_engine_v2.capabilities.capability_snapshot()` and is the
machine-readable source of truth.

## Current implementation stage

```text
v2_at_explicit_solvent_ion_preparation_contract
```

The current `main` branch contains:

- versioned all-atom molecular contracts and canonical SHA-256 identities;
- bounded sparse radius geometry with fixed neighbor and cell capacities;
- a scalar-energy neural reference model with exact coordinate gradients;
- periodic image-shift geometry for the supported short-range path;
- matrix-free projection, torsion-tree, temporal, and physics-gate primitives;
- a fail-closed CPU reference orchestrator and strict checkpoint contracts;
- an independent `betelgeuze-engine-v2` wheel for Python 3.10–3.12;
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
- deterministic bounded docking proposal/search scaffolds with atomic
  candidate-level term decomposition and an uncalibrated, explicit-parameter
  CPU `float64` scorer separating receptor--ligand LJ, screened Coulomb, signed
  ligand internal strain delta, and VDW-overlap penalty. The scorer admits only
  H/C/N/O/F/P/S/Cl/Br/I, requires exact partial-charge/parameter agreement,
  abstains on metals and receptor nonpolymer cofactors, and does not add
  aromatic-specific or stereochemical physics. A separate fit-only calibration
  contract accepts only an identity-audited `fit` partition, deterministically
  fits pairwise logistic term weights, binds the holdout identity commitment,
  and evaluates retained failure poses with all-case and target-family Top-1/
  Top-5/coverage bootstrap intervals. No public partition, fitted model, or
  result is bundled;
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
  and the complete observation ledger. Restart deterministically reproduces the
  entire checkpoint from the trusted source input, requires exact history
  equality, then re-evaluates the current checkpoint state and requires
  bit-exact stored energy and force before continuing. Standalone parsing checks
  canonical structure and internal self-hash consistency; trusted-input replay
  is the source-authentication boundary. This
  is an unvalidated internal numerical contract: it ships no parameter set,
  performs no assignment, and establishes no scientific applicability,
  minimization accuracy, product qualification, or customer execution claim.
- a bounded deterministic CPU `float64` velocity-Verlet NVE reference path for
  one-model systems with explicit atomic masses and caller-bound parameters. It
  rebuilds the compact neighbor list for every force evaluation, supports
  non-periodic or full 3D orthorhombic PBC with per-step wrapping, and can apply
  bounded canonical-pair-order inverse-mass SHAKE corrections using the prior
  constrained pair vectors followed by RATTLE radial-velocity projection.
  Fresh runs require an already position-constrained source state; initial
  radial velocities are projected before the step-zero energy is recorded.
  Minimum-image targets at or above half the shortest periodic length fail
  closed. Binary64 frames and checkpoints bind the complete constraint config,
  maximum accepted position/velocity residuals, cumulative SHAKE/RATTLE
  iterations, trajectory hash chain, and bit-exact same-source, same-parameter,
  same-config, same-runtime continuation. An optional direct-Ewald mode is
  bounded to a neutral single CPU `float64` model in a full 3D orthorhombic
  cell. It uses conducting/tin-foil boundary conditions, caller-bound alpha and
  rectangular reciprocal limits, potential-shifted `erfc` real space,
  reciprocal and self terms, and same-cell exclusion/1-4 `erf` corrections. It
  replaces the frozen v1 screened-Coulomb energy and force without double
  counting, and its complete config is checkpoint-bound. The implementation
  has no general solute constraint or mass assignment, independent
  SHAKE/RATTLE/Ewald
  comparison, accepted drift/convergence study, or cross-host/GPU evidence and
  no PME, net-charge background convention, thermostat/barostat,
  triclinic-cell, NVT/NPT-statistics, scientific, product,
  or customer claim.
- a bounded deterministic CPU `float64` explicit-solvent and monovalent-ion
  preparation. It freezes the exact OpenMM Force Fields Amber TIP3P standard
  XML snapshot at commit `89cd3a18d19c207b595269f36cb7e0d63950944e`
  and its source SHA-256, including TIP3P geometry/masses/charges/LJ and the
  compatible Joung--Cheatham Na+/Cl- masses/charges/LJ values. For a complete,
  unboxed one-model solute with caller-bound masses, partial charges, and
  reference parameters, it deterministically recenters the solute, constructs
  water and ion atoms/residues, water bonds and angles, intrawater exclusions,
  three rigid-water distance constraints, full orthorhombic PBC, exact
  neutralization, per-species molarity, minimum-distance diagnostics, and a
  canonical placement trace. Result identities bind the source and solvated
  systems, both topology and parameter fingerprints, constraints, profile,
  configuration, and placement. Neutral and counterion cases run through the
  actual direct-Ewald evaluator and constrained NVE with bit-exact restart.
  The SHA-256-ordered lattice is neither minimized nor equilibrated, and no
  external energy/force comparison, liquid-density/diffusion/dielectric/RDF or
  ion-property evidence, two-host receipt, scientific validation, product
  qualification, or customer route exists.
- a bounded all-step NVE drift analyzer that rejects subsampled trajectories,
  requires a genuine pause/resume execution, and retains every energy,
  instantaneous kinetic-temperature, linear-momentum, current constraint
  residual, frame, coordinate and velocity digest row. It reports maximum and
  RMS energy/momentum drift, energy-drift slope, exact checkpoint/trajectory
  equality, and all nine caller-predeclared metric rows including failures.
  Threshold fingerprints and both checkpoint identities are provenance-bound.
  These are local numerical implementation diagnostics; no independently
  reviewed acceptance thresholds, external integrator comparison, two-host
  receipt, parameter validation, or scientific/product/customer claim exists.
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
  `O_EXCL`, `O_NOFOLLOW`, and file/directory `fsync`. A separate isolated outer
  launcher and fixed no-site controlled inner bootstrap now apply canonical
  uint32 `PYTHONHASHSEED` during interpreter initialization without consuming
  request stdin in the outer process. The bounded runner binds the exact
  bootstrap/dependency-identity-helper/runner source identity, re-reads the persisted receipt and live
  process, and gives the child only receipt-derived seeds and environment plus
  a parent/child hash probe. It requires the exact signed clean checkout,
  signed aggregate identities for six selected dependency artifacts, protocol,
  and materialization manifest, then consumes
  one durable mode-0600 nonce-bound runner-start marker. It evaluates the ordered
  fourteen-case CPU float64 matrix, retains all success and failure observations,
  preserves complete ordered operational and independent-oracle coordinate
  traces with canonical binary64 raw/evaluated coordinates, per-step coordinate
  and identity digests, whole-trace digests, exact counts, and accepted-energy
  ledgers. A frozen trajectory-comparison contract aligns every evaluation by
  index, iteration, trial, and outcome; applies predefined coordinate `1e-8 Å`
  and energy `1e-10 kcal/mol` max/RMS limits; retains branch, rejection, count,
  and expected-failure dispositions; and binds uninterrupted, paused, and
  resumed result/checkpoint/trajectory digests for three checkpoint cases. The
  runner, writer, and independent result-review verifier recompute this evidence
  and reject omission, reorder, cross-wire, non-finite values, or digest tamper.
  A non-production in-process 14-case implementation check passes all 14
  comparison rows, including both fixed-Born rows, and exact restart equality
  for all three checkpoint cases. The observed implementation-only maxima are
  `3.907985046680551e-14 kcal/mol` for trajectory energy and
  `1.6653345369377348e-15 Å` for raw/evaluated coordinates, within the frozen
  pre-observation bounds; six expected fail-closed rows remain explicitly
  non-comparable and there are no unexpected failures.
  The production entrypoint now rejects a caller-owned mutable checkout and
  requires the complete Engine v2 package tree to be a canonical root-owned,
  non-replaceable source snapshot before package import. The current development
  worktree does not satisfy or provision that external requirement. Before
  package import, both bootstraps independently rehash the signed raw Git commit
  and recursive tree objects using Git SHA-1 object framing, then compare the
  exact tracked `betelgeuze_engine_v2` path set and every file's mode, blob OID,
  SHA-256, and size with the live root-owned read-only tree. The resulting
  canonical source manifest is carried in the six-element bootstrap state. Each
  of the six signed dependency digests likewise binds a canonical per-file
  identity. Run-start durably persists both `<nonce>.source-tree.json` and
  `<nonce>.dependencies.json` with mode 0600, `O_EXCL`, `O_NOFOLLOW`, and
  file/directory fsync before the environment receipt; runner and writer
  finalization require exact persisted/live equality and bind the source digest
  through environment, runner-start, observation, and result identities.
  Workers now retain the exact canonical request transport, request-bound
  pre/payload/post lifecycle evidence, failure-complete payload dispositions,
  native endpoint snapshots, child PID, and payload aggregates. Supervisor reads
  are hard byte-bounded before buffering; a complete raw stdout transcript must
  equal the canonical reconstruction from the request, ordered retained rows,
  and lifecycle. Writer validation and both result-review contracts independently
  reconstructs and re-hashes the successful transcript. Incomplete output keeps
  bounded digest/length/prefix/discard metadata, accepts no child payload, and is
  not independently replayable or review-acceptable. External source/dependency-
  runtime provisioning, kernel-backed source/Git-metadata immutability and
  custody, pre-bootstrap stdlib closure, signed native-DSO allowlisting/lifetime
  closure and kernel vDSO identity remain production blockers. A Linux-only
  fixed-`/proc` primitive now measures PID, nonnegative parent PID, start clock
  tick, boot ID, and PID-namespace inode with bounded race-checked reads, but it
  is not bound into the workers, cannot exclude same-tick PID reuse, and is not
  external launch authenticity or durable uniqueness. Final signed
  evidence-class carrier propagation and external custody remain blockers. The
  active energy-force base chain uses v2 identities
  with a v4 runner/result writer; the active minimization base chain uses v4
  review/execution-environment identities, v5 authorization/result-receipt/
  nonce/run-start identities, a v8 runner, and v7 result writer/result review.
  Their hashes were
  refrozen through the full upstream dependency DAG. A separate read-only
  verifier recognizes 64 superseded contract documents by canonical projection
  hash. Superseded signed attestations, receipts, and run records are not
  supported and no compatibility claim is made for them.
  The energy-force lane now has a frozen Ed25519 result-review leaf with full
  case/variant/metric/failure/worker dispositions, independent recomputation of
  all 56 required metric occurrences from retained raw energy/force arrays with
  bitwise retained-value equality, and four-role separation. No
  production result, attestation, trusted result-reviewer key, or independent
  human approval is bundled; upstream scientific review and authorization remain
  symmetric HMAC, and live dependency-manifest re-verification/external custody
  remain open.
  A common claim-closed Ed25519 base foundation freezes the exact
  `synthetic_validation_production` evidence class, pre-execution permit,
  adjacent monotonic status snapshots, bounded carrier inputs, and a two-event
  dual-distinct-key custody sequence for the exact signed permit followed by its
  exact signed status snapshot. Its v1 projection and hash remain unchanged. It rejects
  downgrade, trust-key aliases, replay-list hits, rewritten status history,
  stale/retroactive handoff status, and raw-byte/run/lane/host transplant within
  those two events. Permit verification only inspects bounded caller-supplied
  consumption state and does not atomically enforce one-use. No production key,
  permit, external status log, global one-use registry,
  enrolled host, immutable artifact store, actual custody chain, or final
  stage-discriminated carrier family is provisioned. An additive companion now
  internally re-verifies that raw prefix and implements production-only Ed25519
  sequence-3 review and sequence-4 authorization carriers/events with causal-time,
  exact scalar-type, role/key/material-separation, and raw/logical revocation checks.
  These artifacts and keys are not provisioned; the energy-force upstream chain
  remains symmetric HMAC and the process digest is bound but not externally
  authenticated. A sequence-5 companion now re-verifies the complete exact raw
  sequence-1-through-4 prefix and lane-local reservation record, binds a
  custodian-signed intent to exact registry/witness authority material and
  realm-global uniqueness slots, and verifies registry plus witness signatures
  over a claimed commit only after a strictly newer post-commit status snapshot.
  The artifact is an attestation, not independent proof of external serializable
  compare-and-set, slot consumption, non-equivocation, epoch continuity, or one
  unique successor; same-prior-head sibling attestations remain possible and all
  actual CAS/one-use/uniqueness fields stay false. No registry, key, intent,
  commit proof, or production chain is provisioned, and environment/later stages
  remain unimplemented. A verifier-only external same-epoch registry-proof
  companion now freshly re-verifies sequence 5, checks a fixed-order chain of
  exactly three adjacent transaction-tagged sparse-Merkle leaf transitions,
  verifies separated backend/head-observer signatures and the supplied freshly
  reverified status-lineage-tail denials, and requires the backend-native
  checkpoint to equal a caller-supplied expected sequence/checkpoint. A supplied
  proof verifies the backend's serializable/committed attestation, the exact
  three-leaf transition, the observer-signed checkpoint, and equality with that
  caller expectation only. It does not authenticate the expectation's
  provenance or prove that the supplied status tail is globally latest, and does not
  prove actual external CAS, global one-use consumption, status-head CAS,
  realm-wide non-equivocation, epoch continuity, later-head consistency, or a
  unique successor; all actual and promotion fields remain false. No proof,
  keys, or backend is bundled. A separate verifier-only authenticated
  head/status-receipt companion now snapshots both nested inputs, reproduces the
  same raw proof twice, verifies a role-separated external Ed25519 receipt over
  the exact proof/sequence-5/head/status/service/time/challenge projection, and
  requires a separately reverified strict status descendant issued after the
  receipt. Its current tail can revoke or supersede the exact receipt, authority,
  proof, checkpoint, or service identity. This establishes only the bounded
  receipt signature, exact binding, and caller challenge equality; challenge
  freshness/one-use, a globally latest head, CAS, global slot consumption,
  non-equivocation, later-head consistency, epoch continuity, and successor
  uniqueness remain false. No receipt, receipt-authority key, caller challenge,
  or post-receipt status descendant is provisioned. A verifier-only same-epoch
  later-head companion now freshly re-verifies that receipt, verifies a strict
  adjacent backend-signed checkpoint/state-root path and an observer signature
  over the full path, and proves that the original three consumed reservation
  leaves remain included in the caller-pinned later state root. A status tail
  issued after the consistency proof supplies its denial fence, and the signed
  later-head observation time means observer countersign completion. The slot
  fact is selected-root inclusion of the anchor-attested consumed-leaf encodings,
  not independent proof of actual global consumption. The DTO preserves false
  challenge-freshness and challenge-one-use fields. This establishes only one
  supplied fork's later-head consistency; sibling pins can each pass, so global
  latest, non-equivocation, epoch continuity, CAS, and promotion remain false.
  No consistency proof or post-proof status is provisioned.
  A fixed-policy witness-quorum verifier now binds N/F/Q, the exact ordered
  roster with distinct caller-pinned declared fault-domain identifiers, a stable
  exact-anchor fork scope, and
  Q signed exact-lineage statements. The complete N-member roster must remain
  valid and non-revoked. This verifies only a conditional same-epoch,
  anchor-scoped certificate; the verifier does not observe the fault bound,
  enforce exclusive voting, reconcile independent journals, or rule out a
  hidden sibling certificate. Realm-wide non-equivocation and every promotion
  fact remain false, and no policy, keys, proof, journals, or post-quorum status
  are provisioned.
  A verifier-only adjacent registry-epoch transition companion now freshly
  re-verifies the exact previous same-epoch witness-quorum proof, requires a
  caller-pinned next epoch with integer ordinal exactly one greater, carries the
  previous terminal state root unchanged into sequence-zero genesis, derives
  the genesis checkpoint from the complete transition context, and verifies
  disjoint previous/next fixed-roster Ed25519 quorums over one exact statement.
  This establishes continuity for that supplied transition only. The verifier
  does not enforce exclusive witness locking, compare independent journals,
  exclude separately quorum-signed sibling successors, prove global latest or
  realm-wide non-equivocation, or commit CAS. No transition proof, next policy,
  keys, votes, or post-transition status descendant is provisioned.
  Runtime-integrity companion v13 additionally binds the refrozen minimization
  trajectory-comparison contract together with the exact frozen custody-v1,
  review/authorization, reservation, external registry-proof, authenticated
  head/status receipt, later-head consistency, witness-quorum, adjacent epoch-
  transition continuity, and process-launch-identity contract SHA-256 values;
  runtime v8 through v12 are retained in the read-only legacy registry.
  The separate process-launch measurement primitive creates no network
  namespace, kernel isolation, production key, attestation, root, or receipt.
  A separate failure-inclusive writer now re-verifies the signed chain, live
  environment receipt, runner-start record, and canonical observation before
  atomically persisting one nonce-bound mode-0600 receipt. Its reader requires
  an out-of-band exact receipt hash and current revocation/supersession inputs.
  The exact process entrypoint now accepts only bounded canonical input, binds
  the signed nonce, implementation author, clean source, and dependency bytes
  before package import, reloads reviewer/operator anchors only from the fixed
  external root-owned mode-0600 trust store, and connects environment receipt,
  a child-preflighted fourteen-case run, and result finalization in one verified
  process. It remains fail-closed because no production trust store, signed
  chain, private roots, reserved nonce, or production result receipt is
  provisioned. The minimization result-review validator and Ed25519 signature
  bind the source-manifest digest through the fully validated result receipt,
  but no actual independent-review approval, scientific applicability, or
  parameter-fitting approval exists, so minimization and
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
  separate bounded runner now re-reads that persisted receipt and re-verifies
  the live process. A source-only stdlib `-I -S -B -X
  pycache_prefix=/dev/null` outer launcher validates startup without consuming
  stdin under the root-owned Python executable, removes environment/user-site
  import paths, and re-execs the same
  interpreter as the fixed no-site controlled inner command so canonical
  uint32 `PYTHONHASHSEED` is applied during interpreter initialization. Workers
  receive exact seeds and deterministic environment only from the verified
  receipt and recheck exact argv, cwd, flags, environment identity, and a
  parent/child hash probe; they no longer copy mutable live supervisor state.
  Only root-owned read-only bootstrap-verified dependency roots are supplied.
  The signed runner-source identity binds the bootstrap, dependency-identity
  helper, and runner files.
  The bootstrap now requires a non-root process and a root-owned/read-only
  package snapshot, but no such external production snapshot, kernel-backed
  source/Git-metadata immutability/custody, or external dependency runtime is
  provisioned. It independently verifies the signed raw commit and recursive
  Git tree objects with Git SHA-1 framing and compares a canonical mode/blob-
  OID/SHA-256/size manifest for every tracked package file with the live root-
  owned read-only source tree. The canonical source manifest is passed in the
  six-element bootstrap state and persisted once per nonce as mode-0600
  `<nonce>.source-tree.json`; runner and writer require exact persisted/live
  equality and cross-check its digest through environment, start, observation,
  and result identities. The six signed aggregate dependency digests commit to
  a corresponding durable per-file sidecar. Exact worker requests are now
  retained and cross-checked against those outer identities; successful worker
  transcripts are reconstructed and re-hashed from retained rows and lifecycle
  evidence. Pre-bootstrap stdlib closure, signed native-DSO allowlisting/lifetime
  closure and kernel vDSO identity remain absent. The process launch tuple
  primitive exists, but worker binding, same-tick collision resistance, and
  external launch custody are absent. The common evidence-class/permit/status
  base primitive plus additive sequence-3 review/sequence-4 authorization and
  sequence-5 reservation-commit-attestation companions exist. The external
  same-epoch registry transaction-proof, authenticated head/status receipt, and
  same-epoch later-head consistency, fixed-policy anchor-scoped witness-quorum,
  and adjacent epoch-transition continuity verifiers also exist, but no proof, backend
  key, head-observer key, receipt-authority key, challenge, receipt, later-head
  proof, witness policy/keys/quorum certificate, post-consistency or post-quorum
  status descendant, adjacent transition proof/policy/votes, post-transition
  status descendant, or out-of-band current head is provisioned.
  Environment/later carriers, an external serializable registry, atomic permit
  consumption, realm-wide non-equivocation, externally enforced transition
  uniqueness, and a provisioned chain,
  independent result-review
  dependency-manifest re-verification, and an end-to-end asymmetric upstream
  review/authorization chain remain absent. The energy-force Ed25519
  post-result-review leaf contract is implemented, but no actual production
  receipt, review attestation, trusted key, or independent review exists.
  The inner bootstrap carries one 180-second cooperative preflight deadline
  across re-exec, polls canonical stdin under that deadline, and verifies
  the external operator signature, signed commit/source, and clean checkout
  before the package initializer can run. Reservation and artifact roots must be private external directories
  with no ancestry overlap with the checkout. Root-owned absolute-Git clean-checkout proof with replacement refs
  disabled and rejected for the observed `HEAD`, signed runner source, frozen
  reference-evaluator/materializer/oracle sources, and selected aggregate dependency
  identities, atomically
  consumes one mode-0600 nonce-bound runner-start marker, and evaluates the exact
  twenty-seven cases and fifty-nine variants on CPU float64 under a 120-second
  deadline. Preflight traversal uses bounded `scandir`, direct streaming of
  wheel `RECORD`, pre-read file-size caps, aggregate entry/file/byte budgets,
  and the carried monotonic deadline; it does not establish kernel-enforced
  lifetime isolation.
  Frozen manifest materialization runs in a supervised preflight child;
  remaining budget is rechecked before marker consumption, and evaluator/oracle
  work runs in a separate fixed child whose process is hard-killed at the deadline;
  POSIX timers remain an inner defense. It
  returns one canonical failure-inclusive observation in memory, including
  failed metrics and sanitized evaluator failures. The exact process chain
  executes the absolute checked-out bootstrap path first with the frozen
  isolated outer flags and then with the frozen controlled inner loader; only
  the inner accepts the bounded canonical stdin request, which cannot contain
  trust keys. Reviewer/operator anchors load only from the externally provisioned
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
  primitives. The energy-force Ed25519 result-review leaf validates the exact
  writer receipt and all ordered 27-case, 59-variant, and 19-metric evidence,
  independently recomputes all 56 required metric occurrences from retained raw
  energy/force arrays with bitwise retained-value equality, derives
  case/variant/metric/expected-failure/worker dispositions, checks
  successful input/component/total/force evidence, and requires separation of
  all four governance roles. Its upstream scientific-review and authorization
  records remain symmetric HMAC, and it does not independently reverify the live
  dependency manifest or establish external custody. No production receipt,
  attestation, trusted result-reviewer key, or independent human approval is
  bundled; every production, scientific, fitting, benchmark, and product flag
  remains false.
  The separate minimization Ed25519 result-review contract fully revalidates one
  exact result-writer receipt, binds all fourteen ordered case outcomes and every
  retained or missing metric disposition, verifies exact runtime/oracle/result
  hashes, allowed status/error pairs, exact per-case-budgeted nonnegative counts,
  finite count-consistent energy ledgers recomputed against retained energy
  metrics, and both ordered coordinate traces, and derives trace- and step-level
  dispositions plus an explicit accepted or rejected
  review outcome. Verification reverifies the raw signed pre-execution review and
  authorization Ed25519 chain, requires canonical JSON byte transport, a
  caller-provided result-reviewer public key, pairwise separation from the derived
  implementation author, scientific reviewer, and authorization operator, plus
  explicit current revocation/supersession state for the receipt chain and the
  result-review attestation itself. Full receipt validation and the Ed25519
  signature bind the canonical source-manifest digest as well. A cryptographically verified
  rejection remains a rejection, and even a verified acceptance keeps production,
  scientific, fitting, and product gates closed. No production key, attestation,
  receipt, root, runner start, validation result, independent result-review receipt,
  or scientific acceptance is bundled.

## What the implementation does not establish

All customer and scientific promotion flags remain false. The repository does
not currently establish:

- externally provisioned root-owned source/dependency runtimes, kernel-backed
  source/Git-metadata immutability and custody, pre-bootstrap stdlib closure,
  signed native-DSO allowlisting/lifetime closure, kernel vDSO identity,
  binding of measured worker PID/start-time/boot/namespace identity into signed
  carriers, same-tick collision-resistant external launch identity/custody, or a
  provisioned signed production evidence/custody chain; the claim-closed common
  permit/status base and unprovisioned four-event companion primitives alone do not
  satisfy this requirement;
- a calibrated independent force field;
- independently validated minimization or a scientific minimization protocol;
  the bounded deterministic minimizer and its failure/checkpoint tests are
  implementation evidence only;
- an authorized, independently reviewed CPU reference validation study, an
  accepted analytic oracle, a production or independently accepted durable
  result receipt, or accepted energy/force evidence; test-only synthetic
  observations and receipts are implementation checks, not production
  validation results or parameter-fit data;
- an accepted production trajectory-level minimization comparison, reproduction
  on two CPU hosts, or independent external-implementation comparison; the
  refrozen v2.1 comparison contract and non-production 14/14 implementation
  result do not satisfy the remaining S0 scientific or production exit
  conditions, and no production result has been dispositioned by an independent
  human reviewer;
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
- public CASF/PDBBind/LIT-PCBA/PoseBusters holdout performance or a statistically
  representative public holdout; the frozen four-case protocol fixture is not a
  benchmark result;
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
