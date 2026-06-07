from __future__ import annotations

import json
from pathlib import Path

import pytest

from betelgeuze_product.license_decision import APPROVAL_TOKEN
from betelgeuze_product.license_file_creation import build_product_license_file_creation_work_order
from tools import write_product_license_file as mod


def _commercial_gate_only_license_blocked() -> dict:
    return {
        "summary": {
            "status": "blocked_product_commercial_independence_gate",
            "blocker_count": 1,
            "license_present": False,
        },
        "rows": [{"check": "license_file_present", "status": "fail"}],
    }


def _license_decision_ready(license_text_source: str) -> dict:
    return {
        "summary": {
            "status": "product_license_decision_gate_ready",
            "authorized_for_license_file_creation_review": True,
            "spdx_license_id": "ProprietaryRef-Betelgeuze",
            "license_text_source": license_text_source,
            "copyright_holder": "Betelgeuze",
            "effective_year": "2026",
            "license_present": False,
        }
    }


def _ready_work_order(path: Path, license_text_source: Path) -> None:
    payload = build_product_license_file_creation_work_order(
        license_decision_gate_packet=_license_decision_ready(str(license_text_source)),
        commercial_independence_gate_packet=_commercial_gate_only_license_blocked(),
        target_license_path="LICENSE",
    )
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def test_write_product_license_file_blocks_without_env_approval(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    work_order = tmp_path / "work_order.json"
    template = tmp_path / "approved_license.txt"
    out = tmp_path / "LICENSE"
    template.write_text("Operator approved license text\n", encoding="utf-8")
    _ready_work_order(work_order, template)
    monkeypatch.delenv(APPROVAL_TOKEN, raising=False)

    with pytest.raises(SystemExit) as exc:
        mod.main(["--work-order-json", str(work_order), "--license-template", str(template), "--out", "LICENSE"])

    assert "missing_env_approval_token" in str(exc.value)
    assert not out.exists()


def test_write_product_license_file_writes_only_when_work_order_ready_and_token_present(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    work_order = tmp_path / "work_order.json"
    template = tmp_path / "approved_license.txt"
    template.write_text("Operator approved license text\n", encoding="utf-8")
    _ready_work_order(work_order, template)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(APPROVAL_TOKEN, "1")

    result = mod.main(["--work-order-json", str(work_order), "--license-template", str(template), "--out", "LICENSE"])

    assert result["status"] == "product_license_file_written"
    assert result["license_file_written"] is True
    assert result["external_state_mutated"] is False
    assert (tmp_path / "LICENSE").read_text(encoding="utf-8") == "Operator approved license text\n"


def test_write_product_license_file_blocks_output_path_mismatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    work_order = tmp_path / "work_order.json"
    template = tmp_path / "approved_license.txt"
    template.write_text("Operator approved license text\n", encoding="utf-8")
    _ready_work_order(work_order, template)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(APPROVAL_TOKEN, "1")

    with pytest.raises(SystemExit) as exc:
        mod.main(["--work-order-json", str(work_order), "--license-template", str(template), "--out", "LICENSE.txt"])

    assert "output_path_mismatch" in str(exc.value)
    assert not (tmp_path / "LICENSE.txt").exists()
