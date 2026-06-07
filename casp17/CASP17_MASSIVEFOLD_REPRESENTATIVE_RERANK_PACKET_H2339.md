# CASP17 MassiveFold Representative Rerank Packet

- generated: `2026-06-01T00:22:19+09:00`
- status: `massivefold_representative_rerank_ready_review_only`
- target: `H2339`
- candidates/model1/top5: `130/1/5`
- top5_protocol_count: `5`
- confidence_score min/max: `41.38864/102.90764`
- mean_b_iso min/max: `49.992/93.332`
- model1: `Model_135_afm_basic_model_5_multimer_v1_pred_62.pdb` protocol `afm_basic_v1` score `102.90764` viewer `casp17/massivefold_representative_viewers/h2339/selection_111_afm_basic_v1_model_135/viewer.html`
- top5_manifest: `casp17/massivefold_representative_rerank/h2339/top5_manifest.csv`
- next action: use the review-only model1/top5 picks as accuracy-estimation and conformation-triage inputs; do not submit or count them as internal competitive proof without CASP rule and provenance clearance

## Model1 And Top5 Candidates

| top5_rank | quality_rank | selection | model | protocol | confidence | mean_b_iso | high/low | model1_rmsd | viewer | folder |
| --- | --- | --- | --- | --- | ---: | ---: | --- | ---: | --- | --- |
| `1` | `1` | `111` | `Model_135_afm_basic_model_5_multimer_v1_pred_62.pdb` | `afm_basic_v1` | 102.90764 | 93.304 | `0.97288/0.00308` | 0.0 | `casp17/massivefold_representative_viewers/h2339/selection_111_afm_basic_v1_model_135/viewer.html` | `casp17/massivefold_representative_rerank/h2339/top5/rank_01_selection_111_afm_basic_v1` |
| `2` | `6` | `121` | `Model_174_afm_dropout_full_model_5_multimer_v1_pred_22.pdb` | `afm_dropout_full_v1` | 102.1607 | 92.552 | `0.96893/0.00308` | 36.62 | `casp17/massivefold_representative_viewers/h2339/selection_121_afm_dropout_full_v1_model_174/viewer.html` | `casp17/massivefold_representative_rerank/h2339/top5/rank_02_selection_121_afm_dropout_full_v1` |
| `3` | `11` | `67` | `Model_1_afm_basic_model_4_multimer_v2_pred_44.pdb` | `afm_basic_v2` | 100.96566 | 91.736 | `0.95821/0.00986` | 58.971 | `casp17/massivefold_representative_viewers/h2339/selection_067_afm_basic_v2_model_1/viewer.html` | `casp17/massivefold_representative_rerank/h2339/top5/rank_03_selection_067_afm_basic_v2` |
| `4` | `12` | `60` | `Model_444_afm_woTemplates_model_4_multimer_v1_pred_50.pdb` | `afm_woTemplates_v1` | 100.78402 | 91.359 | `0.96881/0.01196` | 56.944 | `casp17/massivefold_representative_viewers/h2339/selection_060_afm_woTemplates_v1_model_444/viewer.html` | `casp17/massivefold_representative_rerank/h2339/top5/rank_04_selection_060_afm_woTemplates_v1` |
| `5` | `14` | `99` | `Model_974_cf_woTemplates_model_5_multimer_v1_pred_18.pdb` | `cf_woTemplates_v1` | 100.51692 | 91.17 | `0.96598/0.01196` | 55.472 | `casp17/massivefold_representative_viewers/h2339/selection_099_cf_woTemplates_v1_model_974/viewer.html` | `casp17/massivefold_representative_rerank/h2339/top5/rank_05_selection_099_cf_woTemplates_v1` |

## Claim Boundary

CASP17 MassiveFold representative rerank packet only. It ranks organizer-provided external representatives using confidence, geometry, and diversity proxies for review-only model selection. It does not use a native structure, does not prove CASP accuracy, does not create internal predictions, and does not submit models.
