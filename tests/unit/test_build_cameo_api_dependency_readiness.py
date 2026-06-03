from __future__ import annotations

import json
from pathlib import Path

from tools import build_cameo_api_dependency_readiness as mod


def test_build_cameo_api_dependency_readiness_tool_writes_outputs(tmp_path: Path) -> None:
    req = tmp_path / "requirements-api.txt"
    req.write_text("fastapi\n", encoding="utf-8")
    out_json = tmp_path / "api_dep.json"
    out_csv = tmp_path / "api_dep.csv"
    out_md = tmp_path / "api_dep.md"

    mod.main(
        [
            "--requirements-api",
            str(req),
            "--root",
            str(tmp_path),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    summary = json.loads(out_json.read_text(encoding="utf-8"))["summary"]
    assert summary["packet_type"] == "cameo_api_dependency_readiness"
    assert summary["package_install_executed"] is False
    assert out_csv.read_text(encoding="utf-8").startswith("source_line,requirement,")
    assert "CAMEO API Dependency Readiness" in out_md.read_text(encoding="utf-8")
