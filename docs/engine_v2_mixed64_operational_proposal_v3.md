# Engine V2 mixed64 operational proposal v3

The operational proposal bridge converts each pre-refinement admitted mixed64
record into the exact `DockingProposal` state required by V7 refinement,
Scorer V1, and pose validity. It consumes only the sealed geometric-admission
v3 batch; callers cannot supply replacement coordinates, proposal
fingerprints, candidate IDs, scores, results, or authority.

The canonical policy is
`config/engine_v2_mixed64_operational_proposal_v3.json`, with SHA-256
`9535730901a27ab3009e7b6fff12e532dd5d995e8fa33a038f4d321593885de9`.
It binds geometric-admission v3 policy SHA-256
`feb9c00eb71bb45fe07479c6f5b8e6faa171b9968fa4dbb2370e518c71290526`.

Source proposal identity payloads remain capped at 4 MiB. Complete sealed
operational evidence receipts use a separate 128 MiB fail-closed ceiling so a
valid fixed64 admission payload is not rejected by the smaller identity limit.

## Exact source reconstruction

Every source payload must be the canonical identity projection for
`betelgeuze.engine_v2_docking_proposal/3.0.0`, using numeric policy
`betelgeuze.engine_v2_proposal_numeric_identity/1.0.0` and binary64 tensors.
The bridge rederives its SHA, coordinate fingerprint, problem identity,
search-space identity, torsion state, transform, seed, and optional refinement
lineage by constructing the exact `DockingProposal` type.
The complete admission decision, metric, producer, and source hierarchy is
recursively checked before materialization, after all 64 records, and after
batch finalization. The final check also revalidates every emitted operational
proposal tensor and record projection; persistent live-field mutation aborts
the whole call.

Historical payloads that contain only a narrative or legacy proposal identity
are not guessed or discarded. Every admitted dependent slot receives
`source_proposal_identity_not_operational`, retains its slot in the 64-record
batch, and contains no fabricated operational proposal.

## Transformed proposal identity

Every materialized proposal uses its fixed64 slot as its operational proposal
index. The exact source proposal remains separately preserved; this is
especially important for retained control slots 60--62, whose source proposal
indices are 36, 45, and 54. Exact pass-through lanes preserve source
coordinates and the source rigid transform. For indexed SO(3) and single-anchor
lanes, the bridge:

- composes the source transform followed by the placement transform using
  row-vector semantics, `R_out = R_place @ R_source` and
  `t_out = t_source @ R_place.T + t_affine`;
- treats the indexed SO(3) receipt translation as its declared target centroid
  and rederives `t_affine = target_centroid - source_centroid @ R_place.T`;
- reuses the single-anchor receipt translation as its conventional affine
  translation;
- numerically reproduces the producer output coordinates;
- preserves source torsion, problem, and search-space state;
- uses the fixed64 slot as the transformed proposal index;
- derives a source-bound, result-independent seed;
- derives both candidate ID and proposal fingerprint internally.

Only declared proposal/materialization domain errors become typed per-slot
failures. Unexpected runtime errors abort the materialization call instead of
being relabeled as scientific slot evidence.

The receipt preserves both the producer's evidence proposal/coordinate hashes
and the operational `DockingProposal`/coordinate fingerprints. The batch rejects
mixed problem or search-space identities.

## Authority boundary

This bridge materializes identity only. It does not call a refiner, scorer,
validity evaluator, molecular case, reservation service, Historical/Fresh
cohort, product rank, Stage 0 gate, public benchmark, or HIP backend. Producer
attestation and activation eligibility remain false.

The next implementation stage must execute the frozen V7 refiner from these
exact proposals, replay geometric admission on every post-refinement coordinate,
and preserve typed refinement failures before Scorer V1 or validity is called.
