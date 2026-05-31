# CASP17 MassiveFold Representative Rerank Packet

- generated: `2026-05-31T23:45:33+09:00`
- status: `massivefold_representative_rerank_ready_review_only`
- target: `T2313`
- candidates/model1/top5: `130/1/5`
- top5_protocol_count: `5`
- confidence_score min/max: `10.85552/83.5072`
- mean_b_iso min/max: `32.21/78.548`
- model1: `Model_5_afm_woTemplates_model_4_multimer_v3_pred_28.pdb` protocol `afm_woTemplates_v3` score `83.5072` viewer `casp17/massivefold_representative_viewers/t2313/selection_085_afm_woTemplates_v3_model_5/viewer.html`
- top5_manifest: `casp17/massivefold_representative_rerank/t2313/top5_manifest.csv`
- next action: use the review-only model1/top5 picks as accuracy-estimation and conformation-triage inputs; do not submit or count them as internal competitive proof without CASP rule and provenance clearance

## Model1 And Top5 Candidates

| top5_rank | quality_rank | selection | model | protocol | confidence | mean_b_iso | high/low | model1_rmsd | viewer | folder |
| --- | --- | --- | --- | --- | ---: | ---: | --- | ---: | --- | --- |
| `1` | `1` | `85` | `Model_5_afm_woTemplates_model_4_multimer_v3_pred_28.pdb` | `afm_woTemplates_v3` | 83.5072 | 78.548 | `0.7766/0.13562` | 0.0 | `casp17/massivefold_representative_viewers/t2313/selection_085_afm_woTemplates_v3_model_5/viewer.html` | `casp17/massivefold_representative_rerank/t2313/top5/rank_01_selection_085_afm_woTemplates_v3` |
| `2` | `2` | `125` | `Model_10_afm_dropout_noSM_woTemplates_model_5_multimer_v3_pred_11.pdb` | `afm_dropout_noSM_woTemplates_v3` | 80.93886 | 76.493 | `0.74663/0.14552` | 52.165 | `casp17/massivefold_representative_viewers/t2313/selection_125_afm_dropout_noSM_woTemplates_v3_model_10/viewer.html` | `casp17/massivefold_representative_rerank/t2313/top5/rank_02_selection_125_afm_dropout_noSM_woTemplates_v3` |
| `3` | `5` | `50` | `Model_63_af3_basic_af3_seed_704032_sample_0_pred_520.cif` | `basic` | 78.90796 | 74.067 | `0.69408/0.09953` | 59.443 | `casp17/massivefold_representative_viewers/t2313/selection_050_basic_model_63/viewer.html` | `casp17/massivefold_representative_rerank/t2313/top5/rank_03_selection_050_basic` |
| `4` | `9` | `51` | `Model_69_af3_woPaired_af3_seed_880568_sample_2_pred_47.cif` | `woPaired` | 78.39748 | 73.748 | `0.67594/0.10057` | 51.518 | `casp17/massivefold_representative_viewers/t2313/selection_051_woPaired_model_69/viewer.html` | `casp17/massivefold_representative_rerank/t2313/top5/rank_04_selection_051_woPaired` |
| `5` | `12` | `91` | `Model_4_afm_dropout_full_model_4_multimer_v3_pred_44.pdb` | `afm_dropout_full_v3` | 78.2235 | 74.889 | `0.70543/0.17688` | 52.171 | `casp17/massivefold_representative_viewers/t2313/selection_091_afm_dropout_full_v3_model_4/viewer.html` | `casp17/massivefold_representative_rerank/t2313/top5/rank_05_selection_091_afm_dropout_full_v3` |

## Claim Boundary

CASP17 MassiveFold representative rerank packet only. It ranks organizer-provided external representatives using confidence, geometry, and diversity proxies for review-only model selection. It does not use a native structure, does not prove CASP accuracy, does not create internal predictions, and does not submit models.
