# H2339 MassiveFold Acquisition Verification

- model_set_id: `H2339_T332`
- tarball_url: `ftp://files.plbs.fr:21211/CASP17-CAPRI/H2339_T332_all_pdbs_MassiveFold.tar.gz`
- download_path: `casp17/massivefold_external_pool_intake/h2339_t332/downloads/H2339_T332_all_pdbs_MassiveFold.tar.gz`
- sha256_path: `casp17/massivefold_external_pool_intake/h2339_t332/hashes/H2339_T332_all_pdbs_MassiveFold.tar.gz.sha256`
- listing_path: `casp17/massivefold_external_pool_intake/h2339_t332/extracted_models/tarball_listing.txt`
- verification_status: `open_tarball_download_required`
- tarball/size/hash/listing: `awaiting_tarball_download`/`awaiting_tarball_size_check`/`awaiting_tarball`/`awaiting_tarball_listing`

## Acquisition Commands

```bash
mkdir -p casp17/massivefold_external_pool_intake/h2339_t332/downloads casp17/massivefold_external_pool_intake/h2339_t332/hashes casp17/massivefold_external_pool_intake/h2339_t332/extracted_models
curl --fail --location --continue-at - --output casp17/massivefold_external_pool_intake/h2339_t332/downloads/H2339_T332_all_pdbs_MassiveFold.tar.gz 'ftp://files.plbs.fr:21211/CASP17-CAPRI/H2339_T332_all_pdbs_MassiveFold.tar.gz'
sha256sum casp17/massivefold_external_pool_intake/h2339_t332/downloads/H2339_T332_all_pdbs_MassiveFold.tar.gz > casp17/massivefold_external_pool_intake/h2339_t332/hashes/H2339_T332_all_pdbs_MassiveFold.tar.gz.sha256
tar -tzf casp17/massivefold_external_pool_intake/h2339_t332/downloads/H2339_T332_all_pdbs_MassiveFold.tar.gz > casp17/massivefold_external_pool_intake/h2339_t332/extracted_models/tarball_listing.txt
```

## Next Action

download the tarball into the external-pool downloads folder, then record sha256 and tarball listing

## Claim Boundary

MassiveFold acquisition verification board only. It checks local tarball, hash, and listing evidence for organizer-provided external model pools. These structures remain external rerank/accuracy-estimation pools, not internal predictions, not CASP submissions, and not competitive-proof evidence.
