# GPCR Hard-Decoy Suite Contract (DRD2 / HTR2A / OPRM1)

Status: reference. Priority 4 of the product-vision roadmap. Formalizes the
broad-GPCR claim blocker into one measurable benchmark contract.

Source of truth:
- Gate/evaluator: `betelgeuze_product/gpcr_hard_decoy_suite.py` (dep-free)
- Diagnostics inputs: `runs/gpcr_ci_low_recovery_packet_*`,
  `runs/gpcr_guarded_100k_rank_failure_diagnostics_*`, `runs/gpcr_drd2_*`
- Claim wording: `.kiro/steering/claim_safe_wording.md`,
  `docs/BENCHMARK_LEDGER_CURRENT.md` (`broad_family_locked` scope)

## Why

Broad GPCR/router generalization is the repo's main ranking blocker. The
evidence is real but scattered across many diagnostic artifacts. This contract
collapses it into a single, auditable gate so "is broad GPCR claimable yet?" has
one answer, and so the failure has a measurable, named shape.

## Claim gate (fail-closed)

Per target, both must hold:
- `ranking_pr_auc_ci_low >= 0.45`
- `top20_hit_rate >= 0.20`

Plus target-internal decoy separation:
- `decoys_above_positive_count == 0`
- the positive must not be out-anchored: if both anchor distances are present,
  `top_decoy_anchor_distance_a >= positive_anchor_distance_a`.

A target is `green` only when it has zero blockers. The **broad GPCR/router
family claim is locked** until every required target (default DRD2, HTR2A,
OPRM1) is green. No threshold relaxation, no target-identity feature, no fake
pass.

## Hard-decoy taxonomy (`decoy_class`)

| class | meaning |
| --- | --- |
| `over_anchored` | decoy sits closer to the native anchor than the positive (DRD2 Asp114 case) |
| `same_signature` | decoy shares the positive's feature signature (OPRM1 157-decoy case) |
| `multipolar` | multipolar/basic decoy promoted by polar reward |
| `pose_distorted_valid_anchor` | valid anchor but distorted pose |
| `valid_anchor_challenge` | legitimate competing anchor |
| `generic` | ordinary decoy |

## Root-cause tags

`donor_prior_decoy_intrusion`, `weak_contact_prior_mismatch`,
`affinity_hint_md_support_mismatch`, `same_signature_no_discriminator`,
`anchor_separation_insufficient`. Tags are derived from decoy-class counts and
anchor separation so the next scorer work has a named target.

## Per-target row inputs

`build_target_hard_decoy_assessment(row)` requires `target_id`,
`positive_count`; optional `ranking_pr_auc`, `ranking_pr_auc_ci_low`,
`top20_hit_rate`, `decoys_above_positive_count`, `positive_target_rank`,
`positive_anchor_distance_a`, `top_decoy_anchor_distance_a`,
`decoy_class_counts`.

## Family rollup

`build_gpcr_hard_decoy_suite(targets, required_target_ids=...)` returns a family
decision: `family_claim_safe`, `green_target_ids`, `blocked_target_ids`,
`missing_required_target_ids`, and `first_blocked_required_target` for operator
focus. Status is `gpcr_hard_decoy_family_ready` or `broad_family_locked`.

## Out of scope

- Scoring, decoy generation, and pose/anchor computation run under numpy/RDKit/
  GPU/CI. This layer evaluates aggregate rows and decides claim status only.
- Clearing this suite is necessary but, per the benchmark ledger, broad
  GPCR/router product wording stays locked until the family rollup is green.
