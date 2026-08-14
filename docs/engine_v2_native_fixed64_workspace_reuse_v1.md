# Engine V2 native fixed64 workspace reuse v1

This contract removes repeated coordinate-buffer allocation from prepared
fixed64 v2 CPU sessions without changing the scientific pipeline. The opaque
`bg_docking_fixed64_pipeline_v2` handle owns 26 reusable `double` buffers: 3
producer channels, 12 rigid-refinement channels, 8 torsion channels, and 3
final-coordinate channels. Each run zero-fills all 26 buffers before executing
the producer, so a failed or inactive row cannot observe state from a previous
run.

The public ABI remains 1.21. The public handle is still incomplete, no public
structure or run signature changes, and workspace identity, capacity, and run
counters never enter a scientific receipt. Repeating the same admitted input
on the same handle must return a byte-identical result and receipt graph. This
is buffer reuse, not a scientific-result cache.

Because `run` mutates handle-owned workspace, calls that use or destroy the
same v2 handle require external synchronization. Independent handles may run
concurrently. Rust and Python prepared-session wrappers remain `!Send` and
`!Sync`/unsendable, respectively.

The native internal test poisons every workspace buffer between identical runs,
proves every result is byte-identical, proves all 26 data pointers remain
stable, and proves the logical capacity-growth count remains one. It also
proves top-level, component-output, and alias preflight failures leave an
unprovisioned workspace untouched. These are structural allocation checks
only; they do not authorize or assert a product performance claim.

The canonical and vendored native sources must remain byte-identical. The
machine-readable policy is
`config/engine_v2_native_fixed64_workspace_reuse_v1.json`; its verifier is
`tools/verify_engine_v2_native_fixed64_workspace_reuse_v1.py`.

All authority remains false. External authority must reach blocker zero before
reservation, molecular A/B, D1/D2 molecular execution, Fresh-128, a public
benchmark, HIP device execution, Stage 0 admission, or any product/scientific
claim. The consumed native fixed64 CPU v7 qualification is never rerun by this
contract or its CI.
