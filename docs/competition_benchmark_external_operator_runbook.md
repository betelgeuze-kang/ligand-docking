# Competition Benchmark External Operator Runbook

Separate operator actions for **live CAMEO** and **external CASP credibility**. Local builders do not perform these steps.

- status: `competition_external_operator_track_ready`
- architecture_validation_status: `architecture_validation_packages_in_progress`
- evidence_depth_tier: `row_evidence_partial`
- overclaim_warning_count: `1`

## Tracks

| track_id | phase | status | artifact | next_action |
| --- | --- | --- | --- | --- |
| `CAMEO-LIVE-REGISTRATION` | `C-P1` | `ready_for_separate_operator_review` | `runs/cameo_public_registration_approval_gate_current.json` | Operator reviews registration approval intake; no auto-registration is performed. |
| `CAMEO-LIVE-EMAIL` | `C-P1` | `ready_for_separate_operator_send` | `runs/cameo_outbound_email_send_preflight_current.json` | Operator reviews outbound email send preflight before any separate SMTP send. |
| `CAMEO-LIVE-DEPLOY` | `C-P1` | `ready` | `runs/product_rollout_execution_readiness_current.json` | Execute separate operator-approved rollout using deploy/product_rollout_runbook.md. |
| `CAMEO-OFFICIAL-RESULTS` | `C-P2` | `local_intake_ready` | `runs/cameo_official_results_operator_intake.csv` | Add official CAMEO assessment rows to runs/cameo_official_results_operator_intake.csv from organizer pages. |
| `CASP-STRICT-BLIND-EXTERNAL` | `C-P3` | `local_gate_ready` | `casp17/casp17_strict_blind_internal_prediction_source_gate_current.json` | Replace replay placeholder PDBs with verified pre-native predictions before any external CASP claim. |
| `CASP-WINNER-BAND-EXTERNAL` | `C-P4` | `local_review_ready` | `casp17/casp17_historical_winner_normalized_bands_current.json` | Promote only after row-level metric surface and no-leak replay evidence pass architecture validation depth checks. |

## Claim Boundary

Competition external operator track only; it documents separate operator actions for live CAMEO and external CASP credibility without submitting predictions, sending email, or mutating external state.

