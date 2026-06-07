from __future__ import annotations

import json
from pathlib import Path

from tools import build_tools_package_separation_work_order as mod


def _write(path: Path, text: str = "print('ok')\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_tools_package_separation_work_order_classifies_and_scores_fixture(tmp_path: Path) -> None:
    _write(tmp_path / "tools" / "build_cameo_status.py", "import argparse\n")
    _write(tmp_path / "tools" / "build_product_release.py", "from tools import build_cameo_status\n")
    _write(tmp_path / "tools" / "build_unknown_probe.py")
    _write(tmp_path / "tests" / "unit" / "test_cameo.py", "python3 tools/build_cameo_status.py\n")

    payload = mod.build_tools_package_separation_work_order(root=tmp_path)
    summary = payload["summary"]
    by_path = {row["tool_path"]: row for row in payload["rows"]}

    assert summary["status"] == "tools_package_separation_work_order_ready"
    assert summary["tool_file_count"] == 3
    assert summary["package_counts"]["cameo"] == 1
    assert summary["package_counts"]["product"] == 1
    assert summary["other_review_count"] == 1
    assert by_path["tools/build_cameo_status.py"]["proposed_package"] == "cameo"
    assert by_path["tools/build_cameo_status.py"]["test_reference_count"] == 1
    assert by_path["tools/build_product_release.py"]["internal_tool_import_count"] == 1
    assert by_path["tools/build_unknown_probe.py"]["proposed_package"] == "other_review"
    assert summary["move_executed"] is False
    assert summary["import_rewrite_executed"] is False
    assert summary["external_state_mutated"] is False


def test_tools_package_separation_work_order_uses_exact_reference_tokens(tmp_path: Path) -> None:
    _write(tmp_path / "tools" / "run_alpha.py", "import argparse\n")
    _write(tmp_path / "tools" / "run_alpha_current.py", "import argparse\n")
    _write(
        tmp_path / "tests" / "unit" / "test_alpha_current.py",
        "from tools.product import run_alpha_current as mod\n"
        "python3 tools/product/run_alpha_current.py\n",
    )

    payload = mod.build_tools_package_separation_work_order(root=tmp_path)
    by_path = {row["tool_path"]: row for row in payload["rows"]}

    assert by_path["tools/run_alpha.py"]["test_reference_count"] == 0
    assert by_path["tools/run_alpha_current.py"]["test_reference_count"] == 2


def test_tools_package_separation_work_order_tool_writes_outputs(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write(repo / "tools" / "build_casp17_packet.py")
    out_json = tmp_path / "work_order.json"
    out_csv = tmp_path / "work_order.csv"
    out_md = tmp_path / "work_order.md"

    mod.main(["--root", str(repo), "--out-json", str(out_json), "--out-csv", str(out_csv), "--out-md", str(out_md)])

    summary = json.loads(out_json.read_text(encoding="utf-8"))["summary"]
    assert summary["status"] == "tools_package_separation_work_order_ready"
    assert summary["tool_file_count"] == 1
    assert out_csv.read_text(encoding="utf-8").startswith("tool_path,proposed_package,")
    assert "Tools Package Separation Work Order" in out_md.read_text(encoding="utf-8")
