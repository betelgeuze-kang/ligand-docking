from __future__ import annotations

import json
from pathlib import Path

from tools import build_tools_package_reference_review as mod


def _work_order() -> dict:
    return {
        "summary": {
            "status": "tools_package_separation_work_order_ready",
            "reference_counts_included": True,
        },
        "rows": [
            {
                "tool_path": "tools/build_product_alpha.py",
                "proposed_package": "product",
                "migration_batch": "batch_1_low_reference",
                "risk_score": 0,
                "tool_reference_count": 1,
                "test_reference_count": 0,
                "internal_tool_import_count": 0,
            }
        ],
    }


def test_tools_package_reference_review_resolves_exact_caller(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "build_product_alpha.py").write_text("def main():\n    return 0\n", encoding="utf-8")
    (tmp_path / "tools" / "run_family.py").write_text(
        'cmd = "python3 tools/build_product_alpha.py --flag"\n',
        encoding="utf-8",
    )

    payload = mod.build_tools_package_reference_review(work_order_packet=_work_order())
    summary = payload["summary"]
    row = payload["rows"][0]

    assert summary["status"] == "tools_package_reference_review_ready"
    assert summary["review_candidate_count"] == 1
    assert summary["exact_reference_resolved_count"] == 1
    assert row["target_path"] == "tools/product/build_product_alpha.py"
    assert row["reference_locations"] == "tools/run_family.py:1"
    assert row["recommended_action"] == "move_with_wrapper_then_rewrite_recorded_callers"
    assert summary["move_executed"] is False
    assert summary["external_state_mutated"] is False


def test_tools_package_reference_review_blocks_without_reference_counts() -> None:
    packet = _work_order()
    packet["summary"]["reference_counts_included"] = False
    payload = mod.build_tools_package_reference_review(work_order_packet=packet)

    assert payload["summary"]["status"] == "blocked_tools_package_reference_review"
    assert "reference_counts_not_included" in payload["summary"]["blockers"]


def test_tools_package_reference_review_tool_writes_outputs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "build_product_alpha.py").write_text("def main():\n    return 0\n", encoding="utf-8")
    (tmp_path / "tools" / "runner.py").write_text('script = "tools/build_product_alpha.py"\n', encoding="utf-8")
    work_order_json = tmp_path / "work_order.json"
    out_json = tmp_path / "review.json"
    out_csv = tmp_path / "review.csv"
    out_md = tmp_path / "review.md"
    work_order_json.write_text(json.dumps(_work_order()) + "\n", encoding="utf-8")

    mod.main(["--work-order-json", str(work_order_json), "--out-json", str(out_json), "--out-csv", str(out_csv), "--out-md", str(out_md)])

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "tools_package_reference_review_ready"
    assert out_csv.read_text(encoding="utf-8").startswith("tool_path,proposed_package,")
    assert "Tools Package Reference Review" in out_md.read_text(encoding="utf-8")
