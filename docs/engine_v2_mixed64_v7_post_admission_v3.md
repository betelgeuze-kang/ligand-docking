# Engine V2 mixed64 current-V7 post-admission v3

This synthetic-only stage consumes the exact operational fixed64 proposal batch,
executes the current `InteractionAwareTorsionContactEnsembleRefinerV7` once for
each materialized slot with the frozen 24-step budget, and immediately repeats
the full-Cartesian geometric admission on every successful refined coordinate.
Both Python execution components are independent verifier oracles only; neither
is a native or product execution fallback.

The canonical policy is
`config/engine_v2_mixed64_v7_post_admission_v3.json`, with SHA-256
`e19f58ea6015d4695fb8aab7015d0162f6fa359da9627dd6ea8739d6bd20a8a9`.
It binds operational-proposal policy SHA-256
`9535730901a27ab3009e7b6fff12e532dd5d995e8fa33a038f4d321593885de9`.
The post-refinement gate also binds geometric-admission v3 policy SHA-256
`feb9c00eb71bb45fe07479c6f5b8e6faa171b9968fa4dbb2370e518c71290526`.
Complete V7 evidence uses a separate 256 MiB canonical receipt ceiling so it
can contain a valid 128 MiB-bounded operational receipt without narrowing the
upstream contract.

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
- The source file must be a non-symlink regular file no larger than 8 MiB. One
  no-follow descriptor is checked before and after each bounded read; the source
  is hashed before execution, after the batch, and after finalization. An
  identity, metadata, size, or content change aborts the receipt.
- Only `TorsionContactRefinementError`, the declared numerical/domain failure,
  becomes a typed per-slot failure. Unexpected runtime/programming failures
  abort the call. The exact bounded UTF-8 failure reason is retained with its
  SHA-256. Declared failures are not retried, replaced, or reallocated.

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
The result lineage must name the exact V7 refiner ID and version, and the summed
pair count must equal successful slots × ligand atoms × receptor atoms.
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
