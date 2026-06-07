# CASP17 Official Archive First Baseline Model1 Gap Feature Probe

- generated: `2026-06-02T00:46:53+09:00`
- status: `official_archive_first_baseline_model1_gap_feature_probe_ready_baseline_only`
- first baseline: `official_archive_baseline_001` `CASP16` `T1212` native `9B0L`
- features ready/blocked/selected: `14/0/14`
- signals supports-best/model1/ambiguous: `0/0/14` rate `0.000`
- catastrophic/large cases: `5/9`
- first signal: group `163` `ambiguous` model1/best risk `2.467` `2.584` delta `-0.117`
- feature csv: `casp17/official_archive_first_baseline_model1_gap_feature_probe/feature_probe.csv`
- pair matrix csv: `casp17/official_archive_first_baseline_model1_gap_feature_probe/pair_feature_matrix.csv`
- proof eligible: `False` policy `do_not_import_as_internal_prediction`
- next action: use native-free feature signals to tune model1 selection calibration, then repeat on strict-blind eligible internal predictions only

## Feature Worklist

| rank | group | band | delta | signal | model1 risk | best risk | review |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `1` | `163` | `catastrophic_model1_selection_gap` | `78.380` | `ambiguous` | `2.467` | `2.584` | `casp17/official_archive_first_baseline_model1_gap_feature_probe/01_t1212_group_163/FEATURE_PROBE.md` |
| `2` | `304` | `catastrophic_model1_selection_gap` | `71.138` | `ambiguous` | `2.728` | `2.716` | `casp17/official_archive_first_baseline_model1_gap_feature_probe/02_t1212_group_304/FEATURE_PROBE.md` |
| `3` | `286` | `catastrophic_model1_selection_gap` | `61.642` | `ambiguous` | `2.842` | `2.952` | `casp17/official_archive_first_baseline_model1_gap_feature_probe/03_t1212_group_286/FEATURE_PROBE.md` |
| `4` | `419` | `catastrophic_model1_selection_gap` | `61.642` | `ambiguous` | `2.842` | `2.952` | `casp17/official_archive_first_baseline_model1_gap_feature_probe/04_t1212_group_419/FEATURE_PROBE.md` |
| `5` | `262` | `catastrophic_model1_selection_gap` | `53.863` | `ambiguous` | `2.583` | `2.785` | `casp17/official_archive_first_baseline_model1_gap_feature_probe/05_t1212_group_262/FEATURE_PROBE.md` |
| `6` | `345` | `large_selection_gap` | `49.946` | `ambiguous` | `2.643` | `2.811` | `casp17/official_archive_first_baseline_model1_gap_feature_probe/06_t1212_group_345/FEATURE_PROBE.md` |
| `7` | `369` | `large_selection_gap` | `40.826` | `ambiguous` | `2.761` | `2.930` | `casp17/official_archive_first_baseline_model1_gap_feature_probe/07_t1212_group_369/FEATURE_PROBE.md` |
| `8` | `269` | `large_selection_gap` | `39.485` | `ambiguous` | `2.420` | `2.419` | `casp17/official_archive_first_baseline_model1_gap_feature_probe/08_t1212_group_269/FEATURE_PROBE.md` |
| `9` | `221` | `large_selection_gap` | `38.895` | `ambiguous` | `2.677` | `2.382` | `casp17/official_archive_first_baseline_model1_gap_feature_probe/09_t1212_group_221/FEATURE_PROBE.md` |
| `10` | `015` | `large_selection_gap` | `30.043` | `ambiguous` | `2.667` | `2.593` | `casp17/official_archive_first_baseline_model1_gap_feature_probe/10_t1212_group_015/FEATURE_PROBE.md` |
| `11` | `312` | `large_selection_gap` | `27.092` | `ambiguous` | `2.796` | `2.753` | `casp17/official_archive_first_baseline_model1_gap_feature_probe/11_t1212_group_312/FEATURE_PROBE.md` |
| `12` | `052` | `large_selection_gap` | `24.410` | `ambiguous` | `2.457` | `2.481` | `casp17/official_archive_first_baseline_model1_gap_feature_probe/12_t1212_group_052/FEATURE_PROBE.md` |
| `13` | `481` | `large_selection_gap` | `22.961` | `ambiguous` | `2.528` | `2.486` | `casp17/official_archive_first_baseline_model1_gap_feature_probe/13_t1212_group_481/FEATURE_PROBE.md` |
| `14` | `261` | `large_selection_gap` | `22.854` | `ambiguous` | `2.541` | `2.495` | `casp17/official_archive_first_baseline_model1_gap_feature_probe/14_t1212_group_261/FEATURE_PROBE.md` |

## Claim Boundary

Local CASP17 official-archive first baseline model1 gap feature probe only. It uses native-free geometry features from copied baseline-only official archive model1/best-of-5 PDB files to study model-selection failure modes. It is not an official CASP assessment, not strict-blind competitive proof, does not import official archive models as internal predictions, does not push remotes, and does not submit to CASP.
