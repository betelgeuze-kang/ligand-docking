# CASP17 Strict-Blind First Source Request Pickup

- status: `first_source_request_requires_pre_native_source`
- request/target: `source_request_001` `HIST_BBA5` `monomer`
- current prediction/native dates: `2026-02-19` / `2004-05-13`
- current prediction before native: `False`
- first blocker: `first_source_pickup_001` `prediction_not_before_native`
- decision template: `casp17/strict_blind_first_source_request_pickup/source_request_001_hist_bba5/operator_decision_template.csv`
- required files: `casp17/strict_blind_first_source_request_pickup/source_request_001_hist_bba5/required_files_manifest.csv`
- source request template: `casp17/strict_blind_source_gate_source_request_packet/source_request_001/operator_source_values_template.csv`

## Options

| action | status | resolution | required input | blocker | next action |
| --- | --- | --- | --- | --- | --- |
| `first_source_pickup_001` | `operator_input_required` | `acquire_pre_native_prediction_source` | pre-native internal prediction PDB, source id, timestamp evidence, and no-leak provenance | `prediction_not_before_native` | attach a prediction artifact created before the authoritative native release date, with timestamp and no-leak evidence |
| `first_source_pickup_002` | `blocked_no_pre_native_in_scope_candidate` | `replace_candidate` | strict-blind monomer candidate whose prediction predates native release | `no_allowed_first_slot_candidate` | source a different in-scope monomer candidate only if it has pre-native prediction provenance |
| `first_source_pickup_003` | `context_only_not_first_slot_resolution` | `defer_current_slot` | none for monomer first slot; keep complex candidates in their category lane | `complex_candidates_out_of_scope_for_required_monomer_slot` | keep complex/ligand candidates out of this monomer slot until their own strict-blind lane is active |

## Claim Boundary

Local CASP17 strict-blind first-source-request pickup only. It materializes the first source request into an operator decision packet for pre-native prediction sourcing or candidate replacement. It does not create prediction/native files, approve provenance, copy files into source manifests, compute CASP metrics, push remotes, or submit to CASP.
