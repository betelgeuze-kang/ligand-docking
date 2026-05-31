# CASP17 Strict-Blind Internal Prediction Source Apply Plan

- status: `blocked_until_internal_prediction_source_gate_passes`
- required benchmark/target/scope: `hist_REQUIRED_MONOMER_001` `REQUIRED_MONOMER_001` `monomer`
- gate: `awaiting_internal_prediction_source_gate_fields`
- actions ready/blocked/total: `0/16/16`
- first blocker: `internal_prediction_apply_001` `internal_prediction_source_gate_not_ready`
- next action: copy verified internal prediction PDB into the first-slot prediction dropzone

Local CASP17 strict-blind internal prediction source apply plan only. It maps a gate-passed internal prediction source manifest to first-slot dropzone and operator-value actions. It is fail-closed: when the source gate is not ready, every action remains blocked. It does not copy files, mutate operator/intake CSVs, approve provenance, compute CASP metrics, push remotes, or submit to CASP.
