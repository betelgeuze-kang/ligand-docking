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
  molecular systems, and concrete ScorerV1 context;
- the pinned historical archive, member-manifest, and bundle identities;
- complete receptor and ligand coordinates with canonical binary64 identities;
- proof that those coordinates and the ligand topology equal the authenticated
  molecular systems selected by the historical input receipt;
- ligand topology, pocket declaration, and preparation-policy identities;
- the exact pocket center, normalized normal, and binary64 radius, with the
  pocket declaration identity rederived over that geometry and historical case;
- the validity-config fingerprint independently rederived from that radius and
  the immutable public-redocking validity fields;
- the frozen evaluation-pipeline identity plus native-extension and
  scorer-backend receipt identities;
- Python executable, Python shared library, and `libm` payload identities plus
  their independently rederived combined runtime fingerprint; and
- a canonical ordered receptor atom-index projection whose surface points are
  rederived directly from the retained receptor coordinates.

The ninth cohort member, `6M73_FNR`, remains in the denominator through a pinned
`GlobalOrientationDevelopmentHistoricalFailureAuthorityV1` owned by
`GlobalOrientationDevelopmentPreparationFailureReceiptV1`. Its archive,
manifest, bundle, cohort, Phase 2.5 policy, and historical engine receipt are
constants rather than caller-supplied digests. It has a typed preparation
failure and zero candidate rows; it cannot be silently omitted or relabeled as
a scored case.

These contracts can represent future private receipts. They do not populate the
currently absent per-case fingerprints or runtime artifacts in the public
protocol, and they do not make those absent identities available.

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
the experimental arm must own the exact `GlobalOrientationBatch`. Every slot is
rederived from that concrete authority receipt, including generated/failed
state, proposal and coordinate identity, generation receipt, and failure code.

## Failure-complete observations

`GlobalOrientationDevelopmentObservationSlotV1` binds one observation to one
lineage-slot receipt and repeats the case, arm, index, candidate, proposal, and
coordinate identities for independent cross-wire checks.

Score, validity, and RMSD have separate explicit state machines:

- score: `scored` or `unscored`;
- validity: `evaluated` or `not_evaluated`; and
- RMSD: `evaluated` or `not_evaluated`.

A fully successful slot requires the exact full
`SourcePairedClearanceCandidateEvidenceV1` object, including complete ScorerV1
terms, internal validity checks, PoseBusters check map, and RMSD evidence; receipt
digests alone are not accepted. If scoring succeeds but a later evaluator fails,
`GlobalOrientationDevelopmentPartialCandidateEvidenceV1` retains every completed
stage and its raw-score rank alongside a typed failure; it cannot be collapsed
to an invented `unscored` row. A failed generation cannot carry downstream
evidence. Missing values therefore remain observations rather than disappearing
from the denominator or becoming invented finite values.

`GlobalOrientationDevelopmentArmObservationsV1` requires a one-to-one binding
between all 64 lineage slots and all 64 observations. It checks candidate scorer,
validity, PoseBusters, RMSD, native-pose, receptor, and authenticated-input fields
against the case and frozen evaluator bindings. Scorer terms must also match the
concrete prepared-case ScorerV1 context. Partial evaluator stages must describe
one pose artifact, and PoseBusters/RMSD stages must share one report. Raw score ranks are independently
rederived from `(total_score, proposal_index)`. It reports generated, scored, and
unscored counts without evaluating the frozen Go/No-Go criteria.

## Remaining boundary

The fixed protocol still has no decision evaluator and no Go receipt issuer.
Before either could be reviewed, separately authorized private evidence would
have to instantiate these contracts for every required case and arm, while all
existing operational blockers and the historical one-shot reservation gate
remain satisfied. This repository change neither performs nor authorizes that
work.
