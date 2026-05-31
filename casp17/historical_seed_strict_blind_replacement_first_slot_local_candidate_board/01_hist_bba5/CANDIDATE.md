# HIST_BBA5 First Slot Local Candidate

- status: `blocked_chronology_not_strict_blind`
- benchmark: `hist_seed_bba5`
- scope: `monomer`
- strict blind eligible: `False`
- competitive proof allowed: `False`
- prediction/native present: `True/True`
- prediction created/native release/before-native: `2026-02-19` `2004-05-13` `False`
- no-leak ready/open: `False/10`
- ablation/calibration ready: `False/False`
- blockers: `prediction_not_before_native,no_leak_not_ready,ablation_not_ready,calibration_not_ready,strict_blind_not_eligible`
- next action: find or attach a prediction artifact created before authoritative native release

## Evidence Pointers

- prediction_pdb: `data/internal_structures_refined/nightly/2026-02-19-ops-full-dashboard-r1/visual_post_internal_post_bba5_sample000_step00020.pdb`
- native_pdb: `casp17/historical_seed_native_replacement_candidates/01_hist_bba5/native_candidate_1T8J.pdb`
- native_authority_ref: `rcsb:1T8J;doi:10.2210/pdb1t8j/pdb`
- no_leak_dossier: `casp17/historical_seed_no_leak_provenance_dossiers/01_hist_bba5_no_leak_provenance.md`
- ablation_manifest_ref: `casp17/historical_seed_ablation_candidate_manifests/01_hist_bba5_ablation_candidates.csv`
- calibration_values_ref: `casp17/historical_seed_calibration_candidate_ledgers/01_hist_bba5_calibration_candidates.csv`

## Claim Boundary

Local CASP17 first-slot strict-blind replacement local candidate board only. It aggregates existing local historical seed prediction/native/calibration/ablation/provenance artifacts into fail-closed candidates for the current first replacement slot. It does not promote candidates, create evidence, approve no-leak provenance, rewrite intake CSVs, compute CASP metrics, or submit to CASP.
