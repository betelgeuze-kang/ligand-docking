from __future__ import annotations

import json
from pathlib import Path

from tools import build_tools_package_batch2_migration_receipt as mod


def _plan() -> dict:
    return {
        "summary": {"status": "tools_package_batch2_review_plan_ready"},
        "rows": [
            {
                "tool_path": "tools/build_casp17_alpha.py",
                "target_path": "tools/casp17/build_casp17_alpha.py",
                "proposed_package": "casp17",
                "reference_class": "test_only_reference",
                "reference_locations": "tests/unit/test_alpha.py:1",
            }
        ],
    }


def _import_only_plan() -> dict:
    return {
        "summary": {"status": "tools_package_batch2_manual_review_plan_ready"},
        "rows": [
            {
                "tool_path": "tools/wetlab_helpers.py",
                "target_path": "tools/wetlab/wetlab_helpers.py",
                "proposed_package": "wetlab",
                "reference_class": "tool_string_reference",
                "compatibility_wrapper_strategy": "import_only_compatibility_wrapper",
                "reference_locations": "tools/driver.py:1",
            }
        ],
    }


def _intra_slice_plan() -> dict:
    return {
        "summary": {"status": "tools_package_batch2_manual_review_plan_ready"},
        "rows": [
            {
                "tool_path": "tools/build_alpha.py",
                "target_path": "tools/product/build_alpha.py",
                "proposed_package": "product",
                "reference_class": "mixed_references",
                "compatibility_wrapper_strategy": "cli_main_passthrough_wrapper",
                "reference_locations": "tests/unit/test_alpha.py:1",
            },
            {
                "tool_path": "tools/build_beta.py",
                "target_path": "tools/product/build_beta.py",
                "proposed_package": "product",
                "reference_class": "mixed_references",
                "compatibility_wrapper_strategy": "cli_main_passthrough_wrapper",
                "reference_locations": "tools/build_alpha.py:3",
            },
        ],
    }


def _internal_import_plan() -> dict:
    return {
        "summary": {"status": "tools_package_batch2_manual_review_plan_ready"},
        "rows": [
            {
                "tool_path": "tools/cleanup_alpha.py",
                "target_path": "tools/cleanup/cleanup_alpha.py",
                "proposed_package": "cleanup",
                "reference_class": "internal_import_reference",
                "compatibility_wrapper_strategy": "import_only_compatibility_wrapper",
                "reference_locations": "tools/cleanup_alpha.py:3",
            }
        ],
    }


def _write_fixture(root: Path, *, stale: bool = False) -> None:
    package_dir = root / "tools" / "casp17"
    package_dir.mkdir(parents=True)
    (root / "tools" / "__init__.py").write_text("", encoding="utf-8")
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    (package_dir / "build_casp17_alpha.py").write_text("def main():\n    return 0\n", encoding="utf-8")
    (root / "tools" / "build_casp17_alpha.py").write_text(
        "from tools.casp17.build_casp17_alpha import *  # noqa: F401,F403\n"
        "from tools.casp17.build_casp17_alpha import main as _main\n",
        encoding="utf-8",
    )
    (root / "tests" / "unit").mkdir(parents=True)
    import_line = (
        "from tools import build_casp17_alpha as mod\n"
        if stale
        else "from tools.casp17 import build_casp17_alpha as mod\n"
    )
    (root / "tests" / "unit" / "test_alpha.py").write_text(import_line, encoding="utf-8")


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
    (root / "tools" / "driver.py").write_text('cmd = "python3 tools/wetlab/wetlab_helpers.py"\n', encoding="utf-8")


def _write_intra_slice_fixture(root: Path) -> None:
    package_dir = root / "tools" / "product"
    package_dir.mkdir(parents=True)
    (root / "tools" / "__init__.py").write_text("", encoding="utf-8")
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    (package_dir / "build_alpha.py").write_text(
        "def main():\n"
        "    return 0\n"
        'BETA = "tools/product/build_beta.py"\n',
        encoding="utf-8",
    )
    (package_dir / "build_beta.py").write_text("def main():\n    return 0\n", encoding="utf-8")
    (root / "tools" / "build_alpha.py").write_text(
        "from tools.product.build_alpha import *  # noqa: F401,F403\n"
        "from tools.product.build_alpha import main as _main\n",
        encoding="utf-8",
    )
    (root / "tools" / "build_beta.py").write_text(
        "from tools.product.build_beta import *  # noqa: F401,F403\n"
        "from tools.product.build_beta import main as _main\n",
        encoding="utf-8",
    )
    (root / "tests" / "unit").mkdir(parents=True)
    (root / "tests" / "unit" / "test_alpha.py").write_text("python3 tools/product/build_alpha.py\n", encoding="utf-8")


def _write_internal_import_fixture(root: Path) -> None:
    package_dir = root / "tools" / "cleanup"
    package_dir.mkdir(parents=True)
    (root / "tools" / "__init__.py").write_text("", encoding="utf-8")
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    (package_dir / "cleanup_alpha.py").write_text(
        "from __future__ import annotations\n\n"
        "from tools.builder_table_utils import write_csv_rows\n\n"
        "VALUE = write_csv_rows\n",
        encoding="utf-8",
    )
    (root / "tools" / "cleanup_alpha.py").write_text(
        "from tools.cleanup.cleanup_alpha import *  # noqa: F401,F403\n",
        encoding="utf-8",
    )


def test_batch2_migration_receipt_verifies_rewritten_test_import(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    _write_fixture(tmp_path)

    payload = mod.build_tools_package_batch2_migration_receipt(batch2_plan_packet=_plan())

    assert payload["summary"]["status"] == "tools_package_batch2_migration_receipt_ready"
    assert payload["summary"]["verified_migration_count"] == 1
    assert payload["summary"]["reference_rewrite_verified_count"] == 1
    assert payload["summary"]["cli_main_wrapper_count"] == 1
    assert payload["summary"]["import_only_wrapper_count"] == 0
    assert payload["summary"]["caller_or_test_rewrite_executed"] is True
    assert payload["summary"]["external_state_mutated"] is False


def test_batch2_migration_receipt_accepts_import_only_wrapper(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    _write_import_only_fixture(tmp_path)

    payload = mod.build_tools_package_batch2_migration_receipt(batch2_plan_packet=_import_only_plan())

    assert payload["summary"]["status"] == "tools_package_batch2_migration_receipt_ready"
    assert payload["summary"]["verified_migration_count"] == 1
    assert payload["summary"]["cli_main_wrapper_count"] == 0
    assert payload["summary"]["import_only_wrapper_count"] == 1
    assert payload["rows"][0]["wrapper_main_passthrough_required"] is False
    assert payload["rows"][0]["migration_verified"] is True


def test_batch2_migration_receipt_checks_moved_reference_file_target(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    _write_intra_slice_fixture(tmp_path)

    payload = mod.build_tools_package_batch2_migration_receipt(batch2_plan_packet=_intra_slice_plan())

    assert payload["summary"]["status"] == "tools_package_batch2_migration_receipt_ready"
    assert payload["summary"]["verified_migration_count"] == 2
    assert payload["summary"]["reference_rewrite_verified_count"] == 2
    assert payload["rows"][1]["missing_reference_locations"] == ""


def test_batch2_migration_receipt_verifies_internal_import_self_reference(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    _write_internal_import_fixture(tmp_path)

    payload = mod.build_tools_package_batch2_migration_receipt(batch2_plan_packet=_internal_import_plan())

    assert payload["summary"]["status"] == "tools_package_batch2_migration_receipt_ready"
    assert payload["summary"]["verified_migration_count"] == 1
    assert payload["summary"]["reference_rewrite_verified_count"] == 1
    assert payload["summary"]["import_only_wrapper_count"] == 1
    assert payload["rows"][0]["rewritten_reference_locations"] == "tools/cleanup_alpha.py:3"


def test_batch2_migration_receipt_blocks_stale_test_import(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    _write_fixture(tmp_path, stale=True)

    payload = mod.build_tools_package_batch2_migration_receipt(batch2_plan_packet=_plan())

    assert payload["summary"]["status"] == "blocked_tools_package_batch2_migration_receipt"
    assert "reference_not_rewritten" in payload["summary"]["blockers"]
    assert payload["rows"][0]["stale_reference_locations"] == "tests/unit/test_alpha.py:1"


def test_batch2_migration_receipt_tool_writes_outputs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    _write_fixture(tmp_path)
    plan_json = tmp_path / "plan.json"
    out_json = tmp_path / "receipt.json"
    out_csv = tmp_path / "receipt.csv"
    out_md = tmp_path / "receipt.md"
    plan_json.write_text(json.dumps(_plan()) + "\n", encoding="utf-8")

    mod.main(["--batch2-plan-json", str(plan_json), "--out-json", str(out_json), "--out-csv", str(out_csv), "--out-md", str(out_md)])

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "tools_package_batch2_migration_receipt_ready"
    assert out_csv.read_text(encoding="utf-8").startswith("source_path,target_path,")
    assert "Tools Package Batch2 Migration Receipt" in out_md.read_text(encoding="utf-8")
