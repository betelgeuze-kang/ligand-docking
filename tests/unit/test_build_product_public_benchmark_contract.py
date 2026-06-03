from __future__ import annotations

import json
from pathlib import Path

from tools import build_product_public_benchmark_contract as mod


def test_build_product_public_benchmark_contract_tool_writes_outputs(tmp_path: Path) -> None:
    out_json = tmp_path / "contract.json"
    out_csv = tmp_path / "contract.csv"
    out_md = tmp_path / "contract.md"
    template_csv = tmp_path / "template.csv"

    mod.main(
        [
            "--scorecard-csv",
            str(tmp_path / "missing.csv"),
            "--template-csv",
            str(template_csv),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "blocked_product_public_benchmark_contract"
    assert payload["summary"]["requires_24h_server"] is False
    assert out_csv.read_text(encoding="utf-8").startswith("suite_id,benchmark_family,")
    assert template_csv.read_text(encoding="utf-8").startswith("suite_id,benchmark_family,")
    assert "Product Public Benchmark Contract" in out_md.read_text(encoding="utf-8")
