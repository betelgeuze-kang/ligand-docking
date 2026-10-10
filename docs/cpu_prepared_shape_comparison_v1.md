# Prepared parent-shape comparison v1

This is an opt-in development comparison, not a scientific result, candidate
selector, customer execution route, or default change. No archived protocol is
migrated. All existing numerical, source-bound and P2 files remain unchanged.

## Scope and binding

The new sibling package joins P1 prepared source admission and frozen 40/80/160
step controls to the unchanged ShapeProfile and Cartesian executor. Its thin
`minimize_shape` and `verify_shape` wrappers are new APIs: the original shape APIs
still enforce four steps and 17 objective attempts. Changing those APIs, adding
files to their source-manifest directories, or monkeypatching their admission is
not part of this implementation.

`prepare` consumes an already sealed P1 L-BFGS protocol, then seals the exact
protocol bytes, immutable original-parent reference, atom/topology/provenance
identity, source closures including P2, and all four arms. P1 prepared source and
geometry admission remains force-free. Comparison v1 permits no restarts. The
underlying executor and shape profile retain their independently tested restart
mechanisms; comparison v1 does not expose resume or replay unknown work.

- B0: original coordinates, zero optimizer dispatches, one separately charged base
  evaluation, followed by separately reserved P2 diagnostics
- B1: L-BFGS with shape strength 0; no restraint calls or floating point zero
  additions to the base energy/force
- B2: the same L-BFGS controls with shape strength 100
- B3: the same controls with shape strength 1000

Strength units are kcal/mol/angstrom-squared, coordinates angstrom, energy
kcal/mol and force kcal/mol/angstrom. Lower energy is only the selected model's
objective, not a calibrated affinity score. Raw and augmented stationarity,
internal-energy gate and shape penalties remain separately visible. Shape does
not enforce chirality or establish scientific validity.

The actual optimizer-base-call ceiling per optimized arm is bounded by the same
objective-attempt ceiling, `1 + 4 * accepted_steps`: 161, 321 or 641. Graph failures
can consume objective attempts without consuming base force calls. Early
termination and accepted-step exhaustion can leave the call ceiling unspent.
Equal ceilings do not imply equal consumed work. No padding calls are performed.

## Execution, accounting and storage

Each output directory must be new. Creation uses P2's private, exclusive,
no-follow held-directory-descriptor storage. Solver journals keep their existing
locking and durability. Unknown interrupted work is never retried; an existing
comparison output cannot be resumed or overwritten. A process-killing event can
leave no final report: `binding.json` still declares all four planned arms and
started reservations retain uncertainty. It is invalid to treat absent finished
receipts as zero work or rerun in a fresh directory without new authorization.

Each arm stays in the report denominator, including failed solver results and
missing/unknown work. `with_verified_result` means a retained result was verified;
it does not mean convergence, gate success or diagnostic success. Failed base
calls, successful base calls followed by shape failure, restraint calls, B0
single-point work and diagnostic arithmetic have distinct counters. Unknown
actual base totals are null; known completed lower bounds remain visible.
Diagnostic internal evaluator calls are counted, but internal gradient counts
are explicitly not instrumented. P2 cross block/gradient counts are retained.

`verify` authenticates the caller-retained completion digest, report digest,
artifact inventory and available arm results. It replays without force work.
It can verify a failure-inclusive report; this does not turn missing or unknown
work into completed evidence. P2 verifies retained shape sidecars; B0 uses a
separately bound single-point diagnostic sidecar.

Phase wall/CPU measurements include prepared-input validation, geometry
validation, per-arm evaluation/execution, replay, diagnostics, diagnostic
verification, storage inventory and report publication. Solver times are nested
and must not be added again. CPU measurement is current-process CPU, not child
CPU. Logical bytes are measured; physical allocation and storage I/O traffic are
not instrumented. The final completion receipt cannot durably measure its own
write. Historical chemical preparation costs are unavailable, not zero.

The outer supervisor must capture prepare/run/verify process wall, user/system
CPU, peak RSS, exit status and complete output footprint, including receipt
publication. Outer totals and inner phase totals are overlapping views, not
additive costs. Prepare's storage cost receipt is observational; only preparation
phase costs included in the sealed plan are bound by its digest.

## Bounded validation and later execution gate

Local tests use analytic objectives only, BaseException sentinels on molecular
entry points, a process-total dispatch budget, and one CPU thread. They do not
qualify molecular science. A five-minute external timeout bounds the synthetic
suite. Frozen source byte equality is checked separately.

No real comparison is authorized by this document. Before any real run, require
implementation review, applicable CI, an approved input/model and an external
supervision receipt. Proposed first run: one prepared input, 40-step tier, zero
restarts, at most 484 base evaluations including B0, at most 322 shape evaluations,
and at most five unique P2 diagnostic observations per optimized arm plus B0.
No automatic escalation to 80/160 steps, re-preparation, extra inputs, alternate
models or replacement failed arms.

### External supervision recipe

Use a dedicated subprocess/process group and predeclare the exact Python module,
plan digest, output path and environment. Set Torch/OMP/MKL/OpenBLAS threads to
one. Apply a kernel CPU limit of 2700 seconds and an external 2700-second wall
watchdog to the entire comparison process group; record termination signal and
exit status. Use an isolated filesystem quota of 1 GiB for the output directory.
A file-size limit alone is not an aggregate disk quota. If no enforceable quota
is available, the proposed hard storage cap is not established and the real run
must remain blocked pending an approved alternative.

Per-arm ten-minute hard execution limits additionally require a supervisor-aware
arm process boundary; the current single-process comparison API does not provide
that boundary. Therefore the original proposal's per-arm hard cap is not yet
implemented. Before real execution, either add a reviewed supervisor/arm boundary
or explicitly approve a bounded whole-comparison-only cap. Never claim polling,
phase timing or an outer timeout proves an unimplemented per-arm limit.

Test the supervisor with sleeping, CPU-burning and quota-exceeding dummy children,
never with a molecular optimizer. Confirm process-group termination, measured
child CPU, retained partial files, nonzero status, and refusal to retry unknown
reservations. Save the verified supervisor configuration and results alongside
outer cost receipts. A SIGKILL or CPU/quota termination may leave a pending
objective/diagnostic reservation; its actual work remains unknown and is not
reissued.
