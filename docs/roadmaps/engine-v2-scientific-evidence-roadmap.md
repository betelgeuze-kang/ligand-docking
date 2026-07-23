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
| 4. Docking evidence | Pose success, scoring, ranking, and valid screening/enrichment metrics; disjoint probability calibration; Brier/ECE and reliability rows; selective-risk/coverage and abstention; uncertainty intervals; predefined acceptance thresholds; complete denominator | A raw score-margin diagnostic or one passing metric does not establish calibrated confidence, general docking accuracy, or commercial fitness. |
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
- Preserve the frozen v1.1 four-case public redocking protocol definition and its
  exact PoseBusters-commit input, license-metadata, endpoint, failure-denominator,
  ligand-identity-seed, fixed-receptor-frame RMSD, and scorer-source identities.
  Preserve its bounded source-bound offline materializer: seed coordinates are
  ignored; every reference record is retained; all directional-V2000-stereo-
  preserving labeled-graph matches and bounded seed automorphisms contribute to
  the minimum direct receptor-frame RMSD without ligand alignment. It bundles
  and fetches no data, authorizes no docking execution or publication, and is
  neither independent chemical standardization, complete atom-stereo support,
  a statistically representative public benchmark result, nor a PoseBusters-
  equivalence claim.
- Preserve the separate offline suite materializer that verifies all twelve
  receptor/identity-seed/reference files and emits exactly four canonical
  success/failure rows. Completion of all four reference-materialization rows is
  only an input-readiness observation. Pose generation, receptor-ligand validity,
  scoring/ranking, same-input Vina/GNINA/Smina result receipts, public
  denominators and confidence intervals, and an independent rerun remain
  subsequent gates. Preserve the separate preparation work-order contract that
  verifies exact prepared PDBQT and preparation/binary identities and freezes
  native-defined boxes plus common search parameters without executing an
  engine. Work-order readiness is not external-baseline evidence.
- Preserve the public split-provenance layer that distinguishes PDBbind v2020
  fit, 285-case CASF-2016, and the published 308-case PoseBusters Benchmark;
  freezes the official PoseBusters case-list identities; and binds exact case,
  family, cofactor, chemistry, release, and canonical protein-chain-set
  provenance. Require a source-bound all-chain Smith-Waterman/BLOSUM62 maximum-
  identity receipt, explicit temporal/similarity policy, generic calibration
  leakage binding, and exact all-case/target-family denominators. This contract
  includes no PDBbind access approval, full dataset manifest, executed sequence
  audit, benchmark result, or independent review; those remain evidence gates.
- Preserve the PoseBusters pose-ranking intake boundary that binds the exact
  Vina/GNINA/Smina execution/evaluation receipts and RCSB/Pfam annotations as
  test-only data. It must retain all 924 engine/case rows, all 1,031 evaluated
  pose rows, and all 872 failure rows with engine-namespaced component terms,
  RMSD labels, validity labels, all-case Wilson intervals, and caller-pinned
  receipt roots. Preserve the linked pose/scaffold identity overlay: its exact
  RDKit 2025.09.6 reconstruction assigns topology-aware coordinate identities
  to 1,031/1,031 generated poses, retains all 872 failures, and assigns
  start/reference-matched scaffold identities to 308/308 cases. It exposes 229
  scaffold groups, including 33 explicitly named acyclic full-heavy-graph
  fallbacks, with zero generated/source chemistry or cross-engine topology
  mismatches. The coordinate and scaffold identity gates are therefore closed.
  Do not materialize a generic calibration partition until complete
  target-family dispositions, a disjoint fit manifest, and target/ligand/
  scaffold leakage audits are present. PoseBusters test labels must never be
  consumed by a fit API.
- Preserve the bounded extraction-free PoseBusters archive intake that binds
  the exact published ZIP and 308-ID selection, audits the complete central
  directory, and retains the four required streamed artifact identities for
  every selected case in a no-overwrite receipt. The observed 308/308 local
  intake closes only the public-carrier identity sub-gate. Protein sequence and
  release-date provenance, family assignments, preparation, pose generation,
  validity, scoring, external baselines, and independent rerun remain open and
  must use all 308 denominator rows.
- Preserve the extraction-free PoseBusters corpus-audit layer that exactly
  reexecutes the intake and retains parser failures, heavy labeled connectivity,
  raw directional/aromatic V2000 representation, element/formal-charge,
  ligand-capacity, metal, and non-water-cofactor inventories with Wilson 95%
  intervals over all 308 cases. The observed local receipt audited 308/308 and
  matched heavy connectivity for 308/308, but only 34/308 reached the
  provisional scorer chemistry boundary and 0/308 were admitted without
  parameters and partial charges. Raw bond marks are not an independent
  aromaticity or atom-stereo oracle, and this preflight is not pose validity,
  docking, external-baseline, or benchmark evidence.
- Preserve the extraction-free PoseBusters native-crystal-pose geometry
  preflight layered on exact intake and corpus receipts. Its all-308 receipt
  binds fixed-radius receptor overlap, topology-excluded ligand self-overlap,
  native/start heavy-bond delta, exact target-CCD residue-name retention,
  implementation sources, and CPU float64 runtime. The observed exact rerun
  processed 308/308 with zero failures; element geometry was evaluable for
  159/308, the bounded heuristic conjunction was 89/308, and its intersection
  with the reference-scorer chemistry boundary was 15/308. Complete pose
  validity remains 0/308. Treat all values only as native positive-control
  diagnostics: covalency, explicit-hydrogen completeness, chemistry, force-field
  strain, generated-pose validity, PoseBusters equivalence, redocking,
  scoring/ranking, family metrics, and independent rerun remain open.
- Preserve the strict PoseBusters external-input preparation receipt layered on
  exact intake and corpus identities. The pinned optional Meeko/RDKit runtime,
  complete AD4/Gasteiger defaults, Python/dependency payloads, source roles,
  native-defined box centers, and private PDBQT bytes are bound. The observed
  exact rerun attempted the 34-case chemistry subset, prepared 18 input pairs,
  retained 15 template failures plus one receptor-construction failure, and
  abstained on the other 274 rows. Do not enable `allow_bad_res` or silently
  repair/delete residues to increase coverage. Preparation availability alone
  is not charge/type validation, generated-pose evidence, same-input external-
  engine evidence, target-family performance, leakage control, or an
  independent rerun; the next layer closes only the bounded Vina execution
  substep and the denominator stays 308.
- Preserve the prepared-ligand charge/type diagnostic layered on that exact
  preparation identity. It keeps all 308 rows, interprets only strict Meeko
  `SMILES IDX`/`H PARENT` mappings, retains `G0` macrocycle pseudoatoms, and
  directly recomputes the same 12-iteration RDKit Gasteiger algorithm. Frozen
  RDKit 2022.09.5 and 2025.09.6 observations each evaluated 18 cases and 481
  real atoms with zero failures; maximum three-decimal PDBQT charge delta was
  0.0004979832249129013 e, and all bounded element/type, aromatic-carbon, and
  pseudoatom checks passed. The 481 expected charges were bitwise identical
  across versions. Observation payloads are
  `df57b0d48ba905e0f132b66a3b4d4fc344fffc4a40f1d78de181c0264bedba8f`
  and `6d3389ed55e7d47c8e0b0076c485b3f4ee7590cb3f9ddcd12db89030e92b6b50`;
  comparison payload is
  `ab9cf4b72d3af848dd48484fcbb203268fe8d7336ec552ffe52c360dca972b5f`.
  Source-tree and isolated installed-wheel verification passed, and two wheels
  matched at
  `9d1c96336c1fa55051ab3e0fc2192d990860c644dc5f39a0685f07c39613124e`.
  Do not call this an independent charge/type oracle: both versions execute the
  same algorithm, AD4 semantics are not independently reproduced, the source
  SDF and receptor assignments are not audited, and unsupported chemistry
  remains outside the prepared subset.
- Preserve the separate Open Babel 3.2.1 charge and AD4-type implementation
  comparison over the exact same 308-row preparation identity. It evaluated
  all 18 prepared cases without comparison failure, retained 16 preparation
  blocks and 274 chemistry abstentions, compared 481 real atoms, and excluded
  only the two retained `G0` pseudoatoms from real-atom statistics. Charge
  MAE/RMSE/max absolute delta was 0.0038510594375734796 /
  0.012204476318346003 / 0.18097866788513423 e. Exact AD4-type agreement was
  476/481 atoms; the five explicit differences were three `SA`/`S` and two
  macrocycle `CG0`/`C` assignments. Exact source-tree and installed-wheel
  verification reproduced receipt payload SHA-256
  `7754c4b56e10d4543b064c23daaf69ab99e098fda81bfd9fbaecc8694439d943`,
  and two package builds matched at wheel SHA-256
  `d0fc6a2acce76f2e3d23915b533528263d10e8277c0cf6feafd09e318c6d9529`.
  This closes only the independent-implementation execution gap. Do not call
  it a charge oracle or a validation gate. Exact-tag source inspection now
  explains the two `CG0`/`C` rows as Meeko macrocycle-extension vocabulary and
  the three `SA`/`S` rows as a real neutral-thioether acceptor-semantics
  disagreement. RDKit 2022/2025 six-versus-12-versus-24 iteration controls
  also show that the methylsulfone maximum charge delta comes primarily from
  different sulfur parameter-selection branches, not iteration count alone.
  Those are implementation dispositions only: no charge threshold was
  preregistered, thioether acceptor semantics and sulfone charge accuracy are
  not scientifically adjudicated, and source-SDF equivalence, receptor
  assignments, representative unsupported chemistry, second-host
  reproduction, and independent review remain open.
- Preserve the preregistration-first PySCF 2.14.0 fixed-geometry sulfur QM-ESP
  diagnostic layered on that exact archive/preparation/Open Babel chain. The
  protocol was registered before QM execution and binds the four selected
  sulfur cases, all 308 dispositions, source SDF geometry and explicit
  hydrogens, neutral singlet RHF/6-31G* spherical-basis settings, official
  wheel and installed dependency identities, one native thread, four
  equal-weight Lebedev-110 molecular-surface shells, same-site model
  projections, metrics, hashes, failure contract, and non-promotion decision
  gates. Protocol payload SHA-256 is
  `0927260a16f1e09211fb601fade1725e21d35d221d04e69cfd2c624da7c06137`.
  The observation evaluated all 4 scoped cases with zero QM failures and
  retained 304 scope abstentions. Meeko had the lower global weighted ESP RMSE
  in 4/4 cases and Open Babel in 0/4, with small descriptive margins. Exact
  source-tree and isolated installed-wheel observation reexecution reproduced
  payload SHA-256
  `402d1795f18b7eb0c87d8537f3b427fe116c0845bf1337b21e24752cef7e52e6`;
  two builds matched at wheel SHA-256
  `b4564648dbf3fcb681e0b73d1dcbcc2fd96ed10a0fe4a321149fe38545d0d73d`.
  This closes the bounded independent molecular-field execution gap only. No
  accuracy threshold was preregistered, HF/6-31G* is not an absolute oracle,
  atom charges are not observables, four fixed geometries are not
  representative chemistry, and ESP cannot adjudicate the neutral-thioether
  acceptor type. Keep `charge_accuracy_pass=null`,
  `scientifically_validated=false`, and `claim_safe=false`.
- Preserve the preregistration-first default-Vina 1.2.7 sulfur-type invariance
  receipt that resolves the active product-path consequence without deciding
  chemical correctness. Exact tag source maps both `AD_TYPE_S` and
  `AD_TYPE_SA` to element sulfur and then `XS_TYPE_S_P`; default Vina selects XS
  typing, and the XS acceptor set excludes sulfur. The target-only `SA` to `S`
  counterfactual preserved every other PDBQT byte and rescored all 60 retained
  poses across the three neutral-thioether cases. All eight public score
  components were exactly equal for 60/60 pairs, with zero failures and 305
  scope abstentions. Protocol and observation payload SHA-256 values are
  `81f52bbf68518e1d09e0462f8124ac1a810c7cc502ff8923175703e62b28b57f`
  and `a08ced8bbe0dbecc503f8e5eedf96d239130d0dbced897427694afe61742d406`;
  source-tree and installed-wheel exact reexecution passed, and two wheels
  matched at
  `fcbdc2df96c3b7df53f90e50e90688898147bf4665f2a816eb7d82382f547535`.
  Keep the claim narrow: fixed-pose default-Vina score invariance passes, but
  search, complete AD4 scoring, and chemical hydrogen-bond semantics were not
  evaluated.
- Preserve the completed preregistration-first neutral-thioether
  donor-acceptor interaction-energy receipt as a bounded AD4/chemical-semantics
  gate. It freezes the prior QM/Vina chain, exact Vina 1.2.7 AD4 source,
  PySCF/PySCF-dispersion wheels, three fixed thioether models, one methanol O-H
  donor, six S-H distances and one plane-normal control, all complex/ghost
  geometries, B3LYP-D3(BJ)/def2-SVP counterpoise, exact AD4 `S-HD`/`SA-HD`
  formulas and weights, every failure row, and thresholds before calculation.
  The observation completed 21 geometries and 63 SCFs with zero failures,
  retained 305 scope abstentions, and passed both local gates 3/3. QM minima
  were at 2.5 A and -4.758 to -5.258 kcal/mol. Protocol and observation payload
  SHA-256 values are
  `f0b0d84551e63272509acaf967996496cc7100cd2a58b71392fe38bce7d8194c`
  and `30d9ceb83aed88fa45b7bc8c8282e6a50ce0299c9f54b21ce0c8885775c35fce`;
  exact source-tree and fresh installed-wheel observation reexecution matched,
  and two wheels matched at
  `bb47ad0c5dcb0a5b9d298d2ba7f423910c11bf03c13f1691c0ecbec9c6db6f56`.
  Keep the disposition narrow: every plane-normal control was 0.551 to 0.784
  kcal/mol more favorable, and one donor, three fixed gas-phase models, and
  isolated pair terms do not establish general directionality, representative
  chemistry, or a complete AD4 score. Require a second CPU-host exact
  reproduction and independent reviewer receipt before scientific
  adjudication; keep `scientifically_validated=false` and `claim_safe=false`.
- Use the implemented
  `betelgeuze-engine-v2-posebusters-sulfur-reproduce` workflow for that
  external step. Its work order freezes two distinct host identities,
  role-separated operators, a single-use nonce, the exact Engine v2 wheel and
  source members, and the shared runtime projection before execution. Its
  verifier retains and rederives all 308 dispositions, 21 points, 63 SCFs,
  numeric tolerances, and failures; its final approval is detached Ed25519 with
  out-of-band trust, expiry, revocation, and supersession. Implementation is
  complete locally, but no external work order/result/reviewer receipt has
  been issued. Do not mark either evidence gate complete until those real
  artifacts exist.
- Preserve the failure-inclusive Vina 1.2.7 execution receipt layered on that
  exact preparation identity. The frozen single-CPU run retains all 308 rows,
  generated PDBQT bytes, all five canonical binary64 Vina energy components,
  bounded diagnostics, and engine/configuration/source payload identities. The
  observed production run attempted and succeeded on 18/308, recorded zero
  engine failures, retained 16 preparation blocks and 274 chemistry abstentions,
  and stored 355 poses; exact source-tree and installed-wheel reexecution
  matched receipt payload
  SHA-256
  `37b3df7c4c14d739d9fca3970dc73293a48909372314a8dfe1da5bcd956694ae`.
  Two pinned-tool wheel builds also matched byte-for-byte at SHA-256
  `68380b90af9ac286a70e264cb2603288ae5a2d639f32f27b1ae376bdaebc6228`.
  This closes only the bounded Vina execution substep.
- Preserve the failure-inclusive PoseBusters 0.6.5 generated-pose evaluation
  receipt layered on that exact source/preparation/Vina chain. It retains all
  308 dispositions and all 133 typed `redock` report values per generated pose,
  with physical validity and direct symmetry-aware receptor-frame RMSD as
  separate endpoints. The observed run evaluated 355/355 poses, recorded 325
  physical-validity passes, Top-1 RMSD <= 2 A for 10/18 Vina-success cases, and
  Top-5 for 16/18. Installed-wheel exact reexecution matched payload SHA-256
  `9c680e1edd08bfa07c1c71164b696ae050f180c3a2bb04bc91fd5d163a965b86`;
  two deterministic builds matched at wheel SHA-256
  `b0248a218aaea0ef3f00e65d6f77e077cdd81a4c7ac37a128edd7833e3ce49a8`.
  This closes only validity/RMSD on the strict 18-case Vina subset.
- Preserve the same-input GNINA 1.3.3 and Smina 2019-10-15 execution receipts
  and their PoseBusters 0.6.5 evaluations. Each execution retained all 308 rows,
  attempted 18 prepared pairs, succeeded on 17, and explicitly failed
  `7UAW_MF6` on unsupported prepared AutoDock type `CG0`. GNINA retained and
  evaluated 340/340 poses, with 304 physical-validity passes and conditional
  Top-1/Top-5 RMSD <= 2 A of 15/17 and 16/17. Smina retained and evaluated
  336/336, with 312 passes and 10/17 and 15/17. Installed-wheel exact
  reexecution matched evaluation receipt SHA-256
  `0959201d6165d82041447be820977de7ac8ba64b13d1f237ad5b8c914a290259`
  and `0590067f9c1731f6ebcbff36f54ba08d9265f32454b54fa03b7df0dbc328b930`.
- Preserve the conservative observed-target-cluster projection across those
  exact Vina/GNINA/Smina receipts. First-model `ATOM` residue-label sequences,
  minimum 20-residue chains, a 90% global edit-similarity link threshold, and
  connected components produced 296 clusters from 308 cases, including 11
  multi-case clusters, maximum size 3, and 13 links. Vina cluster coverage and
  complete coverage are 18/296 and 17/296; GNINA and Smina are 17/296 and
  16/296. Covered-cluster any-member Top-1/Top-5 RMSD hits remain 10/18 and
  16/18, 15/17 and 16/17, and 10/17 and 15/17. Exact reexecution matched
  payload SHA-256
  `34d782567e816206dcaf2be5207e424b8611a081c9ca6d51bc9500e42ec81e5e`
  and file SHA-256
  `fc69398c600c032f7f5c18ca1fc8baedd51c93db0f933c2320d1f597265750aa`.
  Two pinned-tool wheel builds matched at SHA-256
  `050d06e9fc49ef3c79bcaefbd8854de85fce0ce7fe4a56cc83418a460280a597`,
  and installed-wheel exact verification reproduced the receipt.
  Treat this only as a near-identity proxy: it is not biological target-family
  annotation, every external fit/training manifest is missing, target and
  ligand/scaffold leakage are unevaluated, and
  `leakage_control_passed=false`.
- Preserve the normalized official RCSB/Pfam observation and pocket-associated
  family projection layered on that proxy receipt. Runtime verification is
  network-free and raw API responses are not retained. Exact archive chains
  map to exact RCSB `asym_id` first and exact `auth_asym_id` only as fallback;
  no truncation, alias, or removed-entry remapping is admitted. The 308-case
  receipt records 306 complete mappings, 299 UniProt cases, 225 Pfam cases,
  explicit unmapped `6Z14_Q4Z`, and removed `7D6O_MTE`. It retains 199 Pfam
  multi-label families and 149 exact Pfam-set partitions with every engine
  failure and abstention. Snapshot payload/file SHA-256 values are
  `4d05e0127bb4c4dfedb5fa0a5f2e11d7de22aae481d34d3840676d04d367b51a`
  and `2287ffc895b28828ff39568f3ee0b98707b8160f04fa10196b469fe9ba722358`;
  target-family receipt payload/file values are
  `ce7d0f32054f05a328554fa04e38964768d2e734157aa9eca4ceb431c2a87076`
  and `164ef81d7e49dbf32aab6eef56325dfd2ee57e889304e7f3ac0dff7f11a36761`.
  Byte-exact local reexecution matched. Two pinned-tool wheels matched at
  `02d837ed5f624505a5a02bf1a5489f8aec1dcf0bacd15ef39b0fa6abf8526deb`,
  and isolated installed-wheel verification reproduced both receipts. The
  HTTPS observation is not
  independently RCSB-signed and Pfam coverage is incomplete.
- The next evidence slice must obtain engine fit/training manifests, then bind
  target-sequence and ligand/scaffold overlap against those manifests. The
  independent implementation has now executed and exact source rules explain
  the observed differences. The next charge/type work is a preregistered
  quantum electrostatic-potential reference protocol for the neutral
  thioethers and `7F5D_EUO` methylsulfone, with error metrics defined on the
  molecular field rather than treating either atom-charge partition as an
  oracle. Then
  use the frozen external-reproduction workflow to execute the
  second-CPU-host rerun and obtain reviewer acceptance without
  relabeling either family or charge receipt as leakage-controlled or
  independently validated. Calibration and any benchmark or product claim
  remain open.
- Treat the executable four-case rigid geometry lane only as a pipeline
  diagnostic. It now separates proposal coverage (oracle-best valid RMSD and
  generated-hit count) from score selection (Top-1/Top-5) while retaining all
  candidate failures. Because its pocket is native-defined and its score is an
  unfitted element-radius heuristic, any observed number is development evidence
  rather than a holdout result. Do not tune and then promote this four-case
  cohort; freeze a disjoint public evaluation partition before threshold review.
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
- Keep the bounded CPU `float64` velocity-Verlet NVE path as implementation
  evidence only. It requires explicit masses and caller-bound parameters,
  rebuilds compact neighbors at every force evaluation, supports non-periodic
  or full 3D orthorhombic PBC with wrapping, optionally applies canonical-pair
  inverse-mass SHAKE/RATTLE, and binds constraint residual/iteration, binary64
  trajectory, and exact checkpoint/restart identities. A neutral CPU `float64`
  orthorhombic direct-Ewald option now replaces screened Coulomb with explicit
  real/reciprocal/self/exclusion-scaling components and is restart-bound. It
  does not assign general solute constraints or masses and does not satisfy an NVE-drift or
  Ewald-convergence acceptance protocol, independent SHAKE/RATTLE/Ewald or
  two-host reproduction, PME, net-charge-background, independently accepted
  thermostat/barostat or NVT/NPT-statistics, triclinic-PBC, CPU/GPU-parity,
  scientific, or product gates.
  A separate bounded preparation now freezes one exact Amber TIP3P/
  Joung--Cheatham Na+/Cl- source snapshot and deterministically materializes
  water/ion topology, parameters, exclusions, rigid-water constraints, full
  orthorhombic PBC, neutralization, molarity, clearance diagnostics, and a
  canonical placement trace. Neutral and counterion cases execute through the
  actual direct-Ewald and constrained-NVE restart path. This closes the missing
  explicit-particle wiring only: the initial lattice is unequilibrated and no
  independent source transcription, energy/force parity, water/ion observable,
  two-host, or scientific acceptance receipt exists.
  A bounded canonical-ensemble path now layers constrained BAOAB Langevin NVT
  and molecular-centre isotropic Monte Carlo NPT over that exact force,
  constraint, PBC, and explicit-particle stack. Seeded counter-RNG position,
  mutable cell, all barostat proposals and dispositions, energy/coordinate/
  volume/finite-difference molecular-pressure traces, and trajectory/barostat
  hash heads survive canonical pause/serialize/resume. A separate all-step
  analyzer emits autocorrelation time, effective sample size, confidence
  intervals, target bias, constraint residual, acceptance count/fraction,
  exact-restart, and every predeclared failed metric. This closes the missing
  thermostat/barostat/statistics implementation surface only. Independent
  integrator and pressure comparison, reviewed burn-in and thresholds,
  production-length liquid/ion distributions, density/compressibility/heat
  capacity, two-host reproduction, and CPU/GPU parity remain required.
  A bounded analyzer now requires every evaluated frame plus a genuine
  pause/resume run and emits energy max/RMS/slope, momentum max/RMS, instantaneous
  kinetic-temperature, current constraint residual, trajectory-byte identity,
  exact restart, and all nine predeclared pass/fail metric rows. This closes an
  implementation-observability gap only; independently reviewed thresholds,
  longer physical systems, external-integrator comparison, two-host receipts,
  and accepted NVE-drift evidence remain required.
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
  out-of-band trusted reviewer public key, Ed25519 integrity, and at most 30 days
  of validity. No trusted key or attestation is bundled, and review verification
  alone cannot authorize execution or fitting.
- Preserve the separate frozen single-run authorization receipt contract. It
  requires a still-valid verified review, pairwise-distinct authorization
  operator identity, an out-of-band Ed25519 public key, exact code/runner/environment/
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
  accepted production trajectory disposition, two-host reproduction, external-
  implementation comparison, applicability, fitting, and scientific gates closed. Complete
  ordered operational and independent-oracle coordinate traces, including every
  canonical binary64 raw/evaluated coordinate, per-step identities and digests,
  whole-trace digests, exact counts, accepted-energy-ledger consistency, and
  trace/step review dispositions, are now implemented as contract-integrity
  evidence. A frozen comparison contract additionally aligns every evaluation,
  applies predefined coordinate/energy max/RMS thresholds, retains branch,
  rejection, count, and expected-failure dispositions, and binds three exact
  checkpoint/restart digest comparisons through runner, writer, and result
  review. The refrozen v2.1 protocol uses internal half-tolerance projection
  convergence headroom while preserving the declared acceptance threshold. The
  non-production check passes all 14/14 rows and all three checkpoint equality
  rows, including both fixed-Born rows. This is not accepted production evidence.
  No key, attestation, approval, or production evidence is bundled.
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
- Preserve the verifier-only adjacent registry-epoch transition contract as an
  integrity boundary, not production evidence. It freshly re-verifies the
  previous same-epoch witness quorum, requires exact integer ordinal adjacency,
  carries the terminal state root unchanged into sequence-zero genesis, derives
  the genesis checkpoint from the complete context, and verifies disjoint
  previous/next Ed25519 quorums over one exact statement. No actual transition
  proof, next policy, keys, votes, or post-transition status is bundled; the
  verifier does not enforce witness locking, compare independent journals,
  exclude a quorum-signed sibling successor, establish realm-wide
  non-equivocation/global latest, or commit external CAS. Those externally
  provisioned controls remain prerequisites for any production evidence chain.
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
