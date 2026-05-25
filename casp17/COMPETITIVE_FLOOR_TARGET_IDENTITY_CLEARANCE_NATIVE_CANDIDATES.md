# CASP17 Target Identity Clearance Native Candidates

- generated: `2026-05-26T04:20:03+09:00`
- native_candidate_packet_status: `review_required`
- fetch_rcsb: `True`
- targets/candidate rows: `3/5`
- operator/relaxed/blocked/no-candidate/prepared: `0/0/4/1/0`
- current-target collisions: `4`
- fetch errors: `0` `-`
- first next action: do not use until operator proves this is not leakage from a current/open CASP17 target

## Candidates

| target | status | query | pdb | title | release | blockers | next action |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `H1319` | `blocked_current_target_collision` | `relaxed` `Human astrovirus VA1 capsid spike` | `8UFN` | Crystal Structure of neuronal HAstV VA1 capsid spike domain at 2.73 A resolution | `2024-02-14` | `current_target_name_collision,relaxed_query_match_requires_operator_review,candidate_public_before_target_entry` | do not use until operator proves this is not leakage from a current/open CASP17 target |
| `H1319` | `blocked_current_target_collision` | `relaxed` `Human astrovirus VA1 capsid spike` | `8UFO` | Crystal Structure of Gastrointestinal HAstV VA1 capsid spike domain at 1.46 A resolution | `2024-02-14` | `current_target_name_collision,relaxed_query_match_requires_operator_review,candidate_public_before_target_entry` | do not use until operator proves this is not leakage from a current/open CASP17 target |
| `H1321` | `blocked_current_target_collision` | `relaxed` `Human astrovirus VA1 capsid spike` | `8UFN` | Crystal Structure of neuronal HAstV VA1 capsid spike domain at 2.73 A resolution | `2024-02-14` | `current_target_name_collision,relaxed_query_match_requires_operator_review,candidate_public_before_target_entry` | do not use until operator proves this is not leakage from a current/open CASP17 target |
| `H1321` | `blocked_current_target_collision` | `relaxed` `Human astrovirus VA1 capsid spike` | `8UFO` | Crystal Structure of Gastrointestinal HAstV VA1 capsid spike domain at 1.46 A resolution | `2024-02-14` | `current_target_name_collision,relaxed_query_match_requires_operator_review,candidate_public_before_target_entry` | do not use until operator proves this is not leakage from a current/open CASP17 target |
| `H2324` | `no_rcsb_candidate_found` | `prepared` `T Cell Receptor N17.2, complex (5 chains); T Cell Receptor N17.2` | `-` | - | `-` | `rcsb_candidate_missing` | broaden RCSB/manual native search and document no-leak evidence |

## Claim Boundary

Local CASP17 competitive-floor native candidate packet only. It prepares and optionally executes compact RCSB candidate searches for operator review. It does not assert a native structure, clear no-leak provenance, copy native files into workorders, score native accuracy, mutate operator intake, or submit to CASP. Any RCSB hit must still pass operator no-leak/current-target review before use.
