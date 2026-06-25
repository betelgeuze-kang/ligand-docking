from __future__ import annotations

import json
from pathlib import Path

from tools import build_product_capability_surface_contract as mod


def _readiness() -> dict:
    return {
        "summary": {
            "status": "product_handoff_ready",
            "target_id": "ADRB2",
            "family": "gpcr",
            "ligand_count": 3,
            "request_contract_status": "pass",
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


def _execution_readiness() -> dict:
    return {
        "summary": {
            "status": "restricted_unattended_execution_wiring_ready",
            "restricted_unattended_execution_ready": True,
            "restricted_unattended_execution_runtime_ready": False,
        }
    }


def _scope_breadth() -> dict:
    return {
        "summary": {
            "allowed_scope_families": ["gpcr", "ion_channel", "kinase"],
            "blocked_claim_scopes": [
                "transporter_domain_promotion",
                "pxr_domain_promotion",
                "general_protein_ligand_platform",
            ],
            "general_platform_claim_allowed": False,
        }
    }


def _root(tmp_path: Path) -> Path:
    (tmp_path / "api").mkdir(parents=True)
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


def _split_router_root(tmp_path: Path) -> Path:
    (tmp_path / "api").mkdir(parents=True)
    router_files = {
        "product_docking.py": '@router.post("/structure/analyze")\n',
        "product_capabilities.py": '@router.get("/capabilities")\n',
        "product_architecture.py": '@router.get("/architecture")\n',
        "product_service_contracts.py": '@router.get("/service-boundary")\n@router.get("/api-contract")\n',
        "product_operational.py": '@router.get("/operational-quality")\n',
        "product_release_ops.py": (
            '@router.get("/operations")\n'
            '@router.get("/commercial-independence")\n'
            '@router.get("/release-readiness")\n'
        ),
        "product_license.py": (
            '@router.get("/license-decision")\n'
            '@router.get("/license-options")\n'
            '@router.get("/license-file-work-order")\n'
        ),
        "product_evidence_goal.py": '@router.get("/goal-completion-audit")\n',
    }
    for filename, content in router_files.items():
        (tmp_path / "api" / filename).write_text(content, encoding="utf-8")
    (tmp_path / "betelgeuze_product").mkdir()
    (tmp_path / "betelgeuze_product" / "docking_request.py").write_text("# request contract\n", encoding="utf-8")
    (tmp_path / "betelgeuze_product" / "cli.py").write_text("# product CLI\n", encoding="utf-8")
    return tmp_path


def test_product_capability_surface_contract_tool_writes_outputs(tmp_path: Path) -> None:
    root = _root(tmp_path / "repo")
    paths = {
        "readiness": tmp_path / "readiness.json",
        "work_order": tmp_path / "work_order.json",
        "preflight": tmp_path / "preflight.json",
        "structure_report": tmp_path / "structure_report.json",
        "bundle": tmp_path / "bundle.json",
        "delivery": tmp_path / "delivery.json",
        "pilot": tmp_path / "pilot.json",
        "execution_readiness": tmp_path / "execution_readiness.json",
        "scope_breadth": tmp_path / "scope_breadth.json",
    }
    paths["readiness"].write_text(json.dumps(_readiness()) + "\n", encoding="utf-8")
    paths["work_order"].write_text(json.dumps(_work_order()) + "\n", encoding="utf-8")
    paths["preflight"].write_text(json.dumps(_preflight()) + "\n", encoding="utf-8")
    paths["structure_report"].write_text(json.dumps(_structure_report()) + "\n", encoding="utf-8")
    paths["bundle"].write_text(json.dumps(_bundle()) + "\n", encoding="utf-8")
    paths["delivery"].write_text(json.dumps(_delivery()) + "\n", encoding="utf-8")
    paths["pilot"].write_text(json.dumps(_pilot()) + "\n", encoding="utf-8")
    paths["execution_readiness"].write_text(json.dumps(_execution_readiness()) + "\n", encoding="utf-8")
    paths["scope_breadth"].write_text(json.dumps(_scope_breadth()) + "\n", encoding="utf-8")
    out_json = tmp_path / "capability.json"
    out_csv = tmp_path / "capability.csv"
    out_md = tmp_path / "capability.md"

    mod.main(
        [
            "--readiness-json",
            str(paths["readiness"]),
            "--work-order-json",
            str(paths["work_order"]),
            "--preflight-json",
            str(paths["preflight"]),
            "--structure-report-json",
            str(paths["structure_report"]),
            "--bundle-contract-json",
            str(paths["bundle"]),
            "--delivery-evidence-json",
            str(paths["delivery"]),
            "--pilot-packet-json",
            str(paths["pilot"]),
            "--execution-readiness-json",
            str(paths["execution_readiness"]),
            "--scope-breadth-json",
            str(paths["scope_breadth"]),
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

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "product_capability_surface_contract_ready"
    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["product_structure_analysis_endpoint_present"] is True
    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["product_structure_analysis_report_ready"] is True
    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["result_bundle_generation_contract_ready"] is True
    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["result_bundle_artifact_count"] == 1
    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["result_bundle_rerun_command_present"] is True
    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["delivery_claim_backed_by_bundle_validation"] is False
    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["restricted_unattended_execution_ready"] is True
    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["capability_count"] == 9
    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["allowed_scope_families"] == ["gpcr", "ion_channel", "kinase"]
    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["blocked_claim_scopes"] == [
        "transporter_domain_promotion",
        "pxr_domain_promotion",
        "general_protein_ligand_platform",
    ]
    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["general_platform_claim_allowed"] is False
    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["product_architecture_endpoint_present"] is True
    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["product_service_boundary_endpoint_present"] is True
    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["product_api_contract_endpoint_present"] is True
    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["product_operational_quality_endpoint_present"] is True
    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["product_license_decision_endpoint_present"] is True
    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["product_license_options_endpoint_present"] is True
    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["product_license_file_work_order_endpoint_present"] is True
    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["product_goal_completion_audit_endpoint_present"] is True
    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["product_cli_surface_present"] is True
    assert out_csv.read_text(encoding="utf-8").startswith("capability_id,domain,")
    assert "Product Capability Surface Contract" in out_md.read_text(encoding="utf-8")
    assert "result_bundle_generation_contract_ready" in out_md.read_text(encoding="utf-8")
    assert "delivery_claim_backed_by_bundle_validation" in out_md.read_text(encoding="utf-8")
    assert "restricted_scope_claim_guard_ready" in out_md.read_text(encoding="utf-8")


def test_product_capability_surface_contract_accepts_split_api_router_files(tmp_path: Path) -> None:
    root = _split_router_root(tmp_path / "repo")

    payload = mod.build_product_capability_surface_contract(
        readiness_packet=_readiness(),
        work_order_packet=_work_order(),
        preflight_packet=_preflight(),
        structure_report_packet=_structure_report(),
        bundle_contract_packet=_bundle(),
        delivery_evidence_packet=_delivery(),
        pilot_packet=_pilot(),
        scope_breadth_packet=_scope_breadth(),
        execution_readiness_packet=_execution_readiness(),
        root=root,
    )

    summary = payload["summary"]
    assert summary["status"] == "product_capability_surface_contract_ready"
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
