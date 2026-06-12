from __future__ import annotations

from pathlib import Path

from tools import build_tools_package_batch3_migration_receipt as mod


def _plan() -> dict:
    return {
        "summary": {"status": "tools_package_batch3_review_plan_ready"},
        "rows": [
            {
                "tool_path": "tools/run_alpha.py",
                "target_path": "tools/product/run_alpha.py",
                "proposed_package": "product",
                "review_lane": "lane_a_zero_test_low_internal",
                "selected_for_first_slice": True,
            }
        ],
    }


def _write_fixture(root: Path) -> None:
    package_dir = root / "tools" / "product"
    package_dir.mkdir(parents=True)
    (root / "tools" / "__init__.py").write_text("", encoding="utf-8")
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    (package_dir / "run_alpha.py").write_text("def main():\n    return 0\n", encoding="utf-8")
    (root / "tools" / "run_alpha.py").write_text(
        "from tools.product.run_alpha import *  # noqa: F401,F403\n"
        "from tools.product.run_alpha import main as _main\n",
        encoding="utf-8",
    )


def test_batch3_migration_receipt_verifies_selected_lane_a_move(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    _write_fixture(tmp_path)

    payload = mod.build_tools_package_batch3_migration_receipt(batch3_plan_packet=_plan())

    assert payload["summary"]["status"] == "tools_package_batch3_migration_receipt_ready"
    assert payload["summary"]["plan_selected_count"] == 1
    assert payload["summary"]["verified_migration_count"] == 1
    assert payload["summary"]["blocked_migration_count"] == 0
    assert payload["summary"]["compatibility_wrapper_retained"] is True
    assert payload["rows"][0]["wrapper_main_passthrough_required"] is True
