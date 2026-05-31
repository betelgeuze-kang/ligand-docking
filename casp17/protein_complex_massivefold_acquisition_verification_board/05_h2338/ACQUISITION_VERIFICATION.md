# H2338 MassiveFold Acquisition Verification

- model_set_id: `H2338_T331`
- tarball_url: `ftp://files.plbs.fr:21211/CASP17-CAPRI/H2338_T331_all_pdbs_MassiveFold.tar.gz`
- download_path: `casp17/massivefold_external_pool_intake/h2338_t331/downloads/H2338_T331_all_pdbs_MassiveFold.tar.gz`
- sha256_path: `casp17/massivefold_external_pool_intake/h2338_t331/hashes/H2338_T331_all_pdbs_MassiveFold.tar.gz.sha256`
- listing_path: `casp17/massivefold_external_pool_intake/h2338_t331/extracted_models/tarball_listing.txt`
- verification_status: `verified_for_external_rerank_intake`
- tarball/size/hash/listing: `tarball_present`/`size_matches_declared`/`sha256_match`/`tarball_listing_present`

## Acquisition Commands

```bash
mkdir -p casp17/massivefold_external_pool_intake/h2338_t331/downloads casp17/massivefold_external_pool_intake/h2338_t331/hashes casp17/massivefold_external_pool_intake/h2338_t331/extracted_models
curl --fail --location --continue-at - --output casp17/massivefold_external_pool_intake/h2338_t331/downloads/H2338_T331_all_pdbs_MassiveFold.tar.gz 'ftp://files.plbs.fr:21211/CASP17-CAPRI/H2338_T331_all_pdbs_MassiveFold.tar.gz'
sha256sum casp17/massivefold_external_pool_intake/h2338_t331/downloads/H2338_T331_all_pdbs_MassiveFold.tar.gz > casp17/massivefold_external_pool_intake/h2338_t331/hashes/H2338_T331_all_pdbs_MassiveFold.tar.gz.sha256
tar -tzf casp17/massivefold_external_pool_intake/h2338_t331/downloads/H2338_T331_all_pdbs_MassiveFold.tar.gz > casp17/massivefold_external_pool_intake/h2338_t331/extracted_models/tarball_listing.txt
```

## Next Action

pool may be used only as an external rerank/accuracy-estimation input with provenance preserved

## Claim Boundary

MassiveFold acquisition verification board only. It checks local tarball, hash, and listing evidence for organizer-provided external model pools. These structures remain external rerank/accuracy-estimation pools, not internal predictions, not CASP submissions, and not competitive-proof evidence.
