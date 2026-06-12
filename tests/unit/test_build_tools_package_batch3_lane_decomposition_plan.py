from __future__ import annotations

from tools import build_tools_package_batch3_lane_decomposition_plan as mod


def test_batch3_lane_decomposition_selects_lane_b_move_candidates() -> None:
    payload = mod.build_tools_package_batch3_lane_decomposition_plan(
        batch3_plan_packet={
            "summary": {"status": "tools_package_batch3_review_plan_ready"},
            "rows": [
                {
                    "tool_path": "tools/run_alpha.py",
                    "proposed_package": "product",
                    "target_path": "tools/product/run_alpha.py",
                    "target_module_exists": False,
                    "has_non_target_canonical_module": False,
                    "review_lane": "lane_b_low_test_reference",
                    "test_reference_count": 1,
                    "tool_reference_count": 0,
                    "internal_tool_import_count": 2,
                },
                {
                    "tool_path": "tools/run_beta.py",
                    "proposed_package": "product",
                    "target_path": "tools/product/run_beta.py",
                    "target_module_exists": False,
                    "has_non_target_canonical_module": False,
                    "review_lane": "lane_b_low_test_reference",
                    "test_reference_count": 1,
                    "tool_reference_count": 0,
                    "internal_tool_import_count": 2,
                },
            ],
        },
        selection_limit=1,
    )

    summary = payload["summary"]
    assert summary["status"] == "tools_package_batch3_lane_decomposition_plan_ready"
    assert summary["candidate_count"] == 2
    assert summary["lane_b_target_move_candidate_count"] == 2
    assert summary["selected_for_next_slice_count"] == 1
    assert payload["rows"][0]["selected_for_next_slice"] is True
    assert payload["rows"][1]["selected_for_next_slice"] is False


def test_batch3_lane_decomposition_separates_existing_canonical_and_classification_rows() -> None:
    payload = mod.build_tools_package_batch3_lane_decomposition_plan(
        batch3_plan_packet={
            "summary": {"status": "tools_package_batch3_review_plan_ready"},
            "rows": [
                {
                    "tool_path": "tools/already_moved.py",
                    "proposed_package": "product",
                    "target_path": "tools/product/already_moved.py",
                    "target_module_exists": True,
                    "has_non_target_canonical_module": False,
                    "review_lane": "lane_b_low_test_reference",
                },
                {
                    "tool_path": "tools/canonical_accounting.py",
                    "proposed_package": "product",
                    "target_path": "tools/product/canonical_accounting.py",
                    "target_module_exists": False,
                    "has_non_target_canonical_module": True,
                    "review_lane": "lane_c_internal_import_heavy",
                },
                {
                    "tool_path": "tools/unclassified.py",
                    "proposed_package": "other_review",
                    "target_path": "",
                    "target_module_exists": False,
                    "has_non_target_canonical_module": False,
                    "review_lane": "lane_d_high_reference_manual",
                },
                {
                    "tool_path": "tools/reclassified_wrapper.py",
                    "proposed_package": "other_review",
                    "target_path": "tools/product/reclassified_wrapper.py",
                    "target_module_exists": True,
                    "canonical_module_exists": True,
                    "canonical_module_path": "tools/product/reclassified_wrapper.py",
                    "has_non_target_canonical_module": False,
                    "review_lane": "lane_b_low_test_reference",
                },
                {
                    "tool_path": "tools/heavy.py",
                    "proposed_package": "wetlab",
                    "target_path": "tools/wetlab/heavy.py",
                    "target_module_exists": False,
                    "has_non_target_canonical_module": False,
                    "review_lane": "lane_d_high_reference_manual",
                },
            ],
        }
    )

    counts = payload["summary"]["decomposition_lane_counts"]
    assert counts["existing_target_wrapper_verification"] == 2
    assert counts["canonical_owner_review"] == 1
    assert counts["package_classification_required"] == 1
    assert counts["lane_d_manual_migration_review"] == 1
    assert payload["summary"]["selected_for_next_slice_count"] == 0
