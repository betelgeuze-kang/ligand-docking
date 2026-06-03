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
        '@router.get("/release-readiness")\n',
        encoding="utf-8",
    )
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
    }
    paths["readiness"].write_text(json.dumps(_readiness()) + "\n", encoding="utf-8")
    paths["work_order"].write_text(json.dumps(_work_order()) + "\n", encoding="utf-8")
    paths["preflight"].write_text(json.dumps(_preflight()) + "\n", encoding="utf-8")
    paths["structure_report"].write_text(json.dumps(_structure_report()) + "\n", encoding="utf-8")
    paths["bundle"].write_text(json.dumps(_bundle()) + "\n", encoding="utf-8")
    paths["delivery"].write_text(json.dumps(_delivery()) + "\n", encoding="utf-8")
    paths["pilot"].write_text(json.dumps(_pilot()) + "\n", encoding="utf-8")
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
    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["product_architecture_endpoint_present"] is True
    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["product_service_boundary_endpoint_present"] is True
    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["product_api_contract_endpoint_present"] is True
    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["product_operational_quality_endpoint_present"] is True
    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["product_license_decision_endpoint_present"] is True
    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["product_license_options_endpoint_present"] is True
    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["product_license_file_work_order_endpoint_present"] is True
    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["product_cli_surface_present"] is True
    assert out_csv.read_text(encoding="utf-8").startswith("capability_id,domain,")
    assert "Product Capability Surface Contract" in out_md.read_text(encoding="utf-8")
    assert "result_bundle_generation_contract_ready" in out_md.read_text(encoding="utf-8")
    assert "delivery_claim_backed_by_bundle_validation" in out_md.read_text(encoding="utf-8")
