# CASP16 T1212 Official Archive Baseline

- baseline_candidate_id: `official_archive_baseline_001`
- source_candidate_id: `official_archive_source_001`
- lane_type: `official_archive_baseline_replay`
- competitive_proof_eligible: `False`
- strict_blind_intake_policy: `do_not_import_as_internal_prediction`
- other_team_model_policy: `official_archive_models_are_baseline_only`
- model1_selection_policy: `model1_and_best_of_5_may_be_scored_only_as_external_baseline`
- download_policy: `operator_explicit_download_required_no_automatic_tarball_fetch`
- prediction_tarball_url: `https://predictioncenter.org/download_area/CASP16/predictions/regular/T1212.tar.gz`
- native_structure_file_url: `https://files.rcsb.org/download/9B0L.pdb`
- prediction/native dates: `2024-06-03 09:22` `2025-02-01`

## Operator Acquisition Commands

Run these only when you intentionally want an external official-archive baseline replay copy.

```bash
mkdir -p casp17/historical_seed_official_archive_baseline_lane/001_casp16_t1212_fanzor2_ternary_structure_protein_subunit_of_m1212/downloads casp17/historical_seed_official_archive_baseline_lane/001_casp16_t1212_fanzor2_ternary_structure_protein_subunit_of_m1212/models casp17/historical_seed_official_archive_baseline_lane/001_casp16_t1212_fanzor2_ternary_structure_protein_subunit_of_m1212/native
curl -L -o casp17/historical_seed_official_archive_baseline_lane/001_casp16_t1212_fanzor2_ternary_structure_protein_subunit_of_m1212/downloads/T1212.tar.gz 'https://predictioncenter.org/download_area/CASP16/predictions/regular/T1212.tar.gz'
curl -L -o casp17/historical_seed_official_archive_baseline_lane/001_casp16_t1212_fanzor2_ternary_structure_protein_subunit_of_m1212/native/9B0L.pdb 'https://files.rcsb.org/download/9B0L.pdb'
```

## Claim Boundary

Local CASP17 official-archive baseline replay lane only. It separates official CASP15/16 archive submissions from strict-blind internal prediction evidence. Rows here may be useful for historical leaderboard-style baseline replay, model-ranking calibration, and metric-surface smoke tests, but they are not competitive-proof evidence and must not be imported as internal CASP17 predictions.
