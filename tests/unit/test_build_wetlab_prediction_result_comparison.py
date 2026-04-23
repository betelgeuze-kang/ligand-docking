from __future__ import annotations

import pandas as pd

from tools import build_wetlab_prediction_result_comparison as mod


def test_build_wetlab_prediction_result_comparison_percent_inhibition() -> None:
    prediction = pd.DataFrame(
        [
            {"target_id": "EGFR_KINASE", "chembl_id": "CHEMBL_A", "binding_score_composite_v5": 9.0, "compound_name": "A"},
            {"target_id": "EGFR_KINASE", "chembl_id": "CHEMBL_B", "binding_score_composite_v5": 7.0, "compound_name": "B"},
            {"target_id": "EGFR_KINASE", "chembl_id": "CHEMBL_C", "binding_score_composite_v5": 2.0, "compound_name": "C"},
        ]
    )
    actual = pd.DataFrame(
        [
            {"target_id": "EGFR_KINASE", "chembl_id": "CHEMBL_A", "percent_inhibition": 90.0, "replicate_count": 3},
            {"target_id": "EGFR_KINASE", "chembl_id": "CHEMBL_B", "percent_inhibition": 62.0, "replicate_count": 3},
            {"target_id": "EGFR_KINASE", "chembl_id": "CHEMBL_C", "percent_inhibition": 12.0, "replicate_count": 3},
        ]
    )

    payload = mod.build_payload(prediction, actual)

    assert payload["summary"]["status"] == "wetlab_prediction_result_comparison_ready"
    assert payload["summary"]["actual_value_kind"] == "percent_inhibition"
    assert payload["summary"]["merged_row_count"] == 3
    assert payload["summary"]["global_spearman_prediction_vs_activity"] == 1.0
    assert payload["targets"][0]["top1_rank_match"] is True
    assert payload["targets"][0]["top3_hit_count"] == 2


def test_build_wetlab_prediction_result_comparison_ic50_converts_to_pic50() -> None:
    prediction = pd.DataFrame(
        [
            {"target": "HIV1_PROTEASE", "compound_id": "cmp_1", "commercial_overall_score_v2": 80.0},
            {"target": "HIV1_PROTEASE", "compound_id": "cmp_2", "commercial_overall_score_v2": 50.0},
        ]
    )
    actual = pd.DataFrame(
        [
            {"target": "HIV1_PROTEASE", "compound_id": "cmp_1", "ic50_nM": 10.0},
            {"target": "HIV1_PROTEASE", "compound_id": "cmp_2", "ic50_nM": 1000.0},
        ]
    )

    payload = mod.build_payload(prediction, actual)
    rows = payload["rows"]

    assert payload["summary"]["actual_value_kind"] == "ic50_nM"
    assert rows[0]["observed_activity_score"] == 8.0
    assert rows[1]["observed_activity_score"] == 6.0
