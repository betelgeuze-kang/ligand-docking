# Redocking P0/P1: isolated execution and observable evaluation

This implementation follows the fixed smoke2/development32 baseline in run
[41651548827](https://github.com/betelgeuze-kang/ligand-docking/actions/runs/41651548827).
It is development evidence. It does not authorize execution of the fresh holdout
or claim an accuracy improvement. The prior baseline report remains unchanged.

## Execution changes

`tools/run_redocking_isolated_development.py` is a new, explicit-profile entrypoint.
It materializes and verifies one case, then runs Engine V2, Vina mode and GNINA
mode in separate processes. A timeout or typed failure in one engine does not
prevent the other engines from running. A cleanup failure stops the sequence.
The controller retains operational status separately from scientific receipts;
missing or invalid observations remain in the full case denominator.

Each worker has an independent wall limit: materialization 120 seconds, Engine
V2 900 seconds, Vina and GNINA 420 seconds each. The external executable's own
search timeout remains 300 seconds. The controller samples process-tree RSS
against 6 GiB, drains bounded stdout/stderr streams, and handles descendants that
create a separate session. This is observed process-tree supervision rather
than a cgroup memory guarantee. The configured outer job limits include cleanup,
installation, verification and upload time.

Worker journals commit immutable, hash-linked events before atomically replacing
the checkpoint. Requests, materialization hashes, source identity, fixed seed,
profile, actual evaluator identity and receipt hashes are connected. A supplied
job preflight must be ready and match the worker's newly observed evaluator and
source identities. An interrupted stage remains an observation; it does not
become a successful docking receipt.

## Optional P1 observation

The existing public runner keeps its default numerical path. The new
`development_observation_v1` profile observes the unchanged V7/ScorerV1 pipeline.
It records proposal generation, preparation, refinement, candidate serialization,
PoseBusters execution, report validation, Top5 serialization and receipt creation.
Copied binary64 coordinates identify proposal, post-V6, post-V7 optimization,
selected refinement and final ranked states. Native RMSD and PoseBusters labels
are evaluated after search and are not passed into search observers.

An evaluation result may be reused only for the same complete serialized pose
record, including title and rank, exact receptor/native bytes, evaluator identity
and evaluation policy. Incomplete batches and failed evaluations are not cached.
Reference molecules retained for preparation reuse are copied before exposure to
an evaluator. A sink failure is explicit and prevents publication of a successful
scientific receipt. Candidate denominator, score formula, weights, ranking rule,
seed and the five-pose success contract remain unchanged.

## Environment and upload evidence

Admission resolves the ordinary evaluator, test and installer packages together
with `torch==2.6.0+cpu`. PoseBusters is downloaded separately without dependencies
because this frozen protocol uses the `rdkit-pypi` distribution name. Every wheel,
version and SHA256 is frozen before molecular execution. All workers install the
same shared wheel bundle into a fresh Python 3.10.22 venv, with hash requirements,
no dependency re-resolution and no bytecode compilation. The nine native GNINA
runtime wheels keep their existing hash requirements, isolated target and native
loader-only path; their wheel and installed library identities must match the
admission reference.

Only admission may create a reference. A development worker missing a reference
fails before docking. Start/end snapshots preserve raw installed-file inventories
and previous evaluator fingerprints. Content comparisons may explain validated
bytecode and installer bookkeeping differences, but cannot hide Python source,
native library, console-script, version or wheel changes. Interpreter/libpython
bytes and explicit source files are included. This does not claim identity of the
entire hosted runner image or hardware.

After all producers finish, evidence is sealed into one verified ZIP. Its internal
inventory includes hidden pinned inputs and must exactly match actual ZIP members.
Disposable staged external binaries are excluded explicitly. Actions uploads the
sealed ZIP, avoiding hidden-file omission by directory upload defaults.

## Validation protocol

The workflow `.github/workflows/redocking_p0_p1.yml` first runs focused P0/P1 tests
and default-path regressions in the frozen runtime. The real PoseBusters equivalence
test must execute; a skip does not satisfy admission.

On one node, case 0 runs legacy then P1, and case 1 runs P1 then legacy. Admission
compares complete Engine V2 scientific result dictionaries, including every one of
64 candidates, refinement evidence, all floating-point binary64 values, and Top5
pose hashes. Only operational timing and command path strings are excluded.
Lineage validation checks candidate identity, coordinates and final rank binding;
it is not just an event count. Each successful P1 smoke must reuse the five exact
Top5 evaluation records. Both external smoke executions must succeed with validated
input/evaluator/source identities; their numerical comparisons are reported
separately from the Engine V2 optimization gate.

After admission, four jobs execute the same 32 historical development cases in
fixed shards starting at 2, 10, 18 and 26. Aggregation verifies sealed ZIPs,
receipts, actual pose bytes, phase journals and environment comparisons, retaining
missing cases and engines in denominators. Fatal shard state and absent reference
comparisons prevent a complete classification. Nested stage timers are not
summed as disjoint costs.

The new independent engine deadlines change operational resource allocation from
the old shared 900-second case deadline. Any increase in observation coverage must
be reported separately from numerical accuracy. Same-node smoke timings are a
small engineering comparison, not a general performance claim.

## Historical protocol compatibility

The prior global-orientation protocol binds the exact 187-file Engine V2 Python
source manifest and the original public runner. Those historical identities and
the original protocol are unchanged. An explicit `--historical-snapshot` verifier
now checks the original bytes as static evidence and emits a distinct receipt
with `live_checkout_verified=false` and `execution_authorized=false`. Five changed
source files are retained as inert text; the other original files must still
match their frozen size and hash. The default verifier continues to reject the
old protocol against the newer executable sources. Archival verification never
imports the retained source or grants current execution authority.

Research-only stage, isolation, runtime and analysis tools are excluded explicitly
from the product Docker context and its import boundary. Separately, the existing
source-verification Git timeout now yields a structured verification blocker. Its
15-second bound, dirty-checkout rejection and refusal to authorize execution remain
in force.

## Validation results

The first cloud attempt was
[41692479481](https://github.com/betelgeuze-kang/ligand-docking/actions/runs/41692479481),
at commit `4e49ac1507c55709c11f4003d59c1ae371b45c1d`. Frozen-runtime tests recorded
**340 passed, 3 skipped, zero failures**; the three skips concern unavailable
Rust-native implementations. The required real PoseBusters reuse-equivalence test
ran successfully. All four paired molecular executions completed, but admission
failed in offline receipt validation because its relative analysis directory was
compared with the absolute output path recorded during execution. Development32
was therefore not started in this attempt.

The correction validates the original command against the separately hash-bound
worker request, while validating actual input and pose bytes at their retained
location. It supports both relative local paths and relocated evidence archives
without rewriting the original receipts. Focused regression tests passed 44/44,
including path, request, materialization and input tampering cases. Re-analysis of
the sealed original artifact with the corrected validator passed paired admission;
that diagnostic result is separate from the original failed workflow/gate.

All six case/engine scientific comparisons were exact, including both complete
64-candidate Engine V2 rows, every binary64 value and the ten selected SDF record
hashes. Each P1 Engine V2 run retained 261 coordinate snapshots and reused five
Top5 evaluation records after one 64-candidate evaluation. No prepared-input cache
hit occurred in these runs. The single-node environment was unchanged from start
to end. The sealed artifact verified 1,555 payload files and 1,556 total members,
with SHA256 `1a43e8de9843023ccfd3b99b9966a9ab4c765cd5ad1455f63b594d6c0e00f7ba`.

| Case | Legacy Engine V2 worker wall | P1 worker wall | Observed change |
| --- | ---: | ---: | ---: |
| 5SAK_ZRY | 160.9865 s | 152.2856 s | -8.7009 s (-5.40%) |
| 5SB2_1K2 | 95.2569 s | 94.1008 s | -1.1561 s (-1.21%) |

These are single paired observations, including observation and journal overhead,
and do not establish a general speedup. PoseBusters itself still occupied 114.5492 s
and 40.6016 s respectively. No scoring weights or accuracy outcome changed.

A new cloud attempt on the corrected revision is required before the 32-case
development stage can be considered validated. Its run identity, full-denominator
results, environment comparisons and remaining failures will be recorded here.
