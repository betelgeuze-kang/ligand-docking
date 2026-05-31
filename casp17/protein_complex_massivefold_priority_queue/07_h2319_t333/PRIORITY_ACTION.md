# H2319 Protein/Complex MassiveFold Priority Action

- queue_rank: `7`
- queue_id: `protein_complex_massivefold_priority_007`
- pool_id: `massivefold_external_pool_008`
- model_set_id: `H2319_T333`
- priority_reason: `protein_heteromer_or_immune_complex_massivefold_pool_from_organizer_ftp_listing`
- row_status: `ready_for_rule_checked_external_pool_acquisition`
- tarball_url: `ftp://files.plbs.fr:21211/CASP17-CAPRI/H2319_T333_all_pdbs_MassiveFold.tar.gz`
- acquisition_manifest: `casp17/massivefold_external_pool_intake/h2319_t333/ACQUISITION_MANIFEST.md`
- internal_prediction_policy: `do_not_mark_as_internal_prediction`
- competitive_proof_eligible: `False`
- download_policy: `operator_explicit_download_required_no_automatic_tarball_fetch`

## Next Action

rule-check external MassiveFold use, download only into the external-pool folder, hash the tarball, extract a listing, then run protein/complex rerank and accuracy-estimation experiments without internal-proof claims

## Claim Boundary

Protein/complex MassiveFold priority queue only. These rows are organizer-provided external model pools for rule-checked reranking and accuracy-estimation work on CASP17 protein, immune, and complex targets. They are not internal predictions, not CASP submissions, and not competitive-proof evidence.
