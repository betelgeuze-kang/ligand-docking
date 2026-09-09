# Post-freeze BindingDB method review and evaluation

The existing fit manifest binds its method ledger. If evaluation methods are
unknown at fit time, replacing that ledger after review invalidates the frozen
checkpoint's manifest binding. The new `public_bindingdb_postfreeze_evaluation`
adapter supports this phase transition without editing the original fit artifact
or any original producer module. Existing BindingDB and ChEMBL consumers retain
their contracts. This does not implement native ChEMBL evaluation.

## Execution and reuse

1. `capture-methods` loads the original source-bound metadata and uses the
   existing frozen validator to reproduce every saved prediction. It then scans
   source mapping IDs against the full bound identity graph. Shared assay keys
   crossing frozen roles/components, unknown linked records and reserved source
   policies fail before evaluation method descriptions are opened.
2. The capture manifest binds a separate method-body file; bodies cannot be
   opened just to discover whether the original checkpoint is valid. Existing
   `phase_assays` provides exact native mapping/description provenance. Capture
   does not read numeric evaluation rows.
3. An internal development review covers every evaluation ID once, with status,
   reason and exact captured source references. It cannot replace fit decisions.
   The schema does not represent external reviewer approval.
4. `evaluate` reproduces the capture from its original sources and validates the
   complete review before using the existing native row reader, `derive`, and
   metric primitives. Original model, fit manifest and assignments are retained.
   Unknown, ambiguous, missing, invalid and censored results remain in the
   requested denominator. Uncomputed physical energy and force labels stay null.

```sh
python -m tools.product.public_bindingdb_postfreeze_evaluation capture-methods \
  --manifest FIT_MANIFEST --manifest-sha256 FIT_MANIFEST_SHA \
  --frozen-fit FROZEN_FIT --frozen-fit-sha256 FROZEN_FIT_SHA \
  --output-dir METHOD_CAPTURE
python -m tools.product.public_bindingdb_postfreeze_evaluation evaluate \
  --capture METHOD_CAPTURE/method-capture.json --capture-sha256 CAPTURE_SHA \
  --review METHOD_REVIEW --review-sha256 REVIEW_SHA --output-dir EVALUATION
```

Capture/review/evaluation use new, separately named v1 schemas. All original
producer hashes and checkpoints remain unchanged. A later adapter source change
requires its own verified capture; old captures must not be silently rehashed.
Neither command fits, resplits, tunes or enables customer ranking. Source byte
checks before/after execution also cover archives containing unread rows.

## Actual AKT1 diagnostic, 2026-09-09 UTC

Original BindingDB source:93,712 rows. Current context:154,604 nodes. Exact AKT1
catalogue annotation:210 rows. The predeclared endpoint-presence selection and
one fixed component split assigned122 rows:85 fit,18 calibration,19 development.
Original model used55 exact supported fit rows in3 components. It froze122
predictions before any evaluation-method content or native evaluation values.

Checkpoint SHA256:
`d5c4c17902ee35c920c2948f445f06b0aba13c4ba02cfa8a13390a18689ff4b3`.
Frozen-fit SHA256:
`0b3dcc405f5029adf741ca149adc9ab70b6688d0b574e69313d4ee9bb799bd17`.
Fit manifest SHA256:
`00b5fc2e017b1f00cb336b5e1747c992b21335ebfbfe88f8c893434f9cecb5c7`.
These bytes were preserved, with no retraining or producer migration.

The post-freeze method review admitted21 records at the database-curated
biochemical IC50 scope. Fourteen generic Akt mappings remained isoform-ambiguous;
two methods described PKD screening rather than an established AKT1 counter-screen.
The latter two observations were also censored. All37 native values and210
requested target ledger rows were retained.

| Diagnostic | Calibration | Development |
|---|---:|---:|
| Requested rows |18|19|
| Exact supported rows |16|5|
| Supported components |1|1|
| Supported coverage |88.9%|26.3%|
| Mean-baseline MAE in pIC50 |0.470805|0.929223|
| Frozen Ridge MAE in pIC50 |0.543839|1.168317|
| Supported positives at pIC50 >=6 |7|0|
| Top20% row budget |4|1|
| Ridge positive hits |0|0|

**Do not promote this model:** both supported MAEs were worse than the mean
baseline, and calibration recovered no supported positives at the fixed budget.
The baseline calibration tie-expected hit count was1.75 (recall0.25), not an
observed random draw. Development recall/AP are undefined because its supported
subset contained no positives. Full-request recall is unavailable because
excluded labels are not assumed negative. Each supported role contains only one
component; these observations do not establish broad generalization.

These are database-curated experimental IC50 values, not independently confirmed
primary compound tables, harmonized assay conditions, potential energy, docking
poses or residence time. The primary abstract of
[PMID15801821](https://pubmed.ncbi.nlm.nih.gov/15801821/) supports experimental
fluorescence-enzyme validation of Akt1 inhibitors; the paper's docking title is
not a reason to turn its experimental assay records into computed labels.
[PMID15686884](https://pubmed.ncbi.nlm.nih.gov/15686884/) distinguishes Akt1/Akt2
inhibition. Neither abstract proves per-record numerical/chemical identity.

Method capture CLI:exit0,wall27.996452s,CPU27.985389s,peakRSS1,295,600KiB.
Evaluation CLI:exit0,wall40.909493s,CPU40.901197s,peakRSS1,805,404KiB.
Earlier intake+fit:wall61.590543s. Combined core workflow wall130.496488s excludes
acquisition, census, human/assistant method review and tests. These are individual
CPU observations; there is no p50/p95, GPU, cache/batch comparison or engine
acceleration claim.

Fresh synthetic controls reproduce the legacy method-ledger rewrite rejection,
exercise both new CLIs and cover bad frozen predictions, rehashed captures,
body access order, role/coverage/source review tampering, shared-assay bridges,
zero/censored/missing observations and unknown-method denominators. Existing
regressions remain unchanged. Actual evidence separately checks all37 native
unit/log/relation conversions, both role metrics, complete ledgers and unchanged
model/predictions/context.

Local evidence root:
`/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-bindingdb-postfreeze-6orrtz6r`.
Raw sources remain separately hash-bound; this is not a portable public data
distribution. User WIP, protected holdouts, Fresh128 and one-use qualification
remain untouched. Scientific validation, performance qualification, independent
review and customer execution approval remain absent.
