# CASP17 MassiveFold Representative Rerank Packet

- generated: `2026-05-31T23:59:40+09:00`
- status: `massivefold_representative_rerank_ready_review_only`
- target: `H2338`
- candidates/model1/top5: `130/1/5`
- top5_protocol_count: `5`
- confidence_score min/max: `48.46328/103.87838`
- mean_b_iso min/max: `55.271/94.298`
- model1: `Model_2_afm_dropout_full_model_4_multimer_v3_pred_64.pdb` protocol `afm_dropout_full_v3` score `103.87838` viewer `casp17/massivefold_representative_viewers/h2338/selection_029_afm_dropout_full_v3_model_2/viewer.html`
- top5_manifest: `casp17/massivefold_representative_rerank/h2338/top5_manifest.csv`
- next action: use the review-only model1/top5 picks as accuracy-estimation and conformation-triage inputs; do not submit or count them as internal competitive proof without CASP rule and provenance clearance

## Model1 And Top5 Candidates

| top5_rank | quality_rank | selection | model | protocol | confidence | mean_b_iso | high/low | model1_rmsd | viewer | folder |
| --- | --- | --- | --- | --- | ---: | ---: | --- | ---: | --- | --- |
| `1` | `1` | `29` | `Model_2_afm_dropout_full_model_4_multimer_v3_pred_64.pdb` | `afm_dropout_full_v3` | 103.87838 | 94.298 | `0.97147/0.00541` | 0.0 | `casp17/massivefold_representative_viewers/h2338/selection_029_afm_dropout_full_v3_model_2/viewer.html` | `casp17/massivefold_representative_rerank/h2338/top5/rank_01_selection_029_afm_dropout_full_v3` |
| `2` | `3` | `96` | `Model_4_afm_basic_model_4_multimer_v3_pred_63.pdb` | `afm_basic_v3` | 103.42614 | 93.922 | `0.97233/0.00934` | 37.009 | `casp17/massivefold_representative_viewers/h2338/selection_096_afm_basic_v3_model_4/viewer.html` | `casp17/massivefold_representative_rerank/h2338/top5/rank_02_selection_096_afm_basic_v3` |
| `3` | `11` | `54` | `Model_29_afm_basic_model_4_multimer_v2_pred_25.pdb` | `afm_basic_v2` | 102.95262 | 93.507 | `0.97111/0.00934` | 15.056 | `casp17/massivefold_representative_viewers/h2338/selection_054_afm_basic_v2_model_29/viewer.html` | `casp17/massivefold_representative_rerank/h2338/top5/rank_03_selection_054_afm_basic_v2` |
| `4` | `13` | `16` | `Model_508_afm_basic_model_5_multimer_v1_pred_28.pdb` | `afm_basic_v1` | 102.41998 | 93.144 | `0.97713/0.00676` | 64.275 | `casp17/massivefold_representative_viewers/h2338/selection_016_afm_basic_v1_model_508/viewer.html` | `casp17/massivefold_representative_rerank/h2338/top5/rank_04_selection_016_afm_basic_v1` |
| `5` | `18` | `129` | `Model_1755_cf_woTemplates_model_5_multimer_v1_pred_12.pdb` | `cf_woTemplates_v1` | 102.09926 | 92.672 | `0.97455/0.01094` | 73.752 | `casp17/massivefold_representative_viewers/h2338/selection_129_cf_woTemplates_v1_model_1755/viewer.html` | `casp17/massivefold_representative_rerank/h2338/top5/rank_05_selection_129_cf_woTemplates_v1` |

## Claim Boundary

CASP17 MassiveFold representative rerank packet only. It ranks organizer-provided external representatives using confidence, geometry, and diversity proxies for review-only model selection. It does not use a native structure, does not prove CASP accuracy, does not create internal predictions, and does not submit models.
