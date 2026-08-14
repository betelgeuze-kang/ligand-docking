# Engine V2 native fixed64 prepared session v1

## Status and boundary

`native_fixed64_prepare_session_v1` converts one bounded v3 Python transport
document into Rust-owned input, creates one native context and one
`Fixed64Pipeline`, and returns a thread-confined
`NativeFixed64PreparedSessionV1`. Repeated session calls reuse that exact
native pipeline while executing proposal, admission, refinement, ScorerV1,
validity, stable ranking, and clustering again for all 64 slots. Scientific results are not cached.

This is synthetic native CPU development only. It grants no reservation,
molecular execution, historical A/B, D1/D2 execution, Fresh-128, public
benchmark, qualification rerun, Stage 0 admission, product performance claim,
or HIP device-execution authority. External authority must reach blocker zero
before any gated execution is attempted.

The machine-readable contract is
`config/engine_v2_native_fixed64_prepared_session_v1.json`. Its independent
verifier is
`tools/verify_engine_v2_native_fixed64_prepared_session_v1.py`.

## Preparation and ownership

The v3 top-level key schema and every nested cardinality are checked before
Python-owned sequences are copied. The admitted values are converted into one
`OwnedCompletePipelineInput`; the caller's mappings and lists are never
retained. Mutating them after preparation cannot alter the session.

The session owns:

1. the bounded Rust input and exact prepared-input projection;
2. one `Fixed64Pipeline`, including its private `Rc<ContextInner>` lease; and
3. a content receipt equal to SHA-256 of the prepared-session v1 domain, the
   length-prefixed fixed64 pipeline profile ID, and the prepared-input
   projection.

The class is deliberately `!Send` and `!Sync`. PyO3's `unsendable` guard
confines construction, execution, and destruction to the creating Python
thread, matching the native ABI synchronization contract. The stateless v3
entrypoint continues to release the GIL around a one-shot construction and
run through the same Rust-owned input parser. Prepared-session v1 accepts only
`cpp_cpu_reference` and `rust_cpu`; both HIP backend identifiers fail before a
native context is created. Rust field order destroys the native pipeline and
its context lease before dropping the owned prepared input.

## Repeated execution and evidence

`run()` accepts `cli`, `benchmark`, `api`, or `product_shadow`. Consumer
identity remains outside the prepared scientific projection. Therefore all
four views share the same pipeline and prepared-input receipts, while each
consumer-view receipt stays domain-separated. Product shadow retains only its
pre-existing operator second-opinion permission; automatic rank change,
customer pose emission, and production claim permissions remain false.

Every call executes the full scientific pipeline again. No result, rank,
failure, or run counter is fed into the next call, and no run count enters a
scientific receipt. The immutable session description records only prepared
content, fixed cardinalities, lifecycle facts, and false authority fields.

## Verification

Native integration tests compare repeated session executions to the stateless
v3 result, exercise all four consumer surfaces, verify 64-slot denominator and
receipt identity, and mutate the original Python input after preparation to
prove Rust ownership. The verifier binds the canonical JSON contract to the
Rust owner/parser, Python factory and evidence checks, tests, and this document.
It fails closed on duplicate JSON keys, non-canonical JSON, authority drift,
lifecycle drift, or missing source bindings.
