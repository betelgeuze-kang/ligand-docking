# Native ChEMBL fit intake, version 3

The API intake could normalize native-exported rows at module level, but the
full trainer rejected that output before fitting. The native adapter now builds
and revalidates a complete fit intake through the existing ChEMBL normalizer and
`train_public_chembl_selector` consumer. It does not implement another molecular
engine or an interaction residual.

## Inputs and preservation

`python -m tools.product.public_chembl_native_intake --manifest PATH
--manifest-sha256 SHA --output-dir NEW_DIRECTORY` accepts a
`native_chembl_sqlite_fit_intake_manifest_v1` manifest. Each input is bound by
path and SHA256: native release extraction receipt, full target activity and
linked assay/document metadata, complete endpoint selection inventory, original
context, original reservation plan and assignment observations, reserved
context, method evidence files, and executed SQL export plans/observations.
These are SQLite exports, not synthetic API request/response receipts.

The adapter replays the original full-component split: descending component
size, SHA256(`seed:component_id`) tie order, then fixed 70/15/15 row deficits.
It verifies the metadata selection from the full graph and linked metadata;
preserves the original context followed by exactly the original role
observation nodes; and checks that the resulting reserved components match the
original assignments. Native activity and assay documents can differ: their
full union is retained. Extra unreferenced documents are rejected.

Duplicate IDs, changed source bytes, wrong metadata associations, undeclared
SQL projections, cache admission changes, and fit exports containing reserved
IDs fail closed. The role and method checks run before the outcome file is
opened. Method content is allowed only for preassigned fit assays in this
version. Unknown methods remain unknown; their rows and role denominators are
retained. The original raw metadata, native observation, role assignment and
source records are carried in the output.

The numerical policy reuses `normalized_record`, chemical identity,
`public_assay_components`, `public_chembl_measurement`, and `residual_evidence`.
IC50 censoring, nulls and data-quality flags remain explicit. Coordinates,
atom order, physical environment, energy residual and force labels are not
manufactured from these catalogue observations.

## Actual measured-data integration (2026-09-09)

The local ChEMBL 37 snapshot contains 10,321 target catalogue metadata rows,
including 3,930 IC50 rows. Before content access, 257 rows were assigned as
fit 180, calibration 39, development 38. The original plan SHA256 is
`55c5c05ddf5fb181c625964d2cd96274d5f429b86874b835e00818447c639f2a`.

The full native CLI processed all 257 assignments and retained the full 3,930
row inventory. It consumed only the already acquired 57 fit observations:
31 exact supported candidates and 26 excluded observations; 200 assigned
observations remained unread. This includes all 77 reserved observations.
All 31 eligible candidates belong to one original component. The actual
existing trainer successfully revalidated the native intake and then refused
with `insufficient_supported_fit_rows_or_components`. No new public-data fit,
checkpoint or scientific-quality result was produced. Its minimum of two
components was not weakened.

The 57 observations come from three method-assessed fit documents. The
chemical scope remains heavy atoms 5–70, one fragment, the previously declared
elements, no isotopes and no radicals. The eight macrocyclic peptide rows are
outside that scope. Another new observation is censored (`>98,000 nM`).
Neither inclusion scope nor censoring was changed to increase training size.

## Checkpoint and execution boundaries

Native checkpoints use `public_chembl_cheap_selector_ridge_v3` and explicitly
bind `intake_source_kind=native_chembl_sqlite_release_v1`. Fixed Morgan features,
Ridge alpha 10, weighting, minimum cohort size, and complete pre-evaluation
prediction freezing reuse the existing trainer. Fresh synthetic integration
tests execute this full fit/save/reload/predict route.

Producer implementation hashes change with this implementation. Historical
v1/v2 checkpoints continue to require their original pinned source runtime;
they are not made compatible by rewriting hashes or relabelling schemas. No
historical public model is retrained or migrated here. Product shadow serving
is not promoted to accept v3 by this change.

Native evaluation captures are **not implemented** in this initial adapter.
An evaluation request fails explicitly before reading any native evaluation
source. API evaluation remains on its existing path. A native evaluation
adapter must bind a genuine frozen model and complete pre-label predictions
before future reserved content/observations may be opened. Consequently this
change does not establish end-to-end native evaluation or product readiness.

## Validation and limitations

New controls cover full CLI/synthetic fitting, unknown methods, original split
replay, reserved outcome access order, duplicate exports, query/metadata/source
tampering, rehashed cache changes, separate assay document provenance, and
explicit evaluation refusal. Existing API, BindingDB, measurement, identity,
and learning controls are retained in the same CI job. CI uses synthetic
fixtures; it does not download the public development snapshot or execute a
protected qualification protocol.

Actual local evidence resides outside the dirty user checkout under
`engine-v2-native-fit-adapter-95x8mfsz` on the data volume; the run report binds
source hashes, commands, raw logs, JUnit, environment and cost. The first actual
attempt exposed a document-union mismatch; it was corrected by preserving the
assay-referenced document and adding positive/negative synthetic controls.
Failures are retained in the evidence record.

This work does not measure engine speedup, pose/active recovery, calibrated
uncertainty, physical-state equivalence or independent scientific validation.
The fitted synthetic control is not a real experimental training result.
Public-data training still needs additional supported independent fit data;
native evaluation and product routing remain subsequent work.
