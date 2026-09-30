# SRO campaign failure and execution-guard repair — 2026-09-30

The frozen four-case CPU development campaign was launched once and stopped
after the first native case failed. None of the four cases produced authenticated
numeric endpoints or an independently audited recovery result. The original
failure is retained; future guard changes do not turn it into a successful run.

## Actual execution

| Requested | Completed | Failed | Unstarted | Independent endpoint states |
| ---: | ---: | ---: | ---: | ---: |
| 4 | 0 | 1 | 3 | 0 |

The enclosing campaign took 212.522516053 seconds. Native invocation and
dispatch times are nested inside this duration and are not added to it.
Case `perturbed_01` made one new score dispatch, one graph dispatch and one force
dispatch attempt. Score and graph returned; force ended with `AdapterError`.
The one force attempt is **not a successful energy/force observation**. Its
durable objective record is a failed evaluation, with no initial or current
numeric state, no accepted step and no pending objective. One saved baseline
score receipt was reused without an additional score dispatch. The external
oracle stage did not start. Subsequent case work remains unknown, not zero.

The parent stopped after the native process returned nonzero, as prescribed by
the frozen fatal-stop rule. No automatic retry, resume, replacement start,
budget reset, reference-guided proposal or best-trajectory substitution occurred.
The parent controller's exit code was zero because it published a stopped
campaign receipt; that exit code is not campaign success.

## Failure mechanism and future repair

The first force failure is consistent with a specific lazy-import alias defect.
The strict guard patches `evaluate_reference_force_field` in already loaded
modules. Input binding then lazily imports `openmm_periodic_extension`, which
captures that patched function as an alias. Restoring only the modules present
at guard entry leaves the new module's alias pointing at the deny sentinel.
The periodic force path subsequently calls that alias. The journal retains
`AdapterError` without its original detailed message, so this causal attribution
is a source-and-execution-path inference rather than a captured exception-message
proof.

The separate outer verification failure is explicit in stderr. Saved-result
verification reconstructs deterministic pose validity, and the name-wide
`evaluate` prohibition blocks the installed `ElementAwarePoseValidityContext`.
The installed sparse replacement computes geometry using distances and bounded
cell maps; it does not execute force, scoring, minimization or the native graph.

Future code preloads the known periodic extension before patching and restores
escaped deny aliases on guard exit. Saved-result verification alone uses an
explicit mode allowing the exact installed pose-validity function identities.
The default preparation/input-binding guard stays strict. Other `evaluate`
methods, force, scoring, minimization, native graph and OpenMM remain denied,
including calls after a swallowed exception. Profile/trace state is restored.
These are research execution guards, not a general-purpose hostile-code sandbox.

The future driver rejects an adapter without the strict saved-geometry keyword
API before importing Torch, binding the installed input or dispatching native
work. The existing plan builder still binds the original audit and old adapter;
it has not been silently promoted to the repaired adapter. A new audited
snapshot and reviewed prospective plan are required before another campaign.

The numerical, geometry, internal-strain, score-improvement, endpoint-policy,
time and work gates were not relaxed. Engine/wheel source was not rewritten.
The future adapter differs from the `15ed96…` adapter actually used by the failed
campaign. The executed driver/runner/supervisor/oracle remain `3defc8…`,
`a023a2…`, `b2e63b…`, and `9a1598…`; their immutable snapshots are retained.

## Saved-data accounting

The separate readonly exporter authenticates retained source/receipt bytes and
classifies journal and dispatch records without importing molecular engines.
Its detailed output keeps all four cases, the failed force dispatch, score reuse
and unknown unstarted work. The older scalar result format receives no rows
because there is no authenticated native child endpoint document. A generic
saved-result evaluator would therefore not supply molecular evidence for this
run. The export does not invent endpoints or turn missing oracle work into a
numerical pass.

Preflight and surviving post-exit source receipts are byte-identical and report
181 wheel-bound loaded module origins. The parent's failure receipt conservatively
leaves loaded-child origin verification unavailable; that original assertion is
preserved. The later forensic join is separate. Neither file hashes nor module
origins establish restoration of in-memory callable aliases. That restoration
was unverified in the failed campaign despite intact source bytes.

## Validation and retained evidence

Final frozen-source validation passed 224 SRO boundary/protocol tests and 31 subtests (21.98 s), plus 108 independent architecture regression tests (121.39 s). Changed-source/test Ruff and the repository architecture CLI passed. All twelve source/test pins are identical before and after this batch.

The complete SRO suite includes the 73 adapter tests; counts from separate or superseded runs are not added. A separate isolated old-installed import/alias regression passed without numerical dispatch. Independent readonly review accepted the exact future adapter, driver and actual saved export. Earlier fixture setup, broad lint and incorrectly selected image-context checks are preserved; the immutable protocol is still tested, and packaging mutation tests retain image exclusions. No built-image runtime or hosted-CI completion is claimed.

The validation archive retains 58 payloads (589,744 bytes) with manifest `c10645c3af0002695630b3603d851f10d180cc8045ed9bdab3f7a550b1beeb4c`. Original temporary receipt paths remain retained; relocated replay is not claimed.

The original campaign's 109 pre-execution portable tests and source-only review
passed, yet missed the installed lazy-import/verification interaction. Those
original receipts remain alongside the failure. Passing future regressions is
bounded software evidence, not a re-execution of this molecular campaign.
Existing dependencies are reused; no fresh dependency installation is claimed.

- [Machine-readable current evidence](../evidence/sro_stopped_campaign_and_guard_repair_20260930_v1.json).
- Campaign archive: `/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-sro-four-case-recovery-20260930-el_s4ivg`; terminal payload manifest
  `133ee18502f0e2f43b2a4231c6902ae4dab513b6fb5098e89166e8b62f49a1c5`,
  46 payloads, 3,581,679 bytes. Every payload size/hash and the exact set was verified.
- Separate saved export: `/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-sro-stopped-saved-export-20260930-40xz6_2h`; manifest
  `f00c5ac809e485310fded0396ecec6d81570591695d4bbe36088ebea684c64ea`,
  four payloads, 51,331 bytes. Its source is `f0686b…`, distinct from the executed parent.

## Next development decision

CPU execution integrity and a reviewed new prospective execution packet remain
the next priority. Any later campaign must identify this stopped predecessor,
the repaired adapter and new source pins before launch, preserve the original
four-case failure denominator, and retain the same scientific gates. It must
not be described as an automatic continuation or reset of the old campaign.
The frozen `prospective_v1` packet and all original records remain unchanged.

Physical recovery, affinity prediction, endpoint role admission, training,
AI value, HIP parity/acceleration and service qualification remain open.
The previously transcribed Ki rows add no new experimental measurements or
admitted learning labels. Fresh-128 remains untouched.
