# Binding a saved prepared cross report to its input files

Run this verifier after a `prepared_gromacs_components_v3` request has produced a
saved `prepared_cross_interaction_report_v1` or `v2`. Keep the request, report,
and every prepared PDB/SDF/GRO/ITP and parameter file at their declared paths.

```sh
python3 -B -m tools.product.verify_prepared_cross_report_binding \
  --request saved-request.json --report saved-report.json \
  --output new-binding-check.json
```

The output path must be new. Exit 0 requires all requested cases to have been
evaluated and bound; exit 2 records a failed binding. The verifier checks the
exact request hash in the report, the current consumer source hash, all prepared
file hashes through the v3 reader, and the reader's postflight source checks.
It rebuilds the canonical receptor and ligand from those files and compares
their full serialized coordinates, atom metadata, source identities, and
nonbonded parameters with the saved report. It also compares the preparation
provenance, declared model, pocket, source declarations, case order, and
denominator. A preserved system hash beside a changed coordinate tensor or
charge row fails. The CLI rehashes the request, report, and every prepared file
again immediately before a passing result. It does not call the energy kernel.

Run `tools.product.verify_prepared_cross_numerics` separately on the saved
report for the independent scalar energy, force, and pair comparison. A passing
binding check does not imply a passing numerical check, and either check can
fail without changing the other result. To associate the two receipts, compare
this verifier's `report_sha256` with the scalar check's `input_sha256`; they
must be identical.

The v3 request's `source_relationship` and state IDs are caller statements.
They do not map prepared atoms to an original mmCIF structure. This verifier
does not accept an added origin-authentication claim in the saved report and
always returns `original_structure_lineage_verified=false` and
`source_declarations_verified=false`. For 9G4S/A1III, an independently
prepared file set and a separate, reviewed source-atom lineage and component
treatment receipt are still needed. The unresolved 9G4S decision manifest is
unchanged; no chemistry, assay state, physical validity, training permission,
or scientific qualification is established here.
