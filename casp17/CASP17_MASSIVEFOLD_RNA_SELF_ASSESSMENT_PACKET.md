# CASP17 MassiveFold RNA Self-Assessment Packet

- generated: `2026-06-01T22:00:38+09:00`
- status: `massivefold_rna_self_assessment_ready_external_only`
- targets ready/blocked/total: `6/0/6`
- model1/top5/candidates: `6/30/30`
- low-margin targets: `5` below `1.0`
- R2345 guard: `ignore_0930_pacific_invalid_dna_t_request_use_1130_replacement_only`
- next action: use the external-only self-assessment features to stress-test model1 selection and confidence calibration while keeping native-free and no-submission boundaries

## Targets

| target | status | model1 | score gap | top5 mean/spread | diversity/nearest | blockers |
| --- | --- | --- | --- | --- | --- | --- |
| `R2341` | `ready_external_self_assessment_input` | `Model_2_af3_basic_af3_seed_672131_sample_4_pred_869.cif` | `0.10906` | `52.548/1.07352` | `53.2865/24.18` | `-` |
| `R2345` | `ready_external_self_assessment_input` | `Model_4_af3_woUnpaired_af3_seed_418984_sample_3_pred_713.cif` | `1.64062` | `55.303924/4.37956` | `32.49625/20.191` | `-` |
| `R2350` | `ready_external_self_assessment_input` | `Model_20_af3_woPaired_af3_seed_612441_sample_0_pred_640.cif` | `0.02292` | `83.235968/0.19336` | `48.47025/25.783` | `-` |
| `R2351` | `ready_external_self_assessment_input` | `Model_18_af3_woTemplates_af3_seed_103360_sample_3_pred_608.cif` | `0.131` | `83.709572/0.25478` | `57.00825/41.318` | `-` |
| `R2352` | `ready_external_self_assessment_input` | `Model_15_af3_woUnpaired_af3_seed_20656_sample_1_pred_611.cif` | `0.07092` | `82.610732/0.14128` | `29.4805/11.101` | `-` |
| `R2353` | `ready_external_self_assessment_input` | `Model_7_af3_woPaired_af3_seed_634615_sample_2_pred_387.cif` | `0.0928` | `80.324588/0.41312` | `53.534/23.011` | `-` |

## Claim Boundary

CASP17 MassiveFold RNA self-assessment packet only. It converts organizer-provided external model1/top5 pointers into no-native confidence, diversity, geometry, and sequence-guard review features for model-selection calibration. It does not copy coordinates, submit models, use native structures, or create internal competitive-proof evidence.
