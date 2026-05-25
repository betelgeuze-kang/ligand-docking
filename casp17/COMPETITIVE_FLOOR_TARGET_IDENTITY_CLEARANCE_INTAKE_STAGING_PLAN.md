# CASP17 Competitive-Floor Target Identity Clearance Intake Staging Plan

- generated: `2026-05-26T02:17:04+09:00`
- clearance_intake_staging_status: `waiting_on_promoted_manifest`
- promotion_status: `blocked_by_audit`
- promoted/staged/blocked: `0/0/0`
- identity intake rows/open slots: `15/15`
- open monomer/complex slots after staging: `10/5`
- candidate_intake_csv: `casp17/casp17_competitive_floor_identity_intake_bundle_candidate_from_clearance_current.csv`
- first open: `-` `-`
- next action: wait for promoted clearance manifest rows

## Staging Rows

| dropzone | scope | status | benchmark | target | clearance | blockers | next action |
| --- | --- | --- | --- | --- | --- | --- | --- |
| - | - | `waiting_on_promoted_manifest` | - | - | - | `promoted_manifest_empty` | wait for promoted clearance manifest rows |

## Claim Boundary

Local competitive-floor clearance-to-intake staging plan only. It maps already promoted target identity manifest candidate rows onto empty competitive-floor identity intake slots and writes a separate candidate intake CSV for operator review. It does not mutate the live identity intake bundle, mutate the identity unlock kit, fetch native structures, clear provenance, score native accuracy, run predictors, or submit to CASP.
