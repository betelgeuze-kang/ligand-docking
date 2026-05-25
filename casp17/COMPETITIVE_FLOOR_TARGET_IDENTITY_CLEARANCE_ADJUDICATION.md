# CASP17 Target Identity Clearance Adjudication

- generated: `2026-05-26T04:26:50+09:00`
- adjudication_packet_status: `blocked_candidate_risk`
- targets: `3`
- ready/applied/operator-review/collision/manual/fetch: `0/0/0/2/1/0`
- replacement_required/safe_to_apply/md: `2/0/3`
- first open: `H1319` `blocked_current_target_collision`
- first next action: replace this clearance target or provide independent operator proof that the candidate is not current-target leakage

## Target Decisions

| target | status | intake | candidates | collision | manual | replacement | next action |
| --- | --- | --- | ---: | ---: | --- | --- | --- |
| `H1319` | `blocked_current_target_collision` | `awaiting_input` | 2 | 2 | `false` | `true` | replace this clearance target or provide independent operator proof that the candidate is not current-target leakage |
| `H1321` | `blocked_current_target_collision` | `awaiting_input` | 2 | 2 | `false` | `true` | replace this clearance target or provide independent operator proof that the candidate is not current-target leakage |
| `H2324` | `manual_native_search_required` | `awaiting_input` | 1 | 0 | `true` | `false` | broaden manual native search, then document local no-leak evidence before intake |

## Claim Boundary

Local CASP17 competitive-floor clearance adjudication only. It consolidates operator-intake and native-candidate risk signals into target-level next actions. It does not clear no-leak provenance, assert native identity, copy native files, score native accuracy, mutate operator intake, choose final targets, or submit to CASP.
