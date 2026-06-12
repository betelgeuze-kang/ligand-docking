from __future__ import annotations

import json
from pathlib import Path

from tools import build_cameo_validation_operations_dossier as mod


def _input_kit() -> dict:
    return {
        "summary": {"status": "cameo_operator_input_kit_ready", "required_template_count": 3},
        "rows": [{"required_now": True}, {"required_now": True}, {"required_now": True}],
    }


def _input_validation(status: str = "blocked_cameo_operator_input_validation") -> dict:
    return {
        "summary": {
            "status": status,
            "blocker_count": 3 if status.startswith("blocked") else 0,
            "native_local_accuracy_used": False,
            "outbound_email_enabled": False,
            "external_state_mutated": False,
        }
    }


def _repair_preflight(status: str = "blocked_cameo_repair_execution_preflight") -> dict:
    return {
        "summary": {
            "status": status,
            "blocker_count": 4 if status.startswith("blocked") else 0,
            "source_operator_input_validation_status": "blocked_cameo_operator_input_validation",
            "outbound_email_enabled": False,
            "external_state_mutated": False,
        }
    }


def _readiness(status: str = "blocked_cameo_validation_readiness") -> dict:
    return {
        "summary": {
            "status": status,
            "blocker_count": 4 if status.startswith("blocked") else 0,
            "ready_stage_count": 0 if status.startswith("blocked") else 4,
            "stage_count": 4,
            "missing_stage_count": 4 if status.startswith("blocked") else 0,
            "official_cameo_results_used": status == "cameo_validation_evidence_ready",
            "native_local_accuracy_used": False,
            "outbound_email_enabled": False,
            "external_state_mutated": False,
        }
    }


def _official_results_intake(ready: bool = False) -> dict:
    return {
        "summary": {
            "status": "cameo_official_results_intake_ready" if ready else "blocked_cameo_official_results_intake",
            "blocker_count": 0 if ready else 2,
            "model1_official_result_ready": ready,
            "accepted_official_result_count": 1 if ready else 0,
            "native_local_accuracy_used": False,
            "official_cameo_results_used": ready,
            "outbound_email_enabled": False,
            "external_state_mutated": False,
        }
    }


def _evidence_integrity() -> dict:
    return {
        "summary": {
            "status": "cameo_evidence_integrity_contract_ready",
            "evidence_integrity_ready": True,
            "blocker_count": 0,
            "official_results_pending_honest": True,
            "official_result_schema_visible": True,
            "no_local_native_accuracy_substitution": True,
            "external_mutation_flags_clear": True,
            "registration_and_email_gated": True,
            "native_local_accuracy_used": False,
            "outbound_email_enabled": False,
            "external_state_mutated": False,
        }
    }


def _runtime_repair(install_approval_required: bool = True) -> dict:
    return {
        "summary": {
            "status": "cameo_runtime_repair_work_order_ready",
            "install_approval_required": install_approval_required,
            "approval_token_required": "APPROVE_API_DEPENDENCY_INSTALL" if install_approval_required else "",
            "outbound_email_enabled": False,
            "external_state_mutated": False,
        }
    }


def _api_dependency(status: str = "blocked_cameo_api_dependency_readiness") -> dict:
    return {
        "summary": {
            "status": status,
            "blocker_count": 4 if status.startswith("blocked") else 0,
            "outbound_email_enabled": False,
            "external_state_mutated": False,
        }
    }


def _receiver_smoke(status: str = "blocked_cameo_receiver_smoke") -> dict:
    return {
        "summary": {
            "status": status,
            "blocker_count": 1 if status.startswith("blocked") else 0,
            "outbound_email_enabled": False,
            "external_state_mutated": False,
        }
    }


def _capability(allowed: bool = False) -> dict:
    return {
        "summary": {
            "status": "cameo_development_capability_preflight_ready" if allowed else "blocked_cameo_capability_preflight",
            "public_registration_allowed": allowed,
            "public_registration_blocker_count": 0 if allowed else 4,
            "receiver_smoke_post_200_ok": allowed,
            "public_registration_requested": False,
            "registration_approval_token_required": "APPROVE_CAMEO_SERVER_REGISTRATION",
            "outbound_email_approval_token_required": "APPROVE_CAMEO_OUTBOUND_EMAIL",
            "native_local_accuracy_used": False,
            "outbound_email_enabled": False,
            "external_state_mutated": False,
        }
    }


def _outbound_email_draft(ready: bool = True) -> dict:
    return {
        "summary": {
            "status": "cameo_outbound_email_draft_ready" if ready else "blocked_cameo_outbound_email_draft",
            "blocker_count": 0 if ready else 1,
            "draft_eml_written": ready,
            "email_sent": False,
            "smtp_connection_opened": False,
            "outbound_email_enabled": False,
            "external_state_mutated": False,
        }
    }


def _outbound_email_send_preflight(ready: bool = True) -> dict:
    return {
        "summary": {
            "status": "cameo_outbound_email_send_preflight_ready" if ready else "blocked_cameo_outbound_email_send_preflight",
            "blocker_count": 0 if ready else 1,
            "authorized_for_separate_operator_send": ready,
            "email_sent": False,
            "smtp_connection_opened": False,
            "outbound_email_enabled": False,
            "external_state_mutated": False,
        }
    }


def _official_result_fetch_preflight(ready: bool = True) -> dict:
    return {
        "summary": {
            "status": "cameo_official_result_fetch_preflight_ready" if ready else "blocked_cameo_official_result_fetch_preflight",
            "blocker_count": 0 if ready else 1,
            "authorized_for_separate_operator_fetch": ready,
            "network_request_opened": False,
            "official_results_fetched": False,
            "native_local_accuracy_used": False,
            "external_state_mutated": False,
        }
    }


def test_cameo_validation_operations_dossier_consolidates_blocked_current_lane() -> None:
    payload = mod.build_cameo_validation_operations_dossier(
        input_kit_packet=_input_kit(),
        input_validation_packet=_input_validation(),
        repair_preflight_packet=_repair_preflight(),
        readiness_packet=_readiness(),
        official_results_intake_packet=_official_results_intake(),
        evidence_integrity_packet=_evidence_integrity(),
        runtime_repair_packet=_runtime_repair(),
        api_dependency_packet=_api_dependency(),
        receiver_smoke_packet=_receiver_smoke(),
        capability_preflight_packet=_capability(),
        outbound_email_draft_packet=_outbound_email_draft(),
        outbound_email_send_preflight_packet=_outbound_email_send_preflight(),
        official_result_fetch_preflight_packet=_official_result_fetch_preflight(),
    )
    summary = payload["summary"]

    assert summary["status"] == "blocked_cameo_validation_operations_dossier"
    assert summary["blocked_stage_count"] == 5
    assert summary["approval_required_stage_count"] == 1
    assert summary["first_blocked_stage_id"] == "operator_inputs"
    assert summary["first_blocked_stage_source_status"] == "blocked_cameo_operator_input_validation"
    assert summary["first_blocked_stage_artifact"] == "runs/cameo_operator_input_validation_current.json"
    assert summary["first_blocked_stage_blocker_count"] == 3
    assert summary["first_approval_required_stage_id"] == "runtime_receiver_smoke"
    assert summary["first_approval_required_stage_token_required"] == "APPROVE_API_DEPENDENCY_INSTALL"
    assert summary["operator_input_required_count"] == 3
    assert summary["official_results_intake_status"] == "blocked_cameo_official_results_intake"
    assert summary["official_results_intake_ready"] is False
    assert summary["official_results_intake_blocker_count"] == 2
    assert summary["official_model1_result_ready"] is False
    assert summary["official_result_required"] is True
    assert summary["official_result_fetch_preflight_status"] == "cameo_official_result_fetch_preflight_ready"
    assert summary["official_result_fetch_preflight_ready"] is True
    assert summary["official_result_fetch_preflight_authorized"] is True
    assert summary["official_result_fetch_preflight_network_request_opened"] is False
    assert summary["official_result_fetch_preflight_results_fetched"] is False
    assert summary["evidence_integrity_ready"] is True
    assert summary["official_results_pending_honest"] is True
    assert summary["no_local_native_accuracy_substitution"] is True
    assert summary["public_registration_allowed"] is False
    assert summary["outbound_email_draft_status"] == "cameo_outbound_email_draft_ready"
    assert summary["outbound_email_draft_ready"] is True
    assert summary["outbound_email_draft_eml_written"] is True
    assert summary["outbound_email_draft_email_sent"] is False
    assert summary["outbound_email_draft_smtp_connection_opened"] is False
    assert summary["outbound_email_send_preflight_status"] == "cameo_outbound_email_send_preflight_ready"
    assert summary["outbound_email_send_preflight_ready"] is True
    assert summary["outbound_email_send_preflight_authorized"] is True
    assert summary["outbound_email_send_preflight_email_sent"] is False
    assert summary["outbound_email_send_preflight_smtp_connection_opened"] is False
    assert summary["package_install_executed"] is False
    assert summary["server_registration_mutated"] is False
    assert summary["outbound_email_enabled"] is False
    assert set(summary["approval_tokens_required"]) == {
        "APPROVE_API_DEPENDENCY_INSTALL",
        "APPROVE_CAMEO_OUTBOUND_EMAIL",
        "APPROVE_CAMEO_SERVER_REGISTRATION",
    }
    assert any(row["stage"] == "runtime_receiver_smoke" and row["status"] == "approval_required" for row in payload["rows"])
    assert any(row["stage"] == "official_result_fetch_preflight" and row["status"] == "ready" for row in payload["rows"])
    assert any(row["stage"] == "outbound_email_draft" and row["status"] == "ready" for row in payload["rows"])
    assert any(row["stage"] == "outbound_email_send_preflight" and row["status"] == "ready" for row in payload["rows"])


def test_cameo_validation_operations_dossier_names_current_fetch_preflight_blocker() -> None:
    payload = mod.build_cameo_validation_operations_dossier(
        input_kit_packet=_input_kit(),
        input_validation_packet=_input_validation("cameo_operator_inputs_ready_pending_official_results"),
        repair_preflight_packet=_repair_preflight("cameo_repair_execution_not_required"),
        readiness_packet=_readiness("cameo_validation_evidence_ready"),
        official_results_intake_packet=_official_results_intake(True),
        evidence_integrity_packet=_evidence_integrity(),
        runtime_repair_packet=_runtime_repair(False),
        api_dependency_packet=_api_dependency("cameo_api_dependency_ready"),
        receiver_smoke_packet=_receiver_smoke("cameo_receiver_smoke_ready"),
        capability_preflight_packet=_capability(True),
        outbound_email_draft_packet=_outbound_email_draft(),
        outbound_email_send_preflight_packet=_outbound_email_send_preflight(),
        official_result_fetch_preflight_packet=_official_result_fetch_preflight(False),
    )
    summary = payload["summary"]

    assert summary["status"] == "blocked_cameo_validation_operations_dossier"
    assert summary["blocked_stage_count"] == 1
    assert summary["approval_required_stage_count"] == 1
    assert summary["first_blocked_stage_id"] == "official_result_fetch_preflight"
    assert summary["first_blocked_stage_source_status"] == "blocked_cameo_official_result_fetch_preflight"
    assert summary["first_blocked_stage_artifact"] == "runs/cameo_official_result_fetch_preflight_current.json"
    assert summary["first_blocked_stage_blocker_count"] == 1
    assert summary["first_blocked_stage_recommended_action"].startswith("Fill the fetch preflight CSV")
    assert summary["first_approval_required_stage_id"] == "public_registration_and_email"
    assert summary["first_approval_required_stage_token_required"] == (
        "APPROVE_CAMEO_SERVER_REGISTRATION;APPROVE_CAMEO_OUTBOUND_EMAIL"
    )
    assert summary["next_required_step"] == summary["first_blocked_stage_recommended_action"]


def test_cameo_validation_operations_dossier_ready_when_all_operations_clear() -> None:
    payload = mod.build_cameo_validation_operations_dossier(
        input_kit_packet=_input_kit(),
        input_validation_packet=_input_validation("cameo_operator_inputs_ready"),
        repair_preflight_packet=_repair_preflight("cameo_repair_execution_preflight_ready"),
        readiness_packet=_readiness("cameo_validation_evidence_ready"),
        official_results_intake_packet=_official_results_intake(True),
        evidence_integrity_packet=_evidence_integrity(),
        runtime_repair_packet=_runtime_repair(False),
        api_dependency_packet=_api_dependency("cameo_api_dependency_ready"),
        receiver_smoke_packet=_receiver_smoke("cameo_receiver_smoke_ready"),
        capability_preflight_packet=_capability(True),
        outbound_email_draft_packet=_outbound_email_draft(),
        outbound_email_send_preflight_packet=_outbound_email_send_preflight(),
        official_result_fetch_preflight_packet=_official_result_fetch_preflight(),
    )

    assert payload["summary"]["status"] == "blocked_cameo_validation_operations_dossier"
    assert payload["summary"]["blocked_stage_count"] == 0
    assert payload["summary"]["approval_required_stage_count"] == 1
    assert payload["summary"]["official_result_required"] is False
    assert payload["summary"]["official_results_intake_ready"] is True
    assert payload["summary"]["official_result_fetch_preflight_ready"] is True
    assert payload["summary"]["outbound_email_draft_ready"] is True
    assert payload["summary"]["outbound_email_send_preflight_ready"] is True
    assert payload["summary"]["first_blocked_stage_id"] == ""
    assert payload["summary"]["first_approval_required_stage_id"] == "public_registration_and_email"
    assert next(row for row in payload["rows"] if row["stage"] == "public_registration_and_email")["status"] == "approval_required"


def test_cameo_validation_operations_dossier_suppresses_stale_install_approval_when_runtime_ready() -> None:
    payload = mod.build_cameo_validation_operations_dossier(
        input_kit_packet=_input_kit(),
        input_validation_packet=_input_validation("cameo_operator_inputs_ready_pending_official_results"),
        repair_preflight_packet=_repair_preflight("cameo_repair_execution_not_required"),
        readiness_packet=_readiness("cameo_validation_pending_official_results"),
        official_results_intake_packet=_official_results_intake(False),
        evidence_integrity_packet=_evidence_integrity(),
        runtime_repair_packet=_runtime_repair(True),
        api_dependency_packet=_api_dependency("cameo_api_dependency_ready"),
        receiver_smoke_packet=_receiver_smoke("cameo_receiver_smoke_ready"),
        capability_preflight_packet=_capability(False),
        outbound_email_draft_packet=_outbound_email_draft(),
        outbound_email_send_preflight_packet=_outbound_email_send_preflight(),
        official_result_fetch_preflight_packet=_official_result_fetch_preflight(),
    )

    runtime_row = next(row for row in payload["rows"] if row["stage"] == "runtime_receiver_smoke")
    assert runtime_row["status"] == "ready"
    assert runtime_row["approval_token_required"] == ""
    assert payload["summary"]["runtime_install_approval_required"] is False
    assert "APPROVE_API_DEPENDENCY_INSTALL" not in payload["summary"]["approval_tokens_required"]


def test_cameo_validation_operations_dossier_accepts_repair_not_required() -> None:
    payload = mod.build_cameo_validation_operations_dossier(
        input_kit_packet=_input_kit(),
        input_validation_packet=_input_validation("cameo_operator_inputs_ready_pending_official_results"),
        repair_preflight_packet=_repair_preflight("cameo_repair_execution_not_required"),
        readiness_packet=_readiness("cameo_validation_pending_official_results"),
        official_results_intake_packet=_official_results_intake(False),
        evidence_integrity_packet=_evidence_integrity(),
        runtime_repair_packet=_runtime_repair(),
        api_dependency_packet=_api_dependency(),
        receiver_smoke_packet=_receiver_smoke(),
        capability_preflight_packet=_capability(),
        outbound_email_draft_packet=_outbound_email_draft(),
        outbound_email_send_preflight_packet=_outbound_email_send_preflight(),
        official_result_fetch_preflight_packet=_official_result_fetch_preflight(),
    )

    row = next(row for row in payload["rows"] if row["stage"] == "repair_execution_preflight")
    assert row["status"] == "ready"
    assert payload["summary"]["operator_input_required_count"] == 0
    assert payload["summary"]["blocked_stage_count"] == 2


def test_cameo_validation_operations_dossier_tool_writes_outputs(tmp_path: Path) -> None:
    paths = {
        "input_kit": tmp_path / "input_kit.json",
        "input_validation": tmp_path / "input_validation.json",
        "repair_preflight": tmp_path / "repair_preflight.json",
        "readiness": tmp_path / "readiness.json",
        "official_results": tmp_path / "official_results.json",
        "evidence_integrity": tmp_path / "evidence_integrity.json",
        "runtime_repair": tmp_path / "runtime_repair.json",
        "api_dependency": tmp_path / "api_dependency.json",
        "receiver_smoke": tmp_path / "receiver_smoke.json",
        "capability": tmp_path / "capability.json",
        "outbound_email_draft": tmp_path / "outbound_email_draft.json",
        "outbound_email_send_preflight": tmp_path / "outbound_email_send_preflight.json",
        "official_result_fetch_preflight": tmp_path / "official_result_fetch_preflight.json",
    }
    paths["input_kit"].write_text(json.dumps(_input_kit()) + "\n", encoding="utf-8")
    paths["input_validation"].write_text(json.dumps(_input_validation()) + "\n", encoding="utf-8")
    paths["repair_preflight"].write_text(json.dumps(_repair_preflight()) + "\n", encoding="utf-8")
    paths["readiness"].write_text(json.dumps(_readiness()) + "\n", encoding="utf-8")
    paths["official_results"].write_text(json.dumps(_official_results_intake()) + "\n", encoding="utf-8")
    paths["evidence_integrity"].write_text(json.dumps(_evidence_integrity()) + "\n", encoding="utf-8")
    paths["runtime_repair"].write_text(json.dumps(_runtime_repair()) + "\n", encoding="utf-8")
    paths["api_dependency"].write_text(json.dumps(_api_dependency()) + "\n", encoding="utf-8")
    paths["receiver_smoke"].write_text(json.dumps(_receiver_smoke()) + "\n", encoding="utf-8")
    paths["capability"].write_text(json.dumps(_capability()) + "\n", encoding="utf-8")
    paths["outbound_email_draft"].write_text(json.dumps(_outbound_email_draft()) + "\n", encoding="utf-8")
    paths["outbound_email_send_preflight"].write_text(
        json.dumps(_outbound_email_send_preflight()) + "\n", encoding="utf-8"
    )
    paths["official_result_fetch_preflight"].write_text(
        json.dumps(_official_result_fetch_preflight()) + "\n", encoding="utf-8"
    )
    out_json = tmp_path / "dossier.json"
    out_csv = tmp_path / "dossier.csv"
    out_md = tmp_path / "dossier.md"

    mod.main(
        [
            "--input-kit-json",
            str(paths["input_kit"]),
            "--input-validation-json",
            str(paths["input_validation"]),
            "--repair-preflight-json",
            str(paths["repair_preflight"]),
            "--readiness-json",
            str(paths["readiness"]),
            "--official-results-intake-json",
            str(paths["official_results"]),
            "--evidence-integrity-json",
            str(paths["evidence_integrity"]),
            "--runtime-repair-json",
            str(paths["runtime_repair"]),
            "--api-dependency-json",
            str(paths["api_dependency"]),
            "--receiver-smoke-json",
            str(paths["receiver_smoke"]),
            "--capability-preflight-json",
            str(paths["capability"]),
            "--outbound-email-draft-json",
            str(paths["outbound_email_draft"]),
            "--outbound-email-send-preflight-json",
            str(paths["outbound_email_send_preflight"]),
            "--official-result-fetch-preflight-json",
            str(paths["official_result_fetch_preflight"]),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "blocked_cameo_validation_operations_dossier"
    assert out_csv.read_text(encoding="utf-8").startswith("priority,stage,")
    assert "CAMEO Validation Operations Dossier" in out_md.read_text(encoding="utf-8")
