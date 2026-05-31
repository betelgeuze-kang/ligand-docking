# CASP17 MassiveFold Representative Rerank Packet

- generated: `2026-05-31T21:30:23+09:00`
- status: `massivefold_representative_rerank_ready_review_only`
- target: `R2353`
- candidates/model1/top5: `40/1/5`
- top5_protocol_count: `5`
- confidence_score min/max: `79.15782/80.52762`
- mean_b_iso min/max: `72.859/73.668`
- model1: `Model_7_af3_woPaired_af3_seed_634615_sample_2_pred_387.cif` protocol `woPaired` score `80.52762` viewer `casp17/massivefold_representative_viewers/r2353/selection_021_woPaired_model_7/viewer.html`
- top5_manifest: `casp17/massivefold_representative_rerank/r2353/top5_manifest.csv`
- next action: use the review-only model1/top5 picks as accuracy-estimation and conformation-triage inputs; do not submit or count them as internal competitive proof without CASP rule and provenance clearance

## Model1 And Top5 Candidates

| top5_rank | quality_rank | selection | model | protocol | confidence | mean_b_iso | high/low | model1_rmsd | viewer | folder |
| --- | --- | --- | --- | --- | ---: | ---: | --- | ---: | --- | --- |
| `1` | `1` | `21` | `Model_7_af3_woPaired_af3_seed_634615_sample_2_pred_387.cif` | `woPaired` | 80.52762 | 73.668 | `0.76743/0.03937` | 0.0 | `casp17/massivefold_representative_viewers/r2353/selection_021_woPaired_model_7/viewer.html` | `casp17/massivefold_representative_rerank/r2353/top5/rank_01_selection_021_woPaired` |
| `2` | `2` | `32` | `Model_1_af3_woUnpaired_woPaired_af3_seed_3136_sample_2_pred_617.cif` | `woUnpaired_woPaired` | 80.43482 | 73.666 | `0.76803/0.04175` | 55.53 | `casp17/massivefold_representative_viewers/r2353/selection_032_woUnpaired_woPaired_model_1/viewer.html` | `casp17/massivefold_representative_rerank/r2353/top5/rank_02_selection_032_woUnpaired_woPaired` |
| `3` | `3` | `36` | `Model_5_af3_woUnpaired_woPaired_woTemplates_af3_seed_813694_sample_1_pred_871.cif` | `woUnpaired_woPaired_woTemplates` | 80.4287 | 73.628 | `0.76767/0.04163` | 57.936 | `casp17/massivefold_representative_viewers/r2353/selection_036_woUnpaired_woPaired_woTemplates_model_5/viewer.html` | `casp17/massivefold_representative_rerank/r2353/top5/rank_03_selection_036_woUnpaired_woPaired_woTemplates` |
| `4` | `7` | `17` | `Model_35_af3_woUnpaired_woTemplates_af3_seed_639646_sample_3_pred_853.cif` | `woUnpaired_woTemplates` | 80.1173 | 73.502 | `0.76435/0.04459` | 55.531 | `casp17/massivefold_representative_viewers/r2353/selection_017_woUnpaired_woTemplates_model_35/viewer.html` | `casp17/massivefold_representative_rerank/r2353/top5/rank_04_selection_017_woUnpaired_woTemplates` |
| `5` | `8` | `20` | `Model_26_af3_woUnpaired_af3_seed_166439_sample_4_pred_334.cif` | `woUnpaired` | 80.1145 | 73.412 | `0.75771/0.03997` | 45.139 | `casp17/massivefold_representative_viewers/r2353/selection_020_woUnpaired_model_26/viewer.html` | `casp17/massivefold_representative_rerank/r2353/top5/rank_05_selection_020_woUnpaired` |

## Claim Boundary

CASP17 MassiveFold representative rerank packet only. It ranks organizer-provided external representatives using confidence, geometry, and diversity proxies for review-only model selection. It does not use a native structure, does not prove CASP accuracy, does not create internal predictions, and does not submit models.
