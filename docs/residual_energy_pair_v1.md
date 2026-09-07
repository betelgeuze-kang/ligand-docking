# Residual potential-energy pair ingestion

This development-data path is used by
`tools.product.build_residual_production_supervised_dataset`. It does not run
molecular calculations, acquire experimental data, authenticate source programs,
train on a holdout, validate physical dynamics or promote a model.

## Separate three kinds of values

A Stage3 absolute binding/solvation/forcefield proxy is not a residual. A loose
`(target, ligand_id)` join has no pose identity. Unique loose associations are
retained only in `stage3_energy_proxy_value` and related diagnostic columns.
Duplicate Stage3 join keys are excluded rather than resolved by file order.
Neither these proxies nor their absolute values populate `delta_energy` or
`refine_tier_label`.

The existing `reference_binding_kcal_mol - composite_score` label remains
available for legacy **diagnostic score-candidate** training. It is explicitly
marked `legacy_reference_minus_composite_proxy_not_physical_energy` and its source
is an unverified local label. No equality of those scales, experimental origin,
calibrated binding energy or transferability is asserted.

A potential-energy residual is computed as `reference.value - baseline.value`
only after the checks below. Supplied delta values are never trusted.

## Input format

Stage5 CSV rows may include an `energy_pair_json` column containing one JSON
object with `schema_version: residual_potential_energy_pair_v1` and two objects,
`baseline` and `reference`. Duplicate JSON keys are rejected.

The Stage5 row and each observation must have identical nonempty strings for
`target`, `ligand_id`, `pose_id`, and identical 64-character lowercase hexadecimal
SHA-256 declarations for:

- `coordinate_sha256`: the same coordinate snapshot;
- `atom_order_sha256`: the same ordered atoms/identity correspondence;
- `chemical_state_sha256`: the same topology/protonation/chemical state;
- `environment_sha256`: the same box, boundary, restraints and other relevant conditions.

Each observation additionally requires:

| Field | Accepted content |
| --- | --- |
| `status` | `observed`, never `predicted` or `not_run` |
| `evidence_kind` | `computed` or `synthetic`; both sides must use the same kind |
| `energy_kind` | `potential_energy` |
| `unit` | `kcal/mol`; this version does not convert units |
| `value` | finite JSON number, not a string or boolean |
| `source_sha256` | source record's declared SHA-256 |
| `run_id`, `model_id` | nonempty strings identifying the actual calculation |

Model IDs may differ because different methods are being compared. Coordinates,
atom order, chemical state, environment and energy kind must not differ.
An experiment reporting Ki, Kd or IC50 is not a potential-energy observation and
must use a separately specified experimental-label workflow.

## What these checks establish

`energy_pair_status: declared_identity_matched` means that supplied identities,
units, status and values passed structural checks. It does **not** establish that
these declarations are truthful, that the files identified by the hashes exist,
or that the two methods implement appropriate comparable physics. Hash
canonicalization for the coordinate/state records is the producer's contract;
this loader does not infer, align, reorder or regenerate those objects.

Every accepted pair carries a canonical JSON digest and separate baseline,
reference and derived residual values. `physical_energy_residual_validated`
remains false. Invalid pairs produce a specific rejection reason and an empty
energy target while retaining an otherwise valid score row. No force vectors or
uncertainty targets are manufactured.

Materialized rows retain the original Stage5 file SHA-256 and source line.
The reader snapshots one Stage5 file into memory to bind parsing to those exact
bytes; that file-sized memory cost is not claimed to be a throughput optimization.
Original source files must be retained for reconstruction.

## Development-only status and migration

`score_candidate_dataset_ready` reports only the existing count/class/target
minimums. `production_supervised_dataset_ready` remains false. The status becomes
`residual_score_candidate_dataset_ready` (or its blocked counterpart). Consumers
must not reinterpret this as production, physical or independent validation.
The feature inventory no longer calls `role` an inference feature.

Rows explicitly marked test, holdout, blind, validation/val or Fresh-128 in
`role`, `split` or `dataset_split`, or with `evaluation_only=true`, are excluded
and recorded in source rejection counts. This is not a detector for undeclared
holdouts or chemical duplicates under different IDs. Protected evaluation data
must remain outside development inputs and access controls.

Use explicit development paths and new output filenames when materializing:

```bash
python -m tools.product.build_residual_production_supervised_dataset \
  --stage5-glob '/path/to/development/*stage5_ranking_rows.csv' \
  --out-csv /path/to/output/candidate_dataset.csv \
  --out-json /path/to/output/candidate_dataset.json \
  --out-md /path/to/output/candidate_dataset.md
```

The existing candidate trainer can consume the resulting CSV directly; its
force, calibrated uncertainty and production readiness remain false. Synthetic
end-to-end tests exercise this ingestion-to-training connection. They are not
measured docking performance, experimental evidence or trained production weights.
