from __future__ import annotations

import json
from pathlib import Path

from tools import build_product_architecture_contract as mod


def _packet(summary: dict) -> dict:
    return {"summary": summary}


def _root(tmp_path: Path) -> Path:
    (tmp_path / "api").mkdir(parents=True)
    (tmp_path / "api" / "product.py").write_text(
        '@router.get("/architecture")\n@router.get("/service-boundary")\n@router.get("/api-contract")\n',
        encoding="utf-8",
    )
    (tmp_path / "api" / "cameo.py").write_text("# cameo api\n", encoding="utf-8")
    (tmp_path / "api" / "cleanup.py").write_text("# cleanup api\n", encoding="utf-8")
    (tmp_path / "api" / "casp17.py").write_text("# casp17 api\n", encoding="utf-8")
    (tmp_path / "betelgeuze_product").mkdir()
    (tmp_path / "betelgeuze_product" / "docking_request.py").write_text("# docking request\n", encoding="utf-8")
    (tmp_path / "betelgeuze_product" / "execution_preflight.py").write_text("# execution preflight\n", encoding="utf-8")
    (tmp_path / "betelgeuze_product" / "htvs_command.py").write_text("# htvs command\n", encoding="utf-8")
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "run_ligand_htvs_pipeline.py").write_text("# pipeline\n", encoding="utf-8")
    return tmp_path


def _product_release_ready() -> dict:
    return _packet(
        {
            "status": "blocked_product_release_operations_dossier",
            "authorized_for_execution": True,
            "delivery_ready_claim_allowed": True,
            "bundle_assembled": True,
            "bundle_validation_passed": True,
            "pilot_delivery_ready": True,
            "bundle_tag": "product_gpcr_adrb2",
        }
    )


def _execution_preflight_ready() -> dict:
    return {
        "summary": {
            "status": "product_execution_preflight_ready",
            "operational_gate_feasibility_status": "pass",
        },
        "operational_gate_feasibility_checks": [
            {
                "status": "pass",
                "eval_unique_keys": 200,
                "gate_min_eval_unique_keys": 200,
                "gate_ef1_min": 1.2,
                "ranking_labels_csv": "config/labels.csv",
            }
        ],
    }


def test_product_architecture_contract_reports_local_surface_and_gates(tmp_path: Path) -> None:
    payload = mod.build_product_architecture_contract(
        product_capability_packet=_packet(
            {
                "status": "product_capability_surface_contract_ready",
                "structure_analysis_capability_ready": True,
                "ligand_docking_capability_ready": True,
                "local_delivery_bundle_capability_ready": True,
            }
        ),
        product_release_packet=_product_release_ready(),
        commercial_independence_packet=_packet(
            {
                "status": "blocked_product_commercial_independence_gate",
                "commercial_independent_product_claim_allowed": False,
            }
        ),
        product_service_boundary_packet=_packet(
            {
                "status": "product_service_boundary_contract_ready",
                "service_boundary_ready": True,
                "api_route_count": 12,
                "cli_command_count": 9,
            }
        ),
        product_api_contract_packet=_packet(
            {
                "status": "product_api_contract_ready",
                "api_contract_ready": True,
                "expected_route_count": 12,
                "missing_route_count": 0,
                "status_response_missing_key_count": 0,
            }
        ),
        product_execution_preflight_packet=_execution_preflight_ready(),
        public_benchmark_packet=_packet(
            {
                "status": "blocked_product_public_benchmark_contract",
                "public_benchmark_validation_ready": False,
                "benchmark_mode": "self_hosted_reproducible_public_benchmarks",
                "required_suite_count": 5,
                "ready_required_suite_count": 0,
                "blocked_suite_count": 5,
                "requires_24h_server": False,
                "requires_competition_season": False,
                "requires_paid_vps": False,
            }
        ),
        cameo_capability_packet=_packet(
            {
                "status": "blocked_cameo_capability_preflight",
                "api_operations_route_registered": True,
                "api_dependency_ready": False,
                "source_api_dependency_status": "blocked_cameo_api_dependency_readiness",
                "source_receiver_smoke_status": "blocked_cameo_receiver_smoke",
                "public_registration_allowed": False,
                "public_registration_blocker_count": 4,
                "registration_approval_token_required": "APPROVE_CAMEO_SERVER_REGISTRATION",
                "outbound_email_approval_token_required": "APPROVE_CAMEO_OUTBOUND_EMAIL",
            }
        ),
        cameo_architecture_validation_packet=_packet(
            {
                "status": "blocked_cameo_architecture_validation_contract",
                "local_validation_protocol_ready": True,
                "cameo_service_boundary_ready": True,
                "cameo_service_boundary_status": "cameo_service_boundary_contract_ready",
                "cameo_service_boundary_api_route_count": 9,
                "cameo_service_boundary_cli_command_count": 14,
                "cameo_api_contract_ready": True,
                "cameo_api_contract_status": "cameo_api_contract_ready",
                "cameo_api_contract_expected_route_count": 9,
                "cameo_api_contract_missing_route_count": 0,
                "cameo_api_contract_status_response_missing_key_count": 0,
                "cameo_architecture_validation_ready": False,
                "validation_evidence_ready": False,
                "official_results_ready": False,
                "official_results_status": "blocked_cameo_official_results_intake",
                "accepted_official_result_count": 0,
                "model1_official_result_ready": False,
                "operator_intake_csv": "runs/cameo_official_results_operator_intake.csv",
                "public_registration_status": "blocked_cameo_public_registration_approval_gate",
                "public_registration_authorized": False,
            }
        ),
        cleanup_operations_packet=_packet(
            {
                "status": "cleanup_operations_surface_contract_ready",
                "surface_ready": True,
                "cleanup_approval_gate_endpoint_present": True,
            }
        ),
        cleanup_approval_packet=_packet(
            {
                "status": "blocked_cleanup_execution_operator_approval_gate",
                "authorized_for_cleanup_execution": False,
                "approval_token_required": "APPROVE_CLEANUP_EXECUTION",
                "total_reclaim_size_gb": 49.216,
            }
        ),
        cleanup_postcheck_packet=_packet(
            {
                "status": "cleanup_postcheck_contract_ready",
                "postcheck_contract_ready": True,
                "row_count": 7,
                "blocked_row_count": 0,
                "global_refresh_command_count": 9,
            }
        ),
        ligand_cleanup_work_order_packet=_packet({"status": "cleanup_work_order_ready"}),
        ligand_cleanup_preflight_packet=_packet({"status": "ligand_heavy_cleanup_execution_preflight_ready", "blocker_count": 0}),
        casp17_transition_packet=_packet({"status": "casp17_transition_surface_contract_ready", "surface_ready": True}),
        root=_root(tmp_path / "repo"),
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_product_architecture_contract"
    assert summary["local_architecture_surface_ready"] is False
    assert summary["architecture_release_ready"] is False
    assert summary["ready_lane_count"] == 11
    assert summary["blocked_lane_count"] == 2
    assert summary["approval_required_lane_count"] == 1
    assert summary["canonical_architecture_lanes_required"] == [
        "structure_analysis",
        "ligand_docking",
        "scoring_ranking",
        "benchmark_validation",
        "local_delivery",
        "commercial_independence",
        "CAMEO_live_validation",
    ]
    assert summary["canonical_architecture_lane_count"] == 7
    assert summary["canonical_architecture_required_lanes_present"] is True
    assert summary["canonical_architecture_missing_lanes"] == []
    assert summary["canonical_architecture_ready_lane_count"] == 5
    assert summary["canonical_architecture_blocked_lane_count"] == 2
    assert summary["canonical_architecture_blocked_lanes"] == [
        "benchmark_validation",
        "commercial_independence",
    ]
    assert summary["canonical_architecture_lane_statuses"] == {
        "structure_analysis": "ready",
        "ligand_docking": "ready",
        "scoring_ranking": "ready",
        "benchmark_validation": "blocked",
        "local_delivery": "ready",
        "commercial_independence": "blocked",
        "CAMEO_live_validation": "ready",
    }
    assert summary["canonical_architecture_lane_ids"]["benchmark_validation"] == "public_benchmark_validation_gate"
    assert summary["structure_analysis_product_surface_ready"] is True
    assert summary["ligand_docking_execution_contract_ready"] is True
    assert summary["scoring_ranking_contract_ready"] is True
    assert summary["scoring_ranking_eval_unique_keys"] == 200
    assert summary["scoring_ranking_gate_min_eval_unique_keys"] == 200
    assert summary["scoring_ranking_gate_ef1_min"] == 1.2
    assert summary["local_delivery_bundle_validation_ready"] is True
    assert summary["local_delivery_bundle_assembled"] is True
    assert summary["local_delivery_bundle_validation_passed"] is True
    assert summary["local_delivery_pilot_delivery_ready"] is True
    assert summary["product_service_boundary_ready"] is True
    assert summary["product_api_contract_ready"] is True
    assert summary["public_benchmark_validation_ready"] is False
    assert summary["public_benchmark_status"] == "blocked_product_public_benchmark_contract"
    assert summary["public_benchmark_required_suite_count"] == 5
    assert summary["public_benchmark_ready_required_suite_count"] == 0
    assert summary["public_benchmark_blocked_suite_count"] == 5
    assert summary["public_benchmark_requires_24h_server"] is False
    assert summary["public_benchmark_requires_competition_season"] is False
    assert summary["public_benchmark_requires_paid_vps"] is False
    assert summary["cameo_local_surface_ready"] is True
    assert summary["cameo_service_boundary_ready"] is True
    assert summary["cameo_service_boundary_status"] == "cameo_service_boundary_contract_ready"
    assert summary["cameo_service_boundary_api_route_count"] == 9
    assert summary["cameo_service_boundary_cli_command_count"] == 14
    assert summary["cameo_api_contract_ready"] is True
    assert summary["cameo_api_contract_status"] == "cameo_api_contract_ready"
    assert summary["cameo_api_contract_expected_route_count"] == 9
    assert summary["cameo_api_contract_missing_route_count"] == 0
    assert summary["cameo_api_contract_status_response_missing_key_count"] == 0
    assert summary["cameo_architecture_validation_protocol_ready"] is True
    assert summary["cameo_architecture_validation_ready"] is False
    assert summary["cameo_official_validation_evidence_ready"] is False
    assert summary["cameo_official_results_status"] == "blocked_cameo_official_results_intake"
    assert summary["cameo_accepted_official_result_count"] == 0
    assert summary["cameo_model1_official_result_ready"] is False
    assert summary["cameo_operator_intake_csv"] == "runs/cameo_official_results_operator_intake.csv"
    assert summary["cameo_public_registration_status"] == "blocked_cameo_public_registration_approval_gate"
    assert summary["cameo_public_registration_authorized"] is False
    assert summary["cameo_receiver_smoke_ready"] is False
    assert summary["cameo_receiver_smoke_status"] == "blocked_cameo_receiver_smoke"
    assert summary["cameo_api_dependency_ready"] is False
    assert summary["cameo_api_dependency_status"] == "blocked_cameo_api_dependency_readiness"
    assert summary["cameo_public_registration_allowed"] is False
    assert summary["cameo_public_registration_blocker_count"] == 4
    assert summary["cameo_registration_approval_token_required"] == "APPROVE_CAMEO_SERVER_REGISTRATION"
    assert summary["cameo_outbound_email_approval_token_required"] == "APPROVE_CAMEO_OUTBOUND_EMAIL"
    assert summary["cameo_registration_approval_token_count"] == 2
    assert summary["cameo_registration_approval_tokens_required"] == [
        "APPROVE_CAMEO_SERVER_REGISTRATION",
        "APPROVE_CAMEO_OUTBOUND_EMAIL",
    ]
    assert summary["cleanup_control_surface_ready"] is True
    assert summary["cleanup_postcheck_contract_ready"] is True
    assert summary["cleanup_postcheck_row_count"] == 7
    assert summary["cleanup_postcheck_blocked_row_count"] == 0
    assert summary["cleanup_postcheck_global_refresh_command_count"] == 9
    assert summary["cleanup_completion_ready"] is False
    assert summary["ligand_heavy_cleanup_preflight_ready"] is True
    assert summary["casp17_transition_surface_ready"] is True
    assert summary["cleanup_execution_approved"] is False
    assert summary["cleanup_reclaim_size_gb"] == 49.216
    assert summary["execution_enabled"] is False
    assert summary["docking_results_emitted"] is False
    assert summary["cameo_submission_executed"] is False
    assert summary["casp_submission_executed"] is False
    assert summary["cleanup_executed"] is False
    assert summary["external_state_mutated"] is False
    approval_tokens = {row["lane_id"]: row["approval_token_required"] for row in payload["approval_required"]}
    assert approval_tokens["ligand_heavy_cleanup_preflight"] == "APPROVE_CLEANUP_EXECUTION"
    public_benchmark_row = next(row for row in payload["rows"] if row["lane_id"] == "public_benchmark_validation_gate")
    assert public_benchmark_row["status"] == "blocked"
    assert public_benchmark_row["canonical_lane"] == "benchmark_validation"
    assert "requires_24h_server=False" in public_benchmark_row["observed"]
    cameo_row = next(row for row in payload["rows"] if row["lane_id"] == "cameo_optional_live_validation_surface")
    assert cameo_row["status"] == "ready"
    assert cameo_row["canonical_lane"] == "CAMEO_live_validation"
    assert "receiver_smoke_status=blocked_cameo_receiver_smoke" in cameo_row["observed"]
    assert "api_dependency_ready=False" in cameo_row["observed"]
    assert "registration_tokens=APPROVE_CAMEO_SERVER_REGISTRATION;APPROVE_CAMEO_OUTBOUND_EMAIL" in cameo_row["observed"]
    scoring_row = next(row for row in payload["rows"] if row["lane_id"] == "scoring_ranking_contract")
    assert scoring_row["status"] == "ready"
    assert scoring_row["canonical_lane"] == "scoring_ranking"
    assert "eval_unique_keys=200" in scoring_row["observed"]
    local_delivery_row = next(row for row in payload["rows"] if row["lane_id"] == "local_delivery_bundle_validation")
    assert local_delivery_row["status"] == "ready"
    assert local_delivery_row["canonical_lane"] == "local_delivery"
    assert "bundle_validation_passed=True" in local_delivery_row["observed"]


def test_product_architecture_contract_uses_cleanup_completion_gate(tmp_path: Path) -> None:
    payload = mod.build_product_architecture_contract(
        product_capability_packet=_packet(
            {
                "status": "product_capability_surface_contract_ready",
                "structure_analysis_capability_ready": True,
                "ligand_docking_capability_ready": True,
                "local_delivery_bundle_capability_ready": True,
            }
        ),
        product_release_packet=_product_release_ready(),
        commercial_independence_packet=_packet(
            {
                "status": "blocked_product_commercial_independence_gate",
                "commercial_independent_product_claim_allowed": False,
            }
        ),
        product_service_boundary_packet=_packet(
            {
                "status": "product_service_boundary_contract_ready",
                "service_boundary_ready": True,
                "api_route_count": 12,
                "cli_command_count": 9,
            }
        ),
        product_api_contract_packet=_packet(
            {
                "status": "product_api_contract_ready",
                "api_contract_ready": True,
                "expected_route_count": 12,
                "missing_route_count": 0,
                "status_response_missing_key_count": 0,
            }
        ),
        product_execution_preflight_packet=_execution_preflight_ready(),
        cameo_capability_packet=_packet(
            {
                "status": "blocked_cameo_capability_preflight",
                "api_operations_route_registered": True,
                "api_dependency_ready": True,
                "source_api_dependency_status": "cameo_api_dependency_ready",
                "source_receiver_smoke_status": "cameo_receiver_smoke_ready",
                "public_registration_allowed": False,
                "public_registration_blocker_count": 2,
                "registration_approval_token_required": "APPROVE_CAMEO_SERVER_REGISTRATION",
                "outbound_email_approval_token_required": "APPROVE_CAMEO_OUTBOUND_EMAIL",
            }
        ),
        cameo_architecture_validation_packet=_packet(
            {
                "status": "blocked_cameo_architecture_validation_contract",
                "local_validation_protocol_ready": True,
                "cameo_service_boundary_ready": True,
                "cameo_service_boundary_status": "cameo_service_boundary_contract_ready",
                "cameo_api_contract_ready": True,
                "cameo_api_contract_status": "cameo_api_contract_ready",
                "cameo_architecture_validation_ready": False,
                "validation_evidence_ready": False,
                "official_results_ready": False,
            }
        ),
        cleanup_operations_packet=_packet(
            {
                "status": "cleanup_operations_surface_contract_ready",
                "surface_ready": True,
                "cleanup_approval_gate_endpoint_present": True,
            }
        ),
        cleanup_approval_packet=_packet(
            {
                "status": "cleanup_execution_operator_approval_gate_ready",
                "authorized_row_count": 5,
                "awaiting_operator_approval_row_count": 0,
                "blocked_row_count": 0,
                "total_reclaim_size_gb": 49.216,
            }
        ),
        cleanup_postcheck_packet=_packet(
            {
                "status": "cleanup_postcheck_contract_ready",
                "postcheck_contract_ready": True,
                "row_count": 5,
                "blocked_row_count": 0,
                "global_refresh_command_count": 9,
            }
        ),
        cleanup_completion_packet=_packet(
            {
                "status": "cleanup_completion_gate_ready",
                "cleanup_complete": True,
                "blocked_stage_count": 0,
            }
        ),
        ligand_cleanup_work_order_packet=_packet({"status": "cleanup_work_order_ready"}),
        ligand_cleanup_preflight_packet=_packet({"status": "ligand_heavy_cleanup_execution_preflight_ready", "blocker_count": 0}),
        casp17_transition_packet=_packet({"status": "casp17_transition_surface_contract_ready", "surface_ready": True}),
        root=_root(tmp_path / "repo"),
    )

    summary = payload["summary"]
    assert summary["cleanup_completion_ready"] is True
    assert summary["cleanup_execution_approved"] is True
    cleanup_row = next(row for row in payload["rows"] if row["lane_id"] == "ligand_heavy_cleanup_preflight")
    assert cleanup_row["status"] == "ready"
    assert cleanup_row["approval_token_required"] == ""
    assert "cleanup_complete=True" in cleanup_row["observed"]
    assert "cleanup approval gates" not in summary["next_required_step"]


def test_product_architecture_contract_tool_writes_outputs(tmp_path: Path) -> None:
    root = _root(tmp_path / "repo")
    packets = {
        "product_capability": _packet(
            {
                "status": "product_capability_surface_contract_ready",
                "structure_analysis_capability_ready": True,
                "ligand_docking_capability_ready": True,
                "local_delivery_bundle_capability_ready": True,
            }
        ),
        "product_release": _product_release_ready(),
        "commercial": _packet({"status": "blocked_product_commercial_independence_gate", "commercial_independent_product_claim_allowed": False}),
        "service_boundary": _packet(
            {
                "status": "product_service_boundary_contract_ready",
                "service_boundary_ready": True,
                "api_route_count": 12,
                "cli_command_count": 9,
            }
        ),
        "api_contract": _packet(
            {
                "status": "product_api_contract_ready",
                "api_contract_ready": True,
                "expected_route_count": 12,
                "missing_route_count": 0,
                "status_response_missing_key_count": 0,
            }
        ),
        "product_preflight": _execution_preflight_ready(),
        "public_benchmark": _packet(
            {
                "status": "blocked_product_public_benchmark_contract",
                "public_benchmark_validation_ready": False,
                "benchmark_mode": "self_hosted_reproducible_public_benchmarks",
                "required_suite_count": 5,
                "ready_required_suite_count": 0,
                "blocked_suite_count": 5,
                "requires_24h_server": False,
                "requires_competition_season": False,
                "requires_paid_vps": False,
            }
        ),
        "cameo": _packet(
            {
                "status": "blocked_cameo_capability_preflight",
                "api_operations_route_registered": True,
                "api_dependency_ready": False,
                "source_api_dependency_status": "blocked_cameo_api_dependency_readiness",
                "source_receiver_smoke_status": "blocked_cameo_receiver_smoke",
                "public_registration_allowed": False,
                "public_registration_blocker_count": 4,
                "registration_approval_token_required": "APPROVE_CAMEO_SERVER_REGISTRATION",
                "outbound_email_approval_token_required": "APPROVE_CAMEO_OUTBOUND_EMAIL",
            }
        ),
        "cameo_architecture": _packet(
            {
                "status": "blocked_cameo_architecture_validation_contract",
                "local_validation_protocol_ready": True,
                "cameo_service_boundary_ready": True,
                "cameo_service_boundary_status": "cameo_service_boundary_contract_ready",
                "cameo_api_contract_ready": True,
                "cameo_api_contract_status": "cameo_api_contract_ready",
                "cameo_architecture_validation_ready": False,
                "validation_evidence_ready": False,
                "official_results_ready": False,
            }
        ),
        "cleanup_ops": _packet({"status": "cleanup_operations_surface_contract_ready", "surface_ready": True}),
        "cleanup_approval": _packet({"status": "blocked_cleanup_execution_operator_approval_gate", "authorized_for_cleanup_execution": False}),
        "cleanup_postcheck": _packet(
            {
                "status": "cleanup_postcheck_contract_ready",
                "postcheck_contract_ready": True,
                "row_count": 7,
                "blocked_row_count": 0,
                "global_refresh_command_count": 9,
            }
        ),
        "ligand_work": _packet({"status": "cleanup_work_order_ready"}),
        "ligand_preflight": _packet({"status": "ligand_heavy_cleanup_execution_preflight_ready", "blocker_count": 0}),
        "casp17": _packet({"status": "casp17_transition_surface_contract_ready", "surface_ready": True}),
    }
    paths: dict[str, Path] = {}
    for name, payload in packets.items():
        paths[name] = tmp_path / f"{name}.json"
        paths[name].write_text(json.dumps(payload) + "\n", encoding="utf-8")
    out_json = tmp_path / "architecture.json"
    out_csv = tmp_path / "architecture.csv"
    out_md = tmp_path / "architecture.md"

    mod.main(
        [
            "--product-capability-json",
            str(paths["product_capability"]),
            "--product-release-json",
            str(paths["product_release"]),
            "--commercial-independence-json",
            str(paths["commercial"]),
            "--product-service-boundary-json",
            str(paths["service_boundary"]),
            "--product-api-contract-json",
            str(paths["api_contract"]),
            "--product-execution-preflight-json",
            str(paths["product_preflight"]),
            "--public-benchmark-json",
            str(paths["public_benchmark"]),
            "--cameo-capability-json",
            str(paths["cameo"]),
            "--cameo-architecture-validation-json",
            str(paths["cameo_architecture"]),
            "--cleanup-operations-json",
            str(paths["cleanup_ops"]),
            "--cleanup-approval-json",
            str(paths["cleanup_approval"]),
            "--cleanup-postcheck-json",
            str(paths["cleanup_postcheck"]),
            "--ligand-cleanup-work-order-json",
            str(paths["ligand_work"]),
            "--ligand-cleanup-preflight-json",
            str(paths["ligand_preflight"]),
            "--casp17-transition-json",
            str(paths["casp17"]),
            "--root",
            str(root),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    summary = json.loads(out_json.read_text(encoding="utf-8"))["summary"]
    assert summary["status"] == "blocked_product_architecture_contract"
    assert summary["local_architecture_surface_ready"] is False
    assert summary["product_service_boundary_ready"] is True
    assert summary["product_api_contract_ready"] is True
    assert summary["scoring_ranking_contract_ready"] is True
    assert summary["local_delivery_bundle_validation_ready"] is True
    assert summary["public_benchmark_validation_ready"] is False
    assert summary["public_benchmark_requires_24h_server"] is False
    assert summary["cameo_architecture_validation_protocol_ready"] is True
    assert summary["cameo_service_boundary_ready"] is True
    assert summary["cameo_api_contract_ready"] is True
    assert summary["cameo_registration_approval_token_count"] == 2
    assert summary["cameo_receiver_smoke_status"] == "blocked_cameo_receiver_smoke"
    assert summary["cleanup_postcheck_contract_ready"] is True
    csv_text = out_csv.read_text(encoding="utf-8")
    md_text = out_md.read_text(encoding="utf-8")
    assert csv_text.startswith("lane_id,canonical_lane,domain,")
    assert "benchmark_validation" in csv_text
    assert "Product Architecture Contract" in md_text
    assert "canonical_architecture_lanes_required" in md_text
