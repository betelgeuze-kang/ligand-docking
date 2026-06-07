# R2353 MassiveFold Acquisition Verification

- model_set_id: `R2353`
- tarball_url: `ftp://files.plbs.fr:21211/CASP17-CAPRI/R2353_all_cifs_MassiveFold.tar.gz`
- download_path: `casp17/massivefold_external_pool_intake/r2353/downloads/R2353_all_cifs_MassiveFold.tar.gz`
- sha256_path: `casp17/massivefold_external_pool_intake/r2353/hashes/R2353_all_cifs_MassiveFold.tar.gz.sha256`
- listing_path: `casp17/massivefold_external_pool_intake/r2353/extracted_models/tarball_listing.txt`
- verification_status: `verified_for_external_rerank_intake`
- tarball/size/hash/listing: `tarball_present`/`size_matches_declared`/`sha256_match`/`tarball_listing_present`

## Acquisition Commands

```bash
mkdir -p casp17/massivefold_external_pool_intake/r2353/downloads casp17/massivefold_external_pool_intake/r2353/hashes casp17/massivefold_external_pool_intake/r2353/extracted_models
curl --fail --location --continue-at - --output casp17/massivefold_external_pool_intake/r2353/downloads/R2353_all_cifs_MassiveFold.tar.gz 'ftp://files.plbs.fr:21211/CASP17-CAPRI/R2353_all_cifs_MassiveFold.tar.gz'
sha256sum casp17/massivefold_external_pool_intake/r2353/downloads/R2353_all_cifs_MassiveFold.tar.gz > casp17/massivefold_external_pool_intake/r2353/hashes/R2353_all_cifs_MassiveFold.tar.gz.sha256
tar -tzf casp17/massivefold_external_pool_intake/r2353/downloads/R2353_all_cifs_MassiveFold.tar.gz > casp17/massivefold_external_pool_intake/r2353/extracted_models/tarball_listing.txt
```

## Next Action

pool may be used only as an external rerank/accuracy-estimation input with provenance preserved

## Claim Boundary

MassiveFold acquisition verification board only. It checks local tarball, hash, and listing evidence for organizer-provided external model pools. These structures remain external rerank/accuracy-estimation pools, not internal predictions, not CASP submissions, and not competitive-proof evidence.
