# Engine V2 global-orientation contaminated-development protocol

## Status

This document freezes the first molecular development protocol for deterministic
global-orientation proposals. It is a **protocol-only, non-executing** artifact.

```text
historical_execution_authorized = false
fresh_holdout_execution_authorized = false
stage0_admission_authority = false
profile_promotion_authority = false
product_execution_authorized = false
customer_pose_emission_authorized = false
public_or_scientific_claim_authorized = false
```

The protocol does not reserve or consume the historical one-shot A/B, open
fresh-128, change V7, or support a product or scientific claim.

## Frozen cohort

The protocol uses the existing source-paired historical contaminated-development
cohort:

```text
5SD5_HWI
5SIS_JSM
6M2B_EZO
6M73_FNR  # retained preparation failure
6T88_MWQ  # existing baseline recovery
6TW5_9M2
6TW7_NZB
6VTA_AKN
6WTN_RXT
```

Eight cases are scored. `6M73_FNR` remains a typed preparation-failure row.
The seven cases other than `6T88_MWQ` are the previously uncovered breadth
cohort. Exact case-source receipts are mandatory; a case identifier alone is not
source evidence.

The protocol binds:

- Phase 2.5 policy `1.3.0`;
- source-paired activation policy `1.2.0`;
- the historical archive identity;
- the historical case-source authority;
- the global-orientation synthetic contract `1.1.0`;
- scorer-v1 terms schema `1.1.0`; and
- PoseBusters `0.3.1`.

## Arm equality

Both arms retain exactly 64 candidate slots for each scored case and 512 slots
in total.

### Baseline

```text
arm_id = current_v7_frozen
proposal_policy = current_v7_source_paired_frozen
slots_per_scored_case = 64
```

### Experimental

```text
arm_id = global_orientation_v1_frozen
generator_id = deterministic_surface_aware_rigid_v1
orientation_count = 16
translation_shell_radii_angstrom = [2.0]
translation_points_per_shell = 3
minimum_receptor_distance_angstrom = 1.1
```

The denominator is independently rederived as:

```text
16 × (1 + 1 × 3) = 64 candidates per scored case
64 × 8 = 512 candidates
```

The center placement is retained, followed by three deterministic shell
placements for each orientation. Receptor-clash rejections remain in the
denominator.

The arms must share preparation, conformer inputs, pocket declaration, charge
policy, scorer backend, and candidate denominator.

## Information boundary

The proposal generator may consume only ligand coordinates, pocket center,
pocket normal, optional receptor-surface points for the bounded clash prefilter,
and the frozen generator configuration.

The generator must not consume:

- a native or reference pose;
- RMSD;
- a prior score;
- a benchmark outcome;
- fresh-holdout identity; or
- product-routing state.

Reference coordinates are available only to the post-generation evaluator.

## Required evidence and metrics

Every preparation and candidate slot is retained. Complete source geometry must
rederive every global-orientation slot, and every candidate observation must
rederive the evaluation report.

Per case, the report must include:

- proposal oracle;
- valid proposal oracle;
- score-ranked Top-1 and Top-5 oracle;
- selected Top-1;
- selection regret;
- rejected-candidate count; and
- one failure class: `success`, `proposal_failure`, `validity_failure`, or
  `ranking_failure`.

The RMSD decision threshold is frozen at `2.0 Å`.

A summary-only hash is not sufficient evidence. The eventual molecular artifact
format must preserve exact case-source receipts, complete candidate receipts,
full scorer terms, internal validity, the full PoseBusters map, RMSD evidence,
and deterministic ranking.

## Decision rule

A development Go requires every invariant:

1. exact case-source receipt coverage;
2. equal arm denominators;
3. no preparation-failure regression;
4. no reference- or result-dependent generator input;
5. failure-complete candidate rows;
6. independently rederived metrics; and
7. no regression of the existing `6T88_MWQ` baseline recovery.

It also requires at least one primary criterion:

1. a selected exact-valid recovery in a previously uncovered case;
2. proposal-oracle recovery in at least two of eight scored cases; or
3. valid-proposal-oracle recovery in at least two of eight scored cases.

Hard No-Go precedence applies to invariant failure, failure of all primary
criteria, regression of the baseline-recovered case, denominator mismatch, or
detected reference/result leakage.

Execution stops immediately on source-identity mismatch, denominator mismatch,
reference leakage, or non-rederivable evidence.

## Relationship to PR #245

Actual molecular execution remains blocked until PR #245 reaches a reviewed
terminal state or a later scientific-governance decision explicitly supersedes
that dependency. This protocol itself provides no reservation, run-start,
runner, or result writer.

## Promotion boundary

A development Go would mean only that this fixed contaminated-development
experiment met its predeclared criteria. It would not authorize fresh data,
Stage 0, profile promotion, product routing, customer pose output, public
benchmark wording, or a scientific accuracy claim.
