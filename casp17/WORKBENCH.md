# CASP17 Workbench Index

This is the local navigation surface for the current CASP17 internal-physics lane.

- generated: `2026-05-26T03:04:46+09:00`
- workbench_status: `ready_for_operator_fill`
- target model folders: `16/16`
- target object folders: `48`
- target object projections: `48`
- target object viewers: `48`
- target object folder audit: `pass` rows `48/48` chain isolation `48/48`
- target object viewer smoke: `pass` rows `48/48`
- benchmark rows ready/total: `0/40`
- competitive-floor batch: `ready_for_fill` rows `15` missing evidence `490`
- competitive row_fill status: `awaiting_fill` filled/ready/total `15/0/15`
- competitive row_fill worklist: `open_actions` open actions `450` guides `15`
- competitive evidence dropzones: `open_actions` dropzones/manifests `15/15` open actions `450` file actions `180`
- competitive evidence import: `awaiting_import` actions `450` ready/applied `0/0` awaiting files/values `180/270` blocked `0`
- competitive evidence round: `awaiting_import` stages `5` import ready/applied `0/0` patch candidates/planned `0/0`
- competitive unlock priority: `identity_unlock_required` phases `60` identity open `30` target_id open `15` files waiting `180`
- competitive identity unlock kit: `awaiting_identity` rows `0/15/0/15` files unlocked `0`
- competitive identity unlock round: `awaiting_identity` rows `0/15/0/15` import ready/applied `0/0` target_id open `15` files waiting `180`
- competitive identity intake bundle: `awaiting_identity` rows `0/15/0/15` missing fields `60` files unlocked `0`
- competitive identity intake sync: `awaiting_intake` rows `0/0/15/0/15` missing fields `60` mismatches `0` applied `0`
- competitive identity candidates: `awaiting_candidate_sources` rows `0/15/15` source ready/blocked/total `0/40/40` applied `0` operator preflight `blocked`
- competitive identity source repair: `awaiting_target_identity` actions `200` blocked sources `40` phase identity/core/provenance/ablation/calibration `40/40/40/40/40` first phase `target_identity`
- competitive target identity discovery: `review_required` discovered `19` operator/current/closed/unknown/synthetic `3/16/3/0/0` ready intake `0`
- competitive target identity clearance: `awaiting_target_identity_clearance` review `3` prediction/TS/native/provenance `3/3/0/0` ready `0` awaiting prediction/native/no-leak `0/3/0`
- competitive target identity clearance workorders: `awaiting_native_or_provenance` workorders `3` ready/native+provenance/native/provenance `0/3/0/0` dropzones/templates/stubs `3/3/3` preserved templates/stubs `3/3` refreshed templates/stubs `0/0`
- competitive target identity clearance manifest sync: `awaiting_provenance` rows ready/awaiting/blocked/synced `3/0/3/0/0` changed/applied `0/0`
- competitive target identity clearance workorder audit: `blocked` pass/blocked/total `0/3/3` prediction/native/provenance/evidence/manifest `3/0/0/0/0` prediction protein-atoms/coordinate-valid `1855/3` identity discovery blocked/cleared `3/0` native protein-atoms/coordinate-valid `0/0` evidence verified/content-blocked/blocked/waiting `0/0/3/0` manifest/provenance matched/mismatches `0/0` native/prediction distinct/same/waiting `0/0/3`
- competitive target identity clearance promotion: `blocked_by_audit` rows/promoted/blocked `3/0/3` ready/audit-pass `0/0`
- competitive target identity clearance intake staging: `waiting_on_promoted_manifest` promoted/staged/blocked `0/0/0` open slots/candidate rows `15/15`
- competitive target identity clearance candidate intake sync: `waiting_on_staged_identity` rows ready/waiting/blocked/applied `15/0/15/0/0`
- competitive target identity clearance cycle: `awaiting_provenance` stages `1/5/6` sync/audit/promotion `awaiting_provenance`/`blocked`/`blocked_by_audit` staged `0`
- competitive identity cycle: `awaiting_intake` stages `1/6/7` sync `awaiting_intake` ready/awaiting `0/15` missing fields `60` readiness `awaiting_identity`
- competitive file source plan: `waiting_on_identity` actions `180` waiting identity/source `180/0` ready/imported/blocked `0/0/0`
- competitive value entry plan: `waiting_on_identity` actions `270` target/provenance/calibration `30/150/90` waiting identity/value/clearance/ref `270/0/0/0` ready/blocked `0/0`
- competitive execution board: `awaiting_identity` rows `15` identity/apply/file/value/import/blocked `15/0/0/0/0/0` ready/blocked actions `0/450`
- competitive readiness gate: `awaiting_identity` gates pass/blocked `1/5` first blocked `identity_gate` `awaiting_identity`
- competitive value ledgers: `awaiting_values` ledgers/actions `15/270` ready/awaiting `0/270`
- competitive evidence intake: `awaiting_evidence` actions `450` patch candidates `0` awaiting files/values `180/270`
- competitive row_fill patch gate: `awaiting_evidence` actions `450` ready/awaiting/conflicts `0/450/0`
- competitive row_fill apply plan: `awaiting_evidence` actions `450` planned/awaiting/applied `0/450/0`
- competitive operator template: `blocked` rows `0/15`
- competitive row_fill candidates: `15`
- competitive operator preflight: `blocked` rows `0/15`
- required files present/missing: `0/480`
- current proven level: `review_quality`
- next unclosed level: `competitive_floor`
- first operator action: `historical_benchmark_inputs`
- first operator blockers: `ready_total_below_threshold,ready_monomer_below_threshold,ready_complex_below_threshold`
- first fill action: Replace placeholder target/benchmark IDs with a cleared historical non-CASP17 protein target.

## Workbench Artifacts

| artifact | status | ready | blocked | total | path | next action | blockers |
| --- | --- | ---: | ---: | ---: | --- | --- | --- |
| `target_model_folders` | `ready` | 16 | 0 | 16 | `casp17/casp17_target_model_folders_current.json` | Use per-protein folders for local visual review and submission-readiness inspection. | `-` |
| `target_object_catalog` | `ready` | 48 | 0 | 48 | `casp17/casp17_target_object_models_current.md` | Open the per-object catalog for chain-level PDB, projection, and local viewer review. | `projection_missing_count:0,viewer_missing_count:0` |
| `target_object_folder_audit` | `pass` | 48 | 0 | 48 | `casp17/casp17_target_object_folder_audit_current.json` | Keep this pass before treating per-protein object folders as independently reviewable. | `-` |
| `target_object_viewer_smoke` | `pass` | 48 | 0 | 48 | `casp17/casp17_target_object_viewer_smoke_current.json` | Keep this pass before relying on per-object viewer artifacts for review. | `-` |
| `win_gap_closure` | `blocked_input` | 4 | 5 | 9 | `runs/casp17_win_gap_closure_packet_current.json` | historical_benchmark_inputs | `ready_total_below_threshold,ready_monomer_below_threshold,ready_complex_below_threshold` |
| `benchmark_input_scaffold` | `ready` | 0 | 40 | 40 | `runs/casp17_win_tier_benchmark_input_scaffold_current.json` | Fill row folders with cleared historical target identity, internal predictions, native files, provenance, and calibration values. | `missing_evidence_items:1310` |
| `benchmark_input_inventory` | `blocked` | 0 | 40 | 40 | `runs/casp17_win_tier_benchmark_input_inventory_current.json` | Replace placeholder target/benchmark IDs with a cleared historical non-CASP17 protein target. | `missing_files:480` |
| `operator_dashboard` | `ready` | 0 | 40 | 40 | `runs/casp17_win_tier_benchmark_operator_dashboard_current.json` | Replace placeholder target/benchmark IDs with a cleared historical non-CASP17 protein target. | `-` |
| `competitive_floor_batch` | `ready_for_fill` | 15 | 0 | 15 | `casp17/casp17_competitive_floor_batch_current.json` | Fill the copied competitive-floor task folders before expanding to the full 40-row win-tier set. | `missing_evidence_items:490` |
| `competitive_floor_row_fill_status` | `awaiting_fill` | 0 | 15 | 15 | `casp17/casp17_competitive_floor_row_fill_status_current.json` | resolve row_fill.csv blockers and rerun operator-template/preflight | `filled:15,missing_fields:0,placeholders:450,missing_files:180` |
| `competitive_floor_row_fill_worklist` | `open_actions` | 0 | 450 | 15 | `casp17/casp17_competitive_floor_row_fill_worklist_current.json` | replace with a stable hist_* ID for the chosen cleared historical target | `benchmark_id_placeholder` |
| `competitive_floor_evidence_dropzone` | `open_actions` | 0 | 450 | 15 | `casp17/casp17_competitive_floor_evidence_dropzone_current.json` | replace benchmark_id in row_fill.csv after choosing a cleared historical target | `benchmark_id_placeholder` |
| `competitive_floor_evidence_import` | `awaiting_import` | 0 | 450 | 450 | `casp17/casp17_competitive_floor_evidence_import_current.json` | enter proposed_value, evidence_ref, and operator_clearance in the import CSV | `awaiting_import_value` |
| `competitive_floor_evidence_round` | `awaiting_import` | 0 | 450 | 5 | `casp17/casp17_competitive_floor_evidence_round_current.json` | enter proposed_value, evidence_ref, and operator_clearance in the import CSV | `awaiting_import` |
| `competitive_floor_unlock_priority` | `identity_unlock_required` | 0 | 210 | 60 | `casp17/casp17_competitive_floor_evidence_unlock_priority_current.json` | fill benchmark_id and target_id values first; target_id unlocks canonical file recommendations | `identity_unlock` |
| `competitive_floor_identity_unlock_kit` | `awaiting_identity` | 0 | 15 | 15 | `casp17/casp17_competitive_floor_identity_unlock_kit_current.json` | Fill proposed_benchmark_id/proposed_target_id/evidence_ref/operator_clearance, then apply the kit. | `proposed_benchmark_id_required,proposed_target_id_required,evidence_ref_required,operator_clearance_required` |
| `competitive_floor_identity_unlock_round` | `awaiting_identity` | 0 | 30 | 15 | `casp17/casp17_competitive_floor_identity_unlock_round_current.json` | fill proposed_benchmark_id, proposed_target_id, evidence_ref, and operator_clearance in the identity kit | `identity_open:30,files_waiting:180` |
| `competitive_floor_identity_intake_bundle` | `awaiting_identity` | 0 | 15 | 15 | `casp17/casp17_competitive_floor_identity_intake_bundle_current.json` | fill proposed_benchmark_id, proposed_target_id, evidence_ref, operator_clearance | `missing_fields:60` |
| `competitive_floor_identity_intake_sync` | `awaiting_intake` | 0 | 15 | 15 | `casp17/casp17_competitive_floor_identity_intake_sync_current.json` | fill proposed_benchmark_id, proposed_target_id, evidence_ref, and operator_clearance in the intake bundle | `missing_fields:60` |
| `competitive_floor_identity_candidate_packet` | `awaiting_candidate_sources` | 0 | 15 | 15 | `casp17/casp17_competitive_floor_identity_candidate_packet_current.json` | fix blocked local candidate rows until a cleared non-current historical target is ready | `source_ready:0,source_blocked:40,operator_preflight:blocked` |
| `competitive_floor_identity_source_repair_plan` | `awaiting_target_identity` | 0 | 200 | 40 | `casp17/casp17_competitive_floor_identity_source_repair_plan_current.json` | replace REQUIRED target/benchmark placeholders with a cleared non-current historical target identity | `identity:40,core:40,provenance:40,ablation:40,calibration:40` |
| `competitive_floor_target_identity_discovery` | `review_required` | 0 | 19 | 19 | `casp17/casp17_competitive_floor_target_identity_discovery_packet_current.json` | operator must confirm historical eligibility, native availability, and no-leak clearance | `operator_review:3,current:16,closed:3,unknown:0,synthetic:0` |
| `competitive_floor_target_identity_clearance_queue` | `awaiting_target_identity_clearance` | 0 | 3 | 3 | `casp17/casp17_competitive_floor_target_identity_clearance_queue_current.json` | provide a cleared native PDB and complete no-leak/operator provenance review | `prediction:3,ts:3,native:0,provenance:0,await_native:3` |
| `competitive_floor_target_identity_clearance_workorder` | `awaiting_native_or_provenance` | 0 | 3 | 3 | `casp17/casp17_competitive_floor_target_identity_clearance_workorder_current.json` | place a cleared native PDB and complete the no-leak provenance template | `native_provenance:3,native:0,provenance:0,dropzones:3,templates_preserved:3,stubs_preserved:3` |
| `competitive_floor_target_identity_clearance_manifest_sync` | `awaiting_provenance` | 0 | 3 | 3 | `casp17/casp17_competitive_floor_target_identity_clearance_manifest_sync_current.json` | complete the no-leak provenance template before syncing the manifest stub | `ready:0,awaiting_provenance:3,synced:0` |
| `competitive_floor_target_identity_clearance_workorder_audit` | `blocked` | 0 | 3 | 3 | `casp17/casp17_competitive_floor_target_identity_clearance_workorder_audit_current.json` | complete target-origin and no-leak evidence review before native/provenance promotion | `prediction:3,prediction_protein_atoms:1855,prediction_coordinate_valid:3,identity_discovery_blocked:3,identity_discovery_cleared:0,native:0,native_protein_atoms:0,native_coordinate_valid:0,provenance:0,evidence_ref:0,evidence_ref_verified:0,manifest:0,manifest_provenance_matched:0,manifest_provenance_mismatches:0,native_prediction_distinct:0,native_prediction_same:0` |
| `competitive_floor_target_identity_clearance_promotion_plan` | `blocked_by_audit` | 0 | 3 | 3 | `casp17/casp17_competitive_floor_target_identity_clearance_promotion_plan_current.json` | clear the native/provenance workorder audit before promotion | `audit_pass:0,promoted:0,manifest:0` |
| `competitive_floor_target_identity_clearance_intake_staging` | `waiting_on_promoted_manifest` | 0 | 0 | 0 | `casp17/casp17_competitive_floor_target_identity_clearance_intake_staging_plan_current.json` | wait for promoted clearance manifest rows | `promoted:0,staged:0,open_slots:15` |
| `competitive_floor_target_identity_clearance_candidate_intake_sync` | `waiting_on_staged_identity` | 0 | 15 | 15 | `casp17/casp17_competitive_floor_target_identity_clearance_candidate_intake_sync_current.json` | wait for clearance intake staging to produce staged_for_operator_review rows | `ready:0,waiting:15,applied:0` |
| `competitive_floor_target_identity_clearance_cycle` | `awaiting_provenance` | 1 | 5 | 6 | `casp17/casp17_competitive_floor_target_identity_clearance_cycle_current.json` | complete the no-leak provenance template before syncing the manifest stub | `sync:awaiting_provenance,audit:blocked,promotion:blocked_by_audit,staged:0` |
| `competitive_floor_identity_cycle` | `awaiting_intake` | 1 | 6 | 7 | `casp17/casp17_competitive_floor_identity_cycle_current.json` | fill proposed_benchmark_id, proposed_target_id, evidence_ref, and operator_clearance in the intake bundle | `sync:awaiting_intake,readiness:awaiting_identity,missing_fields:60` |
| `competitive_floor_file_source_plan` | `waiting_on_identity` | 0 | 180 | 180 | `casp17/casp17_competitive_floor_file_source_plan_current.json` | fill and apply the compact identity unlock kit first | `target_identity_required` |
| `competitive_floor_value_entry_plan` | `waiting_on_identity` | 0 | 270 | 270 | `casp17/casp17_competitive_floor_value_entry_plan_current.json` | fill and apply the compact identity unlock kit first | `target_identity_required` |
| `competitive_floor_execution_board` | `awaiting_identity` | 0 | 450 | 15 | `casp17/casp17_competitive_floor_execution_board_current.json` | fill proposed_benchmark_id, proposed_target_id, evidence_ref, and operator_clearance | `awaiting_identity` |
| `competitive_floor_readiness_gate` | `awaiting_identity` | 1 | 5 | 6 | `casp17/casp17_competitive_floor_readiness_gate_current.json` | fill proposed_benchmark_id, proposed_target_id, evidence_ref, and operator_clearance | `identity_gate` |
| `competitive_floor_value_ledger` | `awaiting_values` | 0 | 270 | 270 | `casp17/casp17_competitive_floor_value_ledger_current.json` | enter the cleared historical benchmark_id and cite the local target-selection evidence | `awaiting_value` |
| `competitive_floor_evidence_intake` | `awaiting_evidence` | 0 | 450 | 450 | `casp17/casp17_competitive_floor_evidence_intake_current.json` | fill benchmark_id in row_fill.csv from cleared local evidence | `awaiting_operator_value` |
| `competitive_floor_row_fill_patch_gate` | `awaiting_evidence` | 0 | 450 | 450 | `casp17/casp17_competitive_floor_row_fill_patch_gate_current.json` | provide the missing cleared evidence, then rerun intake and this patch gate | `awaiting_evidence` |
| `competitive_floor_row_fill_apply_plan` | `awaiting_evidence` | 0 | 450 | 450 | `casp17/casp17_competitive_floor_row_fill_apply_plan_current.json` | wait for cleared evidence, then rerun intake and patch gate | `awaiting_evidence` |
| `competitive_floor_operator_template` | `blocked` | 0 | 15 | 15 | `casp17/casp17_competitive_floor_batch_operator_template_current.json` | Fill batch row metadata, required file paths, provenance, and calibration until this candidate is ready_for_preflight. | `missing_files:0,placeholder_paths:180,provenance_blockers:150,calibration_blockers:90,row_fill_candidates:15` |
| `competitive_floor_operator_preflight` | `blocked` | 0 | 15 | 15 | `casp17/casp17_competitive_floor_batch_operator_preflight_current.json` | Resolve the first blocked competitive-floor operator row, then rerun the preflight. | `ablation_layer_prediction_pdb_missing,best_model_rank_required_1_to_5,best_native_metric_required_numeric,best_score_required_numeric,current_casp17_target_must_be_false,leakage_clearance_required,native_pdb_not_found,native_release_date_required_iso_date,operator_clearance_required,other_team_model_used_must_be_false,placeholder_target_id,post_release_information_used_must_be_false,prediction_created_at_required_iso_date,prediction_generated_before_native_release_required,prediction_pdb_not_found,public_template_or_native_used_for_prediction_must_be_false,selected_model_rank_required_1_to_5,selected_native_metric_required_numeric,selected_score_required_numeric` |
| `data_bundle` | `ready` | 798 | 0 | 798 | `casp17/casp17_data_bundle_manifest_current.json` | Refresh after new CASP17 runtime artifacts are generated. | `missing_bundle_count:0` |

## Current Target Folders

| target | status | protein/complex | folder |
| --- | --- | --- | --- |
| `T1331` | `ready` | 5AT | `casp17/targets_current/T1331_5AT` |
| `H1335` | `ready` | HCMV Merlin gHgLgO-Fab complex | `casp17/targets_current/H1335_HCMV_Merlin_gHgLgO_Fab_complex` |
| `H2312` | `ready` | EXT1-EXT2-2BAV4 | `casp17/targets_current/H2312_EXT1_EXT2_2BAV4` |
| `T2313` | `ready` | P66 | `casp17/targets_current/T2313_P66` |
| `H2338` | `ready` | Factor XIa antibody complex 9933 | `casp17/targets_current/H2338_Factor_XIa_antibody_complex_9933` |
| `H2339` | `ready` | Factor XIa antibody complex 7508 | `casp17/targets_current/H2339_Factor_XIa_antibody_complex_7508` |
| `H1340` | `ready` | Parahenipavirus F protein /antibody complex | `casp17/targets_current/H1340_Parahenipavirus_F_protein_antibody_complex` |
| `H1343` | `ready` | Hepatitis C Virus sE2 CBH-4G Fab complex | `casp17/targets_current/H1343_Hepatitis_C_Virus_sE2_CBH_4G_Fab_complex` |
| `H2319` | `ready` | Human astrovirus VA1 capsid spike - antibody 7C8 complex | `casp17/targets_current/H2319_Human_astrovirus_VA1_capsid_spike_antibody_7C8_complex` |
| `T1342` | `ready` | Spike glycoprotein ectodomain | `casp17/targets_current/T1342_Spike_glycoprotein_ectodomain` |
| `H1344` | `ready` | HSV gD - HAB72 | `casp17/targets_current/H1344_HSV_gD_HAB72` |
| `H2321` | `ready` | Human astrovirus VA1 capsid spike - antibody 2A2 complex | `casp17/targets_current/H2321_Human_astrovirus_VA1_capsid_spike_antibody_2A2_complex` |
| `H1346` | `ready` | REGN3753 Fab-Fab complex | `casp17/targets_current/H1346_REGN3753_Fab_Fab_complex` |
| `H1347` | `ready` | REGN15499 Fab-Fab complex | `casp17/targets_current/H1347_REGN15499_Fab_Fab_complex` |
| `H1348` | `ready` | gp130 antibody complex | `casp17/targets_current/H1348_gp130_antibody_complex` |
| `H1349` | `ready` | gp130 antibody complex | `casp17/targets_current/H1349_gp130_antibody_complex` |

## Claim Boundary

Local CASP17 workbench index only. It links current target model folders, benchmark input scaffolds, and win-gap packets; it does not fetch native structures, use external predictors, prove native accuracy, or submit to CASP.
