from __future__ import annotations

import json
from pathlib import Path

from tools import build_tools_package_migration_plan as mod


def _work_order(*, reference_counts_included: bool = True) -> dict:
    return {
        "summary": {
            "status": "tools_package_separation_work_order_ready",
            "reference_counts_included": reference_counts_included,
            "tool_file_count": 3,
        },
        "rows": [
            {
                "tool_path": "tools/build_product_alpha.py",
                "proposed_package": "product",
                "matched_keyword": "product",
                "migration_batch": "batch_1_low_reference",
                "risk_score": 0,
                "test_reference_count": 0,
                "tool_reference_count": 0,
                "internal_tool_import_count": 0,
                "has_argparse_cli": True,
            },
            {
                "tool_path": "tools/build_cameo_beta.py",
                "proposed_package": "cameo",
                "matched_keyword": "cameo",
                "migration_batch": "batch_2_review",
                "risk_score": 1,
                "test_reference_count": 1,
                "tool_reference_count": 0,
                "internal_tool_import_count": 0,
                "has_argparse_cli": True,
            },
            {
                "tool_path": "tools/build_unknown.py",
                "proposed_package": "other_review",
                "matched_keyword": "no_keyword_match",
                "migration_batch": "batch_2_review",
                "risk_score": 2,
                "test_reference_count": 0,
                "tool_reference_count": 0,
                "internal_tool_import_count": 0,
                "has_argparse_cli": False,
            },
        ],
    }


def test_tools_package_migration_plan_requires_reference_counts() -> None:
    payload = mod.build_tools_package_migration_plan(
        work_order_packet=_work_order(reference_counts_included=False),
        limit=10,
    )
    summary = payload["summary"]

    assert summary["status"] == "blocked_tools_package_migration_plan"
    assert "reference_counts_not_included" in summary["blockers"]
    assert summary["move_executed"] is False
    assert summary["import_rewrite_executed"] is False
    assert summary["external_state_mutated"] is False


def test_tools_package_migration_plan_selects_low_reference_batch_only() -> None:
    payload = mod.build_tools_package_migration_plan(work_order_packet=_work_order(), limit=10)
    summary = payload["summary"]
    row = payload["rows"][0]

    assert summary["status"] == "tools_package_migration_plan_ready"
    assert summary["candidate_pool_count"] == 1
    assert summary["selected_count"] == 1
    assert summary["selected_package_counts"] == {"product": 1}
    assert row["source_path"] == "tools/build_product_alpha.py"
    assert row["target_path"] == "tools/product/build_product_alpha.py"
    assert row["import_rewrite_hint"] == "tools.build_product_alpha -> tools.product.build_product_alpha"
    assert row["move_executed"] is False


def test_tools_package_migration_plan_tool_writes_outputs(tmp_path: Path) -> None:
    work_order_json = tmp_path / "work_order.json"
    out_json = tmp_path / "plan.json"
    out_csv = tmp_path / "plan.csv"
    out_md = tmp_path / "plan.md"
    work_order_json.write_text(json.dumps(_work_order()) + "\n", encoding="utf-8")

    mod.main(
        [
            "--work-order-json",
            str(work_order_json),
            "--limit",
            "1",
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "tools_package_migration_plan_ready"
    assert out_csv.read_text(encoding="utf-8").startswith("sequence,source_path,")
    assert "Tools Package Migration Plan" in out_md.read_text(encoding="utf-8")
