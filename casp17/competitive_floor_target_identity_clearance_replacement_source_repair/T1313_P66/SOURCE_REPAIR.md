# T1313 Replacement Source Repair

- candidate_name: P66
- source_repair_status: `blocked_current_target_collision`
- replace_target_ids: `H1319;H1321`
- cancellation_date: `-`
- lane_recommendation: `difficult_protein_complexes`
- recommended_action: `do_not_submit_closed_or_server_only`
- fasta_path: `-`
- prediction_pdb: `-`
- raw_validation_json: `-`
- scorecard_json: `-`
- blockers: `current_target_name_collision,fasta_missing,local_prediction_missing,raw_validation_missing,scorecard_missing`
- next_action: choose a non-colliding replacement target or prove no current-target leakage

## Commands

- predictor: `python3 tools/run_casp17_internal_physics_baseline_predictor.py --target-id T1313 --fasta casp17/replacement_source_fasta/T1313.fasta --out-dir runs/casp17_prediction_jobs_current/T1313 --raw-pdb runs/casp17_prediction_jobs_current/T1313/T1313_model_1.pdb --runtime-json runs/casp17_prediction_jobs_current/T1313/backend_runtime.json --metrics-json runs/casp17_prediction_jobs_current/T1313/internal_physics_metrics.json --quality-preset casp17_quality --ranked-raw-count 5 --emit-backbone-atoms --out-json runs/casp17_prediction_jobs_current/T1313/T1313_predictor.json --out-csv runs/casp17_prediction_jobs_current/T1313/T1313_predictor.csv --out-md runs/casp17_prediction_jobs_current/T1313/T1313_predictor.md`
- validation: `python3 tools/validate_casp17_backend_contract.py --target-id T1313 --sequence-path casp17/replacement_source_fasta/T1313.fasta --raw-pdb runs/casp17_prediction_jobs_current/T1313/T1313_model_1.pdb --runtime-json runs/casp17_prediction_jobs_current/T1313/backend_runtime.json --backend-kind internal_physics --require-gpu --out-json runs/casp17_internal_physics_raw_validations_current/T1313_backend_contract.json --out-csv runs/casp17_internal_physics_raw_validations_current/T1313_backend_contract.csv --out-md runs/casp17_internal_physics_raw_validations_current/T1313_backend_contract.md`
- scorecard: `python3 tools/build_casp17_competitive_floor_target_identity_clearance_replacement_scorecard.py --source-repair-json casp17/casp17_competitive_floor_target_identity_clearance_replacement_source_repair_current.json --out-dir runs/casp17_internal_scorecards_current --out-json casp17/casp17_competitive_floor_target_identity_clearance_replacement_scorecard_current.json --out-csv casp17/casp17_competitive_floor_target_identity_clearance_replacement_scorecard_current.csv --out-md casp17/COMPETITIVE_FLOOR_TARGET_IDENTITY_CLEARANCE_REPLACEMENT_SCORECARD.md`

## Claim Boundary

Local CASP17 competitive-floor replacement source repair only. It decomposes replacement candidates into sequence, prediction, validation, scorecard, cancellation, and collision blockers before they can be considered for clearance. It does not invent sequences, fetch native structures, clear no-leak provenance, mutate workorders/operator intake, score native accuracy, choose final replacements, or submit to CASP.
