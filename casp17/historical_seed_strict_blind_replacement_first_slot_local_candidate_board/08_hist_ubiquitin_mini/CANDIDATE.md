# HIST_UBIQUITIN_MINI First Slot Local Candidate

- status: `blocked_chronology_not_strict_blind`
- benchmark: `hist_seed_ubiquitin_mini`
- scope: `monomer`
- strict blind eligible: `False`
- competitive proof allowed: `False`
- prediction/native present: `True/True`
- prediction created/native release/before-native: `2026-02-19` `1987-01-02` `False`
- no-leak ready/open: `False/10`
- ablation/calibration ready: `False/False`
- blockers: `prediction_not_before_native,no_leak_not_ready,ablation_not_ready,calibration_not_ready,strict_blind_not_eligible`
- next action: find or attach a prediction artifact created before authoritative native release

## Evidence Pointers

- prediction_pdb: `data/internal_structures_refined/nightly/2026-02-19-ops-full-dashboard-r1/visual_post_internal_post_ubiquitin_mini_sample000_step00020.pdb`
- native_pdb: `casp17/historical_seed_native_replacement_candidates/08_hist_ubiquitin_mini/native_candidate_1UBQ.pdb`
- native_authority_ref: `rcsb:1UBQ;doi:10.2210/pdb1ubq/pdb`
- no_leak_dossier: `casp17/historical_seed_no_leak_provenance_dossiers/08_hist_ubiquitin_mini_no_leak_provenance.md`
- ablation_manifest_ref: `casp17/historical_seed_ablation_candidate_manifests/08_hist_ubiquitin_mini_ablation_candidates.csv`
- calibration_values_ref: `casp17/historical_seed_calibration_candidate_ledgers/08_hist_ubiquitin_mini_calibration_candidates.csv`

## Claim Boundary

Local CASP17 first-slot strict-blind replacement local candidate board only. It aggregates existing local historical seed prediction/native/calibration/ablation/provenance artifacts into fail-closed candidates for the current first replacement slot. It does not promote candidates, create evidence, approve no-leak provenance, rewrite intake CSVs, compute CASP metrics, or submit to CASP.
