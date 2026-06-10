from __future__ import annotations

from pathlib import Path

from betelgeuze_product.capability_surface import build_product_capability_surface_contract


def _readiness(status: str = "product_handoff_ready") -> dict:
    return {
        "summary": {
            "status": status,
            "target_id": "ADRB2",
            "family": "gpcr",
            "ligand_count": 3,
            "request_contract_status": "pass" if status == "product_handoff_ready" else "fail",
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
        }
    }


def _work_order() -> dict:
    return {"summary": {"status": "product_execution_work_order_ready", "execution_enabled": False, "docking_results_emitted": False, "external_state_mutated": False}}


def _preflight() -> dict:
    return {
        "summary": {
            "status": "product_execution_preflight_ready",
            "unknown_arg_count": 0,
            "config_count": 1,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
        }
    }


def _structure_report() -> dict:
    return {
        "summary": {
            "status": "product_structure_analysis_report_ready",
            "local_structure_parsed": True,
            "atom_count": 42,
            "ligand_like_residue_count": 1,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
        }
    }


def _bundle() -> dict:
    return {
        "summary": {
            "status": "product_bundle_contract_ready",
            "bundle_parser_status": "parsed",
            "bundle_unknown_arg_count": 0,
            "expected_bundle_dir": "runs/local_delivery/bundle_product_gpcr_adrb2",
            "artifact_count": 1,
            "bundle_validation_command_matches": True,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
        },
        "bundle_command_check": {"parsed_args": {"rerun_command": "python3 tools/run_ligand_htvs_pipeline.py --out-prefix runs/product_gpcr_adrb2_after_approval"}},
        "planned_artifact_checks": [{"path": "runs/product_gpcr_adrb2_after_approval_summary.json"}],
    }


def _delivery() -> dict:
    return {
        "summary": {
            "status": "product_delivery_evidence_contract_ready",
            "delivery_ready_claim_allowed": False,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
        }
    }


def _pilot() -> dict:
    return {
        "summary": {
            "status": "product_pilot_packet_preflight_ready",
            "pilot_delivery_ready": False,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
        }
    }


def _execution_readiness(*, ready: bool = True) -> dict:
    return {
        "summary": {
            "status": "restricted_unattended_execution_wiring_ready" if ready else "blocked_restricted_unattended_execution_readiness",
            "restricted_unattended_execution_ready": ready,
            "restricted_unattended_execution_runtime_ready": False,
        }
    }


def _root(tmp_path: Path) -> Path:
    (tmp_path / "api").mkdir()
    (tmp_path / "api" / "product.py").write_text(
        '@router.post("/structure/analyze")\n'
        '@router.get("/capabilities")\n'
        '@router.get("/architecture")\n'
        '@router.get("/service-boundary")\n'
        '@router.get("/api-contract")\n'
        '@router.get("/operational-quality")\n'
        '@router.get("/operations")\n'
        '@router.get("/license-decision")\n'
        '@router.get("/license-options")\n'
        '@router.get("/license-file-work-order")\n'
        '@router.get("/commercial-independence")\n'
        '@router.get("/release-readiness")\n'
        '@router.get("/goal-completion-audit")\n',
        encoding="utf-8",
    )
    (tmp_path / "betelgeuze_product").mkdir()
    (tmp_path / "betelgeuze_product" / "docking_request.py").write_text("# request contract\n", encoding="utf-8")
    (tmp_path / "betelgeuze_product" / "cli.py").write_text("# product CLI\n", encoding="utf-8")
    return tmp_path


def test_product_capability_surface_contract_ready_for_guarded_product_surface(tmp_path: Path) -> None:
    payload = build_product_capability_surface_contract(
        readiness_packet=_readiness(),
        work_order_packet=_work_order(),
        preflight_packet=_preflight(),
        structure_report_packet=_structure_report(),
        bundle_contract_packet=_bundle(),
        delivery_evidence_packet=_delivery(),
        pilot_packet=_pilot(),
        execution_readiness_packet=_execution_readiness(),
        root=_root(tmp_path),
    )

    summary = payload["summary"]
    assert summary["status"] == "product_capability_surface_contract_ready"
    assert summary["capability_count"] == 9
    assert summary["ready_capability_count"] == 9
    assert summary["blocked_capability_count"] == 0
    assert summary["structure_analysis_capability_ready"] is True
    assert summary["product_structure_analysis_report_ready"] is True
    assert summary["product_structure_analysis_atom_count"] == 42
    assert summary["ligand_docking_capability_ready"] is True
    assert summary["result_bundle_generation_contract_ready"] is True
    assert summary["result_bundle_expected_dir"] == "runs/local_delivery/bundle_product_gpcr_adrb2"
    assert summary["result_bundle_artifact_count"] == 1
    assert summary["result_bundle_planned_artifact_paths"] == ["runs/product_gpcr_adrb2_after_approval_summary.json"]
    assert summary["result_bundle_validation_command_matches"] is True
    assert summary["result_bundle_rerun_command_present"] is True
    assert summary["api_surface_ready"] is True
    assert summary["product_structure_analysis_endpoint_present"] is True
    assert summary["product_capability_endpoint_present"] is True
    assert summary["product_architecture_endpoint_present"] is True
    assert summary["product_service_boundary_endpoint_present"] is True
    assert summary["product_api_contract_endpoint_present"] is True
    assert summary["product_operational_quality_endpoint_present"] is True
    assert summary["product_operations_endpoint_present"] is True
    assert summary["product_license_decision_endpoint_present"] is True
    assert summary["product_license_options_endpoint_present"] is True
    assert summary["product_license_file_work_order_endpoint_present"] is True
    assert summary["product_commercial_independence_endpoint_present"] is True
    assert summary["product_release_readiness_endpoint_present"] is True
    assert summary["product_goal_completion_audit_endpoint_present"] is True
    assert summary["product_cli_surface_present"] is True
    assert summary["guarded_claims_ready"] is True
    assert summary["restricted_scope_claim_guard_ready"] is True
    assert summary["restricted_unattended_execution_ready"] is True
    assert summary["allowed_scope_families"] == ["gpcr", "ion_channel", "kinase"]
    assert summary["blocked_claim_scopes"] == [
        "transporter_domain_promotion",
        "pxr_domain_promotion",
        "general_protein_ligand_platform",
    ]
    assert summary["general_platform_claim_allowed"] is False
    assert "general_platform_claim_allowed=False" in summary["scope_claim_boundary_detail"]
    assert summary["delivery_claim_backed_by_bundle_validation"] is False
    assert summary["execution_enabled"] is False
    assert summary["docking_results_emitted"] is False
    assert summary["external_state_mutated"] is False


def test_product_capability_surface_blocks_failed_request_contract(tmp_path: Path) -> None:
    payload = build_product_capability_surface_contract(
        readiness_packet=_readiness(status="blocked_product_handoff"),
        work_order_packet=_work_order(),
        preflight_packet=_preflight(),
        structure_report_packet=_structure_report(),
        bundle_contract_packet=_bundle(),
        delivery_evidence_packet=_delivery(),
        pilot_packet=_pilot(),
        execution_readiness_packet=_execution_readiness(ready=False),
        root=_root(tmp_path),
    )

    assert payload["summary"]["status"] == "blocked_product_capability_surface_contract"
    assert payload["summary"]["capability_count"] == 9
    assert payload["summary"]["structure_analysis_capability_ready"] is False
    assert payload["summary"]["ligand_docking_capability_ready"] is False
    assert any(blocker["code"] == "molecular_structure_analysis_intake_not_ready" for blocker in payload["blockers"])


def test_product_capability_surface_allows_delivery_claim_when_validated_bundle_backs_it(tmp_path: Path) -> None:
    bundle = _bundle()
    bundle["summary"]["bundle_assembled"] = True
    bundle["summary"]["bundle_validation_passed"] = True
    delivery = _delivery()
    delivery["summary"]["delivery_ready_claim_allowed"] = True
    pilot = _pilot()
    pilot["summary"]["pilot_delivery_ready"] = True

    payload = build_product_capability_surface_contract(
        readiness_packet=_readiness(),
        work_order_packet=_work_order(),
        preflight_packet=_preflight(),
        structure_report_packet=_structure_report(),
        bundle_contract_packet=bundle,
        delivery_evidence_packet=delivery,
        pilot_packet=pilot,
        execution_readiness_packet=_execution_readiness(),
        root=_root(tmp_path),
    )

    summary = payload["summary"]
    assert summary["status"] == "product_capability_surface_contract_ready"
    assert summary["guarded_claims_ready"] is True
    assert summary["delivery_claim_backed_by_bundle_validation"] is True
    scope_row = next(row for row in payload["rows"] if row["capability_id"] == "restricted_scope_claim_guard")
    assert scope_row["status"] == "ready"
    assert "blocked_claim_scopes=transporter_domain_promotion,pxr_domain_promotion,general_protein_ligand_platform" in scope_row["observed"]
    guard_row = next(row for row in payload["rows"] if row["capability_id"] == "guarded_claim_and_execution_flags")
    assert "delivery_ready_claim_allowed=True" in guard_row["observed"]
    assert "delivery_claim_backed_by_bundle_validation=True" in guard_row["observed"]
