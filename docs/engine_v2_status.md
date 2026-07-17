# Independent Engine v2 Status

This document is the human-readable companion to
`config/independent_engine_v2_capabilities.yaml`. The YAML snapshot is validated
against `betelgeuze_engine_v2.capabilities.capability_snapshot()` and is the
machine-readable source of truth.

## Current implementation stage

```text
v2_t_cpu_reference_validation_result_receipt_writer
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
- deterministic bounded docking proposal/search scaffolds;
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
  external authenticity proof, and same-UID replacement resistance is not
  established. Test-only signed artifacts and receipts exercise these
  primitives; no production key, attestation, receipt, root, runner start,
  validation result, independent result review, or scientific acceptance is
  bundled.

## What the implementation does not establish

All customer and scientific promotion flags remain false. The repository does
not currently establish:

- a calibrated independent force field;
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
