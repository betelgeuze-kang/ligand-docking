from __future__ import annotations

from betelgeuze_cameo.capability_preflight import (
    OUTBOUND_EMAIL_APPROVAL_TOKEN,
    REGISTRATION_APPROVAL_TOKEN,
    build_cameo_capability_preflight,
)


def _validation(status: str = "blocked_cameo_validation_readiness") -> dict:
    return {"summary": {"status": status}}


def _repair(status: str = "blocked_cameo_repair_execution_preflight") -> dict:
    return {"summary": {"status": status, "blocker_count": 4}}


def _receiver_smoke(status: str = "cameo_receiver_smoke_ready") -> dict:
    return {
        "summary": {
            "status": status,
            "post_200_ok": status == "cameo_receiver_smoke_ready",
            "blocker_count": 0 if status == "cameo_receiver_smoke_ready" else 1,
        }
    }


def test_cameo_capability_preflight_allows_development_receiver_but_not_public_registration() -> None:
    payload = build_cameo_capability_preflight(
        validation_readiness_packet=_validation(),
        repair_execution_preflight_packet=_repair(),
        receiver_scaffold_present=True,
        api_route_registered=True,
        api_operations_route_registered=True,
        local_status_cli_present=True,
    )
    summary = payload["summary"]

    assert summary["status"] == "cameo_development_capability_preflight_ready"
    assert summary["api_operations_route_registered"] is True
    assert summary["public_registration_allowed"] is False
    assert summary["public_registration_blocker_count"] == 4
    assert summary["outbound_email_enabled"] is False
    assert summary["prediction_generation_enabled"] is False
    assert summary["server_registration_mutated"] is False
    assert payload["blockers"] == []


def test_cameo_capability_preflight_blocks_when_receiver_runtime_smoke_is_blocked() -> None:
    payload = build_cameo_capability_preflight(
        validation_readiness_packet=_validation(),
        repair_execution_preflight_packet=_repair(),
        receiver_smoke_packet=_receiver_smoke("blocked_cameo_receiver_smoke"),
        receiver_scaffold_present=True,
        api_route_registered=True,
        api_operations_route_registered=True,
        local_status_cli_present=True,
    )

    assert payload["summary"]["status"] == "blocked_cameo_capability_preflight"
    assert payload["summary"]["source_receiver_smoke_status"] == "blocked_cameo_receiver_smoke"
    assert payload["summary"]["receiver_smoke_post_200_ok"] is False
    assert any(blocker["code"] == "receiver_runtime_smoke_not_ready" for blocker in payload["blockers"])


def test_cameo_capability_preflight_blocks_public_registration_request_until_evidence_and_tokens_ready() -> None:
    payload = build_cameo_capability_preflight(
        validation_readiness_packet=_validation(),
        repair_execution_preflight_packet=_repair(),
        receiver_scaffold_present=True,
        api_route_registered=True,
        api_operations_route_registered=True,
        local_status_cli_present=True,
        public_registration_requested=True,
    )

    assert payload["summary"]["status"] == "blocked_cameo_capability_preflight"
    codes = {blocker["code"] for blocker in payload["blockers"]}
    assert "public_registration_validation_evidence_ready_blocked" in codes
    assert "public_registration_registration_approval_token_present_blocked" in codes


def test_cameo_capability_preflight_public_registration_ready_when_all_policy_inputs_pass() -> None:
    payload = build_cameo_capability_preflight(
        validation_readiness_packet=_validation("cameo_validation_evidence_ready"),
        repair_execution_preflight_packet=_repair("cameo_repair_execution_preflight_ready"),
        receiver_smoke_packet=_receiver_smoke(),
        receiver_scaffold_present=True,
        api_route_registered=True,
        api_operations_route_registered=True,
        local_status_cli_present=True,
        public_registration_requested=True,
        registration_approval_token=REGISTRATION_APPROVAL_TOKEN,
        outbound_email_approval_token=OUTBOUND_EMAIL_APPROVAL_TOKEN,
    )

    assert payload["summary"]["status"] == "cameo_public_registration_preflight_ready"
    assert payload["summary"]["public_registration_allowed"] is True
    assert payload["summary"]["server_registration_mutated"] is False
    assert payload["blockers"] == []


def test_cameo_capability_preflight_blocks_unsafe_capability_flags() -> None:
    payload = build_cameo_capability_preflight(
        validation_readiness_packet=_validation("cameo_validation_evidence_ready"),
        repair_execution_preflight_packet=_repair("cameo_repair_execution_preflight_ready"),
        receiver_scaffold_present=True,
        api_route_registered=True,
        api_operations_route_registered=True,
        local_status_cli_present=True,
        outbound_email_requested=True,
        prediction_generation_requested=True,
    )

    assert payload["summary"]["status"] == "blocked_cameo_capability_preflight"
    codes = {blocker["code"] for blocker in payload["blockers"]}
    assert "outbound_email_disabled_failed" in codes
    assert "prediction_generation_disabled_failed" in codes
