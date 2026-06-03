from __future__ import annotations

import json
from pathlib import Path

from betelgeuze_product.license_options import build_product_license_decision_packet
from tools import build_product_license_decision_packet as tool


def _commercial_only_license_blocked() -> dict:
    return {
        "summary": {
            "status": "blocked_product_commercial_independence_gate",
            "blocker_count": 1,
            "license_present": False,
        },
        "rows": [{"check": "license_file_present", "status": "fail"}],
    }


def _license_gate() -> dict:
    return {
        "summary": {
            "status": "blocked_product_license_decision_gate",
            "operator_intake_csv_present": False,
            "authorized_for_license_file_creation_review": False,
        }
    }


def test_product_license_decision_packet_lists_options_without_writing_license() -> None:
    payload = build_product_license_decision_packet(
        commercial_independence_gate_packet=_commercial_only_license_blocked(),
        license_decision_gate_packet=_license_gate(),
    )

    summary = payload["summary"]
    assert summary["status"] == "product_license_decision_packet_ready"
    assert summary["option_count"] >= 5
    assert summary["commercial_gate_only_license_blocked"] is True
    assert summary["license_file_written"] is False
    assert summary["legal_advice_provided"] is False
    assert summary["external_state_mutated"] is False
    spdx_ids = {row["spdx_license_id"] for row in payload["rows"]}
    assert {"Apache-2.0", "MIT", "BSD-3-Clause", "GPL-3.0-only", "ProprietaryRef-Betelgeuze"} <= spdx_ids
    assert all(row["approval_token_required"] == "APPROVE_PRODUCT_LICENSE_FILE_CREATION" for row in payload["rows"])


def test_product_license_decision_packet_blocks_when_commercial_gate_has_other_blockers() -> None:
    commercial = {
        "summary": {"status": "blocked_product_commercial_independence_gate", "blocker_count": 2, "license_present": False},
        "rows": [
            {"check": "license_file_present", "status": "fail"},
            {"check": "runtime_dependencies_pinned", "status": "fail"},
        ],
    }
    payload = build_product_license_decision_packet(
        commercial_independence_gate_packet=commercial,
        license_decision_gate_packet=_license_gate(),
    )

    assert payload["summary"]["status"] == "blocked_product_license_decision_packet"
    assert payload["summary"]["commercial_gate_only_license_blocked"] is False
    assert any(blocker["code"] == "commercial_gate_not_license_only" for blocker in payload["blockers"])


def test_build_product_license_decision_packet_tool_writes_outputs(tmp_path: Path) -> None:
    commercial_json = tmp_path / "commercial.json"
    license_json = tmp_path / "license.json"
    out_json = tmp_path / "packet.json"
    out_csv = tmp_path / "packet.csv"
    out_md = tmp_path / "packet.md"
    commercial_json.write_text(json.dumps(_commercial_only_license_blocked()) + "\n", encoding="utf-8")
    license_json.write_text(json.dumps(_license_gate()) + "\n", encoding="utf-8")

    tool.main(
        [
            "--commercial-independence-json",
            str(commercial_json),
            "--license-decision-json",
            str(license_json),
            "--operator-template-csv",
            "runs/template.csv",
            "--operator-intake-csv",
            "runs/intake.csv",
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "product_license_decision_packet_ready"
    assert out_csv.read_text(encoding="utf-8").startswith("option_rank,spdx_license_id,")
    assert "Product License Decision Packet" in out_md.read_text(encoding="utf-8")
