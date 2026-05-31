# CASP17 MassiveFold Representative Rerank Packet

- generated: `2026-05-31T20:39:01+09:00`
- status: `massivefold_representative_rerank_ready_review_only`
- target: `R2341`
- candidates/model1/top5: `40/1/5`
- top5_protocol_count: `5`
- confidence_score min/max: `48.2803/53.0992`
- mean_b_iso min/max: `55.409/58.251`
- model1: `Model_2_af3_basic_af3_seed_672131_sample_4_pred_869.cif` protocol `basic` score `53.0992` viewer `casp17/massivefold_representative_viewers/r2341/selection_031_basic_model_2/viewer.html`
- top5_manifest: `casp17/massivefold_representative_rerank/r2341/top5_manifest.csv`
- next action: use the review-only model1/top5 picks as accuracy-estimation and conformation-triage inputs; do not submit or count them as internal competitive proof without CASP rule and provenance clearance

## Model1 And Top5 Candidates

| top5_rank | quality_rank | selection | model | protocol | confidence | mean_b_iso | high/low | model1_rmsd | viewer | folder |
| --- | --- | --- | --- | --- | ---: | ---: | --- | ---: | --- | --- |
| `1` | `1` | `31` | `Model_2_af3_basic_af3_seed_672131_sample_4_pred_869.cif` | `basic` | 53.0992 | 58.122 | `0.29232/0.39277` | 0.0 | `casp17/massivefold_representative_viewers/r2341/selection_031_basic_model_2/viewer.html` | `casp17/massivefold_representative_rerank/r2341/top5/rank_01_selection_031_basic` |
| `2` | `2` | `1` | `Model_1_af3_woUnpaired_woPaired_woTemplates_af3_seed_210550_sample_3_pred_718.cif` | `woUnpaired_woPaired_woTemplates` | 52.99014 | 58.251 | `0.29181/0.40281` | 53.513 | `casp17/massivefold_representative_viewers/r2341/selection_001_woUnpaired_woPaired_woTemplates_model_1/viewer.html` | `casp17/massivefold_representative_rerank/r2341/top5/rank_02_selection_001_woUnpaired_woPaired_woTemplates` |
| `3` | `4` | `28` | `Model_32_af3_woPaired_woTemplates_af3_seed_446958_sample_2_pred_942.cif` | `woPaired_woTemplates` | 52.36314 | 58.005 | `0.29633/0.41487` | 45.043 | `casp17/massivefold_representative_viewers/r2341/selection_028_woPaired_woTemplates_model_32/viewer.html` | `casp17/massivefold_representative_rerank/r2341/top5/rank_03_selection_028_woPaired_woTemplates` |
| `4` | `5` | `29` | `Model_9_af3_woUnpaired_woTemplates_af3_seed_120091_sample_0_pred_340.cif` | `woUnpaired_woTemplates` | 52.26184 | 57.787 | `0.2898/0.40784` | 59.359 | `casp17/massivefold_representative_viewers/r2341/selection_029_woUnpaired_woTemplates_model_9/viewer.html` | `casp17/massivefold_representative_rerank/r2341/top5/rank_04_selection_029_woUnpaired_woTemplates` |
| `5` | `6` | `21` | `Model_7_af3_woUnpaired_af3_seed_914475_sample_4_pred_209.cif` | `woUnpaired` | 52.02568 | 57.608 | `0.29432/0.42441` | 55.231 | `casp17/massivefold_representative_viewers/r2341/selection_021_woUnpaired_model_7/viewer.html` | `casp17/massivefold_representative_rerank/r2341/top5/rank_05_selection_021_woUnpaired` |

## Claim Boundary

CASP17 MassiveFold representative rerank packet only. It ranks organizer-provided external representatives using confidence, geometry, and diversity proxies for review-only model selection. It does not use a native structure, does not prove CASP accuracy, does not create internal predictions, and does not submit models.
