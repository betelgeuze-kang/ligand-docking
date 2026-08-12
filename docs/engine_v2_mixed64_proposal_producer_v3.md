# Engine V2 mixed64 fixed64 producer v3

The producer converts one frozen mixed64 allocation plus complete pre-result
source payloads into exactly 64 ordered generation records. It is synthetic
pre-activation infrastructure and grants no reservation, molecular execution,
historical/Fresh, product, Stage 0, GitHub Actions production, or public claim
authority.

The canonical policy is
`config/engine_v2_mixed64_proposal_producer_v3.json`, with SHA-256
`1bde275ef62ada47611acec9fcba27868ecc928ba9e74a057a075f86ae77bcf7`.
It binds the proposal-geometry policy SHA-256
`1ee6e474e042eadb882542346b9beff4408d1f60e004686320ee657f8e23a8d9`.

## Complete source payloads

Every supplied V7 control, true conformer, and retained control includes:

- canonical proposal-identity payload;
- canonical source receipt, whose embedded receipt SHA is independently
  rederived;
- full binary64 coordinate payload and coordinate SHA;
- for V7 controls, the complete proposal-lineage payload and its rederived
  SHA.

The allocation contains a typed exact-V1.1 evidence receipt that jointly binds
the exact source-receipt SHA, proposal identity, ligand-coordinate identity,
receptor-coordinate identity, and both prepared topology identities before any
result exists. That same exact-source evidence now binds canonical hashes of
the ligand/receptor vdW radii and ligand heavy-atom mask to the prepared
topology identities. Slots 24–35 and 44–59 retain the exact proposal and ligand
coordinate as their generator parent even when an anchor feature is absent.
The bundle rederives the complete exact ligand and receptor payloads plus all
three topology-derived parameter hashes and verifies them against that
evidence. It separately binds pocket geometry. Cross-wired or noncanonical
payloads fail the whole input before generation.
An absent otherwise-declared payload does not reallocate a slot; it becomes a
typed per-slot generation failure.

## Frozen lane execution

- Slots 0–23 and 60–63 are exact coordinate/proposal pass-throughs of their
  selected V7 or retained parents.
- Slots 24–43 invoke the allocation-owned indexed SO(3) receipt. True-conformer
  outputs remain distinct from their parent identities.
- Slots 44–59 invoke the allocation-selected single-anchor receipt and retain
  its full geometric precheck.

Every successful slot emits the existing `ProposalExecutionReceiptV2`, binding
the allocation slot and selected evidence receipts, generation parent, output
proposal and coordinates, exact generation input receipt, producer policy,
implementation-source SHA, and component ID. Generated proposal identities
bind the slot, source payload, placement receipt, and output coordinate
identity. Pass-through proposal identities remain exactly their parent
identities.

A generated proposal remains a transformed output when the proposal/coordinate
identity pair differs from its parent. A legitimate zero-motion placement may
therefore retain the parent coordinate hash while carrying its independently
derived generated-proposal identity; only an unchanged pair is rejected.

## Failure completeness

There is exactly one generation record for each slot. Allocation missing
features, missing source payloads, degenerate SO(3), invalid feature indices,
and other typed geometry failures emit `ProposalGenerationFailureReceiptV1`.
Such a record contains no fabricated proposal, coordinates, or proposal-
execution receipt. It preserves the original slot, allocation failure details,
attempted source payload identity when present, and the canonical failure code.

The producer reads its own implementation and the geometry implementation
before work and again after all slots. Any source drift discards the batch.
The batch embeds all 64 records and reports generated and typed-failure counts
whose sum must remain 64.

## Native ABI 1.19 transform-bound mirror

The versioned C ABI now exposes
`bg_docking_fixed64_producer_v1_run`. It rebuilds the frozen allocation,
rederives every supplied coordinate payload and exact admission-system
identity, dispatches slots 24–43 and 44–59 to the explicitly selected C++,
Rust CPU, `hip_safe`, or `hip_fast` numerical backend, and applies one shared
fixed64 geometric-admission batch to the resulting 64 rows. Pass-through rows
retain their parent proposal identity; generated rows bind placement and output
coordinate receipts. Every failed row owns an unavailable, zero-filled
coordinate segment instead of disappearing from the denominator.

ABI 1.19 also preserves the exact local placement quaternion in every
generated row. Passthrough rows bind the identity rotation, indexed-SO(3) and
single-anchor rows bind their component quaternion, and typed failures keep
the channel all-zero. The quaternion is unit-checked before commit and is part
of the row receipt, so downstream validity/refinement composition cannot
silently invent or cross-wire rotation evidence. The exported frozen profile
identifier is `betelgeuze.engine_v2_mixed64_native_fixed64_producer/1.1.2`.
Patch profile 1.1.2 quantizes each max-scaled pocket-normal ratio to 40
fractional binary bits before unit normalization. This absorbs scale-product
rounding drift such as `[1,1,5]` versus `[0.3,0.3,1.5]` consistently in the
producer, indexed component, and independent Rust replay. It also preserves
out-of-envelope transformed coordinates as typed `NONFINITE_OUTPUT` failures
rather than dropping their fixed64 slots.

The producer commits transactionally only after all nested backend evidence is
validated. Synthetic CPU, sanitizer, and qualified-device parity tests cover
repeat stability, all lane mappings, missing source and feature evidence,
component typed failures, severe-penetration retention, range alias rejection,
and all false authority bits. Rust raw bindings carry compile-time C/C++ layout
assertions and the crate packages the exact same vendored C++ implementation.
This is a non-authoritative implementation mirror, not permission to execute a
molecular corpus.

## Remaining activation boundary

This producer closes the generation implementation gap only within its own
non-authoritative receipt. Activation remains false because:

- geometric admission v3 now preserves generated candidates, allocation
  failures, and runtime proposal failures in the same fixed64 denominator, but
  remains synthetic and non-authoritative;
- a second geometric gate must bind post-refinement coordinates;
- Scorer V1 terms and pose validity must be reexecuted from these exact
  coordinates;
- an independent producer/downstream verifier and attestation are still
  missing.

No D0/D1 molecular run may use this component until those downstream bindings
and the external one-shot authority gate are complete.
