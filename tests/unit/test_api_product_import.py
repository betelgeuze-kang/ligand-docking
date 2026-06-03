from __future__ import annotations

import asyncio
import importlib

import pytest


def test_api_product_router_is_registered_when_fastapi_is_available() -> None:
    pytest.importorskip("fastapi")
    main = importlib.import_module("api.main")
    product = importlib.import_module("api.product")

    paths = {route.path for route in main.app.routes}
    assert "/product/capabilities" in paths
    assert "/product/architecture" in paths
    assert "/product/service-boundary" in paths
    assert "/product/api-contract" in paths
    assert "/product/operational-quality" in paths
    assert "/product/operations" in paths
    assert "/product/license-decision" in paths
    assert "/product/license-options" in paths
    assert "/product/license-file-work-order" in paths
    assert "/product/commercial-independence" in paths
    assert "/product/release-readiness" in paths
    assert "/product/structure/analyze" in paths
    assert "/product/docking/jobs" in paths
    assert "/product/docking/jobs/{job_id}" in paths

    response = asyncio.run(product.get_product_capabilities())

    assert response["status"] == "product_capability_surface_contract_ready"
    assert response["structure_analysis_capability_ready"] is True
    assert response["ligand_docking_capability_ready"] is True
    assert response["product_service_boundary_endpoint_present"] is True
    assert response["product_api_contract_endpoint_present"] is True
    assert response["execution_enabled"] is False
    assert response["docking_results_emitted"] is False
    assert response["external_state_mutated"] is False

    structure = asyncio.run(
        product.analyze_product_structure(
            product.StructureAnalysisRequest(
                pdb_content="ATOM      1  CA  GLY A   1      12.104  13.207  14.321  1.00 10.00           C\n"
            )
        )
    )

    assert structure["status"] == "structure_analysis_ready"
    assert structure["atom_count"] == 1
    assert structure["chain_count"] == 1
    assert structure["execution_enabled"] is False
    assert structure["docking_results_emitted"] is False
    assert structure["external_state_mutated"] is False

    architecture = asyncio.run(product.get_product_architecture())

    assert architecture["status"] == "blocked_product_architecture_contract"
    assert architecture["local_architecture_surface_ready"] is True
    assert architecture["architecture_release_ready"] is False
    assert architecture["structure_analysis_product_surface_ready"] is True
    assert architecture["ligand_docking_execution_contract_ready"] is True
    assert architecture["product_service_boundary_ready"] is True
    assert architecture["product_api_contract_ready"] is True
    assert architecture["cameo_local_surface_ready"] is True
    assert architecture["cameo_service_boundary_ready"] is True
    assert architecture["cameo_service_boundary_status"] == "cameo_service_boundary_contract_ready"
    assert architecture["cameo_service_boundary_api_route_count"] == 9
    assert architecture["cameo_service_boundary_cli_command_count"] == 14
    assert architecture["cameo_api_contract_ready"] is True
    assert architecture["cameo_api_contract_status"] == "cameo_api_contract_ready"
    assert architecture["cameo_api_contract_expected_route_count"] == 9
    assert architecture["cameo_api_contract_missing_route_count"] == 0
    assert architecture["cameo_api_contract_status_response_missing_key_count"] == 0
    assert architecture["cameo_architecture_validation_ready"] is False
    assert architecture["cleanup_control_surface_ready"] is True
    assert architecture["cleanup_postcheck_contract_ready"] is True
    assert architecture["cleanup_postcheck_row_count"] == 5
    assert architecture["cleanup_postcheck_blocked_row_count"] == 0
    assert architecture["cleanup_postcheck_global_refresh_command_count"] == 9
    assert architecture["casp17_transition_surface_ready"] is True
    assert architecture["execution_enabled"] is False
    assert architecture["docking_results_emitted"] is False
    assert architecture["cameo_submission_executed"] is False
    assert architecture["casp_submission_executed"] is False
    assert architecture["cleanup_executed"] is False
    assert architecture["external_state_mutated"] is False

    service_boundary = asyncio.run(product.get_product_service_boundary())

    assert service_boundary["status"] == "product_service_boundary_contract_ready"
    assert service_boundary["service_boundary_ready"] is True
    assert service_boundary["blocker_count"] == 0
    assert service_boundary["execution_enabled"] is False
    assert service_boundary["docking_results_emitted"] is False
    assert service_boundary["license_file_written"] is False
    assert service_boundary["bundle_assembled"] is False
    assert service_boundary["external_state_mutated"] is False

    api_contract = asyncio.run(product.get_product_api_contract())

    assert api_contract["status"] == "product_api_contract_ready"
    assert api_contract["api_contract_ready"] is True
    assert api_contract["blocker_count"] == 0
    assert api_contract["server_started"] is False
    assert api_contract["execution_enabled"] is False
    assert api_contract["docking_results_emitted"] is False
    assert api_contract["license_file_written"] is False
    assert api_contract["bundle_assembled"] is False
    assert api_contract["external_state_mutated"] is False

    operational_quality = asyncio.run(product.get_product_operational_quality())

    assert operational_quality["status"] == "product_operational_quality_contract_ready"
    assert operational_quality["operational_quality_ready"] is True
    assert operational_quality["fail_closed_docking_intake_ready"] is True
    assert operational_quality["ledger_payload_privacy_ready"] is True
    assert operational_quality["input_payload_persisted"] is False
    assert operational_quality["execution_enabled"] is False
    assert operational_quality["docking_results_emitted"] is False
    assert operational_quality["external_state_mutated"] is False

    operations = asyncio.run(product.get_product_operations())

    assert operations["status"] == "blocked_product_release_operations_dossier"
    assert operations["capability_surface_ready"] is True
    assert operations["architecture_contract_ready"] is False
    assert operations["architecture_local_surface_ready"] is True
    assert operations["architecture_release_ready"] is False
    assert operations["architecture_blocked_lane_count"] == 1
    assert operations["architecture_approval_required_lane_count"] == 1
    assert operations["operational_quality_ready"] is True
    assert operations["source_operational_quality_status"] == "product_operational_quality_contract_ready"
    assert operations["operational_quality_blocker_count"] == 0
    assert operations["product_service_boundary_ready"] is True
    assert operations["product_api_contract_ready"] is True
    assert operations["cameo_architecture_validation_ready"] is False
    assert operations["cleanup_postcheck_contract_ready"] is True
    assert operations["cleanup_postcheck_blocked_row_count"] == 0
    assert operations["structure_analysis_capability_ready"] is True
    assert operations["ligand_docking_capability_ready"] is True
    assert operations["authorized_for_execution"] is False
    assert operations["blocked_stage_count"] == 4
    assert operations["approval_required_stage_count"] == 2
    assert operations["approval_token_count"] == 2
    assert operations["approval_tokens_required"] == [
        "APPROVE_PRODUCT_DOCKING_EXECUTION",
        "APPROVE_PRODUCT_LICENSE_FILE_CREATION",
    ]
    assert operations["execution_approval_token_required"] == "APPROVE_PRODUCT_DOCKING_EXECUTION"
    assert any(stage["stage"] == "architecture_contract" for stage in operations["stages"])
    assert any(stage["stage"] == "operator_execution_approval" for stage in operations["stages"])
    assert operations["license_operator_template_csv"].endswith("runs/product_license_decision_operator_template_current.csv")
    assert operations["license_operator_intake_csv"].endswith("runs/product_license_decision_operator_intake.csv")
    assert operations["license_decision_packet_status"] in {
        "product_license_decision_packet_ready",
        "missing_product_license_decision_packet",
    }
    assert operations["source_license_file_creation_work_order_status"] == "blocked_product_license_file_creation_work_order"
    assert operations["license_file_creation_work_order_status"] == "blocked_product_license_file_creation_work_order"
    assert operations["license_file_creation_review_ready"] is False
    assert operations["license_file_creation_work_order_blocker_count"] == 3
    assert operations["license_file_creation_work_order_artifact"].endswith(
        "runs/product_license_file_creation_work_order_current.json"
    )
    assert "approval_token" in operations["license_required_fields"]
    assert operations["license_approval_token_required"] == "APPROVE_PRODUCT_LICENSE_FILE_CREATION"
    assert operations["license_file_written"] is False
    assert operations["execution_enabled"] is False
    assert operations["docking_results_emitted"] is False
    assert operations["external_state_mutated"] is False

    license_decision = asyncio.run(product.get_product_license_decision())

    assert license_decision["status"] == "blocked_product_license_decision_gate"
    assert license_decision["operator_template_csv"].endswith("runs/product_license_decision_operator_template_current.csv")
    assert license_decision["operator_intake_csv"].endswith("runs/product_license_decision_operator_intake.csv")
    assert license_decision["required_decision"] == "create_license_file"
    assert license_decision["approval_token_required"] == "APPROVE_PRODUCT_LICENSE_FILE_CREATION"
    assert license_decision["authorized_for_license_file_creation_review"] is False
    assert license_decision["license_file_written"] is False
    assert license_decision["execution_enabled"] is False
    assert license_decision["docking_results_emitted"] is False
    assert license_decision["external_state_mutated"] is False

    license_options = asyncio.run(product.get_product_license_options())

    assert license_options["status"] in {"product_license_decision_packet_ready", "missing_product_license_decision_packet"}
    assert license_options["operator_template_csv"].endswith("runs/product_license_decision_operator_template_current.csv")
    assert license_options["operator_intake_csv"].endswith("runs/product_license_decision_operator_intake.csv")
    assert license_options["required_decision"] == "create_license_file"
    assert license_options["approval_token_required"] == "APPROVE_PRODUCT_LICENSE_FILE_CREATION"
    assert license_options["license_file_written"] is False
    assert license_options["legal_advice_provided"] is False
    assert license_options["execution_enabled"] is False
    assert license_options["docking_results_emitted"] is False
    assert license_options["external_state_mutated"] is False

    license_work_order = asyncio.run(product.get_product_license_file_work_order())

    assert license_work_order["status"] == "blocked_product_license_file_creation_work_order"
    assert license_work_order["artifact_path"].endswith("runs/product_license_file_creation_work_order_current.json")
    assert license_work_order["license_file_creation_review_ready"] is False
    assert license_work_order["approval_token_required"] == "APPROVE_PRODUCT_LICENSE_FILE_CREATION"
    assert license_work_order["target_license_path"] == "LICENSE"
    assert license_work_order["license_review_manifest_ready"] is False
    assert license_work_order["license_review_manifest"]["target_license_path"] == "LICENSE"
    assert len(license_work_order["license_review_manifest_fingerprint_sha256"]) == 64
    assert license_work_order["license_decision_gate_status"] == "blocked_product_license_decision_gate"
    assert license_work_order["license_file_written"] is False
    assert license_work_order["execution_enabled"] is False
    assert license_work_order["docking_results_emitted"] is False
    assert license_work_order["external_state_mutated"] is False

    commercial = asyncio.run(product.get_product_commercial_independence())

    assert commercial["status"] == "blocked_product_commercial_independence_gate"
    assert commercial["commercial_independent_product_claim_allowed"] is False
    assert commercial["license_decision_status"] == "blocked_product_license_decision_gate"
    assert commercial["license_decision_packet_status"] == "product_license_decision_packet_ready"
    assert commercial["license_decision_packet_ready"] is True
    assert commercial["license_decision_option_count"] == 5
    assert commercial["source_license_file_creation_work_order_status"] == "blocked_product_license_file_creation_work_order"
    assert commercial["license_file_creation_work_order_status"] == "blocked_product_license_file_creation_work_order"
    assert commercial["license_file_creation_review_ready"] is False
    assert commercial["license_file_creation_work_order_blocker_count"] == 3
    assert commercial["license_file_creation_work_order_artifact"].endswith(
        "runs/product_license_file_creation_work_order_current.json"
    )
    assert commercial["commercial_gate_only_license_blocked"] is True
    assert commercial["operator_template_csv"].endswith("runs/product_license_decision_operator_template_current.csv")
    assert commercial["operator_intake_csv"].endswith("runs/product_license_decision_operator_intake.csv")
    assert "approval_token" in commercial["required_fields"]
    assert commercial["required_decision"] == "create_license_file"
    assert commercial["approval_token_required"] == "APPROVE_PRODUCT_LICENSE_FILE_CREATION"
    assert commercial["license_file_written"] is False
    assert commercial["execution_enabled"] is False
    assert commercial["docking_results_emitted"] is False
    assert commercial["external_state_mutated"] is False

    release = asyncio.run(product.get_product_release_readiness())

    assert release["status"] == "blocked_product_release_operations_dossier"
    assert release["product_api_surface_ready"] is True
    assert release["product_architecture_status"] == "blocked_product_architecture_contract"
    assert release["product_architecture_local_surface_ready"] is True
    assert release["product_architecture_release_ready"] is False
    assert release["operational_quality_ready"] is True
    assert release["source_operational_quality_status"] == "product_operational_quality_contract_ready"
    assert release["operational_quality_blocker_count"] == 0
    assert release["product_architecture_blocked_lane_count"] == 1
    assert release["product_architecture_approval_required_lane_count"] == 1
    assert release["product_service_boundary_ready"] is True
    assert release["product_api_contract_ready"] is True
    assert release["product_architecture_cleanup_postcheck_ready"] is True
    assert release["product_architecture_cleanup_postcheck_row_count"] == 5
    assert release["product_architecture_cleanup_postcheck_blocked_row_count"] == 0
    assert release["commercial_independent_product_ready"] is False
    assert release["license_present"] is False
    assert release["license_decision_status"] == "blocked_product_license_decision_gate"
    assert release["license_authorized_for_file_creation_review"] is False
    assert release["license_decision_packet_status"] == "product_license_decision_packet_ready"
    assert release["license_decision_packet_ready"] is True
    assert release["license_decision_option_count"] == 5
    assert release["source_license_file_creation_work_order_status"] == "blocked_product_license_file_creation_work_order"
    assert release["license_file_creation_work_order_status"] == "blocked_product_license_file_creation_work_order"
    assert release["license_file_creation_review_ready"] is False
    assert release["license_file_creation_work_order_blocker_count"] == 3
    assert release["license_file_creation_work_order_artifact"].endswith(
        "runs/product_license_file_creation_work_order_current.json"
    )
    assert release["license_operator_template_csv"].endswith("runs/product_license_decision_operator_template_current.csv")
    assert release["license_operator_intake_csv"].endswith("runs/product_license_decision_operator_intake.csv")
    assert "approval_token" in release["license_required_fields"]
    assert release["license_required_decision"] == "create_license_file"
    assert release["license_approval_token_required"] == "APPROVE_PRODUCT_LICENSE_FILE_CREATION"
    assert release["release_allowed"] is False
    assert release["execution_enabled"] is False
    assert release["docking_results_emitted"] is False
    assert release["license_file_written"] is False
    assert release["external_state_mutated"] is False
