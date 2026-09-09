# Versioned public assay selector shadow

The canonical HTVS runner can optionally write predictions from the pinned public
BACE1, CDK2/cyclin A2, native ChEMBL catalogue-annotation, or native BindingDB
Factor X Ki selector, or native ChEMBL Factor Xa Ki v2 selector before stage1 ligand mapping. The option defaults to disabled.
It neither selects candidates nor changes mapping commands, ranking, stage2 skip
routing, scores, or the downstream candidate denominator.

## Native ChEMBL Factor Xa Ki v2 compatibility

The frozen ChEMBL37 CHEMBL244/P00742 checkpoint is explicitly registered as
`public_chembl_cheap_selector_ridge_v2`, separate from native IC50 v1:

- checkpoint SHA: `c6e508e390df9d295ec53c9cc26f16a27c7ff5e31bf8f479e777f6c2e758049b`
- quantity: `negative_log10_molar_Ki`; endpoint/subtype: `Ki` / `enzyme_inhibition_Ki`
- producer source: `79e3c5fe55b9844a4812df9ce995754d55e10cd3`
- original source-policy SHA: `a968c413f33e95b0ec43840a807b520a9d6bf1fd7dbc6f06cd0df0ccd1d1b358`

Use the existing HTVS flags with this checkpoint/hash and a CSV containing
`smiles`, `target_annotation_sha256`, `endpoint=Ki`, and
`endpoint_subtype=enzyme_inhibition_Ki`. The annotation SHA is the exact value
in the registered checkpoint, not a P00742 string or prepared receptor identity.
Ki outputs use `prediction_quantity`, `predicted_value`, `mean_baseline_value`;
no Ki value is placed in an IC50 field. Missing metadata, unsupported chemistry,
wrong endpoints, declared OOD and nonfinite inputs retain rows and null values.
The exact original ChEMBL chemistry scope has one fragment, 5–70 heavy atoms,
H/C/N/O/F/P/S/Cl/Br/I, no isotope/radical atoms and no declared formal-charge cap.
Runtime admission does not establish chemical OOD performance.

The producer fit224 observations in10 components from316 preassigned fit rows.
All452 predictions were frozen before136 evaluation values. Strict calibration
coverage is20/68 and development3/68. Development MAE worsened from1.00396 to
1.17684 pKi. Full-request recovery, physical target-state correctness and
uncertainty calibration remain unestablished. No refit or outcome-based resplit
was performed for this registration. Later PR511 policy fingerprints differ;
this adapter preserves the original checkpoint/source binding instead of
rewriting the checkpoint to look current.

Actual canonical HTVS parser, `run_pipeline` and shadow-hook execution reproduced
452/452 frozen predictions to max absolute difference1.777e-15. Original CSV
cells/order,10 repeated ligand-ID rows, and the mapping command matched with
shadow off/on. Mapping was intercepted immediately after the real hook; no
mapping subprocess, docking or full engine run occurred. All452 passed runtime
chemical admission, not the experimental-label admission test. The source
metadata roster remains4,766 with its exclusions in the separate intake ledger.

A single imported-process hook took0.13194s wall/0.13179s CPU, peak627,280KiB
for the entire process. A separate fixed CPU profile used5 observations per
size/mode and no outcome-based input selection:

| CSV rows | Fresh-process p50/p95 wall, s | Warm hook p50/p95 wall, s |
|---|---:|---:|
| 32 | 1.7553 / 1.7869 | 0.00961 / 0.00965 |
| 128 | 1.7566 / 1.7909 | 0.03513 / 0.03521 |
| 452 | 1.8555 / 1.8813 | 0.12873 / 0.12983 |

Fresh-process wall includes Python/HTVS-context imports, model loading and
sidecar writing; OS file caches were not flushed. Warm observations follow one
separate warmup in the same process, still reload the model and recompute all
features. These scopes must not be divided into an acceleration ratio. Maximum
fresh-process peak RSS was585,204KiB; every worker succeeded and every prefix
prediction matched the full452-row reference within1e-12. These are descriptive
five-sample observations, not stable deployment-tail estimates, GPU evidence,
matched-quality engine acceleration or end-to-end A–E screening benefit. The
first aggregate report had a dictionary-key error; the completed worker logs
were reaggregated without rerunning or selecting measurements.

The original adapter rejected this new version in44 fresh synthetic controls.
Final local tests include the existing optional real BindingDB metadata replay;
portable CI omits its private local file paths and reports that expected skip.
No prior tests, flags or protections are removed. Model weights/assay data remain
outside Git. Package serving imports no training producer or scikit-learn.

## Native BindingDB Factor X Ki compatibility

**Historical observation only after the expanded identity audit.** All515
point-fit rows became linked to evaluation dependencies in the expanded supplied
graph. Current shadow metadata exposes
`identity_independence_status=failed_expanded_metadata_dependency_audit`, the
exact audit SHA, and disables use as new independent evaluation/training evidence.
This preserves historical arithmetic; it does not prove numerical evaluation
labels were used in fitting. The old quality numbers below must not be promoted
as independent performance evidence. Its bytes and compatibility replay remain
unchanged, and ranking/customer execution stay disabled.

The `public_bindingdb_preassigned_ridge_v1` checkpoint is separately registered:

- checkpoint SHA: `de9b3e21c93b0f15c02df221d2f8ee9caa3d5e0590442c34efed3394b969ac85`
- target annotation SHA: `9359ee693bcd2a1342fbc39019a015888723cdaa006cf0e11a1b9d9fb9518a5f`
- endpoint: `Ki`; quantity: `negative_log10_molar_Ki`
- manifest SHA: `1e7d39305219e0454069ca4668376a7936ac3c3f48a5e653cca845d84d7dc618`
- protocol SHA: `3ea86001a405f15b305522947e8f4f11128f112b91a340bc78134492db675cd9`

Use the same HTVS options below with this checkpoint path/hash. The input CSV
requires `smiles`, `target_annotation_sha256` and `endpoint=Ki`; `ligand_id` and
the original CSV cells are retained. It does not require a ChEMBL endpoint
subtype. The native BindingDB sidecar uses `prediction_quantity`,
`predicted_value` and `mean_baseline_value`. Existing IC50 output fields remain
unchanged for their original checkpoint versions. Ki values are never placed
in IC50 fields, including registered-model failure and unsupported-row paths.

The registry pins the exact producer/helper hashes, checkpoint bytes, catalogue
annotation, endpoint, features and the frozen manifest's runtime chemical scope:
one fragment, 5–70 heavy atoms, H/C/N/O/F/P/S/Cl/Br/I, absolute formal charge at
most two, no radicals or isotopic atoms. The serving package does not import
the training modules or reinterpret catalogue identity as an active Factor Xa
construct, charge assignment or prepared receptor state. Declared OOD, missing
identity and unsupported chemistry receive null predictions. Admission inside
these bounds is not a calibrated OOD assessment.

This model was fit once on 515 database-curated reported Ki observations in
three preassigned components. All914 metadata predictions were frozen before
evaluation-label access. Development MAE improved from1.25085 to1.09580 pKi,
but calibration MAE worsened from1.03115 to1.64274. At a fixed28-of137 budget,
calibration known-positive recovery was11 versus the mean baseline's tie
expectation19.42, with17 selected labels unresolved/outside scope. Full-request
recall remains null. Compatibility registration is not an accuracy or ranking
promotion; customer execution, ranking and calibrated uncertainty remain false.

On 2026-09-09 the actual canonical HTVS parser, `run_pipeline` and shadow hook
were executed with the frozen model and914 metadata-only CSV rows. All914
predictions matched the frozen training-side predictions exactly. The input,
row order, duplicated ligand IDs and downstream mapping command were preserved
with shadow off/on. Mapping was intentionally intercepted after the hook;
no mapping subprocess, docking search or end-to-end engine run occurred.
All914 met runtime chemical admission, which does not mean all914 have usable
experimental labels or a verified physical receptor state.

The separately timed hook took0.2587s wall/0.2584s CPU, with591,596KiB process
peak RSS, including checkpoint loading, CSV parsing, molecular features,
inference, mean baseline and sidecar writing. Imports and downstream mapping
are excluded. This was one CPU integration execution, not a cold/warm, p50/p95
or engine-acceleration benchmark.

Local validation passed191 cases including explicit914-row actual-artifact
replay. Portable CI options passed190 cases with one expected skip because
the local real checkpoint/manifest are not shipped in Git. The synthetic
contracts, previous three IC50 suites and canonical HTVS interception remain
enabled; Ruff passed. The original HTVS runner and previous IC50 tests are
byte-identical. The optional real-artifact test accepts
`BETELGEUZE_BINDINGDB_SHADOW_CHECKPOINT` and
`BETELGEUZE_BINDINGDB_SHADOW_MANIFEST`; its absence must be reported as a skip.

## Original BACE1 IC50 invocation

Example (use the existing immutable checkpoint and its exact byte hash):

```sh
python tools/run_ligand_htvs_pipeline.py \
  --ligand-csv requests.csv \
  --public-assay-shadow-enabled \
  --public-assay-shadow-checkpoint /path/to/BACE1-IC50-selector.json \
  --public-assay-shadow-checkpoint-sha256 f3334484f501c56f58be673b56abf3a1789ce97909855ae1097c86cee230cd16 \
  --out-prefix /path/to/run
```

These options add diagnostics to an otherwise normal HTVS invocation. The command
continues the configured pipeline, including its existing expensive stages.
The test evidence intercepts the child command before mapping or docking executes.

The original CSV must contain `smiles`, `target_state_sha256`, and `endpoint`.
`ligand_id` is preserved when present. The exact declaration accepted by this
checkpoint is state
`b814cbb86d26ad260ab6e487614c96006d46eab45e53122fc17672457125bdfc`
and endpoint `IC50`. This is a caller declaration of the original assay record's
target identity. A target name, receptor file, or `--targets BACE1` does not verify
this state, receptor sequence, preparation, or assay construct.

The sidecar is `<out-prefix>_public_assay_selector_shadow.json`; stage1 metadata
points to it. It records every parseable original CSV row, its index and input
cells, including duplicate IDs, blank rows, invalid widths, and unsupported rows.
Its denominator describes the supplied CSV before stage1 filters, truncation,
metadata overlays, ligand replicas, and queue construction. An unreadable CSV has
an unknown denominator. SDF-only inputs, docking-request JSON inputs, and stage3
resume are explicitly unsupported/not evaluated with unknown requested row counts.
The original inputs remain available to the existing pipeline unchanged.

Missing or invalid SMILES, absent/mismatched state or endpoint, declared OOD, and
structures outside the original intake's size/fragment/element/isotope/radical/
charge scope receive null predictions. No salt stripping, neutralization, tautomer
selection, or stereochemistry completion occurs. Unspecified stereo is not silently
made known. Optional `is_ood` accepts booleans or `true`/`false`/`1`/`0` strings;
other nonempty values are unsupported. Passing these pilot admission bounds does
not establish chemical applicability: OOD remains `not_assessed`, and uncertainty
is null. The checkpoint supplies no reference fingerprints or calibrated OOD model.

The prediction is `predicted_negative_log10_molar_IC50` for this recorded BACE1
state and the retained mixed assay conditions. It is not a potential energy,
force, general affinity estimate, calibrated binder probability, or validated
customer ranking. Calibration, customer execution, and ranking capability flags
remain false.

The package adapter exactly pins the checkpoint bytes, legacy producer SHA,
training protocol, feature specification, endpoint, state, and RDKit `2026.03.6`.
It reproduces the original chiral Morgan radius2/1024-bit float64 linear predictor.
The legacy producer and checkpoint remain immutable. The producer is
`tools/product/train_public_assay_selector.py` from PR #511, exact source head
`43ae79cc3b2268ca38ff8a3cc68cb51d513b3887` and producer SHA
`daae5205bb8d767805be0b786b3e85fa5c70aaecab61535fac5b224bdd562e0d`.
This is checkpoint provenance, not a runtime import or a requirement to copy the
training pipeline into the serving package. The shadow integration is based on
PR #508 head `361049077e30ea7daefbc99556539b47fed30aa3`. A new runtime adapter SHA is
recorded separately; using a different producer/checkpoint requires an explicit
reviewed compatibility migration. Loader, constructor, and prediction errors keep
rows unsupported rather than supplying random weights, zeros, or an intercept
fallback. Output aliases to inputs/checkpoint are rejected.

The new loader imports no `tools.*` or scikit-learn. NumPy and RDKit are needed
when enabled; package initialization retains its existing Torch/NumPy and packaged `core` dependencies.
Canonical HTVS still has pre-existing `tools.*` runtime imports. This change does
not establish that the entire runner is available in a minimal installed wheel.
Synthetic contract tests and public inference parity establish software behavior;
they do not establish prospective accuracy, acceleration, docking validity, or
commercial readiness.


## CDK2/cyclin A2 v2 compatibility migration

The v1 bytes and producer binding above remain unchanged. A second exact checkpoint
is registered for development shadow inference only:

- checkpoint: `00b52d1a6b7e6b7b1c801585adcbca0c73ac57ffe7b8c000cdbc20ad38f1e4fd`
- schema: `public_assay_cheap_selector_ridge_v2`
- recorded target state: `52e47746dd4554dd346720ec0340848ab8e3a19adedf9c453c4d5557fe3576c6`
- producer: `3df5839854abf24284ebbb71bf82635d8ccbc8405b0de8990a01a07854e45a26`
- training protocol: `d3a03b2fca25e290b5ad95fc53169dba910b1a4b5cafdff24149ab1b043d5743`
- identity context: `f9882e243e973861844a6db119fde6263b77847e1517b1a8bbb9d513d52550ac`
- component helper: `c21ea44055d60313eb8305f8f438a989b805748e98b90b010ebfce836b9ea29a`
- policy: `all_supplied_metadata_components_before_target_endpoint_selection_v1`

The producer source is PR #511 head `d40b32be85d92a8daab1d262aba06c6f0dd3acef`.
Its graph includes all supplied archive rows, excluded and other-target bridges,
and explicitly bound external metadata before target/endpoint selection. It does
not claim a globally complete or similarity-complete exclusion inventory. V2
requires its context/helper/policy fields; dropping them, borrowing the v1 schema,
swapping the target/endpoint, or supplying unregistered bytes is rejected. The
runtime imports no training producer or identity graph builder.

This model used 190 as-reported IC50 measurements from the 723 requested rows for
that recorded state: 131 fit, 28 calibration, and 31 development-test rows across
8 identity components. Original ATP and assay conditions were retained; this is
not a condition-specific assay model or a conversion to Ki, Kd, or potential energy.
The 533 other requested rows remain accounted for and are not assumed negative.
Calibration has only one component and no calibrated uncertainty claim is made.

The fixed-seed, fixed-alpha Morgan ridge model did **not** improve the mean baseline:
development RMSE was 1.343573 versus 0.993001, and selecting 7 of 31 unique chemical
states recovered 4 of 23 positives versus the tied mean baseline's expected
5.193548 hits. Positives were predeclared as pIC50 >= 6. These are retrospective
in-scope development observations, not whole-request recall or prospective proof.
No retraining or threshold tuning followed these outcomes. The model is registered
so its actual predictions can be inspected, not as an accuracy approval.

Use the existing CLI options with this checkpoint's path/hash and its recorded
state in the CSV. Output schema `public_assay_selector_shadow_v1` is retained;
additive `checkpoint_schema_version`, `evidence_kind=ai_prediction`, and
`compatibility_registration_only=true` distinguish model provenance. The scope
matches the successfully loaded model at both sidecar and model levels, and is
null when no model was loaded. All ranking, customer, and calibration capabilities
remain false. Existing scores and candidate ordering are not replaced.


## Native ChEMBL annotation compatibility migration

The existing loader and HTVS hook also accept the frozen native checkpoint
`5733e7ba2d21f643034ec111648b94244c5114dfd875391d874eb983e949dca6`, schema
`public_chembl_cheap_selector_ridge_v1`. Its training implementation is bound in
PR #511 head `55717590c8ee9795cfc2ac37984c1f4daa0f8681`. Its six producer hashes,
metadata identity context, split plan, intake scope, and pre-fit protocol are
required unchanged. It uses the same Morgan radius2/1024-bit chiral float64
predictor and RDKit `2026.03.6`; the runtime imports no ChEMBL intake or trainer.

This version's CSV requires `smiles`, `target_annotation_sha256`, `endpoint`, and
`endpoint_subtype`. The exact accepted declaration is:

- annotation: `0ab0f219820e5b0e7b27c07731f35db19b1130863660c46b9e099435b958294f`
- endpoint: `IC50`
- subtype: `enzyme_inhibition_IC50`

The annotation denotes ChEMBL's catalogue target `CHEMBL3038469` under mixed
reported kinase assay conditions. It does not verify a physical receptor state,
construct, cyclin isoform, ATP concentration, or assayed microstate. The native
version never substitutes `target_state_sha256` for this annotation. Legacy
models still require their original state field. No checkpoint fields are renamed
or removed to make a native model resemble a legacy model.

The native intake predeclared 5–70 heavy atoms, one fragment, H/C/N/O/F/P/S/Cl/Br/I,
no isotopes or radicals, and no formal-charge cap. The consumer preserves that
scope; it retains the legacy models' separate absolute charge limit of two.
Neither bound is a calibrated OOD criterion. No neutralization, salt stripping,
stereo completion, physical preparation, or geometry generation occurs.

For each supported row the sidecar records the AI prediction and the frozen
`mean_baseline_negative_log10_molar_IC50`. The latter is the fitted training mean,
marked `mean_baseline_evidence_kind=heuristic`, not a new measurement or an
uncertainty estimate. Unsupported rows retain null AI and baseline predictions.
All original CSV cells, roles, indices, duplicate IDs, and supplied provenance
columns remain visible. Native annotation and endpoint subtype have separate
explicit declaration fields. When no model loads, target and chemical scope
remain null. The additive sidecar schema stays `public_assay_selector_shadow_v1`.

The metadata-only plan reserved 144 candidates: 101 fit, 22 calibration, and 21
development-test rows. Only 53 exact fit observations entered the single frozen
fit; censored and missing fit observations remained in the ledger. Evaluation
admitted 38 exact observations among 43 requested rows. On 18 exact development
rows, model MAE was 1.290238 versus the mean baseline's 1.177240; selecting four
recovered three positives versus the tied mean baseline's expected 3.111111.
Twenty exact calibration rows were all positive and do not establish
classification discrimination or calibrated uncertainty. No refit, seed search,
alpha search, split changes, or threshold tuning followed these outcomes.

Compatibility registration exposes the frozen negative result for inspection.
It keeps default execution disabled, ranking/customer/scientific capabilities
false, and uncertainty null. It supplies no physical-energy residual, force
correction, activity probability, or claim of greater active-candidate recovery.
Existing docking, score, and skip-routing behavior remains unchanged.

Fresh synthetic migration controls cover both old models and this native schema.
A separate local consumer observation reuses the 144 predictions frozen before
evaluation-label acquisition, without reading those labels or invoking training.
Three fresh CPU processes, individual/batch sizes 1/32/144, and seven warm repeats
per size/mode record numerical parity, raw wall/CPU time, and process peak RSS.
The real HTVS entrypoint writes the sidecar before an intentionally intercepted
mapping child; molecular docking and end-to-end candidate selection are not
executed by that observation. These checks establish runtime compatibility and
inference cost, not improved predictive quality or whole-engine acceleration.


## BindingDB AKT1 IC50 compatibility and observed cost

The v1 BindingDB checkpoint schema can describe multiple endpoints. The former
consumer assigned `negative_log10_molar_Ki` to every BindingDB row and a Factor Xa
scope to every BindingDB model. A fresh synthetic IC50 checkpoint reproduced this
error. Output quantity now comes from the exact registered checkpoint binding;
BindingDB scope includes the bound target annotation hash and endpoint. Invalid
rows and unavailable registered model bytes retain the requested model quantity,
while unknown checkpoints remain refused. The sidecar schema stays v1 and adds
`endpoint_semantics_version=registered_checkpoint_quantity_v2`; consumers should
use the separate target annotation hash instead of parsing the old scope string.
No checkpoint, fit schema, coefficients or trainer is rewritten.

The unchanged AKT1/P31749 checkpoint
`d5c4c17902ee35c920c2948f445f06b0aba13c4ba02cfa8a13390a18689ff4b3`
is registered for **shadow observations only**. Its producer/manifest/protocol/
split/target hashes, fitted mean and RDKit version are pinned individually. Its
post-freeze evaluation summary is bound by
`a1be98fd16ca6232555277986c3700a1b4679bc2657437d131d217bf0b043a24`.
The sidecar retains `NOT_PROMOTED`: calibration pIC50 MAE worsened from
0.470805 to 0.543839 on16/18 rows; development worsened from0.929223 to1.168317
on5/19 rows. Supported development positives were zero, so recall/AP remain
undefined. These are database-curated measurements, not independently verified
primary per-compound tables or harmonized assay conditions. Scores are AI
predictions, not molecular energies, receptor-state verification or calibrated
probabilities. Historical Ki checkpoint dependency warnings remain intact.

Actual metadata replay preserved all210 original target rows and source role/
exclusion columns. The122 previously frozen predictions match the product module
and HTVS sidecar exactly (maximum absolute difference0). The88 upstream excluded
rows carry intentionally withheld SMILES, null predictions and the original
exclusion reasons in their input cells. They are not additional scored candidates
or assumed inactive molecules. The canonical HTVS entrypoint ran with explicit
AKT1 catalogue naming and was intercepted before its first ligand-mapping child;
shadow on/off produced the same mapping command. No mapping, docking, physical
energy or external solver execution is established by this interception.

On one local CPU host (Python3.10.12, RDKit2026.03.6, NumPy1.26.4,
single BLAS/OpenMP thread),15 warm repetitions per mode measured the same original
input prefixes. Requested/evaluated counts were1/1,16/11,122/93,210/122.
For the complete210 rows, individual inference wall p50/p95 was36.280/36.315ms;
batch was32.187/32.263ms. Predictions agreed within1e-12 across modes. Process
peak RSS was505348KiB, a process high-water observation rather than incremental
selector allocation. Five fresh processes at each size1,122,210 also ran; for210
rows total process wall p50/p95 was1474.972/1482.706ms and peak RSS505004KiB.
OS file caches were not flushed. Fresh-process time includes eager package imports
and process setup; these measurements are not engine acceleration, GPU parity,
receptor-neighbor caching, docking recovery or end-to-end screening evidence.

Validation:259 passed,0 failures/errors,1 existing optional historical frozen-Ki
replay skipped because its explicit artifacts were not supplied. Includes16 new
synthetic IC50 controls. Separately5 actual checks passed with no failures/skips:
original artifact hashes, independent scalar fingerprint dot products, frozen
prediction equality, full-request sidecars, and identical intercepted mapping.
The original semantic control fails as expected against the old consumer. Initial
local execution errors (wrong module path, incomplete snapshot and cross-schema
scope construction regression) are preserved; the latter was fixed by applying
BindingDB-specific scope only to BindingDB schemas. No protection/test was relaxed.

Current local evidence root:
`/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-akt1-shadow-zklxtbk3`.
It contains source snapshots/hashes, exact commands and exits, raw logs, JUnit,
input/sidecar artifacts, independent checks and all warm/fresh-process samples.
This is a development evidence location, not a portable checkpoint distribution.
The hosted workflow additionally uploads tested source identities and synthetic
logs/JUnit. Customer execution and product ranking remain disabled. Prepared
same-state AKT1 Engine V2 evidence and screening quality/cost improvements remain
open; no external review or approval receipt is implied.
