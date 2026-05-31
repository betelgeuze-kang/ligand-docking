# CASP17 MassiveFold Representative Rerank Packet

- generated: `2026-05-31T20:39:09+09:00`
- status: `massivefold_representative_rerank_ready_review_only`
- target: `R2345`
- candidates/model1/top5: `40/1/5`
- top5_protocol_count: `5`
- confidence_score min/max: `47.08754/57.89694`
- mean_b_iso min/max: `53.122/58.868`
- model1: `Model_4_af3_woUnpaired_af3_seed_418984_sample_3_pred_713.cif` protocol `woUnpaired` score `57.89694` viewer `casp17/massivefold_representative_viewers/r2345/selection_013_woUnpaired_model_4/viewer.html`
- top5_manifest: `casp17/massivefold_representative_rerank/r2345/top5_manifest.csv`
- next action: use the review-only model1/top5 picks as accuracy-estimation and conformation-triage inputs; do not submit or count them as internal competitive proof without CASP rule and provenance clearance

## Model1 And Top5 Candidates

| top5_rank | quality_rank | selection | model | protocol | confidence | mean_b_iso | high/low | model1_rmsd | viewer | folder |
| --- | --- | --- | --- | --- | ---: | ---: | --- | ---: | --- | --- |
| `1` | `1` | `13` | `Model_4_af3_woUnpaired_af3_seed_418984_sample_3_pred_713.cif` | `woUnpaired` | 57.89694 | 58.868 | `0.04745/0.07007` | 0.0 | `casp17/massivefold_representative_viewers/r2345/selection_013_woUnpaired_model_4/viewer.html` | `casp17/massivefold_representative_rerank/r2345/top5/rank_01_selection_013_woUnpaired` |
| `2` | `2` | `16` | `Model_5_af3_woPaired_woTemplates_af3_seed_239697_sample_2_pred_712.cif` | `woPaired_woTemplates` | 56.25632 | 58.341 | `0.04964/0.12555` | 39.618 | `casp17/massivefold_representative_viewers/r2345/selection_016_woPaired_woTemplates_model_5/viewer.html` | `casp17/massivefold_representative_rerank/r2345/top5/rank_02_selection_016_woPaired_woTemplates` |
| `3` | `3` | `7` | `Model_7_af3_woUnpaired_woPaired_af3_seed_567474_sample_4_pred_449.cif` | `woUnpaired_woPaired` | 54.92012 | 57.478 | `0.0073/0.12993` | 29.901 | `casp17/massivefold_representative_viewers/r2345/selection_007_woUnpaired_woPaired_model_7/viewer.html` | `casp17/massivefold_representative_rerank/r2345/top5/rank_03_selection_007_woUnpaired_woPaired` |
| `4` | `6` | `36` | `Model_41_af3_woUnpaired_woTemplates_af3_seed_552323_sample_0_pred_155.cif` | `woUnpaired_woTemplates` | 53.92886 | 56.901 | `0.00365/0.14891` | 40.275 | `casp17/massivefold_representative_viewers/r2345/selection_036_woUnpaired_woTemplates_model_41/viewer.html` | `casp17/massivefold_representative_rerank/r2345/top5/rank_04_selection_036_woUnpaired_woTemplates` |
| `5` | `8` | `21` | `Model_42_af3_woUnpaired_woPaired_woTemplates_af3_seed_513300_sample_2_pred_592.cif` | `woUnpaired_woPaired_woTemplates` | 53.51738 | 56.528 | `0.00073/0.14891` | 20.191 | `casp17/massivefold_representative_viewers/r2345/selection_021_woUnpaired_woPaired_woTemplates_model_42/viewer.html` | `casp17/massivefold_representative_rerank/r2345/top5/rank_05_selection_021_woUnpaired_woPaired_woTemplates` |

## Claim Boundary

CASP17 MassiveFold representative rerank packet only. It ranks organizer-provided external representatives using confidence, geometry, and diversity proxies for review-only model selection. It does not use a native structure, does not prove CASP accuracy, does not create internal predictions, and does not submit models.
