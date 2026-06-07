from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from betelgeuze_product.license_decision import APPROVAL_TOKEN, build_product_license_decision_gate
from tools import fill_product_license_decision_operator_intake as mod


def _commercial_gate_only_license_blocked() -> dict:
    return {
        "summary": {
            "status": "blocked_product_commercial_independence_gate",
            "blocker_count": 1,
            "license_present": False,
        },
        "rows": [{"check": "license_file_present", "status": "fail"}],
    }


def test_fill_product_license_decision_operator_intake_writes_gate_ready_csv(tmp_path: Path) -> None:
    out_csv = tmp_path / "license_intake.csv"

    result = mod.main(
        [
            "--approval-token",
            APPROVAL_TOKEN,
            "--spdx-license-id",
            "ProprietaryRef-Betelgeuze",
            "--license-text-source",
            "legal/product-license-template.txt",
            "--copyright-holder",
            "Betelgeuze",
            "--effective-year",
            "2026",
            "--out-csv",
            str(out_csv),
        ]
    )

    rows = list(csv.DictReader(out_csv.open("r", encoding="utf-8", newline="")))
    payload = build_product_license_decision_gate(
        commercial_independence_gate_packet=_commercial_gate_only_license_blocked(),
        operator_intake_csv=out_csv,
    )

    assert result["status"] == "product_license_decision_operator_intake_written"
    assert rows == [
        {
            "decision": "create_license_file",
            "approval_token": APPROVAL_TOKEN,
            "spdx_license_id": "ProprietaryRef-Betelgeuze",
            "license_text_source": "legal/product-license-template.txt",
            "copyright_holder": "Betelgeuze",
            "effective_year": "2026",
            "notes": "",
        }
    ]
    assert payload["summary"]["status"] == "product_license_decision_gate_ready"
    assert payload["summary"]["authorized_for_license_file_creation_review"] is True


def test_fill_product_license_decision_operator_intake_blocks_bad_token(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc:
        mod.main(
            [
                "--approval-token",
                "WRONG_TOKEN",
                "--spdx-license-id",
                "MIT",
                "--license-text-source",
                "legal/mit.txt",
                "--copyright-holder",
                "Betelgeuze",
                "--effective-year",
                "2026",
                "--out-csv",
                str(tmp_path / "license_intake.csv"),
            ]
        )

    assert "approval_token_mismatch" in str(exc.value)


def test_fill_product_license_decision_operator_intake_blocks_existing_target(tmp_path: Path) -> None:
    out_csv = tmp_path / "license_intake.csv"
    out_csv.write_text("decision,approval_token\n", encoding="utf-8")
    row = mod.build_license_decision_intake_row(
        approval_token=APPROVAL_TOKEN,
        spdx_license_id="MIT",
        license_text_source="legal/mit.txt",
        copyright_holder="Betelgeuze",
        effective_year="2026",
    )

    with pytest.raises(SystemExit) as exc:
        mod.write_license_decision_intake(out_csv=out_csv, row=row)

    assert "target_exists" in str(exc.value)


def test_fill_product_license_decision_operator_intake_cli_prints_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    mod.main(
        [
            "--approval-token",
            APPROVAL_TOKEN,
            "--spdx-license-id",
            "Apache-2.0",
            "--license-text-source",
            "legal/apache-2.0.txt",
            "--copyright-holder",
            "Betelgeuze",
            "--effective-year",
            "2026",
            "--out-csv",
            str(tmp_path / "license_intake.csv"),
        ]
    )

    printed = json.loads(capsys.readouterr().out)
    assert printed["status"] == "product_license_decision_operator_intake_written"
    assert printed["spdx_license_id"] == "Apache-2.0"
    assert printed["external_state_mutated"] is False
