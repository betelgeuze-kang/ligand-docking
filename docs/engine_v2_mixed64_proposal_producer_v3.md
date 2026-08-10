# Engine V2 mixed64 fixed64 producer v3

The producer converts one frozen mixed64 allocation plus complete pre-result
source payloads into exactly 64 ordered generation records. It is synthetic
pre-activation infrastructure and grants no reservation, molecular execution,
historical/Fresh, product, Stage 0, GitHub Actions production, or public claim
authority.

The canonical policy is
`config/engine_v2_mixed64_proposal_producer_v3.json`, with SHA-256
`a5cc354ef227d6d187d565dfbc6d0cfc631218e201198ed5b8a61b43baf6ad6d`.
It binds the proposal-geometry policy SHA-256
`77da86bb08f3fab6072d08f0c75c096723e68490db1c8bb794fb02e81302fc2d`.

## Complete source payloads

Every supplied V7 control, true conformer, and retained control includes:

- canonical proposal-identity payload;
- canonical source receipt, whose embedded receipt SHA is independently
  rederived;
- full binary64 coordinate payload and coordinate SHA;
- for V7 controls, the complete proposal-lineage payload and its rederived
  SHA.

The bundle verifies these rederived identities against the allocation's typed
source evidence. It also binds the exact V1.1 base source, receptor source and
coordinates, ligand/receptor vdW radii, heavy-atom mask, and pocket geometry.
Cross-wired or noncanonical payloads fail the whole input before generation.
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
