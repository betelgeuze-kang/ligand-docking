# CASP17 MassiveFold Representative Rerank Packet

- generated: `2026-06-01T00:49:57+09:00`
- status: `massivefold_representative_rerank_ready_review_only`
- target: `H2321`
- candidates/model1/top5: `130/1/5`
- top5_protocol_count: `5`
- confidence_score min/max: `42.32522/102.10998`
- mean_b_iso min/max: `49.795/92.617`
- model1: `Model_3_afm_dropout_full_model_2_multimer_v3_pred_48.pdb` protocol `afm_dropout_full_v3` score `102.10998` viewer `casp17/massivefold_representative_viewers/h2321/selection_086_afm_dropout_full_v3_model_3/viewer.html`
- top5_manifest: `casp17/massivefold_representative_rerank/h2321/top5_manifest.csv`
- next action: use the review-only model1/top5 picks as accuracy-estimation and conformation-triage inputs; do not submit or count them as internal competitive proof without CASP rule and provenance clearance

## Model1 And Top5 Candidates

| top5_rank | quality_rank | selection | model | protocol | confidence | mean_b_iso | high/low | model1_rmsd | viewer | folder |
| --- | --- | --- | --- | --- | ---: | ---: | --- | ---: | --- | --- |
| `1` | `1` | `86` | `Model_3_afm_dropout_full_model_2_multimer_v3_pred_48.pdb` | `afm_dropout_full_v3` | 102.10998 | 92.617 | `0.96779/0.00203` | 0.0 | `casp17/massivefold_representative_viewers/h2321/selection_086_afm_dropout_full_v3_model_3/viewer.html` | `casp17/massivefold_representative_rerank/h2321/top5/rank_01_selection_086_afm_dropout_full_v3` |
| `2` | `5` | `53` | `Model_14_afm_basic_model_1_multimer_v2_pred_43.pdb` | `afm_basic_v2` | 101.4412 | 91.961 | `0.96602/0.00292` | 32.155 | `casp17/massivefold_representative_viewers/h2321/selection_053_afm_basic_v2_model_14/viewer.html` | `casp17/massivefold_representative_rerank/h2321/top5/rank_02_selection_053_afm_basic_v2` |
| `3` | `6` | `93` | `Model_5_afm_dropout_full_model_2_multimer_v2_pred_42.pdb` | `afm_dropout_full_v2` | 101.13708 | 91.655 | `0.9617/0.00178` | 41.408 | `casp17/massivefold_representative_viewers/h2321/selection_093_afm_dropout_full_v2_model_5/viewer.html` | `casp17/massivefold_representative_rerank/h2321/top5/rank_03_selection_093_afm_dropout_full_v2` |
| `4` | `7` | `125` | `Model_70_afm_basic_model_4_multimer_v3_pred_64.pdb` | `afm_basic_v3` | 100.98888 | 91.569 | `0.95866/0.00203` | 39.181 | `casp17/massivefold_representative_viewers/h2321/selection_125_afm_basic_v3_model_70/viewer.html` | `casp17/massivefold_representative_rerank/h2321/top5/rank_04_selection_125_afm_basic_v3` |
| `5` | `21` | `77` | `Model_8_afm_dropout_noSM_woTemplates_model_3_multimer_v3_pred_1.pdb` | `afm_dropout_noSM_woTemplates_v3` | 98.5448 | 89.491 | `0.94484/0.01623` | 45.77 | `casp17/massivefold_representative_viewers/h2321/selection_077_afm_dropout_noSM_woTemplates_v3_model_8/viewer.html` | `casp17/massivefold_representative_rerank/h2321/top5/rank_05_selection_077_afm_dropout_noSM_woTemplates_v3` |

## Claim Boundary

CASP17 MassiveFold representative rerank packet only. It ranks organizer-provided external representatives using confidence, geometry, and diversity proxies for review-only model selection. It does not use a native structure, does not prove CASP accuracy, does not create internal predictions, and does not submit models.
