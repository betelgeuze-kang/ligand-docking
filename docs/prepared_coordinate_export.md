The coordinate exporter writes explicit receptor and ligand XYZ arrays into
new PDB, SDF and GRO files while retaining the parent's chemical records. It
creates the derived-input provenance introduced in `prepared_coordinate_derivation.md`.
It does not calculate new positions, add atoms, change charges or execute a solver.

Run `python -m betelgeuze_engine.product.prepared_coordinate_export --request
/absolute/export-request.json --output-dir /absolute/new-output-directory`.
The destination must not exist. The CLI returns 0 on completion and 2 on failure.
An existing directory and all original source files remain untouched. A late
validation failure can leave diagnostic files, but no completed
`prepared-input.json` manifest is emitted.

The request contains exactly `schema_version=prepared_coordinate_export_request_v1`,
`parent_input`, `source_declarations`, `coordinates_angstrom`, and `upstream_method`.
The inline parent is an existing v1/v2/v3 GROMACS prepared request. Only its
prepared state ID changes in the new source declarations; frame, parameter and
charge declarations remain equal.

`coordinates_angstrom` contains exactly `receptor` and `ligand`, each an explicit
list of XYZ triples in the parent's atom order. Counts must match exactly. Units
are Å; Boolean, nonnumeric, nonfinite and field-overflow values are rejected.
The arrays must already contain every atom. There is no fitting, registration,
interpolation, topology editing or generation of missing coordinates.

`upstream_method` contains exactly `tool` (`name` and `version`), `operation`,
nonempty `settings`, `evidence` (`method`, `execution`, `model` file references),
and the Boolean `external_solver_called` declaration. These describe the source
of the supplied arrays. The exporter retains upstream settings separately from
its own implementation hash and formatting/roundtrip evidence. Tool execution
is a declaration, not independently authenticated by this input contract.

| Source field | Written precision | Operation |
|---|---|---|
| PDB XYZ | 8-character fields, 3 decimals in Å | Replace only atom coordinate columns |
| SDF V2000 XYZ | 10-character fields, 4 decimals in Å | Replace only atom coordinate columns |
| GRO XYZ | 10 decimals in nm | Divide explicit Å arrays by 10; replace coordinate tokens |

Decimal checks require each formatted value to be within half a printed unit of
the supplied binary64 number. Fixed-width overflow is rejected instead of
truncated. The report additionally records the maximum component error after
re-reading the numeric text in Å, including GRO unit conversion. GRO positions
are synchronized from the ligand array while the original GRO header, atom
identity prefix and box are preserved. The derived reader retains its existing
GRO/SDF consistency limit.

Change indices describe the coordinates actually written, after rounding. If
all changes disappear at output precision, the exporter rejects the request.
The complete derived reader then checks source hashes, unchanged noncoordinate
bytes, atom/parameter correspondence, lineage and actual change indices before
the export request, report and prepared-input manifest are written. Downstream
scoring therefore receives the written state, not the higher-precision supplied
arrays. The original arrays are retained in `export-request.json` for audit.

Validation uses the exact sorted-key JSON representation emitted in
`prepared-input.json`. The returned prepared document uses that same ordering.
Consequently, changing the insertion order of otherwise identical upstream
evidence dictionaries does not change exported system hashes, and the report's
hashes match re-reading the manifest. Caller input dictionaries are not mutated.
This correction is at the writer boundary; the legacy derivation reader and
the meaning of previously stored prepared-input files are unchanged.

The completed output contains `derived.pdb`, `derived.sdf`, `derived.gro`,
`export-request.json`, `export-report.json` and `prepared-input.json`. Passing
this software contract does not establish acceptable geometry, force-field
accuracy, minimizer convergence, experiment linkage, training admission or
scientific qualification. Original numerical failures and any new diagnostic
states remain separate evidence.
