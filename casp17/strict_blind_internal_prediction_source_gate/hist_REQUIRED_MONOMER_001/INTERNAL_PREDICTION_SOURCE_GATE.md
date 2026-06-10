# CASP17 Strict-Blind Internal Prediction Source Gate

- status: `internal_prediction_source_ready_for_first_slot_dropzone`
- required benchmark/target/scope: `hist_REQUIRED_MONOMER_001` `REQUIRED_MONOMER_001` `monomer`
- checks pass/blocked/total: `16/0/16`
- manifest: `casp17/strict_blind_internal_prediction_source_audit/hist_REQUIRED_MONOMER_001/internal_prediction_source_manifest_template.csv`
- prediction/dropzone: `casp17/historical_seed_strict_blind_replacement_evidence_dropzones/01_hist_required_monomer_001/prediction/replacement_prediction.pdb` `casp17/historical_seed_strict_blind_replacement_evidence_dropzones/01_hist_required_monomer_001/prediction/replacement_prediction.pdb`
- first blocker: `-` `-`
- next action: -

Local CASP17 strict-blind internal prediction source gate only. It validates operator-provided manifest fields, prediction PDB presence, basic PDB atom records, chronology, no-leak evidence, and operator clearance for the first historical strict-blind slot. It does not create or copy prediction files, approve provenance, mutate strict-blind intake CSVs, compute CASP metrics, push remotes, or submit to CASP.
