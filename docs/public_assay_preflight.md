# Joint identity preflight

Run before molecular preparation or source role assignment:

```sh
python -m betelgeuze_product.public_assay_preflight --context context.jsonl.gz --context-sha256 SHA256 --candidates candidates.json --candidates-sha256 SHA256 --output preflight.json
```

The context is plain or gzip JSONL identity metadata; candidates are a JSON array of the existing public assay identity node schema. Exact bytes of both inputs must match their supplied SHA-256. All candidates participate jointly, including blocked and incomplete candidates. Duplicate IDs and nonmetadata fields are rejected by the shared validator. Existing output is never overwritten.

A clear result only covers the supplied snapshot. It is not rights clearance, source verification, chemical-state validation, or preparation qualification. Every admission flag remains false. Candidates sharing a component must retain their shared source role; individual candidate screens are insufficient when candidates bridge to reserved context. No experimental values are read or emitted.

For a public ZIP containing candidate CSVs, build the candidate nodes from
only the ID and SMILES columns before examining assay values:

```sh
python -m tools.product.build_public_source_identity_nodes \
  --manifest source-identity-manifest.json \
  --manifest-sha256 SHA256 \
  --output candidates.json
```

The manifest declares one frozen archive and the CSV members selected for
screening. Its schema is:

```json
{
  "schema_version": "public_source_csv_identity_manifest_v1",
  "archive": {"path": "/absolute/path/to/source.zip", "sha256": "SHA256"},
  "document": {"doi": "10.xxxx/example", "pmid": ""},
  "members": [
    {"name": "SI/series.csv", "sha256": "SHA256",
     "id_column": "name", "smiles_column": "smiles"}
  ]
}
```

The builder verifies the manifest, archive, and each member hash, rejects
malformed or duplicate identities, and projects every declared row. It never
emits source ID cells or assay columns. CSVs with policy or provenance columns
need a separate intake that preserves those declarations. Inventory all
relevant members separately: the builder does not prove that a declaration
covers the full paper or that its DOI is correct. It retains the declared DOI
as a conservative graph key but marks document identity incomplete until an
independent source audit. Its node array remains preflight input; no result
grants fit, calibration, evaluation, or prepared status.

The preflight command adds a metadata-only entry point. Existing dataset intake already builds the full identity graph before selection.

The implementation is included in the main wheel under `betelgeuze_product`. The old `tools.product` imports remain compatible in source checkouts; installed execution does not require `tools`.

To explain a preflight component using only these same frozen metadata nodes:

```sh
python -m betelgeuze_product.public_assay_graph_diagnostic \
  --context context.jsonl.gz --context-sha256 SHA256 \
  --candidates candidates.json --candidates-sha256 SHA256 \
  --preflight preflight.json --preflight-sha256 SHA256 \
  --output typed-witness.json
```

The preflight file is optional; when supplied, its exact bytes are hash checked
and its statuses must equal the current authoritative preflight recomputation.
The diagnostic reports direct overlaps by typed key, separately from shortest
paths through other nodes to reserved or unknown policy declarations. A path
search that reaches its resource limit says `incomplete_resource_cap`; it never
claims no boundary. Input and implementation hashes are included. The graph
is limited to supplied metadata, and the diagnostic cannot grant clearance.
