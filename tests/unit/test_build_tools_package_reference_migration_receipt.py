from __future__ import annotations

import json
from pathlib import Path

from tools import build_tools_package_reference_migration_receipt as mod


def _review() -> dict:
    return {
        "summary": {"status": "tools_package_reference_review_ready"},
        "rows": [
            {
                "tool_path": "tools/build_product_alpha.py",
                "target_path": "tools/product/build_product_alpha.py",
                "proposed_package": "product",
                "reference_locations": "tools/runner.py:1",
            }
        ],
    }


def _write_migrated_fixture(root: Path, *, stale: bool = False) -> None:
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
    caller = "tools/build_product_alpha.py" if stale else "tools/product/build_product_alpha.py"
    (root / "tools" / "runner.py").write_text(f'cmd = "{caller}"\n', encoding="utf-8")


def test_reference_migration_receipt_verifies_caller_rewrite(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    _write_migrated_fixture(tmp_path)

    payload = mod.build_tools_package_reference_migration_receipt(reference_review_packet=_review())
    summary = payload["summary"]
    row = payload["rows"][0]

    assert summary["status"] == "tools_package_reference_migration_receipt_ready"
    assert summary["verified_migration_count"] == 1
    assert summary["caller_rewrite_verified_count"] == 1
    assert summary["caller_rewrite_executed"] is True
    assert summary["external_state_mutated"] is False
    assert row["rewritten_caller_locations"] == "tools/runner.py:1"


def test_reference_migration_receipt_blocks_stale_caller(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    _write_migrated_fixture(tmp_path, stale=True)

    payload = mod.build_tools_package_reference_migration_receipt(reference_review_packet=_review())
    blockers = set(payload["summary"]["blockers"])

    assert payload["summary"]["status"] == "blocked_tools_package_reference_migration_receipt"
    assert "caller_line_not_rewritten" in blockers
    assert payload["rows"][0]["stale_caller_locations"] == "tools/runner.py:1"


def test_reference_migration_receipt_tool_writes_outputs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    _write_migrated_fixture(tmp_path)
    review_json = tmp_path / "review.json"
    out_json = tmp_path / "receipt.json"
    out_csv = tmp_path / "receipt.csv"
    out_md = tmp_path / "receipt.md"
    review_json.write_text(json.dumps(_review()) + "\n", encoding="utf-8")

    mod.main(["--reference-review-json", str(review_json), "--out-json", str(out_json), "--out-csv", str(out_csv), "--out-md", str(out_md)])

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "tools_package_reference_migration_receipt_ready"
    assert out_csv.read_text(encoding="utf-8").startswith("source_path,target_path,")
    assert "Tools Package Reference Migration Receipt" in out_md.read_text(encoding="utf-8")
