from __future__ import annotations

import json
from pathlib import Path

from tools import build_product_api_contract as mod


def test_build_product_api_contract_tool_writes_outputs(tmp_path: Path) -> None:
    out_json = tmp_path / "product_api_contract.json"
    out_csv = tmp_path / "product_api_contract.csv"
    out_md = tmp_path / "product_api_contract.md"

    mod.main(
        [
            "--root",
            ".",
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "product_api_contract_ready"
    assert payload["summary"]["api_contract_ready"] is True
    assert out_csv.read_text(encoding="utf-8").startswith("check,status,")
    assert "Product API Contract" in out_md.read_text(encoding="utf-8")
