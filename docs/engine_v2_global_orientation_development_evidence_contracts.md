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

- the archive-member and authenticated-input receipt identities;
- complete receptor and ligand coordinates with canonical binary64 identities;
- ligand topology, pocket declaration, and preparation-policy identities;
- the exact pocket center, normal, and binary64 radius;
- the validity-config fingerprint independently rederived from that radius and
  the immutable public-redocking validity fields;
- evaluation-pipeline, native-extension, and scorer-backend receipt identities;
- Python executable, Python shared library, and `libm` payload identities plus
  their independently rederived combined runtime fingerprint; and
- a canonical ordered receptor atom-index projection whose surface points are
  rederived directly from the retained receptor coordinates.

The ninth cohort member, `6M73_FNR`, remains in the denominator through
`GlobalOrientationDevelopmentPreparationFailureReceiptV1`. It has a typed
preparation failure and zero candidate rows; it cannot be silently omitted or
relabeled as a scored case.

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
or overlong lineages fail closed. The arm-level authority digest binds the exact
baseline lineage authority or experimental generator batch outside the slot
rows.

## Failure-complete observations

`GlobalOrientationDevelopmentObservationSlotV1` binds one observation to one
lineage-slot receipt and repeats the case, arm, index, candidate, proposal, and
coordinate identities for independent cross-wire checks.

Score, validity, and RMSD have separate explicit state machines:

- score: `scored` or `unscored`;
- validity: `evaluated` or `not_evaluated`; and
- RMSD: `evaluated` or `not_evaluated`.

A successful slot requires the exact full
`SourcePairedClearanceCandidateEvidenceV1` object, including complete ScorerV1
terms, internal validity checks, PoseBusters check map, and RMSD evidence; receipt
digests alone are not accepted. Every other state requires a typed failure. A
failed generation cannot carry downstream evidence. Missing values therefore
remain observations rather than disappearing from the denominator or becoming
invented finite values.

`GlobalOrientationDevelopmentArmObservationsV1` requires a one-to-one binding
between all 64 lineage slots and all 64 observations. It reports generated,
scored, and unscored counts without evaluating the frozen Go/No-Go criteria.

## Remaining boundary

The fixed protocol still has no decision evaluator and no Go receipt issuer.
Before either could be reviewed, separately authorized private evidence would
have to instantiate these contracts for every required case and arm, while all
existing operational blockers and the historical one-shot reservation gate
remain satisfied. This repository change neither performs nor authorizes that
work.
