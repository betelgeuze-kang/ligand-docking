# Engine v2 `0.2.0rc2` Runtime Identity Release Candidate

## Purpose

`0.2.0rc2` separates the minimization-validation Ed25519 trust boundary and
runtime byte-identity work from `0.2.0rc1`. It is an internal CPU reference
distribution, not scientific validation evidence.

## Supported environment

```text
Distribution: betelgeuze-engine-v2
Version:      0.2.0rc2
Python:       >=3.10,<3.13
PyTorch:      2.6.0
Execution:    CPU reference
```

## Release gates

- Python 3.10, 3.11, and 3.12 tests;
- Ruff, Pyright, architecture, and legacy-import guards;
- two isolated builds with a byte-identical wheel SHA-256 at the same source
  epoch;
- PEP 561 metadata, clean isolated install, and `pip check`;
- installed `betelgeuze-engine-v2-s0-review` console-entrypoint smoke checks;
- installed `betelgeuze-engine-v2-openmm-materialize` secret-free workflow
  smoke checks (OpenMM remains an optional offline runtime);
- installed `betelgeuze-engine-v2-openmm-native-minimization` failure-inclusive
  endpoint-comparison CLI smoke checks;
- installed `betelgeuze-engine-v2-openmm-fixed-born-disposition`
  preregistered failure-disposition CLI smoke checks;
- installed `betelgeuze-engine-v2-openmm-constraint-stationarity` claim-closed
  same-coordinate candidate CLI smoke checks;
- installed `betelgeuze-engine-v2-minimization-stationarity-successor`
  claim-closed 14-case successor build/verify CLI smoke checks;
- installed `betelgeuze-engine-v2-openmm-nve-trajectory` claim-closed
  same-input NVE/SHAKE/RATTLE/direct-Ewald trajectory CLI smoke checks;
- installed
  `betelgeuze-engine-v2-openmm-explicit-solvent-trajectory` failure-inclusive
  TIP3P/ion trajectory, timestep, and reciprocal-bound CLI smoke checks;
- installed
  `betelgeuze-engine-v2-openmm-force-double-rattle-trajectory` claim-closed
  OpenMM-force/stdlib-double-RATTLE development CLI smoke checks;
- installed `betelgeuze-engine-v2-posebusters-intake` extraction-free local
  archive-intake smoke checks (the public archive remains caller-provided);
- installed `betelgeuze-engine-v2-posebusters-corpus-audit` failure-inclusive
  local chemistry/ingest audit smoke checks;
- installed `betelgeuze-engine-v2-posebusters-native-geometry` failure-inclusive
  native-crystal-pose geometry-preflight smoke checks;
- installed `betelgeuze-engine-v2-posebusters-external-prepare` strict
  failure-inclusive preparation-entrypoint smoke checks (Meeko remains an
  optional, caller-provisioned offline runtime);
- SPDX 2.3 SBOM binding the wheel SHA-256;
- exact pre-import and pre-evaluation byte manifests for Python, the standard
  library, OpenSSL, cryptography, NumPy, and Torch;
- authorization-builder round-trip verification before a signed receipt is
  returned;
- CODEOWNERS review routing and the external branch-protection policy in
  `docs/engine_v2_review_governance.md`.

## Trust boundary

The bootstrap measures installed payload bytes before importing Engine v2,
Torch, or NumPy. The signed authorization must contain exactly the six required
artifact identities, and run-start plus the bounded runner remeasure them.

Private POSIX receipt storage detects changed content only when a verifier is
given the exact receipt SHA-256 out of band. It does not establish resistance to
a malicious same-UID process replacing a pathname or inode; that requires
privileged immutable storage or an external signed transparency system.

## Promotion boundary

- `claim_safe=false`
- `scientifically_validated=false`
- `benchmark_validated=false`
- `customer_execution_enabled=false`

No production result receipt, independent result review, reviewed parameter
set, real-molecule corpus, external solver result, or public docking benchmark
is bundled. The same-input Vina/GNINA/Smina API emits only non-executing work
orders after prepared-PDBQT and identity checks; it bundles neither prepared
inputs nor external engines and does not establish comparison evidence. The
chemistry-aware pose-validity API binds exact force-field LJ parameters,
partial charges, ligand exclusions, proposal identity, cross/self overlap
diagnostics, screened-Coulomb sign decomposition, and signed strain in one
result. Its strain and repulsion limits are caller-declared rather than fitted
or independently reviewed. Aromatic/stereo coverage remains incomplete and
metals/receptor cofactors remain outside scope, so this API does not establish
validated pose quality or change any promotion flag. The accompanying
reference-docking applicability API exact-binds systems, topologies, problem,
config, and optional parameter fingerprints and retains every detected
identity, chemistry, parameter, and capacity blocker in one assessment. It
constructs a scorer only for `admitted_diagnostic`; aromatic/stereo admission
remains interaction-incomplete, and every disposition keeps scientific,
validated-refinement, and claim promotion false. The
PDBbind/CASF/PoseBusters split-provenance API similarly binds only caller-
provided identities, leakage evidence, and family denominators. It accepts no
PDBbind access terms and bundles no dataset, fit, benchmark result, or review.
The OpenMM Reference NVE trajectory command adds a frozen two-case, 16-step
single-host implementation comparison with all three fail-closed rows and
configuration SHA-256
`2beca32683c0393666cc1c3b5a136bed3416f774b0db631133a04bb43928871e`.
It does not establish accepted long-time drift/Ewald convergence, PME,
two-host/GPU parity, independent review, or scientific/P2 promotion.
The separate installed explicit-solvent trajectory successor freezes three
exact 12 Å TIP3P/ion inputs, a four-step Engine/OpenMM comparison, both restart
paths, salted timestep and reciprocal-bound ladders, and four fail-closed rows.
Configuration SHA-256 is
`e40902895938a4d7848e5207d0fe29de1ecaa43ae600c9c9ed8f7b7d0ac6c1b5`.
The local observation
`d510c9c65625c00f7bd14c134c72e1ed5dab004764efc60c7fd96a9dae223157`
is intentionally rejected: 0/3 physical rows pass the full metric set because
OpenMM Reference SETTLE exceeds the rigid-water position threshold, two rows
also expose exact cutoff-equality force divergence, and the Engine timestep
coordinate monotonic row fails at its numerical floor. Ewald convergence and
4/4 negative rows pass. Complete disposition does not promote this result to
accepted solvent, Ewald, NVE, scientific, product, or P2 evidence. Two builds
were byte-identical at wheel SHA-256
`3c08913e23dceb49614f97cad03fe872c1a7d072cb15c7437760c566da452b70`,
and installed-wheel verification reproduced the receipt.
The installable public-ranking-corpus intake now exact-binds canonical
PDBbind-v2020 fit, full CASF-2016 validation, and full PoseBusters-308 test
manifests plus three pairwise all-chain sequence receipts. Its frozen
configuration rejects exact case/PDB/target/receptor/ligand/scaffold/sequence
overlap, maximum sequence identity above 0.90, fit→test and validation→test
release-order violations, sequence-method drift, and scoring/preparation drift.
Configuration SHA-256 is
`4972e41765076e09b7bbec43b7e506dede6ab48b01b173f62cd73a749f694681`.
It securely verifies input file/payload hashes and emits only a canonical
mode-0600, no-overwrite readiness receipt. No production receipt exists because
licensed PDBbind/CASF manifests and executed sequence evidence have not been
provided; the intake cannot fit, select a model, read labels, or authorize a
claim.
Above a passing corpus receipt, the installable
`betelgeuze-engine-v2-public-ranking-calibration-partition-intake` command
securely loads exact PDBbind-fit and CASF-validation calibration partitions.
It recomputes public-manifest bindings and pose-level leakage, retains all
success/failure and positive/negative denominators, and reports fit cases that
cannot form a positive/negative training pair. Validation labels are never
admitted to fitting and no test partition can be supplied. Configuration
SHA-256 is
`c4b423063a36f38d7f6f098a38c7ea54b078c25f3cc04d060ae88638902ff8be`.
No production receipt, fit, selection, metric, review, or claim exists because
the genuine upstream corpus inputs remain absent.
Above that passing intake, the installable
`betelgeuze-engine-v2-public-ranking-calibration-training-view` command uses
only fit-row `status`: it includes every success unchanged and retains every
failure as a hash-bound exclusion disposition. Its receipt embeds the exact
success-only training partition and recomputes training-view/CASF leakage. A
guarded deterministic-fit bridge is available, but validation labels and test
partitions are never inputs. Configuration SHA-256 is
`e5e202d10420b5a557b1227aa0f7735433ebaeadc1656f6b981c14453aeb25b8`.
No production receipt, fit, selected model, metric, review, or claim exists
without genuine upstream corpus inputs.
The installable
`betelgeuze-engine-v2-public-ranking-fit-validation` command adds the next
claim-closed boundary. A canonical manifest workflow-locally preregisters every
deterministic fit candidate and CASF bootstrap configuration. Candidates fit
only the embedded PDBbind rows; CASF contributes only failure-inclusive all-case/
all-pose, target-family, bootstrap-interval validation and selection by
PR-AUC, Top-1, Top-5, then candidate ID. Every candidate and primary metric
must complete or no model is selected. Selection-policy SHA-256 is
`1905b14e37da44293483b9b31a06b2653849b2e986dc75b9e4ad53aa0bc4b9d9`.
The mode-0600 receipt and verifier exact-bind/reexecute ancestry, source,
Python/Torch runtime, configs, models, and reports; a PoseBusters test score
partition is forbidden. Genuine licensed inputs remain absent, so no
production receipt, test result, confidence calibration, independent review,
scientific validation, or docking claim exists. Two builds were byte-identical
at wheel SHA-256
`d338d81d14d08ca7c07f74629ac2b98f94d389f651e44e2b143fb487bfcf4bd3`;
the installed CLI/import boundary passed outside-checkout verification.
The receipt has no independent timestamp/signature custody for the manifest.
The PoseBusters intake command can establish the exact archive, selection, and
308-case artifact identities without extraction, but it performs no preparation,
pose generation, scoring, benchmark execution, or independent review and does
not bundle the public archive or a receipt.
The separate corpus-audit command can add all-308 parser, heavy-graph,
element/charge, metal/cofactor, and raw representation metrics, but performs no
aromaticity/stereo oracle, parameterization, docking, or benchmark and therefore
does not change that promotion boundary.
The separate native-geometry command can add all-308 fixed-radius overlap,
topology-excluded self-overlap, native/start heavy-bond-delta, and exact target-
CCD residue-retention observations. It evaluates a native-crystal-pose positive
control with unvalidated heuristics, not generated poses, force-field strain,
PoseBusters equivalence, docking, scoring/ranking, or benchmark performance, and
therefore also does not change that promotion boundary.
The separate external-preparation command can add exact pinned-runtime and
prepared-PDBQT identities for the bounded chemistry subset. Its local receipt
retains 18 prepared pairs, 16 strict failures, and 274 abstentions, but it does
not repair receptors, validate AD4/Gasteiger assignments, execute an external
engine, evaluate a generated pose, or establish docking performance. It also
does not change the promotion boundary.
The separate prepared-ligand diagnostic command consumes that exact receipt,
retains all 308 dispositions, parses the embedded Meeko atom mappings, and
directly recomputes the same RDKit Gasteiger algorithm. Frozen RDKit 2022.09.5
and 2025.09.6 observations both evaluated 18 cases, 481 real atoms, and two
zero-charge `G0` pseudoatoms without a diagnostic failure. All real charges
were within the 0.0005 e PDBQT serialization tolerance; the maximum delta was
0.0004979832249129013 e. The two expected-charge vectors were bitwise identical
for 481/481 atoms. Observation payload SHA-256 values are
`df57b0d48ba905e0f132b66a3b4d4fc344fffc4a40f1d78de181c0264bedba8f` and
`6d3389ed55e7d47c8e0b0076c485b3f4ee7590cb3f9ddcd12db89030e92b6b50`;
the cross-version comparison is
`ab9cf4b72d3af848dd48484fcbb203268fe8d7336ec552ffe52c360dca972b5f`.
Two wheels were byte-identical at SHA-256
`9d1c96336c1fa55051ab3e0fc2192d990860c644dc5f39a0685f07c39613124e`,
and isolated installed-wheel verification reproduced all receipts. Because
both runs use the same algorithm, this is not independent charge or AD4 typing
validation and does not change the promotion boundary.
The separate Open Babel comparison command uses the independently distributed
Open Babel 3.2.1 `OBChargeModel("gasteiger")` implementation and its PDBQT
writer against the same exact 308-row preparation identity. All 18 prepared
cases completed without comparison failure; 481 real atoms were compared and
the two retained `G0` pseudoatoms were excluded from real-atom statistics.
Charge MAE/RMSE/max absolute delta versus the three-decimal Meeko fields was
0.0038510594375734796 / 0.012204476318346003 / 0.18097866788513423 e. Exact
AD4-type agreement was 476/481 atoms; the five preserved mismatches were three
`SA`/`S` and two macrocycle `CG0`/`C` assignments. Source-tree and isolated
installed-wheel exact verification reproduced receipt payload SHA-256
`7754c4b56e10d4543b064c23daaf69ab99e098fda81bfd9fbaecc8694439d943`;
two package builds matched at wheel SHA-256
`d0fc6a2acce76f2e3d23915b533528263d10e8277c0cf6feafd09e318c6d9529`.
This closes independent-implementation execution, but no accuracy threshold
was preregistered and Open Babel is not a quantum charge oracle. Exact-tag
source inspection explains the two `CG0`/`C` rows as Meeko's macrocycle
extension and the three `SA`/`S` rows as a real neutral-thioether
acceptor-semantics disagreement. A two-version RDKit iteration control also
locates the methylsulfone charge outlier in differing sulfur parameter-selection
semantics rather than iteration count alone. The thioether and sulfone choices
remain scientifically unadjudicated; source-SDF equivalence, receptor
assignments, unsupported chemistry, second-host reproduction, and independent
review remain open, so this does not change the promotion boundary.
The separate sulfur QM-ESP command then preregisters and executes a bounded
independent field reference without treating either atom-charge partition as
an oracle. Its protocol binds the exact source SDF coordinates and explicit
hydrogens for `7CIJ_G0C`, `7F5D_EUO`, `7LT0_ONJ`, and `7NLV_UJE`;
RHF/6-31G* with spherical functions, fixed geometry, and one native thread;
the official PySCF 2.14.0 wheel and installed dependency payloads; four
equal-weight Lebedev-110 molecular-surface shells; the same-site Meeko and Open
Babel projections; all metrics, hashes, failure rows, and claim gates; and the
full 308-case denominator before QM execution. Protocol payload SHA-256 is
`0927260a16f1e09211fb601fade1725e21d35d221d04e69cfd2c624da7c06137`.
The 2026-07-23 production observation evaluated all four scoped cases with zero
QM failures and retained 304 scope abstentions. Meeko had lower global weighted
ESP RMSE in 4/4 cases and Open Babel in 0/4, but the differences were small and
descriptive only. Source-tree and isolated installed-wheel exact reexecution
reproduced observation payload SHA-256
`402d1795f18b7eb0c87d8537f3b427fe116c0845bf1337b21e24752cef7e52e6`;
two pinned-tool builds were byte-identical at wheel SHA-256
`b4564648dbf3fcb681e0b73d1dcbcc2fd96ed10a0fe4a321149fe38545d0d73d`.
No charge-accuracy threshold was preregistered, HF/6-31G* is a defined
reference rather than an absolute oracle, and a molecular ESP comparison does
not decide neutral-thioether `SA`/`S` hydrogen-bond semantics. The bounded
interaction-energy result below still leaves directionality, second-host
reproduction, and independent reviewer acceptance open, so this also leaves
the promotion boundary unchanged.
The separate default-Vina sulfur-type invariance command resolves the product-
path consequence before pursuing that chemical question. It binds exact
AutoDock Vina 1.2.7 source at commit
`8eb40404f4f45608acb3b01427587ac049f27c1f`, the exact preparation/Open
Babel/Vina receipt chain, the Vina runtime and default-scoring configuration,
all 308 rows, and a target-only `SA` to `S` PDBQT mutation. The frozen source
maps both AD types to element sulfur and then `XS_TYPE_S_P`; default Vina uses
XS typing, and its XS acceptor set excludes sulfur. The production observation
rescored every retained pose for the three neutral-thioether cases. All eight
public score components matched exactly for 60/60 pose pairs, with zero score
failures and 305 explicit scope abstentions. Protocol and observation payload
SHA-256 values are
`81f52bbf68518e1d09e0462f8124ac1a810c7cc502ff8923175703e62b28b57f`
and `a08ced8bbe0dbecc503f8e5eedf96d239130d0dbced897427694afe61742d406`.
Source-tree and isolated installed-wheel exact reexecution matched; two builds
were byte-identical at wheel SHA-256
`fcbdc2df96c3b7df53f90e50e90688898147bf4665f2a816eb7d82382f547535`.
This permits only the bounded default-Vina fixed-pose invariance claim. It does
not rerun search, evaluate complete AD4 scoring, or adjudicate chemical
hydrogen-bond acceptance, so the broad scientific and promotion boundary
remains unchanged.
The separate neutral-thioether interaction-energy command then executes the
preregistered AD4/chemical-semantics slice. It binds both prior receipts, exact
Vina 1.2.7 AD4 source, official PySCF 2.14.0 and PySCF-dispersion 1.5.0 wheels,
three fixed thioether models, a methanol O-H donor, six S-H distances and one
plane-normal control, all complex and ghost geometries,
B3LYP-D3(BJ)/def2-SVP density-fitted counterpoise settings, exact AD4
`S-HD`/`SA-HD` pair formulas and weights, all failure rows, and the decision
thresholds before QM execution. The 2026-07-23 production observation completed
all 21 geometries and 63 SCFs with zero failures and retained 305 scope
abstentions. Each QM profile had its minimum at 2.5 A, from -4.758 to -5.258
kcal/mol, and both preregistered local gates passed 3/3. The plane-normal
controls were 0.551 to 0.784 kcal/mol more favorable than the selected
idealized lone-pair direction, however, so the result does not establish a
general directionality rule or adjudicate chemical acceptor semantics.
Protocol and observation payload SHA-256 values are
`f0b0d84551e63272509acaf967996496cc7100cd2a58b71392fe38bce7d8194c`
and `30d9ceb83aed88fa45b7bc8c8282e6a50ce0299c9f54b21ce0c8885775c35fce`.
Exact source-tree and fresh installed-wheel observation reexecution reproduced
the latter. Two pinned-tool wheel builds were byte-identical at SHA-256
`bb47ad0c5dcb0a5b9d298d2ba7f423910c11bf03c13f1691c0ecbec9c6db6f56`.
One donor, three fixed gas-phase models, and isolated AD4 pair terms are not a
complete score or representative benchmark. Second-host reproduction and
independent reviewer approval remain open, so the scientific and promotion
boundary is unchanged.
The companion installed
`betelgeuze-engine-v2-posebusters-sulfur-reproduce` command now provides the
portable external-evidence workflow: preregister a distinct second host,
operators, nonce, exact wheel/source/runtime projection; execute or retain one
failure-inclusive attempt; freshly verify all 308 rows, 21 points, and 63 SCFs;
then create and verify a detached Ed25519 independent-review receipt. The CLI
never accepts a private signing key. Two deterministic builds matched at wheel
SHA-256
`5a6d82b8437b5d461e794f51a13bf127a51e429b3b4c5475b80fa8e417045acd`,
and an outside-checkout installed-wheel CLI smoke passed. No external work
order, result, or review
receipt has yet been issued, so this is engineering readiness only and neither
the second-host nor reviewer gate is closed.
The separate Vina-execution command can consume that exact receipt, require the
payload-bound Vina 1.2.7 runtime, and retain generated PDBQT plus all five Vina
energy components for every successful case while preserving every blocked row.
The 2026-07-23 local ignored-state production receipt succeeded on 18/308,
recorded zero engine failures, retained 16 preparation blocks and 274 chemistry
abstentions, and stored 355 poses. Its receipt payload SHA-256 is
`37b3df7c4c14d739d9fca3970dc73293a48909372314a8dfe1da5bcd956694ae`.
Source-tree and installed-wheel exact verification both reproduced that
receipt, and two pinned-tool wheel builds were byte-identical at SHA-256
`68380b90af9ac286a70e264cb2603288ae5a2d639f32f27b1ae376bdaebc6228`.
The separate generated-pose evaluation command consumes that exact chain and
the pinned PoseBusters 0.6.5 wheel. It retained all 308 dispositions and all 133
typed `redock` values for each generated pose. The local receipt evaluated
355/355 poses; 325 passed all selected non-RMSD tests. Conditional on the 18
Vina-success cases, direct symmetry-aware receptor-frame RMSD <= 2 A was 10/18
at Top-1 and 16/18 at Top-5. Installed-wheel exact reexecution reproduced
receipt payload SHA-256
`9c680e1edd08bfa07c1c71164b696ae050f180c3a2bb04bc91fd5d163a965b86`,
and two pinned-tool wheel builds were byte-identical at SHA-256
`b0248a218aaea0ef3f00e65d6f77e077cdd81a4c7ac37a128edd7833e3ce49a8`.

This closes generated-pose validity and RMSD only for the strictly prepared
18-case Vina subset. Family/leakage evidence, independent scientific
charge/type validation, independent external rerun, and benchmark review
remain absent. It therefore does not change the promotion boundary.

The external-binary execution command also freezes CPU-only GNINA 1.3.3 and
Smina 2019-10-15 same-input lanes. Both production receipts retained all 308
rows, attempted 18 prepared pairs, succeeded on 17, and preserved one explicit
`7UAW_MF6` failure because the prepared AutoDock type `CG0` is unsupported.
GNINA retained 340 poses at execution receipt SHA-256
`60d0e6a67c86075905cd54497ab12a678f0f54a15a11d7e9345122369d390847`;
Smina retained 336 at
`912b7081ba35d11e0accdf1af9c5ebb55c09641390f17242fb8b210d67d27733`.

The paired external generated-pose evaluator retained every engine score and
all 133 typed PoseBusters values. GNINA evaluated 340/340 poses, with 304
physical-validity passes and conditional Top-1/Top-5 RMSD <= 2 A of 15/17 and
16/17. Smina evaluated 336/336, with 312 passes and 10/17 and 15/17. Exact
source-tree and installed-wheel runs reproduced receipt payload SHA-256
`0959201d6165d82041447be820977de7ac8ba64b13d1f237ad5b8c914a290259`
and `0590067f9c1731f6ebcbff36f54ba08d9265f32454b54fa03b7df0dbc328b930`.
Two correctly staged wheels were byte-identical at SHA-256
`02356f803a448fdb3f77f5594ef4927eacc1221d319069fa4b81ace25dc4a8f0`.
The denominator is still 308 and the reported redocking rates are conditional
on only 17 execution-success cases per engine. Complete target-family coverage,
external-fit leakage control, independent-host, independent scientific
charge/type validation, calibration, and reviewer gates remain open;
`claim_safe=false`.

The separate target-cluster command now binds all three exact evaluation
receipts to a conservative receptor near-identity proxy. First-model `ATOM`
residue-label sequences, minimum 20-residue chains, a 90% global edit-similarity
threshold, and connected components produced 296 clusters from 308 cases, with
11 multi-case clusters, maximum size 3, and 13 links. Vina covered 18/296
clusters and completely covered 17; GNINA and Smina each covered 17/296 and
completely covered 16. Covered-cluster any-member Top-1/Top-5 RMSD hits were
10/18 and 16/18 for Vina, 15/17 and 16/17 for GNINA, and 10/17 and 15/17 for
Smina. Exact reexecution matched receipt payload SHA-256
`34d782567e816206dcaf2be5207e424b8611a081c9ca6d51bc9500e42ec81e5e`
and file SHA-256
`fc69398c600c032f7f5c18ca1fc8baedd51c93db0f933c2320d1f597265750aa`.
Two pinned-tool builds were byte-identical at wheel SHA-256
`050d06e9fc49ef3c79bcaefbd8854de85fce0ce7fe4a56cc83418a460280a597`,
and the isolated installed-wheel command reproduced the receipt.
The proxy is not a biological target-family annotation. All three external
fit/training manifests are absent, target and ligand/scaffold training leakage
remain unevaluated, and `leakage_control_passed=false`; the promotion boundary
does not change.

The RCSB target-family command now adds a source-provenance layer without
runtime networking. A normalized official RCSB Data API observation is pinned
with query, retrieval-tool, batch, and canonical content identities while raw
responses are not persisted. Native-ligand pocket chains use an inclusive 6 A
heavy-atom cutoff and exact `asym_id` before exact `auth_asym_id` fallback. The
308-case receipt records 306 complete mappings, 299 UniProt cases, 225 Pfam
cases, one unmapped chain (`6Z14_Q4Z`), and one removed entry (`7D6O_MTE`)
without replacement remapping. It retains 199 overlapping Pfam-family rows and
149 non-overlapping exact Pfam-set partitions for each engine. Snapshot
payload/file SHA-256 values are
`4d05e0127bb4c4dfedb5fa0a5f2e11d7de22aae481d34d3840676d04d367b51a`
and `2287ffc895b28828ff39568f3ee0b98707b8160f04fa10196b469fe9ba722358`;
target-family receipt payload/file SHA-256 values are
`ce7d0f32054f05a328554fa04e38964768d2e734157aa9eca4ceb431c2a87076`
and `164ef81d7e49dbf32aab6eef56325dfd2ee57e889304e7f3ac0dff7f11a36761`.
Two pinned-tool builds were byte-identical at wheel SHA-256
`02d837ed5f624505a5a02bf1a5489f8aec1dcf0bacd15ef39b0fa6abf8526deb`,
and isolated installed-wheel verification reproduced both receipts.
The HTTPS observation is not independently signed by RCSB, Pfam coverage is
incomplete, and no external fit/training manifest is present. Leakage control,
scientific validation, benchmark authorization, and product claims remain
closed.

The new pose-ranking intake command connects the exact production receipts to
the generic calibration boundary without training on PoseBusters. It
caller-pins all three evaluation receipt roots and the RCSB/Pfam root, verifies
the linked archive/preparation/execution receipt and file identities, and
retains 924 engine/case rows, 1,031 successful pose rows, and 872 explicit
failure rows. Engine-namespaced component values, RMSD labels, physical
validity, all-case Top-1/Top-5 counts, and Wilson intervals are retained.
Receipt payload/file SHA-256 values are
`b6526c7407602721f2ec74f09c8b99d4ecdc7336e69417ed6321840663de9ea0`
and `88b756cd3e7d460edefe8330dbae6141e72492953a1af4e71bb60b1146574813`;
two deterministic wheels matched at
`c8019fa070e8ca2fc598e26cbdf3c78394fcf9e0963ec656d736b3864681ac51`,
and installed-wheel materialization was byte-identical.
PoseBusters is fixed to `split_role=test`. The immutable base intake leaves
per-pose coordinate and accepted scaffold hashes null; complete Pfam coverage,
a fit manifest, and leakage audits remain blockers, so it emits no
`PoseRankingCalibrationPartition`.

The pose/scaffold identity command supplies the two missing identity layers as
an exact overlay while leaving the base intake immutable. Under the preparation-
matched RDKit 2025.09.6 runtime, 1,031/1,031 generated poses receive
topology-aware coordinate hashes and all 872 failure rows remain explicit.
Start/reference scaffold identity matches for 308/308 cases, producing 229
groups: 275 cases use a Bemis-Murcko graph and 33 use the explicitly named
acyclic full-heavy-graph fallback. Generated/start chemistry and cross-engine
topology mismatches are zero. Start/reference full chemistry agrees for
305/308; three differences remain pending independent disposition. Receipt
payload/file SHA-256 values are
`e7b92d0fc74b44f652c5196429812fe61165771906d9d487a13ec8719ac52995`
and `fbf3fa34f974dc8bd35b6564a1c004931a9ea0177f25fd551769b91f4db089d8`.
Two deterministic wheels matched at
`d3c51e79dc4783f859b7b2ff4a8f8499d42da0d6a4378035c3cf2114b751285e`,
and installed-wheel verification reconstructed the exact receipt. The remaining
partition identity blocker is complete target-family assignment; fit/training
provenance, leakage audits, independent rerun, and review are also absent, so
the identity command itself emits no `PoseRankingCalibrationPartition` or
product claim.

The ranking-test-partition command then binds that immutable intake and identity
overlay to the observed-sequence and RCSB/Pfam receipts. It emits three
failure-inclusive `PoseRankingCalibrationPartition(split_role="test")` objects:
Vina 645 rows (355 successful, 290 failed), GNINA 631 (340, 291), and Smina
627 (336, 291), each retaining all 308 cases. Successful pose identities are
coordinate hashes; failed rows carry domain-separated failure-observation
hashes explicitly marked as non-coordinate identities. The command revalidates
the 21 ranking, 36 sequence-proxy, and 5,226 RCSB/Pfam metric rows and their
Wilson intervals. The 296 observed-sequence strata are leakage-control proxies,
not biological families, while Pfam coverage remains 225/308. Receipt
payload/file SHA-256 values are
`509a7f7c8fcae221be53d5d7e525e05c37a1314f6d17060c8ed6b68e8e4fc89e`
and `581235213b161caeb41db441ca73428d669a7fa0c9a3ead3bba7632dfa63b1dc`;
two deterministic wheels and installed-wheel verification matched at
`5378c25f700a3f775aca232e379ea9e56b93a75310daead5d7dfdae082d9800e`.
There is still no fit partition, fitting call, leakage audit, calibrated model,
independent rerun/review, scientific validation, or product claim.

The external-ranking evaluation command consumes only that caller-pinned test
receipt. It fixes Vina total energy, GNINA CNN pose score, and Smina minimized
affinity from the source execution policies and refuses a partition whose
scores do not reproduce source pose order. It retains all 308 cases and all 872
failure observations. Vina/GNINA/Smina scored-case coverage is 18/308, 17/308,
and 17/308; all-case Top-1/Top-5 counts are 10/16, 15/16, and 10/15.
Tie-invariant average precision over successful labeled poses is 0.287330,
0.668157, and 0.304352, with 95% case-cluster bootstrap intervals
0.174209–0.512214, 0.534293–0.886705, and 0.183486–0.541608. The receipt binds
coverage, source physical-validity summaries, and all sequence-proxy/Pfam
views so the conditional pose metric cannot stand alone. Production
payload/file SHA-256 values are
`509556b0bcd9ec35f9ff4b1860613f267b2a96d73b18de44b61288498a838137`
and `3f4965ba07be36c6233514d2545c1db0f604bc4245552be2180bcdb780a43dc1`.
The byte-identical installed wheel identified above reconstructed both the
test-partition and evaluation receipts exactly outside the checkout.
External-model training overlap, independent rerun/review, calibrated internal-
scorer performance, complete public-benchmark evidence, and product
qualification remain unproven.

The internal-diagnostic ranking command applies a separate, frozen uncalibrated
policy to the same pose coordinates before loading test labels. The minimize
score sums unit-weight UFF receptor–ligand van der Waals, PDBQT-charge Coulomb,
exact source-atom RDKit UFF strain delta, and UFF overlap terms. Under the
preparation-matched RDKit 2025.09.6 and NumPy 1.26.4 runtime it scored every one
of the 1,031 source-success poses with zero scorer failures and retained all 872
upstream failures. Vina/GNINA/Smina coverage remains 18/17/17 of 308 cases;
all-case Top-1/Top-5 counts are 2/5, 3/5, and 3/3. Successful-pose average
precision is 0.113931 (95% case-cluster bootstrap CI 0.056090–0.270781),
0.169927 (0.100789–0.262457), and 0.106265 (0.064622–0.224549). Production
receipt payload/file SHA-256 values are
`63a2f62cd465438f83e177b11ffd50483a2ff3f94c9399c308da2e8baee45b57`
and `4e4acd968e2a32f4f6ff47b8412b9209b5afe6918bda2019fdc4e9e492a4f3b1`.
The deterministic installed wheel identified above reconstructed this receipt
exactly from outside the checkout.
This result proves an executable term-decomposed diagnostic path, not reference-
force-field validity or calibrated ranking. PoseBusters labels remain test-only;
disjoint fit/validation data and target/ligand/scaffold leakage evidence are
required before any fitting.

The external-ranking reproduction command adds a preregistered second-host
work-order and result contract around that baseline. Before observation, the
work order binds the exact baseline intake/partition/evaluation chain, wheel
and four implementation-source members, distinct host/operator identities, and
a single-use nonce. A result must retain the three fixed public-input roots but
replace the ranking intake, test partition, evaluation, and all six
Vina/GNINA/Smina execution/evaluation receipt and file roots. It rederives and
compares all 924 engine/case rows, including failures, fixed-policy scores,
Top-K outcomes, aggregate and family metrics, intervals, and source-validity
counts. No production work order or result is included because genuine
external host/operator identities and custody evidence have not been supplied.
Same-host exact reconstruction is not independent execution, and the unreviewed
result schema keeps `independent_external_rerun_present=false`,
`physical_host_independence_reviewed=false`,
`independent_reviewer_receipt_approved=false`, and `claim_safe=false`.

The v4 host-review contract requires the exact OpenMM materialization and
native-minimization receipt in addition to both Engine result-review chains.
For a rejected endpoint it also requires and freshly verifies the exact
fixed-Born disposition receipt, signing its receipt/configuration/physics
identity, completeness, and classification without promoting endpoint health.
The observed 6/8 receipt therefore remains a signed rejected host review with
both failed fixed-Born case IDs retained. An accepted endpoint forbids this
failure-specific input. The v4 S0 builder rejects the current review before
signing, requires the disposition path to be not applicable on accepted hosts,
and requires exact native-physics equality for any future accepted two-host
pair. Host-review and S0 contract SHA-256 values are
`6e543d32b320b562fa0b3ad31c1ac26cc7b274fcbb4f79025f53ce1035ea5970`
and `549fbdb865704a84df4ecb525f4ea27a7c5ab8526f7f1be0b0f666cd9c6fd08d`.

The S0 review command is workflow tooling, not bundled evidence. It accepts no
private key: after two raw host chains have been verified through the Python
API, it emits exact canonical approval bytes for an external/HSM signer and
verifies the returned detached signature with a public key before attachment.
Full raw-evidence verification, current revocation state, authenticated custody,
and independent human judgment remain mandatory.
