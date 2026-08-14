# Engine V2 native fixed64 bounded prepared-input v3

## Status

`native_fixed64_complete_pipeline_v3` is the canonical synthetic/test-only
Python transport for the Rust-owned fixed64 pipeline. It replaces v2 for the
CLI, diagnostic benchmark, Python API, and product-shadow adapters without
changing the native 64-slot scientific pipeline. The v2 entrypoint remains
available only for receipt-compatible historical callers; v1 remains retired.

This transport creates no reservation, molecular-execution, public-benchmark,
product-rank, customer-pose, scientific-claim, or production-claim authority.
It does not execute a HIP device and does not establish HIP parity.

The machine-readable limits and authority boundary are frozen in
`config/engine_v2_native_fixed64_bounded_input_v3.json`. The authoritative
release-candidate CI runs
`tools/verify_engine_v2_native_fixed64_bounded_input_v3.py` to bind that
contract to the Rust bridge, Python consumer, and this document.

## Allocation-before-parse boundary

Before a Python sequence is copied into a Rust `Vec`, v3 enforces:

- ligand atoms in `[1, 512]`;
- receptor atoms in `[1, 4096]`;
- exact, length-bounded top-level and nested dictionary key schemas before key
  strings are copied into Rust-owned sets;
- the exact Cartesian receptor--ligand pair denominator no larger than
  `512 * 4096`;
- at most 24 V7 control sources, seven conformer sources, and four retained
  sources, each with exactly the bounded ligand atom count;
- topology row capacities derived from the bounded ligand/receptor atom or
  ligand-pair denominator;
- at most 3,072 atomic-feature rows and 4,096 atom indices per feature row;
- exactly 64 candidate modes, rigid budgets, torsion eligibility values, and
  torsion budgets, plus exactly `64 * ligand_atom_count` baseline torsion
  values;
- a global ceiling of 8,388,608 prepared-input scalar payload values;
- exact booleans and integers where required, finite numeric values, and
  explicit rejection of Python booleans in numeric/integer positions.

The native pipeline rechecks its own semantic and ABI capacities after this
transport preflight. A preflight pass is therefore not scientific admission;
it only proves that Python-owned transport cannot cause an unbounded native
allocation.

## Native prepared-input receipt

Rust computes
`prepared_input_projection_sha256` over a domain-separated, field-ordered
binary encoding of the bounded prepared coordinates, atom parameters,
topology, source inventories, feature geometries, pocket, backend identity,
fixed64 refinement inputs, policies, and derived cardinalities. It does not use
Python JSON serialization. Consumer identity is deliberately excluded because
it is a presentation authority, not scientific prepared input.

Rust then derives:

```text
SHA-256(
  "betelgeuze.engine-v2.native-fixed64-prepared-input-receipt/v1\\0"
  || prepared_input_projection_sha256
  || pipeline_batch_receipt_sha256
)
```

as `prepared_input_receipt_sha256`. The Python facade independently rederives
this outer binding and rejects a cross-wired projection/pipeline pair. The four
consumer surfaces must therefore share both prepared-input and pipeline
receipts while retaining four domain-separated consumer-view receipts.

## Compatibility and promotion boundary

The v3 evidence schema is
`betelgeuze.engine_v2_native_fixed64_complete_python_evidence/3.0.0`.
It adds the bounded-prepared-input flag, projection and outer receipt, exact
Cartesian pair count, and observed/maximum scalar counts. The underlying
candidate denominator, proposal/admission/refinement/ScorerV1/validity/ranking/
clustering receipt graph, authority bits, and v2 historical evidence remain
unchanged.

This implementation may be used for synthetic CPU development and wheel
verification only. External authority must reach blocker zero before any
reservation, molecular A/B, D1/D2 molecular run, Fresh-128, public benchmark,
or HIP device execution is attempted.
