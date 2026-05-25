# H2324 Clearance Adjudication

- target_name: T Cell Receptor N17.2, complex (5 chains)
- adjudication_status: `manual_native_search_required`
- operator_intake_status: `awaiting_input`
- replacement_required: `false`
- manual_native_search_required: `true`
- safe_to_apply_operator_intake: `false`
- blockers: `rcsb_candidate_missing`
- next_action: broaden manual native search, then document local no-leak evidence before intake

## Candidate Signals

| status | query | pdb | release | collisions | blockers |
| --- | --- | --- | --- | --- | --- |
| `no_rcsb_candidate_found` | `prepared` `T Cell Receptor N17.2, complex (5 chains); T Cell Receptor N17.2` | `-` | `-` | `-` | `rcsb_candidate_missing` |

## Claim Boundary

Local CASP17 competitive-floor clearance adjudication only. It consolidates operator-intake and native-candidate risk signals into target-level next actions. It does not clear no-leak provenance, assert native identity, copy native files, score native accuracy, mutate operator intake, choose final targets, or submit to CASP.
