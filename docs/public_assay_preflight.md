# Joint identity preflight

Run before molecular preparation or source role assignment:

```sh
python -m betelgeuze_product.public_assay_preflight --context context.jsonl.gz --context-sha256 SHA256 --candidates candidates.json --candidates-sha256 SHA256 --output preflight.json
```

The context is plain or gzip JSONL identity metadata; candidates are a JSON array of the existing public assay identity node schema. Exact bytes of both inputs must match their supplied SHA-256. All candidates participate jointly, including blocked and incomplete candidates. Duplicate IDs and nonmetadata fields are rejected by the shared validator. Existing output is never overwritten.

A clear result only covers the supplied snapshot. It is not rights clearance, source verification, chemical-state validation, or preparation qualification. Every admission flag remains false. Candidates sharing a component must retain their shared source role; individual candidate screens are insufficient when candidates bridge to reserved context. No experimental values are read or emitted.

This command adds a metadata-only entry point. Existing dataset intake already builds the full identity graph before selection.

The implementation is included in the main wheel under `betelgeuze_product`. The old `tools.product` imports remain compatible in source checkouts; installed execution does not require `tools`.
