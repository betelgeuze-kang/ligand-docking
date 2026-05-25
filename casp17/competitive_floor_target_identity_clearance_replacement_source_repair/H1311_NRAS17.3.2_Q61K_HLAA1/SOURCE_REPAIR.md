# H1311 Replacement Source Repair

- candidate_name: NRAS17.3.2_Q61K_HLAA1
- source_repair_status: `awaiting_sequence`
- replace_target_ids: `H1319;H1321`
- cancellation_date: `-`
- lane_recommendation: `difficult_protein_complexes`
- recommended_action: `do_not_submit_closed_or_server_only`
- fasta_path: `-`
- prediction_pdb: `-`
- raw_validation_json: `-`
- scorecard_json: `-`
- blockers: `fasta_missing,local_prediction_missing,raw_validation_missing,scorecard_missing`
- next_action: provide reviewed FASTA before local prediction can be generated

## Commands

- predictor: `python3 tools/run_casp17_internal_physics_baseline_predictor.py --target-id H1311 --fasta casp17/replacement_source_fasta/H1311.fasta --out-dir runs/casp17_prediction_jobs_current/H1311 --quality-preset casp17_quality --ranked-raw-count 5 --emit-backbone-atoms`
- validation: `python3 tools/validate_casp17_backend_contract.py --target-id H1311 --raw-pdb runs/casp17_prediction_jobs_current/H1311/H1311_model_1.pdb`
- scorecard: `python3 tools/build_casp17_internal_scorecard.py --target-id H1311 --prediction-pdb runs/casp17_prediction_jobs_current/H1311/H1311_model_1.pdb`

## Claim Boundary

Local CASP17 competitive-floor replacement source repair only. It decomposes replacement candidates into sequence, prediction, validation, scorecard, cancellation, and collision blockers before they can be considered for clearance. It does not invent sequences, fetch native structures, clear no-leak provenance, mutate workorders/operator intake, score native accuracy, choose final replacements, or submit to CASP.
