# Engine v2 scientific evidence roadmap

Status: planned evidence program; no scientific or product promotion

Observed baseline: `main@88f0e6ada2b232116e3b08cc5e5994b8734fd950`

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
- Preserve the frozen CPU reference energy/force contract-validation protocol.
  It binds seven synthetic fixture profiles, twenty mutation contracts,
  twenty-seven ordered pass/fail-closed cases, nineteen predefined float64
  metrics, the exact H5 dependency, all-case denominators, future environment
  and result-receipt fields, and an executable closed authorization decision.
  A separate frozen binding now materializes every fixture, mutation, and case
  into fifty-nine deterministic CPU float64 variants and binds both that source
  and a standard-library-only analytic oracle. The oracle uses scalar equations
  with forward-mode exact derivatives and an AST-enforced boundary forbidding
  reference-evaluator, protocol, Torch, NumPy, and external-solver imports. No
  comparison or metric result exists, synthetic values are not fit data, and
  neither validation execution nor a parameter-fitting proposal is authorized.
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
  verification cannot open execution until atomic nonce reservation and run-
  start environment/result contracts exist.
- Obtain an actual independently signed review attestation and separately
  signed non-expired authorization receipt, then atomically reserve its nonce;
  only after every run-start dependency is reverified may any synthetic
  implementation-mathematics result be collected. The
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
