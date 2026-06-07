# CASP17 Target Identity Clearance Replacement Scorecard

- generated: `2026-05-26T05:06:07+09:00`
- replacement_scorecard_status: `replacement_scorecard_blocked`
- candidates: `4`
- pass/blocked/scorecard-json: `1/3/1`
- first open: `H1312` `replacement_source_scorecard_blocked`
- first next action: repair replacement source evidence before clearance review

## Rows

| candidate | status | fasta | prediction | contract | geometry | confidence | scorecard | blockers |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `H1311` | `replacement_source_scorecard_pass` | `casp17/replacement_source_fasta/H1311.fasta` | `runs/casp17_prediction_jobs_current/H1311/H1311_model_1.pdb` | `runs/casp17_internal_physics_raw_validations_current/H1311_backend_contract.json` | `runs/casp17_internal_physics_raw_validations_current/H1311_raw_geometry_sanity.json` | `runs/casp17_internal_physics_raw_validations_current/H1311_raw_confidence_calibration.json` | `runs/casp17_internal_scorecards_current/H1311_internal_scorecard.json` | `-` |
| `H1312` | `replacement_source_scorecard_blocked` | `-` | `-` | `-` | `-` | `-` | `-` | `blocked_current_target_collision,fasta_missing,sequence_provenance_missing,prediction_missing,predictor_json:missing_path,backend_contract_json:missing_path,geometry_json:missing_path,confidence_json:missing_path,residue_count_missing` |
| `H1332` | `replacement_source_scorecard_blocked` | `-` | `-` | `-` | `-` | `-` | `-` | `blocked_cancelled_target,fasta_missing,sequence_provenance_missing,prediction_missing,predictor_json:missing_path,backend_contract_json:missing_path,geometry_json:missing_path,confidence_json:missing_path,residue_count_missing` |
| `T1313` | `replacement_source_scorecard_blocked` | `-` | `-` | `-` | `-` | `-` | `-` | `blocked_current_target_collision,fasta_missing,sequence_provenance_missing,prediction_missing,predictor_json:missing_path,backend_contract_json:missing_path,geometry_json:missing_path,confidence_json:missing_path,residue_count_missing` |

## Claim Boundary

Local CASP17 replacement source scorecard only. It checks that a replacement candidate has reviewed sequence provenance, internal-physics prediction evidence, backend contract pass, raw geometry pass, and raw confidence pass before replacement-clearance review. It does not assert native identity, no-leak provenance, official CASP submission readiness, or structure accuracy.
