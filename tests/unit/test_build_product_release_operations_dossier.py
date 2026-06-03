from __future__ import annotations

import json
from pathlib import Path

from tools import build_product_release_operations_dossier as mod


def _readiness() -> dict:
    return {
        "summary": {
            "status": "product_handoff_ready",
            "target_id": "ADRB2",
            "family": "gpcr",
            "ligand_count": 1,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
        }
    }


def _capability_surface(ready: bool = True) -> dict:
    return {
        "summary": {
            "status": "product_capability_surface_contract_ready" if ready else "blocked_product_capability_surface_contract",
            "blocked_capability_count": 0 if ready else 2,
            "structure_analysis_capability_ready": ready,
            "ligand_docking_capability_ready": ready,
            "api_surface_ready": ready,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
        }
    }


def _operational_quality(ready: bool = True) -> dict:
    return {
        "summary": {
            "status": "product_operational_quality_contract_ready" if ready else "blocked_product_operational_quality_contract",
            "operational_quality_ready": ready,
            "blocker_count": 0 if ready else 2,
            "fail_closed_docking_intake_ready": ready,
            "ledger_payload_privacy_ready": ready,
            "request_traceability_ready": ready,
            "scope_limit_enforcement_ready": ready,
            "heavy_artifact_policy_ready": ready,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
        }
    }


def _architecture(ready: bool = False) -> dict:
    return {
        "summary": {
            "status": "product_architecture_contract_ready" if ready else "blocked_product_architecture_contract",
            "local_architecture_surface_ready": True,
            "architecture_release_ready": ready,
            "blocked_lane_count": 0 if ready else 1,
            "approval_required_lane_count": 0 if ready else 2,
            "product_service_boundary_ready": True,
            "product_api_contract_ready": True,
            "cameo_architecture_validation_ready": ready,
            "cameo_official_validation_evidence_ready": ready,
            "cameo_receiver_smoke_ready": ready,
            "cameo_receiver_smoke_status": "cameo_receiver_smoke_ready" if ready else "blocked_cameo_receiver_smoke",
            "cameo_api_dependency_ready": ready,
            "cameo_api_dependency_status": "cameo_api_dependency_ready" if ready else "blocked_cameo_api_dependency_readiness",
            "cameo_public_registration_allowed": ready,
            "cameo_public_registration_blocker_count": 0 if ready else 4,
            "cameo_registration_approval_token_count": 0 if ready else 2,
            "cameo_registration_approval_tokens_required": []
            if ready
            else ["APPROVE_CAMEO_SERVER_REGISTRATION", "APPROVE_CAMEO_OUTBOUND_EMAIL"],
            "cleanup_postcheck_contract_ready": True,
            "cleanup_postcheck_blocked_row_count": 0,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
        }
    }


def _preflight() -> dict:
    return {
        "summary": {
            "status": "product_execution_preflight_ready",
            "target_id": "ADRB2",
            "family": "gpcr",
            "blocker_count": 0,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
        }
    }


def _work_order() -> dict:
    return {
        "summary": {
            "status": "product_execution_work_order_ready",
            "target_id": "ADRB2",
            "family": "gpcr",
            "bundle_tag": "product_gpcr_adrb2",
            "blocker_count": 0,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
        }
    }


def _approval_gate(authorized: bool = False) -> dict:
    return {
        "summary": {
            "status": "product_execution_operator_approval_gate_ready" if authorized else "blocked_product_execution_operator_approval_gate",
            "authorized_for_execution": authorized,
            "awaiting_operator_approval_row_count": 0 if authorized else 1,
            "operator_approval_csv_present": authorized,
            "approval_token_required": "APPROVE_PRODUCT_DOCKING_EXECUTION",
            "blocker_count": 0 if authorized else 2,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
        }
    }


def _bundle_contract() -> dict:
    return {
        "summary": {
            "status": "product_bundle_contract_ready",
            "bundle_tag": "product_gpcr_adrb2",
            "expected_bundle_dir": "runs/local_delivery/bundle_product_gpcr_adrb2",
            "blocker_count": 0,
            "bundle_assembled": False,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
        }
    }


def _delivery(ready: bool = False) -> dict:
    return {
        "summary": {
            "status": "product_delivery_evidence_contract_ready",
            "bundle_assembled": ready,
            "bundle_validation_passed": ready,
            "delivery_ready_claim_allowed": ready,
            "warning_count": 0 if ready else 2,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
        }
    }


def _pilot(ready: bool = False) -> dict:
    return {
        "summary": {
            "status": "product_pilot_packet_ready" if ready else "product_pilot_packet_preflight_ready",
            "bundle_assembled": ready,
            "bundle_validation_passed": ready,
            "bundle_dir_exists": ready,
            "delivery_ready_claim_allowed": ready,
            "pilot_delivery_ready": ready,
            "warning_count": 0 if ready else 2,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
        }
    }


def _commercial_independence(ready: bool = False) -> dict:
    return {
        "summary": {
            "status": "product_commercial_independence_gate_ready" if ready else "blocked_product_commercial_independence_gate",
            "blocker_count": 0 if ready else 1,
            "commercial_independent_product_claim_allowed": ready,
            "license_present": ready,
            "runtime_requirements_present": True,
            "optional_profiles_separated": True,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
        }
    }


def _license_decision(ready: bool = False) -> dict:
    return {
        "summary": {
            "status": "product_license_decision_gate_ready" if ready else "blocked_product_license_decision_gate",
            "authorized_for_license_file_creation_review": ready,
            "operator_intake_csv_present": ready,
            "approval_token_required": "APPROVE_PRODUCT_LICENSE_FILE_CREATION",
            "missing_required_field_count": 0 if ready else 6,
            "blocker_count": 0 if ready else 4,
            "license_present": False,
            "execution_enabled": False,
            "license_file_written": False,
            "external_state_mutated": False,
        }
    }


def _license_options() -> dict:
    return {
        "summary": {
            "status": "product_license_decision_packet_ready",
            "option_count": 5,
            "license_file_written": False,
            "external_state_mutated": False,
        }
    }


def _license_file_work_order(ready: bool = False) -> dict:
    return {
        "summary": {
            "status": "product_license_file_creation_work_order_ready"
            if ready
            else "blocked_product_license_file_creation_work_order",
            "license_file_creation_review_ready": ready,
            "blocker_count": 0 if ready else 3,
            "approval_token_required": "APPROVE_PRODUCT_LICENSE_FILE_CREATION",
            "license_file_written": False,
            "external_state_mutated": False,
        }
    }


def test_product_release_operations_dossier_consolidates_blocked_current_lane() -> None:
    payload = mod.build_product_release_operations_dossier(
        readiness_packet=_readiness(),
        capability_surface_packet=_capability_surface(),
        operational_quality_packet=_operational_quality(),
        architecture_packet=_architecture(False),
        preflight_packet=_preflight(),
        work_order_packet=_work_order(),
        approval_gate_packet=_approval_gate(False),
        bundle_contract_packet=_bundle_contract(),
        delivery_evidence_packet=_delivery(False),
        pilot_packet=_pilot(False),
        commercial_independence_packet=_commercial_independence(False),
        license_decision_packet=_license_decision(False),
        license_decision_options_packet=_license_options(),
        license_file_work_order_packet=_license_file_work_order(False),
    )
    summary = payload["summary"]

    assert summary["status"] == "blocked_product_release_operations_dossier"
    assert summary["stage_count"] == 10
    assert summary["blocked_stage_count"] == 4
    assert summary["approval_required_stage_count"] == 2
    assert summary["capability_surface_ready"] is True
    assert summary["operational_quality_ready"] is True
    assert summary["source_operational_quality_status"] == "product_operational_quality_contract_ready"
    assert summary["operational_quality_blocker_count"] == 0
    assert summary["architecture_contract_ready"] is False
    assert summary["source_architecture_status"] == "blocked_product_architecture_contract"
    assert summary["architecture_local_surface_ready"] is True
    assert summary["architecture_release_ready"] is False
    assert summary["architecture_blocked_lane_count"] == 1
    assert summary["architecture_approval_required_lane_count"] == 2
    assert summary["product_service_boundary_ready"] is True
    assert summary["product_api_contract_ready"] is True
    assert summary["cameo_architecture_validation_ready"] is False
    assert summary["cameo_official_validation_evidence_ready"] is False
    assert summary["cameo_receiver_smoke_ready"] is False
    assert summary["cameo_receiver_smoke_status"] == "blocked_cameo_receiver_smoke"
    assert summary["cameo_api_dependency_ready"] is False
    assert summary["cameo_api_dependency_status"] == "blocked_cameo_api_dependency_readiness"
    assert summary["cameo_public_registration_allowed"] is False
    assert summary["cameo_public_registration_blocker_count"] == 4
    assert summary["cameo_registration_approval_token_count"] == 2
    assert summary["cameo_registration_approval_tokens_required"] == [
        "APPROVE_CAMEO_SERVER_REGISTRATION",
        "APPROVE_CAMEO_OUTBOUND_EMAIL",
    ]
    assert summary["cleanup_postcheck_contract_ready"] is True
    assert summary["cleanup_postcheck_blocked_row_count"] == 0
    assert summary["structure_analysis_capability_ready"] is True
    assert summary["ligand_docking_capability_ready"] is True
    assert summary["commercial_independence_ready"] is False
    assert summary["license_present"] is False
    assert summary["source_license_decision_packet_status"] == "product_license_decision_packet_ready"
    assert summary["source_license_file_creation_work_order_status"] == "blocked_product_license_file_creation_work_order"
    assert summary["license_decision_option_count"] == 5
    assert summary["license_decision_packet_ready"] is True
    assert summary["license_authorized_for_file_creation_review"] is False
    assert summary["license_file_creation_review_ready"] is False
    assert summary["license_file_creation_work_order_blocker_count"] == 3
    assert summary["license_file_creation_work_order_artifact"] == "runs/product_license_file_creation_work_order_current.json"
    assert summary["approval_tokens_required"] == ["APPROVE_PRODUCT_DOCKING_EXECUTION", "APPROVE_PRODUCT_LICENSE_FILE_CREATION"]
    assert summary["authorized_for_execution"] is False
    assert summary["bundle_assembled"] is False
    assert summary["bundle_validation_passed"] is False
    assert summary["delivery_ready_claim_allowed"] is False
    assert summary["pilot_delivery_ready"] is False
    assert summary["external_state_mutated"] is False
    architecture_row = next(row for row in payload["rows"] if row["stage"] == "architecture_contract")
    assert "cameo_official_validation_evidence_ready=False" in architecture_row["reason"]
    assert "cameo_receiver_smoke_status=blocked_cameo_receiver_smoke" in architecture_row["reason"]
    assert "cameo_api_dependency_status=blocked_cameo_api_dependency_readiness" in architecture_row["reason"]
    assert "cameo_public_registration_allowed=False" in architecture_row["reason"]
    quality_row = next(row for row in payload["rows"] if row["stage"] == "operational_quality_contract")
    assert quality_row["status"] == "ready"
    assert "ledger_payload_privacy_ready=True" in quality_row["reason"]
    license_row = next(row for row in payload["rows"] if row["stage"] == "license_decision_review")
    assert "license_file_creation_work_order_status=blocked_product_license_file_creation_work_order" in license_row["reason"]
    assert "license_file_creation_review_ready=False" in license_row["reason"]
    assert license_row["source_artifact"].endswith("runs/product_license_file_creation_work_order_current.json")


def test_product_release_operations_dossier_ready_when_bundle_and_pilot_are_ready() -> None:
    payload = mod.build_product_release_operations_dossier(
        readiness_packet=_readiness(),
        capability_surface_packet=_capability_surface(),
        operational_quality_packet=_operational_quality(),
        architecture_packet=_architecture(True),
        preflight_packet=_preflight(),
        work_order_packet=_work_order(),
        approval_gate_packet=_approval_gate(True),
        bundle_contract_packet=_bundle_contract(),
        delivery_evidence_packet=_delivery(True),
        pilot_packet=_pilot(True),
        commercial_independence_packet=_commercial_independence(True),
        license_decision_packet=_license_decision(False),
        license_decision_options_packet=_license_options(),
        license_file_work_order_packet=_license_file_work_order(False),
    )

    assert payload["summary"]["status"] == "product_release_operations_dossier_ready"
    assert payload["summary"]["blocked_stage_count"] == 0
    assert payload["summary"]["approval_required_stage_count"] == 0
    assert payload["summary"]["pilot_delivery_ready"] is True


def test_product_release_operations_dossier_tool_writes_outputs(tmp_path: Path) -> None:
    paths = {
        "readiness": tmp_path / "readiness.json",
        "capability_surface": tmp_path / "capability_surface.json",
        "operational_quality": tmp_path / "operational_quality.json",
        "architecture": tmp_path / "architecture.json",
        "preflight": tmp_path / "preflight.json",
        "work_order": tmp_path / "work_order.json",
        "approval_gate": tmp_path / "approval_gate.json",
        "bundle_contract": tmp_path / "bundle_contract.json",
        "delivery": tmp_path / "delivery.json",
        "pilot": tmp_path / "pilot.json",
        "commercial": tmp_path / "commercial.json",
        "license": tmp_path / "license.json",
        "license_options": tmp_path / "license_options.json",
        "license_work_order": tmp_path / "license_work_order.json",
    }
    paths["readiness"].write_text(json.dumps(_readiness()) + "\n", encoding="utf-8")
    paths["capability_surface"].write_text(json.dumps(_capability_surface()) + "\n", encoding="utf-8")
    paths["operational_quality"].write_text(json.dumps(_operational_quality()) + "\n", encoding="utf-8")
    paths["architecture"].write_text(json.dumps(_architecture(False)) + "\n", encoding="utf-8")
    paths["preflight"].write_text(json.dumps(_preflight()) + "\n", encoding="utf-8")
    paths["work_order"].write_text(json.dumps(_work_order()) + "\n", encoding="utf-8")
    paths["approval_gate"].write_text(json.dumps(_approval_gate(False)) + "\n", encoding="utf-8")
    paths["bundle_contract"].write_text(json.dumps(_bundle_contract()) + "\n", encoding="utf-8")
    paths["delivery"].write_text(json.dumps(_delivery(False)) + "\n", encoding="utf-8")
    paths["pilot"].write_text(json.dumps(_pilot(False)) + "\n", encoding="utf-8")
    paths["commercial"].write_text(json.dumps(_commercial_independence(False)) + "\n", encoding="utf-8")
    paths["license"].write_text(json.dumps(_license_decision(False)) + "\n", encoding="utf-8")
    paths["license_options"].write_text(json.dumps(_license_options()) + "\n", encoding="utf-8")
    paths["license_work_order"].write_text(json.dumps(_license_file_work_order(False)) + "\n", encoding="utf-8")
    out_json = tmp_path / "dossier.json"
    out_csv = tmp_path / "dossier.csv"
    out_md = tmp_path / "dossier.md"

    mod.main(
        [
            "--readiness-json",
            str(paths["readiness"]),
            "--capability-surface-json",
            str(paths["capability_surface"]),
            "--operational-quality-json",
            str(paths["operational_quality"]),
            "--architecture-json",
            str(paths["architecture"]),
            "--preflight-json",
            str(paths["preflight"]),
            "--work-order-json",
            str(paths["work_order"]),
            "--approval-gate-json",
            str(paths["approval_gate"]),
            "--bundle-contract-json",
            str(paths["bundle_contract"]),
            "--delivery-evidence-json",
            str(paths["delivery"]),
            "--pilot-packet-json",
            str(paths["pilot"]),
            "--commercial-independence-json",
            str(paths["commercial"]),
            "--license-decision-json",
            str(paths["license"]),
            "--license-decision-options-json",
            str(paths["license_options"]),
            "--license-file-work-order-json",
            str(paths["license_work_order"]),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "blocked_product_release_operations_dossier"
    assert out_csv.read_text(encoding="utf-8").startswith("priority,stage,")
    assert "Product Release Operations Dossier" in out_md.read_text(encoding="utf-8")
