# Ligand Docking and Molecular Dynamics Delivery Engine

[한국어 README](README.ko.md)

This repository contains two deliberately separated surfaces:

1. **Independent Engine v2** — versioned molecular contracts, bounded sparse
   geometry, CPU reference AI/physics composition primitives, strict checkpoint
   handling, bounded PDB/SDF ingestion, docking-search scaffolds, and a complete
   benchmark failure-row ledger.
2. **Legacy/product delivery stack** — local validated-runner workflows, evidence
   gates, API, wetlab packets, CASP/CAMEO preparation, and restricted delivery
   tooling.

The V2 short-range geometry path has a **conditional bounded-degree `O(N)`
algorithmic contract** when density, cutoff, neighbor/cell capacity, model width,
and candidate budgets remain fixed. This is not evidence of measured end-to-end
`O(N)` scaling for the entire repository or for long-range physics.

## Engine v2 Current Status

Current implementation stage:

```text
v2_0_3_0a1_p0_release_line
```

The `0.3.0a1` policy explicitly disables the legacy HIP/ROCm customer route.
Engine v2 remains CPU-reference-only for claim purposes until GPU parity and
product qualification evidence exist.

Implemented and GitHub-hosted CPU tested:

- canonical all-atom state, validation stages, and SHA-256 identities;
- bounded sparse radius geometry and periodic image-shift gradients;
- scalar-energy AI reference model with exact coordinate gradients;
- matrix-free projection, torsion, temporal, and physics-gate primitives;
- fail-closed CPU orchestration and strict runtime/checkpoint fingerprints;
- independent `betelgeuze-engine-v2` wheel for Python 3.10–3.12;
- bounded single-model PDB and single-molecule SDF V2000 parsers;
- independent physics-term registry contracts;
- a verifier-only adjacent registry-epoch transition contract that re-verifies
  the previous same-epoch witness quorum, requires exact ordinal adjacency,
  carries the terminal state root unchanged into a derived sequence-zero
  genesis checkpoint, and requires disjoint previous/next Ed25519 quorums over
  one exact statement; no proof or keys are bundled, and successor uniqueness,
  witness locking, independent journal agreement, realm-wide non-equivocation,
  execution, and every scientific/product claim remain unestablished;
- bounded deterministic CPU `float64` reference minimization with retained
  failure rows and exact checkpoint/restart identity, without scientific or
  product promotion;
- bounded deterministic CPU `float64` velocity-Verlet NVE integration with a
  compact neighbor-list rebuild at every force evaluation, full 3D
  orthorhombic PBC and coordinate wrapping, plus optional canonical-pair-order
  inverse-mass SHAKE position corrections and RATTLE radial-velocity
  projection. Frames and checkpoints bind the complete constraint
  configuration, maximum accepted position/velocity residuals, cumulative
  iteration counts, binary64 trajectory-chain identity, and bit-exact
  same-runtime restart. For neutral single-model CPU `float64` systems in a
  full 3D orthorhombic cell, an optional bounded direct-Ewald reference exactly
  replaces (rather than adds to) the frozen v1 screened-Coulomb term. It binds
  explicit alpha and reciprocal-index bounds, conducting/tin-foil boundary,
  shifted real-space, reciprocal, self, exclusion and 1-4 correction terms into
  the NVE config and restart identity. The installed
  `betelgeuze-engine-v2-openmm-nve-trajectory` offline workflow freezes one
  unconstrained ion-pair and one coupled-constraint water-like 16-step case,
  independently maps the finite direct-Ewald sum into OpenMM Reference, and
  retains every-step energy/force/coordinate/velocity, constraint, drift,
  native-checkpoint restart, and three exact fail-closed rows. Configuration
  SHA-256 is
  `2beca32683c0393666cc1c3b5a136bed3416f774b0db631133a04bb43928871e`;
  the single-host candidate observation
  `d60b15992c4179a93e2276d4da380554e3c69a7819f181347aacab11899140cd`
  passes 2/2 physical and 3/3 failure rows. This is bounded implementation
  comparison only. It ships no general solute constraint/mass assignment,
  validated parameters, accepted Ewald-convergence or long-time NVE-drift
  study, general independent chemistry/solvent coverage, PME, net-charge
  background convention, independently accepted thermostat/barostat or
  NVT/NPT statistics, two-host review, triclinic cells, GPU parity, or a
  product route;
- an installed
  `betelgeuze-engine-v2-openmm-explicit-solvent-trajectory` offline successor
  exact-binds the deterministic materializer to three 12 Å TIP3P/ion cases,
  four-step constrained NVE/OpenMM traces and both restart paths, a salted
  three-timestep ladder, direct-Ewald reciprocal bounds 2/3/4, and four exact
  fail-closed rows. Configuration SHA-256 is
  `e40902895938a4d7848e5207d0fe29de1ecaa43ae600c9c9ed8f7b7d0ac6c1b5`.
  The single-host candidate observation
  `d510c9c65625c00f7bd14c134c72e1ed5dab004764efc60c7fd96a9dae223157`
  deliberately remains 0/3 on the complete physical-case metric: OpenMM
  Reference SETTLE leaves a maximum `4.67e-8 Å` rigid-water residual against
  the frozen `1e-9 Å` threshold, and two inputs additionally expose an exact
  charged-pair cutoff-equality force divergence. The Ewald convergence checks
  and all 4/4 negative rows pass; the Engine timestep coordinate monotonic
  check remains failed at a `1.44e-11 Å` roundoff-scale error. Every failure is
  retained without threshold relaxation or input modification. This is a
  rejected, failure-inclusive diagnostic receipt, not accepted explicit-
  solvent, Ewald, long-time NVE, scientific, product, or P2 evidence. Two
  builds were byte-identical at wheel SHA-256
  `3c08913e23dceb49614f97cad03fe872c1a7d072cb15c7437760c566da452b70`,
  and the installed command reproduced the receipt;
- an installed
  `betelgeuze-engine-v2-openmm-force-double-rattle-trajectory` development
  successor keeps OpenMM Reference as the static force provider but performs
  constrained integration in a separate stdlib-only binary64 implementation
  using previous-constrained-vector SHAKE and projected-current-vector RATTLE.
  It binds three fresh 13.5 Å, four-water/ion inputs, a minimum `0.25 Å`
  force-active cutoff margin, 16 steps and both restart paths, every
  energy/force/coordinate/velocity/constraint/projection observation, and six
  exact failure rows. Configuration SHA-256
  `ba2c1e99183cc124bb664745dfd1b4cbabbd2d4328cc35754e9e4da044606007`
  and single-host observation
  `cd0b849e206124e11996581c81dcc13da9d11ee3caa1c8176b5525dfead271a6`
  (file SHA-256
  `733af591c5366670a1aba79581648f064b8dccbd50d87b2080d139eb018329f0`)
  pass 3/3 physical and 6/6 failure rows. Two builds were byte-identical at
  wheel SHA-256
  `32e5784ed210f9a62de015a71c18c3fe302f897761b4d740563afb04e9352cab`,
  and the installed CLI reproduced the receipt. The thresholds were selected after
  exploratory work, the lattice is not equilibrated, and the integrator is not
  independently maintained. The receipt therefore remains development
  evidence requiring a fresh holdout, two-host reproduction, and independent
  review; it does not supersede the rejected SETTLE receipt or establish
  liquid properties, accepted long-time drift, PME, scientific/product
  validity, or P2 completion;
- bounded deterministic CPU `float64` explicit-solvent preparation that binds a
  frozen OpenMM Force Fields Amber TIP3P/Joung--Cheatham Na+/Cl- source snapshot
  and materializes water/ion atoms, residues, bonds, angles, nonbonded values,
  intrawater exclusions, rigid-water SHAKE/RATTLE constraints, full 3D
  orthorhombic PBC, neutrality, species molarity, minimum-clearance checks, and
  a canonical placement trace. Neutralized preparations are exercised through
  direct Ewald, constrained NVE, and bit-exact checkpoint/restart. The
  SHA-256-ordered lattice is not minimized or equilibrated; source transcription,
  liquid properties, ion behavior, energy/force parity, two-host reproduction,
  and scientific/product use remain unvalidated;
- bounded CPU `float64` canonical-ensemble MD using constrained BAOAB Langevin
  NVT and an optional isotropic molecular-centre Monte Carlo NPT barostat. A
  domain-separated SHA-256 counter stream, mutable orthorhombic cell, complete
  SHAKE/RATTLE state, barostat proposal/acceptance rows, energy/coordinate/
  volume/finite-difference molecular-pressure traces, and trajectory/barostat
  hash heads are checkpoint-bound for bit-exact same-runtime restart. A separate
  all-step analyzer reports initial-positive-sequence autocorrelation, effective
  sample size, normal-approximation confidence intervals, target bias,
  constraint residuals, barostat acceptance, exact restart, and every failed
  metric row. This implementation has no accepted equilibration/production
  protocol, external ensemble comparison, liquid-property evidence, two-host
  reproduction, CPU/GPU parity, or scientific/product promotion;
- bounded all-step NVE drift analysis that requires `trajectory_stride=1` and
  a genuine independently executed pause/resume segment. It retains every
  energy, kinetic-temperature, linear-momentum, current constraint-residual,
  frame, coordinate and velocity digest observation; reports max/RMS energy
  and momentum drift plus energy-drift slope; and preserves all nine
  predeclared threshold/restart metric rows including failures. Passing
  caller-supplied thresholds is not an independent NVE acceptance result,
  two-host reproduction, force-field validation, or scientific/product claim;
- bounded component-energy central-difference force diagnostics and
  non-periodic configurational virials, with every perturbation retained and
  periodic virials fail-closed;
- a separate versioned reference-forcefield extension with ordered-star
  harmonic out-of-plane improper energy/forces and bounded deterministic
  symmetric degree-relaxed equal-weight distance-constraint projection, plus
  projected Armijo minimization with tangent-force convergence and exact
  checkpoint/restart; it is not mass weighted, scientifically validated, or
  product enabled;
- bounded non-periodic CPU `float64` polar Generalized Born transfer energy and
  exact forces using caller-supplied fixed effective Born radii, plus a combined
  v2 evaluator and optional constrained-minimization integration with exact
  solvation-parameter-bound checkpoint/restart; radius estimation, nonpolar
  solvation, salt/ions, periodic solvent, independent validation, and product
  promotion remain unavailable;
- a frozen, execution-disabled CPU minimization validation protocol with 14
  ordered unsolvated, constrained, fixed-Born constrained, checkpoint, and
  fail-closed cases; 10 predefined metrics, all-case failure accounting, exact
  implementation-source identities, and independent-reference requirements are
  bound before results; a separate exact materializer converts all 11 fixtures
  and 14 cases to deterministic CPU float64 v1/v2/fixed-Born runtime inputs,
  checkpoint-pause plans, and failure injections without evaluating physics or
  collecting results; a separately source-bound standard-library reference now
  independently implements constraint/tangent-force projection, fixed-Born,
  bounded backtracking, fail-closed identities, and exact checkpoint/restart,
  while test-only comparisons remain implementation checks rather than
  validation results; a frozen Ed25519 independent-review attestation
  contract now requires author/reviewer identity separation, complete ordered
  checks and limitation acknowledgements, an out-of-band trusted reviewer key,
  and bounded freshness; separate frozen CPU-only, network-disabled execution-
  environment and failure-inclusive result-receipt contracts bind the exact
  14-case/10-metric order and both operational/independent input identities,
  but no production attestation, trusted reviewer key, authorization receipt,
  environment/result receipt, result, or scientific promotion exists;
  a separate single-run Ed25519 authorization contract now binds a verified
  nonexpired review, pairwise-distinct operator, exact code/runner/dependencies,
  both receipt contracts, 24-hour maximum validity, revocation inputs, and a
  one-time nonce, but bundles no operator key, receipt, or nonce reservation;
  a local POSIX reservation primitive now re-verifies the raw signed review and
  authorization chain before consuming the nonce exactly once as a canonical
  mode-0600 record beneath a caller-provisioned mode-0700 root using `O_EXCL`,
  file `fsync`, and directory `fsync`; it has no release/delete API and bundles
  no production root, key, signed artifact, reservation, or execution; a
  separate run-start primitive re-verifies that full chain and durable record,
  observes the exact CPU-only deterministic process and network namespace,
  verifies a maximum-five-minute operator-signed network-isolation attestation,
  and atomically persists one canonical mode-0600 secret-free environment
  receipt under a separate private caller root; it creates no isolation,
  bundles no production key/attestation/root/receipt and authorizes no
  validation, fitting, or claim; the stdlib-only bootstrap now measures the
  active Python executable and standard library, OpenSSL executable, and every
  `RECORD`-declared cryptography/NumPy/Torch payload before Engine v2 or those
  dependencies are imported, and run-start plus the runner remeasure the exact
  six signed rows; a bounded failure-inclusive runner and atomic result writer
  retain complete ordered operational and independent-oracle coordinate traces
  in the receipt, including canonical binary64 raw/evaluated coordinates for
  every evaluation, per-step identities and coordinate digests, whole-trace
  digests, exact counts, and accepted-energy ledgers. A separate Ed25519 result-
  review contract fully revalidates one exact receipt, binds all fourteen case
  outcomes and retained/missing metric dispositions, and derives ordered trace-
  and step-level dispositions before preserving an explicit accepted or rejected
  decision under a caller-provided, role-separated reviewer public key. The
  refrozen v2.1 comparison contract aligns every evaluation under frozen coordinate and
  energy thresholds and binds exact uninterrupted/paused/resumed evidence for
  three checkpoint cases. Internal half-tolerance projection convergence
  headroom leaves the declared acceptance threshold unchanged, and the
  non-production implementation check passes all 14/14 rows, including both
  fixed-Born cases. This
  is not an accepted production trajectory comparison and bundles no key,
  attestation, production receipt, human approval, or scientific evidence. The
  exact bootstrap entrypoint now accepts
  only bounded canonical input, rebinds the signed nonce, author, source, and
  dependency identities before import, reloads reviewer/operator anchors only
  from the fixed external root-owned mode-0600 trust store, rechecks the fixed
  supervised evaluator subprocess runtime, and finalizes the result receipt in the same verified
  process. It remains fail-closed without externally provisioned production
  trust, signed artifacts, private roots, and a reserved nonce;
- a frozen CPU reference energy/force contract-validation protocol with exact
  synthetic case identities, predefined tolerances, retained failure rows, and
  a closed execution/parameter-fitting authorization gate, plus exact fixture
  materialization and a source-bound standard-library-only analytic oracle that
  collect no validation result, plus a frozen signed independent-review
  attestation contract that requires author/reviewer separation and an
  out-of-band trusted reviewer key, and a separate single-run authorization
  receipt contract with operator separation, 24-hour expiry, revocation inputs,
  and one-time nonce semantics. Both artifacts use Ed25519; active verifier
  trust anchors contain exact 32-byte public keys only and reject private or
  symmetric verification material. Frozen CPU execution-environment and
  failure-inclusive result-receipt schemas for all 27 cases and 59 variants,
  and a local POSIX `O_EXCL`/`fsync` one-time nonce-reservation primitive that
  re-verifies both raw signed artifacts before durable consumption, followed by
  a run-start primitive that re-verifies the full chain, observes the live
  CPU-only deterministic process, verifies a short-lived operator-signed
  network-isolation attestation, and atomically persists a secret-free
  environment receipt, followed by a bounded CPU float64 runner that re-reads
  and re-verifies that receipt and its exact code, source, dependency, and
  artifact bindings—including a read-only Git clean-checkout proof for the
  observed `HEAD` and frozen reference-
  evaluator source—atomically consumes a one-time runner-start marker, and
  retains every result or failure for the exact 27-case/59-variant matrix in
  memory under a POSIX-interrupted 120-second materialization/evaluator/oracle
  budget, followed by a failure-inclusive
  result writer that re-verifies the raw signed chain, live environment receipt,
  runner-start marker, and exact observation before atomically persisting one
  canonical private mode-0600 receipt. Its reader requires an out-of-band exact
  receipt hash plus external revocation/supersession inputs; no receipt signature
  or same-UID pathname/inode replacement resistance is claimed, although changed
  content is detected against the out-of-band hash. The exact module command accepts
  only a bounded canonical JSON request without trust keys on standard input;
  reviewer/operator anchors come only from an externally provisioned, fixed-path,
  root-owned mode-0600 trust store that the repository does not bundle. It keeps
  trust material out of stdin, argv, and responses and performs environment
  receipt creation, the run, and result finalization in the same verified process.
  It requires that trust store plus a clean
  source checkout with Git metadata and fails closed when invoked only from an
  installed wheel. A separate provisional minimization result-review contract
  fully validates the fourteen-case writer receipt, reverifies the raw signed
  pre-execution review and authorization role chain, and derives accepted or
  rejected dispositions from exact status, runtime/oracle/result identities,
  per-case-bounded nonnegative integer counts, finite energy ledgers recomputed
  against retained energy metrics, metric evidence, and complete ordered
  operational/independent coordinate traces with per-step identity and digest
  dispositions. Its
  verifier accepts only canonical JSON byte transport and requires explicit
  current revocation and receipt/result-review supersession inputs.
  The `0.3.0a1` identity refreeze binds applicability record `1.2.0`
  (`cfc9d2a5f9ff4ee2539c3e15a8c0519788e26c447a71de4e994c53d4f78760a6`),
  energy/force protocol `1.2.0`
  (`0e34905c635b33b47a26cb459a93840166fc222c663d73af43d40d36814d7ee2`),
  and artifact binding `1.2.0`
  (`b3341f3b98e29594cfcd727353553efa466116f275f5250c4ae944d624ef62b0`).
  This is source/dependency lineage, not a production result or scientific
  acceptance.
  No trusted key, production receipt,
  reservation or artifact root, production nonce reservation, production
  environment receipt, runner start/result receipt, authorized production
  execution, independent result review, or scientific acceptance is bundled;
- a lazy, offline-only adapter pinned to `OpenMM==8.4.0.post2` and its
  `Reference` platform. It maps all 47 supported energy/force variants, retains
  all 12 Engine-contract failures as N/A, and re-evaluates every coordinate in
  the eight supported minimization traces while retaining six fail-closed
  traces. Canonical receipts bind complete OpenMM distribution/native/runtime
  identity, fixed-Born self/pair terms, and recomputed nested errors. A separate
  installable `betelgeuze-engine-v2-openmm-materialize` workflow executes both
  complete frozen matrices, retains all success/failure rows in one canonical
  mode-0600 no-overwrite artifact, including Engine iteration/rejection counts,
  constraint/tangent-force metrics, energy/coordinate traces, and checkpoint
  equality, and can structurally verify or exactly re-execute it. The workflow
  never accepts a private key and fixes
  `production_protocol_execution=false`, independent review and two-host
  reproduction to false, and `claim_safe=false`;
  the separate installable
  `betelgeuze-engine-v2-openmm-native-minimization` workflow executes the
  OpenMM L-BFGS endpoint for all eight supported cases, retains all six
  expected fail-closed rows, and re-evaluates every endpoint with Engine v2 at
  identical coordinates. Current `1.3.0` configuration SHA-256 is
  `9189afe3a01a7eb8ee2c26e8b233db6c2250a14317f8498e34303c1c2b4fdf51`.
  A 2026-07-24 local receipt under superseded `1.0.0` configuration
  `6465f726c408e6df2dd15d318a4cdfc57a8b2edd271ddaa578edcc336110017e`
  retained all 14 rows and passed 8/8 same-coordinate
  energy/force mappings and 8/8 energy-nonincrease checks, but only 6/8 frozen
  endpoint-health checks: the two fixed-Born constrained cases exceeded the
  tangent-force bound after final constraint projection. Receipt SHA-256 is
  `7e5b3454afc41f9954f71dfc3b0b274906323f15fd8ea6630bfcc1e95ce95b7c`;
  status is explicitly rejected, endpoint/trajectory equivalence is not
  claimed, and no S0 gate is opened;
  the installable
  `betelgeuze-engine-v2-openmm-fixed-born-disposition` workflow binds those
  exact rejected inputs and executes a frozen 2-case/16-probe diagnostic with
  OpenMM minimizer callback, restraint-stage, energy, constraint-error, and
  pre/post projection traces. Current v5 configuration SHA-256 is
  `6182cecaa21d5d191baacda1bc9cf7ae7d3cb9eb8b2ca0217757cb23af37c281`.
  The historical receipt below binds v2 configuration
  `ac601f3cfedd68e24b6507778ea36c1676fb24cacf89c7c2fa73848bf3c68045`;
  that lineage retains the rejected v1 observer configuration
  `67f1a6025155d8f62cd3d1aa7da2803e229a4dce7871050db6c323f531f0b8c1`
  and adds only a separate no-reporter bitwise control. Actual receipt
  `870f1ea247da4b0232f22804298e75d554af511da18924a7ba49c1c703f003f2`
  reproduces both controls exactly and classifies a final-constraint-projection
  tradeoff: tangent force passes before projection while the constraint
  residual fails, then the residual passes while tangent force fails after
  projection. The 64–1024 iteration and `1e-8`–`1e-12` tolerance probes do not
  remove it. This completes a bounded failure disposition, not endpoint
  acceptance or causal proof; the 6/8 rejection and S0 block remain;
  a separate claim-closed
  `betelgeuze-engine-v2-openmm-constraint-stationarity` candidate uses a strict
  `1e-14 Å` internal constraint projection and accepts numerical polish only
  when tangent force strictly decreases while energy stays within
  `1e-10 kcal/mol` of the best accepted energy. Candidate and same-coordinate
  OpenMM configuration SHA-256 values are
  `5642654a25a2d024f7cb8c1de024815f6bf6032b06f6c57509d7b784b708f708`
  and `69f5168dbf7bcaa9f4ff85f9e2e9f7800b8b21685110000a90c909d552eab6db`.
  The historical single-host candidate receipt
  `16a4db9ca59ad969c63bb896a8bc3cb3310e7b5cc5f5e94e9a3b2dbf59d79f70`
  binds superseded comparison configuration
  `722d319c865eb15dd12296dee998b26332e2c1ad8edf3e5e6611914b960529d1`
  and passes only the four applicable constrained aliases. Maximum total-energy
  and force errors against OpenMM Reference are `1.07e-14 kcal/mol` and
  `2.40e-14 kcal/mol/Å`; both evaluators meet the unchanged `1e-8` absolute
  tangent-force bound at a constraint residual below `8.66e-15 Å`. The other
  ten frozen rows are explicitly excluded, and validation, S0, two-host, and
  independent-review claims remain false. A separate installed
  `betelgeuze-engine-v2-minimization-stationarity-successor` observation path
  then reuses all fourteen frozen inputs: four v1 rows keep their prior paths,
  four constrained rows use the candidate and a Torch/NumPy-free tuple oracle,
  and six fail-closed rows preserve exact dispositions. Current `1.3.0`
  configuration SHA-256 is
  `edae2c0ff83761426185e5eb269b1e30ea5dd5446c93121eef94163af284c237`.
  The single-host candidate observation
  `18c6d617781e93c903332352d6f66e8eb2897e2c965035cd6f437d0324d3d1b9`
  binds superseded configuration
  `5c39aa346531d8f3cff378361367f7ff236f2c94c0c4bb3db66a28ec8e27d4f5`
  and passes 14/14 rows and 3/3 operational/oracle restart comparisons while
  retaining complete energy, coordinate, and failure traces and binding the
  4/4 OpenMM same-coordinate candidate. It is not a production receipt;
  two-host reproduction, independent review, native OpenMM L-BFGS repair, and
  S0 remain false;
  a separate v7
  Ed25519 verifier freshly checks both Engine result-review chains, the exact
  OpenMM materialization, both component/trace receipts, and the native
  endpoint receipt before signing one host-scoped comparison. On a rejected
  endpoint it also requires and binds the exact disposition receipt,
  configuration, physics projection, completeness, and classification; an
  accepted endpoint forbids that failure-specific input. The current 6/8
  observation therefore produces a signed `rejected` review that retains both
  failed fixed-Born case IDs and cannot report the full external comparison as
  accepted. Host-review contract SHA-256 is
  `f7b57f08afd44e0ab7848c8ce75b08560d00cf381895aaeaf251e23cd3b81c7a`.
  A frozen v6 final S0 bundle contract now freshly reverifies exactly two such
  host inputs, requires distinct host/CPU/session/custody/artifact/nonces and
  exact commit/source/dependency/runtime/seed plus energy-force, trace, and
  native-endpoint physics equality. It rejects either host unless native
  endpoint health is accepted with 8/8 cases, no failed case IDs, and the
  failure-specific disposition path marked not applicable, then verifies a
  role-separated final Ed25519 human approval. S0 contract SHA-256 is
  `5eb28543fa9b11ac3559c20c72955c6c9c9adec757869975c71ef0207beee3a4`.
  A verified bundle can establish
  only the frozen synthetic S0 protocols and admission to S1; chemistry,
  fitting, benchmark, product, customer, and broad scientific claims stay
  closed. The installable `betelgeuze-engine-v2-s0-review` command validates a
  secret-free detached signing request, emits the exact canonical bytes for an
  external/HSM signer, and verifies a returned signature with a public key
  before attachment; it has no private-key option and never overwrites output.
  No host evidence, trust key, final approval, or external custody is bundled,
  so the repository's static S0 decision remains false;
- deterministic bounded torsion/rigid docking proposal and search scaffolds,
  including a receipt-bearing molecular-graph materializer that admits only
  non-ring, non-terminal heavy-atom single-bond bridges and excludes narrow
  amide/sulfonamide/phosphoramidate patterns. This bounded heuristic preserves
  seed bond lengths/angles but is not full resonance perception, ring closure,
  a torsion-energy model, or validated conformer generation. The docking scorer
  surfaces retain candidate-level score-term receipts and an explicit-parameter
  CPU `float64`
  diagnostic scorer that separates cross LJ, screened Coulomb, signed ligand
  internal strain delta, and VDW-overlap penalty. The same scorer atomically
  emits exact pose/problem/parameter-bound contact diagnostics for every
  receptor--ligand pair and every topology-admitted ligand nonbonded pair,
  including worst overlap pairs and attractive/repulsive partial-charge
  decomposition. A separate chemistry-aware validity API gates both contact
  scopes, signed strain, and repulsive Coulomb against explicit caller policy;
  its thresholds are unfitted, aromatic/stereo coverage is fail-closed, metals
  and receptor cofactors remain outside scope, and `claim_safe=false`. A
  failure-inclusive applicability API now inventories all canonical-input,
  chemistry, parameter, and capacity blockers before construction instead of
  losing later blockers at the first exception. It returns the exact assessment
  plus either an admitted diagnostic scorer or an explicit abstention;
  aromatic/stereo inputs remain interaction-incomplete and all admissions
  remain uncalibrated, scientifically unvalidated, and claim-closed. The docking
  surface also provides a fit-only pairwise
  ranking-calibration contract with strict identity-overlap audit and
  failure-inclusive all-case/target-family evaluation, tie-invariant pose-level
  average-precision PR-AUC over successfully scored/labeled poses, explicit
  all-pose coverage/failure denominators, and deterministic case-cluster
  bootstrap intervals. A bound, claim-closed confidence evaluator reports raw
  logistic top-1/runner-up margin diagnostics (Brier, fixed-bin ECE,
  reliability bins, threshold abstention/coverage/risk, and tie-inclusive
  selective-risk curves) overall and per family while retaining failed and
  single-success cases in all-case/all-pose denominators. It explicitly lacks a
  disjoint probability-calibration fit and cannot promote a confidence claim;
- an installable bounded ligand-preparation boundary,
  `betelgeuze-engine-v2-prepare-ligand`. The optional `chemistry` extra pins
  RDKit 2025.9.6; the adapter also recognizes the frozen RDKit 2022.09.5
  runtime already used by repository evidence. It accepts one SMILES token or
  one SDF V2000 record, rejects multiple fragments, radicals, isotopes,
  unsupported elements and charges, requires explicit tetrahedral/double-bond
  stereo by default, records aromaticity and ring membership, enumerates
  bounded diagnostic protomer/tautomer candidates, adds explicit hydrogens,
  and preserves input coordinates or generates a deterministic ETKDGv3/UFF
  conformer. If OpenFF Toolkit is installed, the adapter performs an exact
  RDKit-to-OpenFF-to-RDKit graph round trip; otherwise it records
  `openff_toolkit_unavailable`. Output is a mode-0600 no-overwrite canonical
  Engine v2 system with a hash-bound preparation receipt, ready to pass
  directly to the redocking CLI. No calibrated pKa selection, partial charge,
  force-field parameter, scientific applicability, or product claim is made;
- an installable single-command prepared-input redocking boundary,
  `betelgeuze-engine-v2-redock-diagnostic`. It accepts only exact Engine v2
  canonical receptor and ligand JSON, an explicit spherical pocket, and bounded
  search arguments. The command binds raw file hashes to a typed
  `DockingProblemInput`, recenters the receptor, removes ligand input
  translation, and applies a fixed non-identity orientation. A verified
  RDKit/OpenFF ligand-preparation receipt materializes an authenticated
  bridge-only molecular torsion tree, samples later candidates with independent
  uniform torsions and Shoemake Haar-uniform SO(3) rotations, then selects a
  translation from a bounded receptor-steric-field lattice. The field plan is
  bound to the exact receptor, ligand, pocket, search space, fixed diagnostic
  radius profile, grid, and hard capacities. Candidate zero remains the zero-
  torsion, identity-rotation, zero-translation baseline; later candidates cycle
  over orientation-conditioned nonzero sites ordered by deep overlap, overlap
  count/penalty, and pocket-boundary penalty. Every success or failure row
  preserves all sampled torsion values, rotation matrix, translation, RNG
  states, selected field site and metrics, plan digest, and sampling-state
  digest. Generic canonical input uses the uniform-volume translation fallback;
  an explicit zero-torsion budget retains rigid Haar rotations while still using
  the prepared steric field when the preparation receipt verifies.
  The same verified receipt selects the uncalibrated
  `interpretable-pose-scorer-v0`: four fixed-radius geometry terms plus
  reference-relative bond, angle, and rotatable-dihedral displacement,
  explicit-H directional D-H-A hydrogen-bond reward, and hydrophobic-contact
  reward. Every candidate retains the exact nine-term breakdown, scorer and
  feature fingerprints, and all scientific blockers. The same verified gate
  selects chemistry-aware validity v2, which binds the preparation source to
  the transformed topology and evaluates element-scaled receptor penetration,
  1-2/1-3-excluded ligand self-clash, reference-relative bond/angle geometry,
  and declared atom/double-bond stereo preservation. Generic canonical ligands
  remain on the five-term element-geometry diagnostic and geometric validity
  with explicit missing-preparation/scorer/validity/refiner blockers. The
  verified gate also enables a default six-step deterministic local refiner.
  Each iteration evaluates signed x/y/z translations and rotations plus signed
  rotations about every bounded bridge-only rotatable bond, accepts only a
  strict score decrease, and otherwise reduces all step sizes. Every candidate
  row retains the full receipt: scorer/refiner/torsion-plan identities,
  accepted and rejected move counts, score and coordinate-hash traces,
  term deltas, and bond/angle constraint residuals. Global torsion sampling is
  a bounded bridge heuristic without ring or macrocycle closure and is not
  validated conformer generation. A combined candidate × step × move cap of
  250,000 evaluations rejects oversized refinement requests before search. The
  command
  retains every candidate success/failure row and writes mode-0600 no-overwrite
  JSON containing receptor-frame Top-K coordinates. It performs no chemistry
  preparation, calibrated interaction-energy-grid placement, force-field scoring
  or force/gradient minimization, calibrated ranking, or public benchmark. The
  fixed-radius steric field omits electrostatics, hydrogen bonding, desolvation,
  water/cofactor response, and receptor flexibility and is not scientifically
  validated. The
  local objective is the uncalibrated nine-term score, not physical energy, and
  exposes no analytic force or tangent-force residual. Validity v2 does not
  assign partial charges, independently verify
  protonation/tautomers, recompute absolute stereo labels, or validate aromatic
  planarity; every receipt keeps
  `scientifically_validated=false`, `benchmark_validated=false`, and
  `claim_safe=false`;
- a failure-inclusive rigid-body public diagnostic that derives one redocking
  pocket center from the lowest-index graph-matched native reference, applies a
  fixed non-identity rotation to the seed conformer before proposal generation,
  scores every generated pose with an element-radius geometry heuristic, applies
  deterministic rigid coordinate descent to the initial diverse score Top-K,
  then re-ranks and records the complete refinement trace, full validity, direct
  receptor-frame symmetry-aware RMSD, Top-1/Top-5, and oracle-best generation
  diagnostics. It retains every search/refinement/evaluation failure. It has no
  torsion sampling, supported-force-field refinement, charge-aware physics,
  fitted score, disjoint holdout status, external baseline, or claim-grade
  benchmark result;
- a separate failure-inclusive flexible four-case diagnostic that embeds the
  all-bond torsion materialization receipt, samples candidate zero at zero
  torsion and later candidates from deterministic independent uniform torsions,
  then adds a fixed element-radius ligand nonbonded self-overlap term (excluding
  1-2/1-3 pairs) before the same validity/RMSD evaluation and Top-K rigid
  refinement; final score-order diversity selection excludes invalid poses. It
  has no torsion-energy or bonded-force-field strain term, torsion refinement,
  force-field refinement, holdout status, or docking claim;
- a fail-closed, non-executing same-input external-baseline work-order contract.
  It verifies exact prepared receptor/ligand PDBQT bytes against the frozen
  four-case sources and binds preparation tool/version, executable,
  configuration, container, pocket-definition, and Vina/GNINA/Smina binary
  identities. Each engine receives the same prepared hashes, native-defined
  receptor-frame center, 22.5-A cube, seed, exhaustiveness, mode count, and one
  CPU. Native coordinates may define only the box center and are declared
  forbidden from ligand preparation. This does not bundle prepared files or
  engines, launch a binary, validate a result, establish a statistical holdout,
  or complete an independent rerun;
- a claim-closed public split-provenance contract for caller-provisioned PDBbind
  v2020 fit data, CASF-2016 evaluation data, and the published 308-case
  PoseBusters Benchmark. It freezes official source, citation, access, license,
  endpoint, and case-count facts; the official PoseBusters 308-ID file is bound
  by raw SHA-256 and canonical case-ID projection. Case manifests carry exact
  receptor/ligand/scaffold/protein-chain-set identities, release dates, target
  families, cofactors, and supported/unsupported chemistry dispositions. An
  exact Smith-Waterman/BLOSUM62 tool receipt reports maximum fit similarity over
  all protein-chain pairs and similarity strata. The final link rechecks the
  generic fit/evaluation leakage audit and binds report all-case and target-
  family denominators. It accepts no PDBbind terms, bundles no dataset, runs no
  sequence comparison or benchmark, and includes no result or independent
  review;
- an installable public pose-ranking corpus intake above that in-memory
  contract. It accepts only canonical, caller-pinned PDBbind-v2020
  `fit`/CASF-2016 `validation`/PoseBusters-308 `test` manifests and three
  pairwise all-chain sequence-identity receipts. It recomputes fit↔validation,
  fit↔test, and validation↔test case/PDB/target/receptor/ligand/scaffold/
  sequence overlap; freezes a maximum 0.90 sequence-identity policy; requires
  fit→test and validation→test release ordering; and requires complete official
  CASF and PoseBusters case sets. Inputs use bounded no-follow reads and exact
  file/payload hashes; output is canonical mode-0600 and no-overwrite.
  Configuration SHA-256 is
  `4972e41765076e09b7bbec43b7e506dede6ab48b01b173f62cd73a749f694681`.
  No production receipt exists because licensed PDBbind/CASF manifests and
  executed sequence receipts have not been supplied. The intake contains no
  score, fit, validation/test label, model, metric, or claim;
- an installable PDBbind-fit/CASF-validation calibration-partition intake
  gated by that passing corpus receipt. It accepts only canonical,
  caller-pinned `PoseRankingCalibrationPartition` files with exact
  case/pose/scorer/preparation identities, recomputes both public-manifest
  bindings and pose-level fit/validation leakage, and retains every success,
  failure, positive, negative, case, and pairwise-uninformative denominator.
  Validation labels are evaluation-only and no test-partition argument exists.
  Configuration SHA-256 is
  `c4b423063a36f38d7f6f098a38c7ea54b078c25f3cc04d060ae88638902ff8be`.
  No production receipt exists while the upstream corpus intake is absent;
  fitting, model selection, test evaluation, metrics, review, and claims remain
  false;
- an installable calibration training-view boundary gated by that passing
  partition-intake receipt. It includes every `status=success` fit row
  unchanged in an embedded `PoseRankingCalibrationPartition`, excludes only
  `status=failure` rows from executable fitting, and preserves every excluded
  row in a hash-bound disposition. It recomputes training-view/CASF leakage and
  offers a guarded deterministic-fit bridge without using validation labels or
  accepting a test partition. Configuration SHA-256 is
  `e5e202d10420b5a557b1227aa0f7735433ebaeadc1656f6b981c14453aeb25b8`.
  No production receipt exists while genuine upstream corpus inputs are absent;
  no production fit, selected model, metric, review, or claim is implied;
- an installable PDBbind-fit/CASF-validation model-selection boundary above
  that verified training view. A canonical workflow-local preregistration
  manifest freezes every deterministic fit configuration and the CASF
  bootstrap configuration before this execution evaluates labels. Every
  candidate fits only the embedded PDBbind
  rows; CASF is used only for failure-inclusive all-case/all-pose,
  target-family, confidence-interval evaluation and deterministic selection by
  average-precision PR-AUC, then Top-1, Top-5, and candidate ID. All candidates
  and primary metrics must complete or no model is selected. The frozen
  selection-policy SHA-256 is
  `1905b14e37da44293483b9b31a06b2653849b2e986dc75b9e4ad53aa0bc4b9d9`.
  The command accepts no PoseBusters test score partition and binds source,
  Python/Torch runtime, input, config, model, report, and receipt identities in
  a mode-0600 no-overwrite artifact. Two builds were byte-identical at wheel
  SHA-256
  `d338d81d14d08ca7c07f74629ac2b98f94d389f651e44e2b143fb487bfcf4bd3`,
  and the installed CLI/import boundary was verified outside the checkout.
  The receipt does not prove independently timestamped/signed preregistration.
  Genuine licensed inputs remain absent, so no production fit/validation
  receipt, test result, calibrated confidence, independent rerun/review,
  scientific validation, or docking claim exists;
- an installable, extraction-free PoseBusters 308 archive intake. The command
  requires the exact published Zenodo ZIP and journal 308-ID bytes as local
  regular files, checks their frozen hashes and sizes, audits all 2,570 ZIP
  entries and 428 case directories under hard bounds, verifies archive metadata,
  and CRC-streams the four required artifacts for every selected case. It emits
  exactly 308 success/failure rows and 1,232 artifact identities in a canonical
  mode-0600 no-overwrite receipt that supports exact reexecution. It performs no
  fetch, license acceptance, extraction, pose generation, scoring, or benchmark;
  the archive and receipt are not bundled and `claim_safe=false`;
- an installable, extraction-free PoseBusters 308 corpus audit. It reexecutes
  the exact intake and records all-case parser, heavy labeled-graph, raw
  directional-bond, raw aromatic-bond, element/formal-charge, ligand-capacity,
  metal, and non-water-cofactor inventories with Wilson 95% intervals. It does
  not perceive aromaticity or atom stereo, parameterize molecules, prepare or
  generate poses, score, run an external engine, or execute a benchmark;
- an installable, failure-inclusive internal PoseBusters canonical-preparation
  boundary, `betelgeuze-engine-v2-posebusters-internal-prepare`. It reexecutes
  the exact intake and corpus audit, uses native heavy coordinates only for the
  pocket centroid, parses the receptor without materializing `CRYST1`
  periodicity, prepares the start ligand through the receipt-bearing RDKit
  adapter, and writes source-bound canonical receptor/ligand JSON. Preparation
  failures, upstream failures, and chemistry-scope abstentions remain in the
  all-case denominator with Wilson 95% intervals;
- an installable, failure-inclusive internal cohort executor,
  `betelgeuze-engine-v2-posebusters-internal-execute`. It exactly re-verifies
  the preparation receipt and private artifact tree, derives an authenticated
  deterministic seed per case, runs the prepared redocking diagnostic for each
  prepared row, and writes one canonical report artifact per completed case.
  All upstream/abstention/execution-failure rows remain in the denominator, and
  verification exactly reexecutes both preparation and docking. This boundary
  records internal validity only; RMSD is a separate downstream gate;
  `benchmark_executed=false` and `claim_safe=false`;
- an installable internal direct-RMSD evaluator,
  `betelgeuze-engine-v2-posebusters-internal-rmsd`. It reexecutes the complete
  internal batch, maps RDKit-prepared heavy atoms back to the exact start SDF,
  enumerates every bounded native-to-start heavy-connectivity isomorphism, and
  computes receptor-frame Top-1/Top-K RMSD without ligand alignment. Every
  blocked or failed execution row remains in the all-case denominator, and all
  rates include Wilson 95% intervals. This is connectivity-symmetry diagnostic
  evidence, not complete atom-stereo symmetry or equivalence to the pinned
  PoseBusters oracle. External validity/RMSD, target-family strata,
  runtime/memory metrics, second-host reproduction, and independent review are
  still missing, so
  `benchmark_executed=false` and `claim_safe=false`;
- an installable all-case internal-pose PoseBusters oracle,
  `betelgeuze-engine-v2-posebusters-internal-oracle`. It exactly reexecutes the
  internal preparation, redocking, and direct-RMSD chain; reconstructs RDKit
  conformers from the exact raw start-SDF topology and source-bound prepared
  coordinates without SDF coordinate truncation; and applies the pinned
  PoseBusters 0.6.5 `redock` full report with batch evaluation and per-pose
  fallback. The adapter requires a complete raw/prepared atom bijection, so
  added or missing atoms fail closed instead of disappearing from validity.
  Complete oracle report rows, physical-validity flags, oracle RMSD,
  internal/oracle RMSD deltas, adapter failures, pose failures, and blocked
  upstream rows remain authenticated in the original all-case denominator.
  This is an executable evidence carrier, not a completed public result: no
  official 308-case production receipt is bundled. Target/chemistry strata and
  runtime measurements are supplied only by the separate claim-closed
  companions below; official-cohort execution, same-input external-engine
  comparison, second-host rerun, bundle validation, and independent scientific
  review are still missing. Therefore `benchmark_executed=false` and
  `claim_safe=false`;
- an installable runtime/RSS observation companion,
  `betelgeuze-engine-v2-posebusters-internal-oracle-runtime`. It reexecutes the
  exact deterministic oracle receipt with a payload-independent case observer,
  records `perf_counter_ns` wall duration and Linux `/proc/self/statm` sampled
  RSS at every downstream oracle-loop case boundary plus a 5 ms background
  sampler, and retains measurements for evaluated, failed, blocked, and
  abstained rows. Batch measurements cover the complete exact upstream+oracle
  reexecution; per-case measurements cover only the downstream PoseBusters
  oracle loop, not a full redocking-stage breakdown. The receipt
  binds the unchanged oracle result, exact executing source bytes, a caller-
  anchored Engine v2 wheel, Python/CPU/dependency projection, safe runtime
  variables, and batch/case measurement summaries. Measurement values are
  deliberately not claimed to be byte-reexecutable. RSS is sampled rather than
  a kernel-enforced isolated case maximum; observer overhead is not subtracted,
  and the local receipt is unsigned with no physical-host proof or second-host
  observation. Therefore `benchmark_executed=false` and `claim_safe=false`;
- an installable all-case target/chemistry stratification companion,
  `betelgeuze-engine-v2-posebusters-internal-oracle-strata`. It exactly
  re-verifies the deterministic internal-oracle chain, corpus/preparation
  artifacts, conservative observed-target clusters, and frozen RCSB/Pfam
  annotation binding, then binds the caller-pinned runtime observation.
  Exact Pfam sets are the primary target strata; incomplete annotations and
  mapping failures fall back to explicit observed-sequence-cluster strata.
  Prepared-case charge, size, elements, aromaticity, ring, and stereo come
  from verified canonical prepared ligands; preparation-unavailable cases use
  the corpus-audited native ligand as an explicit fallback. Receptor
  metal/cofactor context comes from the all-case corpus audit. Preparation failures,
  chemistry abstentions, blocked cases, and unknown target OOD status remain
  in primary strata and Wilson 95% denominators. Per-stratum runtime covers
  only the downstream oracle loop and RSS remains sampled. No official
  production result, training-manifest OOD audit, second-host observation,
  independent review, or public bundle validation is claimed; therefore
  `benchmark_executed=false` and `claim_safe=false`;
- an installable second-host internal-oracle reproduction work-order and
  comparison companion,
  `betelgeuze-engine-v2-posebusters-internal-oracle-reproduce`. It
  preregisters exact baseline oracle/runtime/stratification receipt roots, the
  Engine v2 wheel, distinct baseline/external host identities, role-separated
  operator/executor identities, a single-use nonce, and registration time. A
  result requires distinct external runtime and stratification receipt roots,
  the same wheel, exact oracle receipt identity, and exact equality of every
  runtime-free case/stratum/metric field, including failure and abstention
  rows. Runtime and sampled-RSS values are reported as separate observations
  and ratios without an invented performance-equivalence threshold. The
  external runtime observation must payload-bind a canonical execution
  attestation whose host identity, execution operator identity, single-use
  nonce, and observed UTC match the work order exactly; unattested or
  replayed-nonce observations fail closed. Each receipt chain may also carry a
  detached Ed25519 custody signature over the exact oracle, runtime, and
  stratification digests, verified against an out-of-band trust anchor; partial
  signature material fails closed and the verifier never accepts signing keys.
  Attested host identity and nonce single use remain self-declared, so neither
  form proves a physical host. Therefore even a passing comparison retains
  `physical_host_independence_reviewed=false`,
  `independent_external_rerun_present=false`, `benchmark_executed=false`, and
  `claim_safe=false` pending independent custody and scientific review;
- an installable same-input engine comparison,
  `betelgeuze-engine-v2-posebusters-same-input-compare`. It binds the internal
  PoseBusters oracle evaluation and the Vina, GNINA, and Smina generated-pose
  evaluations by exact receipt digest, requires all four to name the same
  archive intake and to remain claim-closed, and compares every case under one
  all-case denominator that is the union of every case in any bound receipt.
  Cases the external engines never reached are retained as explicit
  `absent_from_receipt` rows. Per engine it reports evaluated status,
  any-valid-pose, Top-1 validity, Top-1/Top-5 symmetry-aware RMSD threshold
  hits, and Top-1 valid-and-hit with Wilson 95% intervals, plus pairwise
  internal-versus-external Top-1 agreement partitions. It regenerates no pose,
  executes no engine, and recalibrates no score. The external receipts cover
  only the strictly prepared chemistry subset, so subset selection bias,
  stratification, independent rerun, bundle validation, and scientific review
  remain open and `benchmark_executed=false` and `claim_safe=false` stay fixed;
- an installable public result-bundle validator,
  `betelgeuze-engine-v2-posebusters-validate-bundle`. It validates one
  caller-pinned bundle manifest: six required roles from archive intake through
  the internal oracle evaluation, plus optional runtime observation,
  target/chemistry stratification, and same-input engine comparison. Every
  listed receipt must be bounded mode-0600 canonical ASCII JSON carrying its
  role's schema, must self-authenticate against the manifest digest, and must
  stay claim-closed. Every declared upstream link must resolve to the receipt
  actually in the bundle, so a bundle cannot mix stages from two runs. Unknown
  or duplicate roles, shared receipt digests, a stratification without its
  runtime observation, and paths escaping the bundle root all fail closed. This
  is structural completeness and linkage only: no physics is re-executed, no
  metric is recomputed, the manifest is unsigned, and
  `benchmark_executed=false` and `claim_safe=false` stay fixed;
- an installable, extraction-free PoseBusters 308 native-geometry preflight. It
  exactly reexecutes the intake and corpus audit and records all-case fixed-
  radius receptor/ligand overlap, topology-excluded ligand self-overlap,
  native/start heavy-bond deltas, unsupported elements, and exact target-CCD
  residue-name retention. The native ligand is a crystal-pose positive control;
  the start SDF is a generated conformer, not a pose. The command performs no
  chemistry perception, force-field strain evaluation, generated-pose validity,
  docking, scoring/ranking, external oracle, or benchmark;
- an installable, extraction-free strict PoseBusters external-input preparation
  receipt. It attempts the provisional 34-case chemistry subset with pinned
  Meeko 0.7.1/RDKit 2025.9.6 defaults, never deletes unmatched residues, and
  retains all 308 prepared/failure/abstention rows. The local exact rerun
  produced 18 private receptor/ligand PDBQT pairs, 16 strict failures, and 274
  chemistry abstentions. Native coordinates define only the box center; no
  external engine, generated pose, validity oracle, scoring, or benchmark is
  executed;
- an installable, failure-inclusive prepared-ligand charge/type diagnostic over
  that exact 308-row preparation receipt. It parses Meeko `SMILES IDX` and
  `H PARENT` mappings, recomputes the same 12-iteration RDKit Gasteiger
  algorithm, merges omitted-H charge into its source parent, and retains `G0`
  macrocycle closure pseudoatoms separately. Both frozen RDKit core runtimes
  (2022.09.5 and 2025.09.6; distribution versions 2022.9.5 and 2025.9.6)
  evaluated all 18 prepared cases with zero diagnostic failures: 481 real
  PDBQT atoms and two zero-charge `G0` pseudoatoms were accounted for, every
  real atom was within the 0.0005 e three-decimal serialization tolerance, and
  the maximum delta was 0.0004979832249129013 e. Element/type compatibility and
  aromatic-carbon `A` consistency passed for all 18 cases. The two expected-
  charge vectors were bitwise identical for 481/481 atoms. RDKit 2022 and 2025
  observation payload/file SHA-256 values are
  `df57b0d48ba905e0f132b66a3b4d4fc344fffc4a40f1d78de181c0264bedba8f` /
  `b7e8b3ee7a235f63c79454af8b008230a4ed34e195dc2b85133eae21526962dd`
  and `6d3389ed55e7d47c8e0b0076c485b3f4ee7590cb3f9ddcd12db89030e92b6b50` /
  `f1a78abba41e9783a57616a71930e7bf11f6377a28592d18f2bd66128d26b5f5`;
  comparison payload/file values are
  `ab9cf4b72d3af848dd48484fcbb203268fe8d7336ec552ffe52c360dca972b5f` /
  `121bc96482cf2f73622c650dbce5da1fddc8c32f4421c185c2d4c926fadc978f`.
  Source-tree and isolated installed-wheel verification reproduced all three;
  two builds were byte-identical at wheel SHA-256
  `9d1c96336c1fa55051ab3e0fc2192d990860c644dc5f39a0685f07c39613124e`.
  This is same-algorithm serialization/version diagnostics, not an independent
  charge or AD4 typing oracle; source-SDF equivalence, receptor assignments,
  unsupported chemistry, a second CPU host, and reviewer acceptance remain
  open, so `claim_safe=false`;
- an installable, failure-inclusive independent Open Babel 3.2.1 charge and
  AD4-type implementation comparison over the same exact preparation receipt.
  It uses `OBChargeModel("gasteiger")` full-precision charges and the Open Babel
  PDBQT writer, while preserving all 308 rows and excluding only the two
  retained `G0` pseudoatoms from real-atom statistics. All 18 prepared cases
  completed without comparison failure: charge MAE/RMSE/max absolute delta
  versus the three-decimal Meeko fields was 0.0038510594375734796 /
  0.012204476318346003 / 0.18097866788513423 e, and exact AD4-type agreement
  was 476/481 atoms. The five explicit mismatches were three `SA` versus `S`
  assignments and two Meeko macrocycle `CG0` versus Open Babel `C`
  assignments. Exact-tag source inspection attributes the former to a real
  neutral-thioether acceptor-semantics disagreement (`[SX2]` override versus
  sulfur formal charge -1) and the latter to Meeko's deliberate ring-closure
  vocabulary extension. A two-version RDKit 6/12/24-iteration control also
  shows that the methylsulfone maximum charge delta is dominated by differing
  sulfur parameter-selection semantics, not iteration count alone. Receipt
  payload/file SHA-256 values are
  `7754c4b56e10d4543b064c23daaf69ab99e098fda81bfd9fbaecc8694439d943` /
  `98a5b1c654bbf388f1782519ec9e0a8de54113bcdbb16c08f541d02607342cb5`.
  Exact source-tree and isolated installed-wheel verification passed; two
  builds were byte-identical at wheel SHA-256
  `d0fc6a2acce76f2e3d23915b533528263d10e8277c0cf6feafd09e318c6d9529`.
  This closes the missing independent-implementation execution only. No charge
  accuracy threshold was preregistered, Open Babel is not a quantum charge
  oracle, the three thioether type differences and sulfone charge accuracy
  remain scientifically unadjudicated, and source-SDF equivalence, receptor
  assignments, unsupported chemistry, a second CPU host, and independent
  review remain open, so `claim_safe=false`;
- an installable, preregistration-first PySCF 2.14.0 fixed-geometry sulfur
  QM-ESP diagnostic. The frozen protocol binds the exact source SDF
  coordinates and explicit hydrogens, RHF/6-31G* spherical-basis settings,
  single-thread runtime and official wheel, four equal-weight Lebedev-110
  molecular-surface shells, same-site Meeko/Open Babel charge projections,
  failure-inclusive 308-case denominator, and every implementation and
  dependency identity before QM execution. The production observation
  evaluated the four preregistered sulfur cases with zero QM failures and 304
  explicit scope abstentions. Meeko had the lower global weighted ESP RMSE in
  4/4 cases and Open Babel in 0/4; the model differences were small and are
  descriptive only. Protocol and observation payload SHA-256 values are
  `0927260a16f1e09211fb601fade1725e21d35d221d04e69cfd2c624da7c06137`
  and `402d1795f18b7eb0c87d8537f3b427fe116c0845bf1337b21e24752cef7e52e6`.
  Exact source-tree and isolated installed-wheel observation reexecution
  reproduced the latter, and two builds were byte-identical at wheel SHA-256
  `b4564648dbf3fcb681e0b73d1dcbcc2fd96ed10a0fe4a321149fe38545d0d73d`.
  No charge-accuracy threshold was preregistered, HF/6-31G* is a defined
  reference rather than an absolute oracle, atom charges are not observables,
  and this fixed-geometry field comparison cannot adjudicate neutral-thioether
  `SA` versus `S` hydrogen-bond semantics. The bounded interaction-energy
  result below still leaves directionality, a second CPU host, and independent
  review open, so
  `charge_accuracy_pass=null`, `scientifically_validated=false`, and
  `claim_safe=false`;
- an installable, preregistration-first default-Vina sulfur-type invariance
  audit. Exact AutoDock Vina 1.2.7 tag source shows that both PDBQT `S` and
  `SA` first map to element sulfur and then to the same `XS_TYPE_S_P`; default
  Vina scoring uses XS types, whose acceptor set contains nitrogen and oxygen
  types but not sulfur. The production observation changed only the target
  PDBQT type from `SA` to `S` for all 60 retained poses across the three
  neutral-thioether cases. All eight public `Vina.score()` components were
  exact binary64-equal for 60/60 pose pairs, with zero score failures and 305
  explicit scope abstentions. Protocol and observation payload SHA-256 values
  are
  `81f52bbf68518e1d09e0462f8124ac1a810c7cc502ff8923175703e62b28b57f`
  and `a08ced8bbe0dbecc503f8e5eedf96d239130d0dbced897427694afe61742d406`.
  Source-tree and isolated installed-wheel exact reexecution reproduced the
  observation, and two wheels were byte-identical at SHA-256
  `fcbdc2df96c3b7df53f90e50e90688898147bf4665f2a816eb7d82382f547535`.
  This safely supports only the bounded claim that the observed `SA`/`S`
  distinction does not change fixed-pose scores in the active default-Vina
  1.2.7 lane. It does not rerun search, apply to complete AD4 scoring, adjudicate
  chemical hydrogen-bond acceptance, or promote a docking/product claim, so
  `bounded_default_vina_invariance_claim_safe=true` while
  `scientifically_validated=false` and `claim_safe=false`;
- an installable, preregistration-first neutral-thioether interaction-energy
  diagnostic. It binds the prior QM-ESP and default-Vina receipts, exact Vina
  1.2.7 AD4 source, official PySCF 2.14.0 and PySCF-dispersion 1.5.0 wheels,
  three environment-matched thioether models, one methanol O-H donor, six
  S-H distances, one plane-normal control, fixed complex/ghost geometries,
  B3LYP-D3(BJ)/def2-SVP settings, Boys-Bernardi counterpoise, exact AD4
  `S-HD`/`SA-HD` pair formulas, and every decision threshold before QM
  execution. The production observation completed all 21 geometries and 63
  SCFs with zero failures while retaining 305 scope abstentions. All three QM
  profiles had a 2.5 A minimum at -4.758 to -5.258 kcal/mol and a
  far-referenced well depth of -4.274 to -4.700 kcal/mol. Both the local
  three-model O-H acceptor gate and the AD4 `SA` profile-preference gate passed
  3/3. However, the plane-normal control was 0.551 to 0.784 kcal/mol more
  favorable than the selected idealized lone-pair direction in all three
  models, so directionality and general chemical acceptor semantics remain
  unresolved. Protocol and observation payload SHA-256 values are
  `f0b0d84551e63272509acaf967996496cc7100cd2a58b71392fe38bce7d8194c`
  and `30d9ceb83aed88fa45b7bc8c8282e6a50ce0299c9f54b21ce0c8885775c35fce`.
  Exact source-tree and fresh installed-wheel observation reexecution
  reproduced the latter. Two pinned-tool builds were byte-identical at wheel
  SHA-256
  `bb47ad0c5dcb0a5b9d298d2ba7f423910c11bf03c13f1691c0ecbec9c6db6f56`.
  One donor, three fixed gas-phase models, and an isolated pair term do not
  establish representative ligand/receptor chemistry or a complete AD4 score.
  A second CPU-host reproduction and independent reviewer receipt are still
  missing, so `chemical_acceptor_semantics_adjudicated=false`,
  `scientifically_validated=false`, and `claim_safe=false`;
- an installable
  `betelgeuze-engine-v2-posebusters-sulfur-reproduce` custody contract for that
  frozen observation. It preregisters distinct baseline/external host and
  operator identities, a single-use execution nonce, the exact Engine v2 and
  QM/Vina source-binary chain, then retains all 308 dispositions, 21 geometry
  points, 63 counterpoise SCFs, cross-host numeric differences, and failures.
  Result verification rederives the runtime projection and every comparison;
  reviewer approval uses a secret-free detached Ed25519 request, out-of-band
  trust anchor, role separation, expiry, revocation, and supersession inputs.
  Two pinned-tool builds were byte-identical at wheel SHA-256
  `5a6d82b8437b5d461e794f51a13bf127a51e429b3b4c5475b80fa8e417045acd`,
  and a fresh outside-checkout installed-wheel CLI smoke passed.
  No legitimate external-host work order, result, or reviewer approval has
  been produced in this repository, so both evidence gates remain false and
  no chemistry, docking, benchmark, or product claim changes;
- an installable, failure-inclusive PoseBusters Vina 1.2.7 execution receipt.
  The command accepts only the exact strict-preparation receipt and private
  artifact tree, freezes the single-CPU search configuration, binds the engine
  and implementation payloads, retains every generated PDBQT pose and five
  canonical binary64 energy components, and supports exact reexecution. The
  local ignored-state production receipt attempted and succeeded on all 18
  prepared pairs with zero engine failures, retained the 16 preparation blocks
  and 274 chemistry abstentions in the 308-case denominator, and stored 355
  poses. Receipt payload SHA-256 is
  `37b3df7c4c14d739d9fca3970dc73293a48909372314a8dfe1da5bcd956694ae`.
  Source-tree and installed-wheel exact verification both reproduced that
  receipt; two deterministic wheel builds matched byte-for-byte at SHA-256
  `68380b90af9ac286a70e264cb2603288ae5a2d639f32f27b1ae376bdaebc6228`.
  This receipt establishes pose generation only; its generated-pose evidence is
  supplied by the separate evaluator below;
- an installable, failure-inclusive PoseBusters 0.6.5 generated-pose evaluator.
  It consumes the exact archive, intake, corpus, strict-preparation, and Vina
  receipt chain, reconstructs every retained PDBQT model through pinned Meeko,
  normalizes each RDKit conformer to ID zero, and retains all 133 typed values
  from the official `redock` report plus direct symmetry-aware receptor-frame
  RMSD. The local 308-row receipt evaluated all 355 poses from the 18 Vina
  successes: 325/355 passed all non-RMSD binary tests, Top-1 RMSD <= 2 A was
  10/18, and Top-5 was 16/18. Its payload SHA-256 is
  `9c680e1edd08bfa07c1c71164b696ae050f180c3a2bb04bc91fd5d163a965b86`;
  the receipt file SHA-256 is
  `4903b3c5a34dc18fd38f9ba031099f0f2db688e4de66d2d42159163926a8975f`.
  The installed-wheel exact reexecution matched, and two deterministic wheel
  builds were byte-identical at SHA-256
  `b0248a218aaea0ef3f00e65d6f77e077cdd81a4c7ac37a128edd7833e3ce49a8`.
  The evaluated set is only the strictly prepared chemistry subset; AD4 types
  and Gasteiger charges remain independently unvalidated beyond the bounded
  same-algorithm diagnostic above. Target-family/leakage evidence, an
  independent host rerun, and reviewer acceptance remain absent. Therefore
  this is not a public docking benchmark or product claim and
  `claim_safe=false`;
- installable, failure-inclusive same-input GNINA 1.3.3 and Smina 2019-10-15
  execution receipts. The common CPU-only configuration fixes the 22.5 A box,
  seed 20260723, exhaustiveness 32, 20 modes, 1 A mode separation, Vina scoring,
  and no added ligand hydrogens. Both attempted 18/308 prepared pairs, succeeded
  on 17, retained all 16 preparation failures and 274 chemistry abstentions,
  and failed `7UAW_MF6` explicitly because prepared AutoDock type `CG0` is not
  supported. GNINA retained 340 poses and affinity/CNNscore/CNNaffinity; Smina
  retained 336 poses and minimized affinity. Their execution receipt payload
  SHA-256 values are `60d0e6a67c86075905cd54497ab12a678f0f54a15a11d7e9345122369d390847`
  and `912b7081ba35d11e0accdf1af9c5ebb55c09641390f17242fb8b210d67d27733`;
- an installable GNINA/Smina generated-pose evaluator using the same pinned
  PoseBusters 0.6.5 `redock` contract. GNINA evaluated 340/340 poses, with
  304 physically valid, Top-1 RMSD <= 2 A for 15/17 execution-success cases,
  and Top-5 for 16/17. Smina evaluated 336/336, with 312 physically valid,
  Top-1 10/17, and Top-5 15/17. Production and installed-wheel exact
  reexecution matched receipt payload SHA-256
  `0959201d6165d82041447be820977de7ac8ba64b13d1f237ad5b8c914a290259`
  for GNINA and
  `0590067f9c1731f6ebcbff36f54ba08d9265f32454b54fa03b7df0dbc328b930`
  for Smina. Two correctly staged wheel builds were byte-identical at SHA-256
  `02356f803a448fdb3f77f5594ef4927eacc1221d319069fa4b81ace25dc4a8f0`.
  These are conditional 17-case supported-subset results; complete target-
  family coverage and external-fit leakage control, independent-host,
  independent scientific charge/type validation, calibration, and reviewer
  gates remain open, so
  `benchmark_executed=false` and `claim_safe=false`;
- an installable conservative observed-target-cluster binding for the exact
  Vina/GNINA/Smina evaluation receipts. It reconstructs residue-label sequences
  only from first-model receptor `ATOM` rows, admits chains with at least 20
  residues, links a case pair only when one chain pair has at least 90% global
  edit similarity, and forms connected components. The exact 308-case run
  produced 296 clusters, 11 multi-case clusters, maximum size 3, and 13 links.
  Vina covered 18/296 clusters completely covering 17; GNINA and Smina each
  covered 17/296 and completely covered 16. On covered clusters, the explicit
  any-member Top-1/Top-5 RMSD-hit counts were 10/18 and 16/18 for Vina, 15/17
  and 16/17 for GNINA, and 10/17 and 15/17 for Smina. Exact reexecution matched
  receipt payload SHA-256
  `34d782567e816206dcaf2be5207e424b8611a081c9ca6d51bc9500e42ec81e5e`
  and file SHA-256
  `fc69398c600c032f7f5c18ca1fc8baedd51c93db0f933c2320d1f597265750aa`.
  Two pinned-tool builds were byte-identical at wheel SHA-256
  `050d06e9fc49ef3c79bcaefbd8854de85fce0ce7fe4a56cc83418a460280a597`,
  and the isolated installed-wheel command reproduced the same receipt.
  These clusters are a near-identity proxy, not biological target-family
  annotations. Every engine's fit/training manifest remains missing, so target
  and ligand/scaffold training leakage are unevaluated, `leakage_control_passed`
  is false, and no benchmark or product claim opens;
- an installable offline RCSB/Pfam target-family binding over the same exact
  308 cases and Vina/GNINA/Smina outcomes. A normalized official RCSB Data API
  observation is pinned without retaining raw responses; runtime verification
  performs no network access. Exact `asym_id` matches take precedence over
  exact `auth_asym_id` fallback, with no truncation or alias inference, and
  protein chains are associated with the native ligand at an inclusive 6 A
  heavy-atom cutoff. The production receipt records 306/308 complete chain
  mappings, 299 UniProt-annotated cases, 225 Pfam-annotated cases, one explicit
  unmapped archive chain (`6Z14_Q4Z`), and one removed RCSB entry (`7D6O_MTE`)
  without replacement remapping. It retains 199 Pfam multi-label families and
  149 non-overlapping exact Pfam-set partitions, including every source-engine
  failure and abstention. Snapshot payload/file SHA-256 values are
  `4d05e0127bb4c4dfedb5fa0a5f2e11d7de22aae481d34d3840676d04d367b51a`
  and `2287ffc895b28828ff39568f3ee0b98707b8160f04fa10196b469fe9ba722358`;
  family-receipt payload/file SHA-256 values are
  `ce7d0f32054f05a328554fa04e38964768d2e734157aa9eca4ceb431c2a87076`
  and `164ef81d7e49dbf32aab6eef56325dfd2ee57e889304e7f3ac0dff7f11a36761`.
  Two pinned-tool builds were byte-identical at wheel SHA-256
  `02d837ed5f624505a5a02bf1a5489f8aec1dcf0bacd15ef39b0fa6abf8526deb`,
  and the isolated installed-wheel command reproduced both snapshot and result
  receipts.
  The HTTPS observation is not RCSB-signed, annotation coverage is incomplete,
  and all external fit/training manifests remain missing; leakage control,
  benchmark authorization, scientific validation, and product claims remain
  false;
- an installable, test-only PoseBusters pose-ranking calibration intake. It
  caller-pins the three exact evaluation receipts plus the RCSB/Pfam receipt,
  then verifies the linked archive, preparation, and execution receipt/file
  identities before joining per-pose Vina, GNINA, and Smina score components
  to RMSD and physical-validity labels. The exact reconstruction retains 924
  engine/case rows, 1,031 successful pose rows, and 872 explicit failure rows;
  its all-308 Top-1/Top-5 counts remain Vina 10/16, GNINA 15/16, and Smina
  10/15. Receipt payload/file SHA-256 values are
  `b6526c7407602721f2ec74f09c8b99d4ecdc7336e69417ed6321840663de9ea0`
  and `88b756cd3e7d460edefe8330dbae6141e72492953a1af4e71bb60b1146574813`;
  two pinned-tool wheels matched at
  `c8019fa070e8ca2fc598e26cbdf3c78394fcf9e0963ec656d736b3864681ac51`,
  and source-tree/installed-wheel receipts were byte-identical. PoseBusters is
  fixed to `split_role=test`: no fit API is called.
  The base intake leaves coordinate and scaffold fields null rather than
  synthesizing them; complete Pfam coverage, fit manifests, and
  target/ligand/scaffold leakage evidence also remain absent. The base intake
  itself emits no generic calibration partition and opens no claim;
- an installable PoseBusters pose/scaffold identity overlay over that exact
  test-only intake. It binds all 1,903 intake rows to the caller-pinned archive,
  preparation, execution artifacts, and RDKit 2025.09.6 runtime. All 1,031
  generated poses receive topology-aware coordinate hashes and all 872 failure
  rows remain explicit. Start/reference scaffold identity passes for 308/308
  cases, yielding 229 groups (15 repeated, maximum size 21); 275 cases use a
  Bemis-Murcko graph and 33 use the explicitly named acyclic full-heavy-graph
  fallback. Generated/start chemistry and cross-engine topology mismatches are
  both zero. Start/reference full chemistry agrees for 305/308; the remaining
  three differences are retained for independent disposition. Receipt
  payload/file SHA-256 values are
  `e7b92d0fc74b44f652c5196429812fe61165771906d9d487a13ec8719ac52995`
  and `fbf3fa34f974dc8bd35b6564a1c004931a9ea0177f25fd551769b91f4db089d8`;
  deterministic wheel SHA-256 is
  `d3c51e79dc4783f859b7b2ff4a8f8499d42da0d6a4378035c3cf2114b751285e`,
  with byte-exact installed-wheel verification. Complete target-family
  assignment, fit/training provenance, leakage audits, independent rerun, and
  review remain open; no fit or claim is authorized;
- an installable failure-inclusive PoseBusters ranking test-partition command.
  It caller-pins the ranking-intake, pose/scaffold-identity, observed-sequence-
  cluster, and RCSB/Pfam receipts, revalidates their exact source chain, and
  constructs one `PoseRankingCalibrationPartition(split_role="test")` per
  engine. Vina retains 355 successful poses plus 290 failure observations
  (645 rows), GNINA 340 plus 291 (631), and Smina 336 plus 291 (627), with all
  308 cases present in every partition. Successful `pose_sha256` values are
  coordinate identities; failed rows use explicitly domain-separated failure-
  observation identities that are not coordinates. The receipt validates all
  21 ranking, 36 observed-sequence proxy, and 5,226 RCSB/Pfam metric rows and
  their Wilson intervals. Its 296 complete sequence strata are explicitly
  proxies, not biological families; the separate Pfam observation remains
  225/308. Receipt payload/file SHA-256 values are
  `509a7f7c8fcae221be53d5d7e525e05c37a1314f6d17060c8ed6b68e8e4fc89e`
  and `581235213b161caeb41db441ca73428d669a7fa0c9a3ead3bba7632dfa63b1dc`.
  Two deterministic wheels and installed-wheel verification matched at
  `5378c25f700a3f775aca232e379ea9e56b93a75310daead5d7dfdae082d9800e`.
  No fit partition, fitting call, leakage audit, external rerun, independent
  review, calibrated-scoring claim, or product claim is present;
- an installable, claim-closed PoseBusters external-ranking evaluator over
  those exact test partitions. It fixes the pre-existing source sort policies
  before label evaluation—Vina total energy, GNINA CNN pose score, and Smina
  minimized affinity—and requires each policy to reproduce source pose order.
  All 308 cases and all 872 failure observations remain explicit. Scored-case
  coverage is only 18/308 for Vina and 17/308 for both GNINA and Smina;
  all-case Top-1/Top-5 counts are 10/16, 15/16, and 10/15 respectively.
  Tie-invariant pose-level average precision over successful labeled poses is
  0.287330 (95% case-cluster bootstrap CI 0.174209–0.512214), 0.668157
  (0.534293–0.886705), and 0.304352 (0.183486–0.541608). Coverage and
  failure counts must accompany those conditional pose-level values. Source-
  bound physical-validity counts are 325/355, 304/340, and 312/336. The receipt
  also retains complete 296 sequence-proxy strata plus exact-Pfam-set and
  overlapping Pfam views with an explicit missing-annotation bucket. Receipt
  payload/file SHA-256 values are
  `509556b0bcd9ec35f9ff4b1860613f267b2a96d73b18de44b61288498a838137`
  and `3f4965ba07be36c6233514d2545c1db0f604bc4245552be2180bcdb780a43dc1`.
  The byte-identical wheel identified above reconstructed both the input and
  evaluation receipts exactly from outside the checkout.
  External-model training-overlap audit, independent rerun/review, calibrated
  internal-scorer evidence, complete public-benchmark evidence, and every
  docking product claim remain absent;
- an installable, uncalibrated internal PoseBusters ranking diagnostic over
  the same exact test partitions. It computes all pose scores before loading
  test labels and fixes four equally weighted terms: UFF receptor–ligand van
  der Waals, PDBQT-charge Coulomb, exact source-atom RDKit UFF strain delta,
  and UFF overlap penalty. The frozen RDKit 2025.09.6/NumPy 1.26.4 run scored
  all 1,031 source-success poses with zero scorer failures while retaining all
  872 upstream failures. Vina/GNINA/Smina scored-case coverage remains
  18/17/17 of 308; all-case Top-1/Top-5 counts are 2/5, 3/5, and 3/3.
  Successful-pose average precision is 0.113931
  (95% case-cluster bootstrap CI 0.056090–0.270781), 0.169927
  (0.100789–0.262457), and 0.106265 (0.064622–0.224549), respectively.
  Receipt payload/file SHA-256 values are
  `63a2f62cd465438f83e177b11ffd50483a2ff3f94c9399c308da2e8baee45b57`
  and `4e4acd968e2a32f4f6ff47b8412b9209b5afe6918bda2019fdc4e9e492a4f3b1`.
  The deterministic installed wheel identified above reconstructed this
  receipt exactly outside the checkout.
  This is an executable term-decomposed baseline, not the validated reference
  force field or a calibrated ranker. Test labels cannot be used to tune it;
  a disjoint fit/validation corpus, target/ligand/scaffold leakage audit,
  broader chemistry coverage, independent rerun/review, and every product
  claim remain open;
- an installable, preregistered PoseBusters external-ranking reproduction
  contract. Its work order binds the accepted baseline chain, exact wheel and
  source members, distinct baseline/external host and operator identities, and
  a single-use nonce before observation. Its result accepts only the same three
  fixed public-input roots plus a new ranking-intake/test-partition/evaluation
  chain whose six Vina/GNINA/Smina execution/evaluation receipt and file roots
  all differ from baseline. It compares all 924 engine/case rows, including
  failures, source ranks, native-like labels, tie-inclusive Top-K outcomes,
  fixed-policy scores, ratio metrics, case-cluster intervals, source-validity
  counts, and all family views. The contract and tamper tests are present, but
  no production work order or result has been created because real external
  host/operator identities and custody evidence have not been supplied.
  Same-host exact verification is not an independent rerun; physical-host and
  nonce-custody review, an independent reviewer receipt, and every science or
  product claim remain false;
- benchmark manifests with exactly one ordered success/failure row per case.
- a bounded offline materializer for the frozen four-case PoseBusters contract
  cohort. It verifies caller-supplied seed/reference SDF bytes, retains every
  multi-record parse/match/failure row, ignores seed coordinates, matches
  atomic-number/charge/isotope/aromatic/directional-V2000-stereo labeled
  graphs, enumerates bounded stereo-preserving symmetry mappings, and computes
  the minimum heavy-atom RMSD directly in the receptor frame across every
  matched reference pose without ligand-only alignment. The installable
  `betelgeuze-engine-v2-public-materialize` command additionally verifies all
  twelve receptor/seed/reference files from a local non-symlink input root and
  emits a canonical, no-overwrite, one-row-per-case suite receipt. The exact
  per-case materializer source is bound into protocol v1.1. The suite command
  performs no network fetch, pose generation, pose-validity evaluation, or
  scoring; no data, docking run, benchmark result, independent review, or
  scientific/product claim is bundled.

These surfaces are **not** calibrated docking, MD, free-energy, GPU, or customer
product capabilities. Every current V2 capability remains `claim_safe=false` and
`customer_execution_enabled=false`.

Start with:

- `docs/engine_v2_status.md`
- `docs/engine_v2_public_api.md`
- `config/independent_engine_v2_capabilities.yaml`
- `docs/entrypoints.md`

## Repository Contents

| Area | Purpose |
| --- | --- |
| `betelgeuze_engine_v2/` | Independent V2 contracts, molecular state, sparse geometry, AI/math primitives, strict ingest, physics registry, docking and benchmark scaffolds. |
| `packaging/engine-v2/` | Isolated `betelgeuze-engine-v2` distribution metadata. |
| `core/`, `betelgeuze_engine/` | Legacy physics/runtime and compatibility surfaces. They are not silently imported by the V2 wheel. |
| `api/`, `betelgeuze_product/` | Validated-runner product/API and delivery orchestration. |
| `tools/` | Gates, manifests, bundle builders, benchmark/accounting tools, and operational commands. |
| `tests/` | Unit and integration contracts for V2, legacy runtime, API, evidence, and delivery gates. |
| `config/` | Capability policy, target presets, thresholds, runtime profiles, and gate configuration. |
| `docs/` | Architecture, claim boundaries, reviewer entrypoints, delivery runbooks, wetlab material, and roadmaps. |
| `casp17/` | CASP17 local operator/review scaffolding and status documents. |

## Independent Engine v2 Quick Start

Build the isolated wheel from a clean clone:

```bash
python3 -m venv .venv-v2
source .venv-v2/bin/activate
python -m pip install --upgrade pip
python -m pip install "build>=1.2,<2" numpy==1.26.4
python -m pip install torch==2.6.0 --index-url https://download.pytorch.org/whl/cpu
python tools/build_engine_v2_wheel.py --output-dir dist-engine-v2
python -m pip install --no-deps dist-engine-v2/*.whl
python -m pip check
```

Inspect the machine-readable status:

```bash
python - <<'PY'
from betelgeuze_engine_v2.capabilities import capability_snapshot
import json
print(json.dumps(capability_snapshot(), indent=2, sort_keys=True))
PY
```

The root API is versioned by `ENGINE_API_VERSION`. V2-G ingest, docking,
benchmark, registry, and runtime submodules are provisional before distribution
version `1.0.0`; see `docs/engine_v2_public_api.md`.

## Monorepo Development Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

Run the canonical focused V2 suite:

```bash
python -m pytest -q \
  tests/unit/test_engine_v2_contracts_molecular.py \
  tests/unit/test_engine_v2_sparse_geometry_features.py \
  tests/unit/test_engine_v2_ai_core.py \
  tests/unit/test_engine_v2_periodic_energy.py \
  tests/unit/test_engine_v2_orchestrator_contract.py \
  tests/unit/test_engine_v2_runtime_checkpoint_contracts.py \
  tests/unit/test_engine_v2_packaging_guards.py \
  tests/unit/test_engine_v2_bounded_scaffolds.py \
  tests/unit/test_engine_v2_post_merge_state.py
```

`.github/workflows/ci-engine-v2-main.yml` repeats this contract on relevant pull
requests and every V2-related push to `main` using Python 3.10, 3.11, and 3.12.

## Product API (`/simulate`)

The HTTP product surface is **validated-runner ligand HTVS and backmapping
scoring only**. Generic molecular-dynamics simulation and Engine v2 customer
execution are intentionally unsupported.

```bash
pip install -r requirements-api.txt
uvicorn api.main:app --host 127.0.0.1 --port 8000
```

```bash
curl -s -X POST http://127.0.0.1:8000/simulate \
  -H 'Content-Type: application/json' \
  -d '{"target_name":"ExampleTarget","runner_profile_id":"backmapping_scoring.example"}'
```

Requests without an approved `runner_profile_id` fail closed.

## Local Evidence and Delivery

Generated or sensitive local artifacts are intentionally excluded, including
`data/`, `runs/`, trajectories, checkpoints, local bundles, logs, and caches.
A clean clone contains source, tests, schemas, lightweight figures, and templates;
it does not prove local evidence gates or scientific performance.

For restricted delivery review, start with:

- `docs/local_delivery_runbook.md`
- `docs/local_delivery_claim_policy.md`
- `docs/local_delivery_bundle_schema.md`
- `docs/broad_claim_unlock_roadmap.md`

Local evidence validators are expected to fail closed until the required
artifacts are regenerated or supplied as a reviewed bundle.

## CASP17 and Other Operational Lanes

Detailed, time-sensitive CASP17 status is maintained in:

- `casp17/WORKBENCH.md`
- `casp17/CASP17_CURRENT_STATUS_REPORT.md`
- `casp17/CASP17_WIN_TIER_GOAL.md`

These are local preparation and operator-review surfaces. They do not establish
a submission, leaderboard, or win-tier claim.

## Claim Boundary

Currently acceptable statements:

- V2-G bounded CPU reference contracts and scaffolds are implemented and tested.
- The independent wheel installs in a clean environment for Python 3.10–3.12.
- Strict ingest records source hashes and does not silently infer chemistry.
- Docking and benchmark ledgers preserve failed candidates/cases instead of
  dropping them.
- Restricted local-delivery claims remain governed by their separate evidence
  gates and reviewed local artifacts.

Not acceptable without additional evidence:

- calibrated docking accuracy or broad virtual-screening performance;
- validated force-field, MD, MM/GBSA, FEP, or binding free-energy claims;
- CUDA/ROCm/HIP parity or acceleration claims;
- wetlab-proven hit claims;
- automatic scorer/router/platform promotion;
- broad commercial drug-discovery platform claims.

Implementation, scientific validation, public benchmark evidence, and product
qualification are separate stages. A green source-level test does not collapse
those stages.
