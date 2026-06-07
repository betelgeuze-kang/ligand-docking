# CASP17 Competitive-Floor Field Value Ledger

- value_ledger_csv: `casp17/competitive_floor_batch_current/priority_010_REQUIRED_MONOMER_010/FIELD_VALUE_LEDGER.csv`
- row_fill_csv: `casp17/competitive_floor_batch_current/priority_010_REQUIRED_MONOMER_010/row_fill.csv`
- action count: `18`

| column | class | proposed value | clearance | evidence ref | status | next action |
| --- | --- | --- | --- | --- | --- | --- |
| `benchmark_id` | `target_identity` | `-` | `REQUIRED_OPERATOR_CLEARANCE` | `-` | `awaiting_value` | enter the cleared historical benchmark_id and cite the local target-selection evidence |
| `target_id` | `target_identity` | `-` | `REQUIRED_OPERATOR_CLEARANCE` | `-` | `awaiting_value` | enter the cleared historical target_id and cite the local target-selection evidence |
| `leakage_clearance` | `provenance` | `-` | `REQUIRED_OPERATOR_CLEARANCE` | `-` | `awaiting_value` | enter leakage_clearance only after no-leak evidence supports the value |
| `prediction_method` | `provenance` | `-` | `REQUIRED_OPERATOR_CLEARANCE` | `-` | `awaiting_value` | enter prediction_method only after no-leak evidence supports the value |
| `prediction_created_at` | `provenance` | `-` | `REQUIRED_OPERATOR_CLEARANCE` | `-` | `awaiting_value` | enter prediction_created_at only after no-leak evidence supports the value |
| `native_release_date` | `provenance` | `-` | `REQUIRED_OPERATOR_CLEARANCE` | `-` | `awaiting_value` | enter native_release_date only after no-leak evidence supports the value |
| `prediction_generated_before_native_release` | `provenance` | `-` | `REQUIRED_OPERATOR_CLEARANCE` | `-` | `awaiting_value` | enter prediction_generated_before_native_release only after no-leak evidence supports the value |
| `public_template_or_native_used_for_prediction` | `provenance` | `-` | `REQUIRED_OPERATOR_CLEARANCE` | `-` | `awaiting_value` | enter public_template_or_native_used_for_prediction only after no-leak evidence supports the value |
| `other_team_model_used` | `provenance` | `-` | `REQUIRED_OPERATOR_CLEARANCE` | `-` | `awaiting_value` | enter other_team_model_used only after no-leak evidence supports the value |
| `post_release_information_used` | `provenance` | `-` | `REQUIRED_OPERATOR_CLEARANCE` | `-` | `awaiting_value` | enter post_release_information_used only after no-leak evidence supports the value |
| `current_casp17_target` | `provenance` | `-` | `REQUIRED_OPERATOR_CLEARANCE` | `-` | `awaiting_value` | enter current_casp17_target only after no-leak evidence supports the value |
| `operator_clearance` | `provenance` | `-` | `REQUIRED_OPERATOR_CLEARANCE` | `-` | `awaiting_value` | enter operator_clearance only after no-leak evidence supports the value |
| `selected_model_rank` | `calibration` | `-` | `REQUIRED_OPERATOR_CLEARANCE` | `-` | `awaiting_value` | enter selected_model_rank from the local historical scoring/calibration packet |
| `best_model_rank` | `calibration` | `-` | `REQUIRED_OPERATOR_CLEARANCE` | `-` | `awaiting_value` | enter best_model_rank from the local historical scoring/calibration packet |
| `selected_native_metric` | `calibration` | `-` | `REQUIRED_OPERATOR_CLEARANCE` | `-` | `awaiting_value` | enter selected_native_metric from the local historical scoring/calibration packet |
| `best_native_metric` | `calibration` | `-` | `REQUIRED_OPERATOR_CLEARANCE` | `-` | `awaiting_value` | enter best_native_metric from the local historical scoring/calibration packet |
| `selected_score` | `calibration` | `-` | `REQUIRED_OPERATOR_CLEARANCE` | `-` | `awaiting_value` | enter selected_score from the local historical scoring/calibration packet |
| `best_score` | `calibration` | `-` | `REQUIRED_OPERATOR_CLEARANCE` | `-` | `awaiting_value` | enter best_score from the local historical scoring/calibration packet |

## Claim Boundary

Local competitive-floor value ledger only. It creates per-row ledgers for target identity, provenance, and calibration fields; it does not choose historical targets, clear no-leak provenance, score native accuracy, fetch native structures, run predictors, mutate row_fill.csv, or submit to CASP.
