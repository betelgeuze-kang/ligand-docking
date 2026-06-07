from __future__ import annotations

from tools import build_tools_package_other_review_classification_plan as mod


def test_other_review_classification_plan_ready() -> None:
    payload = mod.build_tools_package_other_review_classification_plan(
        work_order_packet={
            "rows": [
                {
                    "tool_path": "tools/build_product_alpha.py",
                    "proposed_package": "other_review",
                    "migration_batch": "batch_2_review",
                    "risk_score": 2,
                },
                {
                    "tool_path": "tools/run_cameo_smoke.py",
                    "proposed_package": "other_review",
                    "migration_batch": "batch_2_review",
                    "risk_score": 2,
                },
            ]
        }
    )
    summary = payload["summary"]
    assert summary["status"] == "tools_package_other_review_classification_plan_ready"
    assert summary["unclassified_count"] == 0
    assert summary["candidate_count"] == 2
