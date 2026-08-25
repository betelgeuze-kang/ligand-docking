# Global-orientation contaminated-development evidence contracts

## Status

`betelgeuze_engine_v2/benchmark/global_orientation_development_contracts.py`
defines the repository-side data contracts required before the fixed
global-orientation development protocol can receive an evaluator.

The module contains no molecular loader, proposal generator, scorer, evaluator,
reservation client, output writer, or execution entry point. Constructing a
receipt seals caller-supplied observations only. Every receipt keeps historical,
Fresh-128, Stage 0, profile-promotion, product, customer-pose, and public/scientific
authority false.

## Source contract

`GlobalOrientationDevelopmentCaseSourceReceiptV1` is limited to the eight scored
members of the fixed historical cohort. It retains:

- the exact authenticated historical case-source receipt, including its frozen
  archive member, native pose, receptor artifact, and current-V7 lineage;
- the exact authenticated docking problem, canonical receptor and ligand
  molecular systems serialized as independently loadable canonical documents,
  and concrete ScorerV1 context;
- the pinned historical archive, member-manifest, and bundle identities;
- complete receptor and ligand coordinates with canonical binary64 identities;
- proof that those coordinates and the ligand topology equal the authenticated
  molecular systems selected by the historical input receipt;
- ligand topology, pocket declaration, and preparation-policy identities;
- the exact pocket center, normalized normal, and binary64 radius, with the
  pocket declaration identity rederived over that geometry and historical case;
- the validity-config fingerprint independently rederived from that radius and
  the immutable public-redocking validity fields;
- the frozen evaluation-pipeline identity plus the concrete scorer-backend
  receipt, whose receipt and embedded native-extension identities must exactly
  equal the repeated scorer runtime identities and whose backend, options, and
  live-rederived aggregate Python/native implementation manifest must match the
  frozen CPU profile;
- a generator-source receipt rederived only from a sanitized authenticated-input
  projection, prepared ligand, pocket geometry, and authenticated receptor
  subset; the sanitized projection excludes the full input-receipt digest and
  the native-backed pocket source and implementation identities; and
- the exact receptor atom subset selected by the authenticated validity context,
  whose points are rederived directly from retained receptor coordinates rather
  than accepted as a caller-selected surface subset.

The ninth cohort member, `6M73_FNR`, remains in the denominator through a pinned
`GlobalOrientationDevelopmentHistoricalFailureAuthorityV1` owned by
`GlobalOrientationDevelopmentPreparationFailureReceiptV1`. Its archive,
manifest, bundle, cohort, Phase 2.5 policy, and historical engine receipt are
constants rather than caller-supplied digests. It has a typed preparation
`unsupported_large_ring_system` failure and zero candidate rows; it cannot be
silently omitted, relabeled as a scored case, or substituted with a new parser
or runtime regression.

These contracts can represent future private receipts. They do not populate the
currently absent per-case fingerprints or runtime artifacts in the public
protocol, and they do not accept caller-declared runtime digests as evidence.
The protocol's unbound-runtime gate therefore remains closed.

## Exact arm lineage

`GlobalOrientationDevelopmentArmLineageReceiptV1` requires exactly 64 ordered,
unique slots for one prepared case and one of the two frozen arms:

```text
baseline_current_v7
experimental_global_orientation_v1
```

Each `GlobalOrientationDevelopmentLineageSlotV1` is either `generated`, with
proposal, coordinate, and generation-receipt identities, or `failed`, with only
a typed generation failure. Cross-case, cross-arm, reordered, duplicate, short,
or overlong lineages fail closed. A digest alone is not accepted: the baseline
arm must own the exact `SourcePairedClearanceCurrentV7LineageReceiptV1`, while
the experimental arm must own the exact `GlobalOrientationBatch`. The
experimental batch is deterministically regenerated from the retained ligand,
authenticated receptor subset, pocket, frozen config, permitted-input source
receipt, and profile; the supplied batch must equal that regenerated document.
The seed projection excludes the nested historical/native-pose receipt, the
native-backed pocket source identity, and unbound runtime metadata. Every slot
is then rederived from the regenerated
authority, including transforms,
coordinates, minimum receptor distance, generated/failed state, proposal and
coordinate identity, generation receipt, and failure code.

Each accepted experimental slot is also materialized as an exact
`DockingProposal` using the authenticated problem/search-space identities, a
source-seed-derived bounded integer seed, the slot rigid transform and
coordinates, and zero torsion deltas. Because generation rotates centered
ligand coordinates, the proposal records the equivalent affine translation
`slot target - ligand centroid @ rotation.T` and verifies that applying the
stored transform to the original ligand reproduces the bound coordinates. The
lineage's proposal and coordinate fingerprints come from that scorer-compatible
object. The distinct
`GlobalOrientationSlot` receipt remains the generation receipt, so generator
lineage is not mislabeled as scorer proposal authority.

## Failure-complete observations

`GlobalOrientationDevelopmentObservationSlotV1` binds one observation to one
lineage-slot receipt and repeats the case, arm, index, candidate, proposal, and
coordinate identities for independent cross-wire checks.

Score, validity, and RMSD have separate explicit state machines:

- score: `scored` or `unscored`;
- validity: `evaluated` or `not_evaluated`; and
- RMSD: `evaluated` or `not_evaluated`.

Internal validity and PoseBusters are retained independently if one evaluator
completes before the other fails. The combined validity status remains
`not_evaluated` until both receipts exist; neither completed result is discarded.

A fully successful slot requires the exact full
`SourcePairedClearanceCandidateEvidenceV1` object, including complete ScorerV1
terms, internal validity checks, PoseBusters check map, and RMSD evidence; receipt
digests alone are not accepted. If scoring succeeds but a later evaluator fails,
`GlobalOrientationDevelopmentPartialCandidateEvidenceV1` retains every completed
stage and its raw-score rank alongside a typed failure; it cannot be collapsed
to an invented `unscored` row. A failed generation cannot carry downstream
evidence. Missing values therefore remain observations rather than disappearing
from the denominator or becoming invented finite values.
Generated-row failure codes come from frozen per-stage allowlists and must match
the first incomplete stage: scorer failure/backend/timeout/non-finite codes for
scoring; evaluator/internal-validity/PoseBusters failure or timeout codes for
validity; and RMSD failure/mapping/timeout codes after both validity evaluators
complete.

`GlobalOrientationDevelopmentArmObservationsV1` requires a one-to-one binding
between all 64 lineage slots and all 64 observations. It checks candidate scorer,
validity, PoseBusters, RMSD, native-pose, receptor, and authenticated-input fields
against the case and frozen evaluator bindings. Scorer terms must also match the
concrete prepared-case ScorerV1 context. Partial evaluator stages must describe
one pose artifact, and PoseBusters/RMSD stages must share one report. Raw score ranks are independently
rederived from `(total_score, proposal_index)`. It reports generated, scored, and
unscored counts without evaluating the frozen Go/No-Go criteria.

## Exact per-arm metrics

`betelgeuze_engine_v2/benchmark/global_orientation_development_metrics.py`
defines `GlobalOrientationDevelopmentArmMetricsV1`. It accepts only an exact
`GlobalOrientationDevelopmentArmObservationsV1` object and owns that full
64-slot receipt in its output. It rederives proposal and valid-proposal oracles,
score-ranked Top-1/Top-5 oracles, selected Top-1 evidence, selection regret,
candidate counts, typed failure-code counts, and the mutually exclusive failure
class directly from retained complete or partial observations. Caller-supplied
summary values and digest-only substitutes are not inputs.

A generation-failure slot remains a complete observed failure. A generated slot
with only partial downstream evidence remains visible but makes
`metric_evidence_complete = false`; absent validity or RMSD is never converted
to an invented finite value. Unknown selected validity and success remain null,
and the receipt withholds the definitive failure class until metric evidence is
complete. The metrics receipt cannot evaluate the cohort
decision or issue execution, Go, promotion, product, Fresh-128, Stage 0, or
claim authority.

## Remaining boundary

The fixed protocol now has an exact per-arm metrics evaluator, but still has no
cohort decision evaluator and no Go receipt issuer.
Before either could be reviewed, separately authorized private evidence would
have to instantiate these contracts for every required case and arm, while all
existing operational blockers and the historical one-shot reservation gate
remain satisfied. This repository change neither performs nor authorizes that
work.
