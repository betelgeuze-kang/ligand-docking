# Engine v2 scientific evidence roadmap

Status: planned evidence program; no scientific or product promotion

Observed baseline: `main@9a600487defbffee91480267ae9353f5081190c7`

This roadmap separates implemented source contracts from future scientific,
benchmark, hardware, and product evidence. A green source-level test or CI job
does not satisfy a later stage and cannot promote a claim flag.

## Current claim boundary

The current repository state keeps all of the following false:

- `scientific_validation=false`
- `public_benchmark_validation=false`
- `gpu_parity=false`
- `customer_execution=false`
- `commercial_readiness=false`

The capability-level fields `claim_safe`, `scientifically_validated`,
`benchmark_validated`, and `customer_execution_enabled` also remain `false`.
Each stage below requires separately reviewed evidence; stages cannot be
collapsed or inferred from one another.

## Stage gates

| Stage | Required evidence | Explicit non-claim |
|---|---|---|
| 1. Contract correctness | Deterministic identities; serialization round trips; units and dimensions; failure-inclusive ledgers; finite-difference energy/force checks; invariance and fail-closed tests | Does not calibrate a force field or validate docking accuracy. |
| 2. Frozen public benchmark protocol | Versioned CASF/PDBBind-style protocol where licensing permits; split provenance; symmetry-aware RMSD; PoseBusters-style validity; failure-inclusive denominators; frozen manifest and executable/scorer fingerprints; predefined thresholds; no test-set tuning | Protocol readiness is not a successful benchmark result. |
| 3. External baseline receipts | Reviewed offline Vina/GNINA/Smina receipts; binary/version/container identity; exact case coverage; retained failures; input/output hashes; comparable score semantics | Receipt integrity is not public benchmark validation or endorsement of an external engine. |
| 4. Docking evidence | Pose success, scoring, ranking, and valid screening/enrichment metrics; uncertainty intervals; predefined acceptance thresholds; complete denominator | Passing one metric does not establish general docking accuracy or commercial fitness. |
| 5. Physics evidence | Reviewed parameter provenance and applicability domain; independent energy/force references; force validation before dynamics; dedicated protocol for any free-energy claim | Stable execution alone is not physical accuracy. |
| 6. GPU parity | CPU/GPU tolerance contract; deterministic fixtures; kernel-level and end-to-end comparisons; failures retained; performance measured separately | Throughput is not numerical correctness, and CPU tests do not imply GPU parity. |
| 7. Product qualification | Threat model; tenant isolation; artifact integrity; durable quota/rate state; rollback; operational evidence; explicit authorization review | Customer routes remain disabled until every required gate is accepted. |

## Evidence record requirements

Every stage artifact must record:

- immutable input and protocol identities;
- code, dependency, executable, and environment fingerprints appropriate to the
  stage;
- exact case coverage with failures retained in the denominator;
- units, score direction, aggregation, thresholds, and uncertainty method;
- artifact hashes and path-confinement verification;
- reviewer, timestamp, supersession, and revocation status;
- separate values for `implemented`, `scientifically_validated`,
  `benchmark_validated`, `customer_execution_enabled`, and `claim_safe`.

Missing, stale, partial, unsigned, or mismatched evidence must fail closed. A
stage artifact may reference an earlier accepted artifact but must not copy its
claim status without revalidating the dependency and freshness chain.

## Review and promotion rules

1. Define the protocol and acceptance thresholds before observing held-out
   results.
2. Keep training, validation, and test provenance explicit and prevent
   test-set tuning.
3. Review scientific evidence independently from API security and release CI.
4. Review GPU correctness independently from GPU performance.
5. Require a dedicated PR for every claim transition, with the exact evidence
   bundle and affected capability fields in scope.
6. Reject partial promotion: an implementation flag may become true without
   changing any scientific, benchmark, customer, or commercial claim.
7. Keep the customer execution path disabled until product qualification and
   explicit operator authorization are both accepted.

## Near-term work queue

- Keep the bounded coordinate, scalar-value, canonical-topology, and first neutral
  acyclic C/O/H chemical-graph preparation carriers executable. The base graph
  has no coordinate payload, reviewed parameter source bound to it, or directly
  bound canonical `AllAtomSystem`;
  parameterability, geometry quality, and scientific validity remain false.
- Keep the separate graph-bound hydrogen-coordinate scaffold executable. It
  preserves source Cartesian angstrom coordinates and uses a deterministic
  1.0-angstrom fixed parent-offset table for added hydrogens; neighbor geometry,
  stereo, protonation, tautomer, bond-length calibration, clashes, minimization,
  parameterability, and scientific validity remain unestablished.
- Keep the separate instance-level canonical all-atom materializer executable.
  It binds prepared atom/bond identities, source scalar states, exact coordinate
  bits, nonpoly residue/chain source identity, and parent snapshot hashes into
  the existing versioned `AllAtomSystem`; coordination edges remain exact
  metadata rather than covalent bonds, and intercomponent covalence fails closed.
  It assigns no partial charges, masses, or parameters and establishes neither
  geometry quality, chemistry/scientific validity, parameterability, source-format
  round trip, nor customer readiness.
- Keep the reviewed parameter-source provenance contract executable. It freezes
  the official OpenFF Sage 2.2.1 unconstrained release tag, commit, artifact byte
  size and SHA-256, CC-BY-4.0 license identity and license-text SHA-256, reviewer
  role, timestamp, and explicit included/excluded scope. It neither bundles nor
  fetches the artifact, parses OFFXML, assigns parameters or partial charges,
  establishes molecule coverage or applicability, calibrates values, approves
  legal compliance, nor promotes scientific or product claims.
- Keep the separate source-to-system binding carrier executable. It binds the
  reviewed source identity, immutable artifact digest, license identity, and
  declared candidate scope to eligible canonical system hashes while proving
  that binding metadata is the only system change. It does not bundle or parse
  OFFXML, establish parameter coverage/applicability, assign parameters, charges,
  or masses, validate geometry/physics, or make a system parameterable.
- Keep the explicit partial-charge application contract executable. It binds a
  caller-supplied finite binary64 vector to exact system identity, atom order,
  method-provenance digest, and formal total-charge conservation before updating
  `Atom.partial_charge_e`. The synthetic corpus uses positive-zero fixture values
  only. The capability does not generate, calibrate, or scientifically validate
  charges, establish applicability, assign force-field values or masses, or make
  a system parameterable.
- Keep the canonical all-atom identity round-trip receipt executable. It
  re-executes canonical Engine v2 JSON encode/decode/re-encode and requires byte,
  system, topology, coordinate, lineage-metadata, parameter-source-binding, and
  partial-charge-bit identity. It does not re-emit original mmCIF text or preserve
  token spelling, category order, comments, or whitespace, and makes no chemistry,
  parameter, scientific, or product promotion.
- Keep the exact PubChem CID 176 pH-dependent protonation contract executable.
  It binds reviewed factual structure identity, pKa 4.76, caller pH, and a 90%
  dominant-population threshold; ambiguous populations abstain. A selected
  deprotonated state removes only the exact generated hydroxyl hydrogen and
  localizes formal charge without interpreting resonance or tautomer identity,
  then verifies a byte-exact canonical JSON round trip. General acid/base,
  multi-site, polyprotic, pKa prediction/calibration, partial-charge, parameter,
  geometry, scientific, and product claims remain blocked. Exact graph matching
  is a contract comparison and does not authenticate the input structure's
  source identity.
- Keep the separate 7-case PubChem-identity pH corpus executable. It retains two
  selected states, one abstention, and four expected failures with factual
  source identity, retrieval date, and source-specific license-review boundary.
  It bundles no raw PubChem record, contributor text, or conformer and is not
  parameter-fitting or scientific-validation data.
- Keep the exact PubChem CID 177 acetaldehyde/CID 11199 vinyl-alcohol
  reference-canonical tautomer-selection contract and its separate 6-case
  supported/failure corpus executable. Only exact neutral C2H4O graphs are
  accepted; vinyl alcohol moves only its generated hydroxyl hydrogen and
  source-observed hydrogen movement fails closed. Selection is a reviewed
  identity policy, not population, equilibrium, thermodynamic-preference, pH,
  geometry, parameter, or scientific evidence. Raw PubChem records, contributor
  text, and conformers remain unbundled under the source-specific review boundary.
- Keep the exact-input 30-case synthetic supported/failure contract corpus and
  the separate pH and tautomer corpora bound to the 52-axis coverage ledger
  executable. It classifies 25 axes as supported, 27 as explicitly unsupported,
  and 0 as not implemented; zero implementation gaps is not scientific or
  commercial readiness, none of the corpora is parameter-fitting data, and the
  ledger does not make V2-1 exit-ready.
- Keep exact selected source assembly metadata, generation, and Cartesian-
  operation rows bound while blocking preparation whenever any selected assembly
  category is present. Category absence does not prove that the deposited
  asymmetric unit is the biological assembly; identifiers, operation expressions,
  matrices, composition, coordinate expansion, and biological correctness remain
  uninterpreted.
- Keep both official source observation-gap categories bound and classify
  `occupancy_flag` 0 as zero occupancy and 1 as unobserved. Any such declaration
  blocks preparation before chemistry; absence of both optional categories does
  not prove structural completeness, and no identity, missingness, repair, or
  coordinate inference is performed.
- Keep source water and bounded monoatomic metal/nonmetal-ion composition roles
  executable without inferring general ligand, cofactor, modified-residue, or
  biological function. Metal/ion preparation remains explicitly unsupported.
- Keep unresolved general nonpoly components from being guessed as cofactors. The
  explicit unsupported boundary is not evidence that a component is biologically
  not a cofactor.
- Keep `_pdbx_struct_mod_residue` source declarations joined to bounded polymer
  label identity while atom-site observation, parent chemistry, modification
  nature, auth/model/insertion semantics, and preparation remain blocked.
- Keep the complete atom-site model-number set classified while only `{1}` is
  execution-eligible. Multi-model and singleton non-1 input remain explicit
  failure rows; selection, ensemble, trajectory, averaging, and cross-category
  reconciliation remain unimplemented.
- Keep explicit nonpoly atom-site alternate locations as a frozen preparation
  failure row. Conformer selection, occupancy population, and altloc chemistry
  remain unimplemented.
- Keep known nonpoly insertion-code markers exactly joined across scheme,
  atom-site, and connection endpoint identity. This does not interpret polymer
  insertion/deletion, canonical renumbering, or general author/label semantics.
- Preserve the now-closed tautomer implementation row and its bounded real-world
  identity corpus without treating it as scientific validation. Original mmCIF
  lexical re-emission remains explicitly outside the canonical identity receipt.
- Preserve the frozen four-case public redocking protocol definition and its
  exact PoseBusters-commit input, license-metadata, endpoint, failure-denominator,
  ligand-identity-seed, fixed-receptor-frame RMSD, and scorer-source identities.
  Seed coordinates are ignored. It bundles and fetches no data, authorizes no
  execution or publication, and is neither statistically representative nor a
  public benchmark result or PoseBusters-equivalence claim.
- Preserve the frozen H5 parameter-origin and runtime-envelope record. It binds
  exact runtime equations, code-enforced admission, configurable capacity
  defaults, and seven implementation-source hashes while recording that values
  are caller supplied and are not extracted from the reviewed Sage candidate.
  The runtime envelope is not a scientific chemical applicability domain, and
  the record authorizes neither parameter fitting nor a validation study.
- Preserve the bounded deterministic CPU `float64` reference minimizer as an
  implementation contract only. Its steepest-descent direction, Armijo
  backtracking, iteration/backtrack/displacement and neighbor-capacity bounds,
  failure-inclusive rows, and exact binary64 checkpoint/restart identities are
  tested, including bit-exact resumed versus uninterrupted output. This is not
  independent minimization evidence, a calibrated parameter set, chemical
  applicability, or a scientific/product/customer promotion gate.
- Preserve the bounded per-term diagnostics without changing the frozen
  evaluator source. Every `6N` plus/minus perturbation is retained; failed
  perturbations suppress partial force/virial tensors; five central-difference
  component forces must sum to the analytic total within fixed tolerance; and
  non-periodic centered-coordinate virials are checked for symmetry and against
  uniform-strain energy derivatives. Periodic virials remain fail-closed until
  a cell-strain derivative exists. This same-evaluator numerical check is not an
  independent reference, pressure/stress evidence, or scientific validation.
- Preserve the versioned improper/constraint extension without modifying the
  frozen v1 evaluator or parameter source. Its ordered-star out-of-plane `asin`
  definition, harmonic autograd forces, finite-difference/invariance tests, and
  bounded simultaneous degree-relaxed equal-weight distance projection are
  implementation contracts only. Projection retains every iteration and failure
  residual and supports minimum-image distances for admitted orthorhombic PBC.
  The constrained minimizer projects the initial state and every trial, iterates
  a symmetric constraint-tangent force projection, applies Armijo decrease to
  actual projected displacement, retains nested projection failures, and binds
  exact checkpoint/restart identity. Rigid transforms and equivalent-outer-atom
  swaps are tested. The path ignores atomic masses and is not integrated with MD.
  General improper/constraint assignment and coverage, reviewed values,
  independent force/constraint/minimization evidence, long-range physics,
  solvation beyond the fixed-radius polar GB capability, and scientific/product
  promotion remain open.
- Preserve the bounded fixed-effective-radius polar Generalized Born term as an
  explicit provisional solvation scope. It fixes the Still pair function and
  primary DOI `10.1021/ja00172a038`, binds every caller-supplied radius and its
  source digest to topology and the exact v2 charge-parameter fingerprint, sums
  all bounded self/pair terms for one non-periodic CPU `float64` model, derives
  exact forces, exposes a v2 combined evaluator, and optionally feeds that
  energy/force into constrained minimization while binding the solvation
  fingerprint into exact checkpoint/restart state. Analytic, finite-difference,
  rigid-transform, atom-permutation, net-force, identity/coverage, and fail-
  closed PBC checks are implementation evidence only. Effective-radius
  estimation, reviewed parameter applicability, nonpolar solvation, salt/ions,
  periodic solvent, MD integration, independent solvation and solvated-
  minimization reference evidence, and scientific/product promotion remain open.
- Preserve the frozen CPU minimization validation protocol as a result-free
  contract. It binds fourteen ordered unsolvated, constrained, fixed-Born
  constrained, checkpoint/restart, and fail-closed cases; ten predefined CPU
  float64 metrics; exact implementation-source identities; all-case failure
  accounting; and an import-separated independent-reference requirement. A
  separate exact materializer resolves all eleven fixture payloads and projects
  all fourteen cases into deterministic CPU float64 systems, v1/v2/fixed-Born
  parameters, bounded configurations, checkpoint-pause plans, and fail-closed
  identity injections. It imports no evaluator or minimizer entrypoint and
  collects no physics value, checkpoint, metric, or result. A separate
  source-bound standard-library reference implements constraint/tangent-force
  projection, fixed-Born energy/forces, bounded backtracking, fail-closed
  identity/applicability outcomes, and exact checkpoint/restart while importing
  only the audited analytic oracle. Test-only endpoint comparisons are
  implementation checks, not validation results. A frozen Ed25519 review
  attestation contract binds the exact artifacts and requires author/reviewer
  separation, complete ordered technical checks and limitation
  acknowledgements, an out-of-band trusted reviewer key, and bounded freshness.
  Reviewer/operator signing keys remain external, verifier trust stores contain
  only Ed25519 public keys, and the stdlib bootstrap verifies authorization via
  a trusted OpenSSL executable before importing Engine v2 or third-party code.
  The exact canonical-input entrypoint additionally binds the signed nonce,
  author, source, and dependency rows before import, reloads both reviewer and
  operator anchors from the fixed external root-owned mode-0600 trust store,
  rechecks the fixed supervised evaluator subprocess source/dependency/deterministic runtime, and
  finalizes the result receipt in the same verified process. No key, trust
  store, or attestation is bundled. No independent scientific review or
  execution authorization, production result receipt, independent
  result review, parameter applicability, or validation result is present. The
  protocol, materializer, and reference cannot authorize execution, fitting, or
  promotion.
- Preserve the frozen CPU reference energy/force contract-validation protocol.
  It binds seven synthetic fixture profiles, twenty mutation contracts,
  twenty-seven ordered pass/fail-closed cases, nineteen predefined float64
  metrics, the exact H5 dependency, all-case denominators, environment and
  result-receipt fields, and an executable closed authorization decision.
  A separate frozen binding now materializes every fixture, mutation, and case
  into fifty-nine deterministic CPU float64 variants and binds both that source
  and a standard-library-only analytic oracle. The oracle uses scalar equations
  with forward-mode exact derivatives and an AST-enforced boundary forbidding
  reference-evaluator, protocol, Torch, NumPy, and external-solver imports. No
  production result receipt or independently accepted metric evidence exists;
  test-only observations and receipts are implementation checks, synthetic
  values are not fit data, and neither production validation execution nor a
  parameter-fitting proposal is authorized.
- Preserve the separate frozen independent-review attestation contract. It
  requires exact artifact dependencies, complete ordered review checks and
  limitations, implementation-author/reviewer identity separation, an
  out-of-band trusted reviewer key, HMAC-SHA256 integrity, and at most 30 days
  of validity. No trusted key or attestation is bundled, and review verification
  alone cannot authorize execution or fitting.
- Preserve the separate frozen single-run authorization receipt contract. It
  requires a still-valid verified review, pairwise-distinct authorization
  operator identity, an out-of-band trusted key, exact code/runner/environment/
  result/dependency hashes, at most 24 hours of validity, external revocation
  inputs, and an unused one-time nonce. No key or receipt is bundled; receipt
  verification alone cannot open execution.
- Preserve the atomic local one-time nonce-reservation primitive. It re-verifies
  both raw signed artifacts and exact code, runner, environment, result, and
  dependency identities before `O_EXCL`/`O_NOFOLLOW` creation in a caller-owned
  mode-0700 POSIX directory, then synchronizes the file and directory. Duplicate
  or poisoned paths fail closed and there is no release API. No key, receipt,
  root, or production reservation is bundled; filesystem locality and same-UID
  replacement resistance remain external responsibilities.
- Preserve the separate run-start re-verification and environment-receipt
  primitive. It re-verifies the raw review and authorization plus the durable
  nonce record, observes the live Linux/Python/Torch/NumPy/environment/thread/
  determinism/fixed-logical-argv state, verifies a short-lived operator-signed
  network-isolation attestation, and atomically persists one private mode-0600
  canonical environment receipt. It stores path identities rather than paths
  and rejects secret-bearing argv. The library does not kernel-enforce network
  isolation or same-UID replacement resistance, and the receipt authorizes no
  production validation, fitting, result, or scientific claim. No production key,
  attestation, root, nonce reservation, or environment receipt is bundled.
- Preserve the bounded failure-inclusive CPU float64 runner. It re-reads and
  live-reverifies the environment receipt, constrained read-only Git clean-
  checkout proof for the observed `HEAD`, signed runner
  source, dependency rows, and frozen evaluator/materializer/oracle identities,
  atomically consumes one private nonce-bound start
  marker, and evaluates exactly twenty-seven cases and fifty-nine variants under
  a POSIX-interrupted 120-second case-materialization/evaluator/oracle budget.
  Every success, expected failure, unexpected
  failure, missing metric, and failed threshold remains in one canonical
  in-memory observation. The exact module command accepts only a bounded canonical
  stdin request without trust keys. Reviewer/operator anchors load only from the
  externally provisioned fixed `/etc/betelgeuze/engine-v2/reference-validation-trust-anchors.json`
  root-owned mode-0600 store, which is not repository-bundled. Trust material stays
  out of stdin/argv/output while the environment receipt, run, and result finalize
  in one verified process. A missing or unsafe store, a checkout without clean Git
  metadata, or a wheel-only invocation fails closed; marker release/deletion remain
  unavailable. Test-only
  artifacts exercise the primitive; no production key,
  receipt, start, result, acceptance, fitting, or scientific claim is bundled.
- Preserve the failure-inclusive result-receipt writer and verifier. They
  re-verify the raw signed review and authorization, live/persisted execution
  environment, durable runner-start marker, and exact bounded observation before
  atomically persisting one canonical private mode-0600 nonce-bound receipt.
  Every failed case, variant, and metric remains present; metric/status
  contradictions, filename/embedded-nonce mismatches, and blocking special-file
  reads fail closed. Verification requires
  an out-of-band exact receipt SHA-256 plus current external revocation and
  supersession inputs. The receipt is unsigned; private POSIX storage is not an
  external authenticity proof, same-UID replacement resistance is not
  established, and independent result review remains pending. No production
  receipt or scientific claim is bundled.
- Preserve the separate minimization result-review contract. It applies the
  full result-writer receipt validator before deriving deterministic accepted
  or rejected dispositions for all fourteen ordered cases, every retained or
  missing metric, exact runtime/oracle/result identities, allowed status/error
  pairs, exact per-case-budgeted nonnegative counts, finite count-consistent
  energy ledgers recomputed against retained energy metrics, and
  each expected fail-closed outcome. Builder and verifier reverify the raw signed
  pre-execution review and authorization chain before deriving the three upstream
  roles. The Ed25519 verifier requires canonical JSON byte transport, an
  out-of-band result-reviewer public key, pairwise separation across all four
  roles, and explicit current revocation/supersession state for the receipt chain
  and result-review attestation. A verified rejection is never promoted to acceptance,
  and a verified test-only acceptance still leaves production receipt/review,
  trajectory comparison, two-host reproduction, external-implementation
  comparison, applicability, fitting, and scientific gates closed. Complete
  ordered operational and independent-oracle coordinate traces, including every
  canonical binary64 raw/evaluated coordinate, per-step identities and digests,
  whole-trace digests, exact counts, accepted-energy-ledger consistency, and
  trace/step review dispositions, are now implemented as contract-integrity
  evidence. They are not trajectory-level scientific comparison or production
  evidence. No key, attestation, approval, or production evidence is bundled.
- Preserve the separate frozen execution-environment and result-receipt
  contracts. The environment contract fixes a CPU-only, network-disabled Linux
  lane, Python 3.10–3.12, Torch 2.6.0, NumPy 1.26.4, empty GPU visibility,
  deterministic seed/thread controls, exact argv and dependency identities, and
  confined artifact output. The result contract fixes all twenty-seven ordered
  cases, fifty-nine ordered variants, nineteen metric thresholds, retained
  failure rows, environment/authorization hashes, reviewer identity, and
  supersession/revocation fields. No production environment receipt, runner
  start, durable observed value, or result receipt is bundled, and production
  execution remains unauthorized. The run-start, bounded-runner, and result-
  writer primitives satisfy only implementation boundaries when test inputs are
  supplied; they do not satisfy any production result or scientific input.
- Obtain an actual independently signed review attestation and separately
  signed non-expired authorization receipt, then atomically reserve its nonce
  and construct a verified production environment receipt; only then may the
  bounded runner and result writer be considered for authorized synthetic
  implementation-mathematics result collection and a separate independent
  result review. The
  scientific parameterized-force-field lane additionally requires reviewed
  runtime values, a frozen chemical applicability domain, a complete holdout
  manifest, and independent reference artifacts.
- Design CPU/GPU parity fixtures only after the CPU reference behavior and
  tolerances are frozen.
- Close the remaining same-UID artifact TOCTOU, unsigned ledger, and runtime
  receipt re-evaluation risks before considering a customer-route review.

Until those evidence programs are executed and independently accepted, the
repository remains a bounded implementation and evidence-verification
scaffold, not a scientifically validated or commercially ready platform.
