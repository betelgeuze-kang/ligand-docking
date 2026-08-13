# Engine V2 native fixed64 context lease v1

## Status and boundary

`betelgeuze-runtime::Fixed64Pipeline` owns a private `Rc<ContextInner>` lease
on the exact native context that created its two native pipeline handles. The
public `Context` wrapper may therefore leave scope before the pipeline while
the native context remains live. The last lease destroys the context exactly
once, after each pipeline has explicitly destroyed its fixed64 and geometric
admission handles.

This is a synthetic native CPU development boundary. It creates no
reservation, molecular execution, historical A/B, D1/D2 execution,
Fresh-128, public benchmark, Stage 0 admission, product performance claim,
qualification rerun, or HIP device-execution authority.
External authority must reach blocker zero before any gated execution is
attempted.

The machine-readable contract is
`config/engine_v2_native_fixed64_context_lease_v1.json`. Its independent
verifier is `tools/verify_engine_v2_native_fixed64_context_lease_v1.py`.

## Ownership and drop order

The Rust safe layer enforces the following order:

1. `Context::new` creates one non-null native context and wraps it in
   `Rc<ContextInner>`.
2. `Fixed64Pipeline::new` validates the scientific inputs, creates both native
   handles, and clones the exact context lease into the resulting pipeline.
3. Native constructors deep-copy the scientific channels; the caller's input
   slices remain ordinary borrowed constructor inputs and are not retained.
4. Every pipeline run uses the handle from its private context lease.
5. `Fixed64Pipeline::drop` destroys the fixed64 pipeline handle and replay
   admission handle before Rust drops the lease field.
6. Only the last `ContextInner` lease destroys the native context.

Both `Context` and `Fixed64Pipeline` remain `!Send` and `!Sync`. A single
context may create multiple pipelines on its owning thread, and each pipeline
keeps that context alive independently.

## Verification

Native integration tests exercise both `cpp_cpu_reference` and `rust_cpu`.
They run a complete 64-slot receipt after the public wrapper has already been
dropped, verify deterministic repeated receipts, and exercise multiple
pipelines sharing the same context with staggered destruction. Compile-fail
documentation tests preserve the thread-confinement contract.

The verifier also binds the JSON policy to the Rust owner, constructor, run,
drop implementation, integration-test names, and this document. It fails
closed on duplicate JSON keys, non-canonical JSON, authority drift, lifecycle
drift, or missing source bindings.
