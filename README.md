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
v2_at_s0_production_evidence_bundle_contract
```

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
  the NVE config and restart identity. It ships no general solute
  constraint/mass assignment,
  validated parameters, independent SHAKE/RATTLE/Ewald comparison, accepted
  convergence or NVE-drift evidence, PME, net-charge background convention,
  independently accepted thermostat/barostat or NVT/NPT statistics, triclinic
  cells, GPU parity, or a product route;
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
  Ed25519 verifier freshly checks both Engine result-review chains, both OpenMM
  receipts, exact retained Engine outputs/traces, role separation, freshness,
  and revocation/supersession state before signing one host-scoped comparison.
  A frozen final S0 bundle contract now freshly reverifies exactly two such
  host inputs, requires distinct host/CPU/session/custody/artifact/nonces and
  exact commit/source/dependency/runtime/seed/physics equality, and verifies a
  role-separated final Ed25519 human approval. A verified bundle can establish
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
  internal strain delta, and VDW-overlap penalty, plus a fit-only pairwise
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
