from __future__ import annotations

from pathlib import Path

from betelgeuze_product.license_file_creation import build_product_license_file_creation_work_order


def _commercial_gate_only_license_blocked() -> dict:
    return {
        "summary": {
            "status": "blocked_product_commercial_independence_gate",
            "blocker_count": 1,
            "license_present": False,
        },
        "rows": [{"check": "license_file_present", "status": "fail"}],
    }


def _commercial_gate_with_license_present() -> dict:
    return {
        "summary": {
            "status": "product_commercial_independence_gate_ready",
            "blocker_count": 0,
            "license_present": True,
        },
        "rows": [{"check": "license_file_present", "status": "pass"}],
    }


def _license_decision_ready(license_text_source: str = "legal/product-license-template.txt") -> dict:
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


def _license_decision_blocked() -> dict:
    return {
        "summary": {
            "status": "blocked_product_license_decision_gate",
            "authorized_for_license_file_creation_review": False,
            "spdx_license_id": "",
            "license_text_source": "",
            "copyright_holder": "",
            "effective_year": "",
        }
    }


def test_license_file_creation_work_order_blocks_until_license_decision_is_ready() -> None:
    payload = build_product_license_file_creation_work_order(
        license_decision_gate_packet=_license_decision_blocked(),
        commercial_independence_gate_packet=_commercial_gate_only_license_blocked(),
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_product_license_file_creation_work_order"
    assert summary["license_file_creation_review_ready"] is False
    assert summary["license_file_written"] is False
    assert summary["external_state_mutated"] is False
    failed = {row["check"] for row in payload["rows"] if row["status"] == "fail"}
    assert {"license_decision_gate_ready", "license_file_creation_authorized", "license_metadata_complete"} <= failed
    assert any(blocker["code"] == "license_decision_gate_ready_not_ready" for blocker in payload["blockers"])


def test_license_file_creation_work_order_ready_without_writing_license(tmp_path: Path) -> None:
    license_text = tmp_path / "product-license-template.txt"
    license_text.write_text("Operator approved license text.\n", encoding="utf-8")
    payload = build_product_license_file_creation_work_order(
        license_decision_gate_packet=_license_decision_ready(str(license_text)),
        commercial_independence_gate_packet=_commercial_gate_only_license_blocked(),
    )

    summary = payload["summary"]
    assert summary["status"] == "product_license_file_creation_work_order_ready"
    assert summary["license_file_creation_review_ready"] is True
    assert summary["approval_token_required"] == "APPROVE_PRODUCT_LICENSE_FILE_CREATION"
    assert summary["target_license_path"] == "LICENSE"
    assert summary["spdx_license_id"] == "ProprietaryRef-Betelgeuze"
    assert summary["license_text_source_present"] is True
    assert summary["license_text_source_non_empty"] is True
    assert summary["license_text_source_size_bytes"] > 0
    assert len(summary["license_text_source_sha256"]) == 64
    assert summary["license_review_manifest_ready"] is True
    assert len(summary["license_review_manifest_fingerprint_sha256"]) == 64
    assert "tools/write_product_license_file.py" in summary["license_file_write_command_template"]
    assert str(license_text) in summary["license_file_write_command_template"]
    assert summary["license_review_manifest"]["target_license_path"] == "LICENSE"
    assert summary["license_review_manifest"]["license_text_source_sha256"] == summary["license_text_source_sha256"]
    assert summary["license_review_manifest"]["license_file_written"] is False
    assert summary["license_file_written"] is False
    assert summary["external_state_mutated"] is False
    assert all(row["status"] == "pass" for row in payload["rows"])
    create_item = next(row for row in payload["work_items"] if row["step"] == "create_or_review_license_file")
    assert create_item["status"] == "ready_for_separate_operator_step"
    assert create_item["license_review_manifest_fingerprint_sha256"] == summary["license_review_manifest_fingerprint_sha256"]
    assert create_item["command_template"] == summary["license_file_write_command_template"]
    assert create_item["license_file_written"] is False


def test_license_file_creation_work_order_blocks_when_license_text_source_file_is_missing() -> None:
    payload = build_product_license_file_creation_work_order(
        license_decision_gate_packet=_license_decision_ready("legal/missing-product-license-template.txt"),
        commercial_independence_gate_packet=_commercial_gate_only_license_blocked(),
    )

    summary = payload["summary"]
    failed = {row["check"] for row in payload["rows"] if row["status"] == "fail"}
    assert summary["status"] == "blocked_product_license_file_creation_work_order"
    assert summary["license_text_source_present"] is False
    assert "license_text_source_file_ready" in failed
    assert any(blocker["code"] == "license_text_source_file_ready_not_ready" for blocker in payload["blockers"])


def test_license_file_creation_work_order_blocks_when_license_already_present() -> None:
    payload = build_product_license_file_creation_work_order(
        license_decision_gate_packet=_license_decision_ready(),
        commercial_independence_gate_packet=_commercial_gate_with_license_present(),
    )

    assert payload["summary"]["status"] == "blocked_product_license_file_creation_work_order"
    failed = {row["check"] for row in payload["rows"] if row["status"] == "fail"}
    assert {"license_not_already_present", "commercial_gate_only_license_blocked"} <= failed
    assert payload["summary"]["license_file_written"] is False
