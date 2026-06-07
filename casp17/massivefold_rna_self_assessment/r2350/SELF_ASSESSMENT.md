# R2350 MassiveFold RNA Self-Assessment

- status: `ready_external_self_assessment_input`
- model1: `Model_20_af3_woPaired_af3_seed_612441_sample_0_pred_640.cif` `woPaired`
- model1/runner-up/gap: `83.34166/83.31874/0.02292`
- top5 score mean/spread: `83.235968/0.19336`
- diversity/nearest: `48.47025/25.783`
- R2345 guard: `-`

| rank | role | file | protocol | score | diversity | nearest | geometry | low-conf |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `1` | `model1` | `Model_20_af3_woPaired_af3_seed_612441_sample_0_pred_640.cif` | `woPaired` | `83.34166` | `0` | `44.474` | `0.516` | `0.02619` |
| `2` | `top5_decoy` | `Model_5_af3_woUnpaired_woTemplates_af3_seed_100687_sample_3_pred_398.cif` | `woUnpaired_woTemplates` | `83.31874` | `45.595` | `40.709` | `1.704` | `0.02703` |
| `3` | `top5_decoy` | `Model_1_af3_woUnpaired_woPaired_woTemplates_af3_seed_811587_sample_2_pred_367.cif` | `woUnpaired_woPaired_woTemplates` | `83.20776` | `44.474` | `25.783` | `0.781` | `0.02498` |
| `4` | `top5_decoy` | `Model_13_af3_woUnpaired_woPaired_af3_seed_94539_sample_0_pred_25.cif` | `woUnpaired_woPaired` | `83.16338` | `47.055` | `25.783` | `0.783` | `0.02402` |
| `5` | `top5_decoy` | `Model_2_af3_woUnpaired_af3_seed_160939_sample_4_pred_359.cif` | `woUnpaired` | `83.1483` | `56.757` | `52.717` | `1.605` | `0.02523` |

## Claim Boundary

CASP17 MassiveFold RNA self-assessment packet only. It converts organizer-provided external model1/top5 pointers into no-native confidence, diversity, geometry, and sequence-guard review features for model-selection calibration. It does not copy coordinates, submit models, use native structures, or create internal competitive-proof evidence.
