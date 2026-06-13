from __future__ import annotations

from pathlib import Path

from betelgeuze_product.license_decision import APPROVAL_TOKEN, DECISION_CREATE_LICENSE, build_product_license_decision_gate


def _commercial_gate_only_license_blocked() -> dict:
    return {
        "summary": {
            "status": "blocked_product_commercial_independence_gate",
            "blocker_count": 1,
            "license_present": False,
        },
        "rows": [{"check": "license_file_present", "status": "fail"}],
    }


def _commercial_gate_ready_with_license() -> dict:
    return {
        "summary": {
            "status": "product_commercial_independence_gate_ready",
            "blocker_count": 0,
            "license_present": True,
        },
        "rows": [{"check": "license_file_present", "status": "pass"}],
    }


def _write_ready_intake(path: Path) -> None:
    path.write_text(
        "decision,approval_token,spdx_license_id,license_text_source,copyright_holder,effective_year,notes\n"
        f"{DECISION_CREATE_LICENSE},{APPROVAL_TOKEN},ProprietaryRef-Betelgeuze,internal counsel approved text,Betelgeuze,2026,ready\n",
        encoding="utf-8",
    )


def test_product_license_decision_gate_blocks_missing_operator_intake(tmp_path: Path) -> None:
    payload = build_product_license_decision_gate(
        commercial_independence_gate_packet=_commercial_gate_only_license_blocked(),
        operator_intake_csv=tmp_path / "missing.csv",
    )

    assert payload["summary"]["status"] == "blocked_product_license_decision_gate"
    assert payload["summary"]["authorized_for_license_file_creation_review"] is False
    assert payload["summary"]["operator_intake_csv_present"] is False
    assert any(row["check"] == "operator_intake_csv_present" and row["status"] == "fail" for row in payload["rows"])
    assert payload["summary"]["license_file_written"] is False
    assert payload["summary"]["external_state_mutated"] is False


def test_product_license_decision_gate_ready_with_exact_token_and_metadata(tmp_path: Path) -> None:
    intake = tmp_path / "intake.csv"
    _write_ready_intake(intake)

    payload = build_product_license_decision_gate(
        commercial_independence_gate_packet=_commercial_gate_only_license_blocked(),
        operator_intake_csv=intake,
    )

    assert payload["summary"]["status"] == "product_license_decision_gate_ready"
    assert payload["summary"]["authorized_for_license_file_creation_review"] is True
    assert payload["summary"]["spdx_license_id"] == "ProprietaryRef-Betelgeuze"
    assert payload["summary"]["missing_required_field_count"] == 0
    assert all(row["status"] == "pass" for row in payload["rows"])


def test_product_license_decision_gate_ready_when_license_already_present(tmp_path: Path) -> None:
    intake = tmp_path / "intake.csv"
    _write_ready_intake(intake)

    payload = build_product_license_decision_gate(
        commercial_independence_gate_packet=_commercial_gate_ready_with_license(),
        operator_intake_csv=intake,
    )

    summary = payload["summary"]
    assert summary["status"] == "product_license_decision_gate_ready"
    assert summary["authorized_for_license_file_creation_review"] is True
    assert summary["license_present"] is True
    assert summary["commercial_independence_ready"] is True
    assert summary["license_review_state_ready"] is True
    assert all(row["status"] == "pass" for row in payload["rows"])
    assert "existing LICENSE" in summary["next_required_step"]


def test_product_license_decision_gate_blocks_bad_token_or_non_license_blockers(tmp_path: Path) -> None:
    intake = tmp_path / "intake.csv"
    intake.write_text(
        "decision,approval_token,spdx_license_id,license_text_source,copyright_holder,effective_year,notes\n"
        f"{DECISION_CREATE_LICENSE},WRONG_TOKEN,MIT,https://opensource.org/license/mit,Betelgeuze,2026,bad token\n",
        encoding="utf-8",
    )
    commercial_gate = {
        "summary": {"status": "blocked_product_commercial_independence_gate", "blocker_count": 2, "license_present": False},
        "rows": [{"check": "license_file_present", "status": "fail"}, {"check": "runtime_dependencies_pinned", "status": "fail"}],
    }

    payload = build_product_license_decision_gate(
        commercial_independence_gate_packet=commercial_gate,
        operator_intake_csv=intake,
    )

    assert payload["summary"]["status"] == "blocked_product_license_decision_gate"
    assert payload["summary"]["approval_token_valid"] is False
    assert payload["summary"]["commercial_gate_only_license_blocked"] is False
    failed = {row["check"] for row in payload["rows"] if row["status"] == "fail"}
    assert {"approval_token_valid", "commercial_gate_only_license_blocked"} <= failed
