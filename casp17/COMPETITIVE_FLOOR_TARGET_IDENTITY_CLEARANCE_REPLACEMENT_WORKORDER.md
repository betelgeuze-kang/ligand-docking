# CASP17 Target Identity Clearance Replacement Workorder

- generated: `2026-06-02T21:12:55+09:00`
- replacement_workorder_status: `partial_replacement_workorders_ready_for_operator_intake`
- queue_status: `candidate_ready_for_operator_clearance`
- replacement targets/workorder rows: `2/2`
- selected/duplicate/no-ready: `1/1/0`
- dropzones/templates/stubs: `1/1/1`
- native dropzone readmes: `1`
- first open: `H1321` -> `H1311` `blocked_duplicate_candidate_assignment`
- first next action: choose a different ready replacement candidate before materializing this workorder

## Workorders

| rank | replace | candidate | status | folder | prediction | scorecard | blockers | next action |
| ---: | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `H1319` | `H1311` NRAS17.3.2_Q61K_HLAA1 | `selected_for_replacement_workorder` | `casp17/competitive_floor_target_identity_clearance_replacement_workorders/H1319_to_H1311_NRAS17.3.2_Q61K_HLAA1` | `runs/casp17_prediction_jobs_current/H1311/H1311_model_1.pdb` | `runs/casp17_internal_scorecards_current/H1311_internal_scorecard.json` | `-` | fill replacement native dropzone and no-leak provenance template, then run operator intake |
| 2 | `H1321` | `H1311` NRAS17.3.2_Q61K_HLAA1 | `blocked_duplicate_candidate_assignment` | `-` | `runs/casp17_prediction_jobs_current/H1311/H1311_model_1.pdb` | `runs/casp17_internal_scorecards_current/H1311_internal_scorecard.json` | `duplicate_candidate_target_id` | choose a different ready replacement candidate before materializing this workorder |

## Claim Boundary

Local CASP17 replacement clearance workorder only. It selects at most one ready replacement candidate per candidate target id, materializes separate native dropzones/provenance templates/manifest stubs for selected replacement candidates, and blocks duplicate candidate reuse until another replacement is available. It does not mutate the live clearance queue, fetch native structures, clear no-leak provenance, score native accuracy, import rows into identity intake, or submit to CASP.
