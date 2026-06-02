# CASP17 MassiveFold Model-Selection Ledger

- generated: `2026-06-01T23:26:37+09:00`
- status: `massivefold_model_selection_ledger_ready_external_only`
- ledgers ready/blocked/total: `15/0/15`
- selected conditional/watch: `2/1`
- manual-review/review-only: `1/11`
- freeze-ready selected: `3`
- RNA/protein-complex: `6/9`
- first ledger: `R2350` `rna_hybrid` `external_model1_selected_conditional`
- first manual review: `R2352`
- ledger_rule_id: `no_native_massivefold_model_selection_ledger_v1`
- next action: use this external-only ledger for accuracy-estimation review, then resume strict-blind source-gate closure

## Ledger Rows

| rank | target | group | decision | selected model | alternate | confidence gap | probe margin | packet |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `1` | `R2350` | `rna_hybrid` | `external_model1_selected_conditional` | `Model_20_af3_woPaired_af3_seed_612441_sample_0_pred_640.cif` | `-` | `0.02292` | `0.64247` | `casp17/massivefold_model_selection_ledger/01_rna_hybrid_r2350/MODEL_SELECTION_LEDGER.md` |
| `2` | `R2353` | `rna_hybrid` | `external_model1_selected_conditional` | `Model_7_af3_woPaired_af3_seed_634615_sample_2_pred_387.cif` | `-` | `0.0928` | `0.78355` | `casp17/massivefold_model_selection_ledger/02_rna_hybrid_r2353/MODEL_SELECTION_LEDGER.md` |
| `3` | `H2312` | `protein_complex` | `external_model1_selected_watch` | `Model_7550_afm_basic_model_5_multimer_v1_pred_11.pdb` | `-` | `0.0813` | `0.10755` | `casp17/massivefold_model_selection_ledger/03_protein_complex_h2312/MODEL_SELECTION_LEDGER.md` |
| `4` | `R2352` | `rna_hybrid` | `external_model1_blocked_manual_review` | `-` | `Model_7_af3_woPaired_woTemplates_af3_seed_26386_sample_2_pred_237.cif` | `0.07092` | `-0.23587` | `casp17/massivefold_model_selection_ledger/04_rna_hybrid_r2352/MODEL_SELECTION_LEDGER.md` |
| `5` | `H1311` | `protein_complex` | `external_model1_review_only_unfrozen` | `Model_5_afm_basic_model_4_multimer_v3_pred_5.pdb` | `-` | `0.3313` | `-` | `casp17/massivefold_model_selection_ledger/05_protein_complex_h1311/MODEL_SELECTION_LEDGER.md` |
| `6` | `H2319` | `protein_complex` | `external_model1_review_only_unfrozen` | `Model_1_afm_basic_model_4_multimer_v3_pred_25.pdb` | `-` | `0.56512` | `-` | `casp17/massivefold_model_selection_ledger/06_protein_complex_h2319/MODEL_SELECTION_LEDGER.md` |
| `7` | `H2321` | `protein_complex` | `external_model1_review_only_unfrozen` | `Model_3_afm_dropout_full_model_2_multimer_v3_pred_48.pdb` | `-` | `0.66878` | `-` | `casp17/massivefold_model_selection_ledger/07_protein_complex_h2321/MODEL_SELECTION_LEDGER.md` |
| `8` | `H2324` | `protein_complex` | `external_model1_review_only_unfrozen` | `Model_4760_afm_basic_model_5_multimer_v1_pred_26.pdb` | `-` | `0.17602` | `-` | `casp17/massivefold_model_selection_ledger/08_protein_complex_h2324/MODEL_SELECTION_LEDGER.md` |
| `9` | `H2335` | `protein_complex` | `external_model1_review_only_unfrozen` | `Model_7830_afm_basic_model_5_multimer_v1_pred_39.pdb` | `-` | `1.11502` | `-` | `casp17/massivefold_model_selection_ledger/09_protein_complex_h2335/MODEL_SELECTION_LEDGER.md` |
| `10` | `H2338` | `protein_complex` | `external_model1_review_only_unfrozen` | `Model_2_afm_dropout_full_model_4_multimer_v3_pred_64.pdb` | `-` | `0.45224` | `-` | `casp17/massivefold_model_selection_ledger/10_protein_complex_h2338/MODEL_SELECTION_LEDGER.md` |
| `11` | `H2339` | `protein_complex` | `external_model1_review_only_unfrozen` | `Model_135_afm_basic_model_5_multimer_v1_pred_62.pdb` | `-` | `0.74694` | `-` | `casp17/massivefold_model_selection_ledger/11_protein_complex_h2339/MODEL_SELECTION_LEDGER.md` |
| `12` | `T2313` | `protein_complex` | `external_model1_review_only_unfrozen` | `Model_5_afm_woTemplates_model_4_multimer_v3_pred_28.pdb` | `-` | `2.56834` | `-` | `casp17/massivefold_model_selection_ledger/12_protein_complex_t2313/MODEL_SELECTION_LEDGER.md` |
| `13` | `R2341` | `rna_hybrid` | `external_model1_review_only_unfrozen` | `Model_2_af3_basic_af3_seed_672131_sample_4_pred_869.cif` | `-` | `0.10906` | `-` | `casp17/massivefold_model_selection_ledger/13_rna_hybrid_r2341/MODEL_SELECTION_LEDGER.md` |
| `14` | `R2345` | `rna_hybrid` | `external_model1_review_only_unfrozen` | `Model_4_af3_woUnpaired_af3_seed_418984_sample_3_pred_713.cif` | `-` | `1.64062` | `-` | `casp17/massivefold_model_selection_ledger/14_rna_hybrid_r2345/MODEL_SELECTION_LEDGER.md` |
| `15` | `R2351` | `rna_hybrid` | `external_model1_review_only_unfrozen` | `Model_18_af3_woTemplates_af3_seed_103360_sample_3_pred_608.cif` | `-` | `0.131` | `-` | `casp17/massivefold_model_selection_ledger/15_rna_hybrid_r2351/MODEL_SELECTION_LEDGER.md` |

## Claim Boundary

CASP17 MassiveFold model-selection ledger only. It records external no-native model1/top5 selection state for accuracy-estimation workflow. It is not native accuracy, internal prediction proof, or CASP submission evidence.
