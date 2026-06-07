# CASP17 Target Identity Clearance Replacement Queue

- generated: `2026-05-26T05:06:07+09:00`
- replacement_queue_status: `candidate_ready_for_operator_clearance`
- replacement targets/candidate rows: `2/8`
- ready/missing-prediction/current-collision/source-repair/no-candidate: `2/2/4/0/0`
- first open: `H1319` -> `H1332` `blocked_missing_local_prediction`
- first next action: generate or locate local internal prediction/TS artifacts before using this replacement candidate

## Replacement Candidates

| replace | rank | candidate | status | prediction | validation | scorecard | blockers | next action |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| `H1319` | 1 | `H1311` NRAS17.3.2_Q61K_HLAA1 | `candidate_ready_for_operator_clearance` | `runs/casp17_prediction_jobs_current/H1311/H1311_model_1.pdb` | `runs/casp17_internal_physics_raw_validations_current/H1311_raw_confidence_calibration.json` | `runs/casp17_internal_scorecards_current/H1311_internal_scorecard.json` | `-` | create replacement clearance workorder row, then run native candidate/no-leak operator intake |
| `H1319` | 2 | `H1332` Fab 047-09_1A02 binding influenza virus H1 HA Canceled - preprint. | `blocked_missing_local_prediction` | `-` | `-` | `-` | `local_prediction_missing,raw_validation_missing,scorecard_missing` | generate or locate local internal prediction/TS artifacts before using this replacement candidate |
| `H1319` | 3 | `T1313` P66 | `blocked_current_target_collision` | `-` | `-` | `-` | `current_target_name_collision,local_prediction_missing,raw_validation_missing,scorecard_missing` | do not use this replacement candidate unless operator proves it is not current-target leakage |
| `H1319` | 4 | `H1312` EXT1-EXT2-2BAV4 | `blocked_current_target_collision` | `-` | `-` | `-` | `current_target_name_collision,local_prediction_missing,raw_validation_missing,scorecard_missing` | do not use this replacement candidate unless operator proves it is not current-target leakage |
| `H1321` | 1 | `H1311` NRAS17.3.2_Q61K_HLAA1 | `candidate_ready_for_operator_clearance` | `runs/casp17_prediction_jobs_current/H1311/H1311_model_1.pdb` | `runs/casp17_internal_physics_raw_validations_current/H1311_raw_confidence_calibration.json` | `runs/casp17_internal_scorecards_current/H1311_internal_scorecard.json` | `-` | create replacement clearance workorder row, then run native candidate/no-leak operator intake |
| `H1321` | 2 | `H1332` Fab 047-09_1A02 binding influenza virus H1 HA Canceled - preprint. | `blocked_missing_local_prediction` | `-` | `-` | `-` | `local_prediction_missing,raw_validation_missing,scorecard_missing` | generate or locate local internal prediction/TS artifacts before using this replacement candidate |
| `H1321` | 3 | `T1313` P66 | `blocked_current_target_collision` | `-` | `-` | `-` | `current_target_name_collision,local_prediction_missing,raw_validation_missing,scorecard_missing` | do not use this replacement candidate unless operator proves it is not current-target leakage |
| `H1321` | 4 | `H1312` EXT1-EXT2-2BAV4 | `blocked_current_target_collision` | `-` | `-` | `-` | `current_target_name_collision,local_prediction_missing,raw_validation_missing,scorecard_missing` | do not use this replacement candidate unless operator proves it is not current-target leakage |

## Claim Boundary

Local CASP17 competitive-floor clearance replacement queue only. It ranks closed watchlist protein targets as possible replacements for collision-blocked clearance targets, while checking current-target name collisions and local prediction evidence. It does not choose a final replacement, fetch native structures, clear no-leak provenance, mutate clearance workorders/operator intake, score native accuracy, or submit to CASP.
