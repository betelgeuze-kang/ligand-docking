# CASP17 Strict-Blind First Slot Source Bridge

- status: `first_slot_source_bridge_internal_prediction_required`
- required benchmark/target/scope: `hist_REQUIRED_MONOMER_001` `REQUIRED_MONOMER_001` `monomer`
- official candidates ready/total: `24/24`
- native authority bridge ready: `2`
- official prediction baseline-only/import-blocked: `24/24`
- auto-apply allowed: `0`
- first candidate: `CASP16` `T1212` `9b0l`
- first blocker: `internal_pre_native_prediction_pdb_required`
- next action: provide a pre-native internal prediction PDB; use official archive files only for native authority/baseline review

## Field Bridge

| field | status | allowed use | candidate value | evidence | destination | next action |
| --- | --- | --- | --- | --- | --- | --- |
| `replacement_target_id` | `operator_review_ready` | target_identity_preview_only | `CASP16_T1212` | `casp17/historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates/001_casp16_t1212` | `` | operator must accept the historical target identity before any intake mutation |
| `prediction_pdb` | `blocked_internal_prediction_required` | official_archive_prediction_tarball_baseline_only_not_internal_proof | `https://predictioncenter.org/download_area/CASP16/predictions/regular/T1212.tar.gz` | `casp17/historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates/001_casp16_t1212` | `casp17/historical_seed_strict_blind_replacement_evidence_dropzones/01_hist_required_monomer_001/prediction/replacement_prediction.pdb` | supply a pre-native internal prediction PDB; keep official archive models in baseline lane only |
| `native_pdb` | `native_authority_candidate_ready_for_operator_download` | native_reference_candidate_after_operator_target_selection | `https://files.rcsb.org/download/9B0L.pdb` | `https://www.rcsb.org/structure/9b0l` | `casp17/historical_seed_strict_blind_replacement_evidence_dropzones/01_hist_required_monomer_001/native/replacement_native.pdb` | operator may fetch this native PDB into the dropzone after accepting the target identity |
| `native_authority_ref` | `native_authority_ref_candidate_ready` | native_authority_markdown_candidate_after_operator_target_selection | `https://www.rcsb.org/structure/9b0l` | `casp17/historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates/001_casp16_t1212` | `casp17/historical_seed_strict_blind_replacement_evidence_dropzones/01_hist_required_monomer_001/authority/native_authority.md` | write native authority markdown only after the target identity is accepted |
| `prediction_created_at` | `operator_value_candidate_ready` | chronology_candidate_from_archive_metadata | `2024-06-03` | `https://predictioncenter.org/download_area/CASP16/predictions/regular/` | `` | operator must confirm archive timestamp semantics before using this date |
| `native_release_date` | `operator_value_candidate_ready` | native_public_anchor_date_candidate | `2025-02-01` | `https://predictioncenter.org/download_area/CASP16/targets/` | `` | operator must confirm the native/public anchor date before using this date |
| `no_leak_evidence_ref` | `operator_evidence_required` | not_available_from_official_archive_candidate | `` | `` | `casp17/historical_seed_strict_blind_replacement_evidence_dropzones/01_hist_required_monomer_001/no_leak/no_leak_evidence.md` | attach independent no-leak evidence for the internal prediction source |
| `ablation_manifest_ref` | `operator_evidence_required` | same_run_ablation_required_not_archive_baseline | `` | `` | `casp17/historical_seed_strict_blind_replacement_evidence_dropzones/01_hist_required_monomer_001/ablation/ablation_manifest.json` | attach true same-run/pre-minimization ablation layers for the internal prediction |
| `calibration_values_ref` | `operator_evidence_required` | calibration_required_for_internal_model_selection | `` | `` | `casp17/historical_seed_strict_blind_replacement_evidence_dropzones/01_hist_required_monomer_001/calibration/calibration_values.json` | attach calibration values for model1/best-of-5 ranking after internal prediction is supplied |

Local CASP17 first-slot source bridge only. It converts official CASP15/16 archive candidate metadata into a fail-closed operator preview for the first strict-blind slot. Official archive native structures may guide native authority review, but official archive prediction tarballs remain external/other-team baseline material and are not internal competitive-proof predictions. This tool does not download files, create evidence, approve no-leak provenance, mutate intake CSVs, compute CASP metrics, or submit to CASP.
