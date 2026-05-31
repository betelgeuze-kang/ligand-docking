# CASP17 Historical Seed Native Replacement Candidates

- generated: `2026-05-31T14:47:54+09:00`
- status: `partial_native_replacement_candidates_ready`
- review-ready/source-required/file-blocked/complex-authority: `10/0/0/7`
- monomer candidates: `10`
- candidate dir: `casp17/historical_seed_native_replacement_candidates`
- first blocked: `HIST_COMPLEX_01_TCRUZI_PDE_EXTERNAL_PDEB1_010_CHEMBL4453005`
- next action: attach external native/source authority for this complex reference or replace the seed row

## Rows

| rank | target | scope | status | pdb | atoms | candidate | blockers |
| ---: | --- | --- | --- | --- | ---: | --- | --- |
| 1 | `HIST_BBA5` | `monomer` | `operator_review_ready` | `1T8J` | 386 | `casp17/historical_seed_native_replacement_candidates/01_hist_bba5/native_candidate_1T8J.pdb` | `-` |
| 2 | `HIST_CHIGNOLIN` | `monomer` | `operator_review_ready` | `1UAO` | 2484 | `casp17/historical_seed_native_replacement_candidates/02_hist_chignolin/native_candidate_1UAO.pdb` | `-` |
| 3 | `HIST_CRAMBIN` | `monomer` | `operator_review_ready` | `1CRN` | 327 | `casp17/historical_seed_native_replacement_candidates/03_hist_crambin/native_candidate_1CRN.pdb` | `-` |
| 4 | `HIST_FSD_1` | `monomer` | `operator_review_ready` | `1FSD` | 20664 | `casp17/historical_seed_native_replacement_candidates/04_hist_fsd_1/native_candidate_1FSD.pdb` | `-` |
| 5 | `HIST_GB1_MINI` | `monomer` | `operator_review_ready` | `2GB1` | 855 | `casp17/historical_seed_native_replacement_candidates/05_hist_gb1_mini/native_candidate_2GB1.pdb` | `-` |
| 6 | `HIST_PROTEIN_A_BDOMAIN` | `monomer` | `operator_review_ready` | `1BDD` | 941 | `casp17/historical_seed_native_replacement_candidates/06_hist_protein_a_bdomain/native_candidate_1BDD.pdb` | `-` |
| 7 | `HIST_TRP_CAGE` | `monomer` | `operator_review_ready` | `1L2Y` | 11552 | `casp17/historical_seed_native_replacement_candidates/07_hist_trp_cage/native_candidate_1L2Y.pdb` | `-` |
| 8 | `HIST_UBIQUITIN_MINI` | `monomer` | `operator_review_ready` | `1UBQ` | 660 | `casp17/historical_seed_native_replacement_candidates/08_hist_ubiquitin_mini/native_candidate_1UBQ.pdb` | `-` |
| 9 | `HIST_VILLIN_HP35` | `monomer` | `operator_review_ready` | `1YRF` | 731 | `casp17/historical_seed_native_replacement_candidates/09_hist_villin_hp35/native_candidate_1YRF.pdb` | `-` |
| 10 | `HIST_WW_DOMAIN_FIP35` | `monomer` | `operator_review_ready` | `2F21` | 1403 | `casp17/historical_seed_native_replacement_candidates/10_hist_ww_domain_fip35/native_candidate_2F21.pdb` | `-` |
| 11 | `HIST_COMPLEX_01_TCRUZI_PDE_EXTERNAL_PDEB1_010_CHEMBL4453005` | `complex` | `native_authority_ref_required` | `-` | 0 | `-` | `external_native_or_source_authority_required` |
| 12 | `HIST_COMPLEX_02_TCRUZI_PDE_EXTERNAL_PDEB1_043_CHEMBL2171451` | `complex` | `native_authority_ref_required` | `-` | 0 | `-` | `external_native_or_source_authority_required` |
| 13 | `HIST_COMPLEX_03_TCRUZI_PDE_EXTERNAL_PDEB1_025_CHEMBL4441871` | `complex` | `native_authority_ref_required` | `-` | 0 | `-` | `external_native_or_source_authority_required` |
| 14 | `HIST_COMPLEX_04_TCRUZI_PDE_EXTERNAL_PDEB1_032_CHEMBL4445930` | `complex` | `native_authority_ref_required` | `-` | 0 | `-` | `external_native_or_source_authority_required` |
| 15 | `HIST_COMPLEX_05_TCRUZI_PDE_EXTERNAL_PDEB1_007_CHEMBL3764370` | `complex` | `native_authority_ref_required` | `-` | 0 | `-` | `external_native_or_source_authority_required` |
| 16 | `HIST_COMPLEX_06_TCRUZI_PDE_EXTERNAL_PDEB1_017_CHEMBL3765606` | `complex` | `native_authority_ref_required` | `-` | 0 | `-` | `external_native_or_source_authority_required` |
| 17 | `HIST_COMPLEX_07_TCRUZI_PDE_BINDINGDB_PDEB1_007_BDB50397079` | `complex` | `native_authority_ref_required` | `-` | 0 | `-` | `external_native_or_source_authority_required` |

## Claim Boundary

Local CASP17 historical seed native replacement candidate packet only. It copies existing public RCSB-derived PDB files into per-seed review folders and records authority references for operator review. It does not replace active native files, mutate operator CSVs, clear no-leak provenance, score native accuracy, fetch missing structures, run predictors, or submit to CASP.
