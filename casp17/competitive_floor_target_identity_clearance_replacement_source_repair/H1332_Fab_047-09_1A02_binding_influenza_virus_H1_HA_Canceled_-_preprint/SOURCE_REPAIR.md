# H1332 Replacement Source Repair

- candidate_name: Fab 047-09_1A02 binding influenza virus H1 HA Canceled - preprint.
- source_repair_status: `blocked_cancelled_target`
- replace_target_ids: `H1319;H1321`
- cancellation_date: `2026-05-18`
- lane_recommendation: `out_of_scope_cancelled`
- recommended_action: `ignore_for_selected_lanes`
- fasta_path: `-`
- prediction_pdb: `-`
- raw_validation_json: `-`
- scorecard_json: `-`
- blockers: `target_cancelled,fasta_missing,local_prediction_missing,raw_validation_missing,scorecard_missing`
- next_action: exclude this replacement unless an operator explicitly reopens the canceled target rationale

## Commands

- predictor: `python3 tools/run_casp17_internal_physics_baseline_predictor.py --target-id H1332 --fasta casp17/replacement_source_fasta/H1332.fasta --out-dir runs/casp17_prediction_jobs_current/H1332 --raw-pdb runs/casp17_prediction_jobs_current/H1332/H1332_model_1.pdb --runtime-json runs/casp17_prediction_jobs_current/H1332/backend_runtime.json --metrics-json runs/casp17_prediction_jobs_current/H1332/internal_physics_metrics.json --quality-preset casp17_quality --ranked-raw-count 5 --emit-backbone-atoms --out-json runs/casp17_prediction_jobs_current/H1332/H1332_predictor.json --out-csv runs/casp17_prediction_jobs_current/H1332/H1332_predictor.csv --out-md runs/casp17_prediction_jobs_current/H1332/H1332_predictor.md`
- validation: `python3 tools/validate_casp17_backend_contract.py --target-id H1332 --sequence-path casp17/replacement_source_fasta/H1332.fasta --raw-pdb runs/casp17_prediction_jobs_current/H1332/H1332_model_1.pdb --runtime-json runs/casp17_prediction_jobs_current/H1332/backend_runtime.json --backend-kind internal_physics --require-gpu --out-json runs/casp17_internal_physics_raw_validations_current/H1332_backend_contract.json --out-csv runs/casp17_internal_physics_raw_validations_current/H1332_backend_contract.csv --out-md runs/casp17_internal_physics_raw_validations_current/H1332_backend_contract.md`
- scorecard: `python3 tools/build_casp17_competitive_floor_target_identity_clearance_replacement_scorecard.py --source-repair-json casp17/casp17_competitive_floor_target_identity_clearance_replacement_source_repair_current.json --out-dir runs/casp17_internal_scorecards_current --out-json casp17/casp17_competitive_floor_target_identity_clearance_replacement_scorecard_current.json --out-csv casp17/casp17_competitive_floor_target_identity_clearance_replacement_scorecard_current.csv --out-md casp17/COMPETITIVE_FLOOR_TARGET_IDENTITY_CLEARANCE_REPLACEMENT_SCORECARD.md`

## Claim Boundary

Local CASP17 competitive-floor replacement source repair only. It decomposes replacement candidates into sequence, prediction, validation, scorecard, cancellation, and collision blockers before they can be considered for clearance. It does not invent sequences, fetch native structures, clear no-leak provenance, mutate workorders/operator intake, score native accuracy, choose final replacements, or submit to CASP.
