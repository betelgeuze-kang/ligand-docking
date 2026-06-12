from __future__ import annotations

import pytest

from tools import build_tools_package_batch3_other_review_classification_plan as mod


def test_batch3_other_review_classification_plan_ready() -> None:
    payload = mod.build_tools_package_batch3_other_review_classification_plan(
        batch3_plan_packet={
            "summary": {"status": "tools_package_batch3_review_plan_ready"},
            "rows": [
                {
                    "tool_path": "tools/build_alk2_launch_packet.py",
                    "proposed_package": "other_review",
                    "migration_batch": "batch_3_high_reference",
                    "review_lane": "lane_a_zero_test_low_internal",
                    "target_path": "",
                },
                {
                    "tool_path": "tools/build_idp_release_report.py",
                    "proposed_package": "other_review",
                    "migration_batch": "batch_3_high_reference",
                    "review_lane": "lane_a_zero_test_low_internal",
                    "target_path": "",
                },
                {
                    "tool_path": "tools/build_p2_data_lifecycle_manifest.py",
                    "proposed_package": "other_review",
                    "migration_batch": "batch_3_high_reference",
                    "review_lane": "lane_a_zero_test_low_internal",
                    "target_path": "",
                },
            ],
        }
    )

    summary = payload["summary"]
    assert summary["status"] == "tools_package_batch3_other_review_classification_plan_ready"
    assert summary["candidate_count"] == 3
    assert summary["classified_count"] == 3
    assert summary["unclassified_count"] == 0
    rows = {row["tool_path"]: row for row in payload["rows"]}
    assert rows["tools/build_alk2_launch_packet.py"]["reclassified_package"] == "wetlab"
    assert rows["tools/build_idp_release_report.py"]["target_path"] == "tools/product/build_idp_release_report.py"
    assert rows["tools/build_p2_data_lifecycle_manifest.py"]["target_path"] == (
        "tools/cleanup/build_p2_data_lifecycle_manifest.py"
    )


def test_batch3_other_review_classification_blocks_unknown_rows() -> None:
    payload = mod.build_tools_package_batch3_other_review_classification_plan(
        batch3_plan_packet={
            "summary": {"status": "tools_package_batch3_review_plan_ready"},
            "rows": [
                {
                    "tool_path": "tools/unmapped_batch3_tool.py",
                    "proposed_package": "other_review",
                    "migration_batch": "batch_3_high_reference",
                    "review_lane": "lane_a_zero_test_low_internal",
                    "target_path": "",
                }
            ],
        }
    )

    assert payload["summary"]["status"] == "blocked_tools_package_batch3_other_review_classification_plan"
    assert payload["summary"]["unclassified_count"] == 1
    assert payload["rows"][0]["classification_status"] == "manual_review_required"


def test_batch3_other_review_classifies_idp_branch_training() -> None:
    payload = mod.build_tools_package_batch3_other_review_classification_plan(
        batch3_plan_packet={
            "summary": {"status": "tools_package_batch3_review_plan_ready"},
            "rows": [
                {
                    "tool_path": "tools/train_idp_branch_model.py",
                    "proposed_package": "other_review",
                    "migration_batch": "batch_3_high_reference",
                    "review_lane": "lane_a_zero_test_low_internal",
                    "target_path": "",
                }
            ],
        }
    )

    summary = payload["summary"]
    row = payload["rows"][0]
    assert summary["status"] == "tools_package_batch3_other_review_classification_plan_ready"
    assert summary["classified_count"] == 1
    assert summary["unclassified_count"] == 0
    assert row["reclassified_package"] == "product"
    assert row["target_path"] == "tools/product/train_idp_branch_model.py"


@pytest.mark.parametrize(
    "stem",
    [
        "run_ligand_stress_validation",
        "run_ligand_topk_delivery",
        "run_nightly_screening_batch",
        "run_ood_first_validation_batch",
        "run_rust_native_inference_poc",
        "run_strict_release_with_regression_gate",
        "stage2_full_report",
        "sweep_ai_interval_tradeoff",
        "validate_accuracy_gate",
    ],
)
def test_batch3_other_review_classifies_current_product_runtime_tools(stem: str) -> None:
    payload = mod.build_tools_package_batch3_other_review_classification_plan(
        batch3_plan_packet={
            "summary": {"status": "tools_package_batch3_review_plan_ready"},
            "rows": [
                {
                    "tool_path": f"tools/{stem}.py",
                    "proposed_package": "other_review",
                    "migration_batch": "batch_3_high_reference",
                    "review_lane": "lane_a_zero_test_low_internal",
                    "target_path": "",
                }
            ],
        }
    )

    summary = payload["summary"]
    row = payload["rows"][0]
    assert summary["status"] == "tools_package_batch3_other_review_classification_plan_ready"
    assert summary["unclassified_count"] == 0
    assert row["reclassified_package"] == "product"
    assert row["target_path"] == f"tools/product/{stem}.py"


def test_batch3_other_review_classification_ready_when_no_candidates_remain() -> None:
    payload = mod.build_tools_package_batch3_other_review_classification_plan(
        batch3_plan_packet={
            "summary": {"status": "tools_package_batch3_review_plan_ready"},
            "rows": [
                {
                    "tool_path": "tools/monitor_ligand_stress_progress.py",
                    "proposed_package": "other_review",
                    "migration_batch": "batch_3_high_reference",
                    "review_lane": "lane_a_zero_test_low_internal",
                    "target_path": "tools/product/monitor_ligand_stress_progress.py",
                    "target_module_exists": True,
                }
            ],
        }
    )

    summary = payload["summary"]
    assert summary["status"] == "tools_package_batch3_other_review_classification_plan_ready"
    assert summary["plan_ready"] is True
    assert summary["candidate_count"] == 0
    assert summary["unclassified_count"] == 0
