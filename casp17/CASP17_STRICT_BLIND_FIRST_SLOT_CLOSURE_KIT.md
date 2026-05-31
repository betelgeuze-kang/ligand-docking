# CASP17 Strict-Blind First Slot Closure Kit

- generated: `2026-06-01T03:36:10+09:00`
- status: `blocked_on_internal_prediction_source_gate`
- required benchmark/target/scope: `hist_REQUIRED_MONOMER_001` `REQUIRED_MONOMER_001` `monomer`
- steps ready/blocked/total: `0/7/7`
- fill items source-gate/source-request/file/operator/total: `11/17/12/20/60`
- source-gate operator packet: `awaiting_source_gate_operator_values` ready/awaiting/total `0/11/11` patch `0/11` csv `casp17/strict_blind_source_gate_operator_packet/hist_REQUIRED_MONOMER_001/source_gate_operator_values.csv`
- source-gate source requests: `awaiting_pre_native_source_or_candidate_replacement` pre-native/replacement/operator-repair/total `10/7/0/17` first `source_request_001` `HIST_BBA5` `pre_native_prediction_source_required` `prediction_not_before_native` folder `casp17/strict_blind_source_gate_source_request_packet`
- source/apply/dropzone/operator/intake: `awaiting_internal_prediction_source_gate_fields` `blocked_until_internal_prediction_source_gate_passes` `awaiting_strict_blind_evidence_files` `awaiting_operator_values` `awaiting_operator_input`
- first blocker: `internal_prediction_source_gate` `internal_source_id_missing_or_external`
- kit folder: `casp17/strict_blind_first_slot_closure_kit/hist_REQUIRED_MONOMER_001`

## Steps

| step | status | ready/blocked/total | artifact | first blocker | next action |
| --- | --- | --- | --- | --- | --- |
| `internal_prediction_source_gate` | `awaiting_internal_prediction_source_gate_fields` | `3/13/16` | `casp17/casp17_strict_blind_internal_prediction_source_gate_current.json` | `internal_source_id_missing_or_external` | set source_id to an internal pre-native prediction source, not an official archive or MassiveFold pool |
| `source_gate_operator_packet` | `awaiting_source_gate_operator_values` | `0/11/11` | `casp17/strict_blind_source_gate_operator_packet/hist_REQUIRED_MONOMER_001/source_gate_operator_values.csv` | `source_id:awaiting_operator_value` | set source_id to an internal pre-native prediction source, not an official archive or MassiveFold pool |
| `source_gate_source_requests` | `awaiting_pre_native_source_or_candidate_replacement` | `0/17/17` | `casp17/strict_blind_source_gate_source_request_packet` | `source_request_001:prediction_not_before_native` | attach a prediction artifact created before the authoritative native release date, with timestamp and no-leak evidence |
| `internal_prediction_apply_plan` | `blocked_until_internal_prediction_source_gate_passes` | `0/16/16` | `casp17/casp17_strict_blind_internal_prediction_source_apply_plan_current.json` | `internal_prediction_source_gate_not_ready` | copy verified internal prediction PDB into the first-slot prediction dropzone |
| `first_slot_evidence_files` | `awaiting_strict_blind_evidence_files` | `0/6/6` | `casp17/historical_seed_strict_blind_replacement_evidence_dropzones/01_hist_required_monomer_001` | `missing_files:6,operator_values_required:10` | place strict-blind evidence files in this dropzone, then rerun dropzone and intake preflight |
| `first_slot_operator_values` | `awaiting_operator_values` | `0/10/10` | `casp17/historical_seed_strict_blind_replacement_intake/01_hist_required_monomer_001/replacement_operator_values.csv` | `replacement_target_id` | fill operator_value for replacement_target_id in replacement_operator_values.csv |
| `first_slot_intake_preflight` | `awaiting_operator_input` | `0/16/16` | `casp17/historical_seed_strict_blind_replacement_intake/01_hist_required_monomer_001/replacement_candidate_intake.csv` | `replacement_target_id_required,replacement_benchmark_id_required,target_identity_non_current_historical_required,prediction_pdb_required,native_pdb_required,native_authority_ref_required,prediction_created_at_required,native_release_date_required,prediction_generated_before_native_release_required,no_leak_evidence_ref_required,public_template_or_native_used_for_prediction_required,other_team_model_used_required,post_release_information_used_required,ablation_manifest_ref_required,calibration_values_ref_required,operator_clearance_required` | fill replacement_candidate_intake.csv with strict-blind evidence, then rerun intake preflight |

Local CASP17 first-slot closure kit only. It gathers existing source gate, source-acquisition request, apply-plan, evidence-dropzone, operator-value, and intake-preflight blockers for the first strict-blind historical slot. It does not fetch external archives, create or copy evidence files, mutate intake/operator CSVs, approve provenance, compute CASP metrics, push remotes, or submit to CASP.
