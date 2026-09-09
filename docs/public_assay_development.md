# Public assay development intake and first learning experiment

This path is an offline development importer and a target-specific cheap-selector
candidate. It does not enable customer execution, docking ranking, physical
energy correction, calibrated uncertainty, or a new molecular engine.

For new BindingDB learning, use the staged native adapter described below.
The historical generic trainer filters eligible endpoint rows before assigning
roles. Its original checkpoints and observations are retained, but it does not
provide the outcome-independent role assignment of the new staged path.

## Native BindingDB preassignment and observed Factor X pilot, 2026-09-09

`tools.product.public_bindingdb_staged_intake` and
`tools.product.train_public_bindingdb_staged_selector` reuse the existing
chemistry, measurement, metadata-component, Morgan-feature and metric primitives.
The six existing BindingDB/ChEMBL helpers remain byte-identical. This is an
offline data and learning adapter, not a third molecular engine.

The new manifest binds the native BindingDB archive, original assay mapping and
descriptions, original metadata context, preassigned role plan, endpoint-specific
method ledger and chemistry scope. It rejects missing or duplicate source IDs,
reserved or unknown source policies, cached value/role/provenance changes and
method-ledger endpoint mismatches. All source-archive graph vertices are checked
against original line and record IDs before authorized observation rows are
decoded. Unselected and opposite-phase observation rows are not decoded.
Original source policy fields stay intact; derived nested rows retain the fixed
role and evaluation-only markers instead of the historical helper's defaults.

The actual module sequence is:

```sh
python -m tools.product.public_bindingdb_staged_intake \
  --manifest MANIFEST --manifest-sha256 MANIFEST_SHA \
  --phase fit --output-dir FIT_INTAKE
python -m tools.product.train_public_bindingdb_staged_selector \
  --input-dir FIT_INTAKE --summary-sha256 FIT_SUMMARY_SHA \
  --phase fit --output-dir FIT_MODEL
python -m tools.product.public_bindingdb_staged_intake \
  --manifest MANIFEST --manifest-sha256 MANIFEST_SHA \
  --phase evaluation --frozen-fit FIT_MODEL/frozen-fit.json \
  --frozen-fit-sha256 FROZEN_SHA --output-dir EVALUATION_INTAKE
python -m tools.product.train_public_bindingdb_staged_selector \
  --input-dir EVALUATION_INTAKE --summary-sha256 EVALUATION_SUMMARY_SHA \
  --phase evaluation --output-dir EVALUATION_RESULT
```

Each output directory must be new. The fit command writes the protocol before
fitting and freezes the checkpoint and predictions for every selected metadata
row before evaluation-label intake. Evaluation rederives all saved predictions
from the checkpoint and metadata before decoding evaluation observations. The
new checkpoint schema is `public_bindingdb_preassigned_ridge_v1`, with quantity
`negative_log10_molar_Ki` or `negative_log10_molar_IC50`. No old checkpoint is
migrated or implicitly accepted by a product loader.

A metadata-only census of the 93,712-row source archive selected P00742, human
coagulation factor X, by independent component count before endpoint presence or
values were inspected. Of 1,213 requested target rows, 298 remained blocked by
the supplied identity context and one was outside the chemistry scope. The
remaining 914 rows were assigned once to fit/calibration/development test:
640/137/137 rows in 9/4/5 metadata components. The supplied graph contains
127,158 metadata vertices; it is an explicitly bound audit universe, not a claim
of complete similarity or public-database coverage.

Method review retained the original assignments. Thirty-nine development rows
had a thrombin method inconsistent with the Factor X annotation. Other missing,
unknown, ambiguous or endpoint-incompatible methods remain visible. The native
Ki fit phase read only its 640 assigned rows: 517 exact, four censored and 119
missing observations. After method and source admission, 515 rows in three
components entered the predeclared Ridge fit (alpha 10). The model and all 914
metadata predictions were frozen before accessing the 274 evaluation rows.

The target is a catalogue annotation, not a verified active Factor Xa construct.
The canonical precursor sequence, activation cleavage, post-translational
modifications and assay-specific cofactors cannot be equated to a prepared
physical receptor. The label is a database-curated reported experimental Ki;
primary numerical tables were not independently remeasured or fully verified.
It is not Kd, an IC50 conversion, potential energy or an energy residual.

| Frozen observed endpoint evaluation | Calibration | Development test |
|---|---:|---:|
| Original assigned rows | 137 | 137 |
| Compatible exact Ki rows / components | 106 / 2 | 90 / 4 |
| Compatible exact label coverage | 77.37% | 65.69% |
| Missing / censored observations | 27 / 4 | 39 / 8 |
| Mean baseline MAE, pKi | 1.03115 | 1.25085 |
| Morgan Ridge MAE, pKi | 1.64274 | 1.09580 |
| Supported-row top-20% budget | 22 | 18 |
| Mean baseline expected positive hits at that budget | 19.72 | 16.00 |
| Morgan Ridge positive hits at that budget | 17 | 18 |

The model improved the development subset and worsened calibration. At the
same fixed budget of 28 candidates from each full 137-row role, the model
selected 11 known positives plus 17 unresolved/out-of-scope labels in calibration,
and 21 known positives plus seven unresolved/out-of-scope labels in development.
The constant baseline's tie-expected known-positive counts were 19.42 and 16.35.
These are conditional observations on known labels, not full-request recall;
unknown, censored and unsupported labels are not assumed negative. Full-request
recall remains null. Unique-chemical-state metrics are recorded separately.
No hyperparameter search, endpoint fallback, post-outcome resplit, refit or
uncertainty calibration followed this evaluation. This evidence does not support
ranking promotion or a general improvement claim.

The four actual CPU module invocations returned exit 0 and took 115.7767 s total
wall including startup, 112.2270 s summed phase CPU, and 1,847,212 KiB maximum
process peak RSS. The fit phase itself took 29.5312 s including full source
revalidation; feature generation was 0.0830 s, Ridge fit 0.0110 s and frozen
914-row inference 0.1505 s. These are single correctness executions on a shared
host, not p50/p95 or cold/warm benchmarks. No GPU/VRAM, docking recall,
matched-quality engine speedup or end-to-end candidate-recovery cost was measured.

The final checkpoint SHA-256 is
`de9b3e21c93b0f15c02df221d2f8ee9caa3d5e0590442c34efed3394b969ac85`;
the frozen-fit artifact SHA-256 is
`50788721bb36996541ef6daadc2cf58f39dfc322dd0edad32eb3ca2a3b096842`.
The manifest SHA-256 is
`1e7d39305219e0454069ca4668376a7936ac3c3f48a5e653cca845d84d7dc618`.
Data, checkpoint and raw execution artifacts remain local development files.

New synthetic controls reproduce the previous generic defect: changing one
row from exact to missing, censored or nonfinite moved eight unchanged peer
roles. Those three intentional old-code failures remain in the evidence. The
new metadata-first path retains the original roles across those controls. The
final CI-scope local suite passed 309 cases with no failure, error or skip; Ruff
passed. Earlier import-command and unused-variable failures are also retained.
The local environment was Python 3.10.12, NumPy 1.26.4, SciPy 1.12.0,
scikit-learn 1.7.2, RDKit 2026.3.6, pytest 9.0.2 and Ruff 0.12.4 with one
BLAS/OpenMP thread. Hosted CI uses its own pinned environment and must be
reported separately on the current head.

Public-data development, actual model fitting, performance observations,
scientific validation and customer execution are separate decisions. Only the
first three have the limited observations above. The sources include BindingDB's
own literature curation under its source-specific attribution terms; open paper
access is not an independent grant for all supplementary data or commercial
uses. No external human reviewer, experimental confirmation or approval receipt
is asserted. A separately versioned product shadow adapter must be executed
before this checkpoint can be counted as an integrated product observation.

## Source and chemistry contract

`python -m tools.product.build_public_assay_development_dataset` consumes an
already downloaded BindingDB TSV/ZIP, reaction-to-assay mapping, assay description
file and an identity exclusion catalog. Each input requires its expected SHA-256.
It writes a new directory with `records.jsonl`, `ledger.jsonl`,
`identity-context.jsonl`, and `summary.json`.
Existing output directories are rejected. It performs no network request.

The source row, original role/split/evaluation declarations, source line/member,
archive hash, release, original SMILES/InChI, chemistry, protein chain sequences,
assay identifiers/text, publication/curation dates, pH and temperature survive.
RDKit canonicalization retains stereochemistry and formal state; it does not
remove salts, generate coordinates, choose a tautomer, infer stereo or protonation,
or assign receptor parameters. The declared pilot ligand scope is one fragment,
5–70 heavy atoms, H/C/N/O/F/P/S/Cl/Br/I, formal charge within ±2, no radicals or
isotopic atoms. This is a data/feature scope, not Engine V2 parameterability.

Ki, Kd, IC50 and EC50 remain different concentration observations. Exact,
censored, approximate, absent and invalid observations are distinct. A reported
zero concentration is retained as invalid for a logarithmic concentration
endpoint; measured zero pH/temperature and a valid zero log value are retained.
No assay concentration is converted to potential energy or a force label.
Coordinates, pose, atom order, forces and potential energy are explicitly absent.

Duplicate reaction IDs anywhere in the source exclude every matching requested
occurrence. No last/max-affinity row is selected. Ambiguous/missing assay joins
remain visible; all joined original evaluation-only declarations are honored.
Protected matches emit identifiers and rejection reasons only. Cross-database
exclusions use source IDs, pinned RDKit isomeric/stereo-independent hashes and
InChIKey identities. Catalog coverage is declared explicitly: it is not a proof
of complete repository-wide or similarity-based holdout separation.

License handling follows each row's curation source. In the observed
`BindingDB_BindingDB_Articles_202609` archive, 93,023 rows identify BindingDB
literature curation, 429 ChEMBL, and 260 another research group. The filename
does not establish one license for all 93,712 rows. BindingDB-curated and
ChEMBL-origin records carry different license identifiers; unresolved origins
cannot enter split assignment. The official format also describes PDB links
as sequence-similarity annotations, not exact experimental-state matches.
Sources: [BindingDB downloads](https://www.bindingdb.org/rwd/bind/chemsearch/marvin/Download.jsp),
[TSV specification](https://www.bindingdb.org/rwd/bind/chemsearch/marvin/BindingDB-TSV-Format.pdf),
[BindingDB source/license paper](https://doi.org/10.1093/nar/gkae1075).

## CPU learning path and evaluation boundary

`python -m tools.product.train_public_assay_selector --help` describes the
hash-bound importer output, exact target-state hash, endpoint and fresh output
directory inputs. It trains one Ridge model (alpha 10) over chirality-aware
1024-bit Morgan radius-2 ligand fingerprints. All features are available before
docking. The target is fixed per model; IDs and assay outcomes are not features.
This model predicts negative-log molar concentration for its exact endpoint,
not affinity energy or molecular interaction information.

Before fitting, the command writes the source-bound protocol and split IDs.
The v2 model contract requires the shared metadata context described below.
Connected components share a split whenever they share a DOI/PMID alias,
Murcko scaffold, stereo-independent ligand identity, source ligand ID or
InChIKey connectivity. Label-blind deficit assignment targets 70/15/15 percent;
too few groups fail instead of falling back to a random row split. Calibration
rows are reserved and reported, but no uncertainty calibrator is fitted here.
This is an ordinary iterative development experiment, not a frozen or one-use
qualification protocol. It does not claim a similarity ceiling or temporal/OOD
generalization. [DataSAIL's addendum](https://www.nature.com/articles/s41467-025-67495-w)
and its [versioned split archive](https://zenodo.org/records/17376012) informed
the leakage checks; their supplied splits and benchmark data are not executed
or repurposed here.

The saved JSON checkpoint pins endpoint, target, feature contract, RDKit version,
implementation hash and training protocol. Its separate loader verifies those
fields and the externally supplied checkpoint hash. Evaluation uses this saved
checkpoint, checks equality against the in-memory model, and retains failures.
Individual-measurement and unique-chemical-state budget metrics are separate.
The latter uses the predeclared median across retained assay measurements; it
does not make heterogeneous assay conditions equivalent. Full-request recall is
unavailable when excluded/missing/censored labels prevent its determination.

## Metadata admission before target and endpoint selection

`public_assay_components.py` is reused by the real importer and trainer. Every
occurrence in the supplied TSV archive is a graph vertex, including other
targets, duplicate IDs, invalid chemistry, rejected rows, and rows without an
eligible endpoint. Metadata links are constructed before target/endpoint
selection. Original policy fields and joined assay policy provenance are retained;
calibration, development-test, protected, and unknown-policy components cannot
be fit rows. A measured zero declaration is distinguished from an unknown value.
This graph covers the supplied universe, not an inventory of every public or
protected dataset. Missing chemistry and similarity coverage remain limitations.

Optional `--reserved-context` and `--reserved-context-sha256` bind a separately
prepared metadata-only JSONL input. It contains hashed identity links and original
policy declarations with source hashes/member/line; observation values, assay
text, coordinates, model output, and nested arbitrary payloads are not accepted.
External nodes have `external:` identifiers. No external metadata file can grant
training authorization or reinterpret an experimental endpoint as engine energy.

The cache binds source and external node sets independently, checks every source
occurrence and its origin-derived ID, and checks all normalized and excluded
ledger entries before the trainer accesses endpoint observations. Duplicate node
IDs and duplicate JSON keys fail. Sidecars without this contract require a fresh
intake directory. This is consistency validation of an explicitly hash-bound
universe; it is not a signed independent attestation of source completeness.

The record schema stays `public_bindingdb_assay_development_v1`; its chemical and
measurement meanings do not change. New training checkpoints use
`public_assay_cheap_selector_ridge_v2` and pin the component implementation,
context, target, endpoint, feature contract, and protocol. The existing product
v1 shadow adapter remains separately pinned to its previously measured v1 model;
it does not automatically accept v2 checkpoints. No new interaction residual or
customer inference approval follows from this migration.

## First observed development run, 2026-09-08

The source archive SHA-256 is
`1203194f366623ae9b4caee34f2477d412ebddbda267593df9d1d92d0c66fb74`.
Two requested targets (CDK2/BACE1) contributed 2,387 rows: 2,343 normalized,
42 excluded for duplicate reaction IDs, and 2 for invalid SMILES. Across those
normalized rows, 1,833 were eligible for endpoint-specific split assignment;
missing exact endpoints, ambiguous assay joins and scope failures remain recorded.

The first model uses one human BACE1 target state and IC50 only. Its denominator
is 432 source rows, 390 normalized rows, 306 exact eligible endpoint rows and
126 total excluded rows. The supported fraction is 70.83 percent. The 306 rows
form 17 connected groups, split 214/47/45 rows (7/5/5 groups). No group crossed splits within those 306 selected rows. A later metadata audit
including 2,343 normalized rows and all 507 BACE source occurrences found a
component joining 60 fit, 4 calibration, and 2 development-test rows. The original
results below are retained as observations; they do not satisfy this expanded
independence criterion. The original development test contains 45 unique chemical
states. No old split, coefficient, checkpoint, or prediction is rewritten.

| Development-test observation | Fit-weighted mean baseline | Morgan Ridge |
|---|---:|---:|
| MAE, pIC50 units | 1.28797 | 1.27284 |
| RMSE, pIC50 units | 1.63559 | 1.46021 |
| Average precision, pIC50 ≥ 6 | 0.62222 | 0.89414 |
| Positive recovery at budget 9 of 45 | 5.6 expected under ties | 8 of 28 positives |
| Recall at that budget | 20.0% expected | 28.57% |
| Prediction failures | 0 | 0 |

These are small retrospective observations from five development-test groups,
with heterogeneous assay conditions and no calibrated confidence interval.
The result does not establish docking pose quality, physical residual accuracy,
prospective hit rate or product readiness. Candidate cost includes feature
generation and inference; reducing the candidate count is not engine acceleration.

On the observed CPU environment (Python 3.10.12, NumPy 1.26.4, RDKit 2026.03.6,
scikit-learn 1.7.2, one BLAS/OpenMP thread), the final learning function took
0.7022 s wall / 0.7020 s CPU, with 652,736 KiB process peak RSS. This includes
input materialization, feature generation, fitting and serialized inference;
imports/process startup, acquisition and intake are separate. Ridge fitting
alone took 0.00345 s. The high RSS of loading the 97.7 MB normalized JSONL pool
is a measured development ingestion limitation, not a model-size requirement.
GPU/VRAM, engine throughput and matched-quality engine acceleration were not
measured.

The first run preceded a denominator correction. A second run used identical
rows, split, seed and hyperparameters and proved bit-identical coefficients and
intercept and byte-identical predictions. Both raw runs are retained; the final
checkpoint SHA-256 is
`f3334484f501c56f58be673b56abf3a1789ce97909855ae1097c86cee230cd16`.
The dataset/model are local development artifacts and are not committed to Git.
The new synthetic module/CLI controls pass 47 tests without protected data.

## Observed full supplied-metadata intake, 2026-09-08

A new directory was generated using the same pinned source archive and requested
CDK2/BACE1 targets, plus the previously retained 2,343-row identity-only role
projection. The graph contains all 93,712 source occurrences and 2,343 external
metadata nodes in 710 components. Ninety-two external nodes declare calibration
or development-test roles. Across the graph, 303 source occurrences have no
resolved chemical identity; their available document/record links remain vertices.

The full requested denominator stays 2,387: 1,568 reserved-component exclusions,
42 duplicate occurrences and 2 invalid SMILES leave 775 normalized rows. Of these,
593 have at least one eligible exact supported endpoint and 182 have no exact
supported endpoint. This count is not a fit/calibration/test cohort size or a
scientific accuracy result. Old data, split assignments and model files remain
unchanged. The graph is more conservative than the original selected-row split;
removed candidates are not an engine speedup.

The final source-bound CLI completed with exit 0: 80.9960 s wall,
80.8486 s CPU, 729,092 KiB process peak RSS.
The process wrapper measured 81.3199 s including startup. One earlier run used a
helper before a joined-external-policy correction; both runs have byte-identical
records, ledger and context. Both raw executions are retained. These are two
correctness executions on a shared CPU host, not a cold/warm or p50/p95 benchmark.
No new public-data fit, molecular solver, GPU run or protected qualification was
executed by this intake. The final local suite passes 141 unique synthetic tests,
including actual intake/trainer consumers and observation-access traps; hosted
CI status must be read on the current PR head separately.

## Offline assay-to-structure identity links

`tools.product.public_assay_structure_links.build_identity_links` consumes local
SHA-256-bound files and performs no downloads. Its keyword-only API is:

```python
build_identity_links(records={"path": absolute_jsonl, "sha256": records_sha},
                     edges=edges, split_assignments=None)
```

Each edge has exactly `record_id`, `pdb_id`, `entry`, `polymers`, `nonpolymers`
and `components`. `entry` is a `{path, sha256}` RCSB core JSON binding or `None`;
the other three metadata fields are lists of bindings. Supply every polymer and
nonpolymer entity declared by that entry, and CCD metadata for every HET ID
declared by the source row. Optional split JSON binds `records_sha256` and an
`assignments` list of `{record_id, split, group}`; absent assignments remain
unassigned and cannot grant training admission.

The importer admission and original evaluation-only declarations remain gates.
The consumer separately verifies target UniProt mapping, entry-to-nonpolymer CCD
membership, and exact canonical isomeric chemistry. Matching a ligand alone
cannot establish the target. Missing mappings and ambiguous CCD identities remain
unknown; no unspecified stereochemistry or alternate protonation is resolved.
It streams the normalized pool, retains selected row/hash/role/split provenance
and every requested edge outcome, and rechecks declared paths and hashes after
use. It does not reopen the original archive; that limitation is explicit in
each source projection. Numeric assay labels and coordinates are not projected.

On 2026-09-08, 14 public source rows declared 41 PDB edges. The source-bound
consumer returned 6 `identity_link_only`, 34 rejected and 1 unknown. Rejections
comprised 20 source-intake contract failures and 14 target-UniProt mismatches;
the unknown edge lacked a polymer UniProt mapping. The six linked edges retain
three existing calibration assignments, one fit assignment and two unassigned
records. These are identity observations, not new fit admissions, assay-construct
equivalence, validated coordinates, charge/force-field support or scientific
validation. The ligand-only model and its checkpoint are unchanged.

The exact-parent local regression passed 104 synthetic tests: 47 existing intake
and selector controls plus 57 new identity-link controls. Three independent
path-binding controls passed separately and are not added to that total. CI
runs these three test modules and uploads their source, raw log and JUnit; it
uses no public cohort downloads or protected data. The actual metadata audit is
separate local evidence and is not a hosted scientific qualification.

## Next integration gates

The cheap selector remains separate from the product's diagnostic score residual
MLP. The existing score trainer correctly rejects experimental concentrations
as composite-score residual references. The product's optional residual shadow
loader is tested with synthetic observations; no experimental residual model has
been fitted into it.

The next work is a licensed, atom/state-matched public structure cohort and an
actual independent-engine baseline, with parameter/charge provenance and all
failures retained. RCSB metadata alone does not provide assay labels or assigned
force-field parameters. Fixed-candidate rescoring and end-to-end screening must
be evaluated separately. Pose evidence should combine symmetry-aware RMSD and
chemical validity, following the endpoint distinction in
[PoseBusters](https://arxiv.org/abs/2308.05777) and its
[versioned data record](https://zenodo.org/records/8278563); those benchmark
structures have not been run or used to train this model.


## ChEMBL metadata identity extension

The common component helper accepts optional raw source fields `ChEMBL Document
ID`, `ChEMBL Parent Molecule ID`, and `ChEMBL Assay ID`. IDs must be strings
matching `CHEMBL[0-9]+`; absent, null and empty values remain missing, while
malformed values fail explicitly. Real DOI and PMID identities coexist with the
ChEMBL local document identity. Parent molecule links constrain reservation and
splitting; they do not replace a salt, stereoisomer, protonation state or original
source molecule.

Rows without an assay ID retain the original v1 node representation. An explicit
assay ID emits `public_assay_identity_context_v2` and a distinct `source_assay`
key. The helper accepts mixed v1/v2 metadata contexts, rejects an assay key in a
v1 node, requires an assay key in v2, and rejects unknown versions. Normalized
source projection regenerates every optional key before accepting a cache.
Deleting an assay key, including downgrading the cached node to v1, cannot hide
it from the normalized coverage check.

A ChEMBL assay may have activity rows associated with several documents. The
assay-level document may also differ from every activity-level document. Keep
both sources: every activity remains a vertex carrying its own document and
assay IDs, and a separate metadata-only assay vertex connects the assay ID to
its own document and source DOI/PMID. Do not choose the last document or remove
unsupported endpoints, other targets or invalid structures before constructing
the graph. This describes the metadata projection contract; the existing
BindingDB normalizer does not become a ChEMBL concentration importer merely
because the common helper supports these identities.

The exact previous helper's 141 intake, selector, structure-link and cache
regressions passed locally. Fresh actual-trainer synthetic controls exposed two
reserved-observation accesses in the old helper; the candidate prevented them
and preserved the disconnected positive control. The combined local suite has
184 passing tests with no failures, errors or skips. These are software
contracts, not experimental validation or evidence of improved active recovery.

### Cache and checkpoint compatibility

The selector intake and checkpoint loader bind the SHA256 of this helper.
Changing the helper therefore invalidates old intake/cache/checkpoint use in the
new consumer even though the selector's numeric checkpoint format is unchanged.
Keep previous measured artifacts with their frozen original consumer. Regenerate
the metadata context and source-bound intake before any new fit; do not overwrite
an old checkpoint hash to make it load or retrain on previously used evaluation
outcomes. New cross-source connections can reveal dependence between previous
roles. Preserve those original roles and historical scores and report the newly
observed connections separately. Scientific, training, customer-runtime and
commercial approvals remain separate and are not granted by this extension.

## Native ChEMBL measured intake and staged learning

`public_chembl_measurement.py` interprets the native published/standard activity
pair, retains original field presence and values, checks supported concentration
or explicit logarithmic transformations, and separates point observations from
censoring, ranges, missing values and inconsistencies. A measured zero is not a
missing value; a zero concentration has no finite negative-log concentration
label. Endpoint names remain distinct. It never generates an energy residual or
force label. Numerical normalization and purpose-specific admission are separate.

`public_chembl_assay_dataset.py` uses the existing chemical canonicalizer and
metadata component helper. Its `public_chembl_assay_development_v1` schema is
explicitly ChEMBL-native; the legacy identity projection is identified separately
from the native API record and response/request origin. Full supplied metadata,
including excluded rows, is checked before any activity capture is read. Native
IDs and the identity projection must agree. Cached chemistry is reproduced for
all activity metadata, and an already declared component split is reproduced
without labels. A rejected or withheld measurement remains in the full ledger
and retains its role. Newly assigned calibration/development reservations are
added to the complete context without replacing prior declarations.

The first scope is database-curated reported enzyme-inhibition IC50 with mixed
assay conditions, under the ChEMBL target annotation CHEMBL3038469. It does not
verify the experimental CDK2/cyclin A2 construct, an assayed microstate, or a
receptor coordinate state. Known secondary reviews and peptide-displacement FP
assays are excluded before this experiment's role assignment. Public access and
primary-paper method compatibility are recorded separately from compound-level
source-value verification. Missing ATP, pH, temperature and construct metadata
are not filled with defaults.

`train_public_chembl_selector.py` reuses the existing Morgan 1024-bit, radius-2,
chirality-aware features and Ridge(alpha=10) model. It is a pre-docking ligand-only
cheap-selector experiment; target identity is an admission constraint, not an
interaction feature. The trainer reconstructs records, the ledger, role context
and summary source/count bindings from native captures. A rehashed cache is not
accepted as independent proof of eligibility or a training label.

The fit phase reads only preassigned fit outcomes, writes a protocol before
fitting, and freezes serialized-checkpoint predictions for every selected
candidate before evaluation outcome acquisition. The evaluation phase requires
that frozen bundle, verifies mean-baseline values and chemical abstentions as
well as numerical predictions, and preserves unsupported/censored outcomes in
its denominator report. No resplitting or hyperparameter search follows
exclusions. The calibration role is reserved for diagnostics in this first run;
no probability or uncertainty calibration is claimed.

Example module interfaces (hashes bind the actual source files and captures):

```bash
python -m tools.product.public_chembl_assay_dataset \
  --manifest metadata-manifest.json --manifest-sha256 SHA256 \
  --captures fit-capture-manifest.json --captures-sha256 SHA256 \
  --phase fit --output-dir fit-intake
python -m tools.product.train_public_chembl_selector \
  --phase fit --input-dir fit-intake --summary-sha256 SHA256 --output-dir fit
```

Evaluation acquisition is a separate developer action after `fit/frozen-fit.json`
exists. Its capture manifest binds that file and the request/response execution
origins. Run the same intake command with `--phase evaluation` and then the trainer
with `--phase evaluation --frozen-fit fit/frozen-fit.json
--frozen-fit-sha256 SHA256`. These tools do not download data or invoke a molecular
solver themselves. Public API acquisition remains separate and auditable.

The new checkpoint schema is `public_chembl_cheap_selector_ridge_v1`, with a
catalogue target annotation hash, explicit prediction quantity and source
implementation bindings. Old BindingDB intakes/checkpoints are not relabeled or
migrated by changing a schema string. Keep original frozen consumers for earlier
models. This developer consumer does not register a new checkpoint in the
BioDiscovery product shadow loader, enable ranking, calibrate uncertainty, or
approve customer execution. IC50/pIC50 is not subtracted from the independent
Engine V2 potential energy.

### First ChEMBL development measurement, 2026-09-09 KST

The full requested metadata universe had 27,489 activity rows. After prior role
reservations and source/method exclusions, 144 candidates were assigned before
activity-value access: fit 101, calibration 22, development test 21. The frozen
plan SHA256 is `ec80249b46e825f24029c8a097ab67497985b414f51fcd94e5495cd7efb11744`.

Native fit captures contained 53 exact, 38 censored and 10 missing observations.
Only the 53 exact rows from four connected components entered this point model.
The frozen checkpoint is
`5733e7ba2d21f643034ec111648b94244c5114dfd875391d874eb983e949dca6`.
All 144 selected candidates received predictions before the 43 evaluation labels
were acquired. Calibration retained 20/22 exact rows in two components;
development evaluation retained 18/21 in five components. Remaining labels stay
in the ledger and are not assumed negative.

| Development test: 18 exact observations | Mean baseline | Morgan Ridge |
|---|---:|---:|
| MAE, negative-log-molar IC50 units | 1.1772403 | 1.2902383 |
| RMSE, same units | 1.5398050 | 1.6647280 |
| Average precision, threshold pIC50 >= 6 | 0.7777778 | 0.8026326 |
| Positive hits at budget 4, fractional treatment of ties | 3.1111111 | 3.0000000 |

The model did not improve error or positive recovery at the declared budget.
Calibration's 20 exact observations were all positive, so its AP=1 for both
methods is not discrimination or calibration evidence. Neither model selection
nor a new split was based on these results. Product ranking remains disabled.
This is retrospective, database-curated development evidence, not confirmation
of the paper's individual compound-to-value mappings or prospective assay hits.

The actual CPU fit process took 35.383 s wall / 35.380 s CPU, peak RSS
2,133,188 KiB, including full metadata/capture verification and serialized
prediction checks. Within that process, featurization took 0.006729 s and the
Ridge fit 0.001392 s. These are single-process observations, not p50/p95,
end-to-end docking speedup, or an equal-quality cost improvement. Input download,
intake, evaluation, source-paper review and packaging costs are separate.

Validation retained the original 184 public-assay tests and added 99 portable
measurement/staged-consumer controls: 283 passed, no failures/errors/skips,
with warnings treated as errors. A separate internal AI reviewer used 20 new
metadata/cache/frozen-prediction controls; they passed on the same three module
hashes. Intermediate implementation failures and reference-fixture errata are
retained in the evidence bundle. An accidentally broad collection against the
partial repository snapshot produced 1,273 collection errors; it was not a
passing full-repository suite and no protection was removed to pass it.
