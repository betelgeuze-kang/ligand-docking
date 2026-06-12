from __future__ import annotations

import json
from pathlib import Path

from tools import build_tools_package_migration_receipt as mod


def _plan() -> dict:
    return {
        "summary": {"status": "tools_package_migration_plan_ready"},
        "rows": [
            {
                "source_path": "tools/build_product_alpha.py",
                "target_path": "tools/product/build_product_alpha.py",
                "proposed_package": "product",
            }
        ],
    }


def _import_only_plan() -> dict:
    return {
        "summary": {"status": "tools_package_migration_plan_ready"},
        "rows": [
            {
                "source_path": "tools/wetlab_helpers.py",
                "target_path": "tools/wetlab/wetlab_helpers.py",
                "proposed_package": "wetlab",
            }
        ],
    }


def _write_fixture(root: Path) -> None:
    package_dir = root / "tools" / "product"
    package_dir.mkdir(parents=True)
    (root / "tools" / "__init__.py").write_text("", encoding="utf-8")
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    (package_dir / "build_product_alpha.py").write_text("def main():\n    return 0\n", encoding="utf-8")
    (root / "tools" / "build_product_alpha.py").write_text(
        "from tools.product.build_product_alpha import *  # noqa: F401,F403\n"
        "from tools.product.build_product_alpha import main as _main\n",
        encoding="utf-8",
    )


def _write_import_only_fixture(root: Path) -> None:
    package_dir = root / "tools" / "wetlab"
    package_dir.mkdir(parents=True)
    (root / "tools" / "__init__.py").write_text("", encoding="utf-8")
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    (package_dir / "wetlab_helpers.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "tools" / "wetlab_helpers.py").write_text(
        "from tools.wetlab.wetlab_helpers import *  # noqa: F401,F403\n",
        encoding="utf-8",
    )


def test_tools_package_migration_receipt_verifies_wrapped_move(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    _write_fixture(tmp_path)

    payload = mod.build_tools_package_migration_receipt(plan_packet=_plan())
    summary = payload["summary"]
    row = payload["rows"][0]

    assert summary["status"] == "tools_package_migration_receipt_ready"
    assert summary["verified_migration_count"] == 1
    assert summary["move_executed"] is True
    assert summary["compatibility_wrapper_retained"] is True
    assert summary["external_state_mutated"] is False
    assert row["wrapper_imports_target"] is True
    assert row["target_module_py_compile_ok"] is True


def test_tools_package_migration_receipt_allows_import_only_helpers(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    _write_import_only_fixture(tmp_path)

    payload = mod.build_tools_package_migration_receipt(plan_packet=_import_only_plan())
    summary = payload["summary"]
    row = payload["rows"][0]

    assert summary["status"] == "tools_package_migration_receipt_ready"
    assert row["wrapper_imports_target"] is True
    assert row["wrapper_main_passthrough_required"] is False
    assert row["wrapper_main_passthrough"] is False


def test_tools_package_migration_receipt_blocks_missing_target(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "tools" / "build_product_alpha.py").write_text("# wrapper without target\n", encoding="utf-8")

    payload = mod.build_tools_package_migration_receipt(plan_packet=_plan())
    blockers = set(payload["summary"]["blockers"])

    assert payload["summary"]["status"] == "blocked_tools_package_migration_receipt"
    assert "target_module_missing" in blockers
    assert "package_init_missing" in blockers
    assert "wrapper_import_missing" in blockers


def test_tools_package_migration_receipt_tool_writes_outputs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    _write_fixture(tmp_path)
    plan_json = tmp_path / "plan.json"
    out_json = tmp_path / "receipt.json"
    out_csv = tmp_path / "receipt.csv"
    out_md = tmp_path / "receipt.md"
    plan_json.write_text(json.dumps(_plan()) + "\n", encoding="utf-8")

    mod.main(["--plan-json", str(plan_json), "--out-json", str(out_json), "--out-csv", str(out_csv), "--out-md", str(out_md)])

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "tools_package_migration_receipt_ready"
    assert out_csv.read_text(encoding="utf-8").startswith("source_path,target_path,")
    assert "Tools Package Migration Receipt" in out_md.read_text(encoding="utf-8")
