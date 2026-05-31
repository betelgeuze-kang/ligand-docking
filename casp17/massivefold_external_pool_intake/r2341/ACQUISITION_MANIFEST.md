# R2341 MassiveFold External Pool

- pool_id: `massivefold_external_pool_007`
- primary_target_id: `R2341`
- target_category: `rna_or_hybrid`
- bundle_format: `cif_bundle`
- tarball_url: `ftp://files.plbs.fr:21211/CASP17-CAPRI/R2341_all_cifs_MassiveFold.tar.gz`
- ftp_size_bytes: `667779936`
- model_pool_policy: `external_rerank_accuracy_estimation_pool`
- internal_prediction_policy: `do_not_mark_as_internal_prediction`
- competitive_proof_eligible: `False`
- submission_policy: `rule_check_required_before_any_human_submission_use`
- download_policy: `operator_explicit_download_required_no_automatic_tarball_fetch`
- sequence_guard: `-`

## Operator Acquisition Commands

Run only when this external pool is intentionally needed for rerank or accuracy-estimation experiments.

```bash
mkdir -p casp17/massivefold_external_pool_intake/r2341/downloads casp17/massivefold_external_pool_intake/r2341/extracted_models casp17/massivefold_external_pool_intake/r2341/hashes
curl -L -o casp17/massivefold_external_pool_intake/r2341/downloads/R2341_all_cifs_MassiveFold.tar.gz 'ftp://files.plbs.fr:21211/CASP17-CAPRI/R2341_all_cifs_MassiveFold.tar.gz'
sha256sum casp17/massivefold_external_pool_intake/r2341/downloads/R2341_all_cifs_MassiveFold.tar.gz > casp17/massivefold_external_pool_intake/r2341/hashes/R2341_all_cifs_MassiveFold.tar.gz.sha256
tar -tzf casp17/massivefold_external_pool_intake/r2341/downloads/R2341_all_cifs_MassiveFold.tar.gz > casp17/massivefold_external_pool_intake/r2341/extracted_models/tarball_listing.txt
```

## Claim Boundary

Local CASP17 MassiveFold external-pool intake only. It records organizer-provided tarball links, per-target acquisition folders, and rerank/accuracy-estimation guardrails. It does not download large tarballs, submit CASP models, or convert external MassiveFold structures into internal competitive-proof predictions.
