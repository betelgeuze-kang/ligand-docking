# CASP17 Organizer Notice Packet

- generated: `2026-05-31T18:49:13+09:00`
- organizer_notice_status: `organizer_notice_intake_ready`
- source_notice_ref: `operator_email_excerpt_casp17_organizer`
- R2345 first request: `ignored_invalid_dna_t_in_rna_sequence`
- R2345 replacement request: `accepted_second_request_only`
- MassiveFold links: `15` RNA/hybrid `6` protein/complex `9`
- R2341 available: `True` `ftp://files.plbs.fr:21211/CASP17-CAPRI/R2341_all_cifs_MassiveFold.tar.gz`
- R2345 available: `True` `ftp://files.plbs.fr:21211/CASP17-CAPRI/R2345_all_cifs_MassiveFold.tar.gz`
- model_pool_policy: `external_rerank_accuracy_estimation_pool`
- internal_prediction_policy: `do_not_mark_as_internal_prediction`
- submission_policy: `rule_check_required_before_any_human_submission_use`
- next action: keep R2345 09:30 Pacific request quarantined, validate the 11:30 Pacific RNA sequence, and treat MassiveFold tarballs as external rerank/accuracy-estimation pools until CASP rule use is checked

## Notice Rows

| notice | target | type | status | action |
| - | - | - | - | - |
| `organizer_notice_001` | `R2345` | `sequence_request_quarantine` | `ignored_invalid_dna_t_in_rna_sequence` | `do_not_use_first_request_for_modeling_or_scoring` |
| `organizer_notice_002` | `R2345` | `sequence_request_replacement` | `accepted_second_request_only` | `treat_second_request_as_r2345_active_modeling_request` |
| `organizer_notice_003` | `R2341` | `massivefold_first_rna_set_available` | `massivefold_external_model_set_available` | `track_as_external_candidate_pool_for_rerank_and_accuracy_estimation` |
| `organizer_notice_004` | `R2345` | `massivefold_r2345_set_observed` | `massivefold_external_model_set_available` | `track_external_set_separately_from_internal_prediction_lane` |

## MassiveFold Links

| model_set | category | bundle | size_bytes | url |
| - | - | - | - | - |
| `H1311_T327` | `protein_or_complex` | `pdb_cif_bundle` | `1934629344` | `ftp://files.plbs.fr:21211/CASP17-CAPRI/H1311_T327_all_pdbs_MassiveFold.tar.gz` |
| `H2324_T328` | `protein_or_complex` | `pdb_cif_bundle` | `2015208150` | `ftp://files.plbs.fr:21211/CASP17-CAPRI/H2324_T328_all_pdbs_MassiveFold.tar.gz` |
| `H2312_T329` | `protein_or_complex` | `pdb_cif_bundle` | `3298849154` | `ftp://files.plbs.fr:21211/CASP17-CAPRI/H2312_T329_all_pdbs_MassiveFold.tar.gz` |
| `T2313_T330` | `protein_or_complex` | `pdb_cif_bundle` | `4188101793` | `ftp://files.plbs.fr:21211/CASP17-CAPRI/T2313_T330_all_pdbs_MassiveFold.tar.gz` |
| `H2338_T331` | `protein_or_complex` | `pdb_cif_bundle` | `2381698579` | `ftp://files.plbs.fr:21211/CASP17-CAPRI/H2338_T331_all_pdbs_MassiveFold.tar.gz` |
| `H2339_T332` | `protein_or_complex` | `pdb_cif_bundle` | `4709153238` | `ftp://files.plbs.fr:21211/CASP17-CAPRI/H2339_T332_all_pdbs_MassiveFold.tar.gz` |
| `R2341` | `rna_or_hybrid` | `cif_bundle` | `667779936` | `ftp://files.plbs.fr:21211/CASP17-CAPRI/R2341_all_cifs_MassiveFold.tar.gz` |
| `H2319_T333` | `protein_or_complex` | `pdb_cif_bundle` | `2269895275` | `ftp://files.plbs.fr:21211/CASP17-CAPRI/H2319_T333_all_pdbs_MassiveFold.tar.gz` |
| `H2321_T334` | `protein_or_complex` | `pdb_cif_bundle` | `2306336886` | `ftp://files.plbs.fr:21211/CASP17-CAPRI/H2321_T334_all_pdbs_MassiveFold.tar.gz` |
| `R2345` | `rna_or_hybrid` | `cif_bundle` | `245903877` | `ftp://files.plbs.fr:21211/CASP17-CAPRI/R2345_all_cifs_MassiveFold.tar.gz` |
| `R2350` | `rna_or_hybrid` | `cif_bundle` | `1362175616` | `ftp://files.plbs.fr:21211/CASP17-CAPRI/R2350_all_cifs_MassiveFold.tar.gz` |
| `R2351` | `rna_or_hybrid` | `cif_bundle` | `1361443421` | `ftp://files.plbs.fr:21211/CASP17-CAPRI/R2351_all_cifs_MassiveFold.tar.gz` |
| `R2352` | `rna_or_hybrid` | `cif_bundle` | `1362404890` | `ftp://files.plbs.fr:21211/CASP17-CAPRI/R2352_all_cifs_MassiveFold.tar.gz` |
| `R2353` | `rna_or_hybrid` | `cif_bundle` | `1378962270` | `ftp://files.plbs.fr:21211/CASP17-CAPRI/R2353_all_cifs_MassiveFold.tar.gz` |
| `H2335_T335` | `protein_or_complex` | `pdb_cif_bundle` | `4192785208` | `ftp://files.plbs.fr:21211/CASP17-CAPRI/H2335_T335_all_pdbs_MassiveFold.tar.gz` |
