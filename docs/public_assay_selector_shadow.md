# Public BACE1 IC50 selector shadow

The canonical HTVS runner can optionally write predictions from the pinned public
BACE1 selector before stage1 ligand mapping. The option defaults to disabled.
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
