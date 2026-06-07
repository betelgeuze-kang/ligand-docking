# H1319 Clearance Adjudication

- target_name: Human astrovirus VA1 capsid spike - antibody 7C8 complex
- adjudication_status: `blocked_current_target_collision`
- operator_intake_status: `awaiting_input`
- replacement_required: `true`
- manual_native_search_required: `false`
- safe_to_apply_operator_intake: `false`
- blockers: `current_target_collision_blocks_native_candidate`
- next_action: replace this clearance target or provide independent operator proof that the candidate is not current-target leakage

## Candidate Signals

| status | query | pdb | release | collisions | blockers |
| --- | --- | --- | --- | --- | --- |
| `blocked_current_target_collision` | `relaxed` `Human astrovirus VA1 capsid spike` | `8UFN` | `2024-02-14` | `H2319` | `current_target_name_collision,relaxed_query_match_requires_operator_review,candidate_public_before_target_entry` |
| `blocked_current_target_collision` | `relaxed` `Human astrovirus VA1 capsid spike` | `8UFO` | `2024-02-14` | `H2319` | `current_target_name_collision,relaxed_query_match_requires_operator_review,candidate_public_before_target_entry` |

## Claim Boundary

Local CASP17 competitive-floor clearance adjudication only. It consolidates operator-intake and native-candidate risk signals into target-level next actions. It does not clear no-leak provenance, assert native identity, copy native files, score native accuracy, mutate operator intake, choose final targets, or submit to CASP.
