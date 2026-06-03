from __future__ import annotations

import json
from pathlib import Path

from betelgeuze_cameo.architecture_validation import build_cameo_architecture_validation_contract
from tools import build_cameo_architecture_validation_contract as tool


def _packet(summary: dict) -> dict:
    return {"summary": summary}


def _threshold_policy_packet() -> dict:
    return _packet(
        {
            "status": "cameo_performance_threshold_policy_ready",
            "threshold_policy_ready": True,
            "profile_name": "product_grade_model1",
            "min_model1_lddt": 0.7,
            "min_model1_tm_score": 0.5,
            "min_model1_qs_score": 0.0,
            "max_model1_rmsd_A": 5.0,
        }
    )


def _service_boundary_packet() -> dict:
    return _packet(
        {
            "status": "cameo_service_boundary_contract_ready",
            "service_boundary_ready": True,
            "api_route_count": 8,
            "expected_api_route_count": 8,
            "missing_api_route_count": 0,
            "cli_command_count": 13,
            "expected_cli_command_count": 13,
            "missing_cli_command_count": 0,
            "artifact_registry_mismatch_count": 0,
        }
    )


def _api_contract_packet() -> dict:
    return _packet(
        {
            "status": "cameo_api_contract_ready",
            "api_contract_ready": True,
            "expected_route_count": 8,
            "missing_route_count": 0,
            "status_response_missing_key_count": 0,
        }
    )


def test_cameo_architecture_validation_contract_reports_local_protocol_without_official_claim() -> None:
    payload = build_cameo_architecture_validation_contract(
        product_architecture_packet=_packet({"status": "blocked_product_architecture_contract", "local_architecture_surface_ready": True}),
        validation_operations_packet=_packet({"status": "blocked_cameo_validation_operations_dossier", "stage_count": 6}),
        validation_readiness_packet=_packet(
            {"status": "blocked_cameo_validation_readiness", "official_cameo_results_used": False}
        ),
        performance_threshold_policy_packet=_threshold_policy_packet(),
        performance_scorecard_packet={},
        official_results_packet=_packet(
            {
                "status": "blocked_cameo_official_results_intake",
                "accepted_official_result_count": 0,
                "model1_official_result_ready": False,
            }
        ),
        public_registration_packet=_packet(
            {"status": "blocked_cameo_public_registration_approval_gate", "authorized_for_registration_review": False}
        ),
        service_boundary_packet=_service_boundary_packet(),
        api_contract_packet=_api_contract_packet(),
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_cameo_architecture_validation_contract"
    assert summary["local_validation_protocol_ready"] is True
    assert summary["cameo_service_boundary_ready"] is True
    assert summary["cameo_api_contract_ready"] is True
    assert summary["performance_threshold_policy_ready"] is True
    assert summary["performance_threshold_profile_name"] == "product_grade_model1"
    assert summary["cameo_architecture_validation_ready"] is False
    assert summary["official_cameo_results_used"] is False
    assert summary["server_registration_mutated"] is False
    assert summary["prediction_generation_enabled"] is False
    assert summary["outbound_email_enabled"] is False
    assert summary["native_local_accuracy_used"] is False
    assert summary["external_state_mutated"] is False
    rows_by_lane = {row["lane_id"]: row["status"] for row in payload["rows"]}
    assert rows_by_lane["cameo_service_boundary_contract"] == "ready"
    assert rows_by_lane["cameo_api_contract"] == "ready"
    assert rows_by_lane["cameo_performance_threshold_policy"] == "ready"
    assert rows_by_lane["cameo_performance_scorecard"] == "blocked"


def test_cameo_architecture_validation_contract_ready_requires_official_evidence_and_registration() -> None:
    payload = build_cameo_architecture_validation_contract(
        product_architecture_packet=_packet({"status": "product_architecture_contract_ready", "local_architecture_surface_ready": True}),
        validation_operations_packet=_packet({"status": "cameo_validation_operations_dossier_ready", "stage_count": 6}),
        validation_readiness_packet=_packet(
            {"status": "cameo_validation_evidence_ready", "official_cameo_results_used": True}
        ),
        performance_threshold_policy_packet=_threshold_policy_packet(),
        performance_scorecard_packet=_packet(
            {
                "status": "cameo_performance_evidence_ready",
                "official_cameo_results_used": True,
                "model1_official_result_count": 1,
            }
        ),
        official_results_packet=_packet(
            {
                "status": "cameo_official_results_intake_ready",
                "accepted_official_result_count": 1,
                "model1_official_result_ready": True,
            }
        ),
        public_registration_packet=_packet(
            {"status": "cameo_public_registration_approval_ready", "authorized_for_registration_review": True}
        ),
        service_boundary_packet=_service_boundary_packet(),
        api_contract_packet=_api_contract_packet(),
    )

    assert payload["summary"]["status"] == "cameo_architecture_validation_contract_ready"
    assert payload["summary"]["cameo_architecture_validation_ready"] is True
    assert payload["blockers"] == []
    assert payload["approval_required"] == []


def test_cameo_architecture_validation_contract_blocks_missing_service_boundary() -> None:
    payload = build_cameo_architecture_validation_contract(
        product_architecture_packet=_packet({"status": "product_architecture_contract_ready", "local_architecture_surface_ready": True}),
        validation_operations_packet=_packet({"status": "cameo_validation_operations_dossier_ready", "stage_count": 6}),
        validation_readiness_packet=_packet(
            {"status": "cameo_validation_evidence_ready", "official_cameo_results_used": True}
        ),
        performance_threshold_policy_packet=_threshold_policy_packet(),
        performance_scorecard_packet=_packet(
            {
                "status": "cameo_performance_evidence_ready",
                "official_cameo_results_used": True,
                "model1_official_result_count": 1,
            }
        ),
        official_results_packet=_packet(
            {
                "status": "cameo_official_results_intake_ready",
                "accepted_official_result_count": 1,
                "model1_official_result_ready": True,
            }
        ),
        public_registration_packet=_packet(
            {"status": "cameo_public_registration_approval_ready", "authorized_for_registration_review": True}
        ),
        api_contract_packet=_api_contract_packet(),
    )

    assert payload["summary"]["status"] == "blocked_cameo_architecture_validation_contract"
    assert payload["summary"]["local_validation_protocol_ready"] is False
    assert payload["summary"]["cameo_service_boundary_ready"] is False
    rows_by_lane = {row["lane_id"]: row["status"] for row in payload["rows"]}
    assert rows_by_lane["cameo_service_boundary_contract"] == "blocked"


def test_cameo_architecture_validation_tool_writes_outputs(tmp_path: Path) -> None:
    packets = {
        "architecture": _packet({"status": "blocked_product_architecture_contract", "local_architecture_surface_ready": True}),
        "operations": _packet({"status": "blocked_cameo_validation_operations_dossier", "stage_count": 6}),
        "readiness": _packet({"status": "blocked_cameo_validation_readiness", "official_cameo_results_used": False}),
        "threshold_policy": _threshold_policy_packet(),
        "performance": {},
        "official": _packet({"status": "blocked_cameo_official_results_intake"}),
        "registration": _packet({"status": "blocked_cameo_public_registration_approval_gate"}),
        "service_boundary": _service_boundary_packet(),
        "api_contract": _api_contract_packet(),
    }
    paths: dict[str, Path] = {}
    for name, payload in packets.items():
        paths[name] = tmp_path / f"{name}.json"
        paths[name].write_text(json.dumps(payload) + "\n", encoding="utf-8")
    out_json = tmp_path / "cameo_architecture.json"
    out_csv = tmp_path / "cameo_architecture.csv"
    out_md = tmp_path / "cameo_architecture.md"

    tool.main(
        [
            "--product-architecture-json",
            str(paths["architecture"]),
            "--validation-operations-json",
            str(paths["operations"]),
            "--validation-readiness-json",
            str(paths["readiness"]),
            "--performance-threshold-policy-json",
            str(paths["threshold_policy"]),
            "--performance-scorecard-json",
            str(paths["performance"]),
            "--official-results-json",
            str(paths["official"]),
            "--public-registration-json",
            str(paths["registration"]),
            "--service-boundary-json",
            str(paths["service_boundary"]),
            "--api-contract-json",
            str(paths["api_contract"]),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    summary = json.loads(out_json.read_text(encoding="utf-8"))["summary"]
    assert summary["local_validation_protocol_ready"] is True
    assert summary["cameo_architecture_validation_ready"] is False
    assert out_csv.read_text(encoding="utf-8").startswith("lane_id,status,")
    assert "CAMEO Architecture Validation Contract" in out_md.read_text(encoding="utf-8")
