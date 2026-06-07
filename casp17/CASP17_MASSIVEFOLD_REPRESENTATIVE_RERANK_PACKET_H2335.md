# CASP17 MassiveFold Representative Rerank Packet

- generated: `2026-06-01T01:09:55+09:00`
- status: `massivefold_representative_rerank_ready_review_only`
- target: `H2335`
- candidates/model1/top5: `130/1/5`
- top5_protocol_count: `5`
- confidence_score min/max: `25.89826/94.11582`
- mean_b_iso min/max: `40.33/86.328`
- model1: `Model_7830_afm_basic_model_5_multimer_v1_pred_39.pdb` protocol `afm_basic_v1` score `94.11582` viewer `casp17/massivefold_representative_viewers/h2335/selection_030_afm_basic_v1_model_7830/viewer.html`
- top5_manifest: `casp17/massivefold_representative_rerank/h2335/top5_manifest.csv`
- next action: use the review-only model1/top5 picks as accuracy-estimation and conformation-triage inputs; do not submit or count them as internal competitive proof without CASP rule and provenance clearance

## Model1 And Top5 Candidates

| top5_rank | quality_rank | selection | model | protocol | confidence | mean_b_iso | high/low | model1_rmsd | viewer | folder |
| --- | --- | --- | --- | --- | ---: | ---: | --- | ---: | --- | --- |
| `1` | `1` | `30` | `Model_7830_afm_basic_model_5_multimer_v1_pred_39.pdb` | `afm_basic_v1` | 94.11582 | 86.328 | `0.90013/0.04696` | 0.0 | `casp17/massivefold_representative_viewers/h2335/selection_030_afm_basic_v1_model_7830/viewer.html` | `casp17/massivefold_representative_rerank/h2335/top5/rank_01_selection_030_afm_basic_v1` |
| `2` | `6` | `32` | `Model_12_afm_basic_model_4_multimer_v3_pred_12.pdb` | `afm_basic_v3` | 93.0008 | 85.715 | `0.87838/0.06836` | 78.846 | `casp17/massivefold_representative_viewers/h2335/selection_032_afm_basic_v3_model_12/viewer.html` | `casp17/massivefold_representative_rerank/h2335/top5/rank_02_selection_032_afm_basic_v3` |
| `3` | `7` | `67` | `Model_7964_afm_dropout_full_model_5_multimer_v1_pred_41.pdb` | `afm_dropout_full_v1` | 92.90986 | 85.341 | `0.89515/0.05624` | 21.59 | `casp17/massivefold_representative_viewers/h2335/selection_067_afm_dropout_full_v1_model_7964/viewer.html` | `casp17/massivefold_representative_rerank/h2335/top5/rank_03_selection_067_afm_dropout_full_v1` |
| `4` | `8` | `117` | `Model_7659_cf_woTemplates_model_5_multimer_v1_pred_18.pdb` | `cf_woTemplates_v1` | 92.85496 | 85.253 | `0.87354/0.04619` | 52.585 | `casp17/massivefold_representative_viewers/h2335/selection_117_cf_woTemplates_v1_model_7659/viewer.html` | `casp17/massivefold_representative_rerank/h2335/top5/rank_04_selection_117_cf_woTemplates_v1` |
| `5` | `17` | `35` | `Model_40_afm_dropout_full_model_4_multimer_v3_pred_48.pdb` | `afm_dropout_full_v3` | 92.48552 | 85.287 | `0.87236/0.07161` | 78.913 | `casp17/massivefold_representative_viewers/h2335/selection_035_afm_dropout_full_v3_model_40/viewer.html` | `casp17/massivefold_representative_rerank/h2335/top5/rank_05_selection_035_afm_dropout_full_v3` |

## Claim Boundary

CASP17 MassiveFold representative rerank packet only. It ranks organizer-provided external representatives using confidence, geometry, and diversity proxies for review-only model selection. It does not use a native structure, does not prove CASP accuracy, does not create internal predictions, and does not submit models.
