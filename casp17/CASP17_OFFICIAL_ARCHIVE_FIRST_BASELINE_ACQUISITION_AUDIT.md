# CASP17 Official Archive First Baseline Acquisition Audit

- generated: `2026-06-01T23:45:56+09:00`
- status: `official_archive_first_baseline_acquired`
- first baseline: `official_archive_baseline_001` `CASP16` `T1212` native `9B0L`
- ready/blocked/total artifacts: `2/0/2`
- tarball: `True` `25069184` bytes members/models `358/357` sha `fe1f11355d1b2100`
- native PDB: `True` `618516` bytes atoms `7051` sha `48e6c1b21f7f6fc0`
- proof eligible: `False` policy `do_not_import_as_internal_prediction`
- next action: extract and score the baseline-only model1/best-of-5 set without importing it as internal proof

## Artifact Rows

| kind | status | path | validation | next action |
| --- | --- | --- | --- | --- |
| `prediction_tarball` | `present` | `casp17/historical_seed_official_archive_baseline_lane/001_casp16_t1212_fanzor2_ternary_structure_protein_subunit_of_m1212/downloads/T1212.tar.gz` | `tar_readable=True;models=357` | ready for baseline-only audit |
| `native_pdb` | `present` | `casp17/historical_seed_official_archive_baseline_lane/001_casp16_t1212_fanzor2_ternary_structure_protein_subunit_of_m1212/native/9B0L.pdb` | `atom_records=7051` | ready for baseline-only audit |

## Claim Boundary

Local CASP17 official-archive first baseline acquisition audit only. It verifies that the first external official CASP archive tarball and native PDB are present inside the baseline lane. It does not import official archive models as internal predictions, fill strict-blind operator values, compute CASP metrics, push remotes, or submit to CASP.
