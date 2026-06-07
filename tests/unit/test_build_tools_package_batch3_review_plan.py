from __future__ import annotations

from tools import build_tools_package_batch3_review_plan as mod


def test_batch3_review_plan_ready() -> None:
    payload = mod.build_tools_package_batch3_review_plan(
        work_order_packet={
            "rows": [
                {
                    "tool_path": "tools/build_accounting_report.py",
                    "proposed_package": "product",
                    "migration_batch": "batch_3_high_reference",
                    "risk_score": 5,
                    "test_reference_count": 0,
                    "internal_tool_import_count": 0,
                }
            ]
        }
    )
    summary = payload["summary"]
    assert summary["status"] == "tools_package_batch3_review_plan_ready"
    assert summary["batch3_total_count"] == 1
    assert summary["first_slice_candidate_count"] == 1
