# Engine V2 source-paired clearance activation evidence

## Status

This slice makes the frozen clearance shadow rule structurally testable with
runtime-authenticated inputs. It does not execute the protected historical A/B.
The governance policy is
`config/engine_v2_source_paired_clearance_activation.json`, schema
`betelgeuze.engine_v2_source_paired_clearance_activation_policy/1.2.0`, with
SHA-256
`988d0bb47bfa6ff934887e1e12b5a512b55aaf40033a04963d141c4ffefe212c`.
Its base is exact `main` commit
`e782fb2dadd83ce4b9e41fc1af5b970fe63e28ca`.

The underlying PR #243 policy is not changed or re-fitted. Its SHA-256 remains
`e5936f33d5aec54aae67f519e5cf6dffcc61181237270adb3e367a5f65cb29ad`.
The original pure evaluator accepts caller-supplied probe scalars; therefore a
self-hashed probe or decision proves internal consistency, not source
provenance, and is not admissible activation evidence.

## Receipt chain

`SourcePairedClearanceCaseSourceReceiptV1` first binds one of the exact eight
scored historical case IDs to the pinned V1.1 archive, member manifest, bundle,
and report identities. For each case it then requires the exact frozen archive
member path, raw member SHA-256, internal member-receipt SHA-256, authenticated
input, source-proposal receipt, allocation, native pose, receptor, input
artifact set, and current-V7 candidate-lineage identity. The complete per-case
authority map is frozen as
`4c083af473c369bf35fc34fdf4fe797ddbb2ef60b5474a78d6354415e3aa06bc`.
An arbitrary self-consistent member or a relabelled case therefore fails
closed. The archived score and rank scalars remain explicitly unauthorized
because that archive did not retain complete scorer-term receipts.

`SourcePairedClearanceCurrentV7LineageReceiptV1` reconstructs all 64 ordered
current-V7 candidate states as typed proposals. Each row must be either an
exact source-slot identity passthrough or a typed V1.1 refined proposal whose
immediate parent, source slot, proposal fingerprint, coordinate/torsion state,
authenticated input, allocation, receipt self-hash, implementation authority,
and policy flags all agree. The outer evidence receipt compares every baseline
row with this exact lineage, including non-target rows; copying the same forged
non-target into both arms is not sufficient.

`SourcePairedTorsionRescueActivationSnapshotV1` is builder-only and available
only after an exact fixed rescue target has produced complete V1.1 clearance
telemetry. Before the snapshot is released, the refiner requires the typed,
self-hashed `SourcePairedTorsionRescueProposalReceipt` and verifies its exact 64
ordered slots, authenticated input, allocation, target slot, and parent slot.
The snapshot then binds that complete proposal receipt, the full V1.1 payload
and SHA-256, full allocation payload and SHA-256, candidate and source proposal
identities, source and candidate coordinate/torsion identities, V6-baseline and
optimized coordinate/torsion states, raw minimum distance, minimum VDW surface
gap, receptor/internal/combined objectives, ligand and receptor atom counts,
exact pair count, and torsion availability/selection state. Cross-wired
receipts, coordinates, torsion metadata, objective fields, count products,
policies, proposal slots, or parent slots fail closed.

Snapshot schema `1.2.0` additionally carries the exact authenticated docking
input receipt, its hash-bound element-aware validity context, and the exact
receptor-coordinate tensor. The public adapter verifies the complete input and
context hash chain, reconstructs the frozen VDW policy and ligand/receptor
radii from the bound element lists, and independently recomputes every raw
distance, surface gap, ratio, and arg-min atom index for both states. It also
binds the baseline torsion tensor to the frozen source slot, replays every
authenticated V1.1 torsion move with the refiner's canonical angle semantics,
and requires the replayed optimized and actual current-V7 torsion digests to
match. Snapshot subclasses are rejected before method dispatch.

The activation adapter reconstructs the unchanged PR #243 probe only from each
snapshot and seals each decision and selected-or-retained state before scoring.
The activated state constructor is builder-token guarded, and the outer receipt
independently rederives every state from the source snapshot and baseline
proposal before accepting it. A private-constructor or reflection-produced
state that does not exactly match this rederivation is rejected.
The outer receipt requires one snapshot/state pair for every rescue target in
the frozen allocation, in allocation order; a missing, duplicated, reordered,
or extra target is rejected. An eligible decision may replace only its
designated experimental candidate state. An ineligible decision retains its
exact current V7 scientific evidence. Every non-target candidate must remain
identical between arms, so the changed slot set is exactly the set of selected
targets.

`SourcePairedClearanceSelectionActivationReceiptV1` then binds:

- the case-source receipt, frozen per-case archive-member authority, complete
  64-slot source-proposal receipt, complete 64-slot current-V7 typed lineage,
  per-candidate V1.1 receipts where applicable, and exact allocation receipt;
- every target's source snapshot, frozen policy SHA, probe-input SHA, and
  decision SHA;
- every target's current-V7 baseline candidate and selected-or-retained
  experimental candidate;
- exactly 64 ordered candidate rows for each arm;
- each candidate's complete `ScorerV1Terms` payload and receipt, with scorer
  authority bound to the same authenticated case input;
- complete internal `PoseValidityResult` evidence bound to proposal,
  coordinates, pose artifact, problem, context, configuration, and evaluator;
- the exact 22-check PoseBusters `0.3.1` redock map, bound to the same pose,
  native pose, receptor, report, implementation, and configuration as its
  authenticated symmetry-aware RMSD receipt; and
- the full ordering under `(total_score binary64, proposal_index)`, including
  bound Top-1 and Top-5 receipts.

Consequently score-term, internal-validity, PoseBusters, RMSD, exact-valid,
rank, Top-1, and Top-5 semantics are rederivable from the new receipt. The
older historical archive without complete `ScorerV1Terms` is used only for its
pinned source lineage and is not accepted as score, term, validity, rank,
Top-1, or Top-5 authority.

## Authority boundary

Evidence construction is available, but all execution and promotion boundaries
remain closed:

- historical A/B execution and result materialization are unauthorized;
- no generic runner, CLI, API, benchmark execution command, or product path is
  wired;
- default V7 selection and customer pose output are unchanged;
- fresh-holdout execution is unauthorized; and
- Stage 0 admission, scientific/public claims, and product claims are false.

The later exactly-once A/B requires its own predeclared execution authority and
must not reuse the incomplete historical score archive. This slice creates no
benchmark output, score result, or fresh-case evidence.

## Verification

The authoritative `ci-engine-v2-main` workflow compiles the activation sources,
verifies the self-hashed policy, runs snapshot and activation behavior tests,
checks the full scoring/ranking receipt, and audits that these paths remain in
the existing authoritative workflow. No new workflow or execution entrypoint is
introduced.
