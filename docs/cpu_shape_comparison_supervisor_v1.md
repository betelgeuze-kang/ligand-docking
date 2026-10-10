# Source-bound per-arm comparison supervision

This additive helper leaves the approved P3 package, protocol, numerical closures,
and defaults unchanged. It is a development execution boundary, not authorization
for real molecular work or scientific promotion.

## One-shot worker boundary

The production command launches a fresh process group for each predeclared arm
B0/B1/B2/B3. Only the fixed installed worker module is admitted; requests cannot
supply arbitrary commands, executables or Python callbacks. Requests bind exact
helper source hashes, P3 plan digest, arm and resource controls. Workers re-admit
P3 sources/reference and require the 40-step, zero-restart tier. All molecular
execution and diagnostics stay in that worker. No worker is resumed or retried.

The parent durably writes the arm request and started reservation before spawn.
The worker installs Linux parent-death SIGKILL protection, checks the parent PID
race, and installs kernel CPU/file/core limits before workload imports. These
worker limits start inside launch after Python and the helper's standard-library
bootstrap. That pre-install runtime startup is trusted and is not sandboxed;
it performs bounded request/source reads and has no intended output beyond small
stderr. The parent process-group wall watchdog covers startup. The logical-write
guarantee requires this reviewed trusted-runtime bootstrap; it does not claim
to bound hostile site hooks, runtime startup or unaudited native writes. Standard
`platform.platform()` metadata is resolved before installing the scientific-work
child-process ban: frozen provenance may lazily invoke the standard uname helper.
The fixed PATH is /usr/bin:/bin. This bootstrap is covered by the process-group
wall watchdog and kernel limits; it is not molecular execution. All subsequent
Python subprocess/fork/exec attempts are denied.

Each worker gets a new session/process group. The supervising parent kills the
whole group on wall timeout or an exception while waiting. Parent death kills the
worker directly; no descendants are permitted during arm execution. A Linux
wait4 call provides that specific worker's user CPU, system CPU and peak RSS,
without cumulative-child accounting. Worker phase clocks provide nested detail.
Retained stderr is separately bounded and included in artifact inventory.

An exit without a validated worker result is `failed_or_unknown`, even when some
files exist. Neither silence nor a partial result means zero work. Started
objective/diagnostic reservations remain untouched. Existing arm directories
cannot be reused. A killed supervising parent may leave no final report; its
binding and per-arm started reservations remain authoritative about planned work.
The full four-arm denominator is declared before any worker starts.

The worker verifies completed P3 results/sidecars before returning. Available
results can later be replayed force-free with `verify_supervised_arm`. Process completion, unknown base work and unknown diagnostics have separate
flags. A normally exiting worker can still retain unknown scientific work. A
completed process/result receipt is not a claim of convergence, energy-gate success,
complete diagnostics, or scientific qualification. Failed arms remain visible.

## CPU and wall controls

Default worker wall and nominal kernel CPU limits are 600 seconds each. The
CLI whole-parent wall watchdog is 2700 seconds and covers parent setup, waiting,
inventory and publication. Its timeout kills/reaps an active worker group while
retaining reservations. Separately, total_wall_seconds is a worker-scheduling
allowance; a later worker receives no more than its remaining allowance. The production CLI separately applies a 300-second soft kernel
CPU limit with explicit default SIGXCPU termination to its parent process. Its
inherited hard ceiling stays at 600 seconds so workers can set their own
600/600 limit without privileges. The nominal parent plus four worker CPU budget
is therefore 2700 seconds. Kernel scheduling/accounting granularity can produce
small termination overshoot; these are not sub-millisecond deadlines.

The CPU limit applies to the worker process and its threads. The arm phase has no
permitted child processes. Standard runtime metadata bootstrap may briefly run
uname; this is a trusted bootstrap exception, not a general process-tree or
cgroup CPU sandbox. Per-PID wait4 accounting includes the runtime's reported
usage; no extra precision beyond Linux accounting is claimed.

Calls to the Python API from an existing process do not automatically impose
the CLI parent's kernel CPU limit or whole-parent wall watchdog; the API's
total_wall_seconds alone is a scheduling allowance. The main-thread wall_deadline
context is tested separately and rejects a preexisting alarm. Use the dedicated CLI process for the proposed real execution,
and retain its outer wall/user/system CPU/exit-status receipt. Kernel limit
support is Linux-specific and fails closed when unavailable.

## Storage: explicit alternative to a filesystem quota

This environment has no privileged quota mount. Instead, the helper proves a
conservative bound on regular-file logical payload bytes for its trusted Python
writers. The default policy has these limits (the explicit research opt-in is
described below):

- Kernel RLIMIT_FSIZE: at most 2 MiB per worker-written regular file
- At most 120 monotonic write/link reservations per optimized arm
- At most 16 such reservations for B0
- Reopening an existing file and publishing a hard link both consume tokens
- Tokens are charged before the operation and never refunded on failure/unlink
- The inherited bounded stderr file consumes the first token
- Each worker also permits at most 16 directory creations
- Parent control/receipt files are individually capped at 256 KiB; the fixed
  four-arm source creates fewer than the conservative 64-file allowance

The aggregate upper bound is (3 × 120 + 16) × 2 MiB + 64 × 256 KiB = 768 MiB,
leaving headroom below the originally proposed 1 GiB. No polling-based disk
check is presented as a hard bound. Kernel file limits and pre-operation audit
reservations stop single-file and many-file growth. Partial files are retained.

This is explicitly a trusted-source Python audit contract, not a sandbox against
malicious native code, direct native syscalls, runtime tampering or an untrusted
Python installation. Molecular reference code uses reviewed Python/os file
writers; arbitrary plugins and worker executables are not admitted. Filesystem
metadata, block-allocation overhead, source inputs and unrelated environment
files are outside the logical-payload bound. Physical quota compliance is not
claimed. The bound is an alternative that must be accepted in the final run plan,
not silently substituted for a promised physical filesystem quota.

Storage reservations can exhaust before the objective-attempt ceiling. All
optimized arms have the same resource controls; exhaustion is an explicit
resource failure, not convergence or a replacement reason. No padding calls or
replacement runs are performed. Actual completed and unknown computation remains
separate in the retained P3 evidence.

## Validation and scope

A distinct source-bound `synthetic_control` lane admits prepared plans only when
P3 preflight explicitly says synthetic_control. It blocks molecular evaluation
entry points, installs bounded analytic objective and retained-diagnostic mocks,
uses the real P3 executor/journal/verification, and restores patches afterward.
The production CLI exposes no synthetic switch. Synthetic evidence cannot be
promoted into real preparation/scientific evidence.

Tests exercise completed worker collection and replay, CPU/wall termination,
parent death, file growth, many-file growth, forbidden descendants, tampering,
no retry, and actual P3 single-arm plus four-arm subprocess workflows with
analytic arithmetic. No real molecular execution is part of these tests.

Before any real run: independently review this helper and its trusted-writer
boundary, accept the exact storage alternative and limits, freeze input/model and
source digests, retain whole-process cost receipts, and authorize one bounded
run. Historical chemical preparation costs remain unavailable when absent from
sealed inputs. Existing P3 claim boundaries and diagnostic limitations remain.

## Explicit research storage policy

The default remains 120 write/link reservations per optimized arm and 2 MiB per
file (768 MiB aggregate logical payload with B0 and parent receipts). The CLI
option `--resource-policy research_161` explicitly admits 360 reservations per
optimized arm and 8 MiB per file. B0 remains limited to 16 reservations. Parent
receipts remain at most 64 files of 256 KiB. Research aggregate logical payload:

`(3 * 360 + 16) * 8 MiB + 64 * 256 KiB = 8784 MiB = 8.578125 GiB`.

This pre-result change addresses prospective serialization headroom, not an
observed comparison outcome. A complete optimized arm uses `2*A + 2*K + 25`
write/link tokens at A objective attempts and K selected diagnostic records,
including bounded stderr and its final worker receipt. Thus 161 attempts and
five records require 357 tokens, leaving three of 360. B0 uses 15 of 16. An
embedded worker storage snapshot precedes its final two publication tokens.
The 8 MiB cap is a hard file bound, not a promise that every trajectory fits.
CPU, wall, restart, objective, scientific and failure policies are unchanged.

Before creating any comparison output, the research comparison route checks
`f_bavail * f_frsize` through a no-follow descriptor for the output parent. It
requires the declared aggregate logical bound plus 1 GiB of free headroom:
9.578125 GiB at the full research limits. The binding records the observed
available bytes, filesystem device and threshold. Insufficient space rejects
admission before workers or output files. This is a point-in-time observation,
not exclusive disk reservation, preallocation, physical quota or a guarantee
against concurrent consumers; later ENOSPC remains a failure and never permits
retry or changing policy mid-run. The low-level single-arm API retains its
per-worker caps; whole-comparison free-space admission applies through the
comparison entry points and CLI.

A new policy must be bound in request/receipt identities, independently reviewed
and pass hosted CI before real execution. Limits above the default require the
explicit research policy name; unknown policies and ceilings above 360/8 MiB are
rejected. No result-driven tuning or automatic enlargement is admitted.

Worker artifact inventory/replay has an 8 MiB read ceiling so a research journal
above 2 MiB can still be collected and verified. The selected kernel file limit
and source-bound supervisor inventory still enforce 2 MiB for the default policy;
raising a read ceiling does not raise that default write allowance. Frozen P3
journal limits and evidence semantics are unchanged.
The newly created output directory's device identity is rechecked against the
admission observation before any receipt or worker dispatch. A changed output
filesystem rejects execution and may leave only the empty reservation directory.
