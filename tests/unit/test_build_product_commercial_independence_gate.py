from __future__ import annotations

import json
from pathlib import Path

from tools import build_product_commercial_independence_gate as mod


def test_build_product_commercial_independence_gate_tool_writes_outputs(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "api").mkdir()
    (root / "api" / "product.py").write_text("# product API\n", encoding="utf-8")
    (root / "betelgeuze_product").mkdir()
    (root / "betelgeuze_product" / "__init__.py").write_text("", encoding="utf-8")
    (root / "betelgeuze_product" / "cli.py").write_text("def main():\n    return 0\n", encoding="utf-8")
    (root / "betelgeuze_cameo").mkdir()
    (root / "betelgeuze_cameo" / "__init__.py").write_text("", encoding="utf-8")
    (root / "betelgeuze_cameo" / "cli.py").write_text("def main():\n    return 0\n", encoding="utf-8")
    (root / "betelgeuze_cleanup").mkdir()
    (root / "betelgeuze_cleanup" / "__init__.py").write_text("", encoding="utf-8")
    (root / "betelgeuze_cleanup" / "cli.py").write_text("def main():\n    return 0\n", encoding="utf-8")
    (root / "pyproject.toml").write_text(
        """
[project]
name = "betelgeuze-md-product"
version = "0.1.0"
requires-python = ">=3.11"

[project.scripts]
betelgeuze-product = "betelgeuze_product.cli:main"
betelgeuze-cameo = "betelgeuze_cameo.cli:main"
betelgeuze-cleanup = "betelgeuze_cleanup.cli:main"

[tool.setuptools.packages.find]
include = ["betelgeuze_product*", "betelgeuze_cameo*", "betelgeuze_cleanup*"]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (root / "LICENSE").write_text("Proprietary\n", encoding="utf-8")
    (root / "requirements.txt").write_text("numpy==1.26.4\n", encoding="utf-8")
    for name in ("requirements-api.txt", "requirements-deploy.txt", "requirements-optional.txt", "requirements-train.txt"):
        (root / name).write_text("# optional profile\n", encoding="utf-8")
    out_json = tmp_path / "gate.json"
    out_csv = tmp_path / "gate.csv"
    out_md = tmp_path / "gate.md"

    mod.main(["--root", str(root), "--out-json", str(out_json), "--out-csv", str(out_csv), "--out-md", str(out_md)])

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "product_commercial_independence_gate_ready"
    assert payload["summary"]["product_cli_surface_present"] is True
    assert payload["summary"]["pyproject_packaging_metadata_present"] is True
    assert payload["summary"]["console_entrypoint_targets_present"] is True
    assert out_csv.read_text(encoding="utf-8").startswith("check,status,")
    assert "Product Commercial Independence Gate" in out_md.read_text(encoding="utf-8")
