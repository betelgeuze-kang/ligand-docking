from __future__ import annotations

import json
from pathlib import Path

from tools import build_product_operational_quality_contract as mod


def test_build_product_operational_quality_contract_tool_writes_outputs(tmp_path: Path) -> None:
    out_json = tmp_path / "quality.json"
    out_csv = tmp_path / "quality.csv"
    out_md = tmp_path / "quality.md"

    mod.main(["--out-json", str(out_json), "--out-csv", str(out_csv), "--out-md", str(out_md)])

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "product_operational_quality_contract_ready"
    assert payload["summary"]["input_payload_persisted"] is False
    assert out_csv.read_text(encoding="utf-8").startswith("check,status,")
    assert "Product Operational Quality Contract" in out_md.read_text(encoding="utf-8")
