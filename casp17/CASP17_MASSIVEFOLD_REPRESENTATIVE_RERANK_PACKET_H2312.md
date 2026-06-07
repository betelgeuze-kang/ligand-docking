# CASP17 MassiveFold Representative Rerank Packet

- generated: `2026-05-31T23:23:22+09:00`
- status: `massivefold_representative_rerank_ready_review_only`
- target: `H2312`
- candidates/model1/top5: `130/1/5`
- top5_protocol_count: `5`
- confidence_score min/max: `41.84732/101.58484`
- mean_b_iso min/max: `50.065/92.105`
- model1: `Model_7550_afm_basic_model_5_multimer_v1_pred_11.pdb` protocol `afm_basic_v1` score `101.58484` viewer `casp17/massivefold_representative_viewers/h2312/selection_122_afm_basic_v1_model_7550/viewer.html`
- top5_manifest: `casp17/massivefold_representative_rerank/h2312/top5_manifest.csv`
- next action: use the review-only model1/top5 picks as accuracy-estimation and conformation-triage inputs; do not submit or count them as internal competitive proof without CASP rule and provenance clearance

## Model1 And Top5 Candidates

| top5_rank | quality_rank | selection | model | protocol | confidence | mean_b_iso | high/low | model1_rmsd | viewer | folder |
| --- | --- | --- | --- | --- | ---: | ---: | --- | ---: | --- | --- |
| `1` | `1` | `122` | `Model_7550_afm_basic_model_5_multimer_v1_pred_11.pdb` | `afm_basic_v1` | 101.58484 | 92.03 | `0.96902/0.00141` | 0.0 | `casp17/massivefold_representative_viewers/h2312/selection_122_afm_basic_v1_model_7550/viewer.html` | `casp17/massivefold_representative_rerank/h2312/top5/rank_01_selection_122_afm_basic_v1` |
| `2` | `2` | `12` | `Model_6050_cf_woTemplates_model_5_multimer_v1_pred_26.pdb` | `cf_woTemplates_v1` | 101.50354 | 92.105 | `0.96577/0.00739` | 56.614 | `casp17/massivefold_representative_viewers/h2312/selection_012_cf_woTemplates_v1_model_6050/viewer.html` | `casp17/massivefold_representative_rerank/h2312/top5/rank_02_selection_012_cf_woTemplates_v1` |
| `3` | `11` | `126` | `Model_8659_afm_woTemplates_model_5_multimer_v1_pred_61.pdb` | `afm_woTemplates_v1` | 100.90322 | 91.477 | `0.96093/0.0029` | 7.065 | `casp17/massivefold_representative_viewers/h2312/selection_126_afm_woTemplates_v1_model_8659/viewer.html` | `casp17/massivefold_representative_rerank/h2312/top5/rank_03_selection_126_afm_woTemplates_v1` |
| `4` | `13` | `28` | `Model_7811_afm_dropout_full_model_5_multimer_v1_pred_66.pdb` | `afm_dropout_full_v1` | 100.7713 | 91.253 | `0.96647/0.00202` | 2.787 | `casp17/massivefold_representative_viewers/h2312/selection_028_afm_dropout_full_v1_model_7811/viewer.html` | `casp17/massivefold_representative_rerank/h2312/top5/rank_04_selection_028_afm_dropout_full_v1` |
| `5` | `18` | `65` | `Model_8060_afm_dropout_noSM_woTemplates_model_5_multimer_v1_pred_55.pdb` | `afm_dropout_noSM_woTemplates_v1` | 100.40252 | 90.881 | `0.96586/0.00299` | 6.283 | `casp17/massivefold_representative_viewers/h2312/selection_065_afm_dropout_noSM_woTemplates_v1_model_8060/viewer.html` | `casp17/massivefold_representative_rerank/h2312/top5/rank_05_selection_065_afm_dropout_noSM_woTemplates_v1` |

## Claim Boundary

CASP17 MassiveFold representative rerank packet only. It ranks organizer-provided external representatives using confidence, geometry, and diversity proxies for review-only model selection. It does not use a native structure, does not prove CASP accuracy, does not create internal predictions, and does not submit models.
