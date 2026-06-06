from __future__ import annotations

import json
from pathlib import Path

from tools import build_tools_package_batch2_manual_review_plan as mod


def _work_order() -> dict:
    return {
        "summary": {
            "status": "tools_package_separation_work_order_ready",
            "reference_counts_included": True,
            "tool_file_count": 4,
        },
        "rows": [
            {
                "tool_path": "tools/build_wetlab_alpha.py",
                "proposed_package": "wetlab",
                "migration_batch": "batch_2_review",
                "risk_score": 2,
                "tool_reference_count": 0,
                "test_reference_count": 0,
                "internal_tool_import_count": 1,
            },
            {
                "tool_path": "tools/build_product_beta.py",
                "proposed_package": "product",
                "migration_batch": "batch_2_review",
                "risk_score": 3,
                "tool_reference_count": 1,
                "test_reference_count": 1,
                "internal_tool_import_count": 0,
            },
            {
                "tool_path": "tools/build_other_gamma.py",
                "proposed_package": "other_review",
                "migration_batch": "batch_2_review",
                "risk_score": 2,
                "tool_reference_count": 1,
                "test_reference_count": 0,
                "internal_tool_import_count": 0,
            },
            {
                "tool_path": "tools/build_product_delta.py",
                "proposed_package": "product",
                "migration_batch": "batch_2_review",
                "risk_score": 2,
                "tool_reference_count": 0,
                "test_reference_count": 0,
                "internal_tool_import_count": 0,
            },
        ],
    }


def _write_fixture(root: Path) -> None:
    (root / "tools").mkdir()
    (root / "tests" / "unit").mkdir(parents=True)
    for name in ["build_wetlab_alpha.py", "build_product_beta.py", "build_other_gamma.py", "build_product_delta.py"]:
        (root / "tools" / name).write_text("def main():\n    return 0\n", encoding="utf-8")
    (root / "tools" / "wetlab_driver.py").write_text("from tools import build_wetlab_alpha\n", encoding="utf-8")
    (root / "tools" / "product_runner.py").write_text('cmd = "python3 tools/build_product_beta.py"\n', encoding="utf-8")
    (root / "tests" / "unit" / "test_beta.py").write_text("from tools import build_product_beta as mod\n", encoding="utf-8")


def test_batch2_manual_review_plan_selects_exact_reference_bearing_target_rows(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    _write_fixture(tmp_path)

    payload = mod.build_tools_package_batch2_manual_review_plan(work_order_packet=_work_order(), limit=10)
    summary = payload["summary"]
    rows = {row["tool_path"]: row for row in payload["rows"]}

    assert summary["status"] == "tools_package_batch2_manual_review_plan_ready"
    assert summary["batch2_total_count"] == 4
    assert summary["batch2_target_package_count"] == 3
    assert summary["batch2_reference_bearing_target_count"] == 2
    assert summary["selected_count"] == 2
    assert rows["tools/build_wetlab_alpha.py"]["manual_lane"] == "single_reference_class_rewrite_review"
    assert rows["tools/build_wetlab_alpha.py"]["reference_locations"] == "tools/wetlab_driver.py:1"
    assert rows["tools/build_wetlab_alpha.py"]["source_has_main"] is True
    assert rows["tools/build_wetlab_alpha.py"]["compatibility_wrapper_strategy"] == "cli_main_passthrough_wrapper"
    assert rows["tools/build_product_beta.py"]["manual_lane"] == "mixed_reference_rewrite_review"
    assert rows["tools/build_product_beta.py"]["exact_reference_count"] == 2
    assert summary["selected_source_has_main_count"] == 2
    assert summary["selected_import_only_wrapper_count"] == 0
    assert summary["move_executed"] is False
    assert summary["external_state_mutated"] is False


def test_batch2_manual_review_plan_blocks_without_exact_reference_locations(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    (tmp_path / "tools").mkdir()
    (tmp_path / "tests" / "unit").mkdir(parents=True)
    (tmp_path / "tools" / "run_alpha.py").write_text("def main():\n    return 0\n", encoding="utf-8")
    (tmp_path / "tests" / "unit" / "test_alpha_current.py").write_text(
        "from tools import run_alpha_current as mod\n",
        encoding="utf-8",
    )
    packet = {
        "summary": {
            "status": "tools_package_separation_work_order_ready",
            "reference_counts_included": True,
            "tool_file_count": 1,
        },
        "rows": [
            {
                "tool_path": "tools/run_alpha.py",
                "proposed_package": "product",
                "migration_batch": "batch_2_review",
                "risk_score": 2,
                "tool_reference_count": 0,
                "test_reference_count": 1,
                "internal_tool_import_count": 0,
            }
        ],
    }

    payload = mod.build_tools_package_batch2_manual_review_plan(work_order_packet=packet, limit=1)

    assert payload["summary"]["status"] == "blocked_tools_package_batch2_manual_review_plan"
    assert "no_batch2_manual_review_candidates_with_exact_references" in payload["summary"]["blockers"]
    assert payload["summary"]["skipped_missing_reference_candidate_count"] == 1
    assert payload["rows"] == []


def test_batch2_manual_review_plan_records_internal_import_self_references(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    (tmp_path / "tools").mkdir()
    (tmp_path / "tests" / "unit").mkdir(parents=True)
    (tmp_path / "tools" / "cleanup_alpha.py").write_text(
        "from __future__ import annotations\n\n"
        "from tools.builder_table_utils import write_csv_rows\n\n"
        "VALUE = write_csv_rows\n",
        encoding="utf-8",
    )
    packet = {
        "summary": {
            "status": "tools_package_separation_work_order_ready",
            "reference_counts_included": True,
            "tool_file_count": 1,
        },
        "rows": [
            {
                "tool_path": "tools/cleanup_alpha.py",
                "proposed_package": "cleanup",
                "migration_batch": "batch_2_review",
                "risk_score": 2,
                "tool_reference_count": 0,
                "test_reference_count": 0,
                "internal_tool_import_count": 1,
            }
        ],
    }

    payload = mod.build_tools_package_batch2_manual_review_plan(work_order_packet=packet, limit=1)

    assert payload["summary"]["status"] == "tools_package_batch2_manual_review_plan_ready"
    assert payload["summary"]["selected_count"] == 1
    assert payload["summary"]["skipped_missing_reference_candidate_count"] == 0
    assert payload["rows"][0]["reference_class"] == "internal_import_reference"
    assert payload["rows"][0]["reference_locations"] == "tools/cleanup_alpha.py:3"
    assert payload["rows"][0]["first_reference_excerpt"] == "from tools.builder_table_utils import write_csv_rows"


def test_batch2_manual_review_plan_skips_existing_target_module(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    (tmp_path / "tools" / "wetlab").mkdir(parents=True)
    (tmp_path / "tests" / "unit").mkdir(parents=True)
    (tmp_path / "tools" / "wetlab_helper.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / "tools" / "wetlab" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "tools" / "wetlab" / "wetlab_helper.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / "tools" / "driver.py").write_text("from tools import wetlab_helper\n", encoding="utf-8")
    packet = {
        "summary": {
            "status": "tools_package_separation_work_order_ready",
            "reference_counts_included": True,
            "tool_file_count": 1,
        },
        "rows": [
            {
                "tool_path": "tools/wetlab_helper.py",
                "proposed_package": "wetlab",
                "migration_batch": "batch_2_review",
                "risk_score": 2,
                "tool_reference_count": 0,
                "test_reference_count": 0,
                "internal_tool_import_count": 1,
            }
        ],
    }

    payload = mod.build_tools_package_batch2_manual_review_plan(work_order_packet=packet, limit=1)

    assert payload["summary"]["status"] == "blocked_tools_package_batch2_manual_review_plan"
    assert payload["summary"]["batch2_reference_bearing_target_count"] == 1
    assert payload["summary"]["batch2_unmigrated_reference_bearing_target_count"] == 0
    assert payload["summary"]["skipped_existing_target_candidate_count"] == 1
    assert payload["rows"] == []


def test_batch2_manual_review_plan_tool_writes_outputs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    _write_fixture(tmp_path)
    work_order_json = tmp_path / "work_order.json"
    out_json = tmp_path / "manual_plan.json"
    out_csv = tmp_path / "manual_plan.csv"
    out_md = tmp_path / "manual_plan.md"
    work_order_json.write_text(json.dumps(_work_order()) + "\n", encoding="utf-8")

    mod.main(["--work-order-json", str(work_order_json), "--out-json", str(out_json), "--out-csv", str(out_csv), "--out-md", str(out_md)])

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "tools_package_batch2_manual_review_plan_ready"
    assert out_csv.read_text(encoding="utf-8").startswith("sequence,tool_path,")
    assert "Tools Package Batch2 Manual Review Plan" in out_md.read_text(encoding="utf-8")
