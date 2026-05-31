# CASP17 Active Scope Decision

- generated: `2026-05-31T16:50:09+09:00`
- scope decision: `casp17_only`
- CASP17 continuation: `active`
- CASP17 priority: `historical_benchmark_then_competitive_floor`
- CAPRI Round 65 participation: `deferred_pi_required`
- CAPRI hold reason: `operator_not_pi_capri_registration_requires_pi_or_research_group_lead`
- CAPRI artifact policy: `preserve_context_no_registration_no_submission`
- next action: clear historical non-CASP17 target identity, no-leak provenance, native files, and prediction files

## Lane Policy

| lane | status | priority | reason | next action |
| --- | --- | ---: | --- | --- |
| `casp17_historical_benchmark` | `active` | 1 | `required_to_raise_scaffold_score_from_65_to_90` | clear historical non-CASP17 target identity, no-leak provenance, native files, and prediction files |
| `casp17_competitive_floor` | `active` | 2 | `required_to_raise_competitive_proof_from_15_25_to_85_90` | fill the 15-row competitive-floor batch after cleared historical identities are available |
| `casp17_3d_object_library` | `active` | 3 | `required_for_per-object_review_and_submission_readiness` | keep per-protein folders, per-chain viewers, projections, and audits green |
| `capri_round65` | `deferred_pi_required` | 0 | `operator_not_pi_capri_registration_requires_pi_or_research_group_lead` | preserve CAPRI artifacts as context only until a PI or research-group lead confirms registration |

## Claim Boundary

Local scope-decision packet only. It records operator participation scope for CASP17/CAPRI planning, does not register for CASP or CAPRI, does not submit models, and does not claim official performance.
