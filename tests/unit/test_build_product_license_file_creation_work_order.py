from __future__ import annotations

import json
from pathlib import Path

from tools import build_product_license_file_creation_work_order as mod


def _commercial_gate_only_license_blocked() -> dict:
    return {
        "summary": {
            "status": "blocked_product_commercial_independence_gate",
            "blocker_count": 1,
            "license_present": False,
        },
        "rows": [{"check": "license_file_present", "status": "fail"}],
    }


def _license_decision_ready() -> dict:
    return {
        "summary": {
            "status": "product_license_decision_gate_ready",
            "authorized_for_license_file_creation_review": True,
            "spdx_license_id": "ProprietaryRef-Betelgeuze",
            "license_text_source": "internal counsel approved text",
            "copyright_holder": "Betelgeuze",
            "effective_year": "2026",
            "license_present": False,
        }
    }


def test_build_product_license_file_creation_work_order_tool_writes_outputs(tmp_path: Path) -> None:
    license_json = tmp_path / "license_decision.json"
    commercial_json = tmp_path / "commercial.json"
    out_json = tmp_path / "license_work_order.json"
    out_csv = tmp_path / "license_work_order.csv"
    out_md = tmp_path / "license_work_order.md"
    license_json.write_text(json.dumps(_license_decision_ready()) + "\n", encoding="utf-8")
    commercial_json.write_text(json.dumps(_commercial_gate_only_license_blocked()) + "\n", encoding="utf-8")

    mod.main(
        [
            "--license-decision-json",
            str(license_json),
            "--commercial-independence-json",
            str(commercial_json),
            "--target-license-path",
            "LICENSE",
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "product_license_file_creation_work_order_ready"
    assert payload["summary"]["license_file_written"] is False
    assert "tools/write_product_license_file.py" in payload["summary"]["license_file_write_command_template"]
    assert payload["summary"]["external_state_mutated"] is False
    assert out_csv.read_text(encoding="utf-8").startswith("check,status,")
    md_text = out_md.read_text(encoding="utf-8")
    assert "Product License File Creation Work Order" in md_text
    assert "license_file_write_command_template" in md_text


def test_build_product_license_file_creation_work_order_tool_blocks_missing_inputs(tmp_path: Path) -> None:
    out_json = tmp_path / "license_work_order.json"
    out_csv = tmp_path / "license_work_order.csv"
    out_md = tmp_path / "license_work_order.md"

    mod.main(
        [
            "--license-decision-json",
            str(tmp_path / "missing_license.json"),
            "--commercial-independence-json",
            str(tmp_path / "missing_commercial.json"),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "blocked_product_license_file_creation_work_order"
    assert payload["summary"]["blocker_count"] >= 1
    assert out_csv.exists()
    assert out_md.exists()
