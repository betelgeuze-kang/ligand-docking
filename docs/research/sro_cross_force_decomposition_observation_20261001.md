# Saved-initial-state native cross force observation, 2026-10-01

The new unchanged cross baseline and the instrumented cross calculation return
exactly identical energies, all 78 ligand force components and 15,881 active
pair counts. The external initial-state force residual is reproduced in the LJ
component. Coulomb passes the unchanged `1e-8` gate. This locates the residual
in this particular component comparison; it does not establish its numerical
cause or qualify the preparation or the service.

**The complete execution failed after the numerical observations.** Its final
environment provenance step raised `ValueError: bounded_input_required`.
The receipt, raw observations, durable events and root process record preserve
that failure. Neither that receipt nor the historical campaign is relabeled
successful, and this diagnostic was not retried.

| New native component versus saved newR initial OpenMM original arm | Max absolute force-component residual (kcal/mol/Å) | Atom / axis, zero based | Original `1e-8` force gate |
| --- | ---: | --- | --- |
| Combined cross | 4.761386662721634e-8 | 19 / z | fail |
| Cross LJ | 4.7672074288129807e-8 | 19 / z | fail |
| Cross screened Coulomb | 6.536993168992922e-13 | 24 / z | pass |

All three component energy comparisons pass their fixed `1e-8` gate. The new
baseline LJ and Coulomb energy hex values exactly match the stored R2 initial
component energies. Stored R2 scalar energies, new native force vectors and
stored newR OpenMM component vectors remain distinct evidence roles. These are
new native observations, not recovered historical native term vectors.

## Intervention and arithmetic limits

The executing diagnostic is source revision r3, SHA
`3b2fab601d97805516c4f633562fc2368b8aa8aaa6e6242e1eaa79f1cd01c41b`.
It observes only the saved initial coordinates of development case
`perturbed_02`. It loads the frozen wheel source closure from wheel SHA
`00814229724d90cca5b81d00c2a78a4ae6dfe983e95930552ca693d2c13484b8`.
The original cross method remains byte-pinned through member SHA
`22c7c9a6c5ceee1c508ec6003149037c4cca7c6e1034a991c8d33c488fa2d82a`.

The baseline delegates the original combined-gradient call once per active
block. The diagnostic retains the original `lj + electro` gradient and original
force subtraction, energy accumulation, block ordering and active pair
enumeration, while additionally observing separate LJ and Coulomb gradients.
Both arms must return exactly identical complete outputs. Captured combined
gradients must reconstruct each returned force in original order exactly.
Both checks pass in the retained observations. Separate components never
replace the authoritative combined force.

There are 12 active receptor blocks out of 18 maximum blocks. Their indices are
`0, 2, 3, 4, 5, 7, 8, 9, 10, 13, 14, 15`. Each retains ordered ligand/receptor
pair identities. The ligand has 26 atoms and the receptor has 4,376 atoms;
the receptor block size remains 256.

The largest combined-minus-separately-summed-LJ/Coulomb difference is
`2.9103830456733704e-10`, at atom 24 / z. Replacing only the accumulation of
the already observed block gradients by `math.fsum` changes combined and LJ
forces by at most `5.820766091346741e-11`, at atom 24 / z. The Coulomb change is
at most `7.105427357601002e-15`, at atom 23 / x. These observations are much
smaller than the external LJ residual. They do not probe within-block pair
reduction, distance/power arithmetic, coordinate conversion or an alternative
derivative implementation. They provide no justification for loosening the
gate or changing the historical failed initial-state result.

## Completion, failure and cost accounting

The two cross entries and 48 backward calls completed: 12 baseline combined,
12 diagnostic combined, 12 diagnostic LJ and 12 diagnostic Coulomb. Each
backward group reserved at most 18 slots; six inactive slots per group were
known not dispatched. The 74 maximum reservations therefore consist of 50
completed boundary calls and 24 inactive backward slots, with zero numerical
error or unknown calls. This reservation count is not a completed-call count.
New internal-force, score, optimizer and OpenMM calls are zero. Autograd graph
construction occurs within the cross entries; a zero separate graph-builder
API count does not mean graphs were absent.

The complete child execute process took `7.859861210` seconds. Within it, the
receipt entry scope took `7.326016975` seconds and the numerical scope
`2.677619527` seconds. Cross entry scopes were `1.400731135` seconds for the
baseline and `1.235499541` seconds for the diagnostic. Recorded backward leaf
wall times sum to `0.399713403` seconds. These are nested scopes with observation
and fsynced journal costs; they must not be added or used as a speed comparison.
The complete process failed during subsequent provenance recording.

Six authorized input roles were read and checked before computation. The
post-computation product source closure contains 155 loaded module pins.
The completed receipt seal, vectors and journal can be independently checked.
The failed environment step left the final Torch/NumPy version/thread/module
manifest and the subsequent complete source/input rehash unavailable. They
must not be inferred from an earlier run. The Python executable had already
been checked against the frozen binary pin before numerical dispatch.
The five closed R2 metadata and stored-observation pins remained unchanged.

Source review and 42 synthetic mock tests preceded this execution. Those tests
prove bounded software contracts, not actual molecular accuracy. A separate
read-only reviewer reported matching full arm outputs, four force-sum groups,
three external component residuals and call counts without another force or
OpenMM evaluation. The final scoped conclusions are retained as root-recorded reviewer
communication; no independent standalone reproducer/archive was authored.
The reviewer did not independently complete receipt-seal, full event-order or
cost audits, direct returned-force versus reaccumulated-force matching, external
energy gates or combined-minus-LJ/Q vector recomputation. Its newR file hash
was supplied, not independently rehashed. Root separately checked the original
receipt seal and retains the raw source, vectors and journal. Exact review and QA references are in the
[evidence sidecar](../evidence/sro_cross_force_decomposition_observation_20261001_v1.json).

A subsequent root-owned standard-library arithmetic audit separately rehashed
both retained receipts and the journal, verified both receipt self-seals, matched
all returned force components to original-order block reconstruction, and
recomputed the combined-minus-LJ/Q vectors and all external component energy
and force comparisons. All recorded values and unchanged gates match. It also
checked the 260 recorded event rows against receipt observations and call
boundaries, and checked nested timing-scope consistency. Its standalone script
and report are retained in
`/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-sro-saved-cross-arithmetic-review-20261001-qrh8ez6j`.
This is a separate root audit of saved observations; it does not broaden the
earlier reviewer communication or provide new engine calculations, missing r3
provenance, scientific qualification or an external independent experiment.

The durable journal records raw returned gradients before finished events.
For a hard stop with no finished event, a started event's
`dispatch_attempted=false` is only a snapshot before dispatch; work remains
unknown. The normal retained final receipt in this run has complete call
boundaries. No automatic retry or checkpoint reinterpretation is authorized.

## Software repair and evidence boundary

The frozen helper's pin contract requires a nonempty file. A read-only stat
audit found valid zero-byte Python package sources in the pinned dependency
site, making a loaded empty package the plausible provenance failure source.
The exact offending loaded module was not recorded, so this remains an
inference rather than an established failure trace.

The subsequently prepared r4 repair handles empty, canonical, regular `.py`
module sources explicitly with the empty-file SHA256, descriptor/path identity
checks and EOF checks. It rejects empty compiled files, symlinks, protected
paths and drift. Nonempty dependency pins retain their bounded behavior;
numerical input guards and the frozen helper remain unchanged. Missing or
non-file module origins are recorded explicitly rather than silently omitted.
This manifest describes loaded file-backed module sources and unresolved
origins, not every OS library, kernel or in-memory instruction.

The r4 repair and hosted mock-only CI have separate synthetic QA. The existing
mock's fixed-method fixture now uses the discovered repository root while
retaining its exact source SHA/AST checks, so it can run on hosted runners.
The workflow has pinned actions/dependencies, configured hosted runners, read-only
permissions, no credentials retained and no numerical dataset/artifact upload.
A separate isolated r4 provenance-only runtime probe completed after the
code review and 81 mock tests. It pinned 742 loaded file-backed modules,
including 10 empty Python sources, and retained 39 unresolved module
origins explicitly. It made no custom tensor, product, force, score,
optimizer, OpenMM or molecular-body call. Normal native library import
initialization was performed and is not quantified. Its dtype/device
fields are diagnostic policy, not tensor measurements. This separate
successful source-pinning observation does not supply the missing r3
runtime manifest or complete shared-library provenance.

**r4 has not been numerically executed.** Its QA does not repair the already
failed r3 receipt. The executing r3 source, test and plan snapshots remain
unchanged alongside their original reviews.

## Retained evidence and next question

The actual run is retained at
`/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-sro-cross-decomposition-20261001-fitq45_l`.
Plan SHA is
`ed1c697f634421ad774363c9d0221082d75dc940313043724313a00b8cf4eb39`.
The 341,609-byte numerical receipt SHA is
`2cee8fe89f9ba9c450dda6ba25d1f031e0fea05635228ef01526f0229350507b`;
its status remains **failed**. The 299,478-byte events file SHA is
`d5e14bd74aa0380292c23e84362e6de6f1d6b33afd9efc6dc131fe06a3705373`.
Root observation SHA is
`14484c1ae30f5de7f08d04df9b62ae1835374eb12231c46b942d82c1747b8e36`.
The saved newR OpenMM reference SHA remains
`4d392e37f9c6a933b980fd39cd48fbd0dc12df7f8c4bf01c025dbb3b76ba8dfc`.
The [pre-execution plan](sro_cross_force_decomposition_diagnostic_plan_20261001.md)
retains its historical source snapshot.

The next narrowly scoped numerical question is the LJ distance/power and
within-block derivative/reduction path in the dominant initial-state residual.
It needs a separately reviewed plan, component-compatible reference arithmetic
and an explicit call budget. Establish environment provenance before its force
dispatch, and retain completed work if later recording fails. Do not obtain a
green result by weakening the fixed gate or replacing the old receipt.

R2 remains completed 2 / failed 1 / unstarted 1, recovery **0/4**. No original
ligand reference, protected Fresh-128, assay/training role, experimental affinity
label, scientific qualification, HIP parity, AI gain or release authority is
promoted. This single saved development state is not an independent evaluation
cohort. The five-goal objective remains incomplete.
