# R2353 RNA/Hybrid MassiveFold Priority Action

- queue_rank: `6`
- queue_id: `rna_hybrid_massivefold_priority_006`
- model_set_id: `R2353`
- priority_reason: `rna_hybrid_massivefold_pool_from_organizer_ftp_listing`
- row_status: `ready_for_rule_checked_external_pool_acquisition`
- tarball_url: `ftp://files.plbs.fr:21211/CASP17-CAPRI/R2353_all_cifs_MassiveFold.tar.gz`
- acquisition_manifest: `casp17/massivefold_external_pool_intake/r2353/ACQUISITION_MANIFEST.md`
- sequence_guard: `-`
- r2345_invalid_request_status: `-`
- r2345_active_request_status: `-`
- internal_prediction_policy: `do_not_mark_as_internal_prediction`
- competitive_proof_eligible: `False`
- download_policy: `operator_explicit_download_required_no_automatic_tarball_fetch`

## Next Action

rule-check external MassiveFold use, download only into the external-pool folder, hash the tarball, extract a listing, then run rerank/accuracy-estimation experiments without internal-proof claims

## Claim Boundary

RNA/hybrid MassiveFold priority queue only. These rows are organizer-provided external model pools for rule-checked reranking and accuracy-estimation work. They are not internal predictions, not CASP submissions, and not competitive-proof evidence.
