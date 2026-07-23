# Changelog

This changelog tracks the independent `betelgeuze-engine-v2` distribution. The
legacy/product monorepo has separate operational evidence and does not inherit a
scientific claim from a package version.

## 0.2.0rc2 — Runtime identity release candidate

### Added

- The active 27-case/59-variant energy-force production-evidence chain now uses
  Ed25519 from pre-execution scientific review through authorization,
  run-start/bootstrap trust loading, result review, single-host OpenMM review,
  and two-host S0 approval. Verifiers accept exact public keys only; private and
  symmetric trust material are not part of the active chain. The refrozen v3/v5
  base contracts, v4 custody companions, v14 runtime-integrity contract, and
  read-only legacy identities do not provision keys or evidence and do not open
  any production, S0, scientific, fitting, or product claim.
- A pinned OpenMM Reference offline mapping and receipt path for the frozen
  27-case/59-variant energy-force and 14-case minimization protocols, including
  fixed-Born self/pair components and complete retained traces, plus a
  role-separated single-host external result review and an exact two-host S0
  evidence-bundle verifier. The installable
  `betelgeuze-engine-v2-s0-review` command supports secret-free detached final
  review: it emits canonical bytes for an external/HSM Ed25519 signer and
  verifies the returned signature with a public key before no-overwrite
  attachment. No production evidence, trust key, authenticated custody, final
  approval, S0 acceptance, or scientific/product promotion is bundled.
- An installable `betelgeuze-engine-v2-openmm-materialize` workflow executes
  the complete 27/59 energy-force and 14-case operational-trace comparisons,
  retains all failure rows plus Engine iteration/rejection counts,
  constraint/tangent-force metrics, energy/coordinate traces, and checkpoint
  equality in one canonical mode-0600 no-overwrite artifact, and supports
  structural verification or exact local re-execution. It never
  accepts private signing material and cannot mark production execution,
  independent review, two-host reproduction, validation, or claim safety true.
- An installable `betelgeuze-engine-v2-openmm-native-minimization` workflow now
  executes the separate OpenMM L-BFGS endpoint for all eight supported
  minimization cases, retains all six expected fail-closed rows, and
  re-evaluates each endpoint with Engine v2 at the same coordinates. Frozen
  configuration SHA-256 is
  `6465f726c408e6df2dd15d318a4cdfc57a8b2edd271ddaa578edcc336110017e`.
  The 2026-07-24 local failure-inclusive receipt passed 8/8 same-coordinate
  mappings and 8/8 energy-nonincrease checks but only 6/8 endpoint-health
  checks: both fixed-Born constrained cases exceeded the frozen tangent-force
  bound after final constraint projection. Receipt SHA-256 is
  `7e5b3454afc41f9954f71dfc3b0b274906323f15fd8ea6630bfcc1e95ce95b7c`;
  the status remains rejected and no endpoint/trajectory equivalence,
  production, S0/S1, scientific, or product claim is opened.
- An installable `betelgeuze-engine-v2-openmm-fixed-born-disposition` workflow
  now binds that exact rejected materialization/native receipt and records a
  preregistered two-alias by eight-probe solver/projection matrix. The v1
  observer path correctly rejected itself because reporter instrumentation
  changed endpoint last bits; v2 preserves its configuration identity
  `67f1a6025155d8f62cd3d1aa7da2803e229a4dce7871050db6c323f531f0b8c1`
  and separates an exact no-reporter control without changing any probe or
  endpoint-health threshold. Frozen v2 configuration SHA-256 is
  `ac601f3cfedd68e24b6507778ea36c1676fb24cacf89c7c2fa73848bf3c68045`.
  The actual v2 receipt reproduced both source endpoints bitwise, retained 16
  reporter traces, and classified both aliases as
  `final_constraint_projection_tradeoff_observed`: pre-projection tangent force
  was `4.561743820542636e-09 kcal/mol/Å` while constraint residual was
  `1.1016157942744798e-05 Å`; the final `6.256008569372265e-06 Å` maximum
  coordinate projection reduced the residual to
  `1.9898749314961606e-11 Å` but raised tangent force to
  `3.692322529338441e-04 kcal/mol/Å`. Iteration bounds 64–1024 and optimizer
  tolerances `1e-8`–`1e-12` did not resolve the tradeoff. Receipt/file SHA-256
  values are
  `870f1ea247da4b0232f22804298e75d554af511da18924a7ba49c1c703f003f2`
  and `a63d920b33925c2f0a27ba2fe150ef719c55dc66195cadadc4dd342dd589d127`.
  This accepts failure-disposition evidence only: the frozen native endpoint
  remains 6/8 and rejected, exact optimizer rejection count and causal root
  cause remain unavailable, and S0/S1/product claims stay closed.
- A separate claim-closed constraint-stationarity candidate now uses a strict
  `1e-14 Å` internal distance projection and permits numerical polish only when
  tangent force strictly decreases and energy remains within
  `1e-10 kcal/mol` of the best accepted energy. Candidate and same-coordinate
  OpenMM configuration SHA-256 values are
  `5642654a25a2d024f7cb8c1de024815f6bf6032b06f6c57509d7b784b708f708`
  and `722d319c865eb15dd12296dee998b26332e2c1ad8edf3e5e6611914b960529d1`.
  The installable
  `betelgeuze-engine-v2-openmm-constraint-stationarity` workflow retains exact
  restart, energy/coordinate traces, rejection rows, source/package/runtime
  identity, and fixed-Born self/pair terms. Its single-host candidate receipt
  (`16a4db9ca59ad969c63bb896a8bc3cb3310e7b5cc5f5e94e9a3b2dbf59d79f70`)
  passed only the four applicable constrained aliases: maximum total-energy
  and force errors versus OpenMM Reference were `1.07e-14 kcal/mol` and
  `2.40e-14 kcal/mol/Å`, while both evaluators met the unchanged `1e-8`
  absolute tangent-force bound at constraint residual below `8.66e-15 Å`.
  The other ten frozen cases are explicitly excluded, the native L-BFGS result
  remains rejected at 6/8, and validation, S0, two-host, independent-review,
  chemistry, and product claims remain false.
- A separate 14-case minimization-stationarity successor now reuses every
  frozen input without rewriting the frozen protocol or receipt. The four v1
  rows retain their original operational/independent paths, the four
  constrained aliases use the new stationarity candidate plus a Torch/NumPy-
  free tuple-arithmetic oracle, and all six expected fail-closed dispositions
  are re-executed. Configuration SHA-256 is
  `5c39aa346531d8f3cff378361367f7ff236f2c94c0c4bb3db66a28ec8e27d4f5`.
  The single-host claim-closed observation
  `18c6d617781e93c903332352d6f66e8eb2897e2c965035cd6f437d0324d3d1b9`
  passed 14/14 rows and all three operational/oracle restart comparisons,
  retains complete energy/coordinate/failure traces, and binds the 4/4
  same-coordinate OpenMM candidate receipt. Two fixed-Born accepted steps
  per alias fall on opposite Armijo/polish floating-point boundaries between
  implementations; their accepted-state trajectories, counts, final
  coordinates, and final physics remain within the preregistered bounds.
  This is not a production validation receipt: two-host reproduction,
  independent review, native OpenMM L-BFGS repair, and S0 remain open.
- An installable `betelgeuze-engine-v2-openmm-nve-trajectory` offline workflow
  now freezes one unconstrained ion-pair and one coupled O-H-constraint
  water-like 16-step trajectory plus nonperiodic, net-charged, and triclinic
  fail-closed rows. It independently maps the bounded direct-Ewald lattice into
  OpenMM Reference forces, uses OpenMM's documented velocity-Verlet/RATTLE
  sequence, retains every energy/force/coordinate/velocity and constraint/drift
  value, verifies Engine exact and OpenMM native-checkpoint restart, and binds
  complete source, dependency, binary, and environment identity. Configuration
  SHA-256 is
  `2beca32683c0393666cc1c3b5a136bed3416f774b0db631133a04bb43928871e`.
  The deterministic single-host candidate observation
  `d60b15992c4179a93e2276d4da380554e3c69a7819f181347aacab11899140cd`
  (file SHA-256
  `9a7161cd118adf467d3d4caf8f6378285aea6991bc8d763fcc9f20cbf0a2f586`)
  passes 2/2 physical and 3/3 failure rows. Two builds were byte-identical at
  wheel SHA-256
  `e784158af0ef5a5c85a2e7c0900280bdb0629c8950fd0344696ac00044281c48`,
  and installed-wheel verification reproduced the receipt. It is not accepted
  long-time drift/Ewald convergence, PME, broad chemistry/solvent,
  two-host/GPU, independent-review, scientific, product, or P2 evidence.
- An installable
  `betelgeuze-engine-v2-openmm-explicit-solvent-trajectory` successor now
  binds three exact 12 Å materialized TIP3P/ion inputs, four-step constrained
  NVE/OpenMM traces, both restart paths, a salted equal-horizon timestep
  ladder, direct-Ewald reciprocal bounds 2/3/4, and four exact fail-closed
  rows. Configuration SHA-256 is
  `e40902895938a4d7848e5207d0fe29de1ecaa43ae600c9c9ed8f7b7d0ac6c1b5`.
  Candidate observation and file SHA-256 values are
  `d510c9c65625c00f7bd14c134c72e1ed5dab004764efc60c7fd96a9dae223157`
  and
  `d1425d77a1457e05b596597139e4c7c76bfb6357f066e0f7c37cf5f919c96810`.
  The receipt preserves a 0/3 physical-case result: OpenMM Reference SETTLE
  leaves up to `4.67e-8 Å` rigid-water residual against the frozen `1e-9 Å`
  threshold, and two exact charged-pair cutoff-boundary inputs also fail the
  force-max, force-RMS, and trajectory-velocity rows. Both implementations pass
  Ewald bound convergence and all four negative cases pass; the Engine
  timestep coordinate monotonic row remains failed at `1.44e-11 Å`. No
  threshold or physical input was changed, and complete failure disposition
  does not open explicit-solvent, Ewald, long-time NVE, scientific, product,
  or P2 claims. Two builds were byte-identical at wheel SHA-256
  `3c08913e23dceb49614f97cad03fe872c1a7d072cb15c7437760c566da452b70`;
  installed-wheel verification reproduced the candidate receipt.
- An installable
  `betelgeuze-engine-v2-openmm-force-double-rattle-trajectory` development
  successor now separates static OpenMM Reference force evaluation from a
  stdlib-only binary64 constrained integrator. Three fresh 13.5 Å systems each
  contain four deterministic TIP3P waters, optional ions, nonzero velocities,
  and at least `0.25 Å` retained-frame cutoff margin. Previous-vector SHAKE and
  current-vector RATTLE run for 16 steps with exact restart, complete traces,
  and six fail-closed rows. Configuration SHA-256 is
  `ba2c1e99183cc124bb664745dfd1b4cbabbd2d4328cc35754e9e4da044606007`;
  candidate observation and file SHA-256 values are
  `cd0b849e206124e11996581c81dcc13da9d11ee3caa1c8176b5525dfead271a6`
  and
  `733af591c5366670a1aba79581648f064b8dccbd50d87b2080d139eb018329f0`.
  All 3/3 physical and 6/6 failure rows pass, including the unchanged
  `1e-6 kcal/mol` drift gate. Two builds were byte-identical at wheel SHA-256
  `32e5784ed210f9a62de015a71c18c3fe302f897761b4d740563afb04e9352cab`,
  and installed-wheel verification reproduced the receipt. This is
  post-exploration development evidence:
  the first current-vector result remains preserved, the rejected SETTLE
  receipt is not superseded, and fresh holdout, two-host reproduction,
  independent review, liquid/ion observables, PME, and scientific/product/P2
  acceptance remain open.
- The OpenMM host result-review and two-host S0 contracts are refrozen as v4.
  A rejected native endpoint now requires the exact fixed-Born disposition
  receipt to be freshly verified and signs its receipt, configuration, physics
  projection, completeness, and classification separately from endpoint
  acceptance. Missing, cross-wired, tampered, revoked, or superseded
  disposition evidence fails closed; an accepted native endpoint forbids that
  failure-specific input. The current 6/8 run therefore remains a signed
  rejection even though its disposition is complete. The S0 builder requires
  the disposition path to be not applicable on both accepted 8/8 hosts and
  still rejects the observed host before signing. Current host-review and S0
  contract SHA-256 values are
  `6e543d32b320b562fa0b3ad31c1ac26cc7b274fcbb4f79025f53ce1035ea5970`
  and `549fbdb865704a84df4ecb525f4ea27a7c5ab8526f7f1be0b0f666cd9c6fd08d`.
- A bounded offline reference-pose materializer for the frozen PoseBusters
  four-case contract cohort. Protocol v1.1 now selects every reference SDF
  record matching the identity seed's labeled graph instead of requiring one
  record, retains parse/mismatch/search-failure rows, ignores seed coordinates,
  preserves directional V2000 bond stereo, enumerates bounded stereo-preserving
  automorphisms, and computes the minimum direct receptor-frame heavy-atom RMSD
  across all matched records without ligand alignment. Canonical receipts and
  the protocol bind the exact materializer source. No data, public benchmark
  run, result, independent review, or scientific/product claim is included.
- An installable `betelgeuze-engine-v2-public-materialize` offline suite command
  verifies all twelve frozen receptor/seed/reference artifacts, rejects symlink
  inputs, retains all four success/failure case rows, embeds canonical reference
  receipts, and writes a mode-0600 no-overwrite suite receipt. It does not fetch
  data, generate poses, evaluate pose validity, score, or create docking evidence.
- A fail-closed same-input external-baseline preparation contract now verifies
  exact four-case receptor/ligand PDBQT bytes and their source, preparation-tool,
  configuration, executable, and container identities before emitting three
  non-executing Vina/GNINA/Smina work orders. All engines receive the same
  prepared hashes, native-defined receptor-frame centers, frozen 22.5-A boxes,
  seed, exhaustiveness, mode count, and CPU count; engine binary identities and
  score semantics remain distinct and exact. No prepared artifacts, engine
  binaries, executions, result receipts, statistical holdout, independent
  preparation audit, or independent rerun is bundled.
- A public split-provenance layer now freezes the official PDBbind v2020,
  CASF-2016, and published 308-case PoseBusters source/access boundaries. The
  PoseBusters 308-ID file is fixed by raw and canonical case-projection SHA-256.
  Caller-provisioned case manifests bind release date, receptor, ligand,
  scaffold, canonical protein-chain-set, target-family, cofactor, and supported/
  unsupported chemistry identities. A source-bound Smith-Waterman/BLOSUM62
  receipt records the maximum identity over every evaluation/fit protein-chain
  pair and low/medium/high strata. Separate bindings recheck generic
  calibration partitions, leakage audits, all-case denominators, and exact
  target-family denominators. No PDBbind license acceptance, dataset archive,
  full manifest, sequence run, fitted model, benchmark result, or independent
  rerun is bundled.
- A new installable
  `betelgeuze-engine-v2-public-ranking-corpus-intake` command turns that API
  into a file-bound three-way readiness gate. It requires canonical,
  caller-pinned PDBbind-v2020 fit, complete 285-case CASF-2016 validation, and
  complete 308-case PoseBusters test manifests plus fit↔validation, fit↔test,
  and validation↔test all-chain sequence receipts. The frozen policy rejects
  exact case/PDB/target/receptor/ligand/scaffold/sequence overlap, sequence
  identity above 0.90, fit→test or validation→test release-order violations,
  method drift, missing access/selection evidence, and protocol/preparation
  drift. Configuration SHA-256 is
  `4972e41765076e09b7bbec43b7e506dede6ab48b01b173f62cd73a749f694681`.
  The canonical receipt is mode-0600/no-overwrite and contains no score or
  label fields. No production receipt is emitted without real caller-provided
  licensed manifests and executed sequence evidence; fitting, model selection,
  metrics, review, and claims remain absent.
- A new installable
  `betelgeuze-engine-v2-public-ranking-calibration-partition-intake` command
  admits canonical PDBbind-fit and CASF-validation
  `PoseRankingCalibrationPartition` files only after that three-way corpus
  receipt passes. It exact-binds file/payload identities, recomputes public
  manifest bindings and pose-level leakage, and retains success/failure,
  positive/negative, case, term-schema, and pairwise-trainability denominators.
  Validation labels remain evaluation-only and the API has no test-partition
  input. Configuration SHA-256 is
  `c4b423063a36f38d7f6f098a38c7ea54b078c25f3cc04d060ae88638902ff8be`.
  It performs no fit, model selection, benchmark, review, or claim promotion;
  no production receipt exists without the genuine upstream corpus.
- A new installable
  `betelgeuze-engine-v2-public-ranking-calibration-training-view` command
  materializes a fit-only view only after the calibration-partition intake
  passes. Selection is frozen to `status`: every successful fit row is included
  unchanged, while every failure is excluded only from executable fitting and
  retained as a hash-bound disposition. The receipt embeds the exact training
  partition, recomputes training-view/CASF leakage, and supports a guarded
  deterministic-fit bridge without validation-label use or a test-partition
  input. Configuration SHA-256 is
  `e5e202d10420b5a557b1227aa0f7735433ebaeadc1656f6b981c14453aeb25b8`.
  No production receipt, fit, selected model, metric, review, or claim exists
  without genuine upstream corpus inputs.
- A new installable
  `betelgeuze-engine-v2-public-ranking-fit-validation` command preregisters
  every deterministic fit candidate and the CASF bootstrap configuration in a
  workflow-local canonical manifest, fits only the verified PDBbind training
  view, and
  evaluates CASF with failure-inclusive all-case/all-pose, target-family, and
  confidence-interval evidence. The deterministic selection rule is
  average-precision PR-AUC, Top-1, Top-5, then candidate ID; its policy
  SHA-256 is
  `1905b14e37da44293483b9b31a06b2653849b2e986dc75b9e4ad53aa0bc4b9d9`.
  Any incomplete candidate or unavailable primary metric retains its result
  row and blocks selection. The mode-0600 no-overwrite receipt exact-binds
  ancestry, source, Python/Torch runtime, configs, models, reports, and
  selection, while verification reexecutes the full workflow. PoseBusters test
  score partitions are forbidden. Two builds were byte-identical at wheel
  SHA-256
  `d338d81d14d08ca7c07f74629ac2b98f94d389f651e44e2b143fb487bfcf4bd3`
  (1,708,814 bytes), and the installed CLI/import boundary was verified outside
  the checkout. No genuine licensed inputs or production receipt are present,
  no independent timestamp/signature custody proves external preregistration,
  and no test, confidence-calibration, independent-review, scientific-
  validation, chemistry, or product claim is opened.
- An installable `betelgeuze-engine-v2-posebusters-intake` command now verifies
  the exact published PoseBusters Zenodo archive and journal 308-ID selection
  from caller-provided local files. It uses bounded no-follow regular-file
  access, audits the ZIP directory without extraction, rejects duplicate,
  traversal, encrypted, unsupported-compression, symlink, count, size, and
  metadata-identity violations, and CRC-streams all four artifacts for every
  selected case into 308 failure-inclusive rows. Its canonical mode-0600 output
  is no-overwrite and exactly reexecutable. It fetches and accepts no data or
  terms, extracts nothing, executes no docking or benchmark, and bundles no
  archive, scientific result, or review.
- An installable `betelgeuze-engine-v2-posebusters-corpus-audit` command now
  reexecutes that exact intake and audits every selected receptor, native
  ligand, and start conformer without extraction. Its failure-inclusive receipt
  records element/formal-charge, metal, non-water cofactor, ligand-capacity,
  heavy labeled-graph, raw V2000 aromatic-bond, and raw directional-bond
  inventories with all-case Wilson 95% intervals. It performs no aromaticity or
  atom-stereo oracle, preparation, pose generation, scoring, external baseline,
  family analysis, or benchmark and cannot admit a case without explicit
  parameters and partial charges.
- An installable `betelgeuze-engine-v2-posebusters-native-geometry` command now
  reexecutes the exact intake and corpus audit, then records native-crystal-pose
  fixed-radius receptor overlap, topology-excluded ligand self-overlap, and
  native/start heavy-bond delta observations for all 308 cases. It distinguishes
  unsupported elements and exact target-CCD residue-name retention, binds CPU
  float64 runtime and implementation identities, and supports byte-exact
  reexecution. These unvalidated heuristics are a positive-control preflight,
  not PoseBusters equivalence, generated-pose validity, strain energy, docking,
  ranking, or benchmark evidence.
- An installable `betelgeuze-engine-v2-posebusters-external-prepare` command now
  exactly reexecutes the intake and corpus audit, attempts strict pinned Meeko
  preparation only for the 34-case provisional chemistry subset, and preserves
  all 308 dispositions. It binds Python and external dependency payloads, the
  complete default AD4/Gasteiger configuration, native-defined box centers, and
  private no-overwrite PDBQT artifacts. The 2026-07-23 local receipt retained
  274 chemistry abstentions, 18 prepared input pairs, 15 strict receptor-template
  failures, and one receptor-construction failure. It never enables
  `allow_bad_res`, executes no Vina/GNINA/Smina binary, evaluates no generated
  pose, and is preparation evidence rather than docking or benchmark evidence.
- An installable
  `betelgeuze-engine-v2-posebusters-prepared-ligand-diagnostic` command now
  consumes that exact preparation receipt, preserves all 308 dispositions, and
  binds the Python/RDKit distribution payload before directly recomputing the
  same Gasteiger algorithm from strict `SMILES IDX`/`H PARENT` mappings. RDKit
  2022.09.5 and 2025.09.6 observations each evaluated 18 prepared cases, 481
  real atoms, and two zero-charge `G0` macrocycle pseudoatoms with zero
  diagnostic failures. The maximum PDBQT three-decimal charge delta was
  0.0004979832249129013 e and all element/type plus aromatic-carbon checks
  passed. Cross-version expected charges were bitwise equal for 481/481 atoms.
  Observation payloads are
  `df57b0d48ba905e0f132b66a3b4d4fc344fffc4a40f1d78de181c0264bedba8f`
  and `6d3389ed55e7d47c8e0b0076c485b3f4ee7590cb3f9ddcd12db89030e92b6b50`;
  comparison payload is
  `ab9cf4b72d3af848dd48484fcbb203268fe8d7336ec552ffe52c360dca972b5f`.
  Two wheels were byte-identical at
  `9d1c96336c1fa55051ab3e0fc2192d990860c644dc5f39a0685f07c39613124e`,
  and isolated installed-wheel verification reproduced all three receipts.
  This is same-algorithm persistence and serialization evidence, not an
  independent charge/type oracle, benchmark, or product claim.
- A new installable
  `betelgeuze-engine-v2-posebusters-openbabel-compare` command performs a
  separately distributed Open Babel 3.2.1 implementation comparison against
  that exact 308-row preparation receipt. It binds the official CPython 3.10
  wheel (`ca6345ca6cc66522208c45355a90472d657be78dec7706757d477bfb0c105413`),
  Open Babel distribution payload, Python/platform identity, source commit,
  configuration, implementation sources, and every prepared/failure/abstention
  row. All 18 prepared cases completed with zero comparison failures, covering
  481 real atoms and retaining two excluded `G0` pseudoatoms. Charge
  MAE/RMSE/max absolute delta was 0.0038510594375734796 /
  0.012204476318346003 / 0.18097866788513423 e; exact AD4 types agreed for
  476/481 atoms. The five retained mismatches are three `SA`/`S` and two
  `CG0`/`C` assignments. Exact source-tree and isolated installed-wheel
  verification matched receipt payload SHA-256
  `7754c4b56e10d4543b064c23daaf69ab99e098fda81bfd9fbaecc8694439d943`;
  two package builds were byte-identical at
  `d0fc6a2acce76f2e3d23915b533528263d10e8277c0cf6feafd09e318c6d9529`.
  This is descriptive independent-implementation evidence, not an independent
  scientific charge oracle or validated threshold. Exact-tag source follow-up
  explains `CG0`/`C` as Meeko macrocycle-extension vocabulary and `SA`/`S` as
  a neutral-thioether acceptor-semantics disagreement; a controlled RDKit
  iteration study points to sulfur parameter selection, not iteration count
  alone, for the methylsulfone charge outlier. Chemical correctness,
  source-SDF equivalence, receptor auditing, second-host reproduction, and
  reviewer acceptance remain open and `claim_safe=false`.
- A new installable
  `betelgeuze-engine-v2-posebusters-sulfur-qm-esp` command separates
  preregistration from observation for a bounded PySCF 2.14.0 fixed-geometry
  molecular-ESP diagnostic. The protocol binds the exact four sulfur cases,
  all 308 dispositions, source SDF coordinates and explicit hydrogens,
  RHF/6-31G* spherical-basis SCF settings, official PySCF wheel and installed
  dependency payloads, single-thread native runtime, equal-weight Lebedev-110
  molecular-surface shells, same-site Meeko/Open Babel charge projections,
  metrics, and claim gates before QM execution. The local production
  observation evaluated 4/4 scoped cases with zero QM failures and retained
  304 explicit scope abstentions. Meeko had lower global weighted ESP RMSE in
  all four cases, but only by small descriptive margins. Exact source-tree and
  isolated installed-wheel reexecution reproduced observation payload SHA-256
  `402d1795f18b7eb0c87d8537f3b427fe116c0845bf1337b21e24752cef7e52e6`;
  the prior protocol payload is
  `0927260a16f1e09211fb601fade1725e21d35d221d04e69cfd2c624da7c06137`,
  and two builds were byte-identical at wheel SHA-256
  `b4564648dbf3fcb681e0b73d1dcbcc2fd96ed10a0fe4a321149fe38545d0d73d`.
  No accuracy threshold was preregistered. This does not validate atom charges,
  decide neutral-thioether `SA`/`S` hydrogen-bond semantics, establish a
  representative chemistry benchmark, or permit product promotion. The
  bounded interaction-energy result below still leaves directionality,
  second-host reproduction, and independent review open, and
  `claim_safe=false`.
- A new installable
  `betelgeuze-engine-v2-posebusters-vina-sulfur-invariance` command
  preregisters and executes the product-path consequence of the three
  neutral-thioether `SA`/`S` differences. It binds exact AutoDock Vina 1.2.7
  tag source files, the preparation/Open Babel/Vina receipt chain, all 308
  dispositions, every retained pose, the Vina distribution/runtime, and a
  target-only PDBQT `SA` to `S` mutation before rescoring. The source projection
  fixes both AD types to element sulfur and then `XS_TYPE_S_P`, confirms default
  Vina scoring uses XS types, and confirms sulfur is absent from the XS
  acceptor set. The production observation rescored 60 poses across three
  cases; all eight public score components were exactly equal for 60/60 pairs,
  with zero failures and 305 scope abstentions. Source-tree and installed-wheel
  exact verification reproduced observation payload SHA-256
  `a08ced8bbe0dbecc503f8e5eedf96d239130d0dbced897427694afe61742d406`;
  protocol payload SHA-256 is
  `81f52bbf68518e1d09e0462f8124ac1a810c7cc502ff8923175703e62b28b57f`,
  and two wheels were byte-identical at SHA-256
  `fcbdc2df96c3b7df53f90e50e90688898147bf4665f2a816eb7d82382f547535`.
  The narrow fixed-pose default-Vina invariance claim passes. Search was not
  rerun, complete AD4 scoring and chemical acceptor semantics remain
  unevaluated, and no benchmark or product promotion follows;
  `claim_safe=false` remains.
- A new installable
  `betelgeuze-engine-v2-posebusters-sulfur-interaction` command preregisters
  and executes the bounded AD4/chemical-semantics follow-up. It freezes the
  prior QM/Vina receipt chain, exact Vina 1.2.7 AD4 source, PySCF 2.14.0 and
  PySCF-dispersion 1.5.0 wheels, three fixed thioether models, one methanol O-H
  donor, six S-H distances plus one orientation control, all complex/ghost
  geometries, B3LYP-D3(BJ)/def2-SVP counterpoise settings, exact `S-HD` and
  `SA-HD` pair terms, failures, metrics, and gates before execution. The local
  production run completed 21 geometries and 63 SCFs with zero failures,
  retained 305 abstentions, and passed both preregistered local gates for 3/3
  models. QM minima were at 2.5 A and -4.758 to -5.258 kcal/mol. The
  plane-normal controls were nevertheless 0.551 to 0.784 kcal/mol more
  favorable, so directionality and general chemical semantics remain open.
  Protocol/observation payload SHA-256 values are
  `f0b0d84551e63272509acaf967996496cc7100cd2a58b71392fe38bce7d8194c` /
  `30d9ceb83aed88fa45b7bc8c8282e6a50ce0299c9f54b21ce0c8885775c35fce`;
  exact source-tree and fresh installed-wheel observation reexecution matched,
  and two deterministic wheels matched at
  `bb47ad0c5dcb0a5b9d298d2ba7f423910c11bf03c13f1691c0ecbec9c6db6f56`.
  This is one O-H probe over three fixed gas-phase models and an isolated AD4
  pair comparison, not representative chemistry, a complete AD4 score, or
  product validation. Second-host reproduction and independent review remain
  missing; `scientifically_validated=false` and `claim_safe=false`.
- Added the installable
  `betelgeuze-engine-v2-posebusters-sulfur-reproduce` external evidence
  contract. It freezes two host/operator identities, an execution nonce, the
  baseline receipts, Engine v2 wheel, source members, and shared runtime
  projection before the second-host run; compares all 308 dispositions, 21
  points, and 63 counterpoise SCFs with failure retention; and supports a
  detached, role-separated Ed25519 reviewer receipt with expiry, revocation,
  and supersession checks. Two pinned-tool builds were byte-identical at
  `5a6d82b8437b5d461e794f51a13bf127a51e429b3b4c5475b80fa8e417045acd`,
  and outside-checkout installed-wheel CLI smoke passed. This release contains
  the workflow and verifier,
  not an external-host result or independent approval, so all existing
  scientific and product blockers remain.
- An installable `betelgeuze-engine-v2-posebusters-vina-execute` command now
  consumes that exact preparation receipt and private artifact tree, requires a
  payload-bound Vina 1.2.7 runtime, and freezes the single-CPU search seed, box,
  spacing, exhaustiveness, mode count, and energy range. It retains one
  disposition for every one of the 308 cases, private no-overwrite generated
  PDBQT artifacts, all five Vina energy components as canonical binary64, and
  bounded failure diagnostics. The 2026-07-23 local production receipt attempted
  and succeeded on all 18 prepared pairs with zero engine failures, retained 16
  preparation blocks and 274 chemistry abstentions, and stored 355 poses. Exact
  source-tree and installed-wheel exact reexecution matched receipt payload SHA-256
  `37b3df7c4c14d739d9fca3970dc73293a48909372314a8dfe1da5bcd956694ae`.
  Two pinned-build-tool wheel builds were byte-identical at SHA-256
  `68380b90af9ac286a70e264cb2603288ae5a2d639f32f27b1ae376bdaebc6228`.
  These ignored-state outputs remain the pose-generation layer rather than the
  generated-pose evaluation layer below.
- An installable `betelgeuze-engine-v2-posebusters-evaluate-generated` command
  now consumes the exact archive/intake/corpus/preparation/Vina chain and the
  pinned PoseBusters 0.6.5 wheel. It evaluates every retained PDBQT model under
  the official `redock` configuration, preserves all 133 typed report values,
  separates the 27-test non-RMSD physical-validity endpoint from direct
  symmetry-aware receptor-frame RMSD, and retains all 308 case dispositions.
  The 2026-07-23 local receipt evaluated 355/355 generated poses, with 325
  physically valid poses, Top-1 RMSD <= 2 A for 10/18 Vina-success cases, and
  Top-5 for 16/18. Installed-wheel exact reexecution matched payload SHA-256
  `9c680e1edd08bfa07c1c71164b696ae050f180c3a2bb04bc91fd5d163a965b86`;
  two builds were byte-identical at wheel SHA-256
  `b0248a218aaea0ef3f00e65d6f77e077cdd81a4c7ac37a128edd7833e3ce49a8`.
  This is supported-subset validity/redocking evidence, not a representative
  public benchmark: family/leakage, independent-host, independent scientific
  charge/type validation, and reviewer gates remain open and
  `claim_safe=false`.
- Installable `betelgeuze-engine-v2-posebusters-external-execute` GNINA 1.3.3
  and Smina 2019-10-15 lanes now freeze official executable identity and the
  same CPU-only preparation/search contract. Each retained all 308 rows,
  attempted 18 prepared pairs, succeeded on 17, and explicitly retained the
  `7UAW_MF6` unsupported prepared AutoDock `CG0` engine failure. GNINA stored
  340 poses and all affinity/CNN components at receipt SHA-256
  `60d0e6a67c86075905cd54497ab12a678f0f54a15a11d7e9345122369d390847`;
  Smina stored 336 poses and minimized affinity at
  `912b7081ba35d11e0accdf1af9c5ebb55c09641390f17242fb8b210d67d27733`.
- A new installable
  `betelgeuze-engine-v2-posebusters-external-evaluate-generated` command
  evaluates those exact outputs with the pinned PoseBusters 0.6.5 contract and
  retains engine scores, all 133 typed report values, separate physical-validity
  and RMSD endpoints, and every failure/abstention row. GNINA evaluated 340/340
  poses, recorded 304 physical-validity passes, and reached Top-1/Top-5 RMSD <=
  2 A on 15/17 and 16/17 execution-success cases. Smina evaluated 336/336,
  recorded 312 passes, and reached 10/17 and 15/17. Installed-wheel exact
  reexecution matched receipt SHA-256
  `0959201d6165d82041447be820977de7ac8ba64b13d1f237ad5b8c914a290259`
  and `0590067f9c1731f6ebcbff36f54ba08d9265f32454b54fa03b7df0dbc328b930`.
  Two staged builds were byte-identical at wheel SHA-256
  `02356f803a448fdb3f77f5594ef4927eacc1221d319069fa4b81ace25dc4a8f0`.
  These remain conditional 17-case results; complete target-family coverage,
  external-fit leakage control, independent-host, independent scientific
  charge/type validation, calibration, and reviewer gates remain open.
- A new installable `betelgeuze-engine-v2-posebusters-target-clusters` command
  binds the exact Vina/GNINA/Smina evaluation receipts to conservative observed
  receptor clusters. It uses first-model `ATOM` residue-label sequences,
  minimum 20-residue chains, a 90% global edit-similarity link threshold, and
  connected components. The exact 308-case receipt recorded 296 clusters, 11
  multi-case clusters, maximum size 3, and 13 links. Vina cluster coverage and
  complete coverage were 18/296 and 17/296; GNINA and Smina were 17/296 and
  16/296. Covered-cluster any-member Top-1/Top-5 RMSD hits were 10/18 and 16/18,
  15/17 and 16/17, and 10/17 and 15/17, respectively. Exact reexecution matched
  payload SHA-256
  `34d782567e816206dcaf2be5207e424b8611a081c9ca6d51bc9500e42ec81e5e`
  and file SHA-256
  `fc69398c600c032f7f5c18ca1fc8baedd51c93db0f933c2320d1f597265750aa`.
  Two pinned-tool builds were byte-identical at wheel SHA-256
  `050d06e9fc49ef3c79bcaefbd8854de85fce0ce7fe4a56cc83418a460280a597`,
  and isolated installed-wheel verification reproduced the receipt.
  The receipt explicitly rejects a biological-family interpretation and marks
  all external fit/training manifests missing, so neither target nor
  ligand/scaffold leakage is evaluated and `leakage_control_passed=false`.
- A new installable
  `betelgeuze-engine-v2-posebusters-rcsb-target-families` command consumes a
  normalized, mode-0600 official RCSB Data API observation and the exact
  target-cluster receipt without runtime networking. Pocket-associated protein
  chains use an inclusive 6 A heavy-atom cutoff and exact `asym_id` first,
  exact `auth_asym_id` fallback second; no chain truncation, alias inference,
  or removed-entry remapping is allowed. The 308-case receipt records 306
  complete mappings, 299 UniProt cases, 225 Pfam cases, the explicit
  `6Z14_Q4Z` mapping failure, and removed `7D6O_MTE`. It projects all engine
  dispositions onto 199 Pfam multi-label families and 149 non-overlapping
  exact Pfam sets. Snapshot payload/file SHA-256 values are
  `4d05e0127bb4c4dfedb5fa0a5f2e11d7de22aae481d34d3840676d04d367b51a`
  and `2287ffc895b28828ff39568f3ee0b98707b8160f04fa10196b469fe9ba722358`;
  target-family receipt payload/file SHA-256 values are
  `ce7d0f32054f05a328554fa04e38964768d2e734157aa9eca4ceb431c2a87076`
  and `164ef81d7e49dbf32aab6eef56325dfd2ee57e889304e7f3ac0dff7f11a36761`.
  Two pinned-tool builds were byte-identical at wheel SHA-256
  `02d837ed5f624505a5a02bf1a5489f8aec1dcf0bacd15ef39b0fa6abf8526deb`;
  isolated installed-wheel verification reproduced both receipts.
  The normalized HTTPS observation is not independently source-signed, Pfam
  coverage is incomplete, and fit/training manifests remain missing, so
  `leakage_control_passed=false`, `scientifically_validated=false`, and
  `claim_safe=false` remain mandatory.
- A new installable
  `betelgeuze-engine-v2-posebusters-ranking-intake` command binds the exact
  Vina/GNINA/Smina execution and evaluation receipts to archive, preparation,
  and RCSB/Pfam identities as test-only calibration intake. It retains all 924
  engine/case rows, 1,031 successful pose rows, 872 explicit failure rows,
  engine-specific score-term decomposition, RMSD/validity labels, and
  all-case Wilson intervals. Payload/file SHA-256 values are
  `b6526c7407602721f2ec74f09c8b99d4ecdc7336e69417ed6321840663de9ea0`
  and `88b756cd3e7d460edefe8330dbae6141e72492953a1af4e71bb60b1146574813`;
  two deterministic wheels matched at
  `c8019fa070e8ca2fc598e26cbdf3c78394fcf9e0963ec656d736b3864681ac51`.
  It refuses to invent missing per-pose coordinate
  or scaffold hashes, never calls a fit API, and keeps partition, leakage,
  scientific, and product claims closed.
- A new installable
  `betelgeuze-engine-v2-posebusters-pose-scaffold-identity` command closes the
  ranking intake's coordinate/scaffold identity omissions without consuming
  its test labels. The exact RDKit 2025.09.6 runtime matches the preparation
  payload and host identity; all 1,031 generated poses receive distinct,
  topology-aware three-decimal PDBQT coordinate hashes, all 872 upstream
  failures remain explicit, and all 308 cases receive matched start/reference
  scaffold identities. The corpus contains 229 scaffold identities, including
  33 explicitly named acyclic full-heavy-graph fallbacks. Start/reference full
  chemistry agrees for 305/308 cases while scaffold identity agrees for
  308/308; the three full-chemistry differences remain pending independent
  disposition. Receipt payload/file SHA-256 values are
  `e7b92d0fc74b44f652c5196429812fe61165771906d9d487a13ec8719ac52995`
  and `fbf3fa34f974dc8bd35b6564a1c004931a9ea0177f25fd551769b91f4db089d8`.
  Two deterministic wheels matched at
  `d3c51e79dc4783f859b7b2ff4a8f8499d42da0d6a4378035c3cf2114b751285e`,
  and installed-wheel reconstruction was byte-identical. Complete target
  families, a disjoint fit manifest, leakage audits, external rerun, and
  independent review remain blockers; the identity command itself opens no
  calibration partition or claim.
- A new installable
  `betelgeuze-engine-v2-posebusters-ranking-test-partitions` command binds the
  ranking intake, pose/scaffold identity, observed-sequence clusters, and
  RCSB/Pfam annotations into three failure-inclusive
  `PoseRankingCalibrationPartition(split_role="test")` objects without calling
  a fit API. Vina/GNINA/Smina retain 645/631/627 rows respectively and all 308
  cases per engine; all 1,031 successful rows use exact coordinate identities
  while all 872 failure rows use unique domain-separated observation
  identities that are explicitly not coordinates. The command revalidates 21
  all-case ranking, 36 observed-sequence proxy, and 5,226 RCSB/Pfam metric rows
  plus Wilson intervals. The 296 sequence strata remain non-biological proxies
  and Pfam coverage remains 225/308. Receipt payload/file SHA-256 values are
  `509a7f7c8fcae221be53d5d7e525e05c37a1314f6d17060c8ed6b68e8e4fc89e`
  and `581235213b161caeb41db441ca73428d669a7fa0c9a3ead3bba7632dfa63b1dc`;
  deterministic wheel SHA-256 is
  `5378c25f700a3f775aca232e379ea9e56b93a75310daead5d7dfdae082d9800e`.
  Installed-wheel exact verification passed. No fit partition, leakage audit,
  calibrated scorer, scientific validation, or public claim is authorized.
- A new installable
  `betelgeuze-engine-v2-posebusters-external-ranking-evaluate` command turns
  those exact test partitions into an actual, failure-inclusive external-
  reference result without fitting. It freezes and source-order-checks Vina
  total energy, GNINA CNN pose score, and Smina minimized affinity. Coverage is
  Vina 18/308, GNINA 17/308, and Smina 17/308; all-case Top-1/Top-5 counts are
  10/16, 15/16, and 10/15. Tie-invariant successful-pose average precision and
  95% case-cluster bootstrap intervals are 0.287330
  [0.174209, 0.512214], 0.668157 [0.534293, 0.886705], and 0.304352
  [0.183486, 0.541608]. All 872 failure observations, source-bound validity
  counts, and sequence-proxy/exact-Pfam-set/overlapping-Pfam views remain in the
  receipt. Payload/file SHA-256 values are
  `509556b0bcd9ec35f9ff4b1860613f267b2a96d73b18de44b61288498a838137`
  and `3f4965ba07be36c6233514d2545c1db0f604bc4245552be2180bcdb780a43dc1`.
  The byte-identical wheel above reconstructed both the test-partition and
  evaluation receipts exactly outside the checkout.
  The result does not audit external-model training overlap, establish
  calibrated internal-scoring evidence or representative benchmark coverage,
  or authorize scientific/product claims.
- A new installable
  `betelgeuze-engine-v2-posebusters-internal-diagnostic-ranking` command scores
  those exact Vina/GNINA/Smina pose pools before joining test labels. Its
  frozen, uncalibrated minimize policy sums UFF receptor–ligand van der Waals,
  PDBQT-charge Coulomb, exact source-atom RDKit UFF strain delta, and UFF
  overlap terms with fixed unit weights. The exact RDKit 2025.09.6/NumPy
  1.26.4 production run scored all 1,031 source-success poses with zero scorer
  failures and retained all 872 upstream failure observations. Coverage is
  18/17/17 of 308 cases, all-case Top-1/Top-5 counts are 2/5, 3/5, and 3/3,
  and successful-pose average precision is 0.113931
  [0.056090, 0.270781], 0.169927 [0.100789, 0.262457], and 0.106265
  [0.064622, 0.224549]. Payload/file SHA-256 values are
  `63a2f62cd465438f83e177b11ffd50483a2ff3f94c9399c308da2e8baee45b57`
  and `4e4acd968e2a32f4f6ff47b8412b9209b5afe6918bda2019fdc4e9e492a4f3b1`.
  The deterministic installed wheel at
  `5378c25f700a3f775aca232e379ea9e56b93a75310daead5d7dfdae082d9800e`
  reconstructed the receipt exactly outside the checkout.
  The result demonstrates complete deterministic execution, but it
  underperforms the fixed external source scores and is neither the validated
  reference force field nor a calibrated ranker. PoseBusters remains test-only;
  fitting requires a disjoint corpus and leakage audit.
- A new installable
  `betelgeuze-engine-v2-posebusters-external-ranking-reproduce` command adds
  `materialize-work-order`, `verify-work-order`, `materialize-result`, and
  `verify-result` modes for a preregistered second-host rerun. The work order
  exact-binds the accepted 308-case baseline chain, deterministic Engine v2
  wheel and source members, role-separated host/operator identities, and a
  single-use nonce before the external observation. A result must reuse the
  same archive/preparation/RCSB-Pfam roots while providing distinct
  ranking-intake, test-partition, evaluation, and all six engine
  execution/evaluation receipt and file roots. It compares every one of the
  924 engine/case rows, including failures, scores, Top-K outcomes, aggregate
  and family metrics, intervals, and source-validity counts. Synthetic
  pass/replay/input-drift/score-drift tests are present. No production work
  order or external result is emitted without real external host/operator
  identities; same-host exact verification does not satisfy independent rerun,
  physical custody review, nonce single-use review, or scientific acceptance.
- A claim-closed four-case rigid redocking diagnostic now generates bounded
  poses after a fixed seed-conformer rotation, uses the lowest-index matched
  native record only to define the pocket center, retains every score/failure,
  evaluates geometric validity and direct receptor-frame symmetry-aware RMSD,
  deterministically rigid-refines the initial diverse score Top-K with complete
  accept/reject traces, re-ranks, and reports Top-1/Top-5 plus oracle-best
  generation gaps. Its element-radius heuristic and rigid coordinate descent are
  not a force field, molecular minimizer, or calibrated ranker; torsions,
  supported-force-field refinement, disjoint holdout evidence, and external
  baselines remain missing.
- A bounded molecular-graph torsion-tree materializer emits a canonical
  all-bond receipt and deterministically selects only non-ring, non-terminal
  heavy-atom single-bond bridges, with narrow amide-, sulfonamide-, and
  phosphoramidate-like exclusions. It verifies zero-angle coordinate
  reconstruction and preserves covalent bond lengths across generated poses.
  It is not full resonance perception, ring/macrocycle closure, a torsion-energy
  model, or validated conformer generation. A separate failure-complete public
  flexible diagnostic now embeds these receipts, retains the zero-torsion seed
  baseline, samples later torsions deterministically and uniformly, and adds a
  fixed element-radius ligand nonbonded self-overlap term that excludes 1-2 and
  1-3 pairs before validity/RMSD evaluation and Top-K rigid refinement. Final
  score-order diversity selection excludes invalid poses. Torsion energy,
  bonded force-field strain, torsion refinement, force-field refinement, holdout
  evidence, and every docking claim remain absent.
- A bounded CPU `float64` canonical-ensemble reference path with constrained
  BAOAB Langevin NVT and optional molecular-centre isotropic Monte Carlo NPT.
  A domain-separated SHA-256 counter RNG, mutable orthorhombic cell, complete
  SHAKE/RATTLE state, accepted/Metropolis-rejected/domain-rejected barostat
  rows, finite-difference molecular pressure, and trajectory/barostat hash
  chains survive canonical bit-exact same-runtime restart. A separate all-step
  analyzer reports energy/temperature/volume/pressure series,
  initial-positive-sequence autocorrelation time, effective sample size,
  normal-approximation confidence intervals, target bias, constraint residuals,
  barostat acceptance, exact restart, and every failed metric row. Explicit
  TIP3P/Na+/Cl- direct-Ewald NPT is exercised, but no accepted equilibration,
  external ensemble comparison, liquid-property evidence, two-host receipt,
  GPU parity, or scientific/product claim exists.
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
  configuration, residual maxima, cumulative iterations, explicit CPU/dtype/
  Torch runtime identity, and bit-exact same-runtime restart. An optional
  neutral orthorhombic direct-Ewald mode now
  exactly replaces the frozen v1 screened-Coulomb energy/force with bounded
  shifted-real, reciprocal, self, and exclusion/1-4 correction components and
  binds its canonical config into restart identity. Constraint/mass assignment,
  scientific drift or Ewald-convergence acceptance, independent
  SHAKE/RATTLE/Ewald and cross-host reproduction, PME, net-charge background,
  independently accepted thermostat/barostat or NVT/NPT statistics,
  triclinic-cell, GPU-parity, and product claims remain blocked.
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
  bootstrap intervals. Evaluation schema v2 also retains ranked scores/labels
  and failure codes, computes tie-invariant pose-level average-precision PR-AUC,
  over successfully scored/labeled poses, records successful/failed/all-pose
  denominators so scoring failures remain visible, and uses case-cluster
  bootstrap intervals overall and per target family. Single-class or
  failure-only families remain explicitly unavailable. No public dataset,
  fitted model, result, independent rerun, or scientific/product claim is
  bundled.
- A claim-closed pose-ranking confidence evaluation bound to evaluation schema
  v2. It retains case decisions and failure denominators, reports Brier score,
  fixed-bin ECE/reliability rows, threshold abstention/coverage/selective risk,
  tie-inclusive risk-coverage points, deterministic case-cluster intervals, and
  target-family scopes. Its logistic top-1/runner-up score-margin signal is
  explicitly an uncalibrated proxy; no disjoint probability calibrator,
  reviewed threshold, public result, or confidence claim is bundled.
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
- An identity-bound chemistry-aware pose-validity contract layered on that
  exact reference scorer. One atomic evaluation retains the four score terms,
  proposal/problem/parameter digests, pair-specific LJ-minimum contact ratios,
  worst receptor--ligand and topology-admitted ligand-internal overlaps, and
  attractive/repulsive partial-charge interaction sums. The validity result
  gates both clash scopes, signed strain, and repulsive Coulomb only against
  explicit caller thresholds. It fails closed for unsupported metals/cofactors
  and incomplete aromatic/stereo coverage; thresholds are unfitted and every
  result remains scientifically unvalidated and claim-closed.
- A failure-inclusive reference-docking applicability and abstention contract.
  It binds the exact problem, config, canonical systems, topologies, and
  caller-supplied parameter identities while retaining every detectable
  canonical-input, chemistry, parameter, and execution blocker. Metals,
  receptor nonpolymer cofactors, formal/partial-charge failures, parameter
  coverage, and capacity produce explicit abstentions; aromatic or declared-
  stereo inputs may construct only an interaction-incomplete diagnostic
  scorer. Admission never establishes scientific applicability, validated
  refinement, or a product claim.
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
