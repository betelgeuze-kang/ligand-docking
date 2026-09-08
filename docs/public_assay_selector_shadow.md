# Versioned public IC50 selector shadow

The canonical HTVS runner can optionally write predictions from the pinned public
BACE1, CDK2/cyclin A2, or native ChEMBL catalogue-annotation selector before stage1 ligand mapping. The option defaults to disabled.
It neither selects candidates nor changes mapping commands, ranking, stage2 skip
routing, scores, or the downstream candidate denominator.

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
