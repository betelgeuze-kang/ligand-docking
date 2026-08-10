# Engine V2 geometric admission v3

Geometric admission v3 is the failure-aware, pre-refinement gate immediately
after the fixed64 proposal producer. It consumes one sealed
`Mixed64ProposalProducerBatchV1`; callers cannot supply replacement coordinates,
scores, ranks, validity outcomes, reservations, or authority.

The canonical policy is
`config/engine_v2_geometric_admission_v3.json`, with SHA-256
`0d3203daeb245d29fe4b03a73204d8cddb25ce84b310b008d61729d89659a2c6`.
It binds producer policy SHA-256
`a5cc354ef227d6d187d565dfbc6d0cfc631218e201198ed5b8a61b43baf6ad6d`.

## Failure-complete denominator

The batch always contains 64 ordered decisions. For every successfully
generated candidate, admission replays the existing full-Cartesian Python
reference kernel over all ligand-receptor atom pairs. The only hard rejection
is the frozen binary64 rule `minimum_vdw_ratio < 0.55`, recorded as
`severe_receptor_penetration_min_vdw_ratio`.

Producer failures do not receive coordinates, geometric metrics, or rank
eligibility. An allocation-ineligible slot becomes `typed_allocation_failure`;
a generation-eligible slot with a producer failure becomes
`typed_proposal_generation_failure`. Both preserve their source failure code
and remain in the denominator. No fallback lane or slot reallocation exists.

The aggregate exact-pair bound is checked from generated-candidate, ligand,
and receptor denominators before the first metric traversal. Single-anchor
placement prechecks must have exactly the same metric receipt as the admission
replay.

## Receipt and execution boundary

Decision and batch projections are canonicalized once when their frozen
dataclasses are constructed. Receipt checks hash this immutable byte snapshot,
and `to_dict()` returns a decoded copy. This avoids repeatedly rebuilding the
same nested 64-slot evidence while preserving byte-identical receipts.

This component does not refine, score, rank, evaluate final pose validity, or
authorize an experiment. Reservation, molecular execution, D0/D1/Fresh,
product mutation, Stage 0, GitHub Actions production authority, public
benchmark, and scientific claims all remain false.

## Remaining downstream work

- operational proposal v3 now rederives complete source proposal identities and
  binds transformed coordinates to refiner-compatible `DockingProposal` state;
- bind a second geometric-admission decision to each post-refinement coordinate;
- execute Scorer V1 terms and pose validity from the exact admitted lineage;
- preserve all failure slots through rank/evidence recording;
- add an independent end-to-end verifier and attestation;
- obtain blocker-zero external one-shot authority before any molecular run.
