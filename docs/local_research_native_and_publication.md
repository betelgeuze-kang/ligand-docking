# Local native diagnostics and finalized result receipts

This extends the existing local research workflow from #518/#519. It reuses
bounded assay CSV inference, real prepared CPU rigid evaluation, the source-bound
completion journal, and offline report verification. It does not add another
engine, train a model, authorize product ranking, or make prepared cross physics
interchangeable with native fixed64 docking.

## Actual execution versus capability detection

The existing `--diagnose-only --probe-rocm` observes Torch's HIP tensor path in
an isolated process. It says nothing about the native fixed64 provider. The new
explicit diagnostic calls the existing `NativeFixed64CliAdapter.run` v3 owner,
without changing its admission, backend, source, receipt, or authority rules:

```bash
python -m betelgeuze_product.local_research_workflow \
  --diagnose-native \
  --native-request /absolute/path/to/admitted-test-native-v3.json \
  --native-sha256 EXACT_SHA256_OF_THOSE_BYTES \
  --native-backend hip_safe \
  --native-device 0 \
  --native-timeout 30
```

Supply an already admitted **test-only** native v3 request, `consumer=cli`, with
exactly the backend and device requested on the command line. This interface
never constructs molecular authority, creates qualification receipts, supplies
fake signatures, executes reserved examples, or rewrites a request to pass a
check. The native owner may reject it. `hip_safe` retains its existing build and
runtime restrictions; this change does not broaden any supported device list.
`cpp_cpu_reference` and `rust_cpu` are explicit alternative diagnostics, not
fallbacks. D0's CPU-only rule is unchanged; this interface does not call D0.

The file is read once through a bounded regular-file descriptor and matched to
the caller's SHA-256. Only that snapshot is passed to the child. The child loads
a compiled native v3 extension, invokes the existing owner, and returns a small
receipt with all denominator counts and backend identity. The extension bytes
are hashed before and after. Raw child output, molecular payloads, private paths
and exception messages are not printed. No engine is loaded into the parent.

The receipt's `device_ordinal_requested` is input, not a measured device identity.
A completed native pipeline preserves all 64 slots, including typed failures;
completion does not mean that all slots scored or that valid poses were found.
`native_backend_qualified`, `parity_measured`, `scientifically_validated`,
`customer_execution`, `model_promoted`, and
`prepared_physics_backend_changed` remain false. A successful native diagnostic
is not energy/force parity or permission to relabel prepared CPU work as HIP.

The child deadline is 0.1–120 seconds after spawn, default 30. Timeout, abort,
invalid receipts and missing compiled providers return explicit failure without
CPU fallback. The process group is killed and the child reaped on cancellation
as well. An OS process in uninterruptible sleep is not a hard-real-time bound.
Requests are capped at 4 MiB and receipts at 64 KiB; a receipt file-size limit and
disabled core dumps constrain the worker. There is no arbitrary command or
library-path option. Large inputs must use the owning native API, not raise this
diagnostic's bounds silently.

## Final publication

Each new research attempt now writes `complete.json` *last*, after `report.json`,
HTML, and numeric artifacts have been written and synced. It binds the final
report bytes and complete input/source binding bytes with SHA-256. The report
in turn binds every artifact, including the offline HTML. This catches an
accidental change to a pose energy, ID, timing or source hash in the small report,
not just changes to the large result files.

```bash
python -m betelgeuze_product.local_research_workflow \
  --verify-run --run-dir /absolute/private/run
```

This reads no model, original molecule or SQLite journal and runs no calculation.
For a modern report, a missing last marker means **incomplete**, not success.
Corruption, duplicate JSON keys, unsafe links and mismatched attempt/source/report
bindings are rejected. Interrupted publication is never silently repaired; a
resume makes a new attempt using the existing source-bound journal. An intact
partial/blocked result retains that original status.

True legacy reports without a publication policy or marker remain readable but
return `summary_receipt_verified=false`. Modern reports whose policy disappears
while the marker remains are invalid. These are corruption checks, not signatures:
a same-user owner able to rewrite receipts and data can forge both. Verification
does not grant source authenticity, scientific correctness, or resume permission.

Source-bound journals remain bound. Prior runs must resume with their original
implementation/environment or start a new run. No model or old journal is
migrated or resealed by this change.

## Validation scope

CPU CI uses fresh synthetic molecules and the real prepared/streaming consumers.
Protocol stubs test native dispatch and the *actual* native receipt-owner checks;
they do not execute a GPU. The real isolated child in CPU CI confirms that a
missing compiled provider is rejected, not replaced by Python or CPU work.
Actual AMD/native execution, numeric parity, MD, public benchmarks, model training
and customer qualification require separate authorized environments and evidence.
