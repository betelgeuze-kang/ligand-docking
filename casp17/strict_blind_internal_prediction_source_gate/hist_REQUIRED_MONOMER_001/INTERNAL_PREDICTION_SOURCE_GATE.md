# CASP17 Strict-Blind Internal Prediction Source Gate

- status: `awaiting_internal_prediction_source_gate_fields`
- required benchmark/target/scope: `hist_REQUIRED_MONOMER_001` `REQUIRED_MONOMER_001` `monomer`
- checks pass/blocked/total: `3/13/16`
- manifest: `casp17/strict_blind_internal_prediction_source_audit/hist_REQUIRED_MONOMER_001/internal_prediction_source_manifest_template.csv`
- prediction/dropzone: `-` `casp17/historical_seed_strict_blind_replacement_evidence_dropzones/01_hist_required_monomer_001/prediction/replacement_prediction.pdb`
- first blocker: `source_id_internal` `internal_source_id_missing_or_external`
- next action: set source_id to an internal pre-native prediction source, not an official archive or MassiveFold pool

Local CASP17 strict-blind internal prediction source gate only. It validates operator-provided manifest fields, prediction PDB presence, basic PDB atom records, chronology, no-leak evidence, and operator clearance for the first historical strict-blind slot. It does not create or copy prediction files, approve provenance, mutate strict-blind intake CSVs, compute CASP metrics, push remotes, or submit to CASP.
