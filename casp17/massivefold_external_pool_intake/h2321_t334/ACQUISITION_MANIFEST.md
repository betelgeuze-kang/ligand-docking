# H2321_T334 MassiveFold External Pool

- pool_id: `massivefold_external_pool_009`
- primary_target_id: `H2321`
- target_category: `protein_or_complex`
- bundle_format: `pdb_cif_bundle`
- tarball_url: `ftp://files.plbs.fr:21211/CASP17-CAPRI/H2321_T334_all_pdbs_MassiveFold.tar.gz`
- ftp_size_bytes: `2306336886`
- model_pool_policy: `external_rerank_accuracy_estimation_pool`
- internal_prediction_policy: `do_not_mark_as_internal_prediction`
- competitive_proof_eligible: `False`
- submission_policy: `rule_check_required_before_any_human_submission_use`
- download_policy: `operator_explicit_download_required_no_automatic_tarball_fetch`
- sequence_guard: `-`

## Operator Acquisition Commands

Run only when this external pool is intentionally needed for rerank or accuracy-estimation experiments.

```bash
mkdir -p casp17/massivefold_external_pool_intake/h2321_t334/downloads casp17/massivefold_external_pool_intake/h2321_t334/extracted_models casp17/massivefold_external_pool_intake/h2321_t334/hashes
curl -L -o casp17/massivefold_external_pool_intake/h2321_t334/downloads/H2321_T334_all_pdbs_MassiveFold.tar.gz 'ftp://files.plbs.fr:21211/CASP17-CAPRI/H2321_T334_all_pdbs_MassiveFold.tar.gz'
sha256sum casp17/massivefold_external_pool_intake/h2321_t334/downloads/H2321_T334_all_pdbs_MassiveFold.tar.gz > casp17/massivefold_external_pool_intake/h2321_t334/hashes/H2321_T334_all_pdbs_MassiveFold.tar.gz.sha256
tar -tzf casp17/massivefold_external_pool_intake/h2321_t334/downloads/H2321_T334_all_pdbs_MassiveFold.tar.gz > casp17/massivefold_external_pool_intake/h2321_t334/extracted_models/tarball_listing.txt
```

## Claim Boundary

Local CASP17 MassiveFold external-pool intake only. It records organizer-provided tarball links, per-target acquisition folders, and rerank/accuracy-estimation guardrails. It does not download large tarballs, submit CASP models, or convert external MassiveFold structures into internal competitive-proof predictions.
