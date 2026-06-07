# CASP17 MassiveFold Representative Rerank Packet

- generated: `2026-05-31T22:53:39+09:00`
- status: `massivefold_representative_rerank_ready_review_only`
- target: `H1311`
- candidates/model1/top5: `130/1/5`
- top5_protocol_count: `5`
- confidence_score min/max: `38.86992/104.19842`
- mean_b_iso min/max: `48.043/94.368`
- model1: `Model_5_afm_basic_model_4_multimer_v3_pred_5.pdb` protocol `afm_basic_v3` score `104.19842` viewer `casp17/massivefold_representative_viewers/h1311/selection_024_afm_basic_v3_model_5/viewer.html`
- top5_manifest: `casp17/massivefold_representative_rerank/h1311/top5_manifest.csv`
- next action: use the review-only model1/top5 picks as accuracy-estimation and conformation-triage inputs; do not submit or count them as internal competitive proof without CASP rule and provenance clearance

## Model1 And Top5 Candidates

| top5_rank | quality_rank | selection | model | protocol | confidence | mean_b_iso | high/low | model1_rmsd | viewer | folder |
| --- | --- | --- | --- | --- | ---: | ---: | --- | ---: | --- | --- |
| `1` | `1` | `24` | `Model_5_afm_basic_model_4_multimer_v3_pred_5.pdb` | `afm_basic_v3` | 104.19842 | 94.368 | `0.98745/0.0` | 0.0 | `casp17/massivefold_representative_viewers/h1311/selection_024_afm_basic_v3_model_5/viewer.html` | `casp17/massivefold_representative_rerank/h1311/top5/rank_01_selection_024_afm_basic_v3` |
| `2` | `6` | `85` | `Model_16_afm_dropout_full_model_4_multimer_v3_pred_36.pdb` | `afm_dropout_full_v3` | 103.86712 | 94.043 | `0.98624/0.0` | 2.431 | `casp17/massivefold_representative_viewers/h1311/selection_085_afm_dropout_full_v3_model_16/viewer.html` | `casp17/massivefold_representative_rerank/h1311/top5/rank_02_selection_085_afm_dropout_full_v3` |
| `3` | `11` | `15` | `Model_5030_afm_dropout_full_model_5_multimer_v1_pred_14.pdb` | `afm_dropout_full_v1` | 102.47614 | 92.939 | `0.97959/0.01194` | 35.789 | `casp17/massivefold_representative_viewers/h1311/selection_015_afm_dropout_full_v1_model_5030/viewer.html` | `casp17/massivefold_representative_rerank/h1311/top5/rank_03_selection_015_afm_dropout_full_v1` |
| `4` | `13` | `122` | `Model_4160_afm_basic_model_1_multimer_v1_pred_46.pdb` | `afm_basic_v1` | 102.10222 | 92.612 | `0.97581/0.0062` | 62.832 | `casp17/massivefold_representative_viewers/h1311/selection_122_afm_basic_v1_model_4160/viewer.html` | `casp17/massivefold_representative_rerank/h1311/top5/rank_04_selection_122_afm_basic_v1` |
| `5` | `17` | `82` | `Model_402_afm_basic_model_2_multimer_v2_pred_0.pdb` | `afm_basic_v2` | 101.6484 | 92.273 | `0.97838/0.01527` | 23.353 | `casp17/massivefold_representative_viewers/h1311/selection_082_afm_basic_v2_model_402/viewer.html` | `casp17/massivefold_representative_rerank/h1311/top5/rank_05_selection_082_afm_basic_v2` |

## Claim Boundary

CASP17 MassiveFold representative rerank packet only. It ranks organizer-provided external representatives using confidence, geometry, and diversity proxies for review-only model selection. It does not use a native structure, does not prove CASP accuracy, does not create internal predictions, and does not submit models.
