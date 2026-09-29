# Canonical normalization CPU cost and exact output preservation

Deferring diagnostic-path formatting reduces repeated CPU work while retaining
fresh canonical traversal and both molecular integrity digests. A controlled
four-state SRO comparison produced **identical full evaluation bytes** with mean
evaluation wall time **1.826910 s → 1.714064 s (6.18% lower)**. This is a small,
single-host fixed-state evaluation measurement, not a full workflow or service
latency result.

## Change and preserved semantics

`canonical_json_value` now constructs the diagnostic location when traversal
fails. Successful traversal still reads every field, mapping key/value, sequence
element and tensor value. Float tokens, signed zero, ordering, canonical bytes,
SHA identities, public exception type and diagnostic locations remain unchanged.
Dataclass output-key and diagnostic-name reads retain their original order even
when a getter or nested value changes the dataclass field descriptor.

The raw object-integrity digest and canonical digest are both calculated afresh
at every existing boundary. No object, tensor-version, metadata, file-size or
mtime cache is introduced. Cross evaluation entry/exit and final identity checks
remain. A new regression records the subtle case where adding a colliding
integer/string mapping key leaves the raw structural digest unchanged but must
still fail canonical validation. Direct tensor `.data`, NumPy-view and nested
metadata changes remain detectable.

Only the canonical normalizer changes in product source. Force equations,
parameters, score rules, acceptance limits, preparation and source reservations
are unchanged. The current native source manifest contains 224 files with digest
`d02bfc102851834e8c823ca0723ad23a34cc4e8ec2774fa29d51d24f96f1870d`.

## Measured scopes

| Scope | Baseline mean wall | Candidate mean wall | Observed decrease |
|---|---:|---:|---:|
| Canonical normalization of the retained receptor | 0.214526 s | 0.166467 s | 22.40% |
| Complete `FixedReceptorEnvironment.assert_intact` | 0.586296 s | 0.570948 s | 2.62% |
| SRO `FixedReceptorEvaluator.evaluate` | 1.826910 s | 1.714064 s | 6.18% |

The rows are separate scopes and must not be summed. Component measurements
are replayed calls after each enclosing guard, not instrumented subspans of that
guard. Its source checks cover the two normalizer implementations and receptor/
cross inputs, not the complete native manifest. The guard profile fixes two warmups per arm and eight alternating pairs; six of eight
guard pairs were faster. The raw integrity pass remains substantial and noisy.
An earlier pilot used a superseded source version and is retained separately;
the table uses the final source SHA
`5a697e413368137308076632437452a7fcb39a1e949f56ace14c749d271195b6`.

The evaluator comparison reuses the four already declared SRO coordinates. It
fixes one warmup per arm followed by two rounds through all four states, reversing
arm order by round/state. **18/18 attempts completed, zero failed; 16 are measured
evaluations and two are warmups.** Both implementations produced the same full
`ExtendedEvaluation` bytes, including forces, energies, component values,
provenance and evaluator fingerprints, for every state and repetition. All eight
measured pairs were faster with the candidate. The four historical states do not
constitute an independent pose or affinity evaluation set.

The control loads the exact normalizer source from commit
`031894211edb613a7659bd08aaab48d44f643f20`. Only that function is switched inside
the same surrounding product source/runtime. This is a controlled function
comparison, not a comparison of two installed releases. Input bytes are parsed
from the same reads used for their hashes and bound to the sealed SRO packet.
Code and inputs are fully hashed again after execution. Failed warmups or
measurements retain their attempted arm, state, phase and elapsed cost.

The enclosing comparison wrapper took 36.798 s before publication, with 4.957 s
setup; process wall time was 38.677 s. Timed evaluation excludes input preparation,
neighbor construction, output serialization, verification and storage. Those
costs are outside the per-arm measurement rather than assumed zero. Page cache,
allocator and external host contention are uncontrolled. No optimizer, training,
candidate search or OpenMM rerun was executed for this A/B comparison.
Independent post-run review also reproduced exact component energies and forces
from the sealed earlier SRO numerical record. One total differs by
1.77636e-15 kcal/mol from different addition grouping, below the unchanged 1e-8
limit; that historical comparison is distinct from the exact A/B full-byte check.

## Validation and integration

The focused differential, mapping-dispatch and receptor-boundary selection passed
87 tests. Independent review corrected dataclass read ordering and two benchmark
harness issues before execution. Existing negative cases and thresholds remain.

The first broader 29-file selection recorded 483 passes, one historical-source
view failure, 41 corresponding setup errors and three installed Rust ABI failures.
These failures are retained in the evidence packet. The historical test-only
source view now names the exact reviewed serializer bytes and complete current
187-file engine manifest. The old historical manifest and protocol seals are
unchanged; production verification still rejects the current source as that old
protocol, and mutation tests cover the newly named source file.

The final same 29-file selection passes **529 tests, zero failures, errors or
skips**, including all three Rust scorer comparison/failure/ranking cases. The
test-only historical mapping retains the old protocol/fixture seals and rejects
new serializer mutation. This invocation pins the final test/helper bytes before
and after execution; the earlier 50-pass receipt does not cover a subsequent
helper docstring change.

The stale global native module remains unchanged. A new offline CPU build uses
the cached pinned manylinux image, Rust toolchain and Cargo registry mounted
read-only. Its wheel embeds the current 202-file Rust closure and exposes the
expected 27-argument ABI. The regression command explicitly imports it from an
isolated target, records the module and extension paths, and verifies all pinned
source and native files remain unchanged. Building takes 66.28 seconds and the
whole native packet uses about 192.83 MiB; no full environment/cache copy or
network download occurs. The previous interrupted build remains recorded.

The current product wheel matches all 513 owned package files and the 224-file
implementation manifest. Outside the checkout, its synthetic ownership and
serialization smoke checks pass 376 assertions with all 176 imported owned
modules coming from the isolated install target. Existing dependencies are
shared; this does not establish fresh dependency installation.

The subsequent installed PR49 execution uses this exact source with the original
one-pose request. All six stages complete: continuous run and verification,
pause after the baseline candidate, resume, verification and equality audit.
Thirteen independently reserialized scope comparisons match exactly, including
complete arm rows, attempts with checkpoint digests, settings and selections.
The baseline journal is reused with zero new baseline score or force calls.
Refinement performs 32 accepted iterations and 38 force evaluations per run;
raw force 37.951442 still fails convergence and bond preservation fails, so the
valid original baseline remains selected. These failures are retained.

This proves candidate-journal reuse across processes, not interruption/resumption
inside minimization. Full solver checkpoint state is not separately published.
All five installed CLI boundaries check 224 implementation files, 513 product
members, distribution metadata and loaded native-module membership. The request
uses the Python CPU reference backend; importing the verified native dependency
does not demonstrate that it computed this trajectory. The enclosing six-stage
wrapper takes 215.791 seconds, excluding earlier build/install, the interrupted
prior attempt and post-run review. This is a cost observation, not an A/B speedup.
The previous attempt's exact termination time and consumed cost are unknown and
remain unknown. The new packet is about 2.82 MiB and reuses installed packages.
Earlier PR49 receipts retain their original source identities and do not qualify
this changed source automatically. Admitted experimental roles, matched
candidate-ordering benefit, affinity and HIP parity remain incomplete.

Evidence: [guard profile](/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-pr49-canonical-profile-20260929-pu21jq79/README.md),
[controlled evaluator result](/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-canonical-cpu-comparison-20260929-dypdzoup/result.json),
[predeclared protocol](/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-canonical-cpu-comparison-20260929-dypdzoup/protocol.json),
and [evidence index](../evidence/canonical_normalization_cpu_v1.json).
