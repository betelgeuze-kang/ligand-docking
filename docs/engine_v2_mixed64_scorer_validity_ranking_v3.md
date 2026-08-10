# Engine V2 mixed64 Scorer V1, validity, and ranking v3

This synthetic-only stage consumes the exact current-V7 post-admission fixed64
batch. It sends only post-refinement geometrically accepted states to the frozen
Python-reference Scorer V1, retains every complete eight-term receipt, evaluates
element-aware pose validity from the scorer's authenticated authority, and
derives stable primary and valid-only ranks.

The canonical policy is
`config/engine_v2_mixed64_scorer_validity_ranking_v3.json`, with SHA-256
`dfaec532a6eacc5f268f69e98788a7c63620659063cf0719f8d865c0817568eb`.
It binds V7 post-admission policy SHA-256
`b23d517b1b5d477129670c70fd9894219f14eb5f7bdb4ab06805ff0243e93beb`.

## Complete scoring semantics

- The exact default `ChemistryPoseScorerV1` configuration and default
  Python-reference backend options are frozen by fingerprint.
- Accepted proposals are passed through one batch call when the accepted set is
  non-empty. Each accepted slot receives one outcome and no retry.
- A successful row preserves typed vdW, electrostatics, directional H-bond,
  hydrophobic contact, desolvation proxy, torsion energy, ligand strain, weak
  pocket prior, total score, exact pair/contact counts, and the complete
  `ScorerV1Terms` receipt.
- The total is independently rederived from all eight terms. Scalar score,
  proposal identity, authority receipt, scorer context/config, and backend
  receipt must agree exactly.

## Validity and rank semantics

Each successfully scored state receives one call to the exact
`ElementAwarePoseValidityContext` owned by the scorer authority. Complete valid,
complete invalid, incomplete, and evaluator-failure outcomes remain distinct.
A validity failure or incomplete result does not discard its complete score.

Primary rank includes every complete score receipt, including pose-invalid and
validity-unavailable rows. It sorts total score ascending, then fixed64 slot,
then result proposal identity. The valid-only view filters that same order to
complete validity `true`; it does not rerank with another score. Top-1 and Top-5
membership therefore rederive from the archived score, term, validity, and rank
evidence rather than from historical narrative rows.

## Failure and authority boundary

All 64 source slots remain present. Upstream rejections/failures are never sent
to the scorer, scorer failures are not retried, and validity failures preserve
their score without gaining valid-rank eligibility.

This stage uses synthetic fixtures only. It grants no reservation, molecular
cohort, Historical A/B, Fresh-128, product rank mutation, customer pose
emission, Stage 0, public benchmark, HIP, or scientific-claim authority.
