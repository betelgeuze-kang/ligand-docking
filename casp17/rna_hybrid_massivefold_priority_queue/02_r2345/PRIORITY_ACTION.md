# R2345 RNA/Hybrid MassiveFold Priority Action

- queue_rank: `2`
- queue_id: `rna_hybrid_massivefold_priority_002`
- model_set_id: `R2345`
- priority_reason: `corrected_1130_pacific_request_only_with_0930_invalid_dna_t_request_quarantined`
- row_status: `ready_for_rule_checked_external_pool_acquisition`
- tarball_url: `ftp://files.plbs.fr:21211/CASP17-CAPRI/R2345_all_cifs_MassiveFold.tar.gz`
- acquisition_manifest: `casp17/massivefold_external_pool_intake/r2345/ACQUISITION_MANIFEST.md`
- sequence_guard: `ignore_0930_pacific_invalid_dna_t_request_use_1130_replacement_only`
- r2345_invalid_request_status: `ignored_invalid_dna_t_in_rna_sequence`
- r2345_active_request_status: `accepted_second_request_only`
- internal_prediction_policy: `do_not_mark_as_internal_prediction`
- competitive_proof_eligible: `False`
- download_policy: `operator_explicit_download_required_no_automatic_tarball_fetch`

## Next Action

rule-check external MassiveFold use, download only into the external-pool folder, hash the tarball, extract a listing, then run rerank/accuracy-estimation experiments without internal-proof claims

## Claim Boundary

RNA/hybrid MassiveFold priority queue only. These rows are organizer-provided external model pools for rule-checked reranking and accuracy-estimation work. They are not internal predictions, not CASP submissions, and not competitive-proof evidence.
