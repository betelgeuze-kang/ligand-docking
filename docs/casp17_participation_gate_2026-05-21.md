# CASP17 Internal Physics Participation Gate

Status date: 2026-05-21

## Current Decision

Use CASP17 as an external blind-evaluation opportunity, but keep every submission fail-closed.

- Current active lane: 100% internal `torch`/coarse-grain physics predictor.
- Scope: all current open selected protein targets materialized by the CASP17 watchlist.
- Current target count: 12.
- Excluded from current open set: `H1319`, because its human deadline was 2026-05-19.
- External predictors, public/template structures, API structure services, and other-team models are not part of the active lane.
- CASP author code is runtime-only input. Do not store it in repo docs, state, configs, or generated examples.
- CASP portal upload/submission is R4 external state and requires explicit confirmation before execution.

## Current Evidence

The recursive internal-physics lane is locally green as of 2026-05-20 23:40 KST:

- `runs/casp17_prediction_launch_packet_recursive_current.json`: 12/12 ready with `backend_mode=internal_physics`, `casp17_quality`, and `--emit-backbone-atoms`.
- `runs/casp17_prediction_recursive_contract_batch_current.json`: 12/12 backend jobs executed and contract-validated.
- `runs/casp17_internal_physics_raw_gate_packet_recursive_current.json`: raw gate `pass`, 12/12 contract/geometry/confidence pass with GPU evidence required.
- `runs/casp17_internal_physics_ts_gate_batch_recursive_current.json`: 12/12 TS converted; import, validation, scorecard, and submission gate completed.
- `runs/casp17_submission_gate_packet_recursive_current.json`: 12/12 `submission_go` under the internal fail-closed gate.
- `runs/casp17_internal_physics_accuracy_readiness_packet_recursive_current.json`: 12/12 accuracy-readiness proxy pass.
- `runs/casp17_predictions_recursive_current/*TS.pdb`: 12 CASP TS files, with chain-count-matched `PARENT` and `TER` rows.
- CASP17 unit suite: 75 passed.

## Claim Boundary

Safe wording before official CASP assessment:

> The repository is internally gated for CASP17 regular-group protein target submission using a 100% internal physics baseline, with all current open selected protein targets passing local format, geometry, confidence, scorecard, submission, and accuracy-readiness proxy gates.

Do not claim CASP17 ranking, native accuracy, experimental correctness, commercial parity, or accepted submission until official CASP evidence exists.

The emitted backbone atoms are explicitly labeled as a CA-anchored compact pseudo-backbone. They make atom-rich raw/TS geometry gates possible, but they are not an all-atom refinement claim.

## Registration Policy

Recommended operating state:

1. Use a regular prediction group for manual submissions.
2. Keep server registration blocked until a separate 72-hour automated server path has its own green gate.
3. Select tertiary structure prediction and assembly/quaternary prediction for the current protein/complex scope.
4. Keep the CASP author code out of committed files and pass it only through `--author-code` at execution time.

Official CASP17 references:

- Main experiment page: https://predictioncenter.org/casp17/
- Registration instructions: https://predictioncenter.org/casp17/registration.cgi
- Submission rules and format: https://predictioncenter.org/casp17/index.cgi?page=format

## Internal Go/No-Go Gate

A target can be submitted only when all required local checks pass:

- `deadline_class=regular`
- `target_id` is present.
- `submission_format=TS`
- `sequence_path` exists and exactly matches the predicted residue sequence.
- `prediction_file_path` exists.
- `format_check_status=pass`
- `model_generation_status=pass`
- `geometry_sanity_status=pass`
- `confidence_calibration_status=pass`
- `internal_scorecard_status=pass`
- Backend contract records `backend_kind=internal_physics`.
- GPU runtime evidence is present for production-quality generation.
- The final submission gate returns `submission_go`.
- The accuracy-readiness proxy returns `pass`.

Fail-closed rules:

- Missing target files block submission.
- Unknown or server-only deadline class blocks submission.
- A target-specific validation JSON with hard blockers blocks submission even if the CSV row says pass.
- A stale or blocked local delivery/accounting artifact blocks all target submission decisions.
- Any external/public/template/provenance ambiguity blocks the existing-structure attach lane.
- CASP portal upload remains blocked until the operator explicitly confirms the external-state action.

## Current Internal Physics Lane

Refresh the current target watchlist and sequences:

```bash
python3 tools/build_casp17_target_watchlist.py

python3 tools/build_casp17_sequence_packet.py \
  --intake-csv runs/casp17_target_intake_seed_current.csv
```

Build the internal-physics launch packet for all current protein targets:

```bash
python3 tools/build_casp17_prediction_import_packet.py \
  --intake-csv runs/casp17_target_intake_seed_with_sequences_current.csv \
  --prediction-dir runs/casp17_predictions_recursive_current \
  --out-json runs/casp17_prediction_import_packet_recursive_current.json \
  --out-csv runs/casp17_prediction_import_packet_recursive_current.csv \
  --out-md runs/casp17_prediction_import_packet_recursive_current.md \
  --out-intake-csv runs/casp17_target_intake_prediction_imported_recursive_current.csv

python3 tools/build_casp17_prediction_launch_packet.py \
  --target-scope all_protein \
  --target-limit 0 \
  --backend-mode internal_physics \
  --backend-supports-multimer \
  --allow-deadline-close \
  --internal-quality-preset casp17_quality \
  --internal-emit-backbone-atoms \
  --prediction-dir runs/casp17_predictions_recursive_current \
  --job-dir runs/casp17_prediction_jobs_recursive_current \
  --prediction-import-json runs/casp17_prediction_import_packet_recursive_current.json \
  --out-json runs/casp17_prediction_launch_packet_recursive_current.json \
  --out-csv runs/casp17_prediction_launch_packet_recursive_current.csv \
  --out-md runs/casp17_prediction_launch_packet_recursive_current.md
```

Run all ready targets through internal prediction and backend contract validation:

```bash
python3 tools/run_casp17_prediction_batch_gate.py \
  --launch-packet-json runs/casp17_prediction_launch_packet_recursive_current.json \
  --execute \
  --stop-after contract \
  --timeout-seconds 21600 \
  --target-limit 0 \
  --continue-on-error \
  --attempt-dir runs/casp17_prediction_recursive_contract_attempts_current \
  --out-json runs/casp17_prediction_recursive_contract_batch_current.json \
  --out-csv runs/casp17_prediction_recursive_contract_batch_current.csv \
  --out-md runs/casp17_prediction_recursive_contract_batch_current.md
```

Run the raw gate:

```bash
python3 tools/build_casp17_internal_physics_raw_gate_packet.py \
  --launch-packet-json runs/casp17_prediction_launch_packet_recursive_current.json \
  --job-dir runs/casp17_prediction_jobs_recursive_current \
  --require-gpu \
  --out-dir runs/casp17_internal_physics_raw_validations_recursive_current \
  --out-json runs/casp17_internal_physics_raw_gate_packet_recursive_current.json \
  --out-csv runs/casp17_internal_physics_raw_gate_packet_recursive_current.csv \
  --out-md runs/casp17_internal_physics_raw_gate_packet_recursive_current.md
```

Convert raw PDBs to CASP TS and run downstream gates:

```bash
python3 tools/run_casp17_internal_physics_ts_gate_batch.py \
  --raw-gate-json runs/casp17_internal_physics_raw_gate_packet_recursive_current.json \
  --launch-packet-json runs/casp17_prediction_launch_packet_recursive_current.json \
  --intake-csv runs/casp17_target_intake_seed_with_sequences_current.csv \
  --prediction-dir runs/casp17_predictions_recursive_current \
  --out-dir runs/casp17_internal_physics_ts_gate_recursive_current \
  --author-code <CASP_AUTHOR_CODE> \
  --execute \
  --import-json runs/casp17_prediction_import_packet_recursive_current.json \
  --import-csv runs/casp17_prediction_import_packet_recursive_current.csv \
  --import-md runs/casp17_prediction_import_packet_recursive_current.md \
  --imported-intake-csv runs/casp17_target_intake_prediction_imported_recursive_current.csv \
  --validation-dir runs/casp17_validations_recursive_current \
  --validation-json runs/casp17_prediction_validation_batch_recursive_current.json \
  --validation-csv runs/casp17_prediction_validation_batch_recursive_current.csv \
  --validation-md runs/casp17_prediction_validation_batch_recursive_current.md \
  --validated-intake-csv runs/casp17_target_intake_validated_recursive_current.csv \
  --scorecard-dir runs/casp17_internal_scorecards_recursive_current \
  --scorecard-json runs/casp17_internal_scorecard_batch_recursive_current.json \
  --scorecard-csv runs/casp17_internal_scorecard_batch_recursive_current.csv \
  --scorecard-md runs/casp17_internal_scorecard_batch_recursive_current.md \
  --scored-intake-csv runs/casp17_target_intake_scored_recursive_current.csv \
  --submission-gate-json runs/casp17_submission_gate_packet_recursive_current.json \
  --submission-gate-csv runs/casp17_submission_gate_packet_recursive_current.csv \
  --submission-gate-md runs/casp17_submission_gate_packet_recursive_current.md \
  --out-json runs/casp17_internal_physics_ts_gate_batch_recursive_current.json \
  --out-csv runs/casp17_internal_physics_ts_gate_batch_recursive_current.csv \
  --out-md runs/casp17_internal_physics_ts_gate_batch_recursive_current.md
```

Run the accuracy-readiness proxy:

```bash
python3 tools/build_casp17_internal_physics_accuracy_readiness_packet.py \
  --target-watchlist-json runs/casp17_target_watchlist_current.json \
  --raw-gate-json runs/casp17_internal_physics_raw_gate_packet_recursive_current.json \
  --ts-gate-json runs/casp17_internal_physics_ts_gate_batch_recursive_current.json \
  --submission-gate-json runs/casp17_submission_gate_packet_recursive_current.json \
  --job-dir runs/casp17_prediction_jobs_recursive_current \
  --require-backbone-atoms \
  --out-json runs/casp17_internal_physics_accuracy_readiness_packet_recursive_current.json \
  --out-csv runs/casp17_internal_physics_accuracy_readiness_packet_recursive_current.csv \
  --out-md runs/casp17_internal_physics_accuracy_readiness_packet_recursive_current.md
```

## Single-Target Internal Predictor

For local debug or targeted re-run:

```bash
python3 tools/run_casp17_internal_physics_baseline_predictor.py \
  --target-id T1331 \
  --fasta runs/casp17_sequences_current/T1331.fasta \
  --out-dir runs/casp17_prediction_jobs_recursive_current/T1331 \
  --raw-pdb runs/casp17_prediction_jobs_recursive_current/T1331/T1331_model_1.pdb \
  --runtime-json runs/casp17_prediction_jobs_recursive_current/T1331/backend_runtime.json \
  --metrics-json runs/casp17_prediction_jobs_recursive_current/T1331/internal_physics_metrics.json \
  --device auto \
  --quality-preset casp17_quality \
  --emit-backbone-atoms
```

CPU execution is test/smoke-only. Production-quality CASP17 generation should keep GPU evidence required.

## Existing-Structure Attach Lane

The existing-structure lane remains available only for internally generated target-specific structures with cleared provenance. It is not the active 100% internal physics submission lane.

```bash
python3 tools/build_casp17_existing_structure_file_checklist.py \
  --write-provenance-scaffold

python3 tools/build_casp17_existing_structure_intake_builder.py \
  --structure-dir runs/casp17_existing_structures_current \
  --provenance-csv runs/casp17_existing_structure_provenance_current.csv \
  --author-code <CASP_AUTHOR_CODE>
```

Required provenance clearance:

- internal target-specific generation
- `public_or_external_source_used=false`
- `other_team_structure_used=false`
- `post_release_structure_used=false`

## Legacy External Adapter

`tools/run_casp17_external_structure_predictor_adapter.py` is retained as a fail-closed integration shim, but it is not part of the current internal-only CASP17 lane. Do not use it for the current submission set unless the work is explicitly re-scoped away from the 100% internal-physics policy.

## Verification

Current expected checks:

```bash
python3 -m pytest tests/unit/test_run_casp17_internal_physics_baseline_predictor.py \
  tests/unit/test_build_casp17_prediction_launch_packet.py \
  tests/unit/test_build_casp17_internal_physics_accuracy_readiness_packet.py \
  tests/unit/test_convert_casp17_ts_prediction_from_pdb.py -q

python3 -m pytest tests/unit/test_*casp17*.py -q
```

Current known-good result:

- focused CASP17 internal physics tests: 15 passed
- full CASP17 targeted unit suite: 75 passed

## External Submission Confirmation

Before uploading to CASP, prepare and confirm:

```text
Target: CASP17 Prediction Center portal
Action: upload/submit runs/casp17_predictions_recursive_current/*TS.pdb
Impact: official CASP17 prediction submission under the registered group
Risk: external irreversible or hard-to-reverse submission record
Rollback: only whatever replace/withdraw behavior CASP portal supports
Verification: CASP receipt/status and target list match the 12 TS files
```
