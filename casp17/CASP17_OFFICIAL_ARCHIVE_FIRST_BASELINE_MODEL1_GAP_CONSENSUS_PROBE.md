# CASP17 Official Archive First Baseline Model1 Gap Consensus Probe

- generated: `2026-06-02T00:55:52+09:00`
- status: `official_archive_first_baseline_model1_gap_consensus_probe_ready_baseline_only`
- first baseline: `official_archive_baseline_001` `CASP16` `T1212` native `9B0L`
- consensus ready/blocked/selected: `14/0/14`
- signals supports-best/model1/ambiguous: `7/6/1` rate `0.500`
- consensus top matches best/model1: `4/3`
- catastrophic/large cases: `5/9`
- first signal: group `163` `supports_model1` ranks model1/best `4` `5` top `T1212TS163_5` margin `-4.201`
- consensus csv: `casp17/official_archive_first_baseline_model1_gap_consensus_probe/consensus_probe.csv`
- pairwise matrix csv: `casp17/official_archive_first_baseline_model1_gap_consensus_probe/pairwise_consensus_matrix.csv`
- proof eligible: `False` policy `do_not_import_as_internal_prediction`
- next action: combine consensus-rank, diversity, and confidence features into a no-native model1 selector; repeat only on strict-blind eligible internal predictions before competitive claims

## Consensus Worklist

| rank | group | band | delta | signal | model1 rank | best rank | top | review |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `1` | `163` | `catastrophic_model1_selection_gap` | `78.380` | `supports_model1` | `4` | `5` | `T1212TS163_5` | `casp17/official_archive_first_baseline_model1_gap_consensus_probe/01_t1212_group_163/CONSENSUS_PROBE.md` |
| `2` | `304` | `catastrophic_model1_selection_gap` | `71.138` | `supports_best_top5` | `5` | `3` | `T1212TS304_2` | `casp17/official_archive_first_baseline_model1_gap_consensus_probe/02_t1212_group_304/CONSENSUS_PROBE.md` |
| `3` | `286` | `catastrophic_model1_selection_gap` | `61.642` | `supports_model1` | `3` | `4` | `T1212TS286_4` | `casp17/official_archive_first_baseline_model1_gap_consensus_probe/03_t1212_group_286/CONSENSUS_PROBE.md` |
| `4` | `419` | `catastrophic_model1_selection_gap` | `61.642` | `supports_model1` | `3` | `4` | `T1212TS419_4` | `casp17/official_archive_first_baseline_model1_gap_consensus_probe/04_t1212_group_419/CONSENSUS_PROBE.md` |
| `5` | `262` | `catastrophic_model1_selection_gap` | `53.863` | `supports_best_top5` | `3` | `1` | `T1212TS262_5` | `casp17/official_archive_first_baseline_model1_gap_consensus_probe/05_t1212_group_262/CONSENSUS_PROBE.md` |
| `6` | `345` | `large_selection_gap` | `49.946` | `supports_model1` | `1` | `2` | `T1212TS345_1` | `casp17/official_archive_first_baseline_model1_gap_consensus_probe/06_t1212_group_345/CONSENSUS_PROBE.md` |
| `7` | `369` | `large_selection_gap` | `40.826` | `supports_best_top5` | `4` | `1` | `T1212TS369_5` | `casp17/official_archive_first_baseline_model1_gap_consensus_probe/07_t1212_group_369/CONSENSUS_PROBE.md` |
| `8` | `269` | `large_selection_gap` | `39.485` | `supports_best_top5` | `4` | `1` | `T1212TS269_4` | `casp17/official_archive_first_baseline_model1_gap_consensus_probe/08_t1212_group_269/CONSENSUS_PROBE.md` |
| `9` | `221` | `large_selection_gap` | `38.895` | `supports_best_top5` | `3` | `1` | `T1212TS221_4` | `casp17/official_archive_first_baseline_model1_gap_consensus_probe/09_t1212_group_221/CONSENSUS_PROBE.md` |
| `10` | `015` | `large_selection_gap` | `30.043` | `supports_model1` | `1` | `3` | `T1212TS015_1` | `casp17/official_archive_first_baseline_model1_gap_consensus_probe/10_t1212_group_015/CONSENSUS_PROBE.md` |
| `11` | `312` | `large_selection_gap` | `27.092` | `supports_model1` | `1` | `2` | `T1212TS312_1` | `casp17/official_archive_first_baseline_model1_gap_consensus_probe/11_t1212_group_312/CONSENSUS_PROBE.md` |
| `12` | `052` | `large_selection_gap` | `24.410` | `ambiguous` | `4` | `5` | `T1212TS052_2` | `casp17/official_archive_first_baseline_model1_gap_consensus_probe/12_t1212_group_052/CONSENSUS_PROBE.md` |
| `13` | `481` | `large_selection_gap` | `22.961` | `supports_best_top5` | `5` | `3` | `T1212TS481_3` | `casp17/official_archive_first_baseline_model1_gap_consensus_probe/13_t1212_group_481/CONSENSUS_PROBE.md` |
| `14` | `261` | `large_selection_gap` | `22.854` | `supports_best_top5` | `4` | `3` | `T1212TS261_2` | `casp17/official_archive_first_baseline_model1_gap_consensus_probe/14_t1212_group_261/CONSENSUS_PROBE.md` |

## Claim Boundary

Local CASP17 official-archive first baseline model1 gap consensus probe only. It uses native-free top5 pairwise CA RMSD clustering on baseline-only official archive models to study model-selection failure modes. It is not an official CASP assessment, not strict-blind competitive proof, does not import official archive models as internal predictions, does not push remotes, and does not submit to CASP.
