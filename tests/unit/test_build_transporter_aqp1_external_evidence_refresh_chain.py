from __future__ import annotations

from unittest.mock import patch

from tools.product.build_transporter_aqp1_external_evidence_refresh_chain import (
    REFRESH_STEPS,
    build_packet,
)


def _fake_reader(payloads: dict[str, dict]):
    def fake_read_json(path_like: str):
        key = str(path_like).replace("/home/betelgeuze/분자동역학/", "")
        if key not in payloads and "/runs/" in str(path_like):
            key = "runs/" + str(path_like).split("/runs/", 1)[-1]
        return payloads.get(key, {"summary": {"status": "refreshed"}})

    return fake_read_json


def test_refresh_chain_uses_intake_claim_safe_approved_count() -> None:
    lane_payloads = {
        "runs/aqp1_direct_binding_external_evidence_intake_current.json": {
            "summary": {
                "status": "aqp1_direct_binding_external_evidence_intake_ready",
                "claim_safe_approved_count": 1,
            }
        },
        "runs/transporter_p0_closure_packet_current.json": {
            "summary": {
                "status": "transporter_p0_closure_packet_ready",
                "aqp1_core_p0_open_count": 0,
            }
        },
        "runs/product_scope_breadth_contract_current.json": {
            "summary": {"status": "product_scope_breadth_contract_ready"}
        },
        "runs/product_ai_architecture_execution_backlog_current.json": {
            "summary": {
                "status": "product_ai_architecture_execution_backlog_ready",
                "scope_deferred_work_item_count": 0,
                "release_blocking_work_item_count": 0,
            }
        },
    }
    commands: list[list[str]] = []

    with patch(
        "tools.accounting.build_transporter_aqp1_external_evidence_refresh_chain._run",
        side_effect=commands.append,
    ), patch(
        "tools.accounting.build_transporter_aqp1_external_evidence_refresh_chain._read_json",
        side_effect=_fake_reader(lane_payloads),
    ):
        payload = build_packet(generated_at_local="2026-06-07T12:00:00+09:00")

    summary = payload["summary"]
    assert summary["status"] == "transporter_aqp1_external_evidence_refresh_chain_ready"
    assert summary["aqp1_claim_safe_approved_count"] == 1
    assert summary["aqp1_claim_safe_approved_row_count"] == 1
    assert "transporter_refresh:aqp1_claim_safe_external_evidence_pending" not in summary["blockers"]
    assert [command[1] for command in commands] == [script for _, script in REFRESH_STEPS]
    assert [lane for lane, _ in REFRESH_STEPS][:2] == [
        "aqp1_external_evidence_operator_fill_guide",
        "aqp1_external_evidence_supplement_example",
    ]


def test_refresh_chain_blocks_when_claim_safe_count_missing() -> None:
    lane_payloads = {
        "runs/aqp1_direct_binding_external_evidence_intake_current.json": {
            "summary": {"status": "blocked_aqp1_direct_binding_external_evidence_intake"}
        },
        "runs/transporter_p0_closure_packet_current.json": {
            "summary": {
                "status": "transporter_p0_closure_packet_ready",
                "aqp1_core_p0_open_count": 0,
            }
        },
        "runs/product_scope_breadth_contract_current.json": {
            "summary": {"status": "product_scope_breadth_contract_ready"}
        },
        "runs/product_ai_architecture_execution_backlog_current.json": {
            "summary": {
                "status": "product_ai_architecture_execution_backlog_ready",
                "scope_deferred_work_item_count": 0,
                "release_blocking_work_item_count": 0,
            }
        },
    }

    with patch(
        "tools.accounting.build_transporter_aqp1_external_evidence_refresh_chain._run"
    ), patch(
        "tools.accounting.build_transporter_aqp1_external_evidence_refresh_chain._read_json",
        side_effect=_fake_reader(lane_payloads),
    ):
        payload = build_packet(generated_at_local="2026-06-07T12:00:00+09:00")

    summary = payload["summary"]
    assert summary["status"] == "transporter_aqp1_external_evidence_refresh_chain_refreshed_with_blockers"
    assert summary["aqp1_claim_safe_approved_count"] == 0
    assert "transporter_refresh:aqp1_claim_safe_external_evidence_pending" in summary["blockers"]
