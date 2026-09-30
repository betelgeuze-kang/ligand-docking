# Prospective initial cross force decomposition diagnostic v1

This benchmark-only module is
`benchmarks/oracles/sro_cross_force_decomposition_diagnostic_v1.py`. There is no
product tool wrapper. Importing it imports neither Torch/OpenMM nor product
modules and reads no molecular input. At publication only source review and mock
QA have occurred. Actual numerical body reads and molecular computations are
still absent until root authorizes a separately pinned numerical execution.

## Frozen question and authority

The completed particle round-trip experiment observed zero total-force arm delta
in both saved states despite seven sigma fields changing by one ULP. That bounded
observation does not explain the original case02 initial force discrepancy.
This new experiment asks for the native cross LJ and screened-Coulomb force
vectors at **initial only**, using the frozen old-wheel arithmetic and the same
prepared derived inputs. R2, its terminal result, packets, code, thresholds and
denominator remain frozen. Neither R2 nor the completed newR experiment resumes.
No tolerance is relaxed and no historical observation is resealed.

The old source `FixedReceptorEnvironment.evaluate_cross` returns LJ/Q energies
but only their combined force. Its source SHA256 is
`22c7c9a6c5ceee1c508ec6003149037c4cca7c6e1034a991c8d33c488fa2d82a`.
The wheel pin is
`00814229724d90cca5b81d00c2a78a4ae6dfe983e95930552ca693d2c13484b8`.
Source closure is every `.py` member of that wheel, with byte count/SHA256 for
each member. Only `.py` members are extracted; wheel data/XML/parameter entries
are not parsed. The relevant current fixed-receptor source must be byte-identical
to that wheel member. The plan pins diagnostic/test/document source and the
stdlib helper source (SHA
`f9d860e150542596457e546802ef8594365c112c424f8a1abf8e82a1734e9c3a`).

## Controlled instrumentation

The baseline compiles the original method body unchanged in a separate namespace.
A delegating Torch namespace proxy measures its existing autograd.grad calls and
captures returned gradients, then returns the same tuple. Original module globals
and Torch globals are never patched. Validation, CPU binary64 Å coordinates,
particle order, receptor block traversal, active pair enumeration, domain checks,
Lorentz-Berthelot mixing, cutoff, quintic switch, energy expressions, force sign,
force accumulation and returned energies/force/count are retained.

The opt-in method is an AST copy of that exact source. It replaces exactly the
single source `gradient = torch.autograd.grad(lj + electro, xyz)[0]` statement:
the original combined operand is evaluated first with `retain_graph=True`, then
LJ is differentiated with graph retention and Coulomb is differentiated with
`retain_graph=False`. The original total gradient variable, original subsequent
finite checks, original `force -= gradient.detach()` operation and return remain.
Every successfully returned gradient is recorded immediately, before the next
backward call. The instrumented combined output must exactly match the newly
observed baseline force, energy hex and active pair count.

The diagnostic stores source block index/start/end and ordered
`[ligand_index, receptor_index]` active pair IDs. Baseline backward keys identify
active-call ordinal because the unchanged original method has no per-block hook;
diagnostic backward keys identify source receptor block index. Their completed
gradient sequence is compared through the original accumulation order.

All 78 force components and component energies are recorded as binary64 hex.
Captured block gradients are reaccumulated with the source subtraction order and
separately with `math.fsum`. These are observations, not replacement outputs.
The original-order combined sum must exactly reproduce the returned combined
force. Separate LJ/Q sums and `combined - (LJ + Q)` are retained without replacing
the authoritative combined result. Empty active sets produce no backward calls.

## Input roles and read phases

The fixed terminal metadata root is
`/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-sro-guard-repair-four-case-20260930-p76d71f6`.
The plan/spec pins are respectively
`b5d7eb702534259e6689ae257cb8bb0ebb2a356131fe33dd07a3d2616b21706c` and
`2a1b69a03827787041c2ee9307ccbd400404bf96166e11343e36d41f2f73de89`.

Preparation reads only those fixed metadata files, owned/frozen source and old
wheel source code. It takes declared `receptor_count=4376` and
`receptor_block_size=256` from root's existing metadata observations. Block size
was selected in the already-bound case02 installed-binding metadata at line
26281, pin `da9d3ca1eb44a006687a520fff437a4b81c3166dc63894c1dd1587d4f78df391`
(891380 bytes). Preparation does not open that binding or any numerical body.

The six later numerical roles are exactly:

| Role | Later authorized use |
| --- | --- |
| receptor | Approved canonical receptor numerical state for the fixed environment |
| ligand | Case02 derived canonical ligand, never original ligand-canonical body |
| parameters | Matching case02 derived base parameters |
| cross_parameters | Matching case02 derived cross parameters and actual block shape |
| endpoint_states | Stored R2 initial coordinates/observations; no resume |
| openmm_reference | Stored newR original-arm cross/LJ/Q vectors and energies |

Derived roles must equal the exact case02 refs in the fixed terminal plan. Base
and cross public validators retain topology/fingerprint/charge/frame/order and
CPU float64/nonperiodic/domain requirements. Initial coordinates and derived
system hash must match their pinned records. Receptor atom count and block size
must match declared metadata before any cross force call. Extensions, original
parameters, original ligand/receptor XML and internal force evaluation are not
needed in this cross-only experiment and have no numerical input role.

The endpoint pin is 154238 bytes, SHA
`f6bb712b6530cdc2b25549a2f051df7b62f46bea248d54c09a179ed0364fa81e`.
The stored newR OpenMM ref is:

```
/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-sro-particle-roundtrip-20261001-ri1tdoph/numerical/receipt.json
bytes: 8783916
sha256: 4d392e37f9c6a933b980fd39cd48fbd0dc12df7f8c4bf01c025dbb3b76ba8dfc
```

Its body remains unread in preparation. In numerical execution its seal, schema,
case, completed OpenMM observation flag and initial coordinate pin must agree.
All source and numerical refs are verified again after execution. Any substituted
or extra numerical role is rejected before numerical bodies are opened. Protected
Fresh-128/reference/evaluation_only/stability_control and original
ligand-canonical body remain forbidden. Outputs must be new directories outside
both frozen experiments, source checkouts and protected path roles. Source refs
must retain exactly the four owned snapshot paths/basenames and frozen helper
SHA. Dependency site and Python binary metadata must match the pinned plan/spec.
Preloaded product/Torch/NumPy modules are rejected before numerical bodies are
opened; all product imports, including required imports, must have exact old-wheel
source bytes inside the isolated extraction. Torch must resolve in the pinned
dependency site. Neither old output may be overwritten or resumed.

## Budget, durable accounting and failure evidence

`K = ceil(4376/256) = 18`. The maximum protocol reserves 74 slots:

| Boundary | Maximum reserved |
| --- | ---: |
| baseline / diagnostic cross entries | 2 |
| baseline combined backward | 18 |
| diagnostic combined backward | 18 |
| diagnostic LJ backward | 18 |
| diagnostic Coulomb backward | 18 |

These 72 backward slots are upper bounds, not completed work. Original source
skips inactive blocks. After a successful entry return, unused slots remain known
not dispatched with an inactive-block reason. A failed entry leaves not-reached
slots not dispatched without claiming they were inactive. Every dispatched call
has an fsynced unknown start, then completion/error and wall/process-CPU timing.
`completed_native_backward_returns` counts successful primitive returns.
`attempted_native_backward_calls` counts completed/error/unknown boundary starts;
per-call `dispatch_attempted` distinguishes a journal interruption before dispatch.
Error/unknown counts and internal-work uncertainty remain separate. A false raw
observation-presence flag does not imply zero work after an unsuccessful call.
Failed/interrupted backward internal work remains unknown. A hard interruption
can leave a durable unknown record. Original total outputs and successful
gradient vectors are durably recorded before downstream observations proceed.
LJ/Q, postprocessing or later integrity failures preserve earlier raw evidence.
The process restores temporary source-import path and bytecode settings in a
finally block. Cleanup/journal secondary errors preserve an earlier primary
failure and completed raw observations. No global evaluator/Torch patch requires
restoration. Backward and authoritative cross vectors are captured before final
journal completion, so a failed finished-event write retains their raw returns.
Python binary SHA, Torch version/module pin, loaded Torch/NumPy
dependency identities, thread counts and CPU float64 execution are recorded.

Cross entry costs enclose backward work and observation I/O; numerical and entry
scopes enclose further work. These nested costs must never be added. Process CPU
is local process cost, not host/campaign CPU equivalence or speedup evidence.
Existing optimizer work counters are not incremented; this independent experiment
reports its own two entries and primitive backward counts. Internal, graph-build,
scorer, optimizer, OpenMM and intrareceptor-energy calls are zero. The zero
graph-build count refers specifically to the separate native neighbor-graph
builder API/optimizer work counter. Active-block autograd graphs are constructed
within the two new cross entries and included in their measured work.

## Comparison and interpretation limits

New baseline cross component energies are also compared separately to the stored
R2 initial component energy hex; this does not create historical term force
vectors. New native combined/LJ/Q force and energy are compared to the stored newR
original OpenMM cross/LJ/Q observations under the unchanged `1e-8` gates. The
original R2 initial discrepancy/failure remains unchanged irrespective of new
comparison outcomes. Newly observed native vectors are not historical R2 term
vectors. An old total minus a new cross observation is not an old native internal
force vector. Residual reduction or term attribution is not root-cause proof.

The `math.fsum` experiment holds observed block vectors fixed and tests block
accumulation only. It does not isolate per-pair reduction inside a block. A later
common-origin/native-Å versus OpenMM-nm experiment could examine coordinate
representation effects at fixed pair order; it is outside this protocol and
requires a separate review and call budget. No pose-recovery, physical-accuracy,
source-admission, qualification, release-readiness or performance claim follows.

## Reviewable commands

```
/usr/bin/python3 -I -B /ABS/benchmark/sro_cross_force_decomposition_diagnostic_v1.py prepare
  --r2 FIXED_R2 --output NEW_MNT_PLAN_DIRECTORY
  --test-source ABS_OWNED_TEST --document-source ABS_OWNED_DOCUMENT
  --openmm-receipt-ref EXACT_JSON_REF
  --receptor-count 4376 --receptor-block-size 256
```

Root inspects the resulting plan and exact SHA before the numerical phase:

```
/usr/bin/python3 -I -B NEW_MNT_PLAN_DIRECTORY/source/sro_cross_force_decomposition_diagnostic_v1.py execute
  --plan EXACT_PLAN_PATH --plan-sha256 EXACT_REVIEWED_SHA256
  --output NEW_MNT_NUMERICAL_DIRECTORY --numerical-phase-authorized
```

Execution failure produces a failed preserved receipt and nonzero CLI exit.
Mock QA stdout/stderr/JUnit and source/test/document/closure pins are preserved
directly in a new MNT directory, including any prior failed attempt. No Git or PR
operation belongs to this assignment. Actual numerical execution remains absent
until its separately authorized receipt exists.
