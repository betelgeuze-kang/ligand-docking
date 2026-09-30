# Prospective Cartesian failure diagnostics 1.4

The opt-in `betelgeuze_product.cpu_refinement_v1_4` runner preserves failure facts
before the existing Cartesian path reduces an exception to a retry class and
type. It adds a source-bound runner, durable journal payload, read-only consumer,
prepared-request API and CLI. It does not amend any historical result or recover
the missing reason of terminated R2 case `perturbed_03`.

The loss occurs in 1.3 `minimization._invoke`: `Exception` becomes `fatal` or
`retryable` plus a type name; the returned receipt has no original message or
throwing stage. The 1.3 kernel correctly terminates an initial failure, including
a retryable initial failure, as `evaluation_failed`; retryable trial failures
follow the existing bounded backtracking. The registered workflow subsequently
creates a generic minimization-failure row, so an outer wrapper cannot recover
the original evaluator exception. In 1.2, initial failure retains a Python cause
on its generic exception, while trial rejection discards the exception object.

## Opt-in identities and authority

The new runner reuses the exact 1.3 `SolverConfig`, `CartesianMachine`, observation
validator and `TrialJournal` storage. Configuration and solver-state schemas
remain 1.3. Diagnostic run bindings and result schemas are explicitly 1.4.
The source manifest includes the complete existing closure and all six new 1.4
modules, including the prepared workflow and CLI. A 1.3 journal cannot be opened
under a 1.4 binding. Existing 1.2/1.3 source and consumers are unchanged.

The journal's format remains its generic storage format, but 1.4 finished payloads
require `failure_detail` and `dispatch_outcome`. Both are inside the event hash
chain. Replay validates their relation to the corresponding authenticated intent,
replays the unchanged kernel transitions and compares checkpoints and any saved
terminal result. It never treats a diagnostic reason as authority to continue,
retry, select a pose, relax a force threshold or admit a new source.

The legacy work fields retain their meanings. In particular,
`known_completed_force_calls` means accounted finished force attempts and can
include an exception, rather than only successful returns. The new dispatch
summary separately records known attempts, normal graph/force returns, dispatch
errors, valid observations, failed objectives, restart mismatches and unfinished
reservations. A normal evaluator return followed by nonfinite observation
rejection is a failed objective with a normal force return. A normal restart
observation that differs from the accepted full observation is a verification
failure with a normal return; it gets the fixed
`restart_full_observation_mismatch` reason and has no invented exception message.
Counters in a returned prepared result are cumulative journal counters, not
invocation deltas. Timings remain nested and must not be summed.

## Private cause preservation

Each caught objective exception records `phase` (`initial`, `trial`, `resume`),
its execution `stage`, attempt and restart index, unchanged retry class, safe type,
typed reason, bounded cause-chain fingerprints and a detail seal. Stage distinguishes
coordinate decoding, state construction, graph building, evaluator execution,
post-evaluation integrity and observation validation.

For a valid UTF-8 message, SHA-256 and byte length cover exactly
`str(exc).encode('utf-8', errors='strict')`. No type prefix, truncation,
normalization or replacement occurs. Raw messages, arbitrary traceback paths,
source text and frame locals are not written. Known applicability reasons use an
exact trusted-message mapping and replay checks its complete message hash and byte
length. Other applicability messages retain the generic typed applicability
reason and their exact fingerprint; their physical cause is not inferred.

If string conversion, strict encoding or secondary diagnostic collection fails,
the message status and fixed secondary error code declare that failure and the
unavailable hash/length remain null. Diagnostic collection cannot replace the
original caught objective exception with an unfinished reservation. By contrast,
a real graph/evaluator `BaseException` still leaves its durable start unfinished:
actual force work is unknown and automatic retry remains forbidden. The pending
summary contains identifiers and the intent hash, without duplicating coordinates.

A source position is published only for a package-relative path present in the
bound source manifest, with matching file SHA and a real line within that file.
It is the deepest eligible frame, not necessarily the ultimate third-party
throw site. A stored fingerprint can authenticate a separately supplied original
message; it cannot reconstruct a missing message or independently prove the
truth of arbitrary hash-consistent fabricated history.

## Prepared-request API and CLI

For already instantiated complete numerical inputs, use 1.4 `minimize`,
`verify_run` and `inspect_run`. `inspect_run` also returns a sealed diagnostic
inspection for failed restart verification and unknown pending work. It does not
suppress malformed evidence or binding/source drift errors.

For an existing `cpu_cartesian_registered_pose_request/1.3.0` document:

- `workflow.audit_request(request)` checks the unchanged request structure and
  authenticates the five raw prepared JSON files and the complete source closure.
  Its scope is byte identity and JSON format only, with zero physics calls.
- `workflow.run_minimization(request, run_dir, resume=False, ...)` parses complete
  canonical inputs, enforces existing numerical guards and calls the actual 1.4
  minimizer and journal. The request SHA and audit receipt are bound to execution.
- `workflow.verify_run(request, run_dir)` authenticates and parses those inputs,
  replays the journal and checks the result without constructing a scorer or
  dispatching graph, force or score work. These are also exported as
  `audit_request`, `run_minimization` and `verify_prepared_run` at package level.

The numerical entry preserves bounded single-model nonperiodic CPU float64 input,
complete base/extension/cross parameters, ligand/receptor limits, unsupported
constraint rejection, pocket/cross coordinate-frame equality, the existing strain
cap and the request's unchanged force threshold. It is numerical-only: it does
not perform registered pose generation, docking validity/scoring comparison or
selection. Those existing workflow authorities are not replaced or bypassed.

`python -m betelgeuze_product.cpu_refinement_v1_4` exposes `audit`, `run`, `resume`
and `verify` subcommands with `--request`; execution and verification also require
`--run-dir`. A run is explicit opt-in prospective execution and requires separately
authorized inputs and endpoint/protocol decisions. CLI exit 0 means a returned
envelope; callers must inspect numerical status, convergence, pending work and
admission fields. It is not a claim of scientific success. Ordinary request/run
exceptions produce a fingerprint-only blocked envelope and exit 2. CLI
interruptions emit a safe interrupted envelope without finishing reservations:
KeyboardInterrupt exits 130, bounded integer SystemExit preserves its code and
other BaseException exits 2. Unknown work must be inspected before continuation.

The supported prepared backend remains `python_cpu_reference`. Existing native
v4 admission can produce that prepared Cartesian request format, but the installed
native v4 wrapper still statically imports 1.3 and is not automatically switched
to 1.4. No native protocol, source role, endpoint, packet, SRO qualification,
training admission or physics authority is promoted. Source-wheel installation
and independent-cwd CLI help/audit checks are separate root-owned verification.

## Software verification and retention

The focused tests use only synthetic request files, graph/evaluator/context
doubles and predetermined toy observations. They exercise the actual minimizer,
kernel, journal, prepared entry, CLI and read-only consumer. Coverage includes
SD/L-BFGS normal and resumed accepted histories/work versus 1.3, initial/trial/
resume applicability/nonfinite/unexpected failures, graph failures before force,
normal-return observation rejection, restart mismatch, private cause hashing,
bad `__str__`, surrogates, diagnostic failure fallback, source-position/reason
mutations, input binding/body/hash/frame/threshold tampering, old-journal rejection
and unfinished-reservation retry prohibition. CLI BaseException tests also verify
safe output and pending retention.

The final software QA is retained directly at:
`/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-cpu-refinement-v1-4-failure-diagnostics-software-qa-20260930-6347ca2e`.
Its `qa-receipt.json` binds raw test/lint logs, final source snapshots and before/
after source pins. This fresh permanent verification replaces unavailable temporary
QA evidence without reconstructing those missing files. No actual molecular target,
native dispatch, score, oracle or R2 rerun is part of these tests. Their outcome is
software-contract evidence only; independent arithmetic/physical validation and
operational adoption remain separate prospective work.
