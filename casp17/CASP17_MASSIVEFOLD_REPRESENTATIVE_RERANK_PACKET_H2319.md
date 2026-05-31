# CASP17 MassiveFold Representative Rerank Packet

- generated: `2026-06-01T00:36:45+09:00`
- status: `massivefold_representative_rerank_ready_review_only`
- target: `H2319`
- candidates/model1/top5: `130/1/5`
- top5_protocol_count: `5`
- confidence_score min/max: `41.5205/105.48786`
- mean_b_iso min/max: `48.978/95.595`
- model1: `Model_1_afm_basic_model_4_multimer_v3_pred_25.pdb` protocol `afm_basic_v3` score `105.48786` viewer `casp17/massivefold_representative_viewers/h2319/selection_125_afm_basic_v3_model_1/viewer.html`
- top5_manifest: `casp17/massivefold_representative_rerank/h2319/top5_manifest.csv`
- next action: use the review-only model1/top5 picks as accuracy-estimation and conformation-triage inputs; do not submit or count them as internal competitive proof without CASP rule and provenance clearance

## Model1 And Top5 Candidates

| top5_rank | quality_rank | selection | model | protocol | confidence | mean_b_iso | high/low | model1_rmsd | viewer | folder |
| --- | --- | --- | --- | --- | ---: | ---: | --- | ---: | --- | --- |
| `1` | `1` | `125` | `Model_1_afm_basic_model_4_multimer_v3_pred_25.pdb` | `afm_basic_v3` | 105.48786 | 95.595 | `0.99433/0.0` | 0.0 | `casp17/massivefold_representative_viewers/h2319/selection_125_afm_basic_v3_model_1/viewer.html` | `casp17/massivefold_representative_rerank/h2319/top5/rank_01_selection_125_afm_basic_v3` |
| `2` | `5` | `1` | `Model_2_afm_dropout_full_model_4_multimer_v3_pred_65.pdb` | `afm_dropout_full_v3` | 104.92274 | 95.046 | `0.99433/0.0` | 52.429 | `casp17/massivefold_representative_viewers/h2319/selection_001_afm_dropout_full_v3_model_2/viewer.html` | `casp17/massivefold_representative_rerank/h2319/top5/rank_02_selection_001_afm_dropout_full_v3` |
| `3` | `11` | `87` | `Model_12_afm_basic_model_1_multimer_v2_pred_64.pdb` | `afm_basic_v2` | 103.80454 | 94.023 | `0.98375/0.0` | 54.647 | `casp17/massivefold_representative_viewers/h2319/selection_087_afm_basic_v2_model_12/viewer.html` | `casp17/massivefold_representative_rerank/h2319/top5/rank_03_selection_087_afm_basic_v2` |
| `4` | `12` | `51` | `Model_10_afm_dropout_full_model_1_multimer_v2_pred_30.pdb` | `afm_dropout_full_v2` | 103.75186 | 93.949 | `0.98169/0.0` | 39.385 | `casp17/massivefold_representative_viewers/h2319/selection_051_afm_dropout_full_v2_model_10/viewer.html` | `casp17/massivefold_representative_rerank/h2319/top5/rank_04_selection_051_afm_dropout_full_v2` |
| `5` | `21` | `44` | `Model_6_cf_woTemplates_model_4_multimer_v3_pred_24.pdb` | `cf_woTemplates_v3` | 101.44694 | 92.228 | `0.95899/0.01341` | 29.335 | `casp17/massivefold_representative_viewers/h2319/selection_044_cf_woTemplates_v3_model_6/viewer.html` | `casp17/massivefold_representative_rerank/h2319/top5/rank_05_selection_044_cf_woTemplates_v3` |

## Claim Boundary

CASP17 MassiveFold representative rerank packet only. It ranks organizer-provided external representatives using confidence, geometry, and diversity proxies for review-only model selection. It does not use a native structure, does not prove CASP accuracy, does not create internal predictions, and does not submit models.
