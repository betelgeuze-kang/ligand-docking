# Local research delivery checks

The development workflow composes the existing prepared rigid-pose CPU consumer,
its transactional completion journal, optional bounded assay shadow predictions,
and private per-attempt reports. It does not run new docking search, MD, train a
model, combine assay values with physical energy, or authorize customer use.
The underlying prepared evaluator still rejects HIP requests; a Torch-HIP probe
is not permission to relabel this different CPU calculation.

## Run and resume

Use an existing `local_research_workflow_request_v1` request. Create a **new**
private directory for a new run:

```bash
python -m betelgeuze_product.local_research_workflow \
  --request request.json --run-dir ./private-run
python -m betelgeuze_product.local_research_workflow \
  --request request.json --run-dir ./private-run --resume
```

Completed successes and failures are restored by the existing journal. Interrupted
uncommitted rows are recomputed. Shadow inference is rerun in bounded batches.
No input, checkpoint, numerical environment or source mismatch is waived.
This code changes the source binding: use the original code/environment to
resume an older run, or begin a new run. Never reseal an old journal to make a
new source version appear identical.

## Isolated ROCm observation

```bash
python -m betelgeuze_product.local_research_workflow --diagnose-only
python -m betelgeuze_product.local_research_workflow --diagnose-only --probe-rocm
```

The first command is metadata-only and imports no engine/ML runtime. The optional
probe now uses a separate, fixed worker process. Only its anonymous receipt file
is inherited; workflow locks and source descriptors are not. Child stdout/stderr
are discarded rather than leaking raw runtime exceptions or filling a pipe.
The small JSON receipt is size/schema checked, and successful Torch arithmetic
still leaves `native_backend_qualified=false` and `scientifically_validated=false`.
CPU/NVIDIA Torch is never reported as HIP.

The default wait timeout is 30 seconds (Python helper range 0.1–120 seconds).
Timeout, native abort, missing runtime, malformed receipt and unavailable device
are distinct observations. The process group is killed and the child reaped on
timeout/interruption; cancellation itself is not swallowed. OS process creation
or uninterruptible kernel sleep cannot be given an absolute deadline: a child
that cannot be reaped promptly is explicitly marked pending. A diagnostic failure
does not discard independent successful CPU physics. No arbitrary worker command,
shared library or external solver is accepted from the request.

Real AMD/native execution and performance still require the supported hardware
and existing provider qualification lane. A stub-child test is not that evidence.

## Verify saved output without recalculation

```bash
python -m betelgeuze_product.local_research_workflow \
  --verify-run --run-dir ./private-run
python -m betelgeuze_product.local_research_workflow \
  --verify-run --run-dir ./private-run --attempt 1
```

Verification takes a nonblocking shared lock, opens the owned private directories,
and uses relative no-follow file descriptors. It never creates a lock, repairs
files, opens the journal database, loads a checkpoint or performs calculations.
Original inputs may be offline. It validates bounded strict JSON receipts, request
identity, backend/claim limits, candidate denominators and referenced artifact
names/sizes/SHA-256 bytes. Large physics/assay files are hashed in 64-KiB blocks,
not parsed into memory. Receipts are limited to 1 MiB (request) and 2 MiB (report).
Symlinks, nonregular files, hard links, path traversal and replacement during
reading are rejected. Verification is about declared artifacts, not arbitrary
unreferenced files in the folder or the journal's independent resume eligibility.

The default is the latest attempt, including an interrupted one. It does not hide
an incomplete latest attempt by choosing an older success. A complete partial or
blocked calculation can be `intact`; `workflow_status` and `workflow_exit_code`
retain the original failure/unsupported status. Verifier exit 0 means local
receipts and declared output agree, **not** that the research succeeded.

New reports publish HTML before final report JSON and bind the HTML digest too.
An interrupted publication remains incomplete. Older #518 reports can be checked
but explicitly return `html_verified=false` when they have no HTML digest.

These local hashes detect accidental corruption and inconsistent receipts, not
hostile owner forgery. Verification is not a signature, source authentication,
scientific validation, GPU qualification, or authorization to resume/migrate a run.

## Validation scope

Tests use freshly generated synthetic molecules and fixture checkpoints. They
include real CPU evaluation, bounded shadow predictions, resume, output byte
changes, bad counters/paths, descriptor-pinned rename controls, fresh CLI reading
without ML imports, and real child timeout/abort/descendant cleanup. Existing
owning tests remain in the CI selection. No protected/public evaluation dataset,
real assay training, AMD device, MD or commercial/customer claim is introduced.
