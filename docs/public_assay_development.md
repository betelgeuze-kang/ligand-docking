# Public assay development intake and first learning experiment

This path is an offline development importer and a target-specific cheap-selector
candidate. It does not enable customer execution, docking ranking, physical
energy correction, calibrated uncertainty, or a new molecular engine.

## Source and chemistry contract

`python -m tools.product.build_public_assay_development_dataset` consumes an
already downloaded BindingDB TSV/ZIP, reaction-to-assay mapping, assay description
file and an identity exclusion catalog. Each input requires its expected SHA-256.
It writes a new directory with `records.jsonl`, `ledger.jsonl`, and `summary.json`.
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
form 17 connected groups, split 214/47/45 rows (7/5/5 groups). No group crosses
splits. The development test contains 45 unique chemical states.

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
