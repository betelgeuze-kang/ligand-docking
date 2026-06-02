# CASP17 Official Archive First Baseline Score Ledger

- generated: `2026-06-02T00:11:04+09:00`
- status: `official_archive_first_baseline_score_ledger_ready_baseline_only`
- first baseline: `official_archive_baseline_001` `CASP16` `T1212` native `9B0L`
- model scores ready/blocked/total: `348/0/348`
- group scores ready/blocked/total: `73/1/74`
- top5 models/complete groups/improved groups: `348/67/52`
- mean model1/best5/delta GDT_TS proxy: `6.224` `17.013` `10.789`
- max gap: `78.380` group `163` `T1212TS163_1` -> `T1212TS163_4`
- proof eligible: `False` policy `do_not_import_as_internal_prediction`
- next action: use the baseline-only score ledger for historical replay calibration; keep strict-blind proof blocked

## Group Ledger

| group | model1 | model1 GDT | best top5 | best GDT | delta |
| --- | --- | --- | --- | --- | --- |
| `014` | `T1212TS014_1` | `4.292` | `T1212TS014_4` | `5.901` | `1.609` |
| `015` | `T1212TS015_1` | `1.395` | `T1212TS015_4` | `31.438` | `30.043` |
| `019` | `T1212TS019_1` | `1.556` | `T1212TS019_3` | `2.146` | `0.590` |
| `022` | `T1212TS022_1` | `0.536` | `T1212TS022_3` | `0.644` | `0.108` |
| `028` | `T1212TS028_1` | `1.609` | `T1212TS028_1` | `1.609` | `0.000` |
| `031` | `T1212TS031_1` | `3.326` | `T1212TS031_2` | `7.564` | `4.238` |
| `033` | `T1212TS033_1` | `43.616` | `T1212TS033_1` | `43.616` | `0.000` |
| `040` | `T1212TS040_1` | `1.395` | `T1212TS040_2` | `2.307` | `0.912` |
| `044` | `T1212TS044_1` | `3.004` | `T1212TS044_1` | `3.004` | `0.000` |
| `051` | `T1212TS051_1` | `3.755` | `T1212TS051_1` | `3.755` | `0.000` |
| `052` | `T1212TS052_1` | `0.590` | `T1212TS052_5` | `25.000` | `24.410` |
| `059` | `T1212TS059_1` | `2.092` | `T1212TS059_3` | `2.790` | `0.698` |
| `075` | `T1212TS075_1` | `1.502` | `T1212TS075_4` | `8.745` | `7.243` |
| `079` | `T1212TS079_1` | `2.468` | `T1212TS079_3` | `4.614` | `2.146` |
| `110` | `T1212TS110_1` | `1.073` | `T1212TS110_1` | `1.073` | `0.000` |
| `112` | `T1212TS112_1` | `0.966` | `T1212TS112_1` | `0.966` | `0.000` |
| `120` | `T1212TS120_1` | `0.858` | `T1212TS120_4` | `3.004` | `2.146` |
| `122` | `T1212TS122_1` | `2.307` | `T1212TS122_1` | `2.307` | `0.000` |
| `132` | `T1212TS132_1` | `0.966` | `T1212TS132_1` | `0.966` | `0.000` |
| `139` | `T1212TS139_1` | `16.202` | `T1212TS139_2` | `29.936` | `13.734` |
| `143` | `T1212TS143_1` | `1.556` | `T1212TS143_2` | `1.663` | `0.107` |
| `145` | `T1212TS145_1` | `5.311` | `T1212TS145_1` | `5.311` | `0.000` |
| `147` | `T1212TS147_1` | `1.717` | `T1212TS147_1` | `1.717` | `0.000` |
| `148` | `T1212TS148_1` | `0.000` | `T1212TS148_3` | `2.736` | `2.736` |
| `159` | `T1212TS159_1` | `0.054` | `T1212TS159_2` | `2.307` | `2.253` |
| `163` | `T1212TS163_1` | `0.268` | `T1212TS163_4` | `78.648` | `78.380` |
| `164` | `T1212TS164_1` | `72.639` | `T1212TS164_4` | `78.702` | `6.063` |
| `167` | `T1212TS167_1` | `9.067` | `T1212TS167_1` | `9.067` | `0.000` |
| `196` | `T1212TS196_1` | `0.000` | `T1212TS196_2` | `0.161` | `0.161` |
| `198` | `T1212TS198_1` | `3.219` | `T1212TS198_1` | `3.219` | `0.000` |

## Claim Boundary

Local CASP17 official-archive first baseline score ledger only. It scores external CASP archive model1/top5 rows against a local native PDB with deterministic CA proxy metrics for historical replay calibration. It is not an official CASP assessment, does not import official archive models as internal predictions, does not fill strict-blind operator values, does not push remotes, and does not submit to CASP.
