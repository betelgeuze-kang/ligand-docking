# CASP17 Official Archive First Baseline Model Pool

- generated: `2026-06-01T23:55:56+09:00`
- status: `official_archive_first_baseline_model_pool_ready`
- first baseline: `official_archive_baseline_001` `CASP16` `T1212` native `9B0L`
- models ready/blocked/expected: `357/0/357`
- groups/model1/top5-complete: `74/73/67`
- top5/extra models: `348/9`
- proof eligible: `False` policy `do_not_import_as_internal_prediction`
- manifests: `casp17/official_archive_first_baseline_model_pool/model1_manifest.csv` `casp17/official_archive_first_baseline_model_pool/top5_manifest.csv` `casp17/official_archive_first_baseline_model_pool/all_models_manifest.csv`
- next action: score baseline-only model1 and best-of-5 against the native PDB without importing as internal proof

## First Models

| rank | model | group | number | atoms | path |
| --- | --- | --- | --- | --- | --- |
| `1` | `T1212TS014_1` | `014` | `1` | `3815` | `casp17/official_archive_first_baseline_model_pool/extracted_models/T1212/all_models/T1212TS014_1.pdb` |
| `2` | `T1212TS014_2` | `014` | `2` | `3815` | `casp17/official_archive_first_baseline_model_pool/extracted_models/T1212/all_models/T1212TS014_2.pdb` |
| `3` | `T1212TS014_3` | `014` | `3` | `3815` | `casp17/official_archive_first_baseline_model_pool/extracted_models/T1212/all_models/T1212TS014_3.pdb` |
| `4` | `T1212TS014_4` | `014` | `4` | `3815` | `casp17/official_archive_first_baseline_model_pool/extracted_models/T1212/all_models/T1212TS014_4.pdb` |
| `5` | `T1212TS014_5` | `014` | `5` | `3815` | `casp17/official_archive_first_baseline_model_pool/extracted_models/T1212/all_models/T1212TS014_5.pdb` |
| `6` | `T1212TS014_6` | `014` | `6` | `3815` | `casp17/official_archive_first_baseline_model_pool/extracted_models/T1212/all_models/T1212TS014_6.pdb` |
| `7` | `T1212TS015_1` | `015` | `1` | `3815` | `casp17/official_archive_first_baseline_model_pool/extracted_models/T1212/all_models/T1212TS015_1.pdb` |
| `8` | `T1212TS015_2` | `015` | `2` | `3815` | `casp17/official_archive_first_baseline_model_pool/extracted_models/T1212/all_models/T1212TS015_2.pdb` |
| `9` | `T1212TS015_3` | `015` | `3` | `3815` | `casp17/official_archive_first_baseline_model_pool/extracted_models/T1212/all_models/T1212TS015_3.pdb` |
| `10` | `T1212TS015_4` | `015` | `4` | `3815` | `casp17/official_archive_first_baseline_model_pool/extracted_models/T1212/all_models/T1212TS015_4.pdb` |
| `11` | `T1212TS015_5` | `015` | `5` | `3815` | `casp17/official_archive_first_baseline_model_pool/extracted_models/T1212/all_models/T1212TS015_5.pdb` |
| `12` | `T1212TS015_6` | `015` | `6` | `3815` | `casp17/official_archive_first_baseline_model_pool/extracted_models/T1212/all_models/T1212TS015_6.pdb` |
| `13` | `T1212TS019_1` | `019` | `1` | `3815` | `casp17/official_archive_first_baseline_model_pool/extracted_models/T1212/all_models/T1212TS019_1.pdb` |
| `14` | `T1212TS019_2` | `019` | `2` | `3815` | `casp17/official_archive_first_baseline_model_pool/extracted_models/T1212/all_models/T1212TS019_2.pdb` |
| `15` | `T1212TS019_3` | `019` | `3` | `3815` | `casp17/official_archive_first_baseline_model_pool/extracted_models/T1212/all_models/T1212TS019_3.pdb` |
| `16` | `T1212TS019_4` | `019` | `4` | `3815` | `casp17/official_archive_first_baseline_model_pool/extracted_models/T1212/all_models/T1212TS019_4.pdb` |
| `17` | `T1212TS019_5` | `019` | `5` | `3815` | `casp17/official_archive_first_baseline_model_pool/extracted_models/T1212/all_models/T1212TS019_5.pdb` |
| `18` | `T1212TS022_1` | `022` | `1` | `3815` | `casp17/official_archive_first_baseline_model_pool/extracted_models/T1212/all_models/T1212TS022_1.pdb` |
| `19` | `T1212TS022_2` | `022` | `2` | `3814` | `casp17/official_archive_first_baseline_model_pool/extracted_models/T1212/all_models/T1212TS022_2.pdb` |
| `20` | `T1212TS022_3` | `022` | `3` | `3815` | `casp17/official_archive_first_baseline_model_pool/extracted_models/T1212/all_models/T1212TS022_3.pdb` |

## Claim Boundary

Local CASP17 official-archive first baseline model-pool extraction only. It extracts external CASP archive submissions into a baseline replay folder and builds model1/top5 manifests. It does not import official archive models as internal predictions, fill strict-blind operator values, compute native accuracy, push remotes, or submit to CASP.
