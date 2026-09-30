# Prospective 7XTB SRO development pose recovery packet

This directory contains a **prospective coordinate packet**, a stdlib generator,
a saved-result coordinate evaluator and portable synthetic boundary tests.
No force, score, native graph, optimizer, OpenMM or model execution is performed.
The packet is `PROSPECTIVE_NOT_EXECUTED`, pending root freeze review. It does not
admit a new source role, rights, training, calibration, independent evaluation,
physical validation, experimental affinity, HIP or service qualification.

The sole retained computational state is the existing **SRO NZ +1,
C10H13N2O+, 26 atoms: 13 observed heavy atoms and 13 generated H**, with the
original fixed, dry 4,376-atom receptor and original parameter files. State and
source uncertainty are inherited from the [preparation](../human_5ht6_sro_numerical_preparation/README.md).
Bound protonation remains unknown; deposited buffer pH 7.4 does not measure it.
This is a known reserved 3.3 Å cryo-EM model, without an independent held-out
pose or per-atom ground truth. The development reference does not grant new
assay/fit/training/evaluation rights. `scientific_pose_recovery_validated` remains
false even when saved quantities meet these development gates.

## Frozen coordinates and budget

Before generation, the code declared every direction, angle and seed below.
All 26 atoms receive one proper rigid rotation around the prepared 13-heavy-atom
centroid followed by a 2.5 Å translation. No internal deformation, new hydrogen
orientation, atom substitution, microstate or receptor alteration is generated.
Seeds identify cases and future solver determinism; generation uses explicit
values without RNG draws, geometry/energy rejection or resampling. The printed
initial errors below are coordinate arithmetic, not observed optimization outcomes.
No direction was tuned after computing them.

| Case | Seed | Translation direction, normalized | Rotation axis, normalized | Angle | Initial no-fit heavy RMSD, Å |
| --- | ---: | --- | --- | ---: | ---: |
| perturbed_01 | 2026093001 | +x | +z | 0° | 2.500000000 |
| perturbed_02 | 2026093002 | −y | +x | 0° | 2.500000000 |
| perturbed_03 | 2026093003 | +z | +z | +25° | 2.681635623 |
| perturbed_04 | 2026093004 | (−1,−1,0) | (1,1,1) | −25° | 2.721494736 |

The initial symmetry-aware RMSD must be at least 2.25 Å, above the 2 Å final
recovery target. All four generated cases remain in the denominator, including
preflight rejection, failed preparation/execution, watchdog, and unstarted cases.
The observed start is in `stability_control/` and has zero initial error. It is
never included in the generated pool or recovery denominator. A saved same-input
historical control can be replayed with explicit `status: retained_control`,
retained receipt references and the same state/input hashes; it never counts as
recovery and is not charged as a new execution. The generator opens preparation
and request identities only, not archived result/trajectory files.

The prospective single native L-BFGS arm has **4 × 417 = 1,668 objective attempts**
as a maximum, including rejected, failed and pending attempts, with 416 accepted
steps per case. Each case separately allows at most two restart-force checks,
two score calls and two endpoint oracle states. The original solver config,
0.05 Å step cap, pocket, receptor parameters and CPU wheel identity are recorded.
The operational ceiling is 7,200 s per case; cases have fixed order 01–04.
A fatal failure or watchdog stops new execution without retry/replacement. A
preflight rejection consumes its case in the denominator with actual zero work.
The optional observed-start control is separately budgeted and reported. No AI
arm, new proposal, extra torsion search or best-trajectory selection is included;
an AI policy/weights/budget comparison requires a separate prospective freeze.
Actual oracle observations and all enclosing/nested timings must be retained by
the future runtime audit; two endpoint states do not mean two OpenMM force calls.

## Coordinate/reference boundary

`calculation_inputs/chemistry.json` is an explicitly derived **coordinate-free
chemical projection**, retaining every original atom index/name, element,
atomic number, formal charge, isotope, aromatic/stereo declaration, partial
charge, mass, and bond index pair/order/aromatic/stereo record. Its SHA is
`1d960edf1ee7c450af7594b0fad6c6f605439e045da8292bfa48a74d4f95a3dc`.
Verification rederives the projection from the hash-pinned preparation and
requires equality. All original parameters, extensions, cross parameters and
receptor bytes remain pinned without modification. The candidate file contains
only IDs, seeds, roles, frame and perturbed coordinates, with SHA
`5fa2b65522197a395c1dd6d88d6add82cfdb61ddaa2e5bced7a4cf528be5541b`.

The full original ligand and atom-provenance paths are restricted to generation,
lineage verification and evaluation. They contain observed/reference coordinates
and must not be runtime/AI selection inputs. Atom metadata and source mappings
are excluded from the coordinate-free projection. Reference XYZ and the explicit
source atom-site 8089–8101 heavy mapping are in `evaluation_only/reference.json`.
Neither reference coordinates, transform pivot, direction/angle specification,
initial RMSD nor stability control may enter proposal/AI selection. The retained
pocket is a separately declared source-derived prior; this is local development
around that known pocket rather than blind receptor-wide docking.

The evaluator uses direct receptor-frame RMSD and the minimum over **declared
heavy graph automorphisms**, without centering, Kabsch fitting, ligand
translation/rotation fitting or receptor realignment. The graph labels preserve
element, formal charge, isotope, aromatic flag, stereo and explicit H count;
nonaromatic bond order/stereo is preserved and aromatic Kekule order is normalized.
Atom names and XYZ do not determine automorphism equivalence. SRO has exactly one
permitted heavy mapping, the identity. Synthetic symmetry cases test permutation
handling. Reference/mapping changes or an undeclared permutation are rejected.

The canonical identity consequence was checked with stdlib compact JSON hashing:
original system SHA is `7736058c5af99dbbdeca8de80eb7029bbd870f8c40186a00838f6601ab026972`
and topology SHA is `b9550701d7081986dd3823950d726cd41ba41909eac28df74b90bfc92087af2b`.
Changing the coordinate tensor alone changes the system seal but keeps topology
SHA. Removing embedded source-reference coordinates from atom metadata changes
the topology SHA as well. A future runtime adapter must explicitly derive new
canonical/system/topology identities and rebind topology/base-parameter/cross
identity fields while proving every original numeric parameter term unchanged.
This generator does not silently reuse the original topology/system seal for a
modified canonical system. Its `runtime_adapter_status` remains
`NOT_IMPLEMENTED_NOT_AUTHORIZED_TO_EXECUTE`; runtime integration and actual input
validation require separate review before molecular execution.

## Acceptance and evaluation

Only the **last accepted state** is assessed; retrospectively selected best
score/energy/reference-error states are unsupported. The unchanged conditions are:

- Raw maximum atom force, using the Euclidean atom-force norm: ≤0.001 kcal/mol/Å.
- Internal-energy increase from that case's initial state: ≤5 kcal/mol.
- Maximum bond-length change from that case's initial state: ≤0.15 Å.
- All eight declared geometry checks are complete and true, including the
  element-radius receptor-overlap check. Missing/undeclared checks are rejected.
- Both endpoint numerical states pass the retained same-math ≤1e−8 kcal/mol
  energy and ≤1e−8 kcal/mol/Å force-component errors.
- The separate dimensionless ordering score strictly improves. Score, energy,
  force convergence and reference pose error retain distinct meanings.
- Recovery additionally requires initial symmetry RMSD ≥2.25 Å, final symmetry
  RMSD ≤2 Å and an improvement ≥0.5 Å. Low RMSD cannot override an admission gate.

The evaluator reads a strict `sro_saved_recovery_results/1` export, binds each
start-coordinate digest, chemistry digest, all five original input digests,
review timestamp, last-state policy, work ledger and retained receipt bytes.
Failed or missing work stays failed/unknown. Completed ledgers require one
successful initial objective, zero unknown pending attempts, exactly two saved
score calls and two endpoint states; rejected/failed attempts count toward 417.
It recomputes atom-force norms, bond deltas and heavy RMSD from saved arrays and
checks the unchanged gates. Molecular/score/oracle observations in an export are
**saved assertions**, not independently authenticated execution by this stdlib
reader. Its output states that limitation; independent source-driven endpoint
and trace receipt verification remains necessary. No source or scientific
admission is granted by the reader.

Root review is a separate sidecar, outside the sealed prospective packet, with
schema `sro_recovery_freeze_review/1`. It must bind the exact protocol/manifest
SHAs, an aware `reviewed_at` timestamp preceding each new execution, reviewer,
`reviewed_before_execution: true` and
`execution_scope: separately_authorized_future_execution`. The helper cannot
replace review of actual derivative runtime inputs, parameters, authority binding,
source bytes and preflight behavior. No approval sidecar or molecular result is
created here. Retained control replay is the sole permitted older observation.

## Packet and validation

The new packet is [prospective_v1](prospective_v1/manifest.json).
Protocol SHA: `5977f12ee7e35710e6a8eb09a19337ff579750f2573fa442d31b89fe3a94ca23`.
Manifest SHA: `4fa96ef4a8457fd20e8bce67dafa380c08b01e15765bcfbb0a1eb67634815dc3`.
Exact generator/evaluator SHA: `cd2b926ec63fcd2af17ecca2e316d48b5b224fbf62c6ab75b3bf8dcb4a7c19b7`.
Every member is bound by size/hash. Generation uses exclusive creation; rerunning
against an existing output rejects without overwriting it. Verification rejects
changed source/input bytes, additional packet files, symlink escapes, rehashed
candidate transformations, leaked references, changed source map/symmetry,
relaxed protocol gates or altered prospective status. The source checkout context
was `24c3c3475174695ecd6a6d4b47b17440e7164553`.

From the repository root, the actual packet verified and **23 stdlib synthetic
boundary tests passed**. Tests include no-fit translation, graph symmetry,
all-pair rigid distance preservation, invalid state/atoms, mutation and leakage,
rights/role escalation, force-vector norms, unchanged admission gates, missing
cases, preflight rejection, fatal stopping, budget/accounting failures,
review/receipt boundaries, create-only output and separate retained control.

```sh
python3 -B docs/research/human_5ht6_sro_pose_recovery/recovery_protocol.py verify \
  --packet docs/research/human_5ht6_sro_pose_recovery/prospective_v1
python3 -B -m unittest discover -s tests/unit -p 'test_sro_pose_recovery_protocol.py' -q
```

For a separately reviewed future saved-result export:

```sh
python3 -B docs/research/human_5ht6_sro_pose_recovery/recovery_protocol.py evaluate-saved \
  --packet docs/research/human_5ht6_sro_pose_recovery/prospective_v1 \
  --results NEW_SAVED_RESULT_EXPORT.json --freeze-review ROOT_FREEZE_REVIEW.json \
  --output NEW_COORDINATE_EVALUATION.json
```

The evaluator exclusively creates its output and never runs the runtime. All
original preparation/archive/Fresh-128 data and shared runtime modules are
preserved. No commit, push, deletion, dependency installation or new force/score
result was produced by this work.

## Subsequent input adapter and root audit — 2026-09-30

The sealed packet retains its original prospective status and historical
`NOT_IMPLEMENTED_NOT_AUTHORIZED_TO_EXECUTE` field. Subsequent work adds the
reference-free [runtime input adapter](runtime_adapter.py) outside that packet.
The [integrated milestone](../integrated_setup_and_sro_inputs_20260930.md) records separate root packet review,
actual four-case derivation and old-wheel input binding, exact primitive/numeric
preservation, readonly independent review and all receipt pins. No perturbed
optimization was run and no recovery result or execution authority was admitted.
The initial paragraphs describe packet creation; the sidecar audit is the current
input-integration evidence. The full execution/accounting/export driver remains
the next task.
