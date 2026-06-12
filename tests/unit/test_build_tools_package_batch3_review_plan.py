from __future__ import annotations

from pathlib import Path

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
    assert summary["first_slice_raw_candidate_count"] == 1


def test_batch3_review_plan_skips_existing_target_and_canonical_shims(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    (tmp_path / "tools" / "product").mkdir(parents=True)
    (tmp_path / "tools" / "accounting").mkdir(parents=True)
    (tmp_path / "tools" / "product" / "already_moved.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / "tools" / "accounting" / "canonical_report.py").write_text("def main():\n    return 0\n", encoding="utf-8")
    (tmp_path / "tools" / "canonical_report.py").write_text(
        '"""Compatibility shim; canonical module: tools.accounting.canonical_report."""\n'
        "from tools.accounting.canonical_report import *\n",
        encoding="utf-8",
    )

    payload = mod.build_tools_package_batch3_review_plan(
        work_order_packet={
            "rows": [
                {
                    "tool_path": "tools/already_moved.py",
                    "proposed_package": "product",
                    "migration_batch": "batch_3_high_reference",
                    "risk_score": 5,
                    "test_reference_count": 0,
                    "internal_tool_import_count": 3,
                },
                {
                    "tool_path": "tools/canonical_report.py",
                    "proposed_package": "product",
                    "migration_batch": "batch_3_high_reference",
                    "risk_score": 5,
                    "test_reference_count": 0,
                    "internal_tool_import_count": 3,
                },
                {
                    "tool_path": "tools/not_moved.py",
                    "proposed_package": "product",
                    "migration_batch": "batch_3_high_reference",
                    "risk_score": 5,
                    "test_reference_count": 0,
                    "internal_tool_import_count": 3,
                },
            ]
        }
    )
    summary = payload["summary"]
    assert summary["first_slice_raw_candidate_count"] == 3
    assert summary["first_slice_candidate_count"] == 1
    assert summary["skipped_existing_target_candidate_count"] == 1
    assert summary["skipped_existing_canonical_candidate_count"] == 1
    rows = {row["tool_path"]: row for row in payload["rows"]}
    assert rows["tools/already_moved.py"]["selected_for_first_slice"] is False
    assert rows["tools/canonical_report.py"]["selected_for_first_slice"] is False
    assert rows["tools/not_moved.py"]["selected_for_first_slice"] is True


def test_batch3_review_plan_treats_other_review_wrapper_import_as_existing_target(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    (tmp_path / "tools" / "product").mkdir(parents=True)
    (tmp_path / "tools" / "product" / "ab_test_ai_hip_graph.py").write_text(
        "def main():\n    return 0\n",
        encoding="utf-8",
    )
    (tmp_path / "tools" / "product" / "builder_json_utils.py").write_text(
        "VALUE = 1\n",
        encoding="utf-8",
    )
    (tmp_path / "tools" / "ab_test_ai_hip_graph.py").write_text(
        "from tools.product.ab_test_ai_hip_graph import *  # noqa: F401,F403\n"
        "from tools.product.ab_test_ai_hip_graph import main as _main\n",
        encoding="utf-8",
    )
    (tmp_path / "tools" / "builder_json_utils.py").write_text(
        "from tools.product.builder_json_utils import *  # noqa: F401,F403\n",
        encoding="utf-8",
    )

    payload = mod.build_tools_package_batch3_review_plan(
        work_order_packet={
            "rows": [
                {
                    "tool_path": "tools/ab_test_ai_hip_graph.py",
                    "proposed_package": "other_review",
                    "migration_batch": "batch_3_high_reference",
                    "risk_score": 5,
                    "test_reference_count": 0,
                    "internal_tool_import_count": 2,
                },
                {
                    "tool_path": "tools/builder_json_utils.py",
                    "proposed_package": "other_review",
                    "migration_batch": "batch_3_high_reference",
                    "risk_score": 5,
                    "test_reference_count": 0,
                    "internal_tool_import_count": 2,
                },
            ]
        }
    )

    summary = payload["summary"]
    rows = {row["tool_path"]: row for row in payload["rows"]}
    row = rows["tools/ab_test_ai_hip_graph.py"]
    helper_row = rows["tools/builder_json_utils.py"]
    assert summary["first_slice_raw_candidate_count"] == 2
    assert summary["first_slice_candidate_count"] == 0
    assert summary["skipped_existing_target_candidate_count"] == 2
    assert summary["skipped_unclassified_candidate_count"] == 0
    assert row["target_path"] == "tools/product/ab_test_ai_hip_graph.py"
    assert row["target_module_exists"] is True
    assert row["selected_for_first_slice"] is False
    assert helper_row["target_path"] == "tools/product/builder_json_utils.py"
    assert helper_row["target_module_exists"] is True
    assert helper_row["selected_for_first_slice"] is False
