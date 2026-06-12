from __future__ import annotations

import pytest

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


def test_other_review_classification_uses_manual_decision_map() -> None:
    payload = mod.build_tools_package_other_review_classification_plan(
        work_order_packet={
            "rows": [
                {
                    "tool_path": "tools/render_readme_molecular_figures.py",
                    "proposed_package": "other_review",
                    "migration_batch": "batch_2_review",
                    "risk_score": 3,
                },
                {
                    "tool_path": "tools/builder_json_utils.py",
                    "proposed_package": "other_review",
                    "migration_batch": "batch_2_review",
                    "risk_score": 3,
                },
                {
                    "tool_path": "tools/audit_ligand_leakage.py",
                    "proposed_package": "other_review",
                    "migration_batch": "batch_2_review",
                    "risk_score": 3,
                },
            ]
        }
    )
    summary = payload["summary"]
    assert summary["status"] == "tools_package_other_review_classification_plan_ready"
    assert summary["unclassified_count"] == 0
    assert summary["manual_decision_count"] == 3
    rows = {row["tool_path"]: row for row in payload["rows"]}
    assert rows["tools/render_readme_molecular_figures.py"]["reclassified_package"] == "wetlab"
    assert rows["tools/builder_json_utils.py"]["reclassified_package"] == "product"
    assert rows["tools/audit_ligand_leakage.py"]["reclassification_keyword"] == (
        "manual_decision:ligand_product_data_leakage_audit"
    )


def test_other_review_classification_ready_when_no_candidates_remain() -> None:
    payload = mod.build_tools_package_other_review_classification_plan(
        work_order_packet={
            "rows": [
                {
                    "tool_path": "tools/product/already_moved.py",
                    "proposed_package": "product",
                    "migration_batch": "batch_2_review",
                    "risk_score": 2,
                }
            ]
        }
    )

    summary = payload["summary"]
    assert summary["status"] == "tools_package_other_review_classification_plan_ready"
    assert summary["plan_ready"] is True
    assert summary["candidate_count"] == 0
    assert summary["unclassified_count"] == 0


@pytest.mark.parametrize(
    ("tool_path", "expected_package"),
    [
        ("tools/__init__.py", "canonical_owner_review"),
        ("tools/speed_profile.py", "product"),
        ("tools/speed_profile_defaults.py", "product"),
        ("tools/sweep_claim_input_profiles.py", "product"),
        ("tools/visualize_experiment_dashboard.py", "product"),
    ],
)
def test_other_review_classification_covers_current_manual_residuals(
    tool_path: str,
    expected_package: str,
) -> None:
    payload = mod.build_tools_package_other_review_classification_plan(
        work_order_packet={
            "rows": [
                {
                    "tool_path": tool_path,
                    "proposed_package": "other_review",
                    "migration_batch": "batch_2_review",
                    "risk_score": 2,
                }
            ]
        }
    )

    summary = payload["summary"]
    row = payload["rows"][0]
    assert summary["status"] == "tools_package_other_review_classification_plan_ready"
    assert summary["unclassified_count"] == 0
    assert row["reclassified_package"] == expected_package
