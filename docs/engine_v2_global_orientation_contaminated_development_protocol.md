# Fixed contaminated-development protocol for global orientation

## Status

This document defines a **protocol-only, execution-blocked** comparison between
the current V7 proposal arm and the deterministic global-orientation proposal
arm merged by PR #250.

It does not reserve or execute the historical A/B, open fresh-128, admit Stage
0, change the active profile, enable a product route, emit customer poses, or
support a public scientific claim.

Machine-readable protocol:

```text
config/engine_v2_global_orientation_contaminated_development.json
```

Protocol schema:

```text
betelgeuze.engine_v2_global_orientation_contaminated_development_protocol/1.1.0
```

Protocol self-hash:

```text
0e8591de97bd8313e748631f4e25222a62c017250b8fe64528eca2d1da0f4f68
```

## Scientific question

The historical failure atlas shows that local refinement cannot recover a pose
when the candidate set never contains a useful rigid-body placement. This
protocol therefore asks one bounded question:

> Under identical prepared ligand, pocket, scorer, validity, and candidate
> budgets, does deterministic global rigid-body proposal generation recover
> valid near-native proposals in previously uncovered historical cases?

The protocol separates proposal coverage, proposal validity, score ranking, and
selected Top-1 performance. A better selected score without a valid near-native
proposal is not a proposal success. A valid near-native proposal that is not
selected is a ranking failure, not a proposal failure.

## Fixed contaminated-development cohort

The protocol uses the exact historical nine-case source-paired cohort:

```text
5SD5_HWI
5SIS_JSM
6M2B_EZO
6M73_FNR
6T88_MWQ
6TW5_9M2
6TW7_NZB
6VTA_AKN
6WTN_RXT
```

The ordered roster SHA-256 is:

```text
cd2c24c9c7d937865f40352375e8a17c6b83b0b0fab8c134218d2c29537493c1
```

`6M73_FNR` is the fixed preparation-failure row. The other eight cases are
scored. `6T88_MWQ` is the baseline recovered case. The seven previously
uncovered cases are:

```text
5SD5_HWI
5SIS_JSM
6M2B_EZO
6TW5_9M2
6TW7_NZB
6VTA_AKN
6WTN_RXT
```

Failed preparation and failed candidate rows remain in every denominator.

## Source identity

The protocol is bound to the reviewed source-paired evidence identities:

| Item | Identity |
|---|---|
| Source commit | `754bebb9ddc2fbffdaca5d4143ff515c3b38c032` |
| Historical archive | `8bef33eba296989b795a11fd05a7e119124b066d91bec28a8b910d38a083fbcc` |
| Member manifest | `7f7f5273362a9457b022bc9b2b95c75625cdd259b1b1685aeb4b57d41d985e21` |
| Bundle checksum | `6ee04e23e01a73bb643bb4d1fde240e06fd2916ea085e3652c11e2428bd432a9` |
| Phase 2.5 policy | `b4c5530dc4766500dbbc854875cfb39baadad94196c63be6150514879993d211` |
| Synthetic global-orientation contract | `02fa37a94f3c1719f5e7b5b808c71d053e313b018ef9bfa7d904869c2ab1dad0` |

The repository does not commit the private molecular source receipts. Their
absence is an execution blocker, not a value to be defaulted.

Before any later execution authority can be considered, each case must provide a
complete source receipt binding case identity, archive-member receipt,
authenticated input receipt, receptor and ligand coordinate identities, ligand
topology identity, pocket declaration identity, and preparation-policy identity.
This binds exact structures and declarations without copying private molecular
material into the repository.

## Information boundary

The experimental generator may consume only prepared ligand coordinates,
declared pocket center and normal, bounded receptor surface points, the frozen
generator configuration, the exact source-receipt identity, and the frozen
profile identity.

It may not consume native or reference pose, RMSD, candidate score, prior
benchmark outcome, fresh-holdout identity, or product-routing state. Reference
poses are available only to the post-generation evaluator. Candidate allocation
after seeing any result is forbidden. The verifier also checks the live
generator signature for forbidden input paths.

## Equal arm contract

Both arms use the same prepared ligand, pocket declaration, scorer backend,
scoring terms, validity and PoseBusters contracts, symmetry-aware RMSD contract,
deterministic execution seed, and exactly 64 candidate slots per scored case.

The baseline arm uses the current V7 proposal authority. The experimental arm
uses:

```text
generator_id = deterministic_surface_aware_rigid_v2
profile_id = deterministic_surface_aware_rigid_v2
orientation_count = 8
translation_shell_radii = [1.5]
translation_points_per_shell = 7
minimum_receptor_distance = 1.1
```

The exact denominator is:

```text
8 × (1 + 1 × 7) = 64 candidates per scored case
```

Therefore each arm has 512 scored candidate rows and the combined comparison has
1,024 scored candidate rows. Receptor-clash rejection does not remove a slot
from the denominator.

Validity is exact, not count-only: PoseBusters 0.3.1 must use the pinned
22-check set
`3b4797c8eb95f6471f3dce0977b95b83fd0ed2630d6079607609fbcb2c1d8b93`,
the full check map, evidence schema
`betelgeuze.engine_v2_source_paired_clearance_posebusters_evidence/2.0.0`,
and internal-validity check-set identity
`dcab24089ac9c88daa53f3faeabd04d71fb819cbbe9f86982d964b657cbc5583`.

## Required metrics

Every scored case must report proposal-oracle RMSD, valid-proposal-oracle RMSD,
score-ranked Top-1 and Top-5 oracle RMSD, selected Top-1 RMSD, selection regret,
generated/accepted/rejected candidate counts, and one mutually exclusive failure
class:

```text
success
proposal_failure
validity_failure
ranking_failure
```

Complete source geometry and every candidate observation must be retained so the
batch and report can be independently regenerated. Summary-only or hash-only
evidence is insufficient.

## Predeclared decision

The decision rules are frozen below, but no executable decision evaluator or Go
receipt issuer is implemented. Current repository evidence types cannot yet
prove all required ligand-coordinate, ligand-topology, pocket-declaration, and
preparation-policy identities; bind each oracle observation to its concrete
baseline or experimental candidate lineage; or retain an explicit unscored
state for every failed slot. Treating a digest label or caller-set completeness
boolean as that evidence is forbidden.

Before an evaluator can be reviewed, repository types must provide all four
machine-verifiable contracts:

1. a case-source receipt containing the ligand, topology, pocket, and
   preparation identities plus receptor-surface points rederived from the bound
   receptor geometry by a frozen extraction procedure;
2. baseline candidate lineage bound to all 64 observation slots;
3. experimental candidate lineage bound to all 64 observation slots; and
4. failure-complete observations with an explicit unscored state.

Until then,
`decision_evaluator_implemented = false` and
`go_receipt_emission_authorized = false`. Missing oracle, selected RMSD, or
score values must eventually remain explicit failure observations rather than
parser errors or invented finite values.

A development Go requires every invariant and both criteria. In particular:

1. the baseline arm reproduces the fixed recovered `6T88_MWQ` Top-1 result;
2. valid-proposal-oracle recovery in at least two of seven previously uncovered
   cases; and
3. no increase in the invalid selected-Top-1 count.

Hard No-Go triggers include any required invariant failure, zero new valid
proposal recovery, regression of the baseline recovered case, or denominator or
source-binding drift. One recovered case is not enough because it fails the
breadth criterion.

Even a Go permits only a separate review of a later development follow-up. It
does not authorize execution, fresh data, Stage 0, product routing, customer
poses, profile promotion, or claims.

## Execution gate

Actual execution remains false. A future execution authority would require all
of the following:

1. PR #245 remains in its reviewed terminal state;
2. complete source receipts exist for all nine cases;
3. a separate execution-authority contract is reviewed;
4. an operator reservation is durably recorded;
5. exact-head CI is green; and
6. independent scientific and security review is complete.

The reserved output boundary is:

```text
.betelgeuze/engine_v2_global_orientation_contaminated_development
```

Directories must be mode `0700`; receipts must be mode `0600`.

## Authority boundary

```text
historical_development_execution_authorized = false
fresh_holdout_execution_authorized = false
stage0_admission_authority = false
profile_promotion_authority = false
product_execution_authorized = false
customer_pose_emission_authorized = false
public_or_scientific_claim_authorized = false
```

This protocol freezes the next scientific question and its evidence rules. It
does not answer that question.
