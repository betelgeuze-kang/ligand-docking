from __future__ import annotations

import json
from pathlib import Path

from tools import build_product_license_decision_gate as mod


def test_build_product_license_decision_gate_tool_writes_outputs_and_template(tmp_path: Path) -> None:
    commercial = tmp_path / "commercial.json"
    commercial.write_text(
        json.dumps(
            {
                "summary": {"status": "blocked_product_commercial_independence_gate", "blocker_count": 1, "license_present": False},
                "rows": [{"check": "license_file_present", "status": "fail"}],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    out_json = tmp_path / "gate.json"
    out_csv = tmp_path / "gate.csv"
    out_md = tmp_path / "gate.md"
    template = tmp_path / "template.csv"

    mod.main(
        [
            "--commercial-independence-json",
            str(commercial),
            "--operator-intake-csv",
            str(tmp_path / "missing.csv"),
            "--template-csv",
            str(template),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "blocked_product_license_decision_gate"
    assert out_csv.read_text(encoding="utf-8").startswith("check,status,")
    assert "Product License Decision Gate" in out_md.read_text(encoding="utf-8")
    template_text = template.read_text(encoding="utf-8")
    assert template_text.startswith("decision,approval_token_required,approval_token,")
    assert "create_license_file,APPROVE_PRODUCT_LICENSE_FILE_CREATION,,OPERATOR_FILL_SPDX" in template_text
