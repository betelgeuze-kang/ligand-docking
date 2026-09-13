# Calculation coordinate arrays

The `prepared_gromacs_coordinate_array_v1` input supplies new calculation XYZs
from a hash-bound JSON file in the legacy parent's canonical atom order. It
retains finite binary64 Angstrom coordinates without the PDB/SDF decimal-place
limits. It does not change the existing text exporter or legacy input meaning.

Use the same `prepared_coordinate_export_request_v1` request documented in
`prepared_coordinate_export.md`, selecting the array writer explicitly:

```bash
python -m betelgeuze_engine.product.prepared_coordinate_array \
  --request /absolute/export-request.json \
  --output-dir /absolute/new-coordinate-array
```

The Python API is `export_prepared_coordinate_array(request, output_dir)`.
It returns a report and writes `coordinates.json`, `export-request.json`,
`export-report.json`, and finally `prepared-input.json`. The output directory
must not already exist. A late failure may leave diagnostic files, without a
completed report/input manifest. The reader never falls back to parent text
coordinates when the array is absent or invalid.

The array has schema `prepared_calculation_coordinate_array_v1`, explicit
`coordinate_unit="angstrom"`, `numeric_representation="binary64"`, and
`atom_order="parent_canonical_atom_index"`. It includes the canonical parent
input hash, both parent system hashes, and exactly one XYZ triple per atom in
`coordinates_angstrom.receptor` and `.ligand`. The exporter converts incoming
Python numbers to binary64 before writing; arbitrary integer/decimal precision
is not promised. It verifies bit-for-bit binary64 re-reading, including signed
zero. No unit conversion or fixed-decimal rounding is performed. The source
file and CLI request each have the existing 16 MiB byte limit.

The prepared input contains the inline legacy v1/v2/v3 parent, coordinate-array
file reference (`path`, `sha256`, `source_id`), new state declarations, and an
explicit `prepared_coordinate_array_record_v1` method record. The record binds
the parent and array hashes, prepared state, tool/version/settings, method,
execution and model evidence, and exact changed atom indices. Parameter,
charge-source and coordinate-frame declarations must match the parent; the
prepared-state ID must differ. At least one observed coordinate must change.
Nested derivations, new atoms, parameter edits and inferred atom mappings are
unsupported. Boolean/nonfinite values, wrong units/order/counts, duplicate
JSON keys and inconsistent parent hashes are rejected.

The parent supplies atom identity, chemical annotations and parameters; its
PDB/SDF/GRO files remain immutable source evidence. The authoritative new XYZ
source is explicitly `coordinate_array`. Parent GRO/SDF agreement observations
are nested under `parent_coordinate_observations`, rather than being presented
as checks of the array. Canonical system provenance binds the parent, array,
method record and new state. Source hashes are rechecked after ingestion and
remain visible to pose reuse and durable checkpoint integrity checks.

This is serialization and ingestion, not molecular preparation. No solver,
alignment, hydrogen generation or chemical normalization is performed. The
method's upstream execution flag remains a declaration, not authentication of
the stated calculation. Array source consistency and arithmetic agreement do
not establish minimization convergence, model validity, binding affinity or
training eligibility; all scientific and product qualification flags remain
false. Coordinate conversion by a caller before export (for example, nm to Å)
is outside the exact roundtrip guarantee and must be recorded separately.
