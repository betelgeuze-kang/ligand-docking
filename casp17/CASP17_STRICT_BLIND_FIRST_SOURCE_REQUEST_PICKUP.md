# CASP17 Strict-Blind First Source Request Pickup

- generated: `2026-06-01T21:39:53+09:00`
- status: `first_source_request_requires_pre_native_source`
- request/target: `source_request_001` `HIST_BBA5` `monomer`
- current prediction/native dates: `2026-02-19` / `2004-05-13` before-native `False`
- options ready/blocked/total: `0/3/3`
- first blocker: `first_source_pickup_001` `prediction_not_before_native`
- pickup folder: `casp17/strict_blind_first_source_request_pickup/source_request_001_hist_bba5`
- next action: attach a prediction artifact created before the authoritative native release date, with timestamp and no-leak evidence

## Actions

| action | status | target | resolution | before native | blocker | next action |
| --- | --- | --- | --- | --- | --- | --- |
| `first_source_pickup_001` | `operator_input_required` | `HIST_BBA5` | `acquire_pre_native_prediction_source` | `False` | `prediction_not_before_native` | attach a prediction artifact created before the authoritative native release date, with timestamp and no-leak evidence |
| `first_source_pickup_002` | `blocked_no_pre_native_in_scope_candidate` | `HIST_BBA5` | `replace_candidate` | `False` | `no_allowed_first_slot_candidate` | source a different in-scope monomer candidate only if it has pre-native prediction provenance |
| `first_source_pickup_003` | `context_only_not_first_slot_resolution` | `HIST_BBA5` | `defer_current_slot` | `False` | `complex_candidates_out_of_scope_for_required_monomer_slot` | keep complex/ligand candidates out of this monomer slot until their own strict-blind lane is active |

## Claim Boundary

Local CASP17 strict-blind first-source-request pickup only. It materializes the first source request into an operator decision packet for pre-native prediction sourcing or candidate replacement. It does not create prediction/native files, approve provenance, copy files into source manifests, compute CASP metrics, push remotes, or submit to CASP.
