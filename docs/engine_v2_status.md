# Independent Engine v2 Status

This document is the human-readable companion to
`config/independent_engine_v2_capabilities.yaml`. The YAML snapshot is validated
against `betelgeuze_engine_v2.capabilities.capability_snapshot()` and is the
machine-readable source of truth.

## Current implementation stage

```text
v2_at_s0_production_evidence_bundle_contract
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
  aromatic-specific or stereochemical physics. Its atomic score/diagnostic
  endpoint now also records exact proposal/problem/parameter identities,
  pair-specific Lorentz--Berthelot contact ratios and worst overlaps for
  receptor--ligand plus topology-excluded ligand-internal pairs, and separate
  attractive/repulsive screened-Coulomb sums. The linked chemistry-aware
  validity contract gates both clash scopes, signed strain, and aggregate
  repulsion only against caller-declared thresholds. Those thresholds are not
  fitted or reviewed; aromatic or declared-stereo inputs remain incomplete,
  metals/cofactors fail closed, and neither a validity nor docking claim is
  promoted. A separate identity-bound applicability assessment retains all
  canonical-input, chemistry, parameter, and execution blockers before scorer
  construction. It returns either the assessment plus the uncalibrated
  diagnostic scorer or an explicit abstention. Metal/cofactor, formal/partial-
  charge, parameter-coverage, identity, and capacity failures remain visible
  together; aromatic/stereo admission remains interaction-incomplete and
  claim-closed. A separate fit-only calibration
  contract accepts only an identity-audited `fit` partition, deterministically
  fits pairwise logistic term weights, binds the holdout identity commitment,
  and evaluates retained failure poses with all-case and target-family Top-1/
  Top-5/coverage bootstrap intervals. Evaluation schema v2 additionally retains
  ranked scores/labels and failure codes and reports tie-invariant pose-level
  average-precision PR-AUC over successfully scored, labeled poses, while
  all-pose coverage/failure counts keep scoring failures visible in the receipt.
  Deterministic case-cluster bootstrap intervals are reported overall and per
  family. Missing positive or negative successful labels produce an explicit
  unavailable metric. A bound confidence-diagnostic receipt additionally
  evaluates a logistic top-1/runner-up score-margin proxy with Brier, fixed-bin
  ECE, reliability bins, threshold abstention/coverage/risk, and tie-inclusive
  selective-risk curves overall and per family. Failed and single-success cases
  abstain but remain in all-case/all-pose denominators. This is not a fitted
  probability calibrator: no disjoint calibration partition, independently
  reviewed threshold, public partition, fitted model, or result is bundled;
- a failure-inclusive four-case rigid redocking diagnostic. It uses the
  lowest-index graph-matched native reference only to define the pocket center,
  applies a fixed non-identity rotation to the seed conformer before bounded
  rigid proposals, retains every candidate score/failure, evaluates complete
  bounded geometric validity and direct receptor-frame symmetry-aware RMSD, and
  applies deterministic rigid coordinate descent to the initial diverse score
  Top-K, re-ranks, and reports complete refinement traces, Top-1/Top-5, plus
  oracle-best generation diagnostics. The score and refinement objective use
  only fixed unvalidated element radii, contact/overlap/penetration terms, and a
  pocket-centroid restraint. They are not force-field energy, a molecular
  minimizer, or a calibrated ranker; there is no torsion sampling,
  supported-force-field refinement, charge-aware physics, disjoint holdout
  status, same-input external baseline, independent rerun, or public benchmark
  claim;
- a separate bounded molecular-graph torsion-tree materializer. It retains one
  receipt row per source bond, selects only non-ring/non-terminal heavy-atom
  single-bond bridges, excludes narrow amide/sulfonamide/phosphoramidate
  patterns, verifies zero-angle reconstruction, and preserves covalent bond
  lengths under proposal sampling. It is not full resonance perception,
  ring/macrocycle closure, a torsion-energy model, or validated conformer
  generation. A separate failure-complete flexible four-case diagnostic embeds
  the torsion receipt, retains the zero-torsion seed baseline, samples later
  torsions deterministically and uniformly, and adds a fixed element-radius
  ligand nonbonded self-overlap term excluding 1-2/1-3 pairs before
  validity/RMSD evaluation plus Top-K rigid refinement. Final selection excludes
  invalid poses before score-order diversity. It has no torsion-energy or bonded
  force-field strain term, does not refine torsions, and has no holdout or
  docking claim;
- a non-executing same-input Vina/GNINA/Smina preparation and work-order
  contract. It verifies exact prepared PDBQT bytes, source and preparation-tool
  provenance, frozen receptor-frame box definitions, deterministic search
  parameters, and exact external-engine executable/container identities. It
  retains all four preparation success/failure rows and emits no work orders if
  any prepared input fails. No real prepared inputs, external binaries,
  executions, result receipts, representative holdout, independent preparation
  audit, or independent rerun is bundled;
- a public split-provenance and pose-ranking linkage contract for PDBbind v2020,
  CASF-2016, and the published 308-case PoseBusters Benchmark. It freezes source,
  license/access, endpoint, official count, and PoseBusters case-list identities;
  binds case release, receptor/ligand/scaffold/protein-chain-set, family,
  cofactor, and chemistry dispositions; retains exact all-chain maximum sequence
  identity strata; and verifies generic calibration leakage plus all-case and
  target-family result denominators. No PDBbind authorization, actual full
  manifest, dataset bytes, sequence receipt, fitted model, result, or external
  review is bundled;
- an installable three-way public pose-ranking corpus intake. It securely
  binds canonical PDBbind-v2020 fit, complete CASF-2016 validation, and complete
  PoseBusters-308 test manifests plus all three pairwise sequence receipts. Its
  frozen policy checks exact case/PDB/target/receptor/ligand/scaffold/sequence
  disjointness, maximum sequence identity 0.90, fit→test and validation→test
  release order, sequence-method identity, and shared scoring/preparation
  identity. Configuration SHA-256 is
  `4972e41765076e09b7bbec43b7e506dede6ab48b01b173f62cd73a749f694681`.
  Inputs are caller-pinned canonical no-follow files and the receipt is
  mode-0600/no-overwrite. No licensed PDBbind/CASF manifests or executed
  sequence receipts have been supplied, so no production receipt or passing
  leakage claim exists; partitions, scores, labels, fitting, model selection,
  metrics, review, and claims remain absent;
- an installable PDBbind-fit/CASF-validation calibration-partition intake
  gated by a verified passing corpus receipt. It strictly loads canonical
  generic partitions, recomputes public-case bindings and pose-level leakage,
  preserves success/failure and positive/negative denominators, and records
  cases without both training classes. Validation labels are evaluation-only,
  fit failures require a separately bound training view, and no test input is
  accepted. Configuration SHA-256 is
  `c4b423063a36f38d7f6f098a38c7ea54b078c25f3cc04d060ae88638902ff8be`.
  No production receipt, fitted scorer, validation selection, test evaluation,
  or claim exists while genuine upstream corpus inputs are absent;
- an installable calibration training-view boundary gated by that passing
  partition-intake receipt. It uses fit-row `status` only, copies every success
  unchanged into an embedded training partition, and retains every failed row
  as a hash-bound exclusion disposition. It recomputes training-view/CASF
  leakage and provides a guarded deterministic-fit bridge without
  validation-label use or test-partition access. Configuration SHA-256 is
  `e5e202d10420b5a557b1227aa0f7735433ebaeadc1656f6b981c14453aeb25b8`.
  No production receipt, fit, selected model, metric, review, or claim exists
  while genuine upstream corpus inputs are absent;
- an installable extraction-free PoseBusters archive intake. It pins the exact
  published Zenodo ZIP and journal 308-ID selection, audits all ZIP paths,
  compression, sizes, counts, metadata, and symlink/encryption boundaries, then
  CRC-streams the four required members per selected case into a canonical
  failure-inclusive mode-0600 receipt. It neither fetches nor extracts data and
  executes no preparation, docking, scoring, or benchmark. A 2026-07-23 local
  ignored-state observation recorded 308/308 ready rows and 1,232 artifact
  identities with receipt payload SHA-256
  `e76c31517be668eb2073cd78a83dd0e2327a041fefe98e9dfed9bab3635b66c6`;
  exact reexecution matched. This is input identity only, not bundled public
  benchmark evidence or a docking claim;
- an installable, failure-inclusive PoseBusters 308 corpus audit layered on the
  exact intake receipt. It parses all receptor/native/start members without
  extraction and records element/formal-charge, metal, non-water cofactor,
  ligand-capacity, heavy labeled-graph, raw aromatic-bond, and raw directional-
  bond inventories with all-308 Wilson intervals. The 2026-07-23 ignored-state
  receipt audited 308/308 and reexecuted exactly: heavy connectivity was
  308/308; provisional scorer chemistry scope was 34/308; actual scorer
  admission was 0/308 because parameters and partial charges were not assigned.
  It performs no chemical aromaticity or atom-stereo perception, preparation,
  pose validity, docking, family analysis, external baseline, or benchmark;
- an installable, failure-inclusive PoseBusters 308 native-geometry preflight
  layered on exact intake and corpus receipts. A 2026-07-23 ignored-state exact
  rerun processed 308/308 with zero failures: element geometry was evaluable for
  159/308, the fixed-radius bounded conjunction was 89/308, six receptors
  retained a residue name equal to the case CCD, and the intersection with the
  reference-scorer chemistry boundary was 15/308. Complete pose validity remains
  0/308. This native-crystal-pose positive control performs no chemistry
  perception, force-field strain, generated-pose evaluation, PoseBusters oracle,
  docking, scoring/ranking, family analysis, external baseline, or benchmark;
- an installable, failure-inclusive PoseBusters 308 strict external-input
  preparation gate. It binds pinned Meeko/RDKit and transitive payloads, frozen
  AD4/Gasteiger defaults, source roles, native-defined box centers, and private
  no-overwrite PDBQT bytes. A 2026-07-23 ignored-state exact rerun attempted
  34/308 cases, materialized 18 receptor/ligand pairs, retained 16 strict
  receptor failures and 274 chemistry abstentions, and executed zero external
  engines or docking cases;
- an installable, failure-inclusive prepared-ligand charge/type diagnostic over
  that exact 308-row preparation. Frozen RDKit 2022.09.5 and 2025.09.6 runs
  each evaluated 18 cases, 481 real atoms, and two separate zero-charge `G0`
  pseudoatoms with no diagnostic failures. All evaluated cases passed the
  0.0005 e PDBQT serialization, element/type, aromatic-carbon, and pseudoatom
  checks; maximum serialization delta was 0.0004979832249129013 e. The two
  same-algorithm expected-charge vectors were bitwise equal for 481/481 atoms.
  Observation payloads are
  `df57b0d48ba905e0f132b66a3b4d4fc344fffc4a40f1d78de181c0264bedba8f`
  and `6d3389ed55e7d47c8e0b0076c485b3f4ee7590cb3f9ddcd12db89030e92b6b50`;
  comparison payload is
  `ab9cf4b72d3af848dd48484fcbb203268fe8d7336ec552ffe52c360dca972b5f`.
  Two deterministic wheels matched at
  `9d1c96336c1fa55051ab3e0fc2192d990860c644dc5f39a0685f07c39613124e`,
  and isolated installed-wheel verification reproduced all receipts. This is
  same-algorithm persistence/serialization evidence, not independent charge or
  AD4 type validation; receptor assignments, unsupported chemistry, a second
  host, and reviewer acceptance remain open;
- an installable, failure-inclusive Open Babel 3.2.1 independent-implementation
  comparison over that exact preparation identity. It evaluated all 18
  prepared cases without comparison failure, retained the other 290 blocked or
  abstained rows, compared 481 real atoms, and retained two excluded `G0`
  pseudoatoms. Charge MAE/RMSE/max absolute delta was
  0.0038510594375734796 / 0.012204476318346003 / 0.18097866788513423 e, and
  exact AD4 types agreed for 476/481 atoms. Exact-tag source inspection shows
  that the three `SA`/`S` rows are a neutral-thioether acceptor-semantics
  disagreement, while the two macrocycle `CG0`/`C` rows are Meeko's deliberate
  ring-closure vocabulary extension. A two-version RDKit iteration control
  shows that the methylsulfone maximum charge delta is driven primarily by
  sulfur parameter-selection semantics, not the six-versus-12 iteration count
  alone. Exact source-tree and isolated
  installed-wheel verification matched payload SHA-256
  `7754c4b56e10d4543b064c23daaf69ab99e098fda81bfd9fbaecc8694439d943`;
  two builds matched at wheel SHA-256
  `d0fc6a2acce76f2e3d23915b533528263d10e8277c0cf6feafd09e318c6d9529`.
  This closes independent-implementation execution, not independent scientific
  validation: there is no preregistered charge threshold or quantum oracle,
  and the thioether acceptor choice plus sulfone charge accuracy remain
  scientifically unadjudicated. Source-SDF equivalence, receptor auditing,
  unsupported chemistry, a second host, and reviewer acceptance remain open;
- an installable, preregistration-first PySCF 2.14.0 fixed-geometry sulfur
  QM-ESP diagnostic over the exact same evidence chain. The registered
  protocol freezes four sulfur cases, source SDF coordinates and explicit
  hydrogens, neutral singlet RHF/6-31G* spherical-basis settings, a
  single-thread official-wheel runtime, four equal-weight Lebedev-110 surface
  shells, same-site Meeko/Open Babel charge projections, all metrics and
  failure rows, and the full 308-case denominator before QM execution. The
  local observation evaluated 4/4 scoped cases with zero QM failures, retained
  304 scope abstentions, and descriptively labeled Meeko as lower global
  weighted ESP RMSE in 4/4 cases. Protocol and observation payload SHA-256
  values are
  `0927260a16f1e09211fb601fade1725e21d35d221d04e69cfd2c624da7c06137`
  and
  `402d1795f18b7eb0c87d8537f3b427fe116c0845bf1337b21e24752cef7e52e6`.
  Exact source-tree and isolated installed-wheel observation reexecution
  matched; two builds were byte-identical at wheel SHA-256
  `b4564648dbf3fcb681e0b73d1dcbcc2fd96ed10a0fe4a321149fe38545d0d73d`.
  The model differences are small, no accuracy threshold was preregistered,
  and the field comparison cannot decide neutral-thioether `SA`/`S`
  hydrogen-bond semantics. The bounded interaction-energy result below still
  leaves directionality, a second CPU host, and independent review missing, so
  `charge_accuracy_pass=null`,
  `scientifically_validated=false`, `benchmark_executed=false`, and
  `claim_safe=false`;
- an installable, preregistration-first default-Vina 1.2.7 sulfur-type
  invariance audit. The protocol binds exact official-tag source, the
  preparation/Open Babel/Vina chain, 308 dispositions, all 60 retained poses
  for the three neutral-thioether cases, runtime/configuration identity, and a
  target-only PDBQT `SA` to `S` mutation. Exact source maps both AD types to
  element sulfur and then the same `XS_TYPE_S_P`; default Vina uses XS typing,
  whose acceptor set excludes sulfur. The observation recorded zero score
  failures and exact equality for every one of eight public score components
  in 60/60 pose pairs, while retaining 305 scope abstentions. Protocol and
  observation payload SHA-256 values are
  `81f52bbf68518e1d09e0462f8124ac1a810c7cc502ff8923175703e62b28b57f`
  and
  `a08ced8bbe0dbecc503f8e5eedf96d239130d0dbced897427694afe61742d406`.
  Source-tree and isolated installed-wheel exact reexecution matched, and two
  wheels were byte-identical at SHA-256
  `fcbdc2df96c3b7df53f90e50e90688898147bf4665f2a816eb7d82382f547535`.
  The bounded fixed-pose default-Vina invariance gate passes. Search, complete
  AD4 scoring, chemical acceptor semantics, representative chemistry,
  second-host reproduction, and reviewer acceptance remain open, so
  `bounded_default_vina_invariance_claim_safe=true` but
  `scientifically_validated=false`, `benchmark_executed=false`, and
  `claim_safe=false`;
- an installable, preregistration-first neutral-thioether interaction-energy
  diagnostic. The protocol binds the prior QM/Vina receipts, exact Vina 1.2.7
  AD4 source, PySCF 2.14.0 plus PySCF-dispersion 1.5.0 wheels, three fixed
  thioether models, a methanol O-H donor, six distances and one plane-normal
  control, every complex/ghost geometry, B3LYP-D3(BJ)/def2-SVP counterpoise,
  exact AD4 pair formulas, failures, metrics, and thresholds before execution.
  The local observation completed 21 geometries and 63 SCFs without failure,
  retained 305 abstentions, placed all three QM minima at 2.5 A and -4.758 to
  -5.258 kcal/mol, and passed the local acceptor and `SA` profile gates 3/3.
  Plane-normal controls were 0.551 to 0.784 kcal/mol more favorable, so
  directionality and general acceptor semantics remain unresolved. Protocol
  and observation payload SHA-256 values are
  `f0b0d84551e63272509acaf967996496cc7100cd2a58b71392fe38bce7d8194c`
  and
  `30d9ceb83aed88fa45b7bc8c8282e6a50ce0299c9f54b21ce0c8885775c35fce`.
  Exact source-tree and fresh installed-wheel observation reexecution matched.
  Two wheels were byte-identical at
  `bb47ad0c5dcb0a5b9d298d2ba7f423910c11bf03c13f1691c0ecbec9c6db6f56`.
  This is not representative chemistry or a complete AD4 score; second-host
  reproduction and reviewer approval remain open, so
  `chemical_acceptor_semantics_adjudicated=false`,
  `scientifically_validated=false`, `benchmark_executed=false`, and
  `claim_safe=false`;
- an installable two-host custody and independent-review workflow for that
  exact interaction result. It preregisters distinct host/operator identities,
  an execution nonce, the exact wheel/source/dependency projection, retains all
  308 rows, 21 points, 63 SCFs and failures, and rederives bounded cross-host
  differences before accepting a detached Ed25519 reviewer signature. The
  implementation and tamper tests are present; two deterministic builds
  matched at wheel SHA-256
  `5a6d82b8437b5d461e794f51a13bf127a51e429b3b4c5475b80fa8e417045acd`
  and outside-checkout installed-wheel CLI smoke passed. No genuine external-host
  result or independent reviewer receipt exists yet. Therefore
  `second_cpu_host_reproduced=false`,
  `independent_reviewer_receipt_approved=false`,
  `scientifically_validated=false`, and `claim_safe=false`;
- an installable, failure-inclusive PoseBusters Vina 1.2.7 execution layer. It
  consumes only that exact preparation receipt and private artifact tree, binds
  the engine/dependency/source/configuration payloads, retains every generated
  PDBQT and five canonical binary64 energy components, and preserves all 308
  dispositions. A 2026-07-23 local production receipt attempted and succeeded
  on all 18 prepared pairs with zero engine failures, retained 16 preparation
  blocks plus 274 chemistry abstentions, and stored 355 poses. Exact source-tree
  and installed-wheel reexecution matched payload SHA-256
  `37b3df7c4c14d739d9fca3970dc73293a48909372314a8dfe1da5bcd956694ae`.
  Two pinned-tool wheel builds were byte-identical at SHA-256
  `68380b90af9ac286a70e264cb2603288ae5a2d639f32f27b1ae376bdaebc6228`.
  This is the pose-generation layer for the evaluator below;
- an installable, failure-inclusive PoseBusters 0.6.5 generated-pose evaluation
  layer. It consumes the exact archive/intake/corpus/preparation/Vina chain,
  retains all 133 typed `redock` report values per pose, and separates the
  27-test non-RMSD physical-validity endpoint from direct symmetry-aware
  receptor-frame RMSD. The local 308-row receipt evaluated all 355 poses, of
  which 325 were physically valid; Top-1 RMSD <= 2 A was 10/18 and Top-5 was
  16/18 on the Vina-success subset. Installed-wheel exact reexecution matched
  payload SHA-256
  `9c680e1edd08bfa07c1c71164b696ae050f180c3a2bb04bc91fd5d163a965b86`;
  two pinned-tool wheel builds were byte-identical at SHA-256
  `b0248a218aaea0ef3f00e65d6f77e077cdd81a4c7ac37a128edd7833e3ce49a8`.
  independent scientific charge/type validation, family/leakage evidence,
  independent external rerun, and reviewer acceptance remain missing, so
  `benchmark_executed=false` and
  `claim_safe=false`;
- installable, failure-inclusive same-input GNINA 1.3.3 and Smina 2019-10-15
  execution and PoseBusters 0.6.5 evaluation layers. Both engine receipts retain
  all 308 rows, attempt 18 prepared cases, succeed on 17, and preserve the
  `7UAW_MF6` unsupported prepared AutoDock `CG0` failure. GNINA retains 340
  poses and evaluates 340/340, with 304 physically valid and conditional
  Top-1/Top-5 RMSD <= 2 A of 15/17 and 16/17. Smina retains 336 and evaluates
  336/336, with 312 physically valid and 10/17 and 15/17. Installed-wheel exact
  reexecution matches evaluation receipt SHA-256
  `0959201d6165d82041447be820977de7ac8ba64b13d1f237ad5b8c914a290259`
  and `0590067f9c1731f6ebcbff36f54ba08d9265f32454b54fa03b7df0dbc328b930`;
  two staged wheels match at
  `02356f803a448fdb3f77f5594ef4927eacc1221d319069fa4b81ace25dc4a8f0`.
  The rates are conditional on a narrow 17-case success subset, not a public
  benchmark. Complete target-family coverage, external-fit leakage control,
  independent-host, independent scientific charge/type validation,
  calibration, and reviewer gates remain open and `claim_safe=false`;
- an installable conservative observed-target-cluster binding over the exact
  Vina/GNINA/Smina evaluation receipts. First-model receptor `ATOM` residue-
  label sequences, minimum 20-residue chains, a 90% global edit-similarity
  threshold, and connected components reduce 308 cases to 296 clusters, with
  11 multi-case clusters, maximum size 3, and 13 retained links. Vina cluster
  coverage/complete coverage is 18/296 and 17/296; GNINA and Smina are 17/296
  and 16/296. Covered-cluster any-member Top-1/Top-5 RMSD hits are 10/18 and
  16/18, 15/17 and 16/17, and 10/17 and 15/17, respectively. Exact
  reexecution matches payload SHA-256
  `34d782567e816206dcaf2be5207e424b8611a081c9ca6d51bc9500e42ec81e5e`
  and file SHA-256
  `fc69398c600c032f7f5c18ca1fc8baedd51c93db0f933c2320d1f597265750aa`.
  Two pinned-tool builds match at wheel SHA-256
  `050d06e9fc49ef3c79bcaefbd8854de85fce0ce7fe4a56cc83418a460280a597`,
  and installed-wheel exact verification reproduces the receipt.
  The clusters are not biological family annotations, all three fit/training
  manifests are missing, target and ligand/scaffold leakage are unevaluated,
  and `leakage_control_passed=false` and `claim_safe=false`;
- an installable, network-free RCSB/Pfam target-family binding over the exact
  308-case archive, normalized official RCSB observation, and frozen target-
  cluster receipt. An inclusive 6 A native-ligand pocket associates protein
  chains; exact `asym_id` takes precedence over exact `auth_asym_id` fallback,
  with no truncation or replacement remapping. The current receipt retains 306
  complete mappings, 299 UniProt cases, 225 Pfam cases, the `6Z14_Q4Z` mapping
  failure, and removed `7D6O_MTE`, then projects all engine dispositions onto
  199 Pfam multi-label families and 149 exact Pfam-set partitions. Snapshot
  payload/file SHA-256 values are
  `4d05e0127bb4c4dfedb5fa0a5f2e11d7de22aae481d34d3840676d04d367b51a`
  and `2287ffc895b28828ff39568f3ee0b98707b8160f04fa10196b469fe9ba722358`;
  result payload/file SHA-256 values are
  `ce7d0f32054f05a328554fa04e38964768d2e734157aa9eca4ceb431c2a87076`
  and `164ef81d7e49dbf32aab6eef56325dfd2ee57e889304e7f3ac0dff7f11a36761`.
  Two pinned-tool wheels match at
  `02d837ed5f624505a5a02bf1a5489f8aec1dcf0bacd15ef39b0fa6abf8526deb`,
  and isolated installed-wheel verification reproduces both receipts.
  The observation is not source-signed, family coverage is incomplete, and
  external fit/training manifests remain absent, so leakage, benchmark,
  scientific, and product gates remain closed;
- an installable, test-only PoseBusters pose-ranking intake that caller-pins
  the three evaluation receipts and the RCSB/Pfam receipt, verifies all linked
  archive/preparation/execution file identities, and joins exact decomposed
  terms to RMSD and validity labels. It retains 924 engine/case rows, 1,031
  successful pose rows, and 872 explicit failure rows across the all-308
  denominator. Payload/file SHA-256 values are
  `b6526c7407602721f2ec74f09c8b99d4ecdc7336e69417ed6321840663de9ea0`
  and `88b756cd3e7d460edefe8330dbae6141e72492953a1af4e71bb60b1146574813`;
  deterministic wheel SHA-256 is
  `c8019fa070e8ca2fc598e26cbdf3c78394fcf9e0963ec656d736b3864681ac51`.
  The base intake keeps coordinate and scaffold hashes null; complete Pfam
  assignments, fit manifests, and leakage audits remain explicit. No
  calibration partition is materialized and all fit/claim flags stay false;
- an installable pose/scaffold identity overlay that binds every one of those
  1,903 intake rows to exact source artifacts. It assigns topology-aware
  coordinate hashes to 1,031/1,031 generated poses, retains 872/872 explicit
  failures, and assigns matched start/reference scaffold identities to 308/308
  cases. There are 229 scaffold groups, 15 repeated groups, maximum size 21,
  and 33 explicitly named acyclic full-heavy-graph fallbacks. Generated/start
  chemistry mismatch and cross-engine topology mismatch counts are zero.
  Start/reference full chemistry matches 305/308 and the three differences
  remain pending independent disposition. Payload/file SHA-256 values are
  `e7b92d0fc74b44f652c5196429812fe61165771906d9d487a13ec8719ac52995`
  and `fbf3fa34f974dc8bd35b6564a1c004931a9ea0177f25fd551769b91f4db089d8`;
  deterministic wheel SHA-256 is
  `d3c51e79dc4783f859b7b2ff4a8f8499d42da0d6a4378035c3cf2114b751285e`.
  Exact installed-wheel verification passed. Complete target-family coverage,
  fit provenance, leakage audits, external rerun, and review remain open;
- an installable PoseBusters ranking test-partition receipt that exact-binds
  the ranking intake, pose/scaffold identities, 296 observed-sequence proxy
  strata, and RCSB/Pfam annotations. It materializes three failure-inclusive
  `split_role=test` partitions: Vina 645 rows, GNINA 631, and Smina 627, each
  retaining all 308 cases. All 1,031 successful rows use coordinate identities;
  all 872 failures use unique domain-separated observation identities explicitly
  marked as non-coordinate. It revalidates 21 ranking, 36 proxy-cluster, and
  5,226 RCSB/Pfam metric rows plus Wilson intervals. Pfam remains 225/308 and
  the sequence strata are not biological families. Receipt payload/file
  SHA-256 values are
  `509a7f7c8fcae221be53d5d7e525e05c37a1314f6d17060c8ed6b68e8e4fc89e`
  and `581235213b161caeb41db441ca73428d669a7fa0c9a3ead3bba7632dfa63b1dc`;
  deterministic and installed-wheel SHA-256 is
  `5378c25f700a3f775aca232e379ea9e56b93a75310daead5d7dfdae082d9800e`.
  Fit partitions, fitting, leakage audits, independent rerun/review, calibrated
  scoring, scientific validation, and public claims remain absent;
- an installable external-engine PoseBusters ranking evaluator over that exact
  test receipt. It freezes Vina total energy, GNINA CNN pose score, and Smina
  minimized affinity before label evaluation and verifies source-order
  consistency. It retains all 308 cases and all 872 failures. Scored-case
  coverage is Vina 18/308, GNINA 17/308, and Smina 17/308; all-case
  Top-1/Top-5 counts are 10/16, 15/16, and 10/15. Successful-pose
  tie-invariant average precision is 0.287330, 0.668157, and 0.304352, with 95%
  case-cluster bootstrap intervals 0.174209–0.512214,
  0.534293–0.886705, and 0.183486–0.541608. Source-bound validity counts and
  sequence-proxy/Pfam views remain explicit. Receipt payload/file SHA-256
  values are
  `509556b0bcd9ec35f9ff4b1860613f267b2a96d73b18de44b61288498a838137`
  and `3f4965ba07be36c6233514d2545c1db0f604bc4245552be2180bcdb780a43dc1`.
  Coverage is too narrow for a representative benchmark; external-model
  training overlap, independent rerun/review, calibrated internal-scoring
  performance, scientific validation, and public claims remain absent;
- an installable internal PoseBusters ranking diagnostic over the exact same
  test partitions. It freezes a label-independent, uncalibrated minimize score
  with four unit-weight terms: UFF receptor–ligand van der Waals, PDBQT-charge
  Coulomb, exact source-atom RDKit UFF strain delta, and UFF overlap. The exact
  RDKit 2025.09.6/NumPy 1.26.4 run scored 1,031/1,031 source-success poses with
  zero scorer failures and retained 872 upstream failures. Vina/GNINA/Smina
  coverage is 18/17/17 of 308; all-case Top-1/Top-5 counts are 2/5, 3/5, and
  3/3. Successful-pose average precision is 0.113931, 0.169927, and 0.106265,
  with 95% case-cluster bootstrap intervals 0.056090–0.270781,
  0.100789–0.262457, and 0.064622–0.224549. Receipt payload/file SHA-256
  values are
  `63a2f62cd465438f83e177b11ffd50483a2ff3f94c9399c308da2e8baee45b57`
  and `4e4acd968e2a32f4f6ff47b8412b9209b5afe6918bda2019fdc4e9e492a4f3b1`.
  The deterministic installed wheel identified above reconstructed the receipt
  exactly outside the checkout.
  It is not the validated reference force field and is not calibrated.
  PoseBusters cannot be used for fitting; a disjoint fit/validation corpus,
  leakage audit, broader chemistry, independent rerun/review, and all science
  and product claims remain open;
- an installable external-ranking reproduction contract that preregisters the
  exact baseline chain, wheel/source members, distinct host/operator
  identities, and a single-use nonce before an external observation. A result
  must retain the same three fixed public-input roots, replace every ranking
  and six engine evidence receipt/file root, and compare all 924 engine/case
  rows including failures, scores, metrics, intervals, family views, and
  source-validity counts. Contract, replay, input-drift, and score-drift tests
  are present. There is no production work order or external result because
  genuine external identities and custody evidence have not been supplied;
  same-host exact verification is not independent execution, and all
  independence, review, science, and product-claim flags remain false;
- a benchmark manifest and one-row-per-case success/failure ledger;
- a frozen v1.1 four-case public redocking protocol definition bound to the
  PoseBusters packaged PDB examples at commit
  `1a5f26aa7270fafba21b7fec8b3633f4c4e45ead`, exact external receptor/reference
  SHA-256 values, MIT repository-license metadata, the RCSB CC0 usage-policy
  identity, an exact ligand-graph identity seed whose coordinates are ignored,
  predefined 2 Å symmetry-aware direct RMSD in the fixed receptor frame plus
  bounded-validity endpoints, all-case failure denominators, and exact scorer-
  source hashes. A separate bounded offline materializer verifies caller-
  supplied artifact bytes, retains every multi-record parse/match/failure row,
  ignores identity-seed coordinates, selects all stereo-aware labeled-graph
  matches, enumerates bounded graph automorphisms, and takes the minimum direct
  receptor-frame RMSD over every matched reference and admitted symmetry. Its
  exact source is protocol-bound. The separate installable offline suite command
  reads the exact protocol-relative files from a non-symlink local root, verifies
  all four receptors plus all eight ligand artifacts, and retains exactly four
  case rows with embedded canonical per-case receipts or failure codes. Its
  output explicitly records that no network fetch, docking prediction,
  pose-validity evaluation, or benchmark execution occurred. No raw data or
  public result is bundled, and the four fixtures do not establish statistical
  representativeness, independent chemical standardization, full atom-stereo
  interpretation, or PoseBusters Benchmark equivalence;
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
  no PME, net-charge background convention, independently accepted
  thermostat/barostat or NVT/NPT-statistics, triclinic-cell, scientific,
  product, or customer claim.
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
- a bounded CPU `float64` canonical-ensemble reference path. NVT uses the
  `B-A-O-A-B` Langevin splitting described by Leimkuhler and Matthews
  ([DOI 10.1063/1.4802990](https://doi.org/10.1063/1.4802990)), removes
  center-of-mass motion, and applies SHAKE after each coordinate drift plus
  RATTLE after the stochastic velocity update and final force kick. The normal
  draws come from a domain-separated SHA-256 counter stream whose seed and
  exact word index are checkpoint-bound. NPT adds fixed-absolute-delta-volume,
  isotropic Monte Carlo moves that scale mass-weighted molecular centres while
  preserving intramolecular coordinates, include the molecular-component
  Jacobian and pressure work in the Metropolis decision, and retain every
  accepted, Metropolis-rejected, or domain-rejected attempt. Pressure is
  observed through a central finite-difference molecular virial, matching the
  documented convention of OpenMM's
  [MonteCarloBarostat](https://docs.openmm.org/latest/api-python/generated/openmm.openmm.MonteCarloBarostat.html).
  Canonical checkpoints bind source/topology/parameters, thermostat/barostat/
  Ewald/constraint configs, coordinates, velocities, mutable cell, RNG index,
  energies, temperature, pressure observation, constraint iterations and
  residuals, attempt counts, and trajectory/barostat hash heads. Explicit
  TIP3P/Na+/Cl- preparations execute this constrained direct-Ewald NPT path and
  reproduce pause/serialize/resume bit-exactly in the same runtime.
- a bounded all-step NVT/NPT statistics analyzer. It requires
  `trajectory_stride=1`, and for NPT `pressure_observation_stride=1`, plus a
  genuine pause/resume endpoint. After a caller-fixed burn-in it reports
  potential, kinetic and total energy, kinetic temperature, and for NPT volume
  and molecular pressure. Each series includes mean, sample deviation,
  initial-positive-sequence autocorrelation time, effective sample size,
  standard error and a caller-fixed normal-approximation confidence interval.
  Predeclared metrics retain temperature/pressure target bias and CI coverage,
  effective sample size, constraint residuals, barostat acceptance bounds,
  minimum attempts, and exact restart failures. These are implementation
  contracts only: no accepted equilibration or production length, external
  distribution comparison, density/compressibility/heat-capacity result,
  independently reviewed thresholds, two-host receipt, GPU parity, scientific
  validation, product qualification, or customer route exists.
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
  active energy-force base chain uses v3 identities through run start, a v5
  runner/result writer, and a v2 result review; the active minimization base chain uses v4
  review/execution-environment identities, v5 authorization/result-receipt/
  nonce/run-start identities, a v8 runner, and v7 result writer/result review.
  Their hashes were
  refrozen through the full upstream dependency DAG. A separate read-only
  verifier recognizes 76 superseded contract documents by canonical projection
  hash. Superseded signed attestations, receipts, and run records are not
  supported and no compatibility claim is made for them.
  The energy-force lane now has a frozen Ed25519 result-review leaf with full
  case/variant/metric/failure/worker dispositions, independent recomputation of
  all 56 required metric occurrences from retained raw energy/force arrays with
  bitwise retained-value equality, and four-role separation. No
  production result, attestation, trusted result-reviewer key, or independent
  human approval is bundled. Upstream scientific review and authorization now
  use Ed25519 with public-key-only trust anchors; live dependency-manifest
  re-verification and external custody remain open.
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
  These artifacts and keys are not provisioned; both lanes' upstream chains use
  public-key-only Ed25519, while the process digest is bound but not externally
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
  Runtime-integrity companion v14 additionally binds the complete energy-force
  Ed25519 chain and the refrozen minimization
  trajectory-comparison contract together with the exact frozen custody-v1,
  review/authorization, reservation, external registry-proof, authenticated
  head/status receipt, later-head consistency, witness-quorum, adjacent epoch-
  transition continuity, and process-launch-identity contract SHA-256 values;
  runtime v8 through v13 are retained in the read-only legacy registry.
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
  author/reviewer identity separation, an out-of-band trusted Ed25519 reviewer
  public key, signature integrity, and a maximum 30-day validity window. No attestation or
  trusted key is bundled, and even a verified review cannot itself authorize
  execution or fitting. The current gate denies validation execution and parameter-fitting proposals.
  A separate authorization contract now binds a future verified review to a
  pairwise-distinct operator identity, out-of-band Ed25519 operator public key, exact code/runner/
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
  independent result-review dependency-manifest re-verification and provisioned
  end-to-end production custody remain absent. The energy-force Ed25519
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
  records are Ed25519 artifacts verified with public keys only, but it does not
  independently reverify the live dependency manifest or establish external
  custody. No production receipt,
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
- an offline-only OpenMM Reference external-oracle adapter. It pins the
  `OpenMM==8.4.0.post2` distribution, native build
  `8.4.0.dev-4768436`/commit `47684368dbbe4185d068be77d32a962059cfc37c`,
  and the `Reference` platform without a CPU fallback. The frozen mapping
  retains all 27 cases and 59 variants, evaluates the 47 pass variants, and
  records the 12 Engine-contract failures as
  `not_applicable_engine_contract`. Native bond/angle/periodic torsion forces
  and explicit CustomForce expressions preserve atom order, units,
  orthorhombic PBC, exclusions, pair scaling, the quintic switch, ordered-star
  improper, and fixed-Born self/pair components. A second canonical builder
  accepts all fourteen operational minimization trace rows, re-evaluates every
  coordinate from the eight passing cases, and retains the six empty expected
  fail-closed rows. The local Reference integration test covers 47 variants and
  572 trace coordinates, including 246 fixed-Born coordinates, under the
  predefined `1e-10 kcal/mol` energy and `1e-8 kcal/mol/angstrom` force max/RMS
  bounds. It hashes the complete installed OpenMM distribution, Python wrapper,
  `_openmm` binary, Python executable, and path-free environment identity, then
  requires exact runtime and adapter-source equality before and after each
  observation. These checks are snapshots and do not establish immutable
  external custody or same-UID replacement resistance.
  The installable `betelgeuze-engine-v2-openmm-materialize` command now runs
  both complete matrices into one bounded canonical mode-0600 artifact,
  refuses overwrite and symlink transport, retains all 27/59 and 14-case rows,
  binds Engine iteration/rejection counts, constraint/tangent-force metrics,
  energy/coordinate traces, and checkpoint equality, and supports exact
  re-execution against the live pinned runtime/source bytes.
  It accepts no private key and fixes production execution, signed result,
  independent review, two-host reproduction, scientific validation, and claim
  safety to false.
  A separate installable
  `betelgeuze-engine-v2-openmm-native-minimization` workflow now executes
  native OpenMM L-BFGS endpoints for eight supported cases, retains six
  expected fail-closed rows, and re-evaluates each endpoint with Engine v2 at
  identical coordinates. Its configuration SHA-256 is
  `6465f726c408e6df2dd15d318a4cdfc57a8b2edd271ddaa578edcc336110017e`.
  The local 2026-07-24 receipt retained all 14 rows and passed 8/8
  same-coordinate mappings plus 8/8 energy-nonincrease checks, but its
  endpoint-health denominator is 6/8 because both fixed-Born constrained rows
  exceed the frozen tangent-force bound after final constraint projection.
  Receipt SHA-256
  `7e5b3454afc41f9954f71dfc3b0b274906323f15fd8ea6630bfcc1e95ce95b7c`
  is therefore explicitly rejected; cross-algorithm endpoint/trace equivalence,
  production execution, S0 acceptance, and every scientific/product claim
  remain false.
  The installable
  `betelgeuze-engine-v2-openmm-fixed-born-disposition` workflow now binds those
  exact rejected inputs and executes two failure aliases across eight frozen
  probes each. Configuration SHA-256
  `ac601f3cfedd68e24b6507778ea36c1676fb24cacf89c7c2fa73848bf3c68045`
  preserves rejected observer-path predecessor
  `67f1a6025155d8f62cd3d1aa7da2803e229a4dce7871050db6c323f531f0b8c1`
  and changes no probe or endpoint-health threshold. Actual mode-0600 receipt
  `870f1ea247da4b0232f22804298e75d554af511da18924a7ba49c1c703f003f2`
  (file SHA-256
  `a63d920b33925c2f0a27ba2fe150ef719c55dc66195cadadc4dd342dd589d127`)
  reproduced both no-reporter source endpoints bitwise, retained all 16
  minimizer traces, and gave exact cross-alias physics equality. It classifies
  `final_constraint_projection_tradeoff_observed`: projection changes
  coordinates by at most `6.256008569372265e-06 Å`, converts a
  tangent-pass/constraint-fail endpoint into a constraint-pass/tangent-fail
  endpoint, and higher iteration/tighter tolerance probes do not resolve it.
  This completes only the bounded disposition row. The frozen native endpoint
  remains rejected at 6/8, OpenMM does not expose exact optimizer rejection
  count, causal root cause is not proven, and S0 remains blocked.
  OpenMM remains a lazy optional offline dependency; no product import or route
  loads it. The v4 Ed25519 external result-review verifier now freshly
  reverifies both Engine result-review chains, exact OpenMM materialization,
  both component/trace receipts, and the native endpoint receipt. It binds the
  exact 27/59 output match, all fourteen operational traces, native endpoint
  rows and a host-comparable native physics projection. For a rejected native
  endpoint it also freshly verifies and signs the exact fixed-Born disposition
  receipt/configuration/physics/classification; for an accepted endpoint that
  failure-specific input is forbidden. Disposition completeness does not
  change endpoint acceptance: the current receipt produces a signed rejection
  retaining both fixed-Born failed case IDs. Contract SHA-256 is
  `6e543d32b320b562fa0b3ad31c1ac26cc7b274fcbb4f79025f53ce1035ea5970`.
  The repository bundles no reviewer key or attestation; one verified host review
  remains non-production and cannot establish two-host reproducibility,
  external custody, S0 acceptance, or scientific promotion.
- a frozen v4 final S0 production-evidence bundle verifier. It freshly reverifies
  exactly two complete host-review evidence inputs and rejects either unless
  its review plus native endpoint health are accepted with 8/8 cases and no
  failed case IDs. Both accepted hosts must report the failure-specific
  disposition path as not applicable. It rejects reuse across host,
  CPU, session, custody, result/review/OpenMM/environment receipt, authorization
  nonce, and outer-review nonce identities, and requires exact equality of the
  commit, source manifests, dependency rows, OpenMM runtime/source, seed, and
  energy-force/minimization/native-endpoint physics projections. Contract
  SHA-256 is
  `549fbdb865704a84df4ecb525f4ea27a7c5ab8526f7f1be0b0f666cd9c6fd08d`.
  It then verifies a bounded,
  canonical, revocable/supersedable Ed25519 approval from a final human reviewer
  distinct from every nested author, scientific reviewer, operator, result
  reviewer, and external-oracle reviewer. An accepted runtime verification opens
  only the frozen synthetic S0 protocols and S1 admission; real-chemistry,
  fitting, benchmark, product, customer, and broad scientific claims remain
  false. The package exposes `betelgeuze-engine-v2-s0-review`: it validates a
  canonical secret-free signing request produced only after both hosts verify,
  writes the exact approval bytes for an external or hardware signer, and
  verifies the detached signature with a public key before attachment. The CLI
  has no private-key input and creates mode-0600 outputs with no overwrite.
  Detached attachment is not acceptance: the full verifier still freshly
  checks both raw host evidence chains and current revocation/supersession state.
  The repository provides no two-host production evidence, trust keys,
  authenticated external custody, or final approval, so its static S0 and S1
  decisions remain closed.

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
  on two CPU hosts, or a signed and independently reviewed production
  external-implementation receipt; the refrozen v2.1 comparison contract,
  non-production 14/14 implementation result, offline OpenMM Reference
  development observations, unprovisioned single-host external-review verifier,
  and unprovisioned two-host/final-approval bundle verifier do not satisfy the
  remaining S0 scientific or production exit conditions, and no production
  result has been dispositioned by an independent human reviewer;
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
