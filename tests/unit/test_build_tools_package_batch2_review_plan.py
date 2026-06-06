from __future__ import annotations

import json
from pathlib import Path

from tools import build_tools_package_batch2_review_plan as mod


def _work_order() -> dict:
    return {
        "summary": {
            "status": "tools_package_separation_work_order_ready",
            "reference_counts_included": True,
            "tool_file_count": 3,
        },
        "rows": [
            {
                "tool_path": "tools/build_product_alpha.py",
                "proposed_package": "product",
                "migration_batch": "batch_2_review",
                "risk_score": 1,
                "tool_reference_count": 0,
                "test_reference_count": 1,
                "internal_tool_import_count": 0,
            },
            {
                "tool_path": "tools/build_cameo_beta.py",
                "proposed_package": "cameo",
                "migration_batch": "batch_2_review",
                "risk_score": 1,
                "tool_reference_count": 1,
                "test_reference_count": 0,
                "internal_tool_import_count": 0,
            },
            {
                "tool_path": "tools/build_unknown.py",
                "proposed_package": "other_review",
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
    (root / "tools" / "build_product_alpha.py").write_text("def main():\n    return 0\n", encoding="utf-8")
    (root / "tools" / "build_cameo_beta.py").write_text("def main():\n    return 0\n", encoding="utf-8")
    (root / "tools" / "runner.py").write_text('cmd = "tools/build_cameo_beta.py"\n', encoding="utf-8")
    (root / "tests" / "unit" / "test_alpha.py").write_text("python3 tools/build_product_alpha.py\n", encoding="utf-8")


def test_tools_package_batch2_review_plan_selects_first_slice(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    _write_fixture(tmp_path)

    payload = mod.build_tools_package_batch2_review_plan(work_order_packet=_work_order(), limit=10)
    summary = payload["summary"]
    rows = {row["tool_path"]: row for row in payload["rows"]}

    assert summary["status"] == "tools_package_batch2_review_plan_ready"
    assert summary["batch2_total_count"] == 3
    assert summary["batch2_target_package_count"] == 2
    assert summary["first_slice_candidate_count"] == 2
    assert summary["selected_count"] == 2
    assert rows["tools/build_product_alpha.py"]["reference_class"] == "test_only_reference"
    assert rows["tools/build_product_alpha.py"]["reference_locations"] == "tests/unit/test_alpha.py:1"
    assert rows["tools/build_cameo_beta.py"]["reference_class"] == "tool_string_reference"
    assert rows["tools/build_cameo_beta.py"]["reference_locations"] == "tools/runner.py:1"
    assert summary["move_executed"] is False
    assert summary["external_state_mutated"] is False


def test_tools_package_batch2_review_plan_does_not_match_module_prefix(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    (tmp_path / "tools").mkdir()
    (tmp_path / "tests" / "unit").mkdir(parents=True)
    (tmp_path / "tools" / "run_alpha.py").write_text("def main():\n    return 0\n", encoding="utf-8")
    (tmp_path / "tests" / "unit" / "test_alpha_current.py").write_text(
        "from tools import run_alpha_current as mod\n"
        'cmd = "python3 tools/run_alpha_current.py"\n',
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
                "risk_score": 1,
                "tool_reference_count": 0,
                "test_reference_count": 1,
                "internal_tool_import_count": 0,
            }
        ],
    }

    payload = mod.build_tools_package_batch2_review_plan(work_order_packet=packet, limit=1)

    assert payload["summary"]["status"] == "blocked_tools_package_batch2_review_plan"
    assert "no_batch2_first_slice_candidates_with_exact_references" in payload["summary"]["blockers"]
    assert payload["summary"]["skipped_missing_reference_candidate_count"] == 1
    assert payload["rows"] == []


def test_tools_package_batch2_review_plan_does_not_match_test_filename_prefix(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    (tmp_path / "tools").mkdir()
    (tmp_path / "tests" / "unit").mkdir(parents=True)
    (tmp_path / "tools" / "build_alpha.py").write_text("def main():\n    return 0\n", encoding="utf-8")
    (tmp_path / "tests" / "unit" / "test_build_alpha.py").write_text(
        "# test file path should not be counted as a script reference\n",
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
                "tool_path": "tools/build_alpha.py",
                "proposed_package": "product",
                "migration_batch": "batch_2_review",
                "risk_score": 1,
                "tool_reference_count": 0,
                "test_reference_count": 1,
                "internal_tool_import_count": 0,
            }
        ],
    }

    payload = mod.build_tools_package_batch2_review_plan(work_order_packet=packet, limit=1)

    assert payload["summary"]["status"] == "blocked_tools_package_batch2_review_plan"
    assert payload["summary"]["selected_count"] == 0
    assert payload["summary"]["skipped_missing_reference_candidate_count"] == 1
    assert payload["rows"] == []


def test_tools_package_batch2_review_plan_skips_existing_target_module(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    (tmp_path / "tools" / "product").mkdir(parents=True)
    (tmp_path / "tests" / "unit").mkdir(parents=True)
    (tmp_path / "tools" / "build_alpha.py").write_text("def main():\n    return 0\n", encoding="utf-8")
    (tmp_path / "tools" / "product" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "tools" / "product" / "build_alpha.py").write_text("def main():\n    return 0\n", encoding="utf-8")
    (tmp_path / "tests" / "unit" / "test_alpha.py").write_text("python3 tools/build_alpha.py\n", encoding="utf-8")
    packet = {
        "summary": {
            "status": "tools_package_separation_work_order_ready",
            "reference_counts_included": True,
            "tool_file_count": 1,
        },
        "rows": [
            {
                "tool_path": "tools/build_alpha.py",
                "proposed_package": "product",
                "migration_batch": "batch_2_review",
                "risk_score": 1,
                "tool_reference_count": 0,
                "test_reference_count": 1,
                "internal_tool_import_count": 0,
            }
        ],
    }

    payload = mod.build_tools_package_batch2_review_plan(work_order_packet=packet, limit=1)

    assert payload["summary"]["status"] == "blocked_tools_package_batch2_review_plan"
    assert payload["summary"]["first_slice_raw_candidate_count"] == 1
    assert payload["summary"]["first_slice_candidate_count"] == 0
    assert payload["summary"]["skipped_existing_target_candidate_count"] == 1
    assert payload["rows"] == []


def test_tools_package_batch2_review_plan_blocks_without_reference_counts() -> None:
    packet = _work_order()
    packet["summary"]["reference_counts_included"] = False
    payload = mod.build_tools_package_batch2_review_plan(work_order_packet=packet)

    assert payload["summary"]["status"] == "blocked_tools_package_batch2_review_plan"
    assert "reference_counts_not_included" in payload["summary"]["blockers"]


def test_tools_package_batch2_review_plan_tool_writes_outputs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    _write_fixture(tmp_path)
    work_order_json = tmp_path / "work_order.json"
    out_json = tmp_path / "plan.json"
    out_csv = tmp_path / "plan.csv"
    out_md = tmp_path / "plan.md"
    work_order_json.write_text(json.dumps(_work_order()) + "\n", encoding="utf-8")

    mod.main(["--work-order-json", str(work_order_json), "--out-json", str(out_json), "--out-csv", str(out_csv), "--out-md", str(out_md)])

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "tools_package_batch2_review_plan_ready"
    assert out_csv.read_text(encoding="utf-8").startswith("sequence,tool_path,")
    assert "Tools Package Batch2 Review Plan" in out_md.read_text(encoding="utf-8")
