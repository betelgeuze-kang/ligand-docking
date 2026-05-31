# CASP17 MassiveFold Representative Rerank Packet

- generated: `2026-05-31T21:19:25+09:00`
- status: `massivefold_representative_rerank_ready_review_only`
- target: `R2352`
- candidates/model1/top5: `40/1/5`
- top5_protocol_count: `5`
- confidence_score min/max: `81.42428/82.69558`
- mean_b_iso min/max: `74.297/75.218`
- model1: `Model_15_af3_woUnpaired_af3_seed_20656_sample_1_pred_611.cif` protocol `woUnpaired` score `82.69558` viewer `casp17/massivefold_representative_viewers/r2352/selection_034_woUnpaired_model_15/viewer.html`
- top5_manifest: `casp17/massivefold_representative_rerank/r2352/top5_manifest.csv`
- next action: use the review-only model1/top5 picks as accuracy-estimation and conformation-triage inputs; do not submit or count them as internal competitive proof without CASP rule and provenance clearance

## Model1 And Top5 Candidates

| top5_rank | quality_rank | selection | model | protocol | confidence | mean_b_iso | high/low | model1_rmsd | viewer | folder |
| --- | --- | --- | --- | --- | ---: | ---: | --- | ---: | --- | --- |
| `1` | `1` | `34` | `Model_15_af3_woUnpaired_af3_seed_20656_sample_1_pred_611.cif` | `woUnpaired` | 82.69558 | 75.136 | `0.80809/0.02318` | 0.0 | `casp17/massivefold_representative_viewers/r2352/selection_034_woUnpaired_model_15/viewer.html` | `casp17/massivefold_representative_rerank/r2352/top5/rank_01_selection_034_woUnpaired` |
| `2` | `3` | `23` | `Model_19_af3_woPaired_af3_seed_986684_sample_4_pred_279.cif` | `woPaired` | 82.62466 | 75.218 | `0.80137/0.0257` | 50.82 | `casp17/massivefold_representative_viewers/r2352/selection_023_woPaired_model_19/viewer.html` | `casp17/massivefold_representative_rerank/r2352/top5/rank_02_selection_023_woPaired` |
| `3` | `4` | `27` | `Model_7_af3_woPaired_woTemplates_af3_seed_26386_sample_2_pred_237.cif` | `woPaired_woTemplates` | 82.6207 | 75.117 | `0.80401/0.02642` | 28.967 | `casp17/massivefold_representative_viewers/r2352/selection_027_woPaired_woTemplates_model_7/viewer.html` | `casp17/massivefold_representative_rerank/r2352/top5/rank_03_selection_027_woPaired_woTemplates` |
| `4` | `5` | `24` | `Model_31_af3_woUnpaired_woPaired_woTemplates_af3_seed_91556_sample_0_pred_695.cif` | `woUnpaired_woPaired_woTemplates` | 82.55842 | 75.11 | `0.79969/0.02498` | 11.101 | `casp17/massivefold_representative_viewers/r2352/selection_024_woUnpaired_woPaired_woTemplates_model_31/viewer.html` | `casp17/massivefold_representative_rerank/r2352/top5/rank_04_selection_024_woUnpaired_woPaired_woTemplates` |
| `5` | `6` | `32` | `Model_18_af3_basic_af3_seed_674916_sample_2_pred_917.cif` | `basic` | 82.5543 | 75.041 | `0.80485/0.02654` | 27.034 | `casp17/massivefold_representative_viewers/r2352/selection_032_basic_model_18/viewer.html` | `casp17/massivefold_representative_rerank/r2352/top5/rank_05_selection_032_basic` |

## Claim Boundary

CASP17 MassiveFold representative rerank packet only. It ranks organizer-provided external representatives using confidence, geometry, and diversity proxies for review-only model selection. It does not use a native structure, does not prove CASP accuracy, does not create internal predictions, and does not submit models.
