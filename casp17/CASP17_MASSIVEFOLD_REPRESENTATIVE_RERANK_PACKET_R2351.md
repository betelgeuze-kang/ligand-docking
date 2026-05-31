# CASP17 MassiveFold Representative Rerank Packet

- generated: `2026-05-31T21:08:12+09:00`
- status: `massivefold_representative_rerank_ready_review_only`
- target: `R2351`
- candidates/model1/top5: `40/1/5`
- top5_protocol_count: `5`
- confidence_score min/max: `82.38588/83.86274`
- mean_b_iso min/max: `75.167/76.155`
- model1: `Model_18_af3_woTemplates_af3_seed_103360_sample_3_pred_608.cif` protocol `woTemplates` score `83.86274` viewer `casp17/massivefold_representative_viewers/r2351/selection_026_woTemplates_model_18/viewer.html`
- top5_manifest: `casp17/massivefold_representative_rerank/r2351/top5_manifest.csv`
- next action: use the review-only model1/top5 picks as accuracy-estimation and conformation-triage inputs; do not submit or count them as internal competitive proof without CASP rule and provenance clearance

## Model1 And Top5 Candidates

| top5_rank | quality_rank | selection | model | protocol | confidence | mean_b_iso | high/low | model1_rmsd | viewer | folder |
| --- | --- | --- | --- | --- | ---: | ---: | --- | ---: | --- | --- |
| `1` | `1` | `26` | `Model_18_af3_woTemplates_af3_seed_103360_sample_3_pred_608.cif` | `woTemplates` | 83.86274 | 76.155 | `0.82725/0.02415` | 0.0 | `casp17/massivefold_representative_viewers/r2351/selection_026_woTemplates_model_18/viewer.html` | `casp17/massivefold_representative_rerank/r2351/top5/rank_01_selection_026_woTemplates` |
| `2` | `2` | `38` | `Model_21_af3_basic_af3_seed_571067_sample_0_pred_415.cif` | `basic` | 83.73174 | 76.085 | `0.81187/0.02259` | 54.726 | `casp17/massivefold_representative_viewers/r2351/selection_038_basic_model_21/viewer.html` | `casp17/massivefold_representative_rerank/r2351/top5/rank_02_selection_038_basic` |
| `3` | `3` | `18` | `Model_6_af3_woUnpaired_af3_seed_447781_sample_3_pred_923.cif` | `woUnpaired` | 83.7126 | 76.109 | `0.81932/0.02451` | 54.843 | `casp17/massivefold_representative_viewers/r2351/selection_018_woUnpaired_model_6/viewer.html` | `casp17/massivefold_representative_rerank/r2351/top5/rank_03_selection_018_woUnpaired` |
| `4` | `6` | `7` | `Model_1_af3_woPaired_af3_seed_783356_sample_0_pred_395.cif` | `woPaired` | 83.63282 | 76.08 | `0.81199/0.02138` | 53.328 | `casp17/massivefold_representative_viewers/r2351/selection_007_woPaired_model_1/viewer.html` | `casp17/massivefold_representative_rerank/r2351/top5/rank_04_selection_007_woPaired` |
| `5` | `7` | `20` | `Model_10_af3_woUnpaired_woPaired_af3_seed_456016_sample_2_pred_222.cif` | `woUnpaired_woPaired` | 83.60796 | 75.978 | `0.818/0.0221` | 65.136 | `casp17/massivefold_representative_viewers/r2351/selection_020_woUnpaired_woPaired_model_10/viewer.html` | `casp17/massivefold_representative_rerank/r2351/top5/rank_05_selection_020_woUnpaired_woPaired` |

## Claim Boundary

CASP17 MassiveFold representative rerank packet only. It ranks organizer-provided external representatives using confidence, geometry, and diversity proxies for review-only model selection. It does not use a native structure, does not prove CASP accuracy, does not create internal predictions, and does not submit models.
