# CASP17 MassiveFold Model1 Risk Queue

- generated: `2026-06-01T22:25:39+09:00`
- status: `massivefold_model1_risk_queue_ready_external_only`
- targets ready/blocked/total: `15/0/15`
- low-margin/critical targets: `13/4`
- RNA/protein-complex targets: `6/9`
- first priority: `R2350` `rna_hybrid` `0.02292` `critical_model1_margin`
- next action: work low-margin model1 targets first, especially protein/immune complexes, and use the queue to drive external rerank and self-assessment calibration experiments

## Queue

| rank | group | target | tier | gap | threshold | model1 | spread | diversity | action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `1` | `rna_hybrid` | `R2350` | `critical_model1_margin` | `0.02292` | `1` | `Model_20_af3_woPaired_af3_seed_612441_sample_0_pred_640.cif` | `0.19336` | `48.47025` | `casp17/massivefold_model1_risk_queue/01_rna_hybrid_r2350/RISK_ACTION.md` |
| `2` | `rna_hybrid` | `R2352` | `critical_model1_margin` | `0.07092` | `1` | `Model_15_af3_woUnpaired_af3_seed_20656_sample_1_pred_611.cif` | `0.14128` | `29.4805` | `casp17/massivefold_model1_risk_queue/02_rna_hybrid_r2352/RISK_ACTION.md` |
| `3` | `protein_complex` | `H2312` | `critical_model1_margin` | `0.0813` | `2` | `Model_7550_afm_basic_model_5_multimer_v1_pred_11.pdb` | `1.18232` | `18.18725` | `casp17/massivefold_model1_risk_queue/03_protein_complex_h2312/RISK_ACTION.md` |
| `4` | `rna_hybrid` | `R2353` | `critical_model1_margin` | `0.0928` | `1` | `Model_7_af3_woPaired_af3_seed_634615_sample_2_pred_387.cif` | `0.41312` | `53.534` | `casp17/massivefold_model1_risk_queue/04_rna_hybrid_r2353/RISK_ACTION.md` |
| `5` | `rna_hybrid` | `R2341` | `high_model1_margin` | `0.10906` | `1` | `Model_2_af3_basic_af3_seed_672131_sample_4_pred_869.cif` | `1.07352` | `53.2865` | `casp17/massivefold_model1_risk_queue/05_rna_hybrid_r2341/RISK_ACTION.md` |
| `6` | `rna_hybrid` | `R2351` | `high_model1_margin` | `0.131` | `1` | `Model_18_af3_woTemplates_af3_seed_103360_sample_3_pred_608.cif` | `0.25478` | `57.00825` | `casp17/massivefold_model1_risk_queue/06_rna_hybrid_r2351/RISK_ACTION.md` |
| `7` | `protein_complex` | `H2324` | `high_model1_margin` | `0.17602` | `2` | `Model_4760_afm_basic_model_5_multimer_v1_pred_26.pdb` | `0.57566` | `57.6945` | `casp17/massivefold_model1_risk_queue/07_protein_complex_h2324/RISK_ACTION.md` |
| `8` | `protein_complex` | `H1311` | `high_model1_margin` | `0.3313` | `2` | `Model_5_afm_basic_model_4_multimer_v3_pred_5.pdb` | `2.55002` | `31.10125` | `casp17/massivefold_model1_risk_queue/08_protein_complex_h1311/RISK_ACTION.md` |
| `9` | `protein_complex` | `H2338` | `high_model1_margin` | `0.45224` | `2` | `Model_2_afm_dropout_full_model_4_multimer_v3_pred_64.pdb` | `1.77912` | `47.523` | `casp17/massivefold_model1_risk_queue/09_protein_complex_h2338/RISK_ACTION.md` |
| `10` | `protein_complex` | `H2319` | `high_model1_margin` | `0.56512` | `2` | `Model_1_afm_basic_model_4_multimer_v3_pred_25.pdb` | `4.04092` | `43.949` | `casp17/massivefold_model1_risk_queue/10_protein_complex_h2319/RISK_ACTION.md` |
| `11` | `protein_complex` | `H2321` | `high_model1_margin` | `0.66878` | `2` | `Model_3_afm_dropout_full_model_2_multimer_v3_pred_48.pdb` | `3.56518` | `39.6285` | `casp17/massivefold_model1_risk_queue/11_protein_complex_h2321/RISK_ACTION.md` |
| `12` | `protein_complex` | `H2339` | `high_model1_margin` | `0.74694` | `2` | `Model_135_afm_basic_model_5_multimer_v1_pred_62.pdb` | `2.39072` | `52.00175` | `casp17/massivefold_model1_risk_queue/12_protein_complex_h2339/RISK_ACTION.md` |
| `13` | `protein_complex` | `H2335` | `high_model1_margin` | `1.11502` | `2` | `Model_7830_afm_basic_model_5_multimer_v1_pred_39.pdb` | `1.6303` | `57.9835` | `casp17/massivefold_model1_risk_queue/13_protein_complex_h2335/RISK_ACTION.md` |
| `14` | `rna_hybrid` | `R2345` | `watch_model1_margin` | `1.64062` | `1` | `Model_4_af3_woUnpaired_af3_seed_418984_sample_3_pred_713.cif` | `4.37956` | `32.49625` | `casp17/massivefold_model1_risk_queue/14_rna_hybrid_r2345/RISK_ACTION.md` |
| `15` | `protein_complex` | `T2313` | `watch_model1_margin` | `2.56834` | `2` | `Model_5_afm_woTemplates_model_4_multimer_v3_pred_28.pdb` | `5.2837` | `53.82425` | `casp17/massivefold_model1_risk_queue/15_protein_complex_t2313/RISK_ACTION.md` |

## Claim Boundary

CASP17 MassiveFold model1 risk queue only. It ranks organizer-provided external RNA, protein, immune, and complex model1/top5 self-assessment rows for no-native reranking and accuracy-estimation follow-up. It does not copy coordinates, submit models, use native structures, or create internal competitive-proof evidence.
