# CASP17 MassiveFold Representative Rerank Packet

- generated: `2026-05-31T23:05:44+09:00`
- status: `massivefold_representative_rerank_ready_review_only`
- target: `H2324`
- candidates/model1/top5: `130/1/5`
- top5_protocol_count: `5`
- confidence_score min/max: `29.64678/99.93822`
- mean_b_iso min/max: `42.214/91.303`
- model1: `Model_4760_afm_basic_model_5_multimer_v1_pred_26.pdb` protocol `afm_basic_v1` score `99.93822` viewer `casp17/massivefold_representative_viewers/h2324/selection_115_afm_basic_v1_model_4760/viewer.html`
- top5_manifest: `casp17/massivefold_representative_rerank/h2324/top5_manifest.csv`
- next action: use the review-only model1/top5 picks as accuracy-estimation and conformation-triage inputs; do not submit or count them as internal competitive proof without CASP rule and provenance clearance

## Model1 And Top5 Candidates

| top5_rank | quality_rank | selection | model | protocol | confidence | mean_b_iso | high/low | model1_rmsd | viewer | folder |
| --- | --- | --- | --- | --- | ---: | ---: | --- | ---: | --- | --- |
| `1` | `1` | `115` | `Model_4760_afm_basic_model_5_multimer_v1_pred_26.pdb` | `afm_basic_v1` | 99.93822 | 91.303 | `0.94293/0.03683` | 0.0 | `casp17/massivefold_representative_viewers/h2324/selection_115_afm_basic_v1_model_4760/viewer.html` | `casp17/massivefold_representative_rerank/h2324/top5/rank_01_selection_115_afm_basic_v1` |
| `2` | `2` | `43` | `Model_75_afm_woTemplates_model_1_multimer_v1_pred_19.pdb` | `afm_woTemplates_v1` | 99.7622 | 91.05 | `0.94482/0.03348` | 61.699 | `casp17/massivefold_representative_viewers/h2324/selection_043_afm_woTemplates_v1_model_75/viewer.html` | `casp17/massivefold_representative_rerank/h2324/top5/rank_02_selection_043_afm_woTemplates_v1` |
| `3` | `3` | `38` | `Model_6_afm_woTemplates_model_2_multimer_v3_pred_24.pdb` | `afm_woTemplates_v3` | 99.75348 | 90.923 | `0.94322/0.02941` | 46.049 | `casp17/massivefold_representative_viewers/h2324/selection_038_afm_woTemplates_v3_model_6/viewer.html` | `casp17/massivefold_representative_rerank/h2324/top5/rank_03_selection_038_afm_woTemplates_v3` |
| `4` | `5` | `82` | `Model_44_cf_woTemplates_model_4_multimer_v3_pred_19.pdb` | `cf_woTemplates_v3` | 99.66466 | 90.832 | `0.95007/0.03028` | 60.788 | `casp17/massivefold_representative_viewers/h2324/selection_082_cf_woTemplates_v3_model_44/viewer.html` | `casp17/massivefold_representative_rerank/h2324/top5/rank_04_selection_082_cf_woTemplates_v3` |
| `5` | `8` | `40` | `Model_4_afm_dropout_noSM_woTemplates_model_4_multimer_v3_pred_25.pdb` | `afm_dropout_noSM_woTemplates_v3` | 99.36256 | 90.519 | `0.94846/0.03086` | 62.242 | `casp17/massivefold_representative_viewers/h2324/selection_040_afm_dropout_noSM_woTemplates_v3_model_4/viewer.html` | `casp17/massivefold_representative_rerank/h2324/top5/rank_05_selection_040_afm_dropout_noSM_woTemplates_v3` |

## Claim Boundary

CASP17 MassiveFold representative rerank packet only. It ranks organizer-provided external representatives using confidence, geometry, and diversity proxies for review-only model selection. It does not use a native structure, does not prove CASP accuracy, does not create internal predictions, and does not submit models.
