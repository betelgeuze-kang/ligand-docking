# Engine V2 mixed64 current-V7 post-admission v3

This synthetic-only stage consumes the exact operational fixed64 proposal batch,
executes the current `InteractionAwareTorsionContactEnsembleRefinerV7` once for
each materialized slot with the frozen 24-step budget, and immediately repeats
the full-Cartesian geometric admission on every successful refined coordinate.

The canonical policy is
`config/engine_v2_mixed64_v7_post_admission_v3.json`, with SHA-256
`7fdaff5b56fe9ddb0baebe60187f0ad067a2e54f7b6db9da9117440dee4d153d`.
It binds operational-proposal policy SHA-256
`9b028cc5ec0d32a6b28538d1a91955f2766fe796f488b38888fdd20819611d9a`.

## Frozen refinement boundary

- The caller supplies only the sealed operational batch and one exact V7
  refiner. There are no coordinate, score, validity, rank, threshold, outcome,
  reservation, or authority inputs.
- The operational batch is recursively checked before refinement, after all
  attempts, and after output finalization. Every materialized proposal index
  must equal its fixed64 slot.
- V7 torsion eligibility remains slot indices 24 through 43, and every
  materialized slot receives exactly one call with `max_steps=24`.
- A refiner with preexisting receipts, a different problem/profile, or an
  implementation source SHA that does not match the checked-out source fails
  before candidate execution.
- The refiner search space, receptor coordinates, receptor vdW radii, and ligand
  vdW radii must exactly match the geometric-admission context before execution.
- The source file is hashed before execution and again after the batch. A source
  change aborts the receipt.
- Only `TorsionContactRefinementError`, the declared numerical/domain failure,
  becomes a typed per-slot failure. Unexpected runtime/programming failures
  abort the call. Declared failures are not retried, replaced, or reallocated.

## Failure-complete post-admission

The output always retains all 64 slots in index order. Upstream nonmaterialized
slots remain explicit; successful V7 results preserve the complete V7 receipt
and proposal lineage; and every result is evaluated against every receptor atom
with the same minimum-vdW-ratio hard rejection at 0.55. Post-refinement rejected
slots remain in the denominator with the typed severe-penetration reason and
cannot enter ranking.

The batch checks the maximum exact pair work before any refiner call. Receipts
bind the input batch, V7 configuration, checked-out V7 source, per-slot source
and result identities, full geometric metrics, status, and rank eligibility.
Finalization recursively revalidates every source and result proposal tensor,
refinement receipt, metric, record projection, and the 64-slot batch. The same
check is available to the scoring/validity stage before it consumes the output.

## Authority boundary

This stage is executable only with synthetic test fixtures. It does not score,
evaluate PoseBusters validity, rank, reserve, run Historical/Fresh cohorts,
mutate product output, admit Stage 0, run public benchmarks, or authorize a
scientific claim. GitHub Actions and test doubles remain non-production
authorities.

The next implementation stage must derive complete Scorer V1 term receipts and
pose-validity evidence from only the accepted post-refinement records, while
preserving all 64 slots and preventing rejected or failed records from ranking.
