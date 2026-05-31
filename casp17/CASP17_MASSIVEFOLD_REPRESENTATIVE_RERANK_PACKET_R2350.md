# CASP17 MassiveFold Representative Rerank Packet

- generated: `2026-05-31T20:58:01+09:00`
- status: `massivefold_representative_rerank_ready_review_only`
- target: `R2350`
- candidates/model1/top5: `40/1/5`
- top5_protocol_count: `5`
- confidence_score min/max: `82.042/83.34166`
- mean_b_iso min/max: `74.938/75.799`
- model1: `Model_20_af3_woPaired_af3_seed_612441_sample_0_pred_640.cif` protocol `woPaired` score `83.34166` viewer `casp17/massivefold_representative_viewers/r2350/selection_020_woPaired_model_20/viewer.html`
- top5_manifest: `casp17/massivefold_representative_rerank/r2350/top5_manifest.csv`
- next action: use the review-only model1/top5 picks as accuracy-estimation and conformation-triage inputs; do not submit or count them as internal competitive proof without CASP rule and provenance clearance

## Model1 And Top5 Candidates

| top5_rank | quality_rank | selection | model | protocol | confidence | mean_b_iso | high/low | model1_rmsd | viewer | folder |
| --- | --- | --- | --- | --- | ---: | ---: | --- | ---: | --- | --- |
| `1` | `1` | `20` | `Model_20_af3_woPaired_af3_seed_612441_sample_0_pred_640.cif` | `woPaired` | 83.34166 | 75.742 | `0.81441/0.02619` | 0.0 | `casp17/massivefold_representative_viewers/r2350/selection_020_woPaired_model_20/viewer.html` | `casp17/massivefold_representative_rerank/r2350/top5/rank_01_selection_020_woPaired` |
| `2` | `2` | `18` | `Model_5_af3_woUnpaired_woTemplates_af3_seed_100687_sample_3_pred_398.cif` | `woUnpaired_woTemplates` | 83.31874 | 75.799 | `0.81285/0.02703` | 45.595 | `casp17/massivefold_representative_viewers/r2350/selection_018_woUnpaired_woTemplates_model_5/viewer.html` | `casp17/massivefold_representative_rerank/r2350/top5/rank_02_selection_018_woUnpaired_woTemplates` |
| `3` | `3` | `37` | `Model_1_af3_woUnpaired_woPaired_woTemplates_af3_seed_811587_sample_2_pred_367.cif` | `woUnpaired_woPaired_woTemplates` | 83.20776 | 75.747 | `0.79916/0.02498` | 44.474 | `casp17/massivefold_representative_viewers/r2350/selection_037_woUnpaired_woPaired_woTemplates_model_1/viewer.html` | `casp17/massivefold_representative_rerank/r2350/top5/rank_03_selection_037_woUnpaired_woPaired_woTemplates` |
| `4` | `4` | `4` | `Model_13_af3_woUnpaired_woPaired_af3_seed_94539_sample_0_pred_25.cif` | `woUnpaired_woPaired` | 83.16338 | 75.621 | `0.80541/0.02402` | 47.055 | `casp17/massivefold_representative_viewers/r2350/selection_004_woUnpaired_woPaired_model_13/viewer.html` | `casp17/massivefold_representative_rerank/r2350/top5/rank_04_selection_004_woUnpaired_woPaired` |
| `5` | `5` | `8` | `Model_2_af3_woUnpaired_af3_seed_160939_sample_4_pred_359.cif` | `woUnpaired` | 83.1483 | 75.633 | `0.80841/0.02523` | 56.757 | `casp17/massivefold_representative_viewers/r2350/selection_008_woUnpaired_model_2/viewer.html` | `casp17/massivefold_representative_rerank/r2350/top5/rank_05_selection_008_woUnpaired` |

## Claim Boundary

CASP17 MassiveFold representative rerank packet only. It ranks organizer-provided external representatives using confidence, geometry, and diversity proxies for review-only model selection. It does not use a native structure, does not prove CASP accuracy, does not create internal predictions, and does not submit models.
