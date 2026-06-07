# R2353 MassiveFold RNA Self-Assessment

- status: `ready_external_self_assessment_input`
- model1: `Model_7_af3_woPaired_af3_seed_634615_sample_2_pred_387.cif` `woPaired`
- model1/runner-up/gap: `80.52762/80.43482/0.0928`
- top5 score mean/spread: `80.324588/0.41312`
- diversity/nearest: `53.534/23.011`
- R2345 guard: `-`

| rank | role | file | protocol | score | diversity | nearest | geometry | low-conf |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `1` | `model1` | `Model_7_af3_woPaired_af3_seed_634615_sample_2_pred_387.cif` | `woPaired` | `80.52762` | `0` | `45.139` | `0.682` | `0.03937` |
| `2` | `top5_decoy` | `Model_1_af3_woUnpaired_woPaired_af3_seed_3136_sample_2_pred_617.cif` | `woUnpaired_woPaired` | `80.43482` | `55.53` | `23.011` | `1.912` | `0.04175` |
| `3` | `top5_decoy` | `Model_5_af3_woUnpaired_woPaired_woTemplates_af3_seed_813694_sample_1_pred_871.cif` | `woUnpaired_woPaired_woTemplates` | `80.4287` | `57.936` | `23.011` | `1.085` | `0.04163` |
| `4` | `top5_decoy` | `Model_35_af3_woUnpaired_woTemplates_af3_seed_639646_sample_3_pred_853.cif` | `woUnpaired_woTemplates` | `80.1173` | `55.531` | `38.731` | `3.41` | `0.04459` |
| `5` | `top5_decoy` | `Model_26_af3_woUnpaired_af3_seed_166439_sample_4_pred_334.cif` | `woUnpaired` | `80.1145` | `45.139` | `38.731` | `1.88` | `0.03997` |

## Claim Boundary

CASP17 MassiveFold RNA self-assessment packet only. It converts organizer-provided external model1/top5 pointers into no-native confidence, diversity, geometry, and sequence-guard review features for model-selection calibration. It does not copy coordinates, submit models, use native structures, or create internal competitive-proof evidence.
