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
an evaluator. This preparation cache covers only PoseBusters decoding of the
native/receptor RDKit molecules within the same Engine V2 worker. It does not
share docking preparation, partial charges or search contexts across cases or
engine processes. A full Top5 result-cache hit skips the second decode entirely,
so it need not produce a prepared-input cache hit. A sink failure is explicit and
prevents publication of a successful
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

### Corrected cloud execution

The corrected source revision is
`16980a83cd425994bdb596077785ebe3a96542a6` (tree
`fa82392f58eaf47f347ce04ca1b1a0ae9b3b35cd`), executed in
[run 41697499611](https://github.com/betelgeuze-kang/ligand-docking/actions/runs/41697499611).
This execution identity remains distinct from later documentation-only commits.

Admission passed **350 tests with 3 optional Rust-native tests skipped**, including
the required real PoseBusters cache-equivalence test. The fresh paired gate passed
in GitHub Actions, and independent re-analysis of the downloaded sealed evidence
reproduced the original paired report exactly. The full installed environment
snapshots were byte-identical before and after admission.

All six case/engine scientific comparisons were exact. Engine V2 comparisons
covered both complete 64-candidate rows, every retained binary64 result and all ten
selected SDF record hashes. Each P1 case verified 261 coordinate snapshots across
four complete 64-candidate stages and five selected poses. One evaluation batch
evaluated the 64 candidates; all five final Top5 records were reused. No
prepared-input cache hit occurred. These checks establish equivalence for the
two tested pairs, not for every possible molecular input.

| Case | Legacy Engine V2 worker wall | P1 worker wall | Observed change |
| --- | ---: | ---: | ---: |
| 5SAK_ZRY | 160.1885 s | 152.8553 s | -7.3332 s (-4.58%) |
| 5SB2_1K2 | 94.9716 s | 93.1936 s | -1.7780 s (-1.87%) |

These are one paired observation per case, including journal and observation
overhead. They do not establish a general speedup. P1 diagnostic evaluation still
took 114.6847 s and 40.4088 s respectively. The narrower reported Engine V2 runtime
was 31.5431 s and 46.1734 s; it must not be substituted for whole-worker wall time.

The admission inner archive verified 1,555 payload files and 1,556 total members.
Its SHA256 is
`2e1eb135d5ba5d656396d3fb2ccfb8e95731754ecaacc3a4b04fdc9106dcd0a0`;
the original downloaded GitHub artifact SHA256 is
`137f6ca8e304fcf5f560aa04267da553062767285779274ddd24c8b7fbe77fe5`.

### Development32

All four development shards and the aggregate job completed successfully. The
original aggregate records `execution_complete=true`,
`scientific_accuracy_complete=true`, 32 attempted cases, zero missing cases,
the four exact shard selections, and complete environment verification. All
five nodes share one verified environment content identity. This completeness
means every expected engine outcome is observed, including typed scientific
failures; it is not a statement that every docking pose is correct.

Every accuracy denominator remains **32**. A valid recovery requires both RMSD
at most 2 Å and the existing geometric/chemical validity checks.

| Engine | Successful / typed failure / unobserved rows | Valid Top1 | Valid Top3 | Valid Top5 |
| --- | ---: | ---: | ---: | ---: |
| Engine V2 | 29 / 3 / 0 | 1/32 (3.125%) | 3/32 (9.375%) | 3/32 (9.375%) |
| Vina mode | 30 / 2 / 0 | 17/32 (53.125%) | 24/32 (75.000%) | 24/32 (75.000%) |
| GNINA mode | 30 / 2 / 0 | 19/32 (59.375%) | 24/32 (75.000%) | 25/32 (78.125%) |

Engine V2 retains 1,856 successful candidate records and 76 jointly valid
candidates. Its RMSD-only oracle is 6/32; the valid oracle is 3/32. These values
do not demonstrate an accuracy improvement. Preparation fails for `6M73_FNR`,
`6YJA_2BA` and `6YR2_T1C` with `unsupported_large_ring_system`. Vina/GNINA each
retain four actual output poses for `6M73_FNR` and `6YR2_T1C`, below the strict
five-pose contract. These remain explicit failures; they are not padded or
removed from the denominator. In total, 96 engine outcomes
are observed: 89 successful receipts and seven typed failures.

The former wholly unobserved case `6YSP_PAL` now has all three results:

| Engine | Worker wall | Limit | Top1 RMSD |
| --- | ---: | ---: | ---: |
| Engine V2 | 858.5021 s | 900 s | 3.962985 Å |
| Vina mode | 89.7164 s | 420 s | 0.396530 Å |
| GNINA mode | 90.3602 s | 420 s | 0.396530 Å |

Engine V2 spent 815.6659 s in the observed PoseBusters stage, approximately 95.01%
of its worker wall, compared with 25.0708 s in search/refinement. Its narrower
reported runtime was only 36.5057 s. V6 and V7 timings nest inside search and are
not additional disjoint costs. The previous shared case timeout and the new
independent engine budgets differ, and the environment also differs; the recovered
observation cannot be attributed to cache reuse alone.

There were **no actual timeouts in this rerun**. Controller journals confirm normal
Engine V2 completion followed by Vina and GNINA. Timeout cleanup and continuation
remain covered by the passing process/controller isolation tests, not by an
observed timeout in this molecular cohort.

Independent offline re-aggregation reproduces all raw case data, accuracy counts
and other aggregate fields. Native Python 3.12 re-aggregation initially differed
in the last bits of two operational time sums, by less than 1e-12 s. Python 3.12
[changed floating-point `sum`](https://docs.python.org/3.12/library/functions.html#sum).
Explicit ordered binary64 additions reproduce the original Python 3.10 sums
exactly from unchanged per-case terms. Both reports and the initial diagnostic
failure are retained; no numerical tolerance or scientific-field exclusion is
introduced. Candidate coordinates, scores, RMSD values and validity remain under
exact comparison.

### Independent evidence checks and findings

All 29 successful Engine V2 rows passed complete lineage and cache verification:
1,856 candidate bindings, 145 ranked pose bindings and 7,569 coordinate snapshots.
Actual counters reconcile with 29 evaluation batches, 1,856 cached candidate
records and **145 reused Top5 records**. Prepared-input cache hits remain zero.
The three typed preparation failures have zero actual candidates and are outside
the successful-lineage proof, while remaining in the fixed32 accuracy denominator.

The separate operational audit verified all 32 materialization workers and 96
engine workers, 128 actual input files, 384 worker/input-role hash comparisons,
256 log files and 160 journals. It found no unfinished stages, checkpoint lag,
workers with observed results but incomplete operations, or retained pinned aliases. The successful
89 scientific receipts bind their actual Top5 SDF records; seven typed failures
remain failures.

The slowest successful Engine V2 cases are dominated by pose evaluation:

| Case | Worker wall | PoseBusters stage | PoseBusters / worker wall |
| --- | ---: | ---: | ---: |
| 6YSP_PAL | 858.5021 s | 815.6659 s | 95.01% |
| 6XHT_V2V | 619.3534 s | 556.9668 s | 89.93% |
| 6TW5_9M2 | 510.6888 s | 451.6193 s | 88.43% |

Across the 29 successful cases, the median PoseBusters stage is 78.9885 s and the
median search/refinement stage is 26.5473 s. External workers have a separate
preparation cost: the median binary staging time is 9.3905 s for Vina mode and
9.4290 s for GNINA mode, plus observed runner import and evaluator initialization
stages. No binary-sharing optimization was introduced here.

| Engine V2 candidate property | Count / 1,856 |
| --- | ---: |
| Geometric valid | 85 |
| Chemical valid | 1,218 |
| Both valid | 76 |
| RMSD at most 2 Å | 11 |
| Both valid and RMSD at most 2 Å | 5 |

V7 penalty decreased for 1,843 candidates, but 1,767 of those final candidates
were still jointly invalid. The other 13 penalties increased and those candidates
were also invalid. The overlap proxy is therefore not a substitute for measured
pose validity. Its units and role remain distinct from physical energy/force or
calibrated binding affinity. Initial-pose PoseBusters validity was not measured,
so these observations do not establish that refinement improved or worsened
validity relative to its starting poses.

The five valid near-native candidates are at ranks 1 and 2 in `6T88_MWQ`, ranks 3
and 4 in `6YQW_82I`, and rank 3 in `6Z0R_Q4H`. The latter two cases identify Top1
ranking failures. No valid near-native candidate lies outside Top5 in this cohort.
Near-native but geometrically invalid candidates also occur in `6XM9_V55`,
`6YQV_8K2` and `6Z4N_Q7B`; they fail protein-distance/overlap checks despite chemical
validity. `6YSP_PAL` has 64 candidates, zero geometrically valid or near-native
candidates, and a best candidate RMSD of 2.560089 Å.

The evidence supports distinct next investigations: profile the expensive
PoseBusters internals before further evaluation optimization, test refinement
against the observed geometric failures, and isolate the two Top1 ranking
failures with fixed candidate sets. Those are follow-on experiments. This P0/P1
change does not tune scoring weights, change search mathematics or run a fresh
accuracy holdout.

### Historical comparison limits

Of the 93 engine outcomes observed in both the historical run and this run,
81 have exactly equal scientific projections under the comparison's declared
time/command/source-receipt exclusions. Twelve projections differ: Engine V2 and
GNINA for each of `6YQV_8K2`, `6YQW_82I`, `6YRV_PJ8`, `6YT6_PKE`, `6YYO_Q1K` and
`6Z0R_Q4H`, all from the historical/current shard starting at 18.

All 93 common rows have exactly equal status, failure code, output RMSD arrays,
geometric-validity arrays and chemical-validity arrays. Seven are typed failures
with empty pose-evaluation arrays; they are not counted as successful molecular
comparisons. Engine V2 differences include internal candidate coordinate/score/
refinement fields, while the GNINA projection differences are serialized pose
hashes. These differences remain explicit and are not waived as exact matches.
The historical comparison does not establish full bitwise reproducibility across
the two executions, and its differing environment/source/resource identities do
not isolate a cause. The same-node paired smoke gate remains the controlled P1
equivalence check.

The three newly observed rows are the Engine V2, Vina and GNINA results for
`6YSP_PAL`. Vina/GNINA each add one valid recovery through that newly observed
case; the Engine V2 recovery counts remain unchanged. This is improved outcome
coverage, without evidence of a changed scoring algorithm's accuracy.

### Source revision CI

The execution source revision also completed all **41 general CI workflows and
119 check runs successfully**, with no failed or cancelled checks in the final
2026-11-03 19:38 UTC general-CI snapshot. After the molecular workflow completed,
the 20:05 UTC check snapshot for that commit confirmed **125/125 checks successful**,
including admission, four development jobs and aggregation.
A later documentation-only head does not inherit a claim that its own checks
have already completed.

| Representative completed evidence | Outcome | Scope |
| --- | --- | --- |
| Frozen P0/P1 admission | 350 passed, 3 skipped | Actual Python 3.10.22/RDKit/PoseBusters environment; only optional Rust-native skips |
| [Engine V2 main, Python 3.11](https://github.com/betelgeuze-kang/ligand-docking/actions/runs/41697517112/job/126131853446) | 2,293 passed, 5 skipped | Full focused CPU suite, wheel build, clean install/pip check, and standalone execution outside checkout |
| [Top-stack complete suite](https://github.com/betelgeuze-kang/ligand-docking/actions/runs/41697516685/job/126132116136) | 2,256 passed, 1,226 skipped | 1,123 historical-evidence conditions, 100 unavailable optional native-extension cases, and 3 unavailable RDKit cases were skipped in this lane |
| [CPU refinement comparison, Python 3.12](https://github.com/betelgeuze-kang/ligand-docking/actions/runs/41697516743/job/126131850579) | 325 passed, 3 skipped | Reference/refinement regression and lint checks |
| [External oracle boundary](https://github.com/betelgeuze-kang/ligand-docking/actions/runs/41697517214/job/126131854073) | 149 + 59 passed | Boundary mutations, engine-free fixtures, actual Docker context, and oracle-free product/Engine V2 wheels |

The main suite and CPU-refinement workflow also completed successfully on their
other Python matrix entries. Counts above are representative recorded logs and
overlap with other suites; they must not be added into one unique-test total.
Conditional skips are not evidence for execution of the unavailable native paths.
The separate frozen admission gate supplies the actual RDKit/PoseBusters checks.

Focused local corrections recorded 44 passing relocation/binding tests,
66 historical-protocol tests and 23 source-verification tests. The completed
cloud log also preserves the structured Git timeout blocker and the historical
verifier's static-only receipt, both with execution authorization denied.

### Preserved first attempt and correction

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

The successful admission of the corrected run is reported above. The earlier
failed workflow and its original false gate remain separate evidence; offline
re-analysis does not change their recorded outcome.
